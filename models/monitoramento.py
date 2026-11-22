import random
from datetime import datetime, timedelta

from models.telemetria import (
    Disjuntor,
    LeituraTelemetria,
    numero_positivo,
)


class Monitoramento:
    def __init__(self, config):
        alertas = config.get("alertas", {})
        self.disjuntor = Disjuntor("FECHADO")
        self.limite_potencia = alertas.get("limite_potencia_w", 2000.0)
        self.regras = [
            {"parametro": "Limite Máximo de Corrente", "valor": alertas.get("limite_corrente_a", 10.0), "unidade": "A"},
            {"parametro": "Limite Máximo de Tensão", "valor": alertas.get("limite_tensao_v", 230.0), "unidade": "V"},
        ]
        self.potencias = []
        self.eixo_x = []
        self.contador = 0

    def atualizar_regras(self, regras):
        self.regras = [dict(regra) for regra in regras]

    def atualizar_limite_potencia(self, valor):
        self.limite_potencia = numero_positivo(valor, "Limite de potência", permite_zero=True)

    def atualizar_disjuntor(self, estado):
        self.disjuntor = Disjuntor(estado)

    def gerar_leitura_simulada(self):
        if self.disjuntor.estado == "ABERTO":
            return LeituraTelemetria(0.0, 0.0)
        return LeituraTelemetria(round(random.uniform(215, 235), 1), round(random.uniform(2, 12), 2))

    def gerar_historico_simulado(self):
        agora = datetime.now()
        for h in range(23, -1, -1):
            hora = (agora - timedelta(hours=h)).hour
            fator = 1 + 0.6 * abs((hora - 19) % 24 - 12) / 12
            self.adicionar_potencia(round(1200 * fator + random.uniform(-80, 80), 1))

    def adicionar_potencia(self, potencia, timestamp=None):
        self.potencias.append(potencia)
        self.eixo_x.append(timestamp if timestamp is not None else self.contador)
        self.contador += 1
        self.potencias = self.potencias[-24:]
        self.eixo_x = self.eixo_x[-24:]

    def avaliar(self, leitura):
        if self.disjuntor.estado == "ABERTO":
            return []
        violacoes = []
        if leitura.potencia > self.limite_potencia:
            violacoes.append((leitura.potencia, f"Potência ({leitura.potencia} W) acima do limite configurado ({self.limite_potencia} W)."))
        for regra in self.regras:
            medido = {"A": leitura.corrente, "V": leitura.tensao}.get(regra["unidade"])
            if medido is not None and medido > regra["valor"]:
                nome = "Corrente" if regra["unidade"] == "A" else "Tensão"
                violacoes.append((medido, f"{nome} ({medido} {regra['unidade']}) ultrapassou '{regra['parametro']}' ({regra['valor']} {regra['unidade']})."))
        return violacoes
