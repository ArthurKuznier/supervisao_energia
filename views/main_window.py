from PySide6.QtCore import Signal
from PySide6.QtWidgets import QMainWindow, QMessageBox, QTableWidgetItem

from ui.Ui_main_window import Ui_MainWindow
from views.limits_dialog import LimitsDialog


class MainWindow(QMainWindow):
    conectar_solicitado = Signal(dict)
    desconectar_solicitado = Signal()
    limites_solicitados = Signal()
    disjuntor_solicitado = Signal(str)
    fechar_solicitado = Signal()
    limite_potencia_alterado = Signal(float)
    validacao_limites_solicitada = Signal(list)

    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self._pode_fechar = False
        self._dialogo_limites = None
        self.ui.btn_conectar.clicked.connect(self._pedir_conexao)
        self.ui.btn_desconectar.clicked.connect(self.desconectar_solicitado.emit)
        self.ui.btn_config_limites.clicked.connect(self.limites_solicitados.emit)
        self.ui.actionLimites.triggered.connect(self.limites_solicitados.emit)
        self.ui.btn_corte_emergencial.clicked.connect(lambda: self._pedir_disjuntor("ABERTO"))
        self.ui.btn_rearmar_disjuntor.clicked.connect(lambda: self._pedir_disjuntor("FECHADO"))
        self.ui.spin_limite_alerta.valueChanged.connect(self.limite_potencia_alterado.emit)

    def configurar(self, config):
        serial = config.get("serial", {})
        self.ui.combo_porta.setCurrentText(serial.get("porta", self.ui.combo_porta.currentText()))
        self.ui.combo_baud.setCurrentText(str(serial.get("baud_rate", "9600")))
        self.ui.spin_timeout.setValue(int(serial.get("timeout_s", 5)))
        self.ui.spin_limite_alerta.setValue(config.get("alertas", {}).get("limite_potencia_w", 2000.0))

    def _pedir_conexao(self):
        self.conectar_solicitado.emit({"porta": self.ui.combo_porta.currentText().strip(),
                                     "baud_rate": self.ui.combo_baud.currentText(),
                                     "timeout_s": self.ui.spin_timeout.value()})

    def _pedir_disjuntor(self, estado):
        if estado == "ABERTO":
            titulo = "Confirmar Corte Emergencial"
            mensagem = "Tem certeza que deseja executar o corte emergencial de carga?\nIsso irá abrir o disjuntor/chave de proteção."
        else:
            titulo = "Rearmar Disjuntor"
            mensagem = "Confirma o rearme do disjuntor e o restabelecimento da carga?"
        if QMessageBox.question(self, titulo, mensagem, QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.disjuntor_solicitado.emit(estado)

    def mostrar_portas(self, portas):
        self.ui.combo_porta.clear()
        self.ui.combo_porta.addItems(portas)

    def editar_limites(self, regras):
        dialogo = LimitsDialog(regras, self)
        self._dialogo_limites = dialogo
        dialogo.salvar_solicitado.connect(self.validacao_limites_solicitada.emit)
        try:
            return dialogo.get_regras() if dialogo.exec() == LimitsDialog.Accepted else None
        finally:
            self._dialogo_limites = None

    def concluir_validacao_limites(self, erro=None):
        if erro is not None:
            QMessageBox.warning(self._dialogo_limites, erro.titulo, str(erro))
        else:
            self._dialogo_limites.accept()

    def mostrar_eventos(self, eventos):
        self.ui.table_eventos.setRowCount(0)
        for evento in reversed(eventos):
            self.inserir_evento(evento)

    def mostrar_conexao(self, texto, ocupado=False, conectado=False):
        self.ui.lbl_status_conexao.setText(texto)
        cor = "#1e8449" if conectado else "#c0392b"
        self.ui.lbl_status_conexao.setStyleSheet(f"color:{cor}; font-weight:bold;")
        self.ui.btn_conectar.setEnabled(not ocupado and not conectado)
        self.ui.btn_desconectar.setEnabled(ocupado or conectado)
        self.ui.combo_porta.setEnabled(not ocupado and not conectado)
        self.ui.combo_baud.setEnabled(not ocupado and not conectado)

    def mostrar_leitura(self, registro):
        self.ui.lbl_tensao_valor.setText(f"{registro['tensao']} V")
        self.ui.lbl_corrente_valor.setText(f"{registro['corrente']} A")
        self.ui.lbl_potencia_valor.setText(f"{registro['potencia']} W")

    def plotar(self, x, y):
        self.ui.curva_consumo.setData(x, y)

    def mostrar_disjuntor(self, estado, habilitado=False):
        self.ui.lbl_status_disjuntor.setText(estado)
        if estado == "FECHADO":
            self.ui.led_disjuntor.setStyleSheet(
                "background-color:#2ecc71; border-radius:11px; border:2px solid #1e8449;")
            self.ui.lbl_status_disjuntor.setStyleSheet(
                "font-weight:bold; font-size:14px; padding:4px 10px; "
                "border-radius:6px; background-color:#e8f8f0; color:#1e8449;")
        else:
            self.ui.led_disjuntor.setStyleSheet(
                "background-color:#e74c3c; border-radius:11px; border:2px solid #922b21;")
            self.ui.lbl_status_disjuntor.setStyleSheet(
                "font-weight:bold; font-size:14px; padding:4px 10px; "
                "border-radius:6px; background-color:#fdecea; color:#922b21;")
        self.ui.btn_corte_emergencial.setEnabled(habilitado and estado == "FECHADO")
        self.ui.btn_rearmar_disjuntor.setEnabled(habilitado and estado == "ABERTO")

    def inserir_evento(self, evento):
        tabela = self.ui.table_eventos
        tabela.insertRow(0)
        for coluna, chave in enumerate(("data_hora", "tipo_evento", "descricao")):
            tabela.setItem(0, coluna, QTableWidgetItem(str(evento.get(chave, ""))))

    def erro(self, texto, titulo="Smart Grid"):
        QMessageBox.critical(self, titulo, texto)

    def closeEvent(self, event):
        if self._pode_fechar:
            event.accept()
        else:
            event.ignore()
            self.fechar_solicitado.emit()

    def permitir_fechamento(self):
        self._pode_fechar = True
        self.close()
