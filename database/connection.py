import sqlite3
import os
import logging

from database.logger import configurar_logger

logger = logging.getLogger("smartgrid")

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(_BASE_DIR, "data", "smartgrid.db")


def get_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row

    conn.execute("PRAGMA foreign_keys = ON;")
    conn.commit()

    return conn


def init_db() -> None:
    schema = """
    CREATE TABLE IF NOT EXISTS dispositivos (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        tag             TEXT    NOT NULL UNIQUE,
        tipo            TEXT    NOT NULL,
        status          TEXT    NOT NULL DEFAULT 'FECHADO'
                        CHECK(status IN ('ABERTO', 'FECHADO')),
        ultima_atualizacao TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS historico_eventos (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        data_hora       TEXT    NOT NULL,
        tipo_evento     TEXT    NOT NULL,
        valor_medido    REAL,
        descricao       TEXT    NOT NULL
    );

    CREATE TABLE IF NOT EXISTS regras_limite (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        parametro       TEXT    NOT NULL,
        valor_limite    REAL    NOT NULL CHECK(valor_limite >= 0),
        unidade         TEXT    NOT NULL
    );
    """

    try:
        with get_connection() as conn:
            conn.executescript(schema)

            agora = _agora_str()
            conn.execute(
                "INSERT OR IGNORE INTO dispositivos (tag, tipo, status, ultima_atualizacao) "
                "VALUES (?, ?, ?, ?)",
                ("DISJ-PRINCIPAL", "Disjuntor", "FECHADO", agora),
            )
            conn.execute(
                "INSERT OR IGNORE INTO dispositivos (tag, tipo, status, ultima_atualizacao) "
                "VALUES (?, ?, ?, ?)",
                ("RELE-EMERGENCIA", "Relé de Emergência", "FECHADO", agora),
            )

        logger.info("Conexão com SQLite estabelecida e esquema validado.")
    except sqlite3.Error as exc:
        logger.error("Falha ao inicializar o banco de dados: %s", exc)
        raise


def _agora_str() -> str:
    from datetime import datetime
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")
