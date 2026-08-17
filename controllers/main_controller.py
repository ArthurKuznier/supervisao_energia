import random
from datetime import datetime, timedelta

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMainWindow, QMessageBox, QTableWidgetItem

from supervisao_energia.ui.Ui_main_window import Ui_MainWindow
from supervisao_energia.controllers.limits_controller import LimitsDialog

try:
    from serial.tools import list_ports
    PYSERIAL_DISPONIVEL = True
except ImportError:
    PYSERIAL_DISPONIVEL = False


class MainController(QMainWindow):

    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # Estado interno da aplicação (nesta entrega, sem camada de Model)
        self.disjuntor_fechado = True
        self.conectado = False
        self.regras_limite = [
            {"parametro": u"Limite Máximo de Corrente", "valor": 10.0, "unidade": "A"},
            {"parametro": u"Limite Máximo de Tensão", "valor": 230.0, "unidade": "V"},
        ]
        self.historico_potencia = []

        self._popular_portas_seriais()
        self._carregar_dados_iniciais_grafico()
        self._conectar_sinais()
        self._iniciar_simulacao_telemetria()

    def _popular_portas_seriais(self):
        portas = []
        if PYSERIAL_DISPONIVEL:
            portas = [p.device for p in list_ports.comports()]
        if not portas:
            portas = [f"COM{i}" for i in range(1, 7)]
        self.ui.combo_porta.addItems(portas)

    def _carregar_dados_iniciais_grafico(self):
        agora = datetime.now()
        horas = list(range(24, 0, -1))
        potencias = []
        base = 1200
        for h in horas:
            hora_do_dia = (agora - timedelta(hours=h)).hour
            fator = 1.0 + 0.6 * abs((hora_do_dia - 19) % 24 - 12) / 12
            potencias.append(round(base * fator + random.uniform(-80, 80), 1))

        self.historico_potencia = potencias
        self.ui.curva_consumo.setData(horas[::-1], potencias)

    def _conectar_sinais(self):
        self.ui.btn_corte_emergencial.clicked.connect(self.corte_emergencial)
        self.ui.btn_conectar.clicked.connect(self.conectar_serial)
        self.ui.btn_desconectar.clicked.connect(self.desconectar_serial)
        self.ui.btn_config_limites.clicked.connect(self.abrir_config_limites)
        self.ui.actionLimites.triggered.connect(self.abrir_config_limites)

    def _iniciar_simulacao_telemetria(self):
        self.timer_telemetria = QTimer(self)
        self.timer_telemetria.setInterval(2000)  # 2 segundos
        self.timer_telemetria.timeout.connect(self.atualizar_telemetria)
        self.timer_telemetria.start()
        self.atualizar_telemetria()

    def atualizar_telemetria(self):
        tensao = round(random.uniform(215.0, 235.0), 1)
        corrente = round(random.uniform(2.0, 12.0), 2)
        potencia = round(tensao * corrente, 1)

        self.ui.lbl_tensao_valor.setText(f"{tensao} V")
        self.ui.lbl_corrente_valor.setText(f"{corrente} A")
        self.ui.lbl_potencia_valor.setText(f"{potencia} W")

        self._atualizar_grafico(potencia)
        self._verificar_limites(tensao, corrente, potencia)

    def _atualizar_grafico(self, nova_potencia):
        self.historico_potencia.append(nova_potencia)
        self.historico_potencia = self.historico_potencia[-24:]
        horas = list(range(len(self.historico_potencia) - 1, -1, -1))
        self.ui.curva_consumo.setData(horas, self.historico_potencia)

    def _verificar_limites(self, tensao, corrente, potencia):
        limite_alerta_potencia = self.ui.spin_limite_alerta.value()
        if potencia > limite_alerta_potencia:
            self.registrar_evento(
                "Alerta", f"Potência ({potencia} W) acima do limite "
                          f"configurado ({limite_alerta_potencia} W).")

        for regra in self.regras_limite:
            if regra["unidade"] == "A" and corrente > regra["valor"]:
                self.registrar_evento(
                    "Alerta", f"Corrente ({corrente} A) ultrapassou "
                              f"'{regra['parametro']}' ({regra['valor']} A).")
            elif regra["unidade"] == "V" and tensao > regra["valor"]:
                self.registrar_evento(
                    "Alerta", f"Tensão ({tensao} V) ultrapassou "
                              f"'{regra['parametro']}' ({regra['valor']} V).")

    def corte_emergencial(self):
        resposta = QMessageBox.question(
            self, "Confirmar Corte Emergencial",
            "Tem certeza que deseja executar o corte emergencial de carga?\n"
            "Isso irá abrir o disjuntor/chave de proteção.",
            QMessageBox.Yes | QMessageBox.No)

        if resposta != QMessageBox.Yes:
            return

        self.disjuntor_fechado = False
        self._atualizar_led_disjuntor()
        self.registrar_evento(
            "Corte Emergencial", "Disjuntor aberto manualmente pelo operador.")

    def _atualizar_led_disjuntor(self):
        if self.disjuntor_fechado:
            self.ui.led_disjuntor.setStyleSheet(
                "background-color:#2ecc71; border-radius:11px; border:2px solid #1e8449;")
            self.ui.lbl_status_disjuntor.setText("FECHADO")
            self.ui.lbl_status_disjuntor.setStyleSheet(
                "font-weight:bold; font-size:14px; padding:4px 10px; "
                "border-radius:6px; background-color:#e8f8f0; color:#1e8449;")
        else:
            self.ui.led_disjuntor.setStyleSheet(
                "background-color:#e74c3c; border-radius:11px; border:2px solid #922b21;")
            self.ui.lbl_status_disjuntor.setText("ABERTO")
            self.ui.lbl_status_disjuntor.setStyleSheet(
                "font-weight:bold; font-size:14px; padding:4px 10px; "
                "border-radius:6px; background-color:#fdecea; color:#922b21;")

    def conectar_serial(self):
        porta = self.ui.combo_porta.currentText()
        baud = self.ui.combo_baud.currentText()

        self.conectado = True
        self.ui.lbl_status_conexao.setText(f"● Conectado ({porta} @ {baud})")
        self.ui.lbl_status_conexao.setStyleSheet("color:#1e8449; font-weight:bold;")
        self.ui.btn_conectar.setEnabled(False)
        self.ui.btn_desconectar.setEnabled(True)
        self.ui.combo_porta.setEnabled(False)
        self.ui.combo_baud.setEnabled(False)

        self.registrar_evento(
            "Conexão", f"Conectado à porta {porta} (baud rate {baud}).")

    def desconectar_serial(self):
        self.conectado = False
        self.ui.lbl_status_conexao.setText("● Desconectado")
        self.ui.lbl_status_conexao.setStyleSheet("color:#c0392b; font-weight:bold;")
        self.ui.btn_conectar.setEnabled(True)
        self.ui.btn_desconectar.setEnabled(False)
        self.ui.combo_porta.setEnabled(True)
        self.ui.combo_baud.setEnabled(True)

        self.registrar_evento("Conexão", "Conexão serial encerrada pelo operador.")

    def abrir_config_limites(self):
        dialogo = LimitsDialog(regras_atuais=self.regras_limite, parent=self)
        if dialogo.exec() == LimitsDialog.Accepted:
            self.regras_limite = dialogo.get_regras()
            self.registrar_evento(
                "Configuração",
                f"Regras de limite atualizadas ({len(self.regras_limite)} regra(s)).")

    def registrar_evento(self, tipo, descricao):
        tabela = self.ui.table_eventos
        linha = 0
        tabela.insertRow(linha)

        timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        tabela.setItem(linha, 0, QTableWidgetItem(timestamp))
        tabela.setItem(linha, 1, QTableWidgetItem(tipo))
        tabela.setItem(linha, 2, QTableWidgetItem(descricao))
