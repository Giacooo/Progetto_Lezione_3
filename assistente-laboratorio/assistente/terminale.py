"""Interfaccia da terminale: legge le domande e stampa le risposte."""

# COSA FA QUESTO FILE
# È la parte che parla con l'utente, dalla tastiera allo schermo. Ha due funzioni:
#   main()  -> mette insieme tutti i pezzi del programma e lo avvia
#   ciclo() -> il "dialogo": mostra "Tu> ", legge la domanda, stampa la risposta, e ripete
# Non sa nulla di modelli o di grafi: chiama solo chi risponde e mostra il risultato.

import sys
from collections.abc import Callable
from pathlib import Path

from assistente.collegamento_mcp import carica_strumenti_mcp, connessione_stdio
from assistente.configurazione import carica_configurazione, configura_log, leggi_ambiente
from assistente.conversazione import Conversazione
from assistente.errori import ErroreCollegamentoMCP, ErroreConfigurazione, ErroreTurno
from assistente.grafo import costruisci_grafo
from assistente.modello import crea_modello
from assistente.strumenti import crea_strumenti

# Il testo che compare davanti alla riga dove si scrive.
PROMPT = "Tu> "
# La parola che chiude la chat (maiuscole e spazi vengono ignorati, vedi ciclo()).
COMANDO_USCITA = "esci"


def ciclo(
    rispondi: Callable[[str], str],
    leggi: Callable[[str], str] = input,
    scrivi: Callable[[str], None] = print,
) -> None:
    """Ripete domanda e risposta finché l'utente non chiude la sessione."""
    # I tre parametri sono "funzioni da collegare": rispondi dice chi risponde alle
    # domande; leggi e scrivi sono di solito input e print, ma i test ne passano di finte
    # per simulare la tastiera e lo schermo senza un vero terminale.
    # Il try esterno serve a chiudere in modo pulito con Ctrl+C o a fine input.
    try:
        # Si ripete all'infinito: si esce solo con break (comando "esci") o con l'eccezione.
        while True:
            # leggi(PROMPT) mostra "Tu> " e restituisce quello che scrivi; poi si tolgono
            # il carattere invisibile BOM (vedi sotto) e gli spazi ai bordi con strip().
            # PowerShell 5.1 antepone un BOM all'input passato con una pipe.
            domanda = leggi(PROMPT).replace("﻿", "").strip()
            # Riga vuota: la ignora e torna a chiedere, senza disturbare il modello.
            if not domanda:
                continue
            # "esci" (in qualunque scrittura: ESCI, Esci...) interrompe il ciclo.
            if domanda.lower() == COMANDO_USCITA:
                break
            try:
                # rispondi(domanda) manda la domanda al resto del programma e restituisce
                # la risposta; scrivi() la stampa.
                scrivi(rispondi(domanda))
            except ErroreTurno as errore:
                # Un turno fallito (es. LM Studio spento): mostra il messaggio chiaro
                # e la chat continua, senza chiudersi.
                scrivi(str(errore))
    # Ctrl+C oppure fine dell'input: invece di un brutto errore, va a capo ed esce.
    except (EOFError, KeyboardInterrupt):
        scrivi("")
    # Questo saluto compare in tutti i casi di uscita.
    scrivi("Arrivederci.")


# La funzione che avvia tutto. Restituisce 0 se va bene, 2 se la configurazione è sbagliata,
# 3 se il server MCP non è disponibile.
def main() -> int:
    # --- 1) Configurazione ---
    # Legge il .env della cartella da cui si lancia il programma (più le variabili di
    # sistema) e lo controlla. Se è sbagliata, stampa il motivo su stderr e si ferma
    # subito: il modello non viene nemmeno contattato.
    try:
        config = carica_configurazione(leggi_ambiente(Path.cwd()))
    except ErroreConfigurazione as errore:
        print(f"Configurazione non valida: {errore}", file=sys.stderr)
        return 2
    # --- 2) Log ---
    configura_log(config.log_level)

    # --- 3) Costruzione dei pezzi, dal basso verso l'alto ---
    # Gli strumenti: l'orologio (con il fuso scelto nel .env) più quelli del server MCP,
    # scoperti all'avvio (discovery). Si caricano PRIMA del modello: se il server non è
    # disponibile ci si ferma subito con il codice 3, senza contattare LM Studio.
    try:
        strumenti = crea_strumenti(config.fuso_orario) + carica_strumenti_mcp(connessione_stdio(Path.cwd()))
    except ErroreCollegamentoMCP as errore:
        print(f"Server MCP non disponibile: {errore}", file=sys.stderr)
        return 3
    # Il modello di LM Studio; bind_tools gli comunica quali strumenti esistono.
    modello = crea_modello(config).bind_tools(strumenti)
    # Il grafo (la mappa del percorso) viene affidato alla Conversazione, che tiene la memoria.
    conversazione = Conversazione(costruisci_grafo(modello, strumenti, config.max_passi))
    # --- 4) Dialogo ---
    # Avvia il ciclo "Tu> ": a ogni domanda chiama conversazione.chiedi.
    ciclo(conversazione.chiedi)
    return 0
