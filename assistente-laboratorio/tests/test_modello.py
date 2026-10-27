from zoneinfo import ZoneInfo

import httpx
import openai
from langchain_core.messages import HumanMessage

from assistente.configurazione import Configurazione
from assistente.modello import crea_modello, traduci_errore

CONFIG = Configurazione(
    lm_base_url="http://localhost:1234/v1",
    lm_model="modello-di-prova",
    fuso_orario=ZoneInfo("Europe/Rome"),
    max_passi=5,
    log_level="INFO",
)
RICHIESTA = httpx.Request("POST", "http://localhost:1234/v1/chat/completions")


def test_crea_modello_usa_la_configurazione():
    modello = crea_modello(CONFIG)
    payload = modello._get_request_payload([HumanMessage("x")])
    assert payload["model"] == "modello-di-prova"
    assert payload["temperature"] == 0.2
    assert payload["reasoning_effort"] == "none"
    assert payload["max_completion_tokens"] == 1024  # langchain-openai usa il nome nuovo
    assert str(modello.openai_api_base) == "http://localhost:1234/v1"


def test_traduci_connessione_fallita():
    errore = traduci_errore(openai.APIConnectionError(request=RICHIESTA))
    assert str(errore) == "Connessione fallita: controllare LM Studio, URL e porta."


def test_traduci_attesa_scaduta():
    errore = traduci_errore(openai.APITimeoutError(request=RICHIESTA))
    assert str(errore) == "Attesa scaduta: controllare server, carico e tempi."


def test_traduci_errore_dal_server():
    risposta = httpx.Response(404, request=RICHIESTA, text="model not found")
    errore = traduci_errore(openai.APIStatusError("x", response=risposta, body=None))
    assert str(errore) == "Errore dal server: 404 model not found"


def test_altri_errori_non_tradotti():
    assert traduci_errore(ValueError("altro")) is None
