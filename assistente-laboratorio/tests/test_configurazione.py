from zoneinfo import ZoneInfo

import pytest

from assistente.configurazione import carica_configurazione, leggi_ambiente
from assistente.errori import ErroreConfigurazione

BASE = {
    "LM_BASE_URL": "http://localhost:1234/v1",
    "LM_MODEL": "modello-di-prova",
    "FUSO_ORARIO": "Europe/Rome",
}


def test_configurazione_completa():
    config = carica_configurazione({**BASE, "MAX_PASSI": "3"})
    assert config.lm_base_url == "http://localhost:1234/v1"
    assert config.lm_model == "modello-di-prova"
    assert config.fuso_orario == ZoneInfo("Europe/Rome")
    assert config.max_passi == 3


def test_default():
    config = carica_configurazione(BASE)
    assert config.max_passi == 5
    assert config.log_level == "INFO"


@pytest.mark.parametrize("nome", ["LM_BASE_URL", "LM_MODEL", "FUSO_ORARIO"])
@pytest.mark.parametrize("valore", [None, "", "  "])
def test_variabile_mancante(nome, valore):
    ambiente = dict(BASE)
    if valore is None:
        del ambiente[nome]
    else:
        ambiente[nome] = valore
    with pytest.raises(ErroreConfigurazione, match=nome):
        carica_configurazione(ambiente)


def test_fuso_non_valido():
    with pytest.raises(ErroreConfigurazione, match="FUSO_ORARIO"):
        carica_configurazione({**BASE, "FUSO_ORARIO": "Europa/Roma"})


@pytest.mark.parametrize("valore", ["zero", "0", "-1"])
def test_max_passi_non_valido(valore):
    with pytest.raises(ErroreConfigurazione, match="MAX_PASSI"):
        carica_configurazione({**BASE, "MAX_PASSI": valore})


def test_log_level_non_valido():
    with pytest.raises(ErroreConfigurazione, match="LOG_LEVEL"):
        carica_configurazione({**BASE, "LOG_LEVEL": "CHIACCHIERE"})


def test_ambiente_prevale_su_env(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("LM_MODEL=dal-file\nFUSO_ORARIO=Europe/Rome\n", encoding="utf-8")
    monkeypatch.setenv("LM_MODEL", "da-ambiente")
    monkeypatch.delenv("FUSO_ORARIO", raising=False)
    ambiente = leggi_ambiente(tmp_path)
    assert ambiente["LM_MODEL"] == "da-ambiente"
    assert ambiente["FUSO_ORARIO"] == "Europe/Rome"


def test_legge_solo_env_della_cartella(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("CHIAVE_DELLA_MADRE=1\n", encoding="utf-8")
    figlia = tmp_path / "figlia"
    figlia.mkdir()
    monkeypatch.delenv("CHIAVE_DELLA_MADRE", raising=False)
    assert "CHIAVE_DELLA_MADRE" not in leggi_ambiente(figlia)
