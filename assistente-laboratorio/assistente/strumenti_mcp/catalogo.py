"""Catalogo locale dei corsi: ricerca per parola e dettaglio dato il codice.

I corsi sono inventati e vengono da un file JSON locale (una lista di oggetti).
La ricerca cerca il testo in UN campo alla volta (titolo, codice o sede), senza
distinguere le maiuscole. Ogni errore dell'utente è un ValueError con un messaggio in italiano.
"""

import json
from pathlib import Path

CAMPI = ("codice", "titolo", "sede", "durata_ore")
MAX_RISULTATI = 20  # massimo di corsi restituiti da una ricerca


def carica_catalogo(percorso: Path) -> list[dict]:
    """Legge il file JSON del catalogo; deve essere una lista di corsi con tutti i campi."""
    contenuto = json.loads(percorso.read_text(encoding="utf-8"))
    if not isinstance(contenuto, list):
        raise ValueError("catalogo non valido: il file deve contenere una lista di corsi")
    codici = set()
    for corso in contenuto:
        if not isinstance(corso, dict) or set(corso) != set(CAMPI):
            raise ValueError(f"corso non valido nel catalogo: {corso!r}. Campi richiesti: {', '.join(CAMPI)}")
        if not isinstance(corso["durata_ore"], int) or isinstance(corso["durata_ore"], bool):
            raise ValueError(f"durata_ore non valida per il corso {corso['codice']}: deve essere un intero")
        if corso["codice"] in codici:
            raise ValueError(f"codice duplicato nel catalogo: {corso['codice']}")
        codici.add(corso["codice"])
    return contenuto


def cerca_corsi(testo: str, max_risultati: int, corsi: list[dict]) -> str:
    """Elenco breve (codice, titolo, sede) dei corsi che contengono il testo."""
    cercato = testo.strip()
    if not cercato:
        raise ValueError("testo vuoto: indica una parola da cercare nel titolo, nel codice o nella sede")
    if not 1 <= max_risultati <= MAX_RISULTATI:
        raise ValueError(f"max_risultati non valido: {max_risultati}. Deve essere un intero tra 1 e {MAX_RISULTATI}")
    chiave = cercato.casefold()
    trovati = [
        corso
        for corso in corsi
        if any(chiave in corso[campo].casefold() for campo in ("titolo", "codice", "sede"))
    ]
    if not trovati:
        return f'Nessun corso trovato per "{cercato}".'
    return "\n".join(f"- {c['codice']}: {c['titolo']} ({c['sede']})" for c in trovati[:max_risultati])


def dettaglio_corso(codice: str, corsi: list[dict]) -> str:
    """Tutti i campi di un corso, dato il codice esatto (maiuscole ininfluenti)."""
    cercato = codice.strip().casefold()
    for corso in corsi:
        if corso["codice"].casefold() == cercato:
            return (
                f"Codice: {corso['codice']}\n"
                f"Titolo: {corso['titolo']}\n"
                f"Sede: {corso['sede']}\n"
                f"Durata: {corso['durata_ore']} ore"
            )
    raise ValueError(f"codice corso {codice.strip()!r} inesistente: usa cerca_corsi per trovare i codici validi")
