"""Test della configurazione del back-end (lezione 6, step 7)."""

# COSA PROVA QUESTO FILE
# Il back-end legge le sue impostazioni dal .env (credenziali di PostgreSQL, indirizzo
# dell'agente, porta su cui ascolta). Qui si controlla che le obbligatorie siano richieste,
# che i valori predefiniti siano quelli della specifica e che i valori sbagliati vengano
# rifiutati con un messaggio chiaro. Nessun database né rete: solo dizionari.

import logging

import pytest

from backend.configurazione import (
    ErroreConfigurazioneBackend,
    ParametriDatabase,
    carica_configurazione,
    configura_log,
)

# Le tre variabili obbligatorie, con valori qualsiasi.
MINIME = {"POSTGRES_USER": "utente", "POSTGRES_PASSWORD": "segreta", "POSTGRES_DB": "chat"}


def test_obbligatorie_mancanti():
    with pytest.raises(ErroreConfigurazioneBackend) as errore:
        carica_configurazione({})
    assert "POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB" in str(errore.value)


def test_obbligatoria_di_soli_spazi():
    with pytest.raises(ErroreConfigurazioneBackend, match="POSTGRES_PASSWORD"):
        carica_configurazione({**MINIME, "POSTGRES_PASSWORD": "   "})


def test_predefiniti():
    config = carica_configurazione(MINIME)
    assert config.database == ParametriDatabase(
        utente="utente", password="segreta", database="chat", host="localhost", porta=5432
    )
    assert config.host == "127.0.0.1"
    assert config.porta == 8001
    assert config.agente_url == "http://localhost:8000"
    assert config.log_level == "INFO"


def test_valori_impostati():
    config = carica_configurazione(
        {
            **MINIME,
            "POSTGRES_HOST": "db",
            "POSTGRES_PORTA": "5433",
            "BACKEND_HOST": "0.0.0.0",
            "BACKEND_PORTA": "9000",
            "AGENTE_URL": "http://agente:8000",
            "LOG_LEVEL": "debug",
        }
    )
    assert (config.database.host, config.database.porta) == ("db", 5433)
    assert (config.host, config.porta) == ("0.0.0.0", 9000)
    assert config.agente_url == "http://agente:8000"
    assert config.log_level == "DEBUG"


@pytest.mark.parametrize("variabile", ["POSTGRES_PORTA", "BACKEND_PORTA"])
@pytest.mark.parametrize("valore", ["0", "70000", "x"])
def test_porte_non_valide(variabile, valore):
    with pytest.raises(ErroreConfigurazioneBackend, match=variabile):
        carica_configurazione({**MINIME, variabile: valore})


def test_agente_url_non_http():
    with pytest.raises(ErroreConfigurazioneBackend, match="AGENTE_URL"):
        carica_configurazione({**MINIME, "AGENTE_URL": "localhost:8000"})


def test_log_level_non_valido():
    with pytest.raises(ErroreConfigurazioneBackend, match="LOG_LEVEL"):
        carica_configurazione({**MINIME, "LOG_LEVEL": "TANTO"})


def test_con_database():
    parametri = carica_configurazione(MINIME).database
    prove = parametri.con_database("chat_prove")
    assert prove.database == "chat_prove"
    assert (prove.utente, prove.password, prove.host, prove.porta) == ("utente", "segreta", "localhost", 5432)
    assert parametri.database == "chat"


def test_configura_log():
    configura_log("DEBUG")
    assert logging.getLogger("backend").level == logging.DEBUG
    configura_log("INFO")
    assert logging.getLogger("backend").level == logging.INFO
