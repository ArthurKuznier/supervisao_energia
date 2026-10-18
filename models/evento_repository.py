import sqlite3
import logging
from datetime import datetime
from typing import List, Dict, Optional

from database.connection import get_connection

logger = logging.getLogger("smartgrid")


class EventoRepository:

    @staticmethod
    def inserir(tipo_evento: str, descricao: str,
                valor_medido: Optional[float] = None) -> int:
        agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        try:
            with get_connection() as conn:
                cursor = conn.execute(
                    "INSERT INTO historico_eventos "
                    "(data_hora, tipo_evento, valor_medido, descricao) "
                    "VALUES (?, ?, ?, ?)",
                    (agora, tipo_evento, valor_medido, descricao),
                )
                return cursor.lastrowid
        except sqlite3.Error as exc:
            logger.error("Falha ao inserir evento '%s': %s", tipo_evento, exc)
            raise

    @staticmethod
    def listar_todos() -> List[Dict]:
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT id, data_hora, tipo_evento, valor_medido, descricao "
                    "FROM historico_eventos "
                    "ORDER BY id DESC"
                ).fetchall()
            return [dict(r) for r in rows]
        except sqlite3.Error as exc:
            logger.error("Falha ao listar eventos: %s", exc)
            raise

    @staticmethod
    def listar_por_tipo(tipo_evento: str) -> List[Dict]:
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT id, data_hora, tipo_evento, valor_medido, descricao "
                    "FROM historico_eventos "
                    "WHERE tipo_evento = ? "
                    "ORDER BY id DESC",
                    (tipo_evento,),
                ).fetchall()
            return [dict(r) for r in rows]
        except sqlite3.Error as exc:
            logger.error("Falha ao filtrar eventos por tipo '%s': %s", tipo_evento, exc)
            raise

    @staticmethod
    def limpar_todos() -> None:
        try:
            with get_connection() as conn:
                conn.execute("DELETE FROM historico_eventos")
            logger.info("Histórico de eventos limpo.")
        except sqlite3.Error as exc:
            logger.error("Falha ao limpar histórico: %s", exc)
            raise
