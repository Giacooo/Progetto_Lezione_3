from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from assistente.strumenti import crea_strumenti, formatta_ora

ROMA = ZoneInfo("Europe/Rome")
GENNAIO = datetime(2026, 1, 15, 11, 0, 0, tzinfo=timezone.utc)
LUGLIO = datetime(2026, 7, 15, 11, 0, 0, tzinfo=timezone.utc)


def test_ora_solare():
    assert formatta_ora(ROMA, GENNAIO) == "2026-01-15T12:00:00+01:00 (Europe/Rome)"


def test_ora_legale():
    assert formatta_ora(ROMA, LUGLIO) == "2026-07-15T13:00:00+02:00 (Europe/Rome)"


def test_altro_fuso():
    fuso = ZoneInfo("America/New_York")
    assert formatta_ora(fuso, GENNAIO) == "2026-01-15T06:00:00-05:00 (America/New_York)"


def test_strumento_contratto():
    (strumento,) = crea_strumenti(ROMA)
    assert strumento.name == "ora_corrente"
    assert strumento.args == {}
    assert strumento.description.startswith("Restituisce data e ora correnti")


def test_strumento_usa_l_istante_iniettato():
    (strumento,) = crea_strumenti(ROMA, adesso=lambda: GENNAIO)
    assert strumento.invoke({}) == "2026-01-15T12:00:00+01:00 (Europe/Rome)"
