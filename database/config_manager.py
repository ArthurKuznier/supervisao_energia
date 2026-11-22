import json
import os
import logging
import math
import tempfile
from copy import deepcopy

logger = logging.getLogger("smartgrid")

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(_BASE_DIR, "data", "config.json")

_DEFAULT_CONFIG = {
    "serial": {
        "porta": "COM1",
        "baud_rate": "9600",
        "timeout_s": 5,
        "intervalo_amostragem_ms": 2000
    },
    "alertas": {
        "limite_potencia_w": 2000.0,
        "limite_corrente_a": 10.0,
        "limite_tensao_v": 230.0
    }
}


def _numero_valido(valor, minimo, maximo, inteiro=False):
    return (
        isinstance(valor, (int, float))
        and not isinstance(valor, bool)
        and minimo <= valor <= maximo
        and math.isfinite(valor)
        and (not inteiro or valor == int(valor))
    )


def _normalizar_config(config):
    resultado = deepcopy(config) if isinstance(config, dict) else {}
    for secao, padrao in _DEFAULT_CONFIG.items():
        if not isinstance(resultado.get(secao), dict):
            resultado[secao] = {}
        for chave, valor in padrao.items():
            resultado[secao].setdefault(chave, deepcopy(valor))

    serial = resultado["serial"]
    if not isinstance(serial["porta"], str) or not serial["porta"].strip():
        serial["porta"] = _DEFAULT_CONFIG["serial"]["porta"]
    baud = serial["baud_rate"]
    serial["baud_rate"] = str(baud) if str(baud) in ("9600", "19200", "38400", "115200") else "9600"
    for chave, minimo, maximo in (("timeout_s", 1, 60), ("intervalo_amostragem_ms", 100, 60000)):
        if _numero_valido(serial[chave], minimo, maximo, inteiro=True):
            serial[chave] = int(serial[chave])
        else:
            serial[chave] = _DEFAULT_CONFIG["serial"][chave]

    alertas = resultado["alertas"]
    for chave, minimo, maximo in (
        ("limite_tensao_v", 0.01, 1_000_000),
        ("limite_corrente_a", 0.01, 1_000_000),
        ("limite_potencia_w", 0, 100_000),
    ):
        if not _numero_valido(alertas[chave], minimo, maximo):
            alertas[chave] = _DEFAULT_CONFIG["alertas"][chave]

    if "regras_limite" in resultado:
        regras = resultado["regras_limite"]
        validas = isinstance(regras, list) and len(regras) >= 2
        if validas:
            validas = all(
                isinstance(regra, dict)
                and isinstance(regra.get("parametro"), str) and regra["parametro"].strip()
                and isinstance(regra.get("unidade"), str) and regra["unidade"].strip()
                and _numero_valido(regra.get("valor"), 0.01, 1_000_000)
                for regra in regras
            )
        if not validas:
            resultado["regras_limite"] = [
                {"parametro": "Limite Máximo de Corrente", "valor": alertas["limite_corrente_a"], "unidade": "A"},
                {"parametro": "Limite Máximo de Tensão", "valor": alertas["limite_tensao_v"], "unidade": "V"},
            ]
    return resultado


def _constante_invalida(valor):
    raise ValueError(f"Constante JSON inválida: {valor}")


def carregar_config() -> dict:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            carregado = json.load(f, parse_constant=_constante_invalida)
    except (ValueError, UnicodeError, OSError) as exc:
        logger.error("Falha ao ler config.json: %s. Usando valores default.", exc)
        carregado = None

    config = _normalizar_config(carregado)
    if config != carregado:
        try:
            salvar_config(config)
        except OSError:
            logger.error("Não foi possível recuperar config.json. Usando configurações em memória.")
    logger.info("Configurações carregadas de config.json.")
    return config


def salvar_config(config: dict) -> None:
    temporario = None
    try:
        config = _normalizar_config(config)
        pasta = os.path.dirname(os.path.abspath(CONFIG_PATH))
        os.makedirs(pasta, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=pasta,
                                         prefix=".config-", suffix=".tmp", delete=False) as f:
            temporario = f.name
            json.dump(config, f, indent=4, ensure_ascii=False, allow_nan=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporario, CONFIG_PATH)
        logger.info("Configurações salvas em config.json.")
    except OSError as exc:
        logger.error("Falha ao salvar config.json: %s", exc)
        raise
    finally:
        if temporario and os.path.exists(temporario):
            try:
                os.unlink(temporario)
            except OSError as exc:
                logger.error("Falha ao remover configuração temporária: %s", exc)
