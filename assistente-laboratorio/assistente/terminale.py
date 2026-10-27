"""Interfaccia da terminale: legge le domande e stampa le risposte."""

import sys
from collections.abc import Callable
from pathlib import Path

from assistente.configurazione import carica_configurazione, configura_log, leggi_ambiente
from assistente.conversazione import Conversazione
from assistente.errori import ErroreConfigurazione, ErroreTurno
from assistente.grafo import costruisci_grafo
from assistente.modello import crea_modello
from assistente.strumenti import crea_strumenti

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
            try:
                scrivi(rispondi(domanda))
            except ErroreTurno as errore:
                scrivi(str(errore))
    except (EOFError, KeyboardInterrupt):
        scrivi("")
    scrivi("Arrivederci.")


def main() -> int:
    try:
        config = carica_configurazione(leggi_ambiente(Path.cwd()))
    except ErroreConfigurazione as errore:
        print(f"Configurazione non valida: {errore}", file=sys.stderr)
        return 2
    configura_log(config.log_level)

    strumenti = crea_strumenti(config.fuso_orario)
    modello = crea_modello(config).bind_tools(strumenti)
    conversazione = Conversazione(costruisci_grafo(modello, strumenti, config.max_passi))
    ciclo(conversazione.chiedi)
    return 0
