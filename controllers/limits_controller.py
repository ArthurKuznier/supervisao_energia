import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QTableWidgetItem, QDoubleSpinBox, QMessageBox
)

from ui.Ui_limits_dialog import Ui_LimitsDialog

logger = logging.getLogger("smartgrid")


class LimitsDialog(QDialog):
    def __init__(self, regras_atuais=None, parent=None):
        super().__init__(parent)
        self.ui = Ui_LimitsDialog()
        self.ui.setupUi(self)

        self.ui.btn_adicionar_regra.clicked.connect(self.adicionar_regra)
        self.ui.btn_remover_regra.clicked.connect(self.remover_regra_selecionada)
        self.ui.buttonBox.accepted.connect(self.salvar)
        self.ui.buttonBox.rejected.connect(self.reject)

        if regras_atuais:
            for regra in regras_atuais:
                self.adicionar_regra(
                    regra["parametro"], regra["valor"], regra["unidade"])
        else:
            self.adicionar_regra("Limite Máximo de Corrente", 10.0, "A")
            self.adicionar_regra("Limite Máximo de Tensão", 230.0, "V")

    def adicionar_regra(self, parametro="", valor=0.0, unidade=""):
        tabela = self.ui.table_regras
        linha = tabela.rowCount()
        tabela.insertRow(linha)

        item_parametro = QTableWidgetItem(parametro if parametro else "Nova regra")
        tabela.setItem(linha, 0, item_parametro)

        spin_valor = QDoubleSpinBox()
        spin_valor.setRange(0.01, 1_000_000)
        spin_valor.setDecimals(2)
        spin_valor.setValue(max(valor, 0.01))
        tabela.setCellWidget(linha, 1, spin_valor)

        item_unidade = QTableWidgetItem(unidade)
        tabela.setItem(linha, 2, item_unidade)

    def remover_regra_selecionada(self):
        linha = self.ui.table_regras.currentRow()
        if linha < 0:
            QMessageBox.information(
                self, "Remover Regra",
                "Selecione uma regra na tabela para remover.")
            return
        self.ui.table_regras.removeRow(linha)

    def salvar(self):
        tabela = self.ui.table_regras

        if tabela.rowCount() < 2:
            QMessageBox.warning(
                self, "Regras Insuficientes",
                "É necessário cadastrar no mínimo duas regras de alerta.")
            return

        for linha in range(tabela.rowCount()):
            item_parametro = tabela.item(linha, 0)
            spin_valor = tabela.cellWidget(linha, 1)
            item_unidade = tabela.item(linha, 2)

            if not item_parametro or not item_parametro.text().strip():
                QMessageBox.warning(
                    self, "Campo Inválido",
                    f"O campo 'Parâmetro' na linha {linha + 1} não pode ser vazio.")
                return

            if spin_valor and spin_valor.value() <= 0:
                QMessageBox.warning(
                    self, "Valor Inválido",
                    f"O valor limite na linha {linha + 1} deve ser maior que zero.")
                return

            if not item_unidade or not item_unidade.text().strip():
                QMessageBox.warning(
                    self, "Campo Inválido",
                    f"O campo 'Unidade' na linha {linha + 1} não pode ser vazio.")
                return

        logger.info("Validação de regras concluída: %d regra(s) aprovadas.", tabela.rowCount())
        self.accept()

    def get_regras(self):
        regras = []
        tabela = self.ui.table_regras
        for linha in range(tabela.rowCount()):
            item_parametro = tabela.item(linha, 0)
            spin_valor = tabela.cellWidget(linha, 1)
            item_unidade = tabela.item(linha, 2)
            regras.append({
                "parametro": item_parametro.text().strip() if item_parametro else "",
                "valor": spin_valor.value() if spin_valor else 0.0,
                "unidade": item_unidade.text().strip() if item_unidade else "",
            })
        return regras