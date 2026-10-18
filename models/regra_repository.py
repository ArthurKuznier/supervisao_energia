import sqlite3
import logging
from typing import List, Dict

from database.connection import get_connection

logger = logging.getLogger("smartgrid")


class RegraRepository:

    @staticmethod
    def inserir(parametro: str, valor_limite: float, unidade: str) -> int:
        try:
            with get_connection() as conn:
                cursor = conn.execute(
                    "INSERT INTO regras_limite (parametro, valor_limite, unidade) "
                    "VALUES (?, ?, ?)",
                    (parametro, valor_limite, unidade),
                )
                return cursor.lastrowid
        except sqlite3.Error as exc:
            logger.error("Falha ao inserir regra '%s': %s", parametro, exc)
            raise

    @staticmethod
    def listar_todos() -> List[Dict]:
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT id, parametro, valor_limite, unidade "
                    "FROM regras_limite ORDER BY id"
                ).fetchall()
            return [dict(r) for r in rows]
        except sqlite3.Error as exc:
            logger.error("Falha ao listar regras: %s", exc)
            raise

    @staticmethod
    def substituir_todas(regras: List[Dict]) -> None:
        try:
            with get_connection() as conn:
                conn.execute("DELETE FROM regras_limite")
                conn.executemany(
                    "INSERT INTO regras_limite (parametro, valor_limite, unidade) "
                    "VALUES (?, ?, ?)",
                    [(r["parametro"], r["valor"], r["unidade"]) for r in regras],
                )
            logger.info("Regras de limite atualizadas (%d regra(s)).", len(regras))
        except sqlite3.Error as exc:
            logger.error("Falha ao substituir regras de limite: %s", exc)
            raise

    @staticmethod
    def excluir(regra_id: int) -> None:
        try:
            with get_connection() as conn:
                conn.execute(
                    "DELETE FROM regras_limite WHERE id = ?", (regra_id,)
                )
            logger.info("Regra id=%d removida.", regra_id)
        except sqlite3.Error as exc:
            logger.error("Falha ao remover regra id=%d: %s", regra_id, exc)
            raise
