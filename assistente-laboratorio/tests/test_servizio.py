"""Test dell'API HTTP dell'agente (lezione 6, step 6), con il grafo simulato."""

# Evidenza del PDF: «test dell'API con il grafo simulato; documentazione OpenAPI consultabile».
# TestClient chiama l'app FastAPI senza aprire porte; il grafo è quello vero, ma modello,
# router, revisore e strumenti sono finti: nessun LM Studio e nessun server MCP.

import logging

import httpx
import openai
import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage
from mcp.types import Prompt, PromptArgument

from assistente.agente import Agente
from assistente.configurazione import carica_configurazione
from assistente.errori import ErroreCollegamentoMCP, ErroreComandoPrompt
from assistente.grafo import costruisci_grafo
from assistente.servizio import crea_app, main
from finti import (
    PREFERENZE_PREDEFINITE,
    ModelloFinto,
    ModelloInsistente,
    revisore_sempre_coerente,
    richiesta,
    router_sempre_conversazione,
    strumenti_fissi,
    strumento_finto,
)

AMBITO = "data e ora, calcoli"
RICHIESTA = httpx.Request("POST", "http://localhost:1234/v1/chat/completions")
CONFIG = carica_configurazione(
    {
        "LM_BASE_URL": "http://localhost:1234/v1",
        "LM_MODEL": "modello-di-prova",
        "FUSO_ORARIO": "Europe/Rome",
        "AMBITO_AGENTE": AMBITO,
    }
)
ELENCO = [
    Prompt(
        name="spiega",
        description="Spiega un argomento al livello richiesto.",
        arguments=[
            PromptArgument(name="argomento", description="concetto da spiegare", required=True),
            PromptArgument(name="livello", description="base, intermedio o avanzato", required=False),
        ],
    )
]


# Un client dell'API con il grafo vero e un modello finto a copione; tra gli strumenti c'è
# una "calcola" finta che risponde sempre 5.
def cliente_con(risposte=(), modello=None, max_passi=5):
    modello = modello or ModelloFinto(list(risposte))
    strumenti = strumenti_fissi() + [strumento_finto("calcola", lambda argomenti: "5")]
    grafo = costruisci_grafo(
        modello, strumenti, max_passi, router_sempre_conversazione(), AMBITO,
        revisore_sempre_coerente(), 2, ModelloFinto([]), 20, 6, PREFERENZE_PREDEFINITE,
    )
    agente = Agente(grafo, {}, CONFIG)
    return TestClient(crea_app(agente)), modello, agente


def righe(caplog, livello=logging.INFO):
    return [r.getMessage() for r in caplog.records if r.levelno == livello]


# ---------------- POST /messaggio ----------------


# Evidenza del PDF: chiamata HTTP con una domanda che usa un tool → risposta e traccia nei log.
def test_messaggio_con_uno_strumento(caplog):
    cliente, _, _ = cliente_con([richiesta("calcola", {"espressione": "45/9"}, "c1"), AIMessage("Fa 5.")])
    with caplog.at_level(logging.INFO, logger="assistente"):
        risposta = cliente.post("/messaggio", json={"messaggio": "Quanto fa 45/9?"})
    assert risposta.status_code == 200
    corpo = risposta.json()
    assert corpo["risposta"] == "Fa 5."
    assert corpo["strumenti_usati"] == [{"nome": "calcola", "argomenti": {"espressione": "45/9"}, "risultato": "5"}]
    assert [m["ruolo"] for m in corpo["cronologia"]] == ["utente", "assistente", "strumento", "assistente"]
    assert corpo["riassunto"] == ""
    log = righe(caplog)
    assert "richiesta endpoint=/messaggio messaggi_cronologia=0 riassunto=no" in log
    assert any(r.startswith("variant=mcp tool=calcola") for r in log)
    assert "risposta endpoint=/messaggio strumenti=['calcola'] messaggi_cronologia=4" in log


