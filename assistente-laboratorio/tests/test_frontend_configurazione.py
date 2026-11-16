"""Test della configurazione del front-end (lezione 6, step 8)."""

# COSA PROVA QUESTO FILE
# frontend/configurazione.py legge l'indirizzo del back-end (BACKEND_URL) e dove ascolta il
# front-end (FRONTEND_HOST, FRONTEND_PORTA): tutto da configurazione, niente scritto nel codice.

import pytest

from frontend.configurazione import (
    ErroreConfigurazioneFrontend,
    carica_configurazione,
    leggi_ambiente,
)


def test_predefiniti():
    config = carica_configurazione({})
    assert (config.backend_url, config.host, config.porta, config.log_level) == (
        "http://127.0.0.1:8001", "127.0.0.1", 8002, "INFO")


def test_valori_dall_ambiente():
    config = carica_configurazione({
        "BACKEND_URL": " http://backend:8001/ ", "FRONTEND_HOST": "0.0.0.0",
        "FRONTEND_PORTA": "8102", "LOG_LEVEL": "debug",
    })
    assert config.backend_url == "http://backend:8001"
    assert (config.host, config.porta, config.log_level) == ("0.0.0.0", 8102, "DEBUG")


def test_backend_url_non_valido():
    with pytest.raises(ErroreConfigurazioneFrontend, match="BACKEND_URL"):
        carica_configurazione({"BACKEND_URL": "ftp://x"})


@pytest.mark.parametrize("porta", ["0", "65536", "abc"])
def test_porta_non_valida(porta):
    with pytest.raises(ErroreConfigurazioneFrontend, match="FRONTEND_PORTA"):
        carica_configurazione({"FRONTEND_PORTA": porta})


def test_log_level_non_valido():
    with pytest.raises(ErroreConfigurazioneFrontend, match="LOG_LEVEL"):
        carica_configurazione({"LOG_LEVEL": "molto"})


def test_env_sovrascritto_dall_ambiente(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("FRONTEND_PORTA=9000\nBACKEND_URL=http://da-file:1\n", encoding="utf-8")
    monkeypatch.setenv("FRONTEND_PORTA", "9001")
    monkeypatch.delenv("BACKEND_URL", raising=False)
    ambiente = leggi_ambiente(tmp_path)
    assert ambiente["FRONTEND_PORTA"] == "9001"
    assert ambiente["BACKEND_URL"] == "http://da-file:1"
