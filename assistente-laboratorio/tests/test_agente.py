"""Test del modulo dell'agente (lezione 6, step 6): turno senza stato, costruzione, prompt e stato."""

# L'agente non ricorda nulla tra un turno e l'altro: riceve cronologia e riassunto, esegue il
# grafo e restituisce tutto aggiornato, insieme agli strumenti usati in QUESTO turno.
# Grafo vero, modello e strumenti finti: nessun LM Studio e nessun server MCP.

import httpx
import openai
import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from assistente.agente import ErroreTurnoAgente, esegui_turno
from assistente.formato import StrumentoUsato
from assistente.grafo import costruisci_grafo
from finti import (
    ORA_FISSA,
    PREFERENZE_PREDEFINITE,
    ModelloFinto,
    ModelloInsistente,
    revisore_sempre_coerente,
    richiesta_ora,
    router_sempre_conversazione,
    strumenti_fissi,
)

RICHIESTA = httpx.Request("POST", "http://localhost:1234/v1/chat/completions")
AMBITO = "data e ora, meteo"


# Grafo vero con modello finto a copione; router e revisore finti sempre favorevoli.
def grafo_con(risposte, max_passi=5, riassuntore=None, soglia_riassunto=20, messaggi_da_tenere=6, modello=None):
    modello = modello or ModelloFinto(risposte)
    grafo = costruisci_grafo(
        modello,
        strumenti_fissi(),
        max_passi,
        router_sempre_conversazione(),
        AMBITO,
        revisore_sempre_coerente(),
        2,
        riassuntore if riassuntore is not None else ModelloFinto([]),
        soglia_riassunto,
        messaggi_da_tenere,
        PREFERENZE_PREDEFINITE,
    )
    return grafo, modello


def giro_dell_ora(id_chiamata="c1"):
    return [
        HumanMessage("Che ore sono?"),
        richiesta_ora(id_chiamata),
        ToolMessage(ORA_FISSA, tool_call_id=id_chiamata, name="ora_corrente"),
        AIMessage("Sono le 12."),
    ]


# ---------------- Turno senza stato ----------------


def test_turno_restituisce_cronologia_e_riassunto():
    grafo, _ = grafo_con([AIMessage("ciao")])
    esito = esegui_turno(grafo, [], [HumanMessage("salve")], "")
    assert esito.risposta == "ciao"
    assert [type(m) for m in esito.cronologia] == [HumanMessage, AIMessage]
    assert [m.text for m in esito.cronologia] == ["salve", "ciao"]
    assert esito.riassunto == ""
    assert esito.strumenti_usati == []


# La cronologia ricevuta non viene toccata: l'aggiornamento è solo nell'esito.
def test_turno_non_modifica_la_cronologia_ricevuta():
    grafo, _ = grafo_con([AIMessage("seconda risposta")])
    ricevuta = [HumanMessage("prima"), AIMessage("prima risposta")]
    esito = esegui_turno(grafo, ricevuta, [HumanMessage("seconda")], "")
    assert len(ricevuta) == 2 and [m.text for m in ricevuta] == ["prima", "prima risposta"]
    assert [m.text for m in esito.cronologia] == ["prima", "prima risposta", "seconda", "seconda risposta"]


def test_strumenti_usati_del_turno():
    grafo, _ = grafo_con([richiesta_ora("c1"), AIMessage("Sono le 12")])
    esito = esegui_turno(grafo, [], [HumanMessage("Che ore sono?")], "")
    assert esito.strumenti_usati == [StrumentoUsato(nome="ora_corrente", argomenti={}, risultato=ORA_FISSA)]


# Gli strumenti già presenti nella cronologia ricevuta appartengono ai turni precedenti.
def test_strumenti_dei_turni_precedenti_non_contano():
    grafo, _ = grafo_con([AIMessage("Prego.")])
    esito = esegui_turno(grafo, giro_dell_ora(), [HumanMessage("Grazie")], "")
    assert esito.strumenti_usati == []


# Il riassunto toglie il primo turno; il vecchio giro dell'orologio (c1) resta nella cronologia
# perché il taglio non lo separa: negli strumenti usati c'è solo quello del turno in corso (c9).
def test_strumenti_usati_dopo_la_compressione():
    riassuntore = ModelloFinto([AIMessage("riassunto di prova")])
    grafo, _ = grafo_con(
        [richiesta_ora("c9"), AIMessage("Sono le 12 anche adesso.")],
        riassuntore=riassuntore,
        soglia_riassunto=4,
        messaggi_da_tenere=2,
    )
    ricevuta = [HumanMessage("Mi chiamo Luca"), AIMessage("Piacere, Luca."), *giro_dell_ora("c1")]
    esito = esegui_turno(grafo, ricevuta, [HumanMessage("E adesso?")], "")
    assert esito.riassunto == "riassunto di prova"
    assert not any(m.text == "Mi chiamo Luca" for m in esito.cronologia)
    assert any(isinstance(m, ToolMessage) and m.tool_call_id == "c1" for m in esito.cronologia)
    assert esito.strumenti_usati == [StrumentoUsato(nome="ora_corrente", argomenti={}, risultato=ORA_FISSA)]


# Ogni errore porta il suo tipo (il servizio ne ricava il codice HTTP) e il messaggio di sempre.
@pytest.mark.parametrize(
    "risposte, tipo, messaggio",
    [
        ([openai.APIConnectionError(request=RICHIESTA)], "connessione", "Connessione fallita: controllare LM Studio, URL e porta."),
        ([openai.APITimeoutError(request=RICHIESTA)], "attesa", "Attesa scaduta: controllare server, carico e tempi."),
        (
            [openai.APIStatusError("x", response=httpx.Response(404, request=RICHIESTA, text="no"), body=None)],
            "server",
            "Errore dal server: 404 no",
        ),
        ([ValueError("risposta malformata")], "inatteso", "Errore inatteso: risposta malformata (dettagli nel log)"),
        ([AIMessage("")], "risposta_vuota", "Il modello ha restituito una risposta vuota."),
    ],
)
def test_errori_classificati(risposte, tipo, messaggio):
    grafo, _ = grafo_con(risposte)
    with pytest.raises(ErroreTurnoAgente) as errore:
        esegui_turno(grafo, [], [HumanMessage("ciao")], "")
    assert errore.value.tipo == tipo
    assert str(errore.value) == messaggio


def test_limite_passi_classificato():
    grafo, _ = grafo_con([], max_passi=1, modello=ModelloInsistente())
    with pytest.raises(ErroreTurnoAgente) as errore:
        esegui_turno(grafo, [], [HumanMessage("Che ore sono?")], "")
    assert errore.value.tipo == "limite_passi"
    assert str(errore.value) == "Limite di passaggi raggiunto: riprova con una domanda diversa."
