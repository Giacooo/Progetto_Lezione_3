# COSA PROVA QUESTO FILE
# Lo strumento orologio (strumenti.py): che il formato dell'ora sia corretto, che l'ora
# solare e quella legale siano gestite, che il fuso venga rispettato e che lo strumento
# abbia nome, descrizione e nessun parametro come previsto.

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from assistente.strumenti import crea_strumenti, formatta_ora

ROMA = ZoneInfo("Europe/Rome")
# Due istanti fissi, in UTC: uno d'inverno e uno d'estate, per provare ora solare e legale.
GENNAIO = datetime(2026, 1, 15, 11, 0, 0, tzinfo=timezone.utc)
LUGLIO = datetime(2026, 7, 15, 11, 0, 0, tzinfo=timezone.utc)


# D'inverno Roma ha UTC+1: le 11:00 UTC diventano le 12:00 con "+01:00".
def test_ora_solare():
    assert formatta_ora(ROMA, GENNAIO) == "2026-01-15T12:00:00+01:00 (Europe/Rome)"


# D'estate (ora legale) Roma ha UTC+2: le 11:00 UTC diventano le 13:00 con "+02:00".
def test_ora_legale():
    assert formatta_ora(ROMA, LUGLIO) == "2026-07-15T13:00:00+02:00 (Europe/Rome)"


# Con un altro fuso (New York, UTC-5 d'inverno) le 11:00 UTC diventano le 06:00 con "-05:00".
# Prova che il fuso arriva dal parametro, non dal computer.
def test_altro_fuso():
    fuso = ZoneInfo("America/New_York")
    assert formatta_ora(fuso, GENNAIO) == "2026-01-15T06:00:00-05:00 (America/New_York)"


# Il "contratto" dello strumento: nome giusto, nessun parametro (args vuoti) e una
# descrizione che inizia come previsto. È ciò che il modello vede dello strumento.
def test_strumento_contratto():
    (strumento,) = crea_strumenti(ROMA)
    assert strumento.name == "ora_corrente"
    assert strumento.args == {}
    assert strumento.description.startswith("Restituisce data e ora correnti")


# Passando un orologio finto (che restituisce sempre GENNAIO), lo strumento dà un
# risultato prevedibile. Mostra che l'orologio si può sostituire nei test.
def test_strumento_usa_l_istante_iniettato():
    (strumento,) = crea_strumenti(ROMA, adesso=lambda: GENNAIO)
    assert strumento.invoke({}) == "2026-01-15T12:00:00+01:00 (Europe/Rome)"
