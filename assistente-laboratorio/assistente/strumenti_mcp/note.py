"""Note persistenti: aggiungi, elenca ed elimina note in un file SQLite.

# COSA FA QUESTO FILE
Le note sono l'unico dato che sopravvive alla chiusura del programma. Ogni funzione apre
il file, esegue l'operazione e lo richiude (su Windows un file aperto bloccherebbe la
pulizia dei test). La tabella e la cartella si creano al primo uso.
Ogni errore dell'utente o dell'archivio è un ValueError con un messaggio in italiano.
"""

import logging
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

TESTO_MAX = 500  # caratteri massimi di una nota (dopo aver tolto gli spazi ai lati)
LIMITE_MIN, LIMITE_MAX = 1, 50


def _apri(percorso: Path) -> sqlite3.Connection:
    """Apre l'archivio (creando cartella e tabella se mancano); da chiudere con closing()."""
    try:
        Path(percorso).parent.mkdir(parents=True, exist_ok=True)
        connessione = sqlite3.connect(percorso)
        try:
            connessione.execute(
                "CREATE TABLE IF NOT EXISTS note ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "testo TEXT NOT NULL, creata TEXT NOT NULL)"
            )
        except Exception:
            connessione.close()
            raise
        return connessione
    except (sqlite3.Error, OSError) as errore:
        raise ValueError(f"Archivio delle note non accessibile: {errore}") from errore


def aggiungi_nota(testo: str, percorso: Path) -> str:
    """Salva una nota e restituisce la conferma con il suo ID."""
    testo = testo.strip()
    if not testo:
        raise ValueError("Testo vuoto: scrivi il contenuto della nota.")
    if len(testo) > TESTO_MAX:
        raise ValueError(f"Testo troppo lungo: massimo {TESTO_MAX} caratteri, ricevuti {len(testo)}.")
    creata = datetime.now().astimezone().isoformat(timespec="seconds")
    try:
        with closing(_apri(percorso)) as connessione:
            cursore = connessione.execute(
                "INSERT INTO note (testo, creata) VALUES (?, ?)", (testo, creata)
            )
            id_nota = cursore.lastrowid
            connessione.commit()
    except sqlite3.Error as errore:
        raise ValueError(f"Archivio delle note non accessibile: {errore}") from errore
    logger.info("nota creata id=%s", id_nota)
    return f"Nota {id_nota} creata il {creata}: {testo}"


def elenca_note(limite: int, percorso: Path) -> str:
    """Elenca le prime `limite` note, in ordine di ID crescente."""
    if not LIMITE_MIN <= limite <= LIMITE_MAX:
        raise ValueError(f"limite non valido: deve essere tra {LIMITE_MIN} e {LIMITE_MAX}.")
    try:
        with closing(_apri(percorso)) as connessione:
            righe = connessione.execute(
                "SELECT id, creata, testo FROM note ORDER BY id LIMIT ?", (limite,)
            ).fetchall()
    except sqlite3.Error as errore:
        raise ValueError(f"Archivio delle note non accessibile: {errore}") from errore
    if not righe:
        return "Nessuna nota salvata."
    return "\n".join(f"Nota {id_nota} del {creata}: {testo}" for id_nota, creata, testo in righe)


def elimina_nota(id_nota: int, percorso: Path) -> str:
    """Elimina la sola nota con questo ID; se non esiste non toglie nulla."""
    try:
        with closing(_apri(percorso)) as connessione:
            try:
                riga = connessione.execute("SELECT testo FROM note WHERE id = ?", (id_nota,)).fetchone()
            except OverflowError:  # ID oltre i 64 bit di SQLite: non può esistere
                riga = None
            if riga is not None:
                connessione.execute("DELETE FROM note WHERE id = ?", (id_nota,))
                connessione.commit()
    except sqlite3.Error as errore:
        raise ValueError(f"Archivio delle note non accessibile: {errore}") from errore
    if riga is None:
        logger.info("eliminazione rifiutata id=%s inesistente", id_nota)
        raise ValueError(f"Nota {id_nota} inesistente: usa elenca_note per vedere gli ID.")
    logger.info("nota eliminata id=%s", id_nota)
    return f"Nota {id_nota} eliminata: {riga[0]}"
