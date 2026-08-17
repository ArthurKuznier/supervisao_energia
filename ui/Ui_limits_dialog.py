# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'limits_dialog.ui'
##
## AVISO! Nenhuma regra de negócio deve ser escrita neste arquivo.
## Toda a lógica pertence a /controllers.
################################################################################

from PySide6.QtCore import Qt, QMetaObject
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QHeaderView, QDialogButtonBox
)


class Ui_LimitsDialog(object):
    def setupUi(self, LimitsDialog):
        if not LimitsDialog.objectName():
            LimitsDialog.setObjectName(u"LimitsDialog")
        LimitsDialog.resize(520, 420)
        LimitsDialog.setWindowTitle(u"Configuração de Limites / Parâmetros")
        LimitsDialog.setModal(True)

        layout = QVBoxLayout(LimitsDialog)

        self.lbl_titulo = QLabel(u"Regras de Alerta Cadastradas")
        self.lbl_titulo.setStyleSheet("font-weight:bold; font-size:13px;")
        layout.addWidget(self.lbl_titulo)

        self.table_regras = QTableWidget(0, 3)
        self.table_regras.setObjectName(u"table_regras")
        self.table_regras.setHorizontalHeaderLabels(
            [u"Parâmetro", u"Valor Limite", u"Unidade"])
        self.table_regras.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table_regras.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table_regras.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        layout.addWidget(self.table_regras)

        botoes_regra = QHBoxLayout()
        self.btn_adicionar_regra = QPushButton(u"+ Adicionar Regra")
        self.btn_adicionar_regra.setObjectName(u"btn_adicionar_regra")
        self.btn_remover_regra = QPushButton(u"- Remover Regra Selecionada")
        self.btn_remover_regra.setObjectName(u"btn_remover_regra")
        botoes_regra.addWidget(self.btn_adicionar_regra)
        botoes_regra.addWidget(self.btn_remover_regra)
        botoes_regra.addStretch()
        layout.addLayout(botoes_regra)

        self.buttonBox = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.button(QDialogButtonBox.Save).setText(u"Salvar")
        self.buttonBox.button(QDialogButtonBox.Cancel).setText(u"Cancelar")
        layout.addWidget(self.buttonBox)

        self.retranslateUi(LimitsDialog)
        QMetaObject.connectSlotsByName(LimitsDialog)

    def retranslateUi(self, LimitsDialog):
        pass
