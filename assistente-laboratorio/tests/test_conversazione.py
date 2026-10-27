import logging

import httpx
import openai
import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from assistente.conversazione import Conversazione
from assistente.errori import ErroreTurno
from assistente.grafo import costruisci_grafo
from finti import ModelloFinto

RICHIESTA = httpx.Request("POST", "http://localhost:1234/v1/chat/completions")


def conversazione_con(risposte):
    modello = ModelloFinto(risposte)
    return Conversazione(costruisci_grafo(modello)), modello


def test_cronologia_dopo_due_turni():
    conversazione, modello = conversazione_con([AIMessage("Ciao Luca"), AIMessage("Ti chiami Luca")])
    assert conversazione.chiedi("Mi chiamo Luca") == "Ciao Luca"
    assert conversazione.chiedi("Come mi chiamo?") == "Ti chiami Luca"
    cronologia = conversazione.cronologia
    assert [type(m) for m in cronologia] == [HumanMessage, AIMessage, HumanMessage, AIMessage]
    assert [m.content for m in cronologia] == ["Mi chiamo Luca", "Ciao Luca", "Come mi chiamo?", "Ti chiami Luca"]
    seconda = modello.chiamate[1]
    assert isinstance(seconda[0], SystemMessage)
    assert [m.content for m in seconda[1:]] == ["Mi chiamo Luca", "Ciao Luca", "Come mi chiamo?"]


@pytest.mark.parametrize(
    "eccezione, messaggio",
    [
        (openai.APIConnectionError(request=RICHIESTA), "Connessione fallita: controllare LM Studio, URL e porta."),
        (openai.APITimeoutError(request=RICHIESTA), "Attesa scaduta: controllare server, carico e tempi."),
        (
            openai.APIStatusError("x", response=httpx.Response(400, request=RICHIESTA, text="bad"), body=None),
            "Errore dal server: 400 bad",
        ),
    ],
)
def test_errore_lascia_la_cronologia_invariata(eccezione, messaggio):
    conversazione, _ = conversazione_con([AIMessage("primo"), eccezione, AIMessage("terzo")])
    conversazione.chiedi("uno")
    prima = list(conversazione.cronologia)
    with pytest.raises(ErroreTurno) as errore:
        conversazione.chiedi("due")
    assert str(errore.value) == messaggio
    assert conversazione.cronologia == prima
    assert conversazione.chiedi("tre") == "terzo"
    assert [m.content for m in conversazione.cronologia] == ["uno", "primo", "tre", "terzo"]


def test_risposta_vuota_e_un_errore():
    conversazione, _ = conversazione_con([AIMessage("")])
    with pytest.raises(ErroreTurno, match="^Il modello ha restituito una risposta vuota.$"):
        conversazione.chiedi("ciao")
    assert conversazione.cronologia == []


def test_log_chiamata_al_modello(caplog):
    conversazione, _ = conversazione_con([AIMessage("ok")])
    with caplog.at_level(logging.INFO, logger="assistente"):
        conversazione.chiedi("ciao")
    righe = [r.getMessage() for r in caplog.records if r.name.startswith("assistente")]
    assert any("Inizio chiamata al modello" in r and "passo 1" in r for r in righe)
    assert any("Fine chiamata al modello" in r and "passo 1" in r for r in righe)
