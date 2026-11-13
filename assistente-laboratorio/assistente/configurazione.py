"""Lettura e validazione della configurazione da ambiente e file .env."""

# COSA FA QUESTO FILE
# È la "guardia all'ingresso": prima che il programma parta, controlla che le impostazioni
# (indirizzo di LM Studio, modello, fuso orario...) ci siano e siano valide.
# Tre funzioni, in ordine di utilizzo:
#   leggi_ambiente()        -> raccoglie le impostazioni (dal file .env e dal sistema)
#   carica_configurazione() -> le controlla e le mette in un oggetto ordinato
#   configura_log()         -> decide come e dove scrivere i messaggi di log

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import dotenv_values

from assistente.errori import ErroreConfigurazione

# Le quattro impostazioni SENZA le quali il programma non può partire.
# AMBITO_AGENTE è l'elenco degli argomenti di cui si occupa l'agente: sta nella
# configurazione e non nel codice, quindi non esiste un ambito "di riserva".
OBBLIGATORIE = ("LM_BASE_URL", "LM_MODEL", "FUSO_ORARIO", "AMBITO_AGENTE")
# I livelli di dettaglio dei log ammessi, dal più al meno dettagliato.
LIVELLI_LOG = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
# Come appare una riga di log, es.: "INFO assistente.grafo: Inizio chiamata al modello".
FORMATO_LOG = "%(levelname)s %(name)s: %(message)s"


# Una "scheda" con tutte le impostazioni già controllate. frozen=True significa che
# dopo la creazione non si può più modificare: nessuno la cambia per sbaglio.
@dataclass(frozen=True)
class Configurazione:
    lm_base_url: str  # dove risponde LM Studio, es. http://localhost:1234/v1
    lm_model: str  # id del modello, es. google/gemma-4-e2b
    fuso_orario: ZoneInfo  # fuso dell'orologio, es. Europe/Rome
    max_passi: int  # massimo di chiamate al modello per ogni tentativo di risposta dell'agente
    log_level: str  # quanto dettagliati sono i log
    ambito: str  # argomenti dell'agente, es. "data e ora, meteo" (usato dal router)
    max_revisioni: int  # volte massime in cui il revisore rimanda la risposta all'agente
    soglia_riassunto: int  # messaggi oltre i quali i più vecchi vengono riassunti
    messaggi_da_tenere: int  # ultimi messaggi che restano intatti dopo il riassunto


def leggi_ambiente(cartella: Path) -> dict[str, str]:
    """Valori di `cartella/.env`, sovrascritti da quelli già presenti nell'ambiente.

    Si legge solo il .env della cartella indicata: nessuna ricerca nelle cartelle madri.
    """
    # 1) Legge il file .env e ne fa un dizionario nome -> valore (scartando le righe vuote).
    da_file = {k: v for k, v in dotenv_values(cartella / ".env").items() if v is not None}
    # 2) Unisce il file con le variabili già impostate nel sistema. Nell'unione vince
    #    quello che sta a destra: se una variabile esiste in entrambi, vale quella del
    #    sistema. È il motivo per cui Docker può cambiare LM_BASE_URL senza toccare il .env.
    return {**da_file, **os.environ}


