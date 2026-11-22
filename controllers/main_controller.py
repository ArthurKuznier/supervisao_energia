import logging
from copy import deepcopy
from datetime import datetime, timezone

from PySide6.QtCore import QObject, QThread, QTimer, Qt, Signal, Slot

from models.monitoramento import Monitoramento
from models.telemetria import ErroValidacaoRegra, validar_regras
from workers.database_worker import DatabaseWorker

logger = logging.getLogger("smartgrid")


class MainController(QObject):
    pedido_banco = Signal(int, str, object)
    parada_banco = Signal()
    historico_recebido = Signal(list)

    def __init__(self, view, config):
        super().__init__(view)
        self.view = view
        self.config = config or {}
        self.model = Monitoramento(config)
        self.conectado = False
        self.pronto = False
        self.encerrado = False
        self._encerrando = False
        self._contador_pedidos = 0
        self._retornos = {}
        self._erros_notificados = set()
        self.view.conectar_solicitado.connect(self.conectar_serial)
        self.view.desconectar_solicitado.connect(self.desconectar_serial)
        self.view.limites_solicitados.connect(self.editar_limites)
        self.view.validacao_limites_solicitada.connect(self.validar_limites)
        self.view.disjuntor_solicitado.connect(self.acionar_disjuntor)
        self.view.fechar_solicitado.connect(self.encerrar)
        self._carregar_portas()
        self.view.configurar(self.config)
        self.view.limite_potencia_alterado.connect(self.atualizar_limite_potencia)
        self.view.mostrar_disjuntor(self.model.disjuntor.estado, habilitado=False)
        self.model.gerar_historico_simulado()
        self.timer = QTimer(self)
        self.timer.setInterval(self.config.get("serial", {}).get("intervalo_amostragem_ms", 2000))
        self.timer.timeout.connect(self.atualizar_telemetria)
        self.thread_banco = QThread(self)
        self.thread_banco.setObjectName("DatabaseThread")
        self.worker_banco = DatabaseWorker()
        self.worker_banco.moveToThread(self.thread_banco)
        self.pedido_banco.connect(self.worker_banco.executar, Qt.QueuedConnection)
        self.parada_banco.connect(self.worker_banco.encerrar, Qt.QueuedConnection)
        self.worker_banco.resultado.connect(self._resultado_banco)
        self.worker_banco.erro.connect(self._erro_banco)
        self.worker_banco.finalizado.connect(self.thread_banco.quit, Qt.DirectConnection)
        self.thread_banco.finished.connect(self.worker_banco.deleteLater)
        self.thread_banco.finished.connect(self._banco_encerrado)
        self.thread_banco.start()
        self._solicitar("inicializar", {"regras_limite": self.config.get("regras_limite"),
                                       "regras_padrao": self.model.regras}, self._dados_carregados)

    def _solicitar(self, operacao, parametros, retorno=None):
        if self._encerrando:
            return
        self._contador_pedidos += 1
        pedido_id = self._contador_pedidos
        if retorno is not None:
            self._retornos[pedido_id] = retorno
        self.pedido_banco.emit(pedido_id, operacao, deepcopy(parametros))
        return pedido_id

    @Slot(int, str, object)
    def _resultado_banco(self, pedido_id, operacao, dados):
        retorno = self._retornos.pop(pedido_id, None)
        if retorno is not None and not self._encerrando:
            retorno(dados)

    @Slot(int, str, str)
    def _erro_banco(self, pedido_id, operacao, mensagem):
        self._retornos.pop(pedido_id, None)
        logger.error("Falha na persistência (%s): %s", operacao, mensagem)
        chave = (operacao, mensagem)
        if not self._encerrando and chave not in self._erros_notificados:
            self._erros_notificados.add(chave)
            self.view.erro(f"Falha na persistência ({operacao}).\n\nDetalhes: {mensagem}", "Erro ao Salvar")

    def _dados_carregados(self, dados):
        self.model.atualizar_regras(dados["regras"])
        if dados["dispositivo"]:
            self.model.atualizar_disjuntor(dados["dispositivo"]["status"])
        self.view.mostrar_eventos(dados["eventos"])
        self.view.mostrar_disjuntor(self.model.disjuntor.estado, habilitado=True)
        self.pronto = True
        self.timer.start()
        self.atualizar_telemetria()

    def _carregar_portas(self):
        try:
            from serial.tools import list_ports
            portas = [porta.device for porta in list_ports.comports()]
        except ImportError:
            portas = []
        self.view.mostrar_portas(portas or [f"COM{i}" for i in range(1, 7)])

    def atualizar_telemetria(self):
        if not self.pronto or self._encerrando:
            return
        leitura = self.model.gerar_leitura_simulada()
        dados = {**leitura.registro(), "timestamp": datetime.now(timezone.utc).isoformat()}
        self.model.adicionar_potencia(leitura.potencia)
        self.view.mostrar_leitura(dados)
        self.view.plotar(self.model.eixo_x, self.model.potencias)
        self._solicitar("medicao", {"dados": dados, "origem": "simulacao"})
        for medido, descricao in self.model.avaliar(leitura):
            logger.warning(descricao)
            self.registrar_evento("Alerta", descricao, medido)

    def conectar_serial(self, parametros):
        self.conectado = True
        porta, baud = parametros["porta"], parametros["baud_rate"]
        self.view.mostrar_conexao(f"● Conectado ({porta} @ {baud})", conectado=True)
        self.config.setdefault("serial", {}).update(parametros)
        self._solicitar("config", self.config)
        self.registrar_evento("Conexão", f"Conectado à porta {porta} (baud rate {baud}).")
        logger.info("Conexão serial estabelecida: %s @ %s baud.", porta, baud)

    def desconectar_serial(self):
        self.conectado = False
        self.view.mostrar_conexao("● Desconectado")
        self.registrar_evento("Conexão", "Conexão serial encerrada pelo operador.")
        logger.info("Conexão serial encerrada.")

    def atualizar_limite_potencia(self, valor):
        self.model.atualizar_limite_potencia(valor)
        self.config.setdefault("alertas", {})["limite_potencia_w"] = valor
        self._solicitar("config", self.config)

    def validar_limites(self, regras):
        try:
            validar_regras(regras)
        except ErroValidacaoRegra as exc:
            self.view.concluir_validacao_limites(exc)
        else:
            logger.info("Validação de regras concluída: %d regra(s) aprovadas.", len(regras))
            self.view.concluir_validacao_limites()

    def editar_limites(self):
        regras = self.view.editar_limites(self.model.regras)
        if regras is None:
            return
        try:
            validar_regras(regras)
        except ValueError as exc:
            self.view.erro(str(exc), "Erro ao Salvar")
            return
        config = deepcopy(self.config)
        config["regras_limite"] = [dict(regra) for regra in regras]
        alertas = config.setdefault("alertas", {})
        for unidade, chave in (("A", "limite_corrente_a"), ("V", "limite_tensao_v")):
            valores = [regra["valor"] for regra in regras if regra["unidade"] == unidade]
            if valores:
                alertas[chave] = min(valores)
        self._solicitar("regras", config, self._regras_salvas)

    def _regras_salvas(self, regras):
        self.model.atualizar_regras(regras)
        self.config["regras_limite"] = [dict(regra) for regra in regras]
        for unidade, chave in (("A", "limite_corrente_a"), ("V", "limite_tensao_v")):
            valores = [regra["valor"] for regra in regras if regra["unidade"] == unidade]
            if valores:
                self.config.setdefault("alertas", {})[chave] = min(valores)
        self.registrar_evento("Configuração", f"Regras de limite atualizadas ({len(regras)} regra(s)).")
        logger.info("Regras de limite atualizadas pelo operador: %d regra(s).", len(regras))

    def acionar_disjuntor(self, estado):
        if self.pronto:
            self._solicitar("acionar", {"estado": estado}, lambda evento: self._disjuntor_salvo(estado, evento))

    def _disjuntor_salvo(self, estado, evento):
        self.model.atualizar_disjuntor(estado)
        self.view.mostrar_disjuntor(estado, habilitado=True)
        self.view.inserir_evento(evento)
        logger.info("Corte emergencial executado. Disjuntor ABERTO." if estado == "ABERTO" else "Disjuntor rearmado. Carga restabelecida.")

    def registrar_evento(self, tipo, descricao, medido=None):
        self._solicitar("evento", {"data_hora": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                                   "tipo_evento": tipo, "descricao": descricao, "valor_medido": medido},
                        self.view.inserir_evento)

    def consultar_historico(self, **filtros):
        return self._solicitar("consultar", filtros, self.historico_recebido.emit)

    def encerrar(self):
        if self._encerrando:
            return
        self._encerrando = True
        self.pronto = False
        self.timer.stop()
        self.parada_banco.emit()

    @Slot()
    def _banco_encerrado(self):
        if not self.thread_banco.wait(0):
            QTimer.singleShot(10, self._banco_encerrado)
            return
        self.thread_banco.deleteLater()
        self.encerrado = True
        self._retornos.clear()
        self.view.permitir_fechamento()
