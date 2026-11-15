"""Interfaccia da terminale: legge le domande e stampa le risposte."""

# COSA FA QUESTO FILE
# È la parte che parla con l'utente, dalla tastiera allo schermo. Ha due funzioni:
#   main()  -> mette insieme tutti i pezzi del programma e lo avvia
#   ciclo() -> il "dialogo": mostra "Tu> ", legge la domanda, stampa la risposta, e ripete
# Dallo step 5 c'è anche crea_smistamento(): riconosce i comandi /prompts e /prompt (i prompt
# MCP, scelti dall'utente) e manda tutte le altre righe alla conversazione come domande.
# Non sa nulla di modelli o di grafi: chiama solo chi risponde e mostra il risultato.

import logging
import sys
from collections.abc import Callable
from pathlib import Path

from langchain_core.messages import BaseMessage

from assistente.collegamento_mcp import (
    carica_preferenze,
    carica_strumenti_mcp,
    connessione_stdio,
    elenca_prompt_mcp,
    richiama_prompt_mcp,
)
from assistente.configurazione import carica_configurazione, configura_log, leggi_ambiente
from assistente.conversazione import Conversazione
from assistente.errori import (
    ErroreCollegamentoMCP,
    ErroreComandoPrompt,
    ErroreConfigurazione,
    ErroreTurno,
)
from assistente.grafo import costruisci_grafo
from assistente.modello import crea_modello
from assistente.prompt_mcp import leggi_comando_prompt, testo_elenco_prompt
from assistente.revisore import crea_revisore
from assistente.router import crea_router
from assistente.strumenti import crea_strumenti

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
                # Un turno fallito (es. LM Studio spento): mostra il messaggio chiaro
                # e la chat continua, senza chiudersi.
                scrivi(str(errore))
    # Ctrl+C oppure fine dell'input: invece di un brutto errore, va a capo ed esce.
    except (EOFError, KeyboardInterrupt):
        scrivi("")
    # Questo saluto compare in tutti i casi di uscita.
    scrivi("Arrivederci.")


# Costruisce la funzione "rispondi" da passare a ciclo() (che così non cambia). Guarda la
# PRIMA parola della riga:
#   /prompts         -> elenco dei prompt del server (nome, descrizione, argomenti);
#   /prompt nome ... -> legge il comando, richiama il prompt (con il controllo degli argomenti
#                       rispetto a prompts/list) e manda i messaggi ottenuti al grafo, come
#                       una domanda: passano da router, agente, strumenti e revisore;
#   tutto il resto   -> domanda normale (anche /Prompts, /help, ...).
# I prompt li sceglie l'UTENTE: il modello non li vede. /prompts e i comandi bloccati non
# entrano nella cronologia e non chiamano il modello. Gli errori diventano ErroreTurno: ciclo()
# li stampa e la chat continua.
def crea_smistamento(
    chiedi: Callable[[str], str],
    chiedi_messaggi: Callable[[list[BaseMessage]], str],
    connessione: dict,
) -> Callable[[str], str]:
    def rispondi(riga: str) -> str:
        parole = riga.split(maxsplit=1)
        comando = parole[0] if parole else ""
        if comando == COMANDO_ELENCO_PROMPT:
            if len(parole) > 1:
                raise ErroreComandoPrompt("Uso: /prompts (senza argomenti)")
            try:
                return testo_elenco_prompt(elenca_prompt_mcp(connessione))
            except ErroreCollegamentoMCP as errore:
                raise ErroreTurno(f"Server MCP non disponibile: {errore}") from errore
        if comando == COMANDO_PROMPT:
            # Errori di LETTURA (virgolette non chiuse, parola senza "="...): il server non è
            # ancora stato contattato, quindi il nome del prompt può mancare (nome=-).
            try:
                nome, argomenti = leggi_comando_prompt(riga)
            except ErroreComandoPrompt as errore:
                log.warning("prompt rifiutato nome=- motivo=%s", errore)
                raise
            # Gli errori del CONTROLLO li scrive già nel log collegamento_mcp: qui salgono
            # così come sono (ErroreComandoPrompt è un ErroreTurno).
            try:
                messaggi = richiama_prompt_mcp(connessione, nome, argomenti)
            except ErroreCollegamentoMCP as errore:
                raise ErroreTurno(f"Server MCP non disponibile: {errore}") from errore
            return chiedi_messaggi(messaggi)
        return chiedi(riga)

    return rispondi


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
    # Come avviare il server MCP (stesso interprete, stessa cartella): serve sia alla
    # discovery degli strumenti sia alla lettura delle preferenze.
    connessione = connessione_stdio(Path.cwd())
    # Gli strumenti del server MCP, scoperti all'avvio (discovery). Si caricano PRIMA del
    # modello: se il server non è disponibile ci si ferma subito con il codice 3, senza
    # leggere le preferenze e senza contattare LM Studio.
    try:
        strumenti_mcp = carica_strumenti_mcp(connessione)
    except ErroreCollegamentoMCP as errore:
        print(f"Server MCP non disponibile: {errore}", file=sys.stderr)
        return 3
    # Le preferenze dell'utente (resource utente://preferenze): le legge l'host, una volta sola,
    # prima della prima domanda. Si leggono DOPO la discovery per distinguere due casi:
    # "server giù" (sopra: errore, codice 3) e "resource non disponibile" (qui: la sessione
    # parte con i valori predefiniti e il fuso di FUSO_ORARIO, con un WARNING nei log).
    preferenze = carica_preferenze(connessione, config.fuso_orario)
    # Gli strumenti: l'orologio, nel fuso delle preferenze (deciso dall'host, non dal modello),
    # più quelli del server MCP. La resource NON è uno strumento: non entra in questa lista.
    strumenti = crea_strumenti(preferenze.fuso) + strumenti_mcp
    # Il modello di LM Studio; bind_tools gli comunica quali strumenti esistono.
    modello = crea_modello(config).bind_tools(strumenti)
    # Il router: stesso modello, ma con un prompt diverso, risposta strutturata e NESSUNO
    # strumento (niente bind_tools): decide solo se la domanda rientra nell'ambito.
    router = crea_router(crea_modello(config))
    # Il revisore: stesso modello, prompt diverso, risposta strutturata e NESSUNO strumento:
    # dice solo se la risposta dell'agente è coerente con la domanda.
    revisore = crea_revisore(crea_modello(config))
    # Il riassuntore: stesso modello, prompt diverso, NESSUNO strumento e testo libero (niente
    # risposta strutturata): oltre la soglia riassume i messaggi più vecchi della conversazione.
    riassuntore = crea_modello(config)
    # Il grafo (la mappa del percorso) viene affidato alla Conversazione, che tiene la memoria.
    conversazione = Conversazione(
        costruisci_grafo(
            modello,
            strumenti,
            config.max_passi,
            router,
            config.ambito,
            revisore,
            config.max_revisioni,
            riassuntore,
            config.soglia_riassunto,
            config.messaggi_da_tenere,
            preferenze,
        )
    )
    # --- 4) Dialogo ---
    # Avvia il ciclo "Tu> ": a ogni riga lo smistamento riconosce i comandi /prompts e /prompt
    # (che usano la stessa connessione al server MCP) e manda le altre righe a conversazione.chiedi.
    ciclo(crea_smistamento(conversazione.chiedi, conversazione.chiedi_messaggi, connessione))
    return 0
