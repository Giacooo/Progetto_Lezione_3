"""Test del modulo delle preferenze (funzioni pure: niente server, niente LM Studio)."""

import json
from zoneinfo import ZoneInfo

import pytest

from assistente.errori import ErrorePreferenze
from assistente.preferenze import Preferenze, leggi_preferenze_da_testo, predefinite, prompt_agente

VALIDO = {"lingua": "inglese", "fuso_orario": "America/New_York", "stile": "dettagliato"}


def json_con(**modifiche) -> str:
    return json.dumps({**VALIDO, **modifiche})


def senza(chiave: str) -> str:
    return json.dumps({k: v for k, v in VALIDO.items() if k != chiave})


# File valido: le tre chiavi diventano una Preferenze con il fuso già convertito.
def test_file_valido():
    assert leggi_preferenze_da_testo(json_con()) == Preferenze(
        "inglese", ZoneInfo("America/New_York"), "dettagliato"
    )


def test_chiavi_in_piu_ignorate():
    assert leggi_preferenze_da_testo(json_con(colore="blu")).lingua == "inglese"


def test_spazi_attorno_alla_lingua_tolti():
    assert leggi_preferenze_da_testo(json_con(lingua=" inglese ")).lingua == "inglese"


# Ogni difetto solleva ErrorePreferenze (mai TypeError o simili) con il motivo.
@pytest.mark.parametrize(
    ("contenuto", "atteso"),
    [
        ("", "JSON non valido"),
        ("   ", "JSON non valido"),
        ("{", "JSON non valido"),
        ("[]", "oggetto"),
        ("null", "oggetto"),
        (senza("lingua"), "manca la chiave 'lingua'"),
        (senza("fuso_orario"), "manca la chiave 'fuso_orario'"),
        (senza("stile"), "manca la chiave 'stile'"),
        (json_con(fuso_orario="Europa/Roma"), "fuso_orario non valido: 'Europa/Roma'"),
        (json_con(fuso_orario="Europe"), "fuso_orario non valido"),
        (json_con(fuso_orario=""), "fuso_orario non valido"),
        (json_con(fuso_orario="../x"), "fuso_orario non valido"),
        (json_con(fuso_orario=5), "fuso_orario"),
        (json_con(stile="lungo"), "stile deve essere 'sintetico' o 'dettagliato', non 'lungo'"),
        (json_con(stile=None), "stile"),
        (json_con(stile=["sintetico"]), "stile"),
        (json_con(lingua=""), "lingua"),
        (json_con(lingua="   "), "lingua"),
        (json_con(lingua="a\nb"), "lingua"),
        (json_con(lingua=["it"]), "lingua"),
    ],
)
def test_difetti(contenuto, atteso):
    with pytest.raises(ErrorePreferenze) as errore:
        leggi_preferenze_da_testo(contenuto)
    assert atteso in str(errore.value)


def test_predefinite():
    fuso = ZoneInfo("Europe/Rome")
    assert predefinite(fuso) == Preferenze("italiano", fuso, "sintetico")


# Il paragrafo delle preferenze sta in cima, poi una riga vuota, poi il prompt di base.
def test_prompt_agente_inizia_con_il_paragrafo():
    preferenze = Preferenze("inglese", ZoneInfo("America/New_York"), "dettagliato")
    assert prompt_agente(preferenze, "BASE") == (
        "Preferenze dell'utente: rispondi in inglese. "
        "Stile: risposte complete, con spiegazioni e passaggi. "
        "Il fuso orario predefinito è America/New_York: "
        "lo strumento ora_corrente lo usa già, non chiederlo all'utente.\n\nBASE"
    )


def test_prompt_agente_con_i_predefiniti():
    assert prompt_agente(predefinite(ZoneInfo("Europe/Rome")), "BASE") == (
        "Preferenze dell'utente: rispondi in italiano. "
        "Stile: risposte brevi e chiare, in poche frasi. "
        "Il fuso orario predefinito è Europe/Rome: "
        "lo strumento ora_corrente lo usa già, non chiederlo all'utente.\n\nBASE"
    )
