import logging
from copy import deepcopy
from datetime import datetime, timezone

from PySide6.QtCore import QObject, QThread, QTimer, Qt, Signal, Slot

from models.monitoramento import Monitoramento
from models.telemetria import ErroValidacaoRegra, validar_regras
from workers.database_worker import DatabaseWorker
from workers.serial_worker import SerialWorker

logger = logging.getLogger("smartgrid")


class MainController(QObject):
    pedido_banco = Signal(int, str, object)
    parada_banco = Signal()
    historico_recebido = Signal(list)
    conectar_porta = Signal(dict)
    desconectar_porta = Signal()
    parada_serial = Signal()
    comando_serial = Signal(str)

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
        self.modo_historico = False
        self._versao_consulta = 0
        self.view.historico_solicitado.connect(self.pedir_historico)
        self.view.tempo_real_solicitado.connect(self.voltar_tempo_real)
        self.view.conectar_solicitado.connect(self.conectar_serial)
        self.view.desconectar_solicitado.connect(self.desconectar_serial)
        self.view.limites_solicitados.connect(self.editar_limites)
        self.view.validacao_limites_solicitada.connect(self.validar_limites)
        self.view.disjuntor_solicitado.connect(self.acionar_disjuntor)
        self.view.fechar_solicitado.connect(self.encerrar)
        self.view.configurar(self.config)
        self.view.limite_potencia_alterado.connect(self.atualizar_limite_potencia)
        self.view.mostrar_disjuntor(self.model.disjuntor.estado, habilitado=False)
        self._serial_finalizado = False
        self._banco_finalizado = False
        self._conectando = False
        self.thread_serial = QThread(self)
        self.thread_serial.setObjectName("SerialThread")
        self.worker_serial = SerialWorker()
        self.worker_serial.moveToThread(self.thread_serial)
        self.thread_serial.started.connect(self.worker_serial.iniciar)
        self.conectar_porta.connect(self.worker_serial.conectar, Qt.QueuedConnection)
        self.desconectar_porta.connect(self.worker_serial.desconectar, Qt.QueuedConnection)
        self.parada_serial.connect(self.worker_serial.encerrar, Qt.QueuedConnection)
        self.comando_serial.connect(self.worker_serial.acionar, Qt.QueuedConnection)
        self.worker_serial.estado_recebido.connect(self._estado_recebido)
        self.worker_serial.comando_confirmado.connect(self._comando_confirmado)
        self.worker_serial.conectado.connect(self._serial_conectado)
        self.worker_serial.desconectado.connect(self._serial_desconectado)
        self.worker_serial.erro.connect(self._erro_serial)
        self.worker_serial.leitura.connect(self.receber_telemetria)
        self.worker_serial.portas.connect(self._portas_recebidas)
        self.worker_serial.finalizado.connect(self.thread_serial.quit, Qt.DirectConnection)
        self.thread_serial.finished.connect(self.worker_serial.deleteLater)
        self.thread_serial.finished.connect(self._serial_encerrado)
        self.thread_serial.start()
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
        self.view.mostrar_disjuntor(self.model.disjuntor.estado, habilitado=False)
        self.pronto = True

    @Slot(list)
    def _portas_recebidas(self, portas):
        preferida = self.config.get("serial", {}).get("porta", "COM1")
        self.view.mostrar_portas(list(dict.fromkeys([preferida, *portas])))
        self.view.configurar(self.config)

    @Slot(object)
    def receber_telemetria(self, leitura):
        if not self.pronto or not self.conectado or self._encerrando:
            return
        dados = {**leitura.registro(), "timestamp": datetime.now(timezone.utc).isoformat()}
        self.model.adicionar_potencia(leitura.potencia, datetime.fromisoformat(dados["timestamp"]).timestamp())
        self.view.mostrar_leitura(dados)
        if not self.modo_historico:
            self.view.plotar(self.model.eixo_x, self.model.potencias)
        self._solicitar("medicao", {"dados": dados, "origem": "serial"})
        for medido, descricao in self.model.avaliar(leitura):
            logger.warning(descricao)
            self.registrar_evento("Alerta", descricao, medido)

    def conectar_serial(self, parametros):
        if not self.pronto or self._encerrando or self.conectado or self._conectando:
            return
        config = {**self.config.get("serial", {}), **parametros}
        self._conectando = True
        self.view.mostrar_conexao("Negociando conexão…", ocupado=True)
        self.conectar_porta.emit(config)

    @Slot(dict)
    def _serial_conectado(self, parametros):
        if self._encerrando:
            return
        self._conectando = False
        self.conectado = True
        porta, baud = parametros["porta"], parametros["baud_rate"]
        self.view.mostrar_conexao(f"● Conectado ({porta} @ {baud})", conectado=True)
        self.config.setdefault("serial", {}).update(parametros)
        self._solicitar("config", self.config)
        self.registrar_evento("Conexão", f"Conectado à porta {porta} (baud rate {baud}).")

    def desconectar_serial(self):
        self._conectando = False
        self.desconectar_porta.emit()

    @Slot()
    def _serial_desconectado(self):
        estava_conectado = self.conectado
        self.conectado = False
        if not self._conectando:
            self.view.mostrar_conexao("● Desconectado")
        self.view.mostrar_disjuntor(self.model.disjuntor.estado, habilitado=False)
        if estava_conectado:
            self.registrar_evento("Conexão", "Conexão serial encerrada.")

    @Slot(str)
    def _erro_serial(self, mensagem):
        self._conectando = False
        self._serial_desconectado()
        if not self._encerrando:
            self.view.erro(mensagem, "Erro de comunicação serial")

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
        if self.pronto and self.conectado and not self._encerrando:
            self.view.mostrar_disjuntor(self.model.disjuntor.estado, habilitado=False)
            self.comando_serial.emit(estado)

    @Slot(str)
    def _estado_recebido(self, estado):
        if self._encerrando:
            return
        self.model.atualizar_disjuntor(estado)
        self.view.mostrar_disjuntor(estado, habilitado=self.conectado)
        self._solicitar("sincronizar", {"estado": estado})

    @Slot(str)
    def _comando_confirmado(self, estado):
        if self._encerrando:
            return
        self.model.atualizar_disjuntor(estado)
        self.view.mostrar_disjuntor(estado, habilitado=self.conectado)
        self._solicitar("acionar", {"estado": estado}, lambda evento: self._disjuntor_salvo(estado, evento))

    def _disjuntor_salvo(self, estado, evento):
        self.view.inserir_evento(evento)
        logger.info("Corte emergencial executado. Disjuntor ABERTO." if estado == "ABERTO" else "Disjuntor rearmado. Carga restabelecida.")

    def registrar_evento(self, tipo, descricao, medido=None):
        self._solicitar("evento", {"data_hora": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                                   "tipo_evento": tipo, "descricao": descricao, "valor_medido": medido},
                        self.view.inserir_evento)

    def consultar_historico(self, **filtros):
        return self._solicitar("consultar", filtros, self.historico_recebido.emit)

    def pedir_historico(self, filtros):
        filtros = dict(filtros)
        for nome in ("inicio", "fim"):
            epoch = filtros.pop(nome + "_epoch", None)
            if epoch is not None:
                filtros[nome] = datetime.fromtimestamp(epoch, timezone.utc).isoformat()
        self._versao_consulta += 1
        versao = self._versao_consulta
        self._solicitar("consultar", filtros, lambda dados: self._mostrar_historico(versao, dados))

    def _mostrar_historico(self, versao, dados):
        if versao != self._versao_consulta:
            return
        self.modo_historico = True
        self.view.plotar([datetime.fromisoformat(linha["timestamp"]).timestamp() for linha in dados],
                         [linha["potencia"] for linha in dados])
        self.view.mostrar_modo_grafico(f"Consulta histórica — {len(dados)} leituras")
        self.historico_recebido.emit(dados)

    def voltar_tempo_real(self):
        self._versao_consulta += 1
        self.modo_historico = False
        self.view.mostrar_modo_grafico("Monitoramento em Tempo Real")
        self.view.plotar(self.model.eixo_x, self.model.potencias)

    def encerrar(self):
        if self._encerrando:
            return
        self._encerrando = True
        self.pronto = False
        self.parada_serial.emit()

    @Slot()
    def _serial_encerrado(self):
        if not self.thread_serial.wait(0):
            QTimer.singleShot(10, self._serial_encerrado)
            return
        self.thread_serial.deleteLater()
        self._serial_finalizado = True
        self.parada_banco.emit()

    @Slot()
    def _banco_encerrado(self):
        if not self.thread_banco.wait(0):
            QTimer.singleShot(10, self._banco_encerrado)
            return
        self.thread_banco.deleteLater()
        self._banco_finalizado = True
        self.encerrado = self._serial_finalizado and self._banco_finalizado
        self._retornos.clear()
        if self.encerrado:
            self.view.permitir_fechamento()
