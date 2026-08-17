# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'main_window.ui'
##
## Widgets dinâmicos (gráfico pyqtgraph, tabela de eventos, cartões de
## telemetria) são montados em código dentro de setupUi() pois dependem
## de componentes que não fazem parte da paleta padrão do Qt Designer
## (ex.: PlotWidget do pyqtgraph). A estrutura de menu/ações permanece
## definida em main_window.ui.
##
## AVISO! Nenhuma regra de negócio deve ser escrita neste arquivo.
## Toda a lógica pertence a /controllers.
################################################################################

from PySide6.QtCore import Qt, QRect, QMetaObject
from PySide6.QtGui import QFont, QAction
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QMenuBar, QMenu, QStatusBar,
    QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QLabel,
    QPushButton, QComboBox, QSpinBox, QDoubleSpinBox, QTableWidget,
    QHeaderView, QFrame, QSizePolicy
)

from pyqtgraph import PlotWidget, mkPen


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(1180, 760)
        MainWindow.setWindowTitle(u"Smart Grid Monitor - Dashboard")

        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        MainWindow.setCentralWidget(self.centralwidget)

        root_layout = QVBoxLayout(self.centralwidget)
        root_layout.setSpacing(12)
        root_layout.setContentsMargins(14, 14, 14, 14)

        linha1 = QHBoxLayout()
        linha1.setSpacing(12)

        self.grp_telemetria = QGroupBox(u"Telemetria em Tempo Real")
        self.grp_telemetria.setObjectName(u"grp_telemetria")
        telemetria_layout = QHBoxLayout(self.grp_telemetria)

        self.lbl_tensao_valor = self._criar_cartao_telemetria(
            telemetria_layout, "lbl_tensao_valor", "Tensão", "-- V")
        self.lbl_corrente_valor = self._criar_cartao_telemetria(
            telemetria_layout, "lbl_corrente_valor", "Corrente", "-- A")
        self.lbl_potencia_valor = self._criar_cartao_telemetria(
            telemetria_layout, "lbl_potencia_valor", "Potência Calculada", "-- W")

        linha1.addWidget(self.grp_telemetria, 3)

        self.grp_disjuntor = QGroupBox(u"Disjuntor / Chave de Proteção")
        self.grp_disjuntor.setObjectName(u"grp_disjuntor")
        disjuntor_layout = QVBoxLayout(self.grp_disjuntor)
        disjuntor_layout.setAlignment(Qt.AlignCenter)

        self.led_disjuntor = QLabel()
        self.led_disjuntor.setObjectName(u"led_disjuntor")
        self.led_disjuntor.setFixedSize(22, 22)
        self.led_disjuntor.setStyleSheet(
            "background-color:#2ecc71; border-radius:11px; border:2px solid #1e8449;")

        self.lbl_status_disjuntor = QLabel(u"FECHADO")
        self.lbl_status_disjuntor.setObjectName(u"lbl_status_disjuntor")
        self.lbl_status_disjuntor.setAlignment(Qt.AlignCenter)
        self.lbl_status_disjuntor.setStyleSheet(
            "font-weight:bold; font-size:14px; padding:4px 10px; "
            "border-radius:6px; background-color:#e8f8f0; color:#1e8449;")

        led_row = QHBoxLayout()
        led_row.setAlignment(Qt.AlignCenter)
        led_row.addWidget(self.led_disjuntor)
        led_row.addWidget(self.lbl_status_disjuntor)

        disjuntor_layout.addLayout(led_row)
        linha1.addWidget(self.grp_disjuntor, 1)

        self.grp_comandos = QGroupBox(u"Comandos de Acionamento")
        self.grp_comandos.setObjectName(u"grp_comandos")
        comandos_layout = QVBoxLayout(self.grp_comandos)

        self.btn_corte_emergencial = QPushButton(u"⚠ Corte Emergencial de Carga")
        self.btn_corte_emergencial.setObjectName(u"btn_corte_emergencial")
        self.btn_corte_emergencial.setMinimumHeight(36)
        self.btn_corte_emergencial.setStyleSheet(
            "QPushButton{background-color:#e74c3c; color:white; font-weight:bold; "
            "border-radius:6px;} QPushButton:hover{background-color:#c0392b;}")

        limite_row = QHBoxLayout()
        self.lbl_limite_alerta = QLabel(u"Limite de alerta de consumo (W):")
        self.spin_limite_alerta = QDoubleSpinBox()
        self.spin_limite_alerta.setObjectName(u"spin_limite_alerta")
        self.spin_limite_alerta.setRange(0, 100000)
        self.spin_limite_alerta.setDecimals(1)
        self.spin_limite_alerta.setValue(2000.0)
        self.spin_limite_alerta.setSuffix(u" W")
        limite_row.addWidget(self.lbl_limite_alerta)
        limite_row.addWidget(self.spin_limite_alerta)

        comandos_layout.addWidget(self.btn_corte_emergencial)
        comandos_layout.addLayout(limite_row)

        linha1.addWidget(self.grp_comandos, 2)
        root_layout.addLayout(linha1)

        linha2 = QHBoxLayout()
        linha2.setSpacing(12)

        self.grp_grafico = QGroupBox(u"Histórico de Consumo - Últimas 24 horas")
        self.grp_grafico.setObjectName(u"grp_grafico")
        grafico_layout = QVBoxLayout(self.grp_grafico)

        self.plot_widget = PlotWidget()
        self.plot_widget.setObjectName(u"plot_widget")
        self.plot_widget.setBackground("w")
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setLabel("left", "Potência (W)")
        self.plot_widget.setLabel("bottom", "Horas atrás")
        self.curva_consumo = self.plot_widget.plot(
            pen=mkPen(color="#2980b9", width=2), symbol="o", symbolSize=5,
            symbolBrush="#2980b9")
        grafico_layout.addWidget(self.plot_widget)

        linha2.addWidget(self.grp_grafico, 3)

        self.grp_serial = QGroupBox(u"Comunicação Serial")
        self.grp_serial.setObjectName(u"grp_serial")
        serial_layout = QGridLayout(self.grp_serial)
        serial_layout.setVerticalSpacing(10)

        self.lbl_porta = QLabel(u"Porta COM:")
        self.combo_porta = QComboBox()
        self.combo_porta.setObjectName(u"combo_porta")

        self.lbl_baud = QLabel(u"Baud Rate:")
        self.combo_baud = QComboBox()
        self.combo_baud.setObjectName(u"combo_baud")
        self.combo_baud.addItems(["9600", "115200"])

        self.lbl_timeout = QLabel(u"Timeout (s):")
        self.spin_timeout = QSpinBox()
        self.spin_timeout.setObjectName(u"spin_timeout")
        self.spin_timeout.setRange(1, 60)
        self.spin_timeout.setValue(5)

        self.btn_conectar = QPushButton(u"Conectar")
        self.btn_conectar.setObjectName(u"btn_conectar")
        self.btn_conectar.setStyleSheet(
            "QPushButton{background-color:#27ae60; color:white; font-weight:bold; "
            "border-radius:6px; padding:6px;} QPushButton:hover{background-color:#1e8449;}")

        self.btn_desconectar = QPushButton(u"Desconectar")
        self.btn_desconectar.setObjectName(u"btn_desconectar")
        self.btn_desconectar.setEnabled(False)
        self.btn_desconectar.setStyleSheet(
            "QPushButton{background-color:#7f8c8d; color:white; font-weight:bold; "
            "border-radius:6px; padding:6px;} QPushButton:hover{background-color:#616a6b;}")

        self.lbl_status_conexao = QLabel(u"● Desconectado")
        self.lbl_status_conexao.setObjectName(u"lbl_status_conexao")
        self.lbl_status_conexao.setStyleSheet("color:#c0392b; font-weight:bold;")
        self.lbl_status_conexao.setAlignment(Qt.AlignCenter)

        self.btn_config_limites = QPushButton(u"Configurar Limites de Alerta...")
        self.btn_config_limites.setObjectName(u"btn_config_limites")

        serial_layout.addWidget(self.lbl_porta, 0, 0)
        serial_layout.addWidget(self.combo_porta, 0, 1)
        serial_layout.addWidget(self.lbl_baud, 1, 0)
        serial_layout.addWidget(self.combo_baud, 1, 1)
        serial_layout.addWidget(self.lbl_timeout, 2, 0)
        serial_layout.addWidget(self.spin_timeout, 2, 1)
        serial_layout.addWidget(self.btn_conectar, 3, 0)
        serial_layout.addWidget(self.btn_desconectar, 3, 1)
        serial_layout.addWidget(self.lbl_status_conexao, 4, 0, 1, 2)

        linha_sep = QFrame()
        linha_sep.setFrameShape(QFrame.HLine)
        serial_layout.addWidget(linha_sep, 5, 0, 1, 2)
        serial_layout.addWidget(self.btn_config_limites, 6, 0, 1, 2)

        linha2.addWidget(self.grp_serial, 2)
        root_layout.addLayout(linha2, 3)

        self.grp_eventos = QGroupBox(u"Histórico de Eventos e Registros")
        self.grp_eventos.setObjectName(u"grp_eventos")
        eventos_layout = QVBoxLayout(self.grp_eventos)

        self.table_eventos = QTableWidget(0, 3)
        self.table_eventos.setObjectName(u"table_eventos")
        self.table_eventos.setHorizontalHeaderLabels([u"Data/Hora", u"Tipo", u"Descrição"])
        self.table_eventos.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table_eventos.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table_eventos.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table_eventos.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_eventos.setSelectionBehavior(QTableWidget.SelectRows)

        eventos_layout.addWidget(self.table_eventos)
        root_layout.addWidget(self.grp_eventos, 2)

        self.menubar = QMenuBar(MainWindow)
        self.menubar.setObjectName(u"menubar")
        self.menuConfiguracoes = QMenu(u"Configurações", self.menubar)
        self.menuConfiguracoes.setObjectName(u"menuConfiguracoes")
        self.actionLimites = QAction(u"Limites de Alerta...", MainWindow)
        self.actionLimites.setObjectName(u"actionLimites")
        self.menuConfiguracoes.addAction(self.actionLimites)
        self.menubar.addMenu(self.menuConfiguracoes)
        MainWindow.setMenuBar(self.menubar)

        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName(u"statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(MainWindow)
        QMetaObject.connectSlotsByName(MainWindow)

    def _criar_cartao_telemetria(self, layout_pai, object_name, titulo, valor_inicial):
        cartao = QFrame()
        cartao.setFrameShape(QFrame.StyledPanel)
        cartao.setStyleSheet(
            "QFrame{background-color:#f4f6f7; border-radius:8px; border:1px solid #d5dbdb;}")
        cartao_layout = QVBoxLayout(cartao)
        cartao_layout.setAlignment(Qt.AlignCenter)

        lbl_titulo = QLabel(titulo)
        lbl_titulo.setAlignment(Qt.AlignCenter)
        lbl_titulo.setStyleSheet("color:#566573; font-size:11px;")

        lbl_valor = QLabel(valor_inicial)
        lbl_valor.setObjectName(object_name)
        lbl_valor.setAlignment(Qt.AlignCenter)
        fonte = QFont()
        fonte.setPointSize(18)
        fonte.setBold(True)
        lbl_valor.setFont(fonte)
        lbl_valor.setStyleSheet("color:#2c3e50;")

        cartao_layout.addWidget(lbl_titulo)
        cartao_layout.addWidget(lbl_valor)
        layout_pai.addWidget(cartao)
        return lbl_valor

    def retranslateUi(self, MainWindow):
        pass
