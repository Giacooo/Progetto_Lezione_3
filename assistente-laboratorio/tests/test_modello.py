# COSA PROVA QUESTO FILE
# Il collegamento al modello (modello.py): che venga configurato come previsto e che
# gli errori tecnici vengano tradotti nei messaggi in italiano. Non chiama LM Studio.
# Nota: il primo test crea il vero oggetto ChatOpenAI, che importa la libreria "openai":
# è quello che su questo PC Windows può essere bloccato da Smart App Control.

from zoneinfo import ZoneInfo

import httpx
import openai
from langchain_core.messages import HumanMessage

from assistente.configurazione import Configurazione
from assistente.modello import crea_modello, traduci_errore

# Una configurazione di prova, costruita a mano.
CONFIG = Configurazione(
    lm_base_url="http://localhost:1234/v1",
    lm_model="modello-di-prova",
    fuso_orario=ZoneInfo("Europe/Rome"),
    max_passi=5,
    log_level="INFO",
)
# Una richiesta HTTP "di facciata", per costruire gli errori di prova.
RICHIESTA = httpx.Request("POST", "http://localhost:1234/v1/chat/completions")


# Il modello creato usa davvero i valori della configurazione e le impostazioni previste:
# modello giusto, temperatura 0.2, ragionamento spento, 1024 token, indirizzo di LM Studio.
# (Il payload è il "pacco" che verrebbe spedito, controllato senza spedirlo.)
def test_crea_modello_usa_la_configurazione():
    modello = crea_modello(CONFIG)
    payload = modello._get_request_payload([HumanMessage("x")])
    assert payload["model"] == "modello-di-prova"
    assert payload["temperature"] == 0.2
    assert payload["reasoning_effort"] == "none"
    assert payload["max_completion_tokens"] == 1024  # langchain-openai usa il nome nuovo
    assert str(modello.openai_api_base) == "http://localhost:1234/v1"


# Server irraggiungibile -> messaggio "Connessione fallita".
def test_traduci_connessione_fallita():
    errore = traduci_errore(openai.APIConnectionError(request=RICHIESTA))
    assert str(errore) == "Connessione fallita: controllare LM Studio, URL e porta."


# Attesa troppo lunga -> messaggio "Attesa scaduta" (e non "Connessione fallita").
def test_traduci_attesa_scaduta():
    errore = traduci_errore(openai.APITimeoutError(request=RICHIESTA))
    assert str(errore) == "Attesa scaduta: controllare server, carico e tempi."


# Il server risponde con un errore (404) -> il messaggio riporta codice e testo.
def test_traduci_errore_dal_server():
    risposta = httpx.Response(404, request=RICHIESTA, text="model not found")
    errore = traduci_errore(openai.APIStatusError("x", response=risposta, body=None))
    assert str(errore) == "Errore dal server: 404 model not found"


# Un errore di altro tipo non viene tradotto: la funzione restituisce None.
def test_altri_errori_non_tradotti():
    assert traduci_errore(ValueError("altro")) is None
