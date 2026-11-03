"""Grafo LangGraph del turno di conversazione.

START → llm ─(richiesta di strumento e passi < limite)→ strumenti → llm
            └(nessuna richiesta, oppure limite raggiunto)→ END
"""

# COSA FA QUESTO FILE (è il cuore della lezione 4)
# Descrive il "percorso" che compie ogni domanda, come una mappa della metropolitana:
#   - le STAZIONI sono i NODI:   "llm" (chiama il modello) e "strumenti" (esegue lo strumento)
#   - i BINARI sono gli ARCHI:   le frecce che dicono quale nodo viene dopo
#   - lo SCAMBIO è l'INSTRADAMENTO: la funzione "instrada" decide dove andare
#   - il FOGLIO che passa di mano in mano è lo STATO: i messaggi e il contatore dei passi

import logging
from collections.abc import Sequence
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import AnyMessage, SystemMessage, ToolMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

log = logging.getLogger(__name__)

# Le istruzioni date al modello all'inizio di OGNI chiamata (il "prompt di sistema").
# Gli dicono chi è, come rispondere e, soprattutto, quando usare lo strumento orologio.
# Un modello piccolo segue queste istruzioni solo in parte: per questo conta come sono scritte.
PROMPT_SISTEMA = (
    "Sei l'assistente del laboratorio. Rispondi in italiano, in modo breve e chiaro. "
    "Hai a disposizione lo strumento ora_corrente, che restituisce data e ora attuali: "
    "chiamalo ogni volta che la domanda riguarda data, ora o giorno della settimana."
)


# LO STATO: il foglio che passa da un nodo all'altro. Contiene due cose:
class StatoTurno(TypedDict):
    # add_messages aggiunge i nuovi messaggi alla lista invece di sostituirla.
    # (La conversazione cresce: domanda, richiesta di strumento, risultato, risposta...)
    messages: Annotated[list[AnyMessage], add_messages]
    # Quante volte, in questo turno, abbiamo chiamato il modello. Serve per il limite.
    passi: int


def costruisci_grafo(modello: Runnable, strumenti: Sequence[BaseTool], max_passi: int):
    """Grafo del turno.

    `modello` deve già conoscere gli strumenti (per LM Studio: `bind_tools`);
    `max_passi` è il numero massimo di chiamate al modello per turno.
    """
    # Un "elenco telefonico" degli strumenti: dato il nome (es. "ora_corrente")
    # si trova subito lo strumento corrispondente.
    per_nome = {strumento.name: strumento for strumento in strumenti}

    # ---------------- NODO 1: "llm" ----------------
    # Chiama il modello e restituisce la sua risposta (che può essere testo oppure
    # una richiesta di strumento).
    def llm(stato: StatoTurno) -> dict:
        # Questo è il passo numero (passi già fatti + 1).
        passo = stato["passi"] + 1
        log.info("Inizio chiamata al modello (passo %d/%d)", passo, max_passi)
        # Invia al modello: prima le istruzioni di sistema, poi tutta la conversazione.
        risposta = modello.invoke([SystemMessage(PROMPT_SISTEMA), *stato["messages"]])
        # Per il log: il modello ha chiesto strumenti o ha dato la risposta finale?
        esito = f"richieste di strumenti: {len(risposta.tool_calls)}" if risposta.tool_calls else "risposta finale"
        log.info("Fine chiamata al modello (passo %d/%d): %s", passo, max_passi, esito)
        # Restituisce le novità da aggiungere allo stato: la risposta e il nuovo contatore.
        return {"messages": [risposta], "passi": passo}

    # ---------------- NODO 2: "strumenti" ----------------
    # Esegue DAVVERO gli strumenti che il modello ha chiesto. Il modello non esegue nulla:
    # scrive solo la richiesta; qui il programma fa il lavoro vero.
    def esegui_strumenti(stato: StatoTurno) -> dict:
        risultati = []
        # L'ultimo messaggio è la risposta del modello: contiene le richieste (tool_calls).
        for richiesta in stato["messages"][-1].tool_calls:
            # Ogni richiesta ha un nome (quale strumento) e degli argomenti.
            nome, argomenti = richiesta["name"], richiesta["args"]
            log.info("Richiesta strumento %s con argomenti %s", nome, argomenti)
            strumento = per_nome.get(nome)
            if strumento is None:
                # Il modello ha chiesto uno strumento che non esiste: non andiamo in crash,
                # rispondiamo "sconosciuto" e lasciamo un avviso nel log.
                risultato = f"Strumento sconosciuto: {nome}"
                log.warning(risultato)
            else:
                # Esegue lo strumento (qui: legge l'ora vera) e ne trasforma il risultato in testo.
                risultato = str(strumento.invoke(argomenti))
                log.info("Risultato strumento %s: %s", nome, risultato)
            # Impacchetta il risultato come "messaggio di strumento". Il tool_call_id lo collega
            # alla richiesta, così il modello sa a quale domanda sta rispondendo il risultato.
            risultati.append(ToolMessage(content=risultato, tool_call_id=richiesta["id"], name=nome))
        return {"messages": risultati}

    # ---------------- LO SCAMBIO: "instrada" ----------------
    # Dopo il nodo "llm" decide dove andare. Può restituire "strumenti" oppure END (fine).
    def instrada(stato: StatoTurno) -> Literal["strumenti", "__end__"]:
        # Il modello non ha chiesto strumenti: ha dato la risposta, il turno è finito.
        if not stato["messages"][-1].tool_calls:
            return END
        # Ha chiesto uno strumento, ma abbiamo già usato tutti i passi consentiti: ci fermiamo.
        # Questo è il freno di sicurezza: impedisce che il ciclo giri all'infinito.
        if stato["passi"] >= max_passi:
            log.warning("Limite di passaggi raggiunto (%d): richiesta di strumento non eseguita", max_passi)
            return END
        # Altrimenti si va ad eseguire lo strumento.
        return "strumenti"

    # ---------------- COSTRUZIONE DELLA MAPPA ----------------
    # Crea un grafo vuoto che lavora sul tipo di stato definito sopra.
    grafo = StateGraph(StatoTurno)
    # Aggiunge le due stazioni, ognuna con il suo nome e la funzione da eseguire.
    grafo.add_node("llm", llm)
    grafo.add_node("strumenti", esegui_strumenti)
    # Si parte sempre dal nodo "llm".
    grafo.add_edge(START, "llm")
    # Dopo "llm" non c'è una freccia sola: decide la funzione "instrada".
    grafo.add_conditional_edges("llm", instrada)
    # Dopo "strumenti" si torna SEMPRE a "llm", perché il modello deve leggere il risultato.
    grafo.add_edge("strumenti", "llm")
    # "Compila" la mappa: la rende un oggetto pronto da usare con .invoke(...).
    return grafo.compile()
