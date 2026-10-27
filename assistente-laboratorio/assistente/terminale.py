"""Interfaccia da terminale: legge le domande e stampa le risposte."""

from collections.abc import Callable

from assistente.grafo import costruisci_grafo_fisso

PROMPT = "Tu> "
COMANDO_USCITA = "esci"


def ciclo(
    rispondi: Callable[[str], str],
    leggi: Callable[[str], str] = input,
    scrivi: Callable[[str], None] = print,
) -> None:
    """Ripete domanda e risposta finché l'utente non chiude la sessione."""
    try:
        while True:
            domanda = leggi(PROMPT).strip()
            if not domanda:
                continue
            if domanda.lower() == COMANDO_USCITA:
                break
            scrivi(rispondi(domanda))
    except (EOFError, KeyboardInterrupt):
        scrivi("")
    scrivi("Arrivederci.")


def main() -> int:
    grafo = costruisci_grafo_fisso()
    ciclo(lambda domanda: grafo.invoke({"user_text": domanda})["answer"])
    return 0
