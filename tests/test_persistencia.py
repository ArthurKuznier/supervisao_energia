import sqlite3

import pytest

from database import connection
from models.leitura_repository import LeituraRepository


@pytest.fixture
def banco_leituras(tmp_path, monkeypatch):
    monkeypatch.setattr(connection, "DB_PATH", str(tmp_path / "smartgrid.db"))
    connection.init_db()


def test_migracao_preserva_eventos_antigos_e_vincula_dispositivo(tmp_path, monkeypatch):
    destino = tmp_path / "antigo.db"
    monkeypatch.setattr(connection, "DB_PATH", str(destino))
    conn = sqlite3.connect(destino)
    conn.execute("CREATE TABLE historico_eventos (id INTEGER PRIMARY KEY, data_hora TEXT, tipo_evento TEXT, valor_medido REAL, descricao TEXT)")
    conn.execute("INSERT INTO historico_eventos VALUES (1, '22/11/2026 10:00:00', 'Rearme', NULL, 'Evento existente')")
    conn.commit()
    conn.close()
    connection.init_db()
    connection.init_db()
    with connection.get_connection() as conn:
        evento = conn.execute("SELECT e.descricao, d.tag FROM historico_eventos e JOIN dispositivos d ON d.id = e.dispositivo_id").fetchone()
        assert tuple(evento) == ("Evento existente", "DISJ-PRINCIPAL")
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert conn.execute("SELECT COUNT(*) FROM historico_eventos").fetchone()[0] == 1


def test_consulta_filtra_periodo_e_ultimas_leituras_em_ordem(banco_leituras):
    for hora in (10, 12, 11):
        LeituraRepository.inserir({"timestamp": f"2026-11-22T{hora}:00:00-03:00", "tensao": 220, "corrente": 2})
    ultimas = LeituraRepository.consultar(limite=2)
    assert [linha["timestamp"] for linha in ultimas] == ["2026-11-22T14:00:00.000000+00:00", "2026-11-22T15:00:00.000000+00:00"]
    assert all(linha["potencia"] == 440 for linha in ultimas)
    periodo = LeituraRepository.consultar(inicio="2026-11-22T10:30:00-03:00", fim="2026-11-22T11:30:00-03:00")
    assert len(periodo) == 1
    assert periodo[0]["dispositivo_id"] is not None


@pytest.mark.parametrize("filtros", [{"limite": 0}, {"limite": True}, {"limite": 10001},
                                      {"inicio": "2026-11-22T12:00:00"},
                                      {"inicio": "2026-11-23T00:00:00Z", "fim": "2026-11-22T00:00:00Z"}])
def test_rejeita_filtros_invalidos(banco_leituras, filtros):
    with pytest.raises(ValueError):
        LeituraRepository.consultar(**filtros)


def test_conexao_fecha_ao_sair_da_transacao(banco_leituras):
    with connection.get_connection() as conn:
        conn.execute("SELECT 1")
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")
