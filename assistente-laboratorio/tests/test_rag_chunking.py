"""Divisione delle ricette in chunk (lezione 7, esercizio 1; verifica di pag. 25)."""

# COSA PROVA QUESTO FILE
# Le due strategie ("paragrafi" e "finestra") su una ricetta breve (un solo chunk) e su una
# lunga (più chunk, ciascuno entro la dimensione, con la sovrapposizione tra consecutivi).

import pytest
from finti_rag import CORPUS_PROVA

from rag.chunking import dividi
from rag.corpus import estrai_ricette

STRATEGIE = ["paragrafi", "finestra"]
LUNGA = next(r for r in estrai_ricette(CORPUS_PROVA) if r.numero == 3).testo
PAROLA_PIU_LUNGA = max(len(p) for p in LUNGA.split())


def sovrapposizione(precedente: str, successivo: str) -> str:
    """Il pezzo più lungo con cui `successivo` comincia e `precedente` finisce."""
    for lunghezza in range(min(len(precedente), len(successivo)), 0, -1):
        if precedente.endswith(successivo[:lunghezza]):
            return successivo[:lunghezza]
    return ""


@pytest.mark.parametrize("strategia", STRATEGIE)
def test_ricetta_breve_un_chunk(strategia):
    testo = ("Tagliate il pollo a pezzi e friggetelo nell'olio bollente. " * 5).strip()
    assert 250 < len(testo) < 400
    assert dividi(testo, strategia, 1200, 200) == [testo]


@pytest.mark.parametrize("strategia", STRATEGIE)
def test_ricetta_lunga_piu_chunk(strategia):
    chunk = dividi(LUNGA, strategia, 400, 80)
    assert len(chunk) >= 3
    assert all(c.strip() for c in chunk)
    assert all(len(c) <= 400 + PAROLA_PIU_LUNGA + 1 for c in chunk)


@pytest.mark.parametrize("strategia", STRATEGIE)
def test_overlap_tra_consecutivi(strategia):
    chunk = dividi(LUNGA, strategia, 400, 80)
    for precedente, successivo in zip(chunk, chunk[1:]):
        comune = sovrapposizione(precedente, successivo).strip()
        assert comune.split(), (precedente, successivo)
        assert len(comune) <= 80 + PAROLA_PIU_LUNGA


@pytest.mark.parametrize("strategia", STRATEGIE)
def test_overlap_zero(strategia):
    chunk = dividi(LUNGA, strategia, 400, 0)
    assert [p for c in chunk for p in c.split()] == LUNGA.split()


@pytest.mark.parametrize("strategia", STRATEGIE)
def test_nessuna_parola_spezzata(strategia):
    parole = set(LUNGA.split())
    for c in dividi(LUNGA, strategia, 400, 80):
        assert set(c.split()) <= parole


@pytest.mark.parametrize("strategia", STRATEGIE)
def test_overlap_vicino_alla_dimensione_termina(strategia):
    chunk = dividi(LUNGA, strategia, 100, 99)
    assert chunk[-1].split()[-1] == LUNGA.split()[-1]


def test_ingredienti_non_spezzati():
    ingredienti = ("Ricotta, grammi 180.\nPetto di cappone, mezzo.\nParmigiano grattato, grammi 30.\n"
                   "Uova, uno intero e un rosso.")
    assert sum(ingredienti in c for c in dividi(LUNGA, "paragrafi", 400, 80)) >= 1


def test_paragrafo_troppo_lungo():
    lungo = " ".join(f"parola{n}" for n in range(130))
    assert len(lungo) > 1000
    testo = "Breve inizio della ricetta.\n\n" + lungo + "\n\nBreve fine."
    chunk = dividi(testo, "paragrafi", 300, 50)
    assert len(chunk) >= 4
    assert all(len(c) <= 300 + 10 for c in chunk)
    assert chunk[0].startswith("Breve inizio")
    assert chunk[-1].endswith("Breve fine.")


def test_strategia_sconosciuta():
    with pytest.raises(ValueError):
        dividi(LUNGA, "frasi", 400, 80)
