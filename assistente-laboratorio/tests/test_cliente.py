"""Test del client HTTP con cui la CLI parla con l'agente (lezione 6, step 6)."""

# Il servizio dell'agente è simulato con httpx.MockTransport: nessuna porta aperta, nessun
# modello. Si controlla che il client rimandi cronologia e riassunto, li aggiorni solo se la
# chiamata riesce e trasformi ogni problema in un messaggio chiaro (ErroreTurno).

import json

import httpx
import pytest
from mcp.types import Prompt, PromptArgument

from assistente.cliente import ClienteAgente
from assistente.errori import ErroreComandoPrompt, ErroreTurno
# Importato con un altro nome: pytest raccoglierebbe "testo_elenco_prompt" come se fosse un test.
from assistente.prompt_mcp import testo_elenco_prompt as elenco_in_testo

ELENCO = [
    Prompt(
        name="spiega",
        description="Spiega un argomento al livello richiesto.",
        arguments=[
            PromptArgument(name="argomento", description="concetto da spiegare", required=True),
            PromptArgument(name="livello", description="base, intermedio o avanzato", required=False),
        ],
    ),
    Prompt(
        name="riassumi_conversazione",
        description="Riassume i turni della conversazione della sessione corrente.",
        arguments=[PromptArgument(name="stile", description="sintetico o dettagliato", required=False)],
    ),
]
ELENCO_JSON = [
    {
        "nome": "spiega",
        "descrizione": "Spiega un argomento al livello richiesto.",
        "argomenti": [
            {"nome": "argomento", "descrizione": "concetto da spiegare", "obbligatorio": True},
            {"nome": "livello", "descrizione": "base, intermedio o avanzato", "obbligatorio": False},
        ],
    },
    {
        "nome": "riassumi_conversazione",
        "descrizione": "Riassume i turni della conversazione della sessione corrente.",
        "argomenti": [{"nome": "stile", "descrizione": "sintetico o dettagliato", "obbligatorio": False}],
    },
]


# Un servizio finto: "gestore" riceve la richiesta e restituisce la risposta; le richieste
# ricevute restano in "ricevute" (metodo, percorso, corpo JSON).
def cliente_con(gestore):
    ricevute = []

    def registra(richiesta: httpx.Request) -> httpx.Response:
        corpo = json.loads(richiesta.content) if richiesta.content else None
        ricevute.append((richiesta.method, richiesta.url.path, corpo))
        return gestore(richiesta)

    client = httpx.Client(transport=httpx.MockTransport(registra), base_url="http://agente")
    return ClienteAgente("http://agente", client=client), ricevute


def turno(risposta, cronologia, riassunto=""):
    return httpx.Response(
        200, json={"risposta": risposta, "strumenti_usati": [], "cronologia": cronologia, "riassunto": riassunto}
    )


def test_chiedi_rimanda_cronologia_e_riassunto():
    prima = [{"ruolo": "utente", "testo": "Mi chiamo Luca"}, {"ruolo": "assistente", "testo": "Piacere"}]
    seconda = prima + [{"ruolo": "utente", "testo": "Come mi chiamo?"}, {"ruolo": "assistente", "testo": "Luca"}]
    risposte = [turno("Piacere", prima, "riassunto 1"), turno("Luca", seconda, "riassunto 2")]
    cliente, ricevute = cliente_con(lambda richiesta: risposte.pop(0))
    assert cliente.chiedi("Mi chiamo Luca") == "Piacere"
    assert cliente.chiedi("Come mi chiamo?") == "Luca"
    assert ricevute[0] == ("POST", "/messaggio", {"messaggio": "Mi chiamo Luca", "cronologia": [], "riassunto": ""})
    assert ricevute[1] == ("POST", "/messaggio", {"messaggio": "Come mi chiamo?", "cronologia": prima, "riassunto": "riassunto 1"})
    assert cliente.cronologia == seconda and cliente.riassunto == "riassunto 2"