# Cronologia e riassunto arrivano dal chiamante e raggiungono il modello.
def test_messaggio_con_cronologia_e_riassunto(caplog):
    cliente, modello, _ = cliente_con([AIMessage("Ti chiami Luca.")])
    cronologia = [{"ruolo": "utente", "testo": "Ciao"}, {"ruolo": "assistente", "testo": "Ciao!"}]
    with caplog.at_level(logging.INFO, logger="assistente"):
        risposta = cliente.post(
            "/messaggio",
            json={"messaggio": "Come mi chiamo?", "cronologia": cronologia, "riassunto": "L'utente si chiama Luca."},
        )
    assert risposta.status_code == 200
    inviati = modello.chiamate[0]
    assert "L'utente si chiama Luca." in inviati[0].text  # messaggio di sistema
    assert [m.text for m in inviati[1:]] == ["Ciao", "Ciao!", "Come mi chiamo?"]
    assert len(risposta.json()["cronologia"]) == 4
    assert risposta.json()["riassunto"] == "L'utente si chiama Luca."
    assert "richiesta endpoint=/messaggio messaggi_cronologia=2 riassunto=sì" in righe(caplog)


def test_messaggio_con_accenti(caplog):
    cliente, _, _ = cliente_con([AIMessage("Perché sì, città!")])
    with caplog.at_level(logging.INFO, logger="assistente"):
        risposta = cliente.post("/messaggio", json={"messaggio": "«Perché» la città?"})
    assert risposta.status_code == 200
    assert risposta.json()["cronologia"][0]["testo"] == "«Perché» la città?"
    assert risposta.json()["risposta"] == "Perché sì, città!"


@pytest.mark.parametrize(
    "risposte, codice, messaggio",
    [
        ([openai.APIConnectionError(request=RICHIESTA)], 503, "Connessione fallita: controllare LM Studio, URL e porta."),
        ([openai.APITimeoutError(request=RICHIESTA)], 504, "Attesa scaduta: controllare server, carico e tempi."),
        (
            [openai.APIStatusError("x", response=httpx.Response(404, request=RICHIESTA, text="no"), body=None)],
            502,
            "Errore dal server: 404 no",
        ),
        ([AIMessage("")], 502, "Il modello ha restituito una risposta vuota."),
        ([ValueError("rotto")], 500, "Errore inatteso: rotto (dettagli nel log)"),
    ],
)
def test_codici_di_errore(risposte, codice, messaggio, caplog):
    cliente, _, _ = cliente_con(risposte)
    with caplog.at_level(logging.INFO, logger="assistente"):
        risposta = cliente.post("/messaggio", json={"messaggio": "ciao"})
    assert risposta.status_code == codice
    assert risposta.json() == {"errore": messaggio}
    assert f"errore endpoint=/messaggio codice={codice} messaggio={messaggio}" in righe(caplog, logging.WARNING)


def test_limite_passi_e_500():
    cliente, _, _ = cliente_con(modello=ModelloInsistente(), max_passi=1)
    risposta = cliente.post("/messaggio", json={"messaggio": "Che ore sono?"})
    assert risposta.status_code == 500
    assert risposta.json() == {"errore": "Limite di passaggi raggiunto: riprova con una domanda diversa."}


# Corpi non validi: 422 e il modello non viene chiamato.
@pytest.mark.parametrize(
    "corpo",
    [
        {"messaggio": ""},
        {"messaggio": "   "},
        {"messaggio": "ciao", "cronologia": [{"ruolo": "sistema", "testo": "x"}]},
        {"messaggio": "ciao", "cronologia": [{"ruolo": "strumento", "testo": "5", "id_chiamata": "zzz"}]},
    ],
)
def test_corpo_non_valido(corpo):
    cliente, modello, _ = cliente_con([AIMessage("non deve arrivare")])
    assert cliente.post("/messaggio", json=corpo).status_code == 422
    assert modello.chiamate == []


# ---------------- Prompt ----------------


def test_prompts_elenco(monkeypatch):
    cliente, _, _ = cliente_con()
    monkeypatch.setattr("assistente.agente.elenca_prompt_mcp", lambda connessione: ELENCO)
    risposta = cliente.get("/prompts")
    assert risposta.status_code == 200
    assert risposta.json() == [
        {
            "nome": "spiega",
            "descrizione": "Spiega un argomento al livello richiesto.",
            "argomenti": [
                {"nome": "argomento", "descrizione": "concetto da spiegare", "obbligatorio": True},
                {"nome": "livello", "descrizione": "base, intermedio o avanzato", "obbligatorio": False},
            ],
        }
    ]


