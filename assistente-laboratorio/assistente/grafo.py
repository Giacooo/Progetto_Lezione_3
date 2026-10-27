"""Grafo LangGraph del turno di conversazione."""

from collections.abc import Callable
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

RISPOSTA_FISSA = "Il grafo è in esecuzione."


class StatoFisso(TypedDict, total=False):
    user_text: str
    answer: str


def costruisci_grafo_fisso(osservatore: Callable[[str], None] | None = None):
    """Primo grafo senza modello: un solo nodo che imposta una risposta fissa."""

    def rispondi(stato: StatoFisso) -> dict:
        if osservatore is not None:
            osservatore(stato["user_text"])
        return {"answer": RISPOSTA_FISSA}

    grafo = StateGraph(StatoFisso)
    grafo.add_node("rispondi", rispondi)
    grafo.add_edge(START, "rispondi")
    grafo.add_edge("rispondi", END)
    return grafo.compile()
