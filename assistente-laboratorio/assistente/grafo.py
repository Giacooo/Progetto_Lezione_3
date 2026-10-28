"""Grafo LangGraph del turno di conversazione.

START → llm ─(richiesta di strumento e passi < limite)→ strumenti → llm
            └(nessuna richiesta, oppure limite raggiunto)→ END
"""

import logging
from collections.abc import Sequence
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import AnyMessage, SystemMessage, ToolMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

log = logging.getLogger(__name__)

PROMPT_SISTEMA = (
    "Sei l'assistente del laboratorio. Rispondi in italiano, in modo breve e chiaro. "
    "Hai a disposizione lo strumento ora_corrente, che restituisce data e ora attuali: "
    "chiamalo ogni volta che la domanda riguarda data, ora o giorno della settimana."
)


class StatoTurno(TypedDict):
    # add_messages aggiunge i nuovi messaggi alla lista invece di sostituirla.
    messages: Annotated[list[AnyMessage], add_messages]
    passi: int


def costruisci_grafo(modello: Runnable, strumenti: Sequence[BaseTool], max_passi: int):
    """Grafo del turno.

    `modello` deve già conoscere gli strumenti (per LM Studio: `bind_tools`);
    `max_passi` è il numero massimo di chiamate al modello per turno.
    """
    per_nome = {strumento.name: strumento for strumento in strumenti}

    def llm(stato: StatoTurno) -> dict:
        passo = stato["passi"] + 1
        log.info("Inizio chiamata al modello (passo %d/%d)", passo, max_passi)
        risposta = modello.invoke([SystemMessage(PROMPT_SISTEMA), *stato["messages"]])
        esito = f"richieste di strumenti: {len(risposta.tool_calls)}" if risposta.tool_calls else "risposta finale"
        log.info("Fine chiamata al modello (passo %d/%d): %s", passo, max_passi, esito)
        return {"messages": [risposta], "passi": passo}

    def esegui_strumenti(stato: StatoTurno) -> dict:
        risultati = []
        for richiesta in stato["messages"][-1].tool_calls:
            nome, argomenti = richiesta["name"], richiesta["args"]
            log.info("Richiesta strumento %s con argomenti %s", nome, argomenti)
            strumento = per_nome.get(nome)
            if strumento is None:
                risultato = f"Strumento sconosciuto: {nome}"
                log.warning(risultato)
            else:
                risultato = str(strumento.invoke(argomenti))
                log.info("Risultato strumento %s: %s", nome, risultato)
            risultati.append(ToolMessage(content=risultato, tool_call_id=richiesta["id"], name=nome))
        return {"messages": risultati}

    def instrada(stato: StatoTurno) -> Literal["strumenti", "__end__"]:
        if not stato["messages"][-1].tool_calls:
            return END
        if stato["passi"] >= max_passi:
            log.warning("Limite di passaggi raggiunto (%d): richiesta di strumento non eseguita", max_passi)
            return END
        return "strumenti"

    grafo = StateGraph(StatoTurno)
    grafo.add_node("llm", llm)
    grafo.add_node("strumenti", esegui_strumenti)
    grafo.add_edge(START, "llm")
    grafo.add_conditional_edges("llm", instrada)
    grafo.add_edge("strumenti", "llm")
    return grafo.compile()
