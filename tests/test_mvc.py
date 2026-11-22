import sqlite3
from time import monotonic
from copy import deepcopy

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtTest import QTest

from controllers.main_controller import MainController
from database import config_manager, connection
from models.dispositivo_repository import DispositivoRepository
from models.monitoramento import Monitoramento
from models.telemetria import LeituraTelemetria
from views.limits_dialog import LimitsDialog
from views.main_window import MainWindow


def aguardar(app, condicao):
    fim = monotonic() + 5
    while not condicao() and monotonic() < fim:
        app.processEvents()
        QTest.qWait(1)
    assert condicao(), "A operação assíncrona não terminou."


def criar_controller(view, config, app):
    controller = MainController(view, config)
    aguardar(app, lambda: controller.pronto)
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


def test_janela_recebe_eventos_sem_ser_controller(app, banco):
    view = MainWindow()
    controller = criar_controller(view, deepcopy(config_manager._DEFAULT_CONFIG), app)
    try:
        assert not isinstance(controller, MainWindow)
        assert controller.timer.isActive()
        assert len(view.ui.curva_consumo.getData()[0]) == 24
        assert view.ui.grp_grafico.title() == "Histórico de Consumo - Últimas 24 horas"
        assert not view.ui.combo_porta.isEditable()
        controller.acionar_disjuntor("ABERTO")
        sincronizar(controller, app)
        assert view.ui.lbl_status_disjuntor.text() == "ABERTO"
        assert not view.ui.btn_corte_emergencial.isEnabled()
        controller.atualizar_telemetria()
        assert view.ui.lbl_potencia_valor.text() == "0.0 W"
        assert view.ui.btn_rearmar_disjuntor.isEnabled()
        controller.acionar_disjuntor("FECHADO")
        sincronizar(controller, app)
        assert view.ui.lbl_status_disjuntor.text() == "FECHADO"
        controller.conectar_serial({"porta": "COM_TESTE", "baud_rate": "9600", "timeout_s": 5})
        sincronizar(controller, app)
        assert controller.conectado
        assert view.ui.lbl_status_conexao.text() == "● Conectado (COM_TESTE @ 9600)"
        assert config_manager.carregar_config()["serial"]["porta"] == "COM_TESTE"
        controller.desconectar_serial()
        assert not controller.conectado
        assert view.ui.lbl_status_conexao.text() == "● Desconectado"
    finally:
        controller.encerrar()
        aguardar(app, lambda: controller.encerrado)
    assert not controller.timer.isActive()


def test_adicionar_regra_pelo_botao_nao_recebe_booleano(app):
    dialogo = LimitsDialog()
    dialogo.ui.btn_adicionar_regra.click()
    assert dialogo.ui.table_regras.rowCount() == 3
    assert dialogo.get_regras()[-1]["parametro"] == "Nova regra"
    dialogo.close()


def test_validacao_mantem_dialogo_aberto_ate_corrigir_regra(app, banco, monkeypatch):
    view = MainWindow()
    controller = criar_controller(view, deepcopy(config_manager._DEFAULT_CONFIG), app)
    avisos = []
    monkeypatch.setattr("views.main_window.QMessageBox.warning", lambda *args: avisos.append(args))

    def editar():
        dialogo = view._dialogo_limites
        unidade = dialogo.ui.table_regras.item(0, 2)
        unidade.setText("")
        dialogo.salvar()
        assert dialogo.isVisible()
        assert avisos[-1][1] == "Campo Inválido"
        unidade.setText("A")
        dialogo.salvar()
    try:
        QTimer.singleShot(0, editar)
        controller.editar_limites()
        sincronizar(controller, app)
        assert controller.model.regras[0]["unidade"] == "A"
        config = config_manager.carregar_config()
        assert config["regras_limite"] == controller.model.regras
        assert config["alertas"]["limite_corrente_a"] == controller.model.regras[0]["valor"]
    finally:
        controller.encerrar()
        aguardar(app, lambda: controller.encerrado)


