import json
from datetime import date
from pathlib import Path

import pytest
from assistente.strumenti_mcp.giorni import aggiungi_giorni_lavorativi, carica_festivita, conta_giorni

FILE_FESTIVITA = Path(__file__).parent.parent / "assistente" / "dati" / "festivita.json"
F = carica_festivita(FILE_FESTIVITA)


def test_file_festivita_reale():
    assert len(F) == 26
    assert F[date(2026, 4, 5)] == "Pasqua"
    assert F[date(2027, 3, 29)] == "Lunedì dell'Angelo"
    assert F[date(2026, 10, 4)] == "San Francesco"


def test_conta_giorni_con_festivita():
    risultato = conta_giorni("2026-12-23", "2026-12-28", F)
    assert "5 giorni di calendario" in risultato
    assert "2 giorni lavorativi" in risultato
    assert "2026-12-25" in risultato and "Natale" in risultato
    assert "2026-12-26" in risultato and "Santo Stefano" in risultato
    assert risultato.endswith("(calcolo indicativo, non normativo)")


def test_conta_giorni_stessa_data():
    risultato = conta_giorni("2026-12-23", "2026-12-23", F)
    assert "0 giorni di calendario" in risultato and "0 giorni lavorativi" in risultato
    assert "Nessuna festività" in risultato
    assert "non normativo" in risultato


def test_singolare():
    risultato = conta_giorni("2026-12-23", "2026-12-24", F)
    assert "1 giorno di calendario" in risultato and "1 giorno lavorativo" in risultato
    assert "1 giorno lavorativo dopo" in aggiungi_giorni_lavorativi("2026-12-23", 1, F)


def test_aggiungi_giorni_lavorativi():
    risultato = aggiungi_giorni_lavorativi("2026-12-23", 2, F)
    assert "2026-12-28" in risultato and "non normativo" in risultato


def test_partenza_di_sabato():
    assert "2026-11-09" in aggiungi_giorni_lavorativi("2026-11-07", 1, F)


def test_festa_di_domenica_senza_effetto():
    assert "2026-10-05" in aggiungi_giorni_lavorativi("2026-10-02", 1, F)


@pytest.mark.parametrize("inizio, fine, frammento", [
    ("03/11/2026", "2026-11-10", "AAAA-MM-GG"),
    ("2026-11-03", "10/11/2026", "AAAA-MM-GG"),
    ("2026-02-30", "2026-03-10", "AAAA-MM-GG"),
    ("2026-11-10", "2026-11-03", "prima"),
    ("2025-12-31", "2026-01-05", "2025"),
    ("2027-12-30", "2028-01-02", "2028"),
    ("20261223", "2026-12-28", "AAAA-MM-GG"),
    ("2026-W52-3", "2026-12-28", "AAAA-MM-GG"),
    ("2026-1-5", "2026-12-28", "AAAA-MM-GG"),
    (" 2026-12-23", "2026-12-28", "AAAA-MM-GG"),
    ("2026-12-23", "20261228", "AAAA-MM-GG"),
])
def test_conta_giorni_errori(inizio, fine, frammento):
    with pytest.raises(ValueError, match=frammento):
        conta_giorni(inizio, fine, F)


@pytest.mark.parametrize("inizio, giorni, frammento", [
    ("03/11/2026", 1, "AAAA-MM-GG"),
    ("2026-02-30", 1, "AAAA-MM-GG"),
    ("2025-12-31", 1, "2025"),
    ("2027-12-30", 5, "2028"),
    ("20261223", 1, "AAAA-MM-GG"),
    ("2026-W52-3", 1, "AAAA-MM-GG"),
    ("2026-1-5", 1, "AAAA-MM-GG"),
    (" 2026-12-23", 1, "AAAA-MM-GG"),
    ("2026-11-03", 0, "tra 1 e 365"),
    ("2026-11-03", 366, "tra 1 e 365"),
])
def test_aggiungi_giorni_errori(inizio, giorni, frammento):
    with pytest.raises(ValueError, match=frammento):
        aggiungi_giorni_lavorativi(inizio, giorni, F)


def test_carica_festivita_data_fuori_dagli_anni(tmp_path):
    percorso = tmp_path / "f.json"
    percorso.write_text(
        json.dumps({"anni": [2026], "festivita": [{"data": "2027-01-01", "nome": "Capodanno"}]}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="2027-01-01"):
        carica_festivita(percorso)
