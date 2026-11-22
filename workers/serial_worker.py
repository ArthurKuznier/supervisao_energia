import logging
from time import monotonic

import serial
from serial.tools import list_ports
from PySide6.QtCore import QObject, QTimer, Signal, Slot

from models.telemetria import LeituraTelemetria
from services.protocolo import VELOCIDADES, TAMANHO_MAXIMO, codificar, decodificar

logger = logging.getLogger("smartgrid")


class SerialWorker(QObject):
    conectado = Signal(dict)
    desconectado = Signal()
    leitura = Signal(object)
    erro = Signal(str)
    portas = Signal(list)
    finalizado = Signal()
    estado_recebido = Signal(str)
    comando_confirmado = Signal(str)

    def __init__(self):
        super().__init__()
        self.porta = None
        self.timer = None
        self.estado = "DESCONECTADO"
        self.buffer = bytearray()
        self.pendente = None
        self.sequencia = 0
        self._finalizando = False

    @Slot()
    def iniciar(self):
        self.timer = QTimer(self)
        self.timer.setInterval(20)
        self.timer.timeout.connect(self._receber)
        self.portas.emit([porta.device for porta in list_ports.comports()])

    @Slot(dict)
    def conectar(self, config):
        self._fechar()
        try:
            self.config = dict(config)
            baud = int(config["baud_rate"])
            intervalo = int(config.get("intervalo_amostragem_ms", 2000))
            if baud not in VELOCIDADES or not 100 <= intervalo <= 60000:
                raise ValueError("Velocidade ou intervalo de amostragem inválido.")
            self.porta = serial.serial_for_url(config["porta"], baudrate=9600, timeout=0, write_timeout=1)
            self.buffer.clear()
            self.estado = "HELLO"
            self.prazo = monotonic() + float(config.get("timeout_s", 5))
            self._enviar({"tipo": "HELLO", "baud_rate": baud, "intervalo_ms": intervalo})
            self.timer.start()
        except (serial.SerialException, OSError, ValueError, KeyError) as exc:
            self._falhar(str(exc))

    def _enviar(self, pacote):
        dados = codificar(pacote)
        if self.porta.write(dados) != len(dados):
            raise serial.SerialException("Envio serial incompleto.")

    def _receber(self):
        try:
            self.buffer.extend(self.porta.read(TAMANHO_MAXIMO))
            if len(self.buffer) > TAMANHO_MAXIMO:
                self.buffer.clear()
                logger.warning("Pacote serial descartado: tamanho excedido.")
            for _ in range(50):
                if b"\n" not in self.buffer:
                    break
                linha, _, restante = self.buffer.partition(b"\n")
                self.buffer = bytearray(restante)
                try:
                    self._processar(decodificar(linha))
                    if self.porta is None:
                        return
                except (ValueError, TypeError, KeyError, UnicodeError) as exc:
                    logger.warning("Pacote serial descartado: %s", exc)
            if self.estado in ("HELLO", "START") and monotonic() > self.prazo:
                raise serial.SerialException("Timeout: a placa não confirmou o handshake.")
            if self.estado == "STOP" and monotonic() > self.prazo:
                self._fechar()
                return
            if self.estado == "ATIVO":
                if self.pendente and monotonic() > self.pendente["prazo"]:
                    raise serial.SerialException("O disjuntor não confirmou o comando. Estado deve ser verificado na placa.")
                if monotonic() - self.ultima_resposta > max(5, self.config.get("intervalo_amostragem_ms", 2000) / 1000 * 3):
                    raise serial.SerialException("Timeout: a placa parou de responder.")
                if monotonic() - self.ultimo_ping >= 2:
                    self._enviar({"tipo": "PING"})
                    self.ultimo_ping = monotonic()
        except (serial.SerialException, OSError) as exc:
            self._falhar(str(exc))

    def _processar(self, pacote):
        if pacote["tipo"] == "ACK" and pacote.get("comando") == self.estado:
            if self.estado == "STOP":
                self._fechar()
                return
            if self.estado == "HELLO":
                self.porta.baudrate = int(self.config["baud_rate"])
                self.estado = "START"
                self._enviar({"tipo": "START"})
            elif self.estado == "START":
                if pacote.get("estado") not in ("ABERTO", "FECHADO"):
                    raise ValueError("Estado inicial de disjuntor inválido.")
                self.estado = "ATIVO"
                self.ultima_resposta = self.ultimo_ping = monotonic()
                self.conectado.emit(dict(self.config))
                self.estado_recebido.emit(pacote["estado"])
        elif self.estado == "ATIVO" and pacote["tipo"] == "ACK" and pacote.get("comando") == "DISJUNTOR":
            if self.pendente and pacote.get("id") == self.pendente["id"] and pacote.get("estado") == self.pendente["estado"]:
                self.ultima_resposta = monotonic()
                self.pendente = None
                self.comando_confirmado.emit(pacote["estado"])
        elif self.estado == "ATIVO" and pacote["tipo"] == "PONG":
            self.ultima_resposta = monotonic()
        elif self.estado == "ATIVO" and pacote["tipo"] == "TELEMETRIA":
            leitura = LeituraTelemetria(pacote["tensao"], pacote["corrente"])
            self.ultima_resposta = monotonic()
            self.leitura.emit(leitura)

    def _falhar(self, mensagem):
        self._fechar()
        self.erro.emit(mensagem)

    @Slot(str)
    def acionar(self, estado):
        if self.estado != "ATIVO" or self.pendente:
            return
        if estado not in ("ABERTO", "FECHADO"):
            self.erro.emit("Comando de disjuntor inválido.")
            return
        self.sequencia += 1
        self.pendente = {"id": self.sequencia, "estado": estado, "prazo": monotonic() + float(self.config.get("timeout_s", 5))}
        try:
            self._enviar({"tipo": "DISJUNTOR", "id": self.sequencia, "estado": estado})
        except (serial.SerialException, OSError) as exc:
            self._falhar(str(exc))

    @Slot()
    def desconectar(self):
        if self.porta and self.estado == "ATIVO":
            try:
                self._enviar({"tipo": "STOP"})
                self.estado = "STOP"
                self.prazo = monotonic() + 1
                return
            except (serial.SerialException, OSError):
                pass
        self._fechar()

    def _fechar(self):
        if self.timer:
            self.timer.stop()
        if self.porta:
            try:
                self.porta.close()
            except OSError as exc:
                logger.error("Falha ao fechar porta serial: %s", exc)
            finally:
                self.porta = None
        self.estado = "DESCONECTADO"
        self.pendente = None
        self.buffer.clear()
        self.desconectado.emit()
        if self._finalizando:
            self._finalizando = False
            self.finalizado.emit()

    @Slot()
    def encerrar(self):
        self._finalizando = True
        self.desconectar()
