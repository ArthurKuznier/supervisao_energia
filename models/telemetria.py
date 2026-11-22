import math
from dataclasses import dataclass


def numero_positivo(valor, nome, permite_zero=False):
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ValueError(f"{nome}: informe um número.")
    if not math.isfinite(valor) or (valor < 0 if permite_zero else valor <= 0):
        raise ValueError(f"{nome}: valor fora do intervalo permitido.")
    return float(valor)


@dataclass(frozen=True)
class LeituraTelemetria:
    tensao: float
    corrente: float

    def __post_init__(self):
        numero_positivo(self.tensao, "Tensão", permite_zero=True)
        numero_positivo(self.corrente, "Corrente", permite_zero=True)

    @property
    def potencia(self):
        return round(self.tensao * self.corrente, 1)

    def registro(self):
        return {"tensao": self.tensao, "corrente": self.corrente, "potencia": self.potencia}


@dataclass(frozen=True)
class Disjuntor:
    estado: str = "ABERTO"

    def __post_init__(self):
        if self.estado not in ("ABERTO", "FECHADO"):
            raise ValueError("Estado de disjuntor inválido.")


class ErroValidacaoRegra(ValueError):
    def __init__(self, titulo, mensagem):
        super().__init__(mensagem)
        self.titulo = titulo


def validar_regras(regras):
    if len(regras) < 2:
        raise ErroValidacaoRegra("Regras Insuficientes", "É necessário cadastrar no mínimo duas regras de alerta.")
    for linha, regra in enumerate(regras, 1):
        if not regra.get("parametro", "").strip():
            raise ErroValidacaoRegra("Campo Inválido", f"O campo 'Parâmetro' na linha {linha} não pode ser vazio.")
        if regra.get("valor", 0) <= 0:
            raise ErroValidacaoRegra("Valor Inválido", f"O valor limite na linha {linha} deve ser maior que zero.")
        if not regra.get("unidade", "").strip():
            raise ErroValidacaoRegra("Campo Inválido", f"O campo 'Unidade' na linha {linha} não pode ser vazio.")
