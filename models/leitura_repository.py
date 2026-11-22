from datetime import datetime, timezone

from database.connection import get_connection
from models.telemetria import LeituraTelemetria


def timestamp_utc(valor):
    instante = datetime.fromisoformat(valor)
    if instante.tzinfo is None:
        raise ValueError("O horário deve incluir o fuso horário.")
    return instante.astimezone(timezone.utc).isoformat(timespec="microseconds")


class LeituraRepository:
    @staticmethod
    def inserir(dados, origem="serial", dispositivo_tag="DISJ-PRINCIPAL"):
        leitura = LeituraTelemetria(dados["tensao"], dados["corrente"])
        timestamp = timestamp_utc(dados.get("timestamp") or datetime.now(timezone.utc).isoformat())
        if origem not in ("serial", "simulacao"):
            raise ValueError("Origem de medição inválida.")
        with get_connection() as conn:
            dispositivo = conn.execute("SELECT id FROM dispositivos WHERE tag = ?", (dispositivo_tag,)).fetchone()
            if dispositivo is None:
                raise ValueError(f"Dispositivo não encontrado: {dispositivo_tag}")
            cursor = conn.execute(
                "INSERT INTO leituras (timestamp, tensao, corrente, potencia, dispositivo_id, origem) VALUES (?, ?, ?, ?, ?, ?)",
                (timestamp, leitura.tensao, leitura.corrente, leitura.potencia, dispositivo["id"], origem),
            )
            return cursor.lastrowid

    @staticmethod
    def consultar(inicio=None, fim=None, limite=1000):
        if isinstance(limite, bool) or not isinstance(limite, int) or not 1 <= limite <= 10000:
            raise ValueError("Informe de 1 a 10000 leituras.")
        inicio = timestamp_utc(inicio) if inicio else None
        fim = timestamp_utc(fim) if fim else None
        if inicio and fim and inicio > fim:
            raise ValueError("O início deve ser anterior ao fim.")
        filtros, parametros = [], []
        for operador, valor in ((">=", inicio), ("<=", fim)):
            if valor:
                filtros.append(f"timestamp {operador} ?")
                parametros.append(valor)
        where = " WHERE " + " AND ".join(filtros) if filtros else ""
        with get_connection() as conn:
            linhas = conn.execute(
                "SELECT * FROM leituras" + where + " ORDER BY timestamp DESC, id DESC LIMIT ?",
                [*parametros, limite],
            ).fetchall()
            return [dict(linha) for linha in reversed(linhas)]
