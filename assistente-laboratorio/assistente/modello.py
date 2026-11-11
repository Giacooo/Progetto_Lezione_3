"""Collegamento al modello servito da LM Studio (API compatibile con OpenAI)."""

# COSA FA QUESTO FILE
# 1) crea_modello(): prepara il "telefono" per chiamare il modello di LM Studio.
# 2) traduci_errore(): trasforma gli errori tecnici in messaggi chiari per l'utente.

import openai
from langchain_openai import ChatOpenAI

from assistente.configurazione import Configurazione
from assistente.errori import ErroreTurno


def crea_modello(config: Configurazione) -> ChatOpenAI:
    # ChatOpenAI parla con qualunque server che usi lo stesso "linguaggio" di OpenAI.
    # LM Studio lo fa, quindi funziona anche se il modello è sul nostro computer.
    return ChatOpenAI(
        # Dove risponde LM Studio (viene da LM_BASE_URL nel .env).
        base_url=config.lm_base_url,
        # Quale modello usare (viene da LM_MODEL nel .env).
        model=config.lm_model,
        api_key="lm-studio",  # LM Studio non verifica la chiave, ma il client ne vuole una
        # "Creatività" del modello: bassa = risposte più stabili e prevedibili.
        temperature=0.2,
        # Senza, gemma consuma i token ragionando e la risposta arriva vuota.
        reasoning_effort="none",
        # Lunghezza massima della risposta, in token (pezzetti di testo).
        max_tokens=1024,
        # Secondi massimi di attesa prima di rinunciare (dà l'errore "Attesa scaduta").
        timeout=120,
        # Nessun tentativo automatico di nascosto: se fallisce, lo vediamo subito.
        max_retries=0,
    )


def traduci_errore(exc: Exception) -> ErroreTurno | None:
    """Messaggio riconoscibile per gli errori del server; None per tutti gli altri."""
    # Riceve un errore qualsiasi e, se lo riconosce, restituisce un ErroreTurno con un
    # messaggio in italiano. Se non lo riconosce restituisce None: sarà il chiamante
    # (conversazione.py) a gestirlo come "errore inatteso".
    # APITimeoutError è una sottoclasse di APIConnectionError: va controllato prima.
    # (Altrimenti ogni timeout verrebbe scambiato per "connessione fallita".)
    if isinstance(exc, openai.APITimeoutError):
        return ErroreTurno("Attesa scaduta: controllare server, carico e tempi.")
    # Il server non risponde affatto: spento, indirizzo o porta sbagliati.
    if isinstance(exc, openai.APIConnectionError):
        return ErroreTurno("Connessione fallita: controllare LM Studio, URL e porta.")
    # Il server ha risposto, ma con un errore (es. 404 se l'id del modello è sbagliato).
    if isinstance(exc, openai.APIStatusError):
        return ErroreTurno(f"Errore dal server: {exc.status_code} {exc.response.text}")
    return None
