"""Interfaccia da terminale: legge le domande e stampa le risposte."""

# COSA FA QUESTO FILE
# È la parte che parla con l'utente, dalla tastiera allo schermo. Ha due funzioni:
#   main()  -> legge la configurazione e avvia il dialogo
#   ciclo() -> il "dialogo": mostra "Tu> ", legge la domanda, stampa la risposta, e ripete
# Dallo step 5 c'è anche crea_smistamento(): riconosce i comandi /prompts e /prompt (i prompt
# MCP, scelti dall'utente) e manda tutte le altre righe all'agente come domande.
# Dallo step 6 la CLI è un CLIENT dell'API dell'agente (vedi cliente.py e servizio.py): non
# costruisce grafo, modello o collegamento MCP; l'agente va avviato a parte con
#   python -m assistente.servizio
# Non sa nulla di modelli o di grafi: chiama solo chi risponde e mostra il risultato.

import logging
import sys
from collections.abc import Callable
from pathlib import Path

from assistente.cliente import ClienteAgente
from assistente.configurazione import carica_configurazione_cliente, configura_log, leggi_ambiente
from assistente.errori import ErroreComandoPrompt, ErroreConfigurazione, ErroreTurno
from assistente.prompt_mcp import leggi_comando_prompt, testo_elenco_prompt

# Il "diario di bordo" di questo modulo: le righe di log portano il suo nome.
log = logging.getLogger(__name__)

# Il testo che compare davanti alla riga dove si scrive.
PROMPT = "Tu> "
# La parola che chiude la chat (maiuscole e spazi vengono ignorati, vedi ciclo()).
COMANDO_USCITA = "esci"
# I due comandi dei prompt MCP: valgono solo scritti così, in minuscolo, come prima parola.
COMANDO_ELENCO_PROMPT = "/prompts"
COMANDO_PROMPT = "/prompt"


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
                # Un turno fallito (es. LM Studio spento, agente non avviato): mostra il
                # messaggio chiaro e la chat continua, senza chiudersi.
                scrivi(str(errore))
    # Ctrl+C oppure fine dell'input: invece di un brutto errore, va a capo ed esce.
    except (EOFError, KeyboardInterrupt):
        scrivi("")
    # Questo saluto compare in tutti i casi di uscita.
    scrivi("Arrivederci.")


# Costruisce la funzione "rispondi" da passare a ciclo() (che così non cambia). Guarda la
# PRIMA parola della riga:
#   /prompts         -> elenco dei prompt (GET /prompts dell'agente);
#   /prompt nome ... -> legge il comando qui (solo la scrittura: virgolette, "="), poi lo manda
#                       all'agente (POST /prompts/{nome}), che controlla gli argomenti rispetto a
#                       prompts/list e fa passare i messaggi ottenuti dal grafo come una domanda;
#   tutto il resto   -> domanda normale (anche /Prompts, /help, ...).
# I prompt li sceglie l'UTENTE: il modello non li vede. Gli errori sono ErroreTurno: ciclo()
# li stampa e la chat continua.
def crea_smistamento(cliente: ClienteAgente) -> Callable[[str], str]:
    def rispondi(riga: str) -> str:
        parole = riga.split(maxsplit=1)
        comando = parole[0] if parole else ""
        if comando == COMANDO_ELENCO_PROMPT:
            if len(parole) > 1:
                raise ErroreComandoPrompt("Uso: /prompts (senza argomenti)")
            return testo_elenco_prompt(cliente.elenca_prompt())
        if comando == COMANDO_PROMPT:
            # Errori di LETTURA (virgolette non chiuse, parola senza "="...): l'agente non viene
            # contattato, quindi il nome del prompt può mancare (nome=-).
            try:
                nome, argomenti = leggi_comando_prompt(riga)
            except ErroreComandoPrompt as errore:
                log.warning("prompt rifiutato nome=- motivo=%s", errore)
                raise
            return cliente.richiama_prompt(nome, argomenti)
        return cliente.chiedi(riga)

    return rispondi


# La funzione che avvia la CLI. Restituisce 0 se va bene, 2 se la configurazione è sbagliata.
# (Server MCP giù e modello spento ora li segnala l'agente: vedi servizio.py.)
def main() -> int:
    # --- 1) Configurazione del client: solo AGENTE_URL e LOG_LEVEL ---
    try:
        config = carica_configurazione_cliente(leggi_ambiente(Path.cwd()))
    except ErroreConfigurazione as errore:
        print(f"Configurazione non valida: {errore}", file=sys.stderr)
        return 2
    # --- 2) Log ---
    configura_log(config.log_level)
    # --- 3) Dialogo ---
    # Ogni riga passa dallo smistamento al client, che la manda all'agente via HTTP insieme a
    # cronologia e riassunto della sessione (li tiene il client: l'agente non ha stato).
    ciclo(crea_smistamento(ClienteAgente(config.agente_url)))
    return 0
