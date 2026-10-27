import logging

import httpx
import openai
import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from assistente.conversazione import Conversazione
from assistente.errori import ErroreTurno
from assistente.grafo import costruisci_grafo
from finti import ModelloFinto, ModelloInsistente, richiesta_ora, strumenti_fissi

RICHIESTA = httpx.Request("POST", "http://localhost:1234/v1/chat/completions")


def conversazione_con(risposte):
    modello = ModelloFinto(risposte)
    return Conversazione(costruisci_grafo(modello, strumenti_fissi(), 5)), modello


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


def test_limite_passi_lascia_la_cronologia_invariata():
    conversazione = Conversazione(costruisci_grafo(ModelloInsistente(), strumenti_fissi(), 3))
    with pytest.raises(ErroreTurno) as errore:
        conversazione.chiedi("Che ore sono?")
    assert str(errore.value) == "Limite di passaggi raggiunto: riprova con una domanda diversa."
    assert conversazione.cronologia == []


def test_cronologia_conserva_il_giro_dello_strumento():
    conversazione, _ = conversazione_con(
        [richiesta_ora(), AIMessage("Sono le 12:00."), AIMessage("Prego.")]
    )
    conversazione.chiedi("Che ore sono?")
    conversazione.chiedi("Grazie")
    assert [type(m) for m in conversazione.cronologia] == [
        HumanMessage, AIMessage, ToolMessage, AIMessage, HumanMessage, AIMessage
    ]


def test_errore_del_server_finisce_nel_log(caplog):
    conversazione, _ = conversazione_con([openai.APIConnectionError(request=RICHIESTA)])
    with caplog.at_level(logging.INFO, logger="assistente"), pytest.raises(ErroreTurno):
        conversazione.chiedi("ciao")
    errori = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert errori == ["Turno fallito: Connessione fallita: controllare LM Studio, URL e porta."]


def test_risposta_vuota_finisce_nel_log(caplog):
    conversazione, _ = conversazione_con([AIMessage("")])
    with caplog.at_level(logging.INFO, logger="assistente"), pytest.raises(ErroreTurno):
        conversazione.chiedi("ciao")
    avvisi = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert avvisi == ["Turno fallito: Il modello ha restituito una risposta vuota."]


def test_errore_inatteso_non_chiude_la_sessione(caplog):
    conversazione, _ = conversazione_con([AIMessage("primo"), ValueError("risposta malformata"), AIMessage("terzo")])
    conversazione.chiedi("uno")
    prima = list(conversazione.cronologia)
    with caplog.at_level(logging.INFO, logger="assistente"), pytest.raises(ErroreTurno) as errore:
        conversazione.chiedi("due")
    assert str(errore.value) == "Errore inatteso: risposta malformata (dettagli nel log)"
    assert conversazione.cronologia == prima
    registrati = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert registrati and registrati[0].exc_info is not None  # traceback completo nel log
    assert conversazione.chiedi("tre") == "terzo"