def test_prompt_valido(monkeypatch):
    cliente, _, _ = cliente_con([AIMessage("MCP è un protocollo.")])
    richiesti = []

    def richiama_finto(connessione, nome, argomenti):
        richiesti.append((nome, argomenti))
        return [HumanMessage("Spiegami MCP")]

    monkeypatch.setattr("assistente.agente.richiama_prompt_mcp", richiama_finto)
    risposta = cliente.post("/prompts/spiega", json={"argomenti": {"argomento": "MCP", "livello": "base"}})
    assert risposta.status_code == 200
    assert risposta.json()["risposta"] == "MCP è un protocollo."
    assert risposta.json()["cronologia"][0]["testo"] == "Spiegami MCP"
    assert richiesti == [("spiega", {"argomento": "MCP", "livello": "base"})]


def test_prompt_non_valido(monkeypatch):
    cliente, modello, _ = cliente_con([AIMessage("non deve arrivare")])

    def rifiuta(connessione, nome, argomenti):
        raise ErroreComandoPrompt("Argomenti obbligatori mancanti: argomento")

    monkeypatch.setattr("assistente.agente.richiama_prompt_mcp", rifiuta)
    risposta = cliente.post("/prompts/spiega", json={"argomenti": {}})
    assert risposta.status_code == 400
    assert risposta.json() == {"errore": "Argomenti obbligatori mancanti: argomento"}
    assert modello.chiamate == []


def server_giu(*argomenti):
    raise ErroreCollegamentoMCP("prova")


def test_prompt_server_giu(monkeypatch):
    cliente, _, _ = cliente_con()
    monkeypatch.setattr("assistente.agente.richiama_prompt_mcp", server_giu)
    risposta = cliente.post("/prompts/spiega", json={"argomenti": {"argomento": "MCP"}})
    assert risposta.status_code == 503
    assert risposta.json() == {"errore": "Server MCP non disponibile: prova"}


def test_prompts_server_giu(monkeypatch):
    cliente, _, _ = cliente_con()
    monkeypatch.setattr("assistente.agente.elenca_prompt_mcp", server_giu)
    risposta = cliente.get("/prompts")
    assert risposta.status_code == 503
    assert risposta.json() == {"errore": "Server MCP non disponibile: prova"}


# ---------------- Stato e OpenAPI ----------------


def test_stato_tutto_ok(monkeypatch):
    cliente, _, agente = cliente_con()
    monkeypatch.setattr(agente, "stato", lambda: {"agente": "ok", "server_mcp": "ok", "modello": "ok"})
    risposta = cliente.get("/stato")
    assert risposta.status_code == 200
    assert risposta.json() == {"agente": "ok", "server_mcp": "ok", "modello": "ok"}


def test_stato_con_lm_studio_spento(monkeypatch):
    cliente, _, agente = cliente_con()
    stato = {"agente": "ok", "server_mcp": "ok", "modello": "LM Studio non raggiungibile: controllare URL e porta"}
    monkeypatch.setattr(agente, "stato", lambda: stato)
    risposta = cliente.get("/stato")
    assert risposta.status_code == 503
    assert risposta.json() == stato


def test_openapi_consultabile():
    cliente, _, _ = cliente_con()
    documento = cliente.get("/openapi.json").json()
    assert {"/messaggio", "/stato", "/prompts", "/prompts/{nome}"} <= set(documento["paths"])
    assert "richieste_strumenti" in documento["components"]["schemas"]["Messaggio"]["properties"]
    assert "RispostaErrore" in documento["components"]["schemas"]
    assert "503" in documento["paths"]["/messaggio"]["post"]["responses"]
    assert cliente.get("/docs").status_code == 200


# ---------------- Avvio del servizio ----------------


