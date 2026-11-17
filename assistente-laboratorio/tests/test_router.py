# COSA PROVA QUESTO FILE
# I pezzi del router (router.py), senza modello e senza grafo: il prompt di sistema, il testo
# fisso del rifiuto, il filtro dei messaggi che il router vede, la lettura della sua risposta
# strutturata e lo schema che ammette solo le due categorie.

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from assistente.router import (
    SCHEMA_CLASSIFICAZIONE,
    leggi_classificazione,
    messaggi_per_router,
    prompt_router,
)
# Importato con un altro nome: pytest considera un test ogni funzione che inizia per "test"
# (anche "testo_rifiuto") e proverebbe a eseguirla.
from assistente.router import testo_rifiuto as rifiuto
from assistente.revisore import indicazione
from finti import ORA_FISSA, classificazione, richiesta_ora


# Il prompt contiene l'ambito letto dalla configurazione e le due categorie, ma non parla
# di strumenti: il router decide solo se la domanda è nell'ambito (requisito 04 del PDF).
def test_prompt_router_contiene_l_ambito_e_non_gli_strumenti():
    p = prompt_router("data e ora, meteo")
    assert "data e ora, meteo" in p
    assert "conversazione" in p
    assert "fuori ambito" in p
    for parola in ("strument", "ora_corrente", "calcola", "meteo_citta"):
        assert parola not in p.lower()


# Step 5: con i concetti del corso nell'ambito, gemma respingeva sempre una delle due
# domande (prove reali): il prompt ha un esempio di spiegazione di un concetto del corso e
# uno di domanda in due parti, entrambi «conversazione»; il vulcano resta «fuori ambito».
def test_prompt_router_esempi_concetto_del_corso_e_domanda_in_due_parti():
    p = prompt_router("data e ora, meteo, concetti del corso (LLM, agenti, MCP)")
    assert "«Spiegami cos'è un agente» → conversazione" in p
    assert "«Che ore sono e piove a Udine?» → conversazione" in p
    assert "«Spiegami come funziona un vulcano» → fuori ambito" in p


# Il rifiuto è un testo fisso costruito con l'ambito della configurazione.
def test_testo_rifiuto():
    assert rifiuto("data e ora, meteo") == (
        "Questa domanda è fuori dal mio ambito. Posso aiutarti con: data e ora, meteo."
    )


# Se l'ambito nel .env finisce già con un punto, il rifiuto non ne mette due di fila.
def test_testo_rifiuto_senza_doppio_punto():
    testo = rifiuto("data e ora, meteo.")
    assert testo.endswith("meteo.")
    assert ".." not in testo


# Il router vede domande e risposte di testo, mai la richiesta di strumento né il suo risultato.
def test_messaggi_per_router_toglie_il_giro_degli_strumenti():
    cronologia = [
        HumanMessage("Che ore sono?"),
        richiesta_ora("call_1"),
        ToolMessage(ORA_FISSA, tool_call_id="call_1"),
        AIMessage("Sono le 12:00."),
        HumanMessage("Grazie"),
    ]
    filtrati = messaggi_per_router(cronologia)
    assert [type(m) for m in filtrati] == [HumanMessage, AIMessage, HumanMessage]
    assert [m.content for m in filtrati] == ["Che ore sono?", "Sono le 12:00.", "Grazie"]


# Una risposta strutturata corretta diventa la coppia (categoria, motivo).
def test_leggi_classificazione_valida():
    assert leggi_classificazione(classificazione("fuori ambito", "storia")) == ("fuori ambito", "storia")


# Categoria scritta in modo diverso, motivo assente o vuoto, JSON illeggibile, risposta che non
# è un dizionario: in tutti i casi la risposta non è valida (None).
@pytest.mark.parametrize(
    "uscita",
    [
        {"parsed": {"categoria": "fuori_ambito", "motivo": "x"}},
        {"parsed": {"categoria": "Fuori ambito", "motivo": "x"}},
        {"parsed": {"categoria": "conversazione"}},
        {"parsed": {"categoria": "conversazione", "motivo": "  "}},
        {"parsed": None, "parsing_error": ValueError("json")},
        {"parsed": "testo"},
    ],
)
def test_leggi_classificazione_non_valida(uscita):
    assert leggi_classificazione(uscita) is None


# Lo schema JSON chiesto al modello ammette solo le due categorie e vuole entrambi i campi.
def test_schema_ammette_solo_le_due_categorie():
    assert SCHEMA_CLASSIFICAZIONE["properties"]["categoria"]["enum"] == ["conversazione", "fuori ambito"]
    assert set(SCHEMA_CLASSIFICAZIONE["required"]) == {"categoria", "motivo"}


# Lezione 6, step 2: l'indicazione del revisore non è una domanda dell'utente e la bozza che
# ha rifiutato non è la risposta del turno. Il router le salta entrambe e vede domande e
# risposte che si alternano (utente, assistente, utente).
def test_messaggi_per_router_salta_indicazione_e_bozza():
    cronologia = [
        HumanMessage("Che ore sono e che tempo fa?"),
        AIMessage("Sono le 12."),
        indicazione("manca il meteo"),
        AIMessage("Sono le 12 e piove."),
        HumanMessage("Grazie"),
    ]
    filtrati = messaggi_per_router(cronologia)
    assert [m.text for m in filtrati] == ["Che ore sono e che tempo fa?", "Sono le 12 e piove.", "Grazie"]
    assert [type(m) for m in filtrati] == [HumanMessage, AIMessage, HumanMessage]
