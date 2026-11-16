"""Configurazione del front-end: lettura e controllo delle variabili d'ambiente."""

# COSA FA QUESTO FILE (lezione 6, step 8)
# È la "guardia all'ingresso" del front-end, come backend/configurazione.py lo è per il back-end.
# Il front-end non importa nulla del back-end né dell'agente, quindi ha la sua piccola
# configurazione (la struttura è la stessa, copiata e non importata):
#   - dove risponde il back-end (BACKEND_URL): lo conosce solo il server del front-end, la
#     pagina nel browser usa percorsi relativi /api/... e non contiene indirizzi;
#   - dove ascolta il front-end (FRONTEND_HOST, FRONTEND_PORTA);
#   - LOG_LEVEL.

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

LIVELLI_LOG = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
# Stesso formato dei log di agente e back-end, es.: "INFO frontend: inoltro metodo=GET ...".
FORMATO_LOG = "%(levelname)s %(name)s: %(message)s"


class ErroreConfigurazioneFrontend(Exception):
    """Configurazione mancante o non valida: il front-end non può partire."""


@dataclass(frozen=True)
class ConfigurazioneFrontend:
    backend_url: str  # dove risponde il back-end, es. http://127.0.0.1:8001 (senza "/" finale)
    host: str  # dove ascolta il front-end: 127.0.0.1 = solo da questo PC
    porta: int  # 8002 (agente 8000, back-end 8001)
    log_level: str


def leggi_ambiente(cartella: Path) -> dict[str, str]:
    """Valori di `cartella/.env`, sovrascritti da quelli già presenti nell'ambiente."""
    da_file = {k: v for k, v in dotenv_values(cartella / ".env").items() if v is not None}
    return {**da_file, **os.environ}


def _porta(ambiente: Mapping[str, str], nome: str, predefinita: str) -> int:
    testo = ambiente.get(nome, "").strip() or predefinita
    try:
        porta = int(testo)
    except ValueError:
        porta = 0
    if not 1 <= porta <= 65535:
        raise ErroreConfigurazioneFrontend(f"{nome} deve essere un intero tra 1 e 65535, non {testo!r}")
    return porta


def carica_configurazione(ambiente: Mapping[str, str]) -> ConfigurazioneFrontend:
    # 127.0.0.1 e non "localhost": su Windows "localhost" prova prima IPv6 (::1), dove il
    # back-end non ascolta, e ogni richiesta perderebbe circa 2 secondi.
    backend_url = ambiente.get("BACKEND_URL", "").strip() or "http://127.0.0.1:8001"
    if not backend_url.startswith(("http://", "https://")):
        raise ErroreConfigurazioneFrontend(
            f"BACKEND_URL deve cominciare con http:// o https://, non {backend_url!r}")

    log_level = (ambiente.get("LOG_LEVEL", "").strip() or "INFO").upper()
    if log_level not in LIVELLI_LOG:
        raise ErroreConfigurazioneFrontend(f"LOG_LEVEL deve essere uno tra {', '.join(LIVELLI_LOG)}")

    return ConfigurazioneFrontend(
        backend_url=backend_url.rstrip("/"),
        host=ambiente.get("FRONTEND_HOST", "").strip() or "127.0.0.1",
        porta=_porta(ambiente, "FRONTEND_PORTA", "8002"),
        log_level=log_level,
    )


def configura_log(livello: str) -> None:
    """Log su stderr: le librerie solo avvisi ed errori, il front-end al livello scelto."""
    logging.basicConfig(level=logging.WARNING, format=FORMATO_LOG, force=True)
    logging.getLogger("frontend").setLevel(livello)
