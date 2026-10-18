import random
import sqlite3
import logging
from datetime import datetime, timedelta

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMainWindow, QMessageBox, QTableWidgetItem

from ui.Ui_main_window import Ui_MainWindow
from controllers.limits_controller import LimitsDialog
from models.evento_repository import EventoRepository
from models.dispositivo_repository import DispositivoRepository
from models.regra_repository import RegraRepository
from database.config_manager import salvar_config

try:
    from serial.tools import list_ports
    PYSERIAL_DISPONIVEL = True
except ImportError:
    PYSERIAL_DISPONIVEL = False

logger = logging.getLogger("smartgrid")


class MainController(QMainWindow):
    def __init__(self, config: dict = None):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self._config = config or {}
        self.disjuntor_fechado = True
        self.conectado = False
        self.historico_potencia = []
        self.historico_x = []
        self.contador_amostras = 0

        self.regras_limite = self._carregar_regras_do_banco()

        self._aplicar_config()
        self._popular_portas_seriais()
        self._carregar_dados_iniciais_grafico()
        self._conectar_sinais()
        self._carregar_historico_na_tabela()
        self._sincronizar_estado_disjuntor()
        self._iniciar_simulacao_telemetria()

    def _aplicar_config(self):
        serial_cfg = self._config.get("serial", {})
        alertas_cfg = self._config.get("alertas", {})

        baud = str(serial_cfg.get("baud_rate", "9600"))
        idx = self.ui.combo_baud.findText(baud)
        if idx >= 0:
            self.ui.combo_baud.setCurrentIndex(idx)

        timeout = serial_cfg.get("timeout_s", 5)
        self.ui.spin_timeout.setValue(int(timeout))

        limite_w = alertas_cfg.get("limite_potencia_w", 2000.0)
        self.ui.spin_limite_alerta.setValue(float(limite_w))

    def _popular_portas_seriais(self):
        portas = []
        if PYSERIAL_DISPONIVEL:
            portas = [p.device for p in list_ports.comports()]
        if not portas:
            portas = [f"COM{i}" for i in range(1, 7)]

        self.ui.combo_porta.addItems(portas)

        porta_salva = self._config.get("serial", {}).get("porta", "")
        idx = self.ui.combo_porta.findText(porta_salva)
        if idx >= 0:
            self.ui.combo_porta.setCurrentIndex(idx)

    def _carregar_regras_do_banco(self) -> list:
        try:
            regras_db = RegraRepository.listar_todos()
            if regras_db:
                return [
                    {"parametro": r["parametro"],
                     "valor": r["valor_limite"],
                     "unidade": r["unidade"]}
                    for r in regras_db
                ]
        except sqlite3.Error as exc:
            logger.error("Falha ao carregar regras do banco: %s", exc)

        alertas = self._config.get("alertas", {})
        defaults = [
            {"parametro": "Limite Máximo de Corrente",
             "valor": alertas.get("limite_corrente_a", 10.0), "unidade": "A"},
            {"parametro": "Limite Máximo de Tensão",
             "valor": alertas.get("limite_tensao_v", 230.0), "unidade": "V"},
        ]
        try:
            RegraRepository.substituir_todas(defaults)
        except sqlite3.Error:
            pass
        return defaults

    def _carregar_dados_iniciais_grafico(self):
        agora = datetime.now()
        potencias = []
        base = 1200
        for h in range(23, -1, -1):
            hora_do_dia = (agora - timedelta(hours=h)).hour
            fator = 1.0 + 0.6 * abs((hora_do_dia - 19) % 24 - 12) / 12
            potencias.append(round(base * fator + random.uniform(-80, 80), 1))

        self.historico_potencia = potencias
        self.historico_x = list(range(len(potencias)))
        self.contador_amostras = len(potencias)
        self.ui.curva_consumo.setData(self.historico_x, self.historico_potencia)

    def _conectar_sinais(self):
        self.ui.btn_corte_emergencial.clicked.connect(self.corte_emergencial)
        self.ui.btn_rearmar_disjuntor.clicked.connect(self.rearmar_disjuntor)
        self.ui.btn_conectar.clicked.connect(self.conectar_serial)
        self.ui.btn_desconectar.clicked.connect(self.desconectar_serial)
        self.ui.btn_config_limites.clicked.connect(self.abrir_config_limites)
        self.ui.actionLimites.triggered.connect(self.abrir_config_limites)

    def _carregar_historico_na_tabela(self):
        try:
            eventos = EventoRepository.listar_todos()
            tabela = self.ui.table_eventos
            tabela.setRowCount(0)
            for ev in eventos:
                linha = tabela.rowCount()
                tabela.insertRow(linha)
                tabela.setItem(linha, 0, QTableWidgetItem(ev["data_hora"]))
                tabela.setItem(linha, 1, QTableWidgetItem(ev["tipo_evento"]))
                tabela.setItem(linha, 2, QTableWidgetItem(ev["descricao"]))
        except sqlite3.Error as exc:
            logger.error("Falha ao carregar histórico na tabela: %s", exc)

    def _sincronizar_estado_disjuntor(self):
        try:
            dispositivo = DispositivoRepository.buscar_por_tag("DISJ-PRINCIPAL")
            if dispositivo:
                aberto = dispositivo["status"] == "ABERTO"
                self.disjuntor_fechado = not aberto
                self._atualizar_led_disjuntor()
                self.ui.btn_corte_emergencial.setEnabled(not aberto)
                self.ui.btn_rearmar_disjuntor.setEnabled(aberto)
        except sqlite3.Error as exc:
            logger.error("Falha ao sincronizar estado do disjuntor: %s", exc)

    def _iniciar_simulacao_telemetria(self):
        self.timer_telemetria = QTimer(self)
        self.timer_telemetria.setInterval(2000)
        self.timer_telemetria.timeout.connect(self.atualizar_telemetria)
        self.timer_telemetria.start()
        self.atualizar_telemetria()

    def atualizar_telemetria(self):
        if not self.disjuntor_fechado:
            tensao, corrente, potencia = 0.0, 0.0, 0.0
        else:
            tensao = round(random.uniform(215.0, 235.0), 1)
            corrente = round(random.uniform(2.0, 12.0), 2)
            potencia = round(tensao * corrente, 1)

        self.ui.lbl_tensao_valor.setText(f"{tensao} V")
        self.ui.lbl_corrente_valor.setText(f"{corrente} A")
        self.ui.lbl_potencia_valor.setText(f"{potencia} W")

        self._atualizar_grafico(potencia)

        if self.disjuntor_fechado:
            self._verificar_limites(tensao, corrente, potencia)

    def _atualizar_grafico(self, nova_potencia):
        self.historico_potencia.append(nova_potencia)
        self.historico_x.append(self.contador_amostras)
        self.contador_amostras += 1
        self.historico_potencia = self.historico_potencia[-24:]
        self.historico_x = self.historico_x[-24:]
        self.ui.curva_consumo.setData(self.historico_x, self.historico_potencia)

    def _verificar_limites(self, tensao, corrente, potencia):
        limite_alerta_potencia = self.ui.spin_limite_alerta.value()
        if potencia > limite_alerta_potencia:
            msg = (f"Potência ({potencia} W) acima do limite "
                   f"configurado ({limite_alerta_potencia} W).")
            logger.warning("Limite de potência violado: %.1f W (Limite: %.1f W).",
                           potencia, limite_alerta_potencia)
            self.registrar_evento("Alerta", msg, valor_medido=potencia)

        for regra in self.regras_limite:
            if regra["unidade"] == "A" and corrente > regra["valor"]:
                msg = (f"Corrente ({corrente} A) ultrapassou "
                       f"'{regra['parametro']}' ({regra['valor']} A).")
                logger.warning("Limite de corrente violado: %.2f A (Limite configurado: %.1f A).",
                               corrente, regra["valor"])
                self.registrar_evento("Alerta", msg, valor_medido=corrente)
            elif regra["unidade"] == "V" and tensao > regra["valor"]:
                msg = (f"Tensão ({tensao} V) ultrapassou "
                       f"'{regra['parametro']}' ({regra['valor']} V).")
                logger.warning("Limite de tensão violado: %.1f V (Limite configurado: %.1f V).",
                               tensao, regra["valor"])
                self.registrar_evento("Alerta", msg, valor_medido=tensao)

    def corte_emergencial(self):
        resposta = QMessageBox.question(
            self, "Confirmar Corte Emergencial",
            "Tem certeza que deseja executar o corte emergencial de carga?\n"
            "Isso irá abrir o disjuntor/chave de proteção.",
            QMessageBox.Yes | QMessageBox.No)

        if resposta != QMessageBox.Yes:
            return

        try:
            from database.connection import get_connection
            agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

            with get_connection() as conn:
                conn.execute(
                    "UPDATE dispositivos SET status = ?, ultima_atualizacao = ? WHERE tag = ?",
                    ("ABERTO", agora, "DISJ-PRINCIPAL"),
                )
                conn.execute(
                    "INSERT INTO historico_eventos "
                    "(data_hora, tipo_evento, valor_medido, descricao) VALUES (?, ?, ?, ?)",
                    (agora, "Corte Emergencial", None,
                     "Disjuntor aberto manualmente pelo operador."),
                )
            self.disjuntor_fechado = False
            self._atualizar_led_disjuntor()
            self.ui.btn_corte_emergencial.setEnabled(False)
            self.ui.btn_rearmar_disjuntor.setEnabled(True)
            self._inserir_evento_na_tabela(agora, "Corte Emergencial",
                                           "Disjuntor aberto manualmente pelo operador.")
            logger.info("Corte emergencial executado. Disjuntor ABERTO.")

        except sqlite3.Error as exc:
            logger.error(
                "Falha na operação de corte emergencial. Rollback executado: %s", exc)
            QMessageBox.critical(
                self, "Erro — Corte Emergencial",
                f"Falha ao executar o corte emergencial.\n"
                f"O banco foi revertido (ROLLBACK).\n\nDetalhes: {exc}")

    def rearmar_disjuntor(self):
        resposta = QMessageBox.question(
            self, "Rearmar Disjuntor",
            "Confirma o rearme do disjuntor e o restabelecimento da carga?",
            QMessageBox.Yes | QMessageBox.No)

        if resposta != QMessageBox.Yes:
            return

        try:
            from database.connection import get_connection
            agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

            with get_connection() as conn:
                conn.execute(
                    "UPDATE dispositivos SET status = ?, ultima_atualizacao = ? WHERE tag = ?",
                    ("FECHADO", agora, "DISJ-PRINCIPAL"),
                )
                conn.execute(
                    "INSERT INTO historico_eventos "
                    "(data_hora, tipo_evento, valor_medido, descricao) VALUES (?, ?, ?, ?)",
                    (agora, "Rearme", None,
                     "Disjuntor rearmado e carga restabelecida pelo operador."),
                )

            self.disjuntor_fechado = True
            self._atualizar_led_disjuntor()
            self.ui.btn_corte_emergencial.setEnabled(True)
            self.ui.btn_rearmar_disjuntor.setEnabled(False)
            self._inserir_evento_na_tabela(agora, "Rearme",
                                           "Disjuntor rearmado e carga restabelecida pelo operador.")
            logger.info("Disjuntor rearmado. Carga restabelecida.")

        except sqlite3.Error as exc:
            logger.error("Falha no rearme do disjuntor. Rollback executado: %s", exc)
            QMessageBox.critical(
                self, "Erro — Rearme",
                f"Falha ao rearmar o disjuntor.\nRollback executado.\n\nDetalhes: {exc}")

    def conectar_serial(self):
        porta = self.ui.combo_porta.currentText()
        baud = self.ui.combo_baud.currentText()
        timeout = self.ui.spin_timeout.value()

        self.conectado = True
        self.ui.lbl_status_conexao.setText(f"● Conectado ({porta} @ {baud})")
        self.ui.lbl_status_conexao.setStyleSheet("color:#1e8449; font-weight:bold;")
        self.ui.btn_conectar.setEnabled(False)
        self.ui.btn_desconectar.setEnabled(True)
        self.ui.combo_porta.setEnabled(False)
        self.ui.combo_baud.setEnabled(False)

        self._config.setdefault("serial", {})
        self._config["serial"]["porta"] = porta
        self._config["serial"]["baud_rate"] = baud
        self._config["serial"]["timeout_s"] = timeout
        try:
            salvar_config(self._config)
        except OSError:
            pass

        self.registrar_evento("Conexão", f"Conectado à porta {porta} (baud rate {baud}).")
        logger.info("Conexão serial estabelecida: %s @ %s baud.", porta, baud)

    def desconectar_serial(self):
        self.conectado = False
        self.ui.lbl_status_conexao.setText("● Desconectado")
        self.ui.lbl_status_conexao.setStyleSheet("color:#c0392b; font-weight:bold;")
        self.ui.btn_conectar.setEnabled(True)
        self.ui.btn_desconectar.setEnabled(False)
        self.ui.combo_porta.setEnabled(True)
        self.ui.combo_baud.setEnabled(True)

        self.registrar_evento("Conexão", "Conexão serial encerrada pelo operador.")
        logger.info("Conexão serial encerrada.")

    def abrir_config_limites(self):
        dialogo = LimitsDialog(regras_atuais=self.regras_limite, parent=self)
        if dialogo.exec() == LimitsDialog.Accepted:
            novas_regras = dialogo.get_regras()
            try:
                RegraRepository.substituir_todas(novas_regras)
                self.regras_limite = novas_regras
                self.registrar_evento(
                    "Configuração",
                    f"Regras de limite atualizadas ({len(novas_regras)} regra(s)).")
                logger.info("Regras de limite atualizadas pelo operador: %d regra(s).",
                            len(novas_regras))
            except sqlite3.Error as exc:
                logger.error("Falha ao salvar regras de limite: %s", exc)
                QMessageBox.critical(
                    self, "Erro ao Salvar",
                    f"Não foi possível salvar as regras no banco.\n\nDetalhes: {exc}")

    def registrar_evento(self, tipo: str, descricao: str,
                         valor_medido: float = None):
        try:
            EventoRepository.inserir(tipo, descricao, valor_medido)
        except sqlite3.Error as exc:
            logger.error("Falha ao persistir evento '%s': %s", tipo, exc)

        agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        self._inserir_evento_na_tabela(agora, tipo, descricao)

    def _inserir_evento_na_tabela(self, data_hora: str, tipo: str, descricao: str):
        tabela = self.ui.table_eventos
        tabela.insertRow(0)
        tabela.setItem(0, 0, QTableWidgetItem(data_hora))
        tabela.setItem(0, 1, QTableWidgetItem(tipo))
        tabela.setItem(0, 2, QTableWidgetItem(descricao))

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