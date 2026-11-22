import logging

from PySide6.QtCore import QObject, Signal, Slot

from database.config_manager import salvar_config
from database.connection import init_db
from models.dispositivo_repository import DispositivoRepository
from models.evento_repository import EventoRepository
from models.leitura_repository import LeituraRepository
from models.regra_repository import RegraRepository

logger = logging.getLogger("smartgrid")


class DatabaseWorker(QObject):
    resultado = Signal(int, str, object)
    erro = Signal(int, str, str)
    finalizado = Signal()

    @Slot(int, str, object)
    def executar(self, pedido_id, operacao, parametros):
        try:
            dados = self._executar(operacao, parametros)
        except Exception as exc:
            logger.exception("Falha na operação de persistência %s", operacao)
            self.erro.emit(pedido_id, operacao, str(exc))
        else:
            self.resultado.emit(pedido_id, operacao, dados)

    def _executar(self, operacao, parametros):
        if operacao == "inicializar":
            init_db()
            regras = parametros.get("regras_limite")
            if regras is None:
                existentes = RegraRepository.listar_todos()
                regras = [{"parametro": r["parametro"], "valor": r["valor_limite"], "unidade": r["unidade"]}
                          for r in existentes] or parametros["regras_padrao"]
            RegraRepository.substituir_todas(regras)
            return {"regras": regras, "dispositivo": DispositivoRepository.buscar_por_tag("DISJ-PRINCIPAL"),
                    "eventos": EventoRepository.listar_todos()}
        if operacao == "config":
            salvar_config(parametros)
        elif operacao == "regras":
            RegraRepository.substituir_todas(parametros["regras_limite"])
            salvar_config(parametros)
            return parametros["regras_limite"]
        elif operacao == "acionar":
            return DispositivoRepository.acionar("DISJ-PRINCIPAL", parametros["estado"])
        elif operacao == "sincronizar":
            DispositivoRepository.atualizar_status("DISJ-PRINCIPAL", parametros["estado"])
        elif operacao == "evento":
            evento = dict(parametros)
            evento["id"] = EventoRepository.inserir(evento["tipo_evento"], evento["descricao"],
                                                   evento.get("valor_medido"), evento["data_hora"])
            return evento
        elif operacao == "medicao":
            return LeituraRepository.inserir(parametros["dados"], parametros.get("origem", "serial"))
        elif operacao == "consultar":
            return LeituraRepository.consultar(**parametros)
        else:
            raise ValueError(f"Operação de persistência inválida: {operacao}")

    @Slot()
    def encerrar(self):
        self.finalizado.emit()
