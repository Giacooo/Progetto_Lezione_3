# COSA PROVA QUESTO FILE
# Che la lettura e il controllo della configurazione (configurazione.py) funzionino:
# valori giusti accettati, valori mancanti o sbagliati rifiutati con un messaggio chiaro.
# Ogni funzione che inizia con "test_" è un test: pytest la esegue e controlla gli "assert"
# (le affermazioni che devono essere vere).

from zoneinfo import ZoneInfo

import pytest

from assistente.configurazione import carica_configurazione, leggi_ambiente
from assistente.errori import ErroreConfigurazione

# Una configurazione minima ma valida, riusata da molti test.
BASE = {
    "LM_BASE_URL": "http://localhost:1234/v1",
    "LM_MODEL": "modello-di-prova",
    "FUSO_ORARIO": "Europe/Rome",
}


# Con tutti i valori giusti, la scheda di configurazione contiene quello che ci aspettiamo.
def test_configurazione_completa():
    config = carica_configurazione({**BASE, "MAX_PASSI": "3"})
    assert config.lm_base_url == "http://localhost:1234/v1"
    assert config.lm_model == "modello-di-prova"
    assert config.fuso_orario == ZoneInfo("Europe/Rome")
    assert config.max_passi == 3


# Se MAX_PASSI e LOG_LEVEL non ci sono, valgono i valori predefiniti: 5 e INFO.
def test_default():
    config = carica_configurazione(BASE)
    assert config.max_passi == 5
    assert config.log_level == "INFO"


# Provato 9 volte (3 variabili x 3 casi): variabile assente, vuota, o fatta di soli spazi.
# In ogni caso deve comparire l'errore e il messaggio deve citare il nome della variabile.
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


# Un fuso inesistente ("Europa/Roma") viene rifiutato.
def test_fuso_non_valido():
    with pytest.raises(ErroreConfigurazione, match="FUSO_ORARIO"):
        carica_configurazione({**BASE, "FUSO_ORARIO": "Europa/Roma"})


# MAX_PASSI deve essere un intero maggiore di zero: "zero", 0 e -1 vengono rifiutati.
@pytest.mark.parametrize("valore", ["zero", "0", "-1"])
def test_max_passi_non_valido(valore):
    with pytest.raises(ErroreConfigurazione, match="MAX_PASSI"):
        carica_configurazione({**BASE, "MAX_PASSI": valore})


# Un livello di log inventato viene rifiutato.
def test_log_level_non_valido():
    with pytest.raises(ErroreConfigurazione, match="LOG_LEVEL"):
        carica_configurazione({**BASE, "LOG_LEVEL": "CHIACCHIERE"})


# Se una variabile è sia nel file .env sia nel sistema, vince quella del sistema.
# (tmp_path è una cartella temporanea; monkeypatch modifica le variabili solo per il test.)
def test_ambiente_prevale_su_env(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("LM_MODEL=dal-file\nFUSO_ORARIO=Europe/Rome\n", encoding="utf-8")
    monkeypatch.setenv("LM_MODEL", "da-ambiente")
    monkeypatch.delenv("FUSO_ORARIO", raising=False)
    ambiente = leggi_ambiente(tmp_path)
    assert ambiente["LM_MODEL"] == "da-ambiente"
    assert ambiente["FUSO_ORARIO"] == "Europe/Rome"


# Si legge solo il .env della cartella indicata, non quello di una cartella madre.
def test_legge_solo_env_della_cartella(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("CHIAVE_DELLA_MADRE=1\n", encoding="utf-8")
    figlia = tmp_path / "figlia"
    figlia.mkdir()
    monkeypatch.delenv("CHIAVE_DELLA_MADRE", raising=False)
    assert "CHIAVE_DELLA_MADRE" not in leggi_ambiente(figlia)


# Con livello INFO, i log del nostro programma sono attivi mentre quelli delle librerie
# esterne (qui "httpx2", nome di prova) mostrano solo avvisi ed errori.
def test_log_solo_dell_assistente_a_info():
    import logging

    from assistente.configurazione import configura_log

    configura_log("INFO")
    assert logging.getLogger("assistente.grafo").isEnabledFor(logging.INFO)
    assert not logging.getLogger("httpx2").isEnabledFor(logging.INFO)
    assert logging.getLogger("httpx2").isEnabledFor(logging.WARNING)