def prepara_main(tmp_path, monkeypatch, env):
    (tmp_path / ".env").write_text(env, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    for nome in ("LM_BASE_URL", "LM_MODEL", "FUSO_ORARIO", "AMBITO_AGENTE", "AGENTE_HOST", "AGENTE_PORTA"):
        monkeypatch.delenv(nome, raising=False)
    avvii = []
    monkeypatch.setattr("assistente.servizio.uvicorn.run", lambda app, host, port: avvii.append((app, host, port)))
    return avvii


ENV_VALIDO = (
    "LM_BASE_URL=http://localhost:1234/v1\nLM_MODEL=modello-di-prova\nFUSO_ORARIO=Europe/Rome\n"
    "AMBITO_AGENTE=data e ora, meteo\n"
)


def test_main_configurazione_non_valida(tmp_path, monkeypatch, capsys):
    avvii = prepara_main(tmp_path, monkeypatch, "LM_BASE_URL=http://localhost:1234/v1\n")
    assert main() == 2
    assert "Configurazione non valida" in capsys.readouterr().err
    assert avvii == []


def test_main_porta_non_valida(tmp_path, monkeypatch, capsys):
    avvii = prepara_main(tmp_path, monkeypatch, ENV_VALIDO + "AGENTE_PORTA=abc\n")
    assert main() == 2
    assert "AGENTE_PORTA" in capsys.readouterr().err
    assert avvii == []


def test_main_server_mcp_non_disponibile(tmp_path, monkeypatch, capsys):
    avvii = prepara_main(tmp_path, monkeypatch, ENV_VALIDO)
    monkeypatch.setattr("assistente.servizio.costruisci_agente", server_giu)
    assert main() == 3
    assert "Server MCP non disponibile: prova" in capsys.readouterr().err
    assert avvii == []


# Prova reale del 2026-11-16: avviato con "python -m assistente.servizio" il modulo si chiama
# __main__ e le righe INFO "richiesta/risposta endpoint=..." sparivano dal log. Qui si esegue il
# modulo proprio come __main__ e, al momento dell'avvio di uvicorn, il suo logger deve essere
# sotto "assistente" e attivo a INFO. (L'avviso di runpy dice solo che il modulo era già
# importato dagli altri test: qui è voluto.)
@pytest.mark.filterwarnings("ignore:'assistente.servizio' found in sys.modules:RuntimeWarning")
def test_log_attivo_quando_avviato_con_python_m(tmp_path, monkeypatch):
    import runpy
    import sys

    prepara_main(tmp_path, monkeypatch, ENV_VALIDO)
    monkeypatch.setattr("assistente.agente.costruisci_agente", lambda config, cartella: Agente("g", {}, config))
    visto = {}

    def run_finto(app, host, port):
        logger = sys.modules["__main__"].log
        visto["nome"], visto["info"] = logger.name, logger.isEnabledFor(logging.INFO)

    monkeypatch.setattr("uvicorn.run", run_finto)
    with pytest.raises(SystemExit) as uscita:
        runpy.run_module("assistente.servizio", run_name="__main__", alter_sys=True)
    assert uscita.value.code == 0
    assert visto == {"nome": "assistente.servizio", "info": True}


# PowerShell 5.1 (Invoke-RestMethod) legge come ISO-8859-1 un JSON senza charset e mostra
# «Ã¨» al posto di «è»: le risposte dichiarano charset=utf-8, anche quelle di errore.
def test_risposte_dichiarano_utf8():
    cliente, _, _ = cliente_con([AIMessage("È così.")])
    assert cliente.post("/messaggio", json={"messaggio": "ciao"}).headers["content-type"] == "application/json; charset=utf-8"
    assert cliente.post("/messaggio", json={"messaggio": "x"}).headers["content-type"] == "application/json; charset=utf-8"


def test_main_avvia_uvicorn(tmp_path, monkeypatch):
    avvii = prepara_main(tmp_path, monkeypatch, ENV_VALIDO)
    cartelle = []
    monkeypatch.setattr(
        "assistente.servizio.costruisci_agente", lambda config, cartella: cartelle.append(cartella) or Agente("g", {}, config)
    )
    assert main() == 0
    assert cartelle == [tmp_path]
    assert [(host, porta) for _, host, porta in avvii] == [("127.0.0.1", 8000)]
