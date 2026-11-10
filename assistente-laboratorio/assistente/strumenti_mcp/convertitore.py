"""Convertitore di unità da elenco chiuso: lunghezza, massa e temperatura.

Lunghezza e massa passano da un'unità di base (metro, chilogrammo) con fattori fissi;
la temperatura passa dal kelvin. Ogni errore dell'utente è un ValueError con un messaggio
in italiano.
"""

import math

DECIMALI = 4  # cifre decimali massime del risultato
_TOLLERANZA_ZERO_ASSOLUTO = 1e-9  # evita falsi errori per gli arrotondamenti di -459.67 F

# unità -> fattore verso l'unità di base della categoria
_LUNGHEZZA = {"mm": 0.001, "cm": 0.01, "m": 1, "km": 1000, "in": 0.0254, "ft": 0.3048, "mi": 1609.344}
_MASSA = {"g": 0.001, "kg": 1, "lb": 0.45359237, "oz": 0.028349523125}
_TEMPERATURA = ("C", "F", "K")

_CATEGORIE = {
    "lunghezza": _LUNGHEZZA,
    "massa": _MASSA,
    "temperatura": dict.fromkeys(_TEMPERATURA),
}
UNITA_AMMESSE = [unita for categoria in _CATEGORIE.values() for unita in categoria]


def _categoria(unita):
    """Restituisce il nome della categoria dell'unità, o ValueError se non è nell'elenco."""
    for nome, unita_della_categoria in _CATEGORIE.items():
        if unita in unita_della_categoria:
            return nome
    raise ValueError(
        f"unità non ammessa: {unita!r}. Unità ammesse (maiuscole comprese): "
        + ", ".join(UNITA_AMMESSE)
    )


def _in_kelvin(valore, unita):
    if unita == "C":
        return valore + 273.15
    if unita == "F":
        return (valore - 32) * 5 / 9 + 273.15
    return valore


def _da_kelvin(kelvin, unita):
    if unita == "C":
        return kelvin - 273.15
    if unita == "F":
        return (kelvin - 273.15) * 9 / 5 + 32
    return kelvin


def _formatta(numero):
    """Al massimo 4 decimali, senza zeri finali e senza "-0"."""
    testo = f"{round(numero, DECIMALI):.{DECIMALI}f}".rstrip("0").rstrip(".")
    return "0" if testo == "-0" else testo


def converti_unita(valore: float, da_unita: str, a_unita: str) -> str:
    """Converte un valore tra due unità della stessa categoria."""
    if not math.isfinite(valore):
        raise ValueError("valore non valido")
    categoria_da = _categoria(da_unita)
    categoria_a = _categoria(a_unita)
    if categoria_da != categoria_a:
        raise ValueError(
            f"unità incompatibili: {da_unita} è {categoria_da}, {a_unita} è {categoria_a}"
        )
    if categoria_da == "temperatura":
        kelvin = _in_kelvin(valore, da_unita)
        if kelvin < -_TOLLERANZA_ZERO_ASSOLUTO:
            raise ValueError("temperatura sotto lo zero assoluto")
        risultato = _da_kelvin(max(kelvin, 0.0), a_unita)
    else:
        fattori = _CATEGORIE[categoria_da]
        risultato = valore * fattori[da_unita] / fattori[a_unita]
    return f"{_formatta(valore)} {da_unita} = {_formatta(risultato)} {a_unita}"
