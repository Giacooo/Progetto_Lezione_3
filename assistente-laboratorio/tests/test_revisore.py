# COSA PROVA QUESTO FILE
# I pezzi del revisore (revisore.py), senza modello e senza grafo: il prompt di sistema, lo
# schema che ammette solo «sì» e «no», la lettura della sua risposta strutturata, il testo
# dell'indicazione per l'agente e la scelta di domanda e risposta da giudicare.

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from assistente.revisore import (
    SCHEMA_VALUTAZIONE,
    domanda_e_risposta,
    e_indicazione,
    indicazione,
    leggi_valutazione,
    messaggi_per_revisore,
    prompt_revisore,
)
from finti import ORA_FISSA, richiesta_ora, valutazione


# Il prompt elenca le due risposte ammesse ma non parla di strumenti: il revisore giudica solo
# se la risposta è coerente con la domanda, non come l'agente l'ha ottenuta.
def test_prompt_revisore_non_nomina_gli_strumenti():
    p = prompt_revisore()
    assert "sì" in p
    assert "no" in p
    for parola in ("strument", "ora_corrente", "calcola", "meteo_citta"):
        assert parola not in p.lower()


# Lo schema ammette per "coerente" solo «sì» e «no» e rende obbligatori entrambi i campi.
def test_schema_ammette_solo_si_e_no():
    assert SCHEMA_VALUTAZIONE["properties"]["coerente"]["enum"] == ["sì", "no"]
    assert set(SCHEMA_VALUTAZIONE["required"]) == {"coerente", "motivo"}


# Una valutazione valida restituisce (coerente, motivo), con il motivo senza spazi ai bordi.
def test_leggi_valutazione_valida():
    assert leggi_valutazione(valutazione("no", " manca il meteo ")) == ("no", "manca il meteo")


# Tutto ciò che non è esattamente «sì»/«no» con un motivo vero è una risposta non valida.
@pytest.mark.parametrize(
    "uscita",
    [
        {"parsed": {"coerente": "si", "motivo": "x"}},
        {"parsed": {"coerente": "Sì", "motivo": "x"}},
        {"parsed": {"coerente": True, "motivo": "x"}},
        {"parsed": {"coerente": "sì"}},
        {"parsed": {"coerente": "sì", "motivo": "  "}},
        {"parsed": None, "parsing_error": ValueError("json")},
        {"parsed": "testo"},
    ],
)
def test_leggi_valutazione_non_valida(uscita):
    assert leggi_valutazione(uscita) is None


# L'indicazione è un messaggio "utente" con il nome del revisore e contiene il motivo.
def test_indicazione_contiene_il_motivo():
    m = indicazione("manca il meteo")
    assert isinstance(m, HumanMessage)
    assert m.name == "revisore"
    assert "manca il meteo" in m.text
    assert e_indicazione(m)
    assert not e_indicazione(HumanMessage("ciao"))


# Il revisore giudica la domanda del turno (non un'indicazione, non un turno precedente)
# e l'ultima risposta dell'agente.
def test_domanda_e_risposta_salta_strumenti_e_indicazioni():
    messaggi = [
        HumanMessage("Mi chiamo Luca"),
        AIMessage("Piacere"),
        HumanMessage("Che ore sono e che tempo fa?"),
        richiesta_ora("call_1"),
        ToolMessage(ORA_FISSA, tool_call_id="call_1"),
        AIMessage("Sono le 12."),
        indicazione("manca il meteo"),
        AIMessage("Sono le 12 e piove."),
    ]
    assert domanda_e_risposta(messaggi) == ("Che ore sono e che tempo fa?", "Sono le 12 e piove.")


# Al revisore arrivano solo il suo prompt e un messaggio con domanda e risposta.
def test_messaggi_per_revisore():
    m = messaggi_per_revisore("D?", "R.")
    assert len(m) == 2
    assert isinstance(m[0], SystemMessage)
    assert m[0].content == prompt_revisore()
    assert "D?" in m[1].text and "R." in m[1].text
