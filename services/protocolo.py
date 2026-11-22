import json

VELOCIDADES = (9600, 19200, 38400, 115200)
TAMANHO_MAXIMO = 4096


def codificar(pacote):
    return (json.dumps(pacote, allow_nan=False, separators=(",", ":")) + "\n").encode("utf-8")


def decodificar(linha):
    if len(linha) > TAMANHO_MAXIMO:
        raise ValueError("Pacote serial muito grande.")
    pacote = json.loads(linha)
    if not isinstance(pacote, dict) or not isinstance(pacote.get("tipo"), str):
        raise ValueError("Pacote serial inválido.")
    return pacote
