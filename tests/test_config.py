import json
from copy import deepcopy

import pytest

from database import config_manager


@pytest.fixture
def config_path(tmp_path, monkeypatch):
    destino = tmp_path / "data" / "config.json"
    monkeypatch.setattr(config_manager, "CONFIG_PATH", str(destino))
    return destino


def test_recria_arquivo_ausente_com_padrao(config_path):
    config = config_manager.carregar_config()
    assert config == config_manager._DEFAULT_CONFIG
    assert json.loads(config_path.read_text(encoding="utf-8")) == config


@pytest.mark.parametrize("conteudo", [b"{", b"[]", b"null", b'"texto"', b"42", b"\xff", b'{"valor": NaN}'])
def test_recupera_arquivo_invalido(config_path, conteudo):
    config_path.parent.mkdir()
    config_path.write_bytes(conteudo)
    config = config_manager.carregar_config()
    assert config == config_manager._DEFAULT_CONFIG
    assert json.loads(config_path.read_text(encoding="utf-8")) == config


def test_corrige_apenas_campos_invalidos_e_preserva_preferencias(config_path):
    original = {
        "serial": {"porta": "COM8", "baud_rate": 38400, "timeout_s": 0,
                   "intervalo_amostragem_ms": 500, "preferencia_extra": "manter"},
        "alertas": {"limite_tensao_v": 220, "limite_corrente_a": -1, "limite_potencia_w": 3000},
        "outra_secao": {"preferencia": True},
    }
    config_path.parent.mkdir()
    config_path.write_text(json.dumps(original), encoding="utf-8")
    config = config_manager.carregar_config()
    assert config["serial"] == {**original["serial"], "baud_rate": "38400", "timeout_s": 5}
    assert config["alertas"] == {**original["alertas"], "limite_corrente_a": 10.0}
    assert config["outra_secao"] == original["outra_secao"]
    assert json.loads(config_path.read_text(encoding="utf-8")) == config


@pytest.mark.parametrize("baud", [9600, "19200", 38400, "115200"])
def test_preserva_quatro_velocidades_suportadas(config_path, baud):
    config_manager.salvar_config({"serial": {"baud_rate": baud}})
    assert config_manager.carregar_config()["serial"]["baud_rate"] == str(baud)


@pytest.mark.parametrize("secao,chave,valor", [
    ("serial", "porta", ""),
    ("serial", "porta", 123),
    ("serial", "baud_rate", 57600),
    ("serial", "timeout_s", True),
    ("serial", "timeout_s", "5"),
    ("serial", "timeout_s", 1.5),
    ("serial", "intervalo_amostragem_ms", 0),
    ("serial", "intervalo_amostragem_ms", 10 ** 400),
    ("alertas", "limite_tensao_v", None),
    ("alertas", "limite_corrente_a", float("inf")),
    ("alertas", "limite_potencia_w", float("nan")),
])
def test_substitui_valores_invalidos_por_padrao(config_path, secao, chave, valor):
    config_manager.salvar_config({secao: {chave: valor}})
    config = config_manager.carregar_config()
    assert config[secao][chave] == config_manager._DEFAULT_CONFIG[secao][chave]


def test_corrige_secoes_com_tipo_incorreto(config_path):
    config_manager.salvar_config({"serial": [], "alertas": "errado"})
    assert config_manager.carregar_config() == config_manager._DEFAULT_CONFIG


def test_copias_nao_alteram_padrao_ou_argumento(config_path):
    padrao = deepcopy(config_manager._DEFAULT_CONFIG)
    original = {"serial": {"porta": "COM9"}}
    config_manager.salvar_config(original)
    assert original == {"serial": {"porta": "COM9"}}
    config = config_manager.carregar_config()
    config["serial"]["porta"] = "COM99"
    assert config_manager.carregar_config()["serial"]["porta"] == "COM9"
    assert config_manager._DEFAULT_CONFIG == padrao


def test_falha_na_substituicao_preserva_arquivo_anterior(config_path, monkeypatch):
    config_manager.salvar_config({"serial": {"porta": "COM8"}})
    antes = config_path.read_bytes()

    def falhar(*args):
        raise PermissionError("arquivo indisponível")

    monkeypatch.setattr(config_manager.os, "replace", falhar)
    with pytest.raises(PermissionError):
        config_manager.salvar_config({"serial": {"porta": "COM9"}})
    assert config_path.read_bytes() == antes
    assert list(config_path.parent.glob(".config-*.tmp")) == []


def test_falha_na_serializacao_preserva_arquivo_anterior(config_path):
    config_manager.salvar_config({})
    antes = config_path.read_bytes()
    with pytest.raises(ValueError):
        config_manager.salvar_config({"preferencia": float("nan")})
    assert config_path.read_bytes() == antes
    assert list(config_path.parent.glob(".config-*.tmp")) == []


def test_retorna_padrao_se_recuperacao_nao_puder_gravar(config_path, monkeypatch):
    def falhar(config):
        raise PermissionError("sem permissão")

    monkeypatch.setattr(config_manager, "salvar_config", falhar)
    assert config_manager.carregar_config() == config_manager._DEFAULT_CONFIG


@pytest.mark.parametrize("regras", [None, {}, [], [True, {}], [
    {"parametro": "Corrente", "valor": True, "unidade": "A"},
    {"parametro": "Tensão", "valor": 220, "unidade": "V"},
]])
def test_recupera_regras_invalidas_sem_perder_outros_campos(config_path, regras):
    config_manager.salvar_config({"regras_limite": regras, "serial": {"porta": "COM9"}})
    config = config_manager.carregar_config()
    assert config["serial"]["porta"] == "COM9"
    assert [regra["unidade"] for regra in config["regras_limite"]] == ["A", "V"]
