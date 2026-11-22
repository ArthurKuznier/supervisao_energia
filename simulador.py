import argparse
import random
import socket
from time import monotonic, sleep

import serial

from services.protocolo import VELOCIDADES, TAMANHO_MAXIMO, codificar, decodificar


class PlacaSimulada:
    def __init__(self):
        self.disjuntor = "FECHADO"
        self.reiniciar_link()

    def reiniciar_link(self):
        self.estado = "ESPERA"
        self.baud_rate = 9600
        self.intervalo = 2.0
        self.ultimo_contato = monotonic()
        self.proxima_leitura = monotonic()

    def processar(self, pacote):
        tipo = pacote["tipo"]
        self.ultimo_contato = monotonic()
        if tipo == "STOP":
            self.reiniciar_link()
            return {"tipo": "ACK", "comando": "STOP"}
        if tipo == "HELLO" and self.estado == "ESPERA":
            baud, intervalo = pacote.get("baud_rate"), pacote.get("intervalo_ms")
            if baud not in VELOCIDADES or isinstance(baud, bool) or not isinstance(intervalo, int) or isinstance(intervalo, bool) or not 100 <= intervalo <= 60000:
                return {"tipo": "ERRO", "mensagem": "Configuração inválida"}
            self.baud_rate, self.intervalo = baud, intervalo / 1000
            self.estado = "NEGOCIADO"
            return {"tipo": "ACK", "comando": "HELLO"}
        if tipo == "START" and self.estado == "NEGOCIADO":
            self.estado = "ATIVO"
            self.proxima_leitura = monotonic() + self.intervalo
            return {"tipo": "ACK", "comando": "START", "estado": self.disjuntor}
        if self.estado != "ATIVO":
            return None
        if tipo == "PING":
            return {"tipo": "PONG"}
        if tipo == "DISJUNTOR" and pacote.get("estado") in ("ABERTO", "FECHADO"):
            self.disjuntor = pacote["estado"]
            return {"tipo": "ACK", "comando": "DISJUNTOR", "id": pacote.get("id"), "estado": self.disjuntor}
        return None

    def telemetria(self):
        if self.estado != "ESPERA" and monotonic() - self.ultimo_contato > 10:
            self.reiniciar_link()
        if self.estado != "ATIVO" or monotonic() < self.proxima_leitura:
            return None
        self.proxima_leitura = monotonic() + self.intervalo
        tensao, corrente = (0.0, 0.0) if self.disjuntor == "ABERTO" else (round(random.uniform(215, 235), 1), round(random.uniform(2, 12), 2))
        return {"tipo": "TELEMETRIA", "tensao": tensao, "corrente": corrente, "estado": self.disjuntor}


def executar_link(placa, ler, escrever, ajustar_baud):
    buffer = bytearray()
    placa.reiniciar_link()
    while True:
        buffer.extend(ler())
        if len(buffer) > TAMANHO_MAXIMO:
            buffer.clear()
        while b"\n" in buffer:
            linha, _, restante = buffer.partition(b"\n")
            buffer = bytearray(restante)
            try:
                resposta = placa.processar(decodificar(linha))
                if resposta:
                    escrever(codificar(resposta))
                    ajustar_baud(placa.baud_rate)
            except (ValueError, TypeError, KeyError, UnicodeError):
                continue
        pacote = placa.telemetria()
        if pacote:
            escrever(codificar(pacote))
        ajustar_baud(placa.baud_rate)
        sleep(0.01)


def main():
    parser = argparse.ArgumentParser()
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--porta")
    grupo.add_argument("--tcp", type=int, metavar="PORTA")
    args = parser.parse_args()
    placa = PlacaSimulada()
    if args.porta:
        with serial.Serial(args.porta, 9600, timeout=0.02, write_timeout=1) as porta:
            def escrever(dados):
                porta.write(dados)
                porta.flush()

            def ajustar(baud):
                if porta.baudrate != baud:
                    porta.baudrate = baud

            executar_link(placa, lambda: porta.read(min(porta.in_waiting, TAMANHO_MAXIMO)), escrever, ajustar)
    else:
        with socket.socket() as servidor:
            servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            servidor.bind(("127.0.0.1", args.tcp))
            servidor.listen(1)
            print(f"Simulador aguardando em socket://127.0.0.1:{args.tcp}", flush=True)
            while True:
                cliente, _ = servidor.accept()
                with cliente:
                    cliente.settimeout(0.02)

                    def ler():
                        try:
                            dados = cliente.recv(TAMANHO_MAXIMO)
                        except socket.timeout:
                            return b""
                        if not dados:
                            raise ConnectionError("Cliente desconectado")
                        return dados

                    try:
                        executar_link(placa, ler, cliente.sendall, lambda baud: None)
                    except (ConnectionError, OSError):
                        placa.reiniciar_link()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
