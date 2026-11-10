import json
from pathlib import Path

import pytest
from assistente.strumenti_mcp.catalogo import carica_catalogo, cerca_corsi, dettaglio_corso

FILE_CATALOGO = Path(__file__).parent.parent / "assistente" / "dati" / "catalogo.json"
C = carica_catalogo(FILE_CATALOGO)


def test_file_catalogo_reale():
    assert len(C) == 10
    assert len({corso["codice"] for corso in C}) == 10
    assert {corso["sede"] for corso in C} <= {"Pordenone", "Udine", "Trieste"}
    python = [corso for corso in C if "Python" in corso["titolo"]]
    assert len(python) >= 2 and len({corso["sede"] for corso in python}) >= 2
    assert [corso["sede"] for corso in python].count("Udine") == 1


def test_cerca_python():
    risultato = cerca_corsi("python", 5, C)
    assert "ITS-DAT-01" in risultato and "ITS-AUT-01" in risultato
    assert "Udine" in risultato and "Pordenone" in risultato
    assert "ITS-AI-01" not in risultato


def test_cerca_limita_i_risultati():
    risultato = cerca_corsi("python", 1, C)
    assert "ITS-DAT-01" in risultato and "ITS-AUT-01" not in risultato  # ordine del file


def test_cerca_per_sede_e_codice():
    assert "ITS-SIC-01" in cerca_corsi("UDINE", 20, C)
    assert cerca_corsi("its-ai-02", 5, C).count("ITS-") == 1


def test_cerca_testo_con_spazi():
    assert "ITS-DAT-01" in cerca_corsi("  Python  ", 5, C)


def test_cerca_senza_risultati():
    assert cerca_corsi("astronautica", 5, C) == 'Nessun corso trovato per "astronautica".'


def test_dettaglio():
    risultato = dettaglio_corso("ITS-AI-01", C)
    assert "Fondamenti di intelligenza artificiale" in risultato
    assert "Pordenone" in risultato and "120 ore" in risultato


def test_dettaglio_codice_senza_distinzione_di_maiuscole():
    assert "ITS-AI-01" in dettaglio_corso("  its-ai-01 ", C)


@pytest.mark.parametrize("testo", ["", "   "])
def test_errore_testo_vuoto(testo):
    with pytest.raises(ValueError, match="testo vuoto"):
        cerca_corsi(testo, 5, C)


@pytest.mark.parametrize("massimo", [0, 21, -1])
def test_errore_max_risultati(massimo):
    with pytest.raises(ValueError, match="max_risultati"):
        cerca_corsi("python", massimo, C)


def test_errore_codice_inesistente():
    with pytest.raises(ValueError, match="cerca_corsi"):
        dettaglio_corso("ITS-XX-99", C)


def test_carica_catalogo_malformato(tmp_path):
    file = tmp_path / "catalogo.json"
    file.write_text(json.dumps({"corsi": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="lista"):
        carica_catalogo(file)
    file.write_text(json.dumps([{"codice": "X", "titolo": "T"}]), encoding="utf-8")
    with pytest.raises(ValueError, match="Campi richiesti"):
        carica_catalogo(file)
    corso = {"codice": "X", "titolo": "T", "sede": "Udine", "durata_ore": 60}
    for durata in ("60", True):
        file.write_text(json.dumps([{**corso, "durata_ore": durata}]), encoding="utf-8")
        with pytest.raises(ValueError, match="durata_ore"):
            carica_catalogo(file)
    file.write_text(json.dumps([corso, corso]), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicato"):
        carica_catalogo(file)