def test_aplica_intervalo_salvo_e_persiste_limite_potencia(app, banco):
    config = deepcopy(config_manager._DEFAULT_CONFIG)
    config["serial"]["intervalo_amostragem_ms"] = 750
    view = MainWindow()
    controller = criar_controller(view, config, app)
    try:
        assert controller.timer.interval() == 750
        view.ui.spin_limite_alerta.setValue(3500)
        sincronizar(controller, app)
        salvo = config_manager.carregar_config()
        assert salvo["alertas"]["limite_potencia_w"] == 3500
        assert controller.model.limite_potencia == 3500
        controller.conectar_serial({"porta": "COM8", "baud_rate": "9600", "timeout_s": 5})
        sincronizar(controller, app)
        assert config_manager.carregar_config()["serial"]["intervalo_amostragem_ms"] == 750
    finally:
        controller.encerrar()
        aguardar(app, lambda: controller.encerrado)


def test_regras_salvas_no_json_sao_restauradas_no_model_e_banco(app, banco):
    config = deepcopy(config_manager._DEFAULT_CONFIG)
    regras = [
        {"parametro": "Corrente personalizada", "valor": 7.5, "unidade": "A"},
        {"parametro": "Tensão personalizada", "valor": 225, "unidade": "V"},
    ]
    config["regras_limite"] = regras
    config_manager.salvar_config(config)
    view = MainWindow()
    controller = criar_controller(view, config_manager.carregar_config(), app)
    try:
        assert controller.model.regras == regras
        with connection.get_connection() as conn:
            assert [r[0] for r in conn.execute("SELECT valor_limite FROM regras_limite ORDER BY id")] == [7.5, 225]
    finally:
        controller.encerrar()
        aguardar(app, lambda: controller.encerrado)


def test_sql_fora_da_gui_e_resultados_na_thread_principal(app, banco, monkeypatch):
    from threading import get_ident

    thread_gui = get_ident()
    threads_sql, threads_view = [], []
    conectar = connection.sqlite3.connect

    def registrar_conexao(*args, **kwargs):
        threads_sql.append(get_ident())
        return conectar(*args, **kwargs)

    monkeypatch.setattr(connection.sqlite3, "connect", registrar_conexao)
    view = MainWindow()
    inserir = view.inserir_evento

    def mostrar(evento):
        threads_view.append(get_ident())
        inserir(evento)

    monkeypatch.setattr(view, "inserir_evento", mostrar)
    controller = criar_controller(view, deepcopy(config_manager._DEFAULT_CONFIG), app)
    historicos = []
    controller.historico_recebido.connect(historicos.append)
    try:
        controller.registrar_evento("Teste", "Evento pela fila")
        controller.consultar_historico(limite=10)
        aguardar(app, lambda: bool(historicos))
        assert historicos[0][0]["origem"] == "simulacao"
        assert threads_sql and all(thread != thread_gui for thread in threads_sql)
        assert threads_view and all(thread == thread_gui for thread in threads_view)
        for _ in range(10):
            controller.atualizar_telemetria()
    finally:
        controller.encerrar()
        aguardar(app, lambda: controller.encerrado)
    with connection.get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM leituras").fetchone()[0] >= 11
        assert conn.execute("SELECT dispositivo_id FROM historico_eventos WHERE descricao = 'Evento pela fila'").fetchone()[0] is not None


def test_consulta_lenta_nao_bloqueia_gui_e_worker_recupera_de_erro(app, banco, monkeypatch):
    from time import sleep
    from models.leitura_repository import LeituraRepository

    consultar = LeituraRepository.consultar
    chamadas = []

    def consulta_lenta(**filtros):
        chamadas.append(True)
        if len(chamadas) == 1:
            raise ValueError("Falha de consulta simulada")
        sleep(0.15)
        return consultar(**filtros)

    monkeypatch.setattr(LeituraRepository, "consultar", consulta_lenta)
    view = MainWindow()
    erros = []
    monkeypatch.setattr(view, "erro", lambda *args: erros.append(args))
    controller = criar_controller(view, deepcopy(config_manager._DEFAULT_CONFIG), app)
    historicos, pulsos = [], []
    controller.historico_recebido.connect(historicos.append)
    timer_gui = QTimer()
    timer_gui.setInterval(10)
    timer_gui.timeout.connect(lambda: pulsos.append(True))
    try:
        controller.consultar_historico(limite=1)
        aguardar(app, lambda: bool(erros))
        timer_gui.start()
        controller.consultar_historico(limite=1)
        aguardar(app, lambda: bool(historicos))
        assert len(pulsos) >= 3
        assert historicos[0]
    finally:
        timer_gui.stop()
        controller.encerrar()
        aguardar(app, lambda: controller.encerrado)
