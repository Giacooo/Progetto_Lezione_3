"""Grafo LangGraph del turno di conversazione."""

import logging
from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage, SystemMessage
from langchain_core.runnables import Runnable
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

log = logging.getLogger(__name__)

PROMPT_SISTEMA = (
    "Sei l'assistente del laboratorio. Rispondi in italiano, in modo breve e chiaro. "
    "Non conosci la data e l'ora attuali: quando servono data, ora o giorno della settimana "
    "usa sempre lo strumento ora_corrente."
)


class StatoTurno(TypedDict):
    # add_messages aggiunge i nuovi messaggi alla lista invece di sostituirla.
    messages: Annotated[list[AnyMessage], add_messages]
    passi: int


def costruisci_grafo(modello: Runnable):
    """Grafo del turno: il nodo `llm` interroga il modello con la cronologia."""

    def llm(stato: StatoTurno) -> dict:
        passo = stato["passi"] + 1
        log.info("Inizio chiamata al modello (passo %d)", passo)
        risposta = modello.invoke([SystemMessage(PROMPT_SISTEMA), *stato["messages"]])
        log.info("Fine chiamata al modello (passo %d)", passo)
        return {"messages": [risposta], "passi": passo}

    grafo = StateGraph(StatoTurno)
    grafo.add_node("llm", llm)
    grafo.add_edge(START, "llm")
    grafo.add_edge("llm", END)
    return grafo.compile()
