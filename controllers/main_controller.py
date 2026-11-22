import logging
import sqlite3
from datetime import datetime

from PySide6.QtCore import QObject, QTimer

from database.config_manager import salvar_config
from models.dispositivo_repository import DispositivoRepository
from models.evento_repository import EventoRepository
from models.monitoramento import Monitoramento
from models.regra_repository import RegraRepository
from models.telemetria import ErroValidacaoRegra, validar_regras

logger = logging.getLogger("smartgrid")


class MainController(QObject):
    def __init__(self, view, config):
        super().__init__(view)
        self.view = view
        self.config = config or {}
        self.model = Monitoramento(config)
        self.conectado = False
        self.view.conectar_solicitado.connect(self.conectar_serial)
        self.view.desconectar_solicitado.connect(self.desconectar_serial)
        self.view.limites_solicitados.connect(self.editar_limites)
        self.view.validacao_limites_solicitada.connect(self.validar_limites)
        self.view.disjuntor_solicitado.connect(self.acionar_disjuntor)
        self.view.fechar_solicitado.connect(self.encerrar)
        self._carregar_dados()
        self._carregar_portas()
        self.view.configurar(self.config)
        self.view.limite_potencia_alterado.connect(self.atualizar_limite_potencia)
        self.view.mostrar_disjuntor(self.model.disjuntor.estado, habilitado=True)
        self.model.gerar_historico_simulado()
        self.timer = QTimer(self)
        self.timer.setInterval(self.config.get("serial", {}).get("intervalo_amostragem_ms", 2000))
        self.timer.timeout.connect(self.atualizar_telemetria)
        self.timer.start()
        self.atualizar_telemetria()

    def _carregar_dados(self):
        try:
            regras_config = self.config.get("regras_limite")
            regras = RegraRepository.listar_todos() if regras_config is None else []
            if regras_config is not None:
                self.model.atualizar_regras(regras_config)
                RegraRepository.substituir_todas(regras_config)
            elif regras:
                self.model.atualizar_regras([
                    {"parametro": r["parametro"], "valor": r["valor_limite"], "unidade": r["unidade"]}
                    for r in regras
                ])
            else:
                RegraRepository.substituir_todas(self.model.regras)
        except (sqlite3.Error, ValueError) as exc:
            logger.error("Falha ao carregar regras do banco: %s", exc)
        try:
            dispositivo = DispositivoRepository.buscar_por_tag("DISJ-PRINCIPAL")
            if dispositivo:
                self.model.atualizar_disjuntor(dispositivo["status"])
        except (sqlite3.Error, ValueError) as exc:
            logger.error("Falha ao sincronizar estado do disjuntor: %s", exc)
        try:
            self.view.mostrar_eventos(EventoRepository.listar_todos())
        except sqlite3.Error as exc:
            logger.error("Falha ao carregar histórico na tabela: %s", exc)

    def _carregar_portas(self):
        try:
            from serial.tools import list_ports
            portas = [porta.device for porta in list_ports.comports()]
        except ImportError:
            portas = []
        self.view.mostrar_portas(portas or [f"COM{i}" for i in range(1, 7)])

    def atualizar_telemetria(self):
        leitura = self.model.gerar_leitura_simulada()
        self.model.adicionar_potencia(leitura.potencia)
        self.view.mostrar_leitura(leitura.registro())
        self.view.plotar(self.model.eixo_x, self.model.potencias)
        for medido, descricao in self.model.avaliar(leitura):
            logger.warning(descricao)
            self.registrar_evento("Alerta", descricao, medido)

    def conectar_serial(self, parametros):
        self.conectado = True
        porta, baud = parametros["porta"], parametros["baud_rate"]
        self.view.mostrar_conexao(f"● Conectado ({porta} @ {baud})", conectado=True)
        self.config.setdefault("serial", {}).update(parametros)
        try:
            salvar_config(self.config)
        except OSError:
            pass
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
        try:
            salvar_config(self.config)
        except OSError as exc:
            self.view.erro(f"Não foi possível salvar as configurações.\n\nDetalhes: {exc}", "Erro ao Salvar")

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
            RegraRepository.substituir_todas(regras)
            self.model.atualizar_regras(regras)
            self.config["regras_limite"] = [dict(regra) for regra in regras]
            alertas = self.config.setdefault("alertas", {})
            for unidade, chave in (("A", "limite_corrente_a"), ("V", "limite_tensao_v")):
                valores = [regra["valor"] for regra in regras if regra["unidade"] == unidade]
                if valores:
                    alertas[chave] = min(valores)
            salvar_config(self.config)
            self.registrar_evento("Configuração", f"Regras de limite atualizadas ({len(regras)} regra(s)).")
            logger.info("Regras de limite atualizadas pelo operador: %d regra(s).", len(regras))
        except (sqlite3.Error, ValueError, OSError) as exc:
            self.view.erro(f"Não foi possível salvar as regras.\n\nDetalhes: {exc}", "Erro ao Salvar")

    def acionar_disjuntor(self, estado):
        try:
            evento = DispositivoRepository.acionar("DISJ-PRINCIPAL", estado)
            self.model.atualizar_disjuntor(estado)
            self.view.mostrar_disjuntor(estado, habilitado=True)
            self.view.inserir_evento(evento)
            logger.info("Corte emergencial executado. Disjuntor ABERTO." if estado == "ABERTO" else "Disjuntor rearmado. Carga restabelecida.")
        except (sqlite3.Error, ValueError) as exc:
            if estado == "ABERTO":
                mensagem = f"Falha ao executar o corte emergencial.\nO banco foi revertido (ROLLBACK).\n\nDetalhes: {exc}"
                titulo = "Erro — Corte Emergencial"
            else:
                mensagem = f"Falha ao rearmar o disjuntor.\nRollback executado.\n\nDetalhes: {exc}"
                titulo = "Erro — Rearme"
            logger.error("Falha na atuação do disjuntor: %s", exc)
            self.view.erro(mensagem, titulo)

    def registrar_evento(self, tipo, descricao, medido=None):
        try:
            EventoRepository.inserir(tipo, descricao, medido)
        except sqlite3.Error as exc:
            logger.error("Falha ao persistir evento: %s", exc)
        self.view.inserir_evento({"data_hora": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                                 "tipo_evento": tipo, "descricao": descricao})

    def encerrar(self):
        self.timer.stop()
        self.view.permitir_fechamento()
