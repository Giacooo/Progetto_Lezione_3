"""Corpus: pulizia del libro di Artusi e divisione in ricette (lezione 7, pipeline fasi 1-3)."""

# COSA FA QUESTO FILE
# Prende il file di testo del libro (Project Gutenberg n. 59047) e restituisce le ricette, una
# per documento, ciascuna con numero, titolo, capitolo e testo pulito.
#
# Le regole sono state verificate sul file vero (vedi la specifica, «Il corpus»):
#   - le ricette stanno tra la riga "RICETTE" e la riga "APPENDICE" (scritte senza rientro: più
#     avanti, nell'indice, le stesse parole compaiono rientrate e vanno ignorate);
#   - una ricetta comincia con una riga "N. Titolo" preceduta da una riga vuota (così un rimando
#     spezzato a capo, "...del N." + "137. Mettete...", non viene preso per una ricetta);
#   - un capitolo comincia con una riga tutta maiuscola, senza rientro, preceduta da DUE righe
#     vuote (così i titoletti interni come "PASTA FROLLA", con una sola riga vuota prima, no);
#   - il testo tra il titolo di un capitolo e la sua prima ricetta (introduzione) non appartiene
#     a nessuna ricetta e non viene indicizzato.
# Pulizia: via BOM e caratteri di controllo; le righe spezzate di un paragrafo tornano una sola
# riga; le righe rientrate (ingredienti) restano righe separate e formano un paragrafo a sé;
# via i trattini bassi dei corsivi (_balsamella_ -> balsamella). Paragrafi separati da "\n\n".

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

INIZIO = "RICETTE"
FINE = "APPENDICE"
TITOLO_RICETTA = re.compile(r"^(\d{1,3})\. (.+)$")
CONTROLLO = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


class ErroreCorpus(Exception):
    """File del libro mancante o non conforme alle regole (ricette mancanti o doppie)."""


@dataclass(frozen=True)
class Ricetta:
    numero: int  # 1-790
    titolo: str  # es. "Gnocchi di patate"
    capitolo: str  # forma leggibile, es. "Minestre asciutte e di magro"
    testo: str  # testo pulito, SENZA la riga del titolo

    @property
    def documento_id(self) -> str:
        """Identificativo del documento, es. "ricetta-089"."""
        return f"ricetta-{self.numero:03d}"


def leggi_file(percorso: Path) -> str:
    """Testo del file in UTF-8, senza BOM."""
    try:
        return percorso.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        raise ErroreCorpus(
            f"file del libro non trovato: {percorso} (scaricarlo come spiegato nel README, sezione RAG)"
        ) from None


def paragrafi(testo: str) -> list[str]:
    """I paragrafi del testo di una ricetta (separati da una riga vuota)."""
    return [p for p in testo.split("\n\n") if p]


def _pulisci(testo: str) -> str:
    """Toglie i trattini bassi dei corsivi e normalizza gli spazi."""
    return " ".join(testo.replace("_", "").split())


def _e_capitolo(riga: str) -> bool:
    return not riga[0].isspace() and riga == riga.upper() and any(c.isalpha() for c in riga)


def _testo_ricetta(righe: list[str]) -> str:
    """Ricompone i paragrafi: righe normali unite da spazi, righe rientrate una per riga."""
    blocchi: list[str] = []
    gruppo: list[str] = []  # righe consecutive dello stesso tipo
    rientrato = False

    def chiudi():
        if gruppo:
            if rientrato:
                blocchi.append("\n".join(_pulisci(r) for r in gruppo))
            else:
                blocchi.append(_pulisci(" ".join(gruppo)))
            gruppo.clear()

    for riga in righe:
        if not riga.strip():
            chiudi()
            continue
        e_rientrata = riga[0].isspace()
        if gruppo and e_rientrata != rientrato:
            chiudi()
        rientrato = e_rientrata
        gruppo.append(riga)
    chiudi()
    return "\n\n".join(b for b in blocchi if b)


def estrai_ricette(testo: str) -> list[Ricetta]:
    """Le ricette del libro, nell'ordine in cui compaiono."""
    righe = [CONTROLLO.sub("", r).replace("\t", "    ").rstrip() for r in testo.lstrip("﻿").splitlines()]
    try:
        inizio = righe.index(INIZIO)
        fine = righe.index(FINE, inizio + 1)
    except ValueError:
        raise ErroreCorpus(f"il file non contiene le righe {INIZIO!r} e {FINE!r}: è il libro giusto?") from None

    ricette: list[Ricetta] = []
    capitolo = ""
    corrente: tuple[int, str, str] | None = None  # numero, titolo, capitolo
    righe_correnti: list[str] = []
    vuote = 0

    def chiudi():
        if corrente is not None:
            numero, titolo, cap = corrente
            ricette.append(Ricetta(numero, titolo, cap, _testo_ricetta(righe_correnti)))

    for riga in righe[inizio + 1:fine]:
        if not riga:
            vuote += 1
            righe_correnti.append("")
            continue
        trovata = TITOLO_RICETTA.match(riga)
        if vuote >= 2 and _e_capitolo(riga):
            chiudi()
            corrente, righe_correnti = None, []
            capitolo = riga.capitalize()
        elif vuote >= 1 and trovata:
            chiudi()
            corrente, righe_correnti = (int(trovata[1]), _pulisci(trovata[2]), capitolo), []
        elif corrente is not None:
            righe_correnti.append(riga)
        vuote = 0
    chiudi()
    return ricette


def controlla_numerazione(ricette: list[Ricetta], attese: int = 790) -> None:
    """Le ricette devono essere numerate da 1 ad `attese`, senza buchi né doppioni."""
    conteggi = Counter(r.numero for r in ricette)
    mancanti = sorted(set(range(1, attese + 1)) - set(conteggi))
    doppie = sorted(n for n, volte in conteggi.items() if volte > 1)
    fuori = sorted(n for n in conteggi if not 1 <= n <= attese)
    problemi = []
    if mancanti:
        problemi.append("mancanti: " + ", ".join(map(str, mancanti)))
    if doppie:
        problemi.append("doppie: " + ", ".join(map(str, doppie)))
    if fuori:
        problemi.append("fuori da 1-" + str(attese) + ": " + ", ".join(map(str, fuori)))
    if problemi:
        raise ErroreCorpus(f"numerazione delle ricette non valida ({len(ricette)} lette) - " + "; ".join(problemi))
