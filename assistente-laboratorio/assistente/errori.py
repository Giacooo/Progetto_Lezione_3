"""Errori riconoscibili mostrati all'utente."""

# COSA FA QUESTO FILE
# Definisce due "etichette" di errore, senza codice dentro. Servono per distinguere
# un errore previsto (che mostriamo con un messaggio chiaro) da un errore qualsiasi.
# Il resto del programma le usa con "raise" (lanciare l'errore) e "except" (gestirlo).


# Si lancia quando il .env manca o ha valori sbagliati. Il programma non parte
# (vedi main() in terminale.py: stampa il messaggio ed esce con codice 2).
class ErroreConfigurazione(Exception):
    """La configurazione manca o non è valida: l'applicazione non può partire."""


# Si lancia quando UNA domanda non va a buon fine (server spento, timeout, risposta
# vuota...). La sessione però continua e la cronologia non viene toccata.
class ErroreTurno(Exception):
    """Il turno non si è concluso: la cronologia resta com'era."""


# Si lancia quando uno strumento MCP rifiuta l'input (espressione non ammessa, unità
# sconosciuta...). Il messaggio è scritto per il modello, che può correggersi e riprovare.
class ErroreStrumento(Exception):
    """Lo strumento ha rifiutato l'input: il messaggio è destinato al modello."""


# Si lancia quando il server MCP non si avvia o cade durante una chiamata. Non dipende
# dall'input del modello: è un problema di collegamento, non dello strumento.
class ErroreCollegamentoMCP(Exception):
    """Il server MCP non è raggiungibile (non parte o è caduto)."""
