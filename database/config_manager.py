import json
import os
import logging

logger = logging.getLogger("smartgrid")

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(_BASE_DIR, "data", "config.json")

_DEFAULT_CONFIG = {
    "serial": {
        "porta": "COM1",
        "baud_rate": "9600",
        "timeout_s": 5
    },
    "alertas": {
        "limite_potencia_w": 2000.0,
        "limite_corrente_a": 10.0,
        "limite_tensao_v": 230.0
    }
}


def carregar_config() -> dict:
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)

    if not os.path.exists(CONFIG_PATH):
        salvar_config(_DEFAULT_CONFIG)
        logger.info("Arquivo config.json não encontrado. Criado com valores default.")
        return dict(_DEFAULT_CONFIG)

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
        logger.info("Configurações carregadas de config.json.")
        return config
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Falha ao ler config.json: %s. Usando valores default.", exc)
        return dict(_DEFAULT_CONFIG)


def salvar_config(config: dict) -> None:
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        logger.info("Configurações salvas em config.json.")
    except OSError as exc:
        logger.error("Falha ao salvar config.json: %s", exc)
        raise
