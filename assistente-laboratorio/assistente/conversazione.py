"""Cronologia della sessione ed esecuzione di un turno attraverso il grafo."""

from langchain_core.messages import BaseMessage, HumanMessage

from assistente.errori import ErroreTurno
from assistente.modello import traduci_errore


class Conversazione:
    def __init__(self, grafo):
        self.grafo = grafo
        self.cronologia: list[BaseMessage] = []

    def chiedi(self, domanda: str) -> str:
        """Esegue un turno; la cronologia cambia solo se il turno riesce."""
        try:
            risultato = self.grafo.invoke(
                {"messages": [*self.cronologia, HumanMessage(domanda)], "passi": 0}
            )
        except Exception as exc:
            errore = traduci_errore(exc)
            if errore is None:
                raise
            raise errore from exc

        finale = risultato["messages"][-1]
        testo = finale.text.strip()
        if not testo:
            raise ErroreTurno("Il modello ha restituito una risposta vuota.")

        self.cronologia = risultato["messages"]
        return testo
