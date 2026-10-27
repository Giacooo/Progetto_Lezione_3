"""Lettura e validazione della configurazione da ambiente e file .env."""

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import dotenv_values

from assistente.errori import ErroreConfigurazione

OBBLIGATORIE = ("LM_BASE_URL", "LM_MODEL", "FUSO_ORARIO")
LIVELLI_LOG = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
FORMATO_LOG = "%(levelname)s %(name)s: %(message)s"


@dataclass(frozen=True)
class Configurazione:
    lm_base_url: str
    lm_model: str
    fuso_orario: ZoneInfo
    max_passi: int
    log_level: str


def leggi_ambiente(cartella: Path) -> dict[str, str]:
    """Valori di `cartella/.env`, sovrascritti da quelli già presenti nell'ambiente.

    Si legge solo il .env della cartella indicata: nessuna ricerca nelle cartelle madri.
    """
    da_file = {k: v for k, v in dotenv_values(cartella / ".env").items() if v is not None}
    return {**da_file, **os.environ}


def carica_configurazione(ambiente: Mapping[str, str]) -> Configurazione:
    valori = {nome: ambiente.get(nome, "").strip() for nome in OBBLIGATORIE}
    mancanti = [nome for nome, valore in valori.items() if not valore]
    if mancanti:
        raise ErroreConfigurazione(f"variabili mancanti: {', '.join(mancanti)}")

    try:
        fuso = ZoneInfo(valori["FUSO_ORARIO"])
    except (ZoneInfoNotFoundError, ValueError):
        raise ErroreConfigurazione(
            f"FUSO_ORARIO non valido: {valori['FUSO_ORARIO']!r} (usare un nome come Europe/Rome)"
        ) from None

    testo_passi = ambiente.get("MAX_PASSI", "").strip() or "5"
    try:
        max_passi = int(testo_passi)
    except ValueError:
        max_passi = 0
    if max_passi < 1:
        raise ErroreConfigurazione(f"MAX_PASSI deve essere un intero maggiore di zero, non {testo_passi!r}")

    log_level = (ambiente.get("LOG_LEVEL", "").strip() or "INFO").upper()
    if log_level not in LIVELLI_LOG:
        raise ErroreConfigurazione(f"LOG_LEVEL deve essere uno tra {', '.join(LIVELLI_LOG)}")

    return Configurazione(
        lm_base_url=valori["LM_BASE_URL"],
        lm_model=valori["LM_MODEL"],
        fuso_orario=fuso,
        max_passi=max_passi,
        log_level=log_level,
    )


def configura_log(livello: str) -> None:
    """Log su stderr, distinguibili dalle risposte grazie a livello e componente."""
    logging.basicConfig(level=livello, format=FORMATO_LOG, force=True)
    # Le librerie restano silenziose a INFO: si vedono solo le righe dell'assistente.
    logging.getLogger("httpx").setLevel(logging.WARNING)