def test_errore_lascia_la_memoria_invariata():
    prima = [{"ruolo": "utente", "testo": "uno"}, {"ruolo": "assistente", "testo": "primo"}]
    risposte = [
        turno("primo", prima, "r"),
        httpx.Response(503, json={"errore": "Connessione fallita: controllare LM Studio, URL e porta."}),
    ]
    cliente, _ = cliente_con(lambda richiesta: risposte.pop(0))
    cliente.chiedi("uno")
    with pytest.raises(ErroreTurno, match="^Connessione fallita: controllare LM Studio, URL e porta.$"):
        cliente.chiedi("due")
    assert cliente.cronologia == prima and cliente.riassunto == "r"


# Review Focus 4: una risposta non JSON (es. AGENTE_URL con un percorso sbagliato) non fa crollare la CLI.
def test_risposta_non_json():
    cliente, _ = cliente_con(lambda richiesta: httpx.Response(404, text="Not Found"))
    with pytest.raises(ErroreTurno) as errore:
        cliente.chiedi("ciao")
    assert str(errore.value) == "Errore dall'agente: 404"
    assert cliente.cronologia == []


def test_risposta_json_senza_errore():
    cliente, _ = cliente_con(lambda richiesta: httpx.Response(422, json={"detail": [{"msg": "x"}]}))
    with pytest.raises(ErroreTurno) as errore:
        cliente.chiedi("ciao")
    assert str(errore.value) == "Errore dall'agente: 422"


def test_agente_non_raggiungibile():
    def rifiuta(richiesta):
        raise httpx.ConnectError("rifiutata", request=richiesta)

    cliente, _ = cliente_con(rifiuta)
    with pytest.raises(ErroreTurno) as errore:
        cliente.chiedi("ciao")
    assert str(errore.value) == "Agente non raggiungibile: controllare che il servizio sia avviato e AGENTE_URL."


def test_attesa_scaduta():
    def lento(richiesta):
        raise httpx.ReadTimeout("lento", request=richiesta)

    cliente, _ = cliente_con(lento)
    with pytest.raises(ErroreTurno) as errore:
        cliente.chiedi("ciao")
    assert str(errore.value) == "Attesa scaduta: l'agente non ha risposto entro 600 secondi."


# Il testo di /prompts resta identico a quello dello step 5.
def test_elenca_prompt_ricostruisce_gli_oggetti():
    cliente, ricevute = cliente_con(lambda richiesta: httpx.Response(200, json=ELENCO_JSON))
    assert elenco_in_testo(cliente.elenca_prompt()) == elenco_in_testo(ELENCO)
    assert ricevute == [("GET", "/prompts", None)]


def test_elenca_prompt_server_giu():
    cliente, _ = cliente_con(lambda richiesta: httpx.Response(503, json={"errore": "Server MCP non disponibile: prova"}))
    with pytest.raises(ErroreTurno, match="^Server MCP non disponibile: prova$"):
        cliente.elenca_prompt()


def test_richiama_prompt_valido():
    cronologia = [{"ruolo": "utente", "testo": "Spiegami MCP"}, {"ruolo": "assistente", "testo": "È un protocollo."}]
    cliente, ricevute = cliente_con(lambda richiesta: turno("È un protocollo.", cronologia))
    assert cliente.richiama_prompt("spiega", {"argomento": "MCP"}) == "È un protocollo."
    assert ricevute == [("POST", "/prompts/spiega", {"argomenti": {"argomento": "MCP"}, "cronologia": [], "riassunto": ""})]
    assert cliente.cronologia == cronologia


def test_prompt_non_valido():
    cliente, _ = cliente_con(
        lambda richiesta: httpx.Response(400, json={"errore": "Argomenti obbligatori mancanti per 'spiega': argomento."})
    )
    with pytest.raises(ErroreComandoPrompt, match="argomento"):
        cliente.richiama_prompt("spiega", {})
    assert cliente.cronologia == []


# Il client vero: indirizzo da AGENTE_URL (con o senza "/" finale) e attesa massima di 600 secondi.
def test_client_vero():
    cliente = ClienteAgente("http://localhost:8000/")
    assert str(cliente.client.build_request("GET", "/stato").url) == "http://localhost:8000/stato"
    assert cliente.client.timeout.read == 600
