"""Collegamento al modello servito da LM Studio (API compatibile con OpenAI)."""

import openai
from langchain_openai import ChatOpenAI

from assistente.configurazione import Configurazione
from assistente.errori import ErroreTurno


def crea_modello(config: Configurazione) -> ChatOpenAI:
    return ChatOpenAI(
        base_url=config.lm_base_url,
        model=config.lm_model,
        api_key="lm-studio",  # LM Studio non verifica la chiave, ma il client ne vuole una
        temperature=0.2,
        # Senza, gemma consuma i token ragionando e la risposta arriva vuota.
        reasoning_effort="none",
        max_tokens=1024,
        timeout=120,
        max_retries=0,
    )


def traduci_errore(exc: Exception) -> ErroreTurno | None:
    """Messaggio riconoscibile per gli errori del server; None per tutti gli altri."""
    # APITimeoutError è una sottoclasse di APIConnectionError: va controllato prima.
    if isinstance(exc, openai.APITimeoutError):
        return ErroreTurno("Attesa scaduta: controllare server, carico e tempi.")
    if isinstance(exc, openai.APIConnectionError):
        return ErroreTurno("Connessione fallita: controllare LM Studio, URL e porta.")
    if isinstance(exc, openai.APIStatusError):
        return ErroreTurno(f"Errore dal server: {exc.status_code} {exc.response.text}")
    return None
