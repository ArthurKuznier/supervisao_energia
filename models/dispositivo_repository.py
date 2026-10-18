import sqlite3
import logging
from datetime import datetime
from typing import List, Dict, Optional

from database.connection import get_connection

logger = logging.getLogger("smartgrid")


class DispositivoRepository:

    @staticmethod
    def buscar_por_tag(tag: str) -> Optional[Dict]:
        try:
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT id, tag, tipo, status, ultima_atualizacao "
                    "FROM dispositivos WHERE tag = ?",
                    (tag,),
                ).fetchone()
            return dict(row) if row else None
        except sqlite3.Error as exc:
            logger.error("Falha ao buscar dispositivo '%s': %s", tag, exc)
            raise

    @staticmethod
    def listar_todos() -> List[Dict]:
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT id, tag, tipo, status, ultima_atualizacao "
                    "FROM dispositivos ORDER BY id"
                ).fetchall()
            return [dict(r) for r in rows]
        except sqlite3.Error as exc:
            logger.error("Falha ao listar dispositivos: %s", exc)
            raise

    @staticmethod
    def atualizar_status(tag: str, novo_status: str) -> None:
        if novo_status not in ("ABERTO", "FECHADO"):
            raise ValueError(
                f"Status inválido: '{novo_status}'. Use 'ABERTO' ou 'FECHADO'."
            )
        agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        try:
            with get_connection() as conn:
                conn.execute(
                    "UPDATE dispositivos "
                    "SET status = ?, ultima_atualizacao = ? "
                    "WHERE tag = ?",
                    (novo_status, agora, tag),
                )
            logger.info("Dispositivo '%s' atualizado para '%s'.", tag, novo_status)
        except sqlite3.Error as exc:
            logger.error(
                "Falha ao atualizar status de '%s' para '%s': %s", tag, novo_status, exc
            )
            raise
