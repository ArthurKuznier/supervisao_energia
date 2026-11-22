import sqlite3
import socket
import subprocess
import sys
from time import monotonic, sleep
from copy import deepcopy

import pytest

from controllers.main_controller import MainController
from database import config_manager, connection
from models.dispositivo_repository import DispositivoRepository
from models.monitoramento import Monitoramento
from models.telemetria import LeituraTelemetria
from views.main_window import MainWindow


def aguardar(app, condicao):
    fim = monotonic() + 5
    while not condicao() and monotonic() < fim:
        app.processEvents()
        sleep(0.005)
    assert condicao(), "A operação assíncrona não terminou."


def criar_controller(view, config, app):
    controller = MainController(view, config)
    try:
        aguardar(app, lambda: controller.pronto)
    except BaseException:
        controller.encerrar()
        aguardar(app, lambda: controller.encerrado)
        raise
    return controller


def sincronizar(controller, app):
    concluido = []
    controller._solicitar("consultar", {"limite": 1}, lambda dados: concluido.append(True))
    aguardar(app, lambda: bool(concluido))


@pytest.fixture
def banco(tmp_path, monkeypatch):
    monkeypatch.setattr(connection, "DB_PATH", str(tmp_path / "smartgrid.db"))
    monkeypatch.setattr(config_manager, "CONFIG_PATH", str(tmp_path / "config.json"))
    connection.init_db()


def test_corte_e_rearme_persistem_estado_e_evento_atomicamente(banco):
    DispositivoRepository.acionar("DISJ-PRINCIPAL", "ABERTO")
    assert DispositivoRepository.buscar_por_tag("DISJ-PRINCIPAL")["status"] == "ABERTO"
    DispositivoRepository.acionar("DISJ-PRINCIPAL", "FECHADO")
    with connection.get_connection() as conn:
        tipos = [r[0] for r in conn.execute("SELECT tipo_evento FROM historico_eventos ORDER BY id")]
    assert tipos == ["Corte Emergencial", "Rearme"]


def test_falha_ao_gravar_evento_reverte_mudanca_do_disjuntor(banco):
    with connection.get_connection() as conn:
        conn.execute("CREATE TRIGGER falha BEFORE INSERT ON historico_eventos BEGIN SELECT RAISE(ABORT, 'falha'); END")
    with pytest.raises(sqlite3.IntegrityError):
        DispositivoRepository.acionar("DISJ-PRINCIPAL", "ABERTO")
    assert DispositivoRepository.buscar_por_tag("DISJ-PRINCIPAL")["status"] == "FECHADO"


def test_model_aplica_regras_personalizadas_e_corte():
    model = Monitoramento({})
    model.atualizar_regras([
        {"parametro": "Corrente", "valor": 5, "unidade": "A"},
        {"parametro": "Tensão", "valor": 230, "unidade": "V"},
    ])
    assert len(model.avaliar(LeituraTelemetria(220, 6))) == 1
    model.atualizar_disjuntor("ABERTO")
    assert model.gerar_leitura_simulada().potencia == 0
    assert model.avaliar(LeituraTelemetria(240, 20)) == []


def test_fluxo_completo_com_simulador(app, banco):
    with socket.socket() as reserva:
        reserva.bind(("127.0.0.1", 0))
        porta = reserva.getsockname()[1]
    processo = subprocess.Popen(
        [sys.executable, "simulador.py", "--tcp", str(porta)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    controller = None
    try:
        assert "aguardando" in processo.stdout.readline()
        config = deepcopy(config_manager._DEFAULT_CONFIG)
        config["serial"].update(porta=f"socket://127.0.0.1:{porta}", intervalo_amostragem_ms=100)
        view = MainWindow()
        erros = []
        view.erro = lambda *args: erros.append(args)
        controller = criar_controller(view, config, app)
        assert controller.model.potencias == []
        for baud in (9600, 19200, 38400, 115200):
            antes = controller.model.contador
            controller.conectar_serial({**config["serial"], "baud_rate": str(baud)})
            aguardar(app, lambda: controller.conectado or bool(erros))
            assert not erros, erros
            aguardar(app, lambda: controller.model.contador > antes)
            if baud != 115200:
                controller.desconectar_serial()
                aguardar(app, lambda: view.ui.lbl_status_conexao.text() == "● Desconectado")
        controller.acionar_disjuntor("ABERTO")
        aguardar(app, lambda: controller.model.disjuntor.estado == "ABERTO")
        aguardar(app, lambda: view.ui.lbl_potencia_valor.text() == "0.0 W")
        controller.acionar_disjuntor("FECHADO")
        aguardar(app, lambda: controller.model.disjuntor.estado == "FECHADO")
        sincronizar(controller, app)
        controller.pedir_historico({"limite": 3})
        aguardar(app, lambda: controller.modo_historico)
        curva = [list(eixo) for eixo in view.ui.curva_consumo.getData()]
        antes = controller.model.contador
        aguardar(app, lambda: controller.model.contador > antes)
        assert [list(eixo) for eixo in view.ui.curva_consumo.getData()] == curva
        controller.voltar_tempo_real()
        assert not controller.modo_historico
        assert list(view.ui.curva_consumo.getData()[1]) == controller.model.potencias
        processo.terminate()
        processo.wait(timeout=5)
        aguardar(app, lambda: bool(erros))
        assert not controller.conectado
    finally:
        if controller is not None:
            controller.encerrar()
            aguardar(app, lambda: controller.encerrado)
        if processo.poll() is None:
            processo.terminate()
        processo.wait(timeout=5)
        processo.stdout.close()
    with connection.get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM leituras WHERE origem = 'serial'").fetchone()[0] >= 4
        tipos = {linha[0] for linha in conn.execute("SELECT tipo_evento FROM historico_eventos")}
        assert {"Corte Emergencial", "Rearme"} <= tipos
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
