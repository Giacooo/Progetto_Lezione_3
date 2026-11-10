"""Test delle note persistenti: SQLite su un file temporaneo, senza modello e senza rete."""

# COSA FA QUESTO FILE
# Controlla aggiunta, elenco, eliminazione, persistenza, errori e log delle note.

import logging
import sqlite3

import pytest
from assistente.strumenti_mcp.note import aggiungi_nota, elenca_note, elimina_nota


@pytest.fixture
def db(tmp_path):
    return tmp_path / "sotto" / "note.sqlite"


def test_aggiunta_assegna_id_crescenti(db):
    assert aggiungi_nota("prima", db).startswith("Nota 1 creata il ")
    assert aggiungi_nota("seconda", db).startswith("Nota 2 creata il ")
    assert aggiungi_nota("terza", db).endswith(": terza")


def test_testo_viene_ripulito(db):
    assert aggiungi_nota("  ciao  ", db).endswith(": ciao")


def test_testo_di_500_caratteri_ammesso(db):
    assert aggiungi_nota("a" * 500, db).endswith("a" * 500)


def test_elenco_ordinato_e_limite(db):
    aggiungi_nota("prima", db)
    aggiungi_nota("seconda", db)
    righe = elenca_note(10, db).split("\n")
    assert len(righe) == 2
    assert righe[0].startswith("Nota 1 del ") and righe[0].endswith(": prima")
    assert righe[1].startswith("Nota 2 del ") and righe[1].endswith(": seconda")
    assert elenca_note(1, db).split("\n") == [righe[0]]


def test_elenco_vuoto(db):
    assert elenca_note(10, db) == "Nessuna nota salvata."


def test_eliminazione(db):
    aggiungi_nota("prima", db)
    aggiungi_nota("seconda", db)
    assert elimina_nota(1, db) == "Nota 1 eliminata: prima"
    risultato = elenca_note(10, db)
    assert "seconda" in risultato and "prima" not in risultato


def test_persistenza(db):
    aggiungi_nota("resta", db)
    assert "resta" in elenca_note(10, db)


@pytest.mark.parametrize("testo", ["", "   ", "x" * 501])
def test_testo_non_valido(db, testo):
    with pytest.raises(ValueError):
        aggiungi_nota(testo, db)
    assert elenca_note(10, db) == "Nessuna nota salvata."


@pytest.mark.parametrize("limite", [0, 51])
def test_limite_non_valido(db, limite):
    with pytest.raises(ValueError, match="limite"):
        elenca_note(limite, db)


def test_eliminazione_inesistente(db):
    aggiungi_nota("prima", db)
    with pytest.raises(ValueError, match="99"):
        elimina_nota(99, db)
    assert elenca_note(10, db).count("\n") == 0 and "prima" in elenca_note(10, db)


def test_percorso_cartella(tmp_path):
    with pytest.raises(ValueError, match="non accessibile"):
        aggiungi_nota("x", tmp_path)


def test_log_modifiche(db, caplog):
    with caplog.at_level(logging.INFO):
        aggiungi_nota("prima", db)
        elimina_nota(1, db)
        with pytest.raises(ValueError):
            elimina_nota(99, db)
    messaggi = [r.getMessage() for r in caplog.records]
    assert "nota creata id=1" in messaggi
    assert "nota eliminata id=1" in messaggi
    assert "eliminazione rifiutata id=99 inesistente" in messaggi


def test_limite_50_ammesso(db):
    assert elenca_note(50, db) == "Nessuna nota salvata."


def test_eliminazione_id_enorme(db, caplog):
    aggiungi_nota("prima", db)
    with caplog.at_level(logging.INFO):
        with pytest.raises(ValueError, match="inesistente"):
            elimina_nota(2**63, db)
    assert f"eliminazione rifiutata id={2**63} inesistente" in [r.getMessage() for r in caplog.records]
    assert "prima" in elenca_note(10, db)
