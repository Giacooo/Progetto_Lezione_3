"""Test della copia di sicurezza del file delle preferenze usata dalle prove reali."""

# COSA PROVA QUESTO FILE
# Le prove reali dello step 4 cambiano il file delle preferenze VERO dell'utente. Qui si
# controlla, in una cartella temporanea (mai in archivio/), che la copia di sicurezza su disco
# (preferenze.json.bak) protegga il file anche se la prova fallisce o viene interrotta.

import pytest
from protezione_preferenze import preferenze_protette

ORIGINALE = b'{"lingua": "italiano", "fuso_orario": "Europe/Rome", "stile": "sintetico"}'


def percorsi(tmp_path):
    percorso = tmp_path / "archivio" / "preferenze.json"
    return percorso, tmp_path / "archivio" / "preferenze.json.bak"


# File presente: durante la prova c'è la copia su disco; alla fine il contenuto originale è
# tornato e la copia è sparita.
def test_file_presente_copiato_e_rimesso(tmp_path):
    percorso, copia = percorsi(tmp_path)
    percorso.parent.mkdir()
    percorso.write_bytes(ORIGINALE)
    with preferenze_protette(percorso):
        assert copia.read_bytes() == ORIGINALE
        percorso.write_text("contenuto di prova", encoding="utf-8")
    assert percorso.read_bytes() == ORIGINALE
    assert not copia.exists()


# File assente: la prova può crearlo, ma alla fine non resta né il file né la copia.
def test_file_assente_resta_assente(tmp_path):
    percorso, copia = percorsi(tmp_path)
    with preferenze_protette(percorso):
        assert percorso.parent.is_dir()
        assert not copia.exists()
        percorso.write_text("contenuto di prova", encoding="utf-8")
    assert not percorso.exists()
    assert not copia.exists()


# Errore dentro la prova: il file viene rimesso com'era lo stesso.
def test_errore_nella_prova_rimette_il_file(tmp_path):
    percorso, copia = percorsi(tmp_path)
    percorso.parent.mkdir()
    percorso.write_bytes(ORIGINALE)
    with pytest.raises(ValueError):
        with preferenze_protette(percorso):
            percorso.unlink()
            raise ValueError("prova fallita")
    assert percorso.read_bytes() == ORIGINALE
    assert not copia.exists()


# Copia già presente (una serie precedente interrotta): ci si ferma subito, senza toccare né il
# file né la copia, che potrebbe essere l'unica versione buona.
def test_copia_gia_presente_ferma_tutto(tmp_path):
    percorso, copia = percorsi(tmp_path)
    percorso.parent.mkdir()
    percorso.write_text("file lasciato da una prova interrotta", encoding="utf-8")
    copia.write_bytes(ORIGINALE)
    with pytest.raises(RuntimeError, match="preferenze.json.bak"):
        with preferenze_protette(percorso):
            pytest.fail("la prova non doveva partire")
    assert percorso.read_text(encoding="utf-8") == "file lasciato da una prova interrotta"
    assert copia.read_bytes() == ORIGINALE
