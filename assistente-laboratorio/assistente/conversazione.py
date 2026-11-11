"""Cronologia della sessione ed esecuzione di un turno attraverso il grafo."""

# COSA FA QUESTO FILE
# Tiene la "memoria" della chat e gestisce UN turno (una domanda e la sua risposta).
# Il modello non ricorda nulla da solo: ad ogni domanda gli rimandiamo tutta la
# conversazione precedente, che è conservata qui nella lista "cronologia".
# Regola d'oro: la cronologia cambia SOLO se il turno finisce bene.

import logging

from langchain_core.messages import BaseMessage, HumanMessage

from assistente.errori import ErroreTurno
from assistente.modello import traduci_errore

# Il "diario di bordo" di questo modulo: le righe di log portano il suo nome.
log = logging.getLogger(__name__)


class Conversazione:
    def __init__(self, grafo):
        # Il grafo che sa come elaborare un turno (vedi grafo.py).
        self.grafo = grafo
        # Tutti i messaggi della sessione, dall'inizio. Parte vuota.
        self.cronologia: list[BaseMessage] = []

    def chiedi(self, domanda: str) -> str:
        """Esegue un turno; la cronologia cambia solo se il turno riesce."""
        # --- Passo 1: far girare il grafo ---
        try:
            # Gli diamo la cronologia + la nuova domanda (con HumanMessage) e passi = 0.
            # La cronologia vera NON viene toccata: lavoriamo su una copia nuova.
            risultato = self.grafo.invoke(
                {"messages": [*self.cronologia, HumanMessage(domanda)], "passi": 0}
            )
        except Exception as exc:
            # Qualcosa è andato storto. Proviamo a tradurre l'errore in un messaggio chiaro.
            errore = traduci_errore(exc)
            if errore is None:
                # Errore non previsto: traceback completo nel log, la sessione continua.
                log.exception("Turno fallito per un errore inatteso")
                errore = ErroreTurno(f"Errore inatteso: {exc} (dettagli nel log)")
            else:
                log.error("Turno fallito: %s", errore)
            # Rilanciamo come ErroreTurno: il terminale lo stamperà e la chat continua.
            raise errore from exc

        # --- Passo 2: controllare il risultato ---
        # L'ultimo messaggio dovrebbe essere la risposta finale del modello.
        finale = risultato["messages"][-1]
        if finale.tool_calls:
            # Il grafo si è fermato al limite con una richiesta di strumento ancora aperta;
            # l'avviso è già nel log del grafo.
            raise ErroreTurno("Limite di passaggi raggiunto: riprova con una domanda diversa.")
        # Prende il testo della risposta e toglie gli spazi ai bordi.
        testo = finale.text.strip()
        if not testo:
            errore = ErroreTurno("Il modello ha restituito una risposta vuota.")
            log.warning("Turno fallito: %s", errore)
            raise errore

        # --- Passo 3: tutto bene, quindi (e solo ora) aggiorniamo la memoria ---
        # Salviamo tutti i messaggi del turno: domanda, eventuali richieste di strumento,
        # risultati e risposta finale.
        self.cronologia = risultato["messages"]
        return testo
