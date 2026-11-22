import sqlite3
from copy import deepcopy

import pytest
from PySide6.QtCore import QTimer

from controllers.main_controller import MainController
from database import config_manager, connection
from models.dispositivo_repository import DispositivoRepository
from models.monitoramento import Monitoramento
from models.telemetria import LeituraTelemetria
from views.limits_dialog import LimitsDialog
from views.main_window import MainWindow


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
    controller = MainController(view, deepcopy(config_manager._DEFAULT_CONFIG))
    try:
        assert not isinstance(controller, MainWindow)
        assert controller.timer.isActive()
        assert len(view.ui.curva_consumo.getData()[0]) == 24
        assert view.ui.grp_grafico.title() == "Histórico de Consumo - Últimas 24 horas"
        assert not view.ui.combo_porta.isEditable()
        controller.acionar_disjuntor("ABERTO")
        assert view.ui.lbl_status_disjuntor.text() == "ABERTO"
        assert not view.ui.btn_corte_emergencial.isEnabled()
        controller.atualizar_telemetria()
        assert view.ui.lbl_potencia_valor.text() == "0.0 W"
        assert view.ui.btn_rearmar_disjuntor.isEnabled()
        controller.acionar_disjuntor("FECHADO")
        assert view.ui.lbl_status_disjuntor.text() == "FECHADO"
        controller.conectar_serial({"porta": "COM_TESTE", "baud_rate": "9600", "timeout_s": 5})
        assert controller.conectado
        assert view.ui.lbl_status_conexao.text() == "● Conectado (COM_TESTE @ 9600)"
        assert config_manager.carregar_config()["serial"]["porta"] == "COM_TESTE"
        controller.desconectar_serial()
        assert not controller.conectado
        assert view.ui.lbl_status_conexao.text() == "● Desconectado"
    finally:
        controller.encerrar()
    assert not controller.timer.isActive()


def test_adicionar_regra_pelo_botao_nao_recebe_booleano(app):
    dialogo = LimitsDialog()
    dialogo.ui.btn_adicionar_regra.click()
    assert dialogo.ui.table_regras.rowCount() == 3
    assert dialogo.get_regras()[-1]["parametro"] == "Nova regra"
    dialogo.close()


def test_validacao_mantem_dialogo_aberto_ate_corrigir_regra(app, banco, monkeypatch):
    view = MainWindow()
    controller = MainController(view, deepcopy(config_manager._DEFAULT_CONFIG))
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
        assert controller.model.regras[0]["unidade"] == "A"
    finally:
        controller.encerrar()
