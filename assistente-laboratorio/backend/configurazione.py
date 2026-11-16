"""Configurazione del back-end: lettura e controllo delle variabili d'ambiente."""

# COSA FA QUESTO FILE (lezione 6, step 7)
# È la "guardia all'ingresso" del back-end, come assistente/configurazione.py lo è per l'agente.
# Il back-end non importa nulla dell'agente, quindi ha la sua piccola configurazione:
#   - credenziali e indirizzo di PostgreSQL (POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
#     obbligatorie; POSTGRES_HOST e POSTGRES_PORTA facoltative). Le stesse variabili le legge
#     anche il container "db" di compose.yaml: le credenziali stanno una volta sola nel .env;
#   - dove ascolta il back-end (BACKEND_HOST, BACKEND_PORTA);
#   - dove risponde l'agente (AGENTE_URL, la stessa variabile della CLI dello step 6);
#   - LOG_LEVEL.

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path

from dotenv import dotenv_values

OBBLIGATORIE = ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB")
LIVELLI_LOG = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
# Stesso formato dei log dell'agente, es.: "INFO backend.app: richiesta operazione=crea chat=-".
FORMATO_LOG = "%(levelname)s %(name)s: %(message)s"


class ErroreConfigurazioneBackend(Exception):
    """Configurazione mancante o non valida: il back-end non può partire."""


# Come raggiungere PostgreSQL.
@dataclass(frozen=True)
class ParametriDatabase:
    utente: str
    password: str
    database: str  # nome del database, es. chat
    host: str  # localhost sul PC; allo step 9 sarà "db"
    porta: int  # 5432

    def con_database(self, nome: str) -> "ParametriDatabase":
        """Gli stessi parametri con un altro database (i test usano <POSTGRES_DB>_prove)."""
        return replace(self, database=nome)


@dataclass(frozen=True)
class ConfigurazioneBackend:
    database: ParametriDatabase
    host: str  # dove ascolta il back-end: 127.0.0.1 = solo da questo PC
    porta: int  # 8001 (l'agente resta su 8000)
    agente_url: str  # dove risponde l'agente, es. http://localhost:8000
    log_level: str


def leggi_ambiente(cartella: Path) -> dict[str, str]:
    """Valori di `cartella/.env`, sovrascritti da quelli già presenti nell'ambiente."""
    da_file = {k: v for k, v in dotenv_values(cartella / ".env").items() if v is not None}
    return {**da_file, **os.environ}


# Una porta: intero tra 1 e 65535, altrimenti errore che nomina la variabile.
def _porta(ambiente: Mapping[str, str], nome: str, predefinita: str) -> int:
    testo = ambiente.get(nome, "").strip() or predefinita
    try:
        porta = int(testo)
    except ValueError:
        porta = 0
    if not 1 <= porta <= 65535:
        raise ErroreConfigurazioneBackend(f"{nome} deve essere un intero tra 1 e 65535, non {testo!r}")
    return porta


def carica_configurazione(ambiente: Mapping[str, str]) -> ConfigurazioneBackend:
    valori = {nome: ambiente.get(nome, "").strip() for nome in OBBLIGATORIE}
    mancanti = [nome for nome, valore in valori.items() if not valore]
    if mancanti:
        raise ErroreConfigurazioneBackend(f"variabili mancanti: {', '.join(mancanti)}")

    database = ParametriDatabase(
        utente=valori["POSTGRES_USER"],
        password=valori["POSTGRES_PASSWORD"],
        database=valori["POSTGRES_DB"],
        host=ambiente.get("POSTGRES_HOST", "").strip() or "localhost",
        porta=_porta(ambiente, "POSTGRES_PORTA", "5432"),
    )

    agente_url = ambiente.get("AGENTE_URL", "").strip() or "http://localhost:8000"
    if not agente_url.startswith(("http://", "https://")):
        raise ErroreConfigurazioneBackend(f"AGENTE_URL deve cominciare con http:// o https://, non {agente_url!r}")

    log_level = (ambiente.get("LOG_LEVEL", "").strip() or "INFO").upper()
    if log_level not in LIVELLI_LOG:
        raise ErroreConfigurazioneBackend(f"LOG_LEVEL deve essere uno tra {', '.join(LIVELLI_LOG)}")

    return ConfigurazioneBackend(
        database=database,
        host=ambiente.get("BACKEND_HOST", "").strip() or "127.0.0.1",
        porta=_porta(ambiente, "BACKEND_PORTA", "8001"),
        agente_url=agente_url,
        log_level=log_level,
    )


def configura_log(livello: str) -> None:
    """Log su stderr: le librerie solo avvisi ed errori, il back-end al livello scelto."""
    logging.basicConfig(level=logging.WARNING, format=FORMATO_LOG, force=True)
    logging.getLogger("backend").setLevel(livello)
