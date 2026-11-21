"""Pulizia del libro e divisione in ricette (lezione 7, esercizio 1)."""

# COSA PROVA QUESTO FILE
# Le regole di riconoscimento di ricette e capitoli sul piccolo libro finto di finti_rag.py e,
# se l'utente l'ha scaricato in dati/artusi.txt, sul libro vero: 790 ricette senza buchi e 23
# capitoli (verifica del corpus chiesta dal PDF, pag. 25). Il libro vero non è in Git: senza il
# file quel test viene saltato.

from pathlib import Path

import pytest
from finti_rag import CORPUS_PROVA, INTRODUZIONE_FRITTI

from rag.corpus import ErroreCorpus, controlla_numerazione, estrai_ricette, leggi_file, paragrafi

LIBRO_VERO = Path(__file__).resolve().parent.parent / "dati" / "artusi.txt"


@pytest.fixture
def ricette():
    return estrai_ricette(CORPUS_PROVA)


def per_numero(ricette, numero):
    return next(r for r in ricette if r.numero == numero)


def test_numeri_titoli_capitoli(ricette):
    assert [r.numero for r in ricette] == [1, 2, 3, 4, 5]
    assert [r.capitolo for r in ricette] == [
        "Brodi, gelatina e sughi", "Brodi, gelatina e sughi", "Minestre in brodo", "Fritti", "Fritti"]
    assert [r.titolo for r in ricette] == [
        "Brodo", "Gelatina", "Cappelletti all'uso di Romagna", "Pollo fritto", "Fritto di cervello"]
    assert per_numero(ricette, 4).documento_id == "ricetta-004"


def test_introduzione_esclusa(ricette):
    assert all(INTRODUZIONE_FRITTI not in r.testo for r in ricette)
    assert all("biada dell'uomo" not in r.testo for r in ricette)
    assert all("base di molte vivande" not in r.testo for r in ricette)


def test_rimando_spezzato_e_titoli_finti(ricette):
    assert 137 not in [r.numero for r in ricette]
    terza = per_numero(ricette, 3).testo
    assert "137. Mettete il composto" in terza
    assert "PASTA FROLLA" in terza
    assert "UN AMMIRATORE" in terza
    assert {r.capitolo for r in ricette} == {"Brodi, gelatina e sughi", "Minestre in brodo", "Fritti"}


def test_appendice_esclusa(ricette):
    assert 227 not in [r.numero for r in ricette]
    assert "Scaloppine" not in per_numero(ricette, 5).testo
    assert "END OF THE PROJECT" not in per_numero(ricette, 5).testo


def test_testo_pulito(ricette):
    terza = per_numero(ricette, 3)
    assert "_" not in terza.testo
    assert "di balsamella fatta" in terza.testo
    assert not terza.testo.startswith("Cappelletti")
    assert terza.testo.startswith("Sono detti così per la loro forma a cappello. Ecco il modo")
    blocchi = paragrafi(terza.testo)
    assert "Ricotta, grammi 180.\nPetto di cappone, mezzo.\nParmigiano grattato, grammi 30.\n" \
           "Uova, uno intero e un rosso." in blocchi
    # Le righe di un paragrafo normale sono unite in una sola riga.
    assert all("\n" not in p for p in blocchi if not p.startswith("Ricotta"))
    assert len(terza.testo) > 1200
    assert "﻿" not in ricette[0].testo


def test_fine_riga_windows_e_senza_bom(ricette):
    windows = CORPUS_PROVA.lstrip("﻿").replace("\n", "\r\n")
    assert estrai_ricette(windows) == ricette


def test_numerazione(ricette):
    controlla_numerazione(ricette, attese=5)
    with pytest.raises(ErroreCorpus, match="mancanti: 3"):
        controlla_numerazione([r for r in ricette if r.numero != 3], attese=5)
    with pytest.raises(ErroreCorpus, match="doppie: 4"):
        controlla_numerazione(ricette + [per_numero(ricette, 4)], attese=5)


def test_file_mancante(tmp_path):
    percorso = tmp_path / "x.txt"
    with pytest.raises(ErroreCorpus) as errore:
        leggi_file(percorso)
    assert str(percorso) in str(errore.value)


def test_leggi_file_toglie_il_bom(tmp_path):
    percorso = tmp_path / "libro.txt"
    percorso.write_text(CORPUS_PROVA, encoding="utf-8")
    assert not leggi_file(percorso).startswith("﻿")


@pytest.mark.skipif(not LIBRO_VERO.exists(), reason="dati/artusi.txt non scaricato (non è in Git)")
def test_libro_vero():
    ricette = estrai_ricette(leggi_file(LIBRO_VERO))
    assert len(ricette) == 790
    controlla_numerazione(ricette)
    capitoli = list(dict.fromkeys(r.capitolo for r in ricette))
    assert len(capitoli) == 23
    assert capitoli[0] == "Brodi, gelatina e sughi"
    assert capitoli[-1] == "Cose diverse"
    gnocchi = per_numero(ricette, 89)
    assert (gnocchi.titolo, gnocchi.capitolo) == ("Gnocchi di patate", "Minestre asciutte e di magro")


def test_libro_finto_come_il_vero():
    assert CORPUS_PROVA.startswith("﻿")
