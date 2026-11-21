"""Configurazione del RAG: lettura e controllo delle variabili d'ambiente (lezione 7)."""

# COSA FA QUESTO FILE
# È la "guardia all'ingresso" degli script del RAG (ingestion, ricerca, valutazione), come
# backend/configurazione.py lo è per il back-end. Legge:
#   - LM_BASE_URL (obbligatoria, la stessa dell'agente): il server di LM Studio;
#   - EMBEDDING_MODELLO (obbligatoria): il modello che trasforma i testi in vettori. Sta qui, e
#     non nel codice, come chiede il PDF: lo stesso per i documenti e per le domande;
#   - QDRANT_URL e QDRANT_COLLEZIONE: dove sta l'indice;
#   - CORPUS_FILE: il file del libro (scaricato a mano in dati/, fuori da Git);
#   - CHUNK_STRATEGIA, CHUNK_DIMENSIONE, CHUNK_OVERLAP: come si divide il testo in pezzi;
#   - LOG_LEVEL.
# Un valore sbagliato produce un errore che nomina la variabile.

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

OBBLIGATORIE = ("LM_BASE_URL", "EMBEDDING_MODELLO")
STRATEGIE = ("paragrafi", "finestra")
LIVELLI_LOG = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
FORMATO_LOG = "%(levelname)s %(name)s: %(message)s"


class ErroreConfigurazioneRag(Exception):
    """Configurazione mancante o non valida: lo script non può partire."""


@dataclass(frozen=True)
class ConfigurazioneRag:
    lm_base_url: str  # es. http://localhost:1234/v1 (senza "/" finale)
    embedding_modello: str  # es. text-embedding-nomic-embed-text-v1.5
    qdrant_url: str  # es. http://127.0.0.1:6333
    collezione: str  # nome della collezione in Qdrant, es. ricette
    corpus_file: Path  # il libro, es. <progetto>/dati/artusi.txt
    strategia: str  # "paragrafi" oppure "finestra"
    dimensione: int  # lunghezza massima di un chunk, in caratteri
    overlap: int  # caratteri ripetuti tra chunk consecutivi
    log_level: str


def leggi_ambiente(cartella: Path) -> dict[str, str]:
    """Valori di `cartella/.env`, sovrascritti da quelli già presenti nell'ambiente."""
    da_file = {k: v for k, v in dotenv_values(cartella / ".env").items() if v is not None}
    return {**da_file, **os.environ}


def _intero(ambiente: Mapping[str, str], nome: str, predefinito: int, minimo: int) -> int:
    testo = ambiente.get(nome, "").strip()
    if not testo:
        return predefinito
    try:
        valore = int(testo)
    except ValueError:
        valore = minimo - 1
    if valore < minimo:
        raise ErroreConfigurazioneRag(f"{nome} deve essere un intero maggiore o uguale a {minimo}, non {testo!r}")
    return valore


def _url(ambiente: Mapping[str, str], nome: str, predefinito: str) -> str:
    url = (ambiente.get(nome, "").strip() or predefinito).rstrip("/")
    if not url.startswith(("http://", "https://")):
        raise ErroreConfigurazioneRag(f"{nome} deve cominciare con http:// o https://, non {url!r}")
    return url


def carica_configurazione(ambiente: Mapping[str, str], cartella: Path) -> ConfigurazioneRag:
    """Controlla le variabili; i percorsi relativi (CORPUS_FILE) partono da `cartella`."""
    mancanti = [nome for nome in OBBLIGATORIE if not ambiente.get(nome, "").strip()]
    if mancanti:
        raise ErroreConfigurazioneRag(f"variabili mancanti: {', '.join(mancanti)}")

    strategia = ambiente.get("CHUNK_STRATEGIA", "").strip() or "paragrafi"
    if strategia not in STRATEGIE:
        raise ErroreConfigurazioneRag(f"CHUNK_STRATEGIA deve essere uno tra {', '.join(STRATEGIE)}, non {strategia!r}")
    dimensione = _intero(ambiente, "CHUNK_DIMENSIONE", 1200, 1)
    overlap = _intero(ambiente, "CHUNK_OVERLAP", 200, 0)
    if overlap >= dimensione:
        raise ErroreConfigurazioneRag(
            f"CHUNK_OVERLAP ({overlap}) deve essere minore di CHUNK_DIMENSIONE ({dimensione})")

    log_level = (ambiente.get("LOG_LEVEL", "").strip() or "INFO").upper()
    if log_level not in LIVELLI_LOG:
        raise ErroreConfigurazioneRag(f"LOG_LEVEL deve essere uno tra {', '.join(LIVELLI_LOG)}")

    corpus = Path(ambiente.get("CORPUS_FILE", "").strip() or "dati/artusi.txt")
    return ConfigurazioneRag(
        lm_base_url=_url(ambiente, "LM_BASE_URL", ""),
        embedding_modello=ambiente["EMBEDDING_MODELLO"].strip(),
        qdrant_url=_url(ambiente, "QDRANT_URL", "http://127.0.0.1:6333"),
        collezione=ambiente.get("QDRANT_COLLEZIONE", "").strip() or "ricette",
        corpus_file=corpus if corpus.is_absolute() else cartella / corpus,
        strategia=strategia,
        dimensione=dimensione,
        overlap=overlap,
        log_level=log_level,
    )


def configura_log(livello: str) -> None:
    """Log su stderr: le librerie solo avvisi ed errori, il RAG al livello scelto."""
    logging.basicConfig(level=logging.WARNING, format=FORMATO_LOG, force=True)
    logging.getLogger("rag").setLevel(livello)
