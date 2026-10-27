"""Cronologia della sessione ed esecuzione di un turno attraverso il grafo."""

import logging

from langchain_core.messages import BaseMessage, HumanMessage

from assistente.errori import ErroreTurno
from assistente.modello import traduci_errore

log = logging.getLogger(__name__)


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
                # Errore non previsto: traceback completo nel log, la sessione continua.
                log.exception("Turno fallito per un errore inatteso")
                errore = ErroreTurno(f"Errore inatteso: {exc} (dettagli nel log)")
            else:
                log.error("Turno fallito: %s", errore)
            raise errore from exc

        finale = risultato["messages"][-1]
        if finale.tool_calls:
            # Il grafo si è fermato al limite con una richiesta di strumento ancora aperta;
            # l'avviso è già nel log del grafo.
            raise ErroreTurno("Limite di passaggi raggiunto: riprova con una domanda diversa.")
        testo = finale.text.strip()
        if not testo:
            errore = ErroreTurno("Il modello ha restituito una risposta vuota.")
            log.warning("Turno fallito: %s", errore)
            raise errore

        self.cronologia = risultato["messages"]
        return testo