def carica_configurazione(ambiente: Mapping[str, str]) -> Configurazione:
    # --- Controllo 1: le quattro variabili obbligatorie ---
    # Per ognuna prende il valore (o testo vuoto se manca) e toglie gli spazi ai bordi.
    valori = {nome: ambiente.get(nome, "").strip() for nome in OBBLIGATORIE}
    # Fa l'elenco di quelle rimaste vuote; se ce ne sono, ferma tutto dicendo quali.
    mancanti = [nome for nome, valore in valori.items() if not valore]
    if mancanti:
        raise ErroreConfigurazione(f"variabili mancanti: {', '.join(mancanti)}")

    # --- Controllo 2: il fuso orario deve esistere davvero ---
    # "Europe/Rome" va bene, "Roma" no. ZoneInfo lancia un errore se il nome non esiste.
    try:
        fuso = ZoneInfo(valori["FUSO_ORARIO"])
    except (ZoneInfoNotFoundError, ValueError):
        raise ErroreConfigurazione(
            f"FUSO_ORARIO non valido: {valori['FUSO_ORARIO']!r} (usare un nome come Europe/Rome)"
        ) from None

    # --- Controllo 3: MAX_PASSI (facoltativo, se manca vale 5) ---
    testo_passi = ambiente.get("MAX_PASSI", "").strip() or "5"
    try:
        max_passi = int(testo_passi)
    except ValueError:
        # Non è un numero (es. "zero"): lo trattiamo come 0, che verrà rifiutato sotto.
        max_passi = 0
    if max_passi < 1:
        raise ErroreConfigurazione(f"MAX_PASSI deve essere un intero maggiore di zero, non {testo_passi!r}")

    # --- Controllo 3 bis: MAX_REVISIONI (facoltativo, se manca vale 2) ---
    # Quante volte, per ogni domanda, il revisore può rimandare la risposta all'agente.
    # Stesse regole di MAX_PASSI: un intero maggiore di zero.
    testo_revisioni = ambiente.get("MAX_REVISIONI", "").strip() or "2"
    try:
        max_revisioni = int(testo_revisioni)
    except ValueError:
        max_revisioni = 0
    if max_revisioni < 1:
        raise ErroreConfigurazione(
            f"MAX_REVISIONI deve essere un intero maggiore di zero, non {testo_revisioni!r}"
        )

    # --- Controllo 3 ter: SOGLIA_RIASSUNTO (facoltativo, se manca vale 20) ---
    # Oltre questo numero di messaggi, i più vecchi vengono sostituiti da un riassunto.
    # Stesse regole di MAX_PASSI: un intero maggiore di zero.
    testo_soglia = ambiente.get("SOGLIA_RIASSUNTO", "").strip() or "20"
    try:
        soglia_riassunto = int(testo_soglia)
    except ValueError:
        soglia_riassunto = 0
    if soglia_riassunto < 1:
        raise ErroreConfigurazione(
            f"SOGLIA_RIASSUNTO deve essere un intero maggiore di zero, non {testo_soglia!r}"
        )

    # --- Controllo 3 quater: MESSAGGI_DA_TENERE (facoltativo, se manca vale 6) ---
    # Quanti messaggi recenti restano intatti dopo il riassunto. Stesse regole.
    testo_da_tenere = ambiente.get("MESSAGGI_DA_TENERE", "").strip() or "6"
    try:
        messaggi_da_tenere = int(testo_da_tenere)
    except ValueError:
        messaggi_da_tenere = 0
    if messaggi_da_tenere < 1:
        raise ErroreConfigurazione(
            f"MESSAGGI_DA_TENERE deve essere un intero maggiore di zero, non {testo_da_tenere!r}"
        )
    # I messaggi da tenere devono essere meno della soglia: altrimenti, superata la soglia,
    # non ci sarebbe niente da togliere e il riassunto non servirebbe mai.
    if messaggi_da_tenere >= soglia_riassunto:
        raise ErroreConfigurazione(
            f"MESSAGGI_DA_TENERE ({messaggi_da_tenere}) deve essere minore di "
            f"SOGLIA_RIASSUNTO ({soglia_riassunto})"
        )

    # --- Controllo 4: LOG_LEVEL (facoltativo, se manca vale INFO) ---
    log_level = (ambiente.get("LOG_LEVEL", "").strip() or "INFO").upper()
    if log_level not in LIVELLI_LOG:
        raise ErroreConfigurazione(f"LOG_LEVEL deve essere uno tra {', '.join(LIVELLI_LOG)}")

    # Tutto a posto: restituisce la scheda con le impostazioni controllate.
    return Configurazione(
        lm_base_url=valori["LM_BASE_URL"],
        lm_model=valori["LM_MODEL"],
        fuso_orario=fuso,
        max_passi=max_passi,
        log_level=log_level,
        ambito=valori["AMBITO_AGENTE"],
        max_revisioni=max_revisioni,
        soglia_riassunto=soglia_riassunto,
        messaggi_da_tenere=messaggi_da_tenere,
    )


def configura_log(livello: str) -> None:
    """Log su stderr, distinguibili dalle risposte grazie a livello e componente."""
    # Le librerie mostrano solo avvisi ed errori; il livello scelto vale per l'assistente.
    # (basicConfig imposta formato e canale: per default stderr, separato dalle risposte;
    #  force=True sostituisce eventuali impostazioni precedenti.)
    logging.basicConfig(level=logging.WARNING, format=FORMATO_LOG, force=True)
    # Solo i messaggi dei nostri moduli ("assistente.*") usano il livello scelto nel .env.
    logging.getLogger("assistente").setLevel(livello)
