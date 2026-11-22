import pytest

from models.monitoramento import Monitoramento
from models.telemetria import LeituraTelemetria


def test_potencia_preserva_calculo_e_arredondamento_original():
    assert LeituraTelemetria(220.1, 10.23).potencia == 2251.6


@pytest.mark.parametrize("valor", [float("nan"), float("inf"), -1, True, "220"])
def test_rejeita_medicao_invalida(valor):
    with pytest.raises(ValueError):
        LeituraTelemetria(valor, 1)


def test_alertas_somente_quando_ultrapassa_limite():
    model = Monitoramento({"alertas": {"limite_potencia_w": 2300.0}})
    assert model.avaliar(LeituraTelemetria(230, 10)) == []
    assert len(model.avaliar(LeituraTelemetria(231, 11))) == 3
