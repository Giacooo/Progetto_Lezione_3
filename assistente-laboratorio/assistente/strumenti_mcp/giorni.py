"""Giorni e scadenze: conteggio di giorni di calendario e lavorativi con festività locali.

Le date sono solo ISO (AAAA-MM-GG). Giorno lavorativo = lunedì-venerdì e non festivo.
Le festività vengono da un file locale che copre solo alcuni anni: fuori da quegli anni
non si calcola nulla (errore esplicito), perché il risultato sarebbe sbagliato in silenzio.
Ogni errore dell'utente è un ValueError con un messaggio in italiano.
"""

import json
import re
from datetime import date, timedelta
from pathlib import Path

GIORNI_MAX = 365  # massimo di giorni lavorativi da aggiungere
NOTA = "(calcolo indicativo, non normativo)"


def carica_festivita(percorso: Path) -> dict[date, str]:
    """Legge il file JSON delle festività; ogni data deve cadere negli anni dichiarati."""
    contenuto = json.loads(percorso.read_text(encoding="utf-8"))
    anni = set(contenuto["anni"])
    festivita = {}
    for voce in contenuto["festivita"]:
        giorno = date.fromisoformat(voce["data"])
        if giorno.year not in anni:
            raise ValueError(f"festività {voce['data']} fuori dagli anni dichiarati {sorted(anni)}")
        festivita[giorno] = voce["nome"]
    return festivita


def _anni_disponibili(festivita):
    return sorted({giorno.year for giorno in festivita})


def _leggi_data(testo):
    # fromisoformat da solo accetta anche "20261223" e "2026-W52-3": qui solo AAAA-MM-GG.
    try:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", testo):
            raise ValueError
        return date.fromisoformat(testo)
    except (ValueError, TypeError):
        raise ValueError(
            f"data non valida: {testo!r}. Usa solo il formato AAAA-MM-GG (esempio: 2026-12-23) "
            "e una data che esista"
        ) from None


def _controlla_anno(giorno, festivita):
    anni = _anni_disponibili(festivita)
    if giorno.year not in anni:
        raise ValueError(
            f"anno {giorno.year} non disponibile: le festività sono presenti solo per "
            f"{', '.join(map(str, anni))}"
        )


def _giorni(numero, aggettivo_singolare, aggettivo_plurale):
    """"1 giorno lavorativo" / "2 giorni lavorativi" (con 0 il plurale)."""
    if numero == 1:
        return f"1 giorno {aggettivo_singolare}"
    return f"{numero} giorni {aggettivo_plurale}"


def _lavorativo(giorno, festivita):
    return giorno.weekday() < 5 and giorno not in festivita


def conta_giorni(data_inizio: str, data_fine: str, festivita: dict[date, str]) -> str:
    """Giorni di calendario e lavorativi tra due date (inizio escluso, fine inclusa)."""
    inizio = _leggi_data(data_inizio)
    fine = _leggi_data(data_fine)
    if fine < inizio:
        raise ValueError(f"la data finale {data_fine} è prima della data iniziale {data_inizio}")
    _controlla_anno(inizio, festivita)
    _controlla_anno(fine, festivita)
    calendario = (fine - inizio).days
    giorni = [inizio + timedelta(days=n) for n in range(1, calendario + 1)]
    lavorativi = sum(_lavorativo(giorno, festivita) for giorno in giorni)
    incluse = [giorno for giorno in giorni if giorno in festivita]
    if incluse:
        elenco = "; ".join(f"{giorno.isoformat()} {festivita[giorno]}" for giorno in incluse)
        testo_festivita = f"Festività nell'intervallo: {elenco}."
    else:
        testo_festivita = "Nessuna festività nell'intervallo."
    return (
        f"Da {inizio.isoformat()} (escluso) a {fine.isoformat()} (incluso): "
        f"{_giorni(calendario, 'di calendario', 'di calendario')}, "
        f"{_giorni(lavorativi, 'lavorativo', 'lavorativi')}. "
        f"{testo_festivita} {NOTA}"
    )


def aggiungi_giorni_lavorativi(data_inizio: str, giorni: int, festivita: dict[date, str]) -> str:
    """Scadenza dopo N giorni lavorativi; la data di partenza non conta mai."""
    inizio = _leggi_data(data_inizio)
    if not 1 <= giorni <= GIORNI_MAX:
        raise ValueError(f"giorni non valido: {giorni}. Deve essere un intero tra 1 e {GIORNI_MAX}")
    _controlla_anno(inizio, festivita)
    corrente = inizio
    contati = 0
    while contati < giorni:
        corrente += timedelta(days=1)
        _controlla_anno(corrente, festivita)  # mai calcolare senza le festività dell'anno
        if _lavorativo(corrente, festivita):
            contati += 1
    return (
        f"Scadenza: {corrente.isoformat()} ({_giorni(giorni, 'lavorativo', 'lavorativi')} dopo {inizio.isoformat()}, "
        f"partenza esclusa). {NOTA}"
    )
