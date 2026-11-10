"""Calcolatrice sicura: valuta espressioni aritmetiche senza usare la valutazione dinamica di Python.

Il testo viene trasformato in un albero con il modulo "ast" e visitato da noi,
accettando solo un elenco chiuso di nodi. Ogni errore dell'utente è un ValueError
con un messaggio in italiano.
"""

import ast
import math
import operator
import re

LUNGHEZZA_MASSIMA = 200  # caratteri dell'espressione
ESPONENTE_MASSIMO = 100  # valore assoluto dell'esponente di "**"
CIFRE_MASSIME = 300  # stima del numero di cifre del risultato di "**"

_OPERATORI_BINARI = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_OPERATORI_UNARI = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_NUMERO_DECIMALE = re.compile(r"\d+(\.\d*)?|\.\d+")  # niente 1e3, 1_0, 0x10


def _valuta(nodo, sorgente):
    """Visita ricorsivamente il nodo e restituisce un numero."""
    if isinstance(nodo, ast.Expression):
        return _valuta(nodo.body, sorgente)
    if isinstance(nodo, ast.Constant):
        # bool è una sottoclasse di int: lo escludiamo esplicitamente
        if type(nodo.value) in (int, float):
            testo = ast.get_source_segment(sorgente, nodo)
            if testo is None or not _NUMERO_DECIMALE.fullmatch(testo):
                raise ValueError(f"numero non ammesso: {testo}")
            return nodo.value
        raise ValueError(
            f"costrutto non ammesso: valore di tipo {type(nodo.value).__name__} ({nodo.value!r})"
        )
    if isinstance(nodo, ast.BinOp) and type(nodo.op) in _OPERATORI_BINARI:
        sinistra = _valuta(nodo.left, sorgente)
        destra = _valuta(nodo.right, sorgente)
        if isinstance(nodo.op, ast.Pow):
            _controlla_potenza(sinistra, destra)
        try:
            return _OPERATORI_BINARI[type(nodo.op)](sinistra, destra)
        except ZeroDivisionError:
            raise ValueError("divisione per zero") from None
        except OverflowError:
            raise ValueError("risultato troppo grande") from None
    if isinstance(nodo, ast.UnaryOp) and type(nodo.op) in _OPERATORI_UNARI:
        return _OPERATORI_UNARI[type(nodo.op)](_valuta(nodo.operand, sorgente))
    raise ValueError(f"costrutto non ammesso: {type(nodo).__name__}")


def _controlla_potenza(base, esponente):
    """Rifiuta potenze con esponente o risultato fuori misura."""
    if base < 0 and esponente != int(esponente):
        raise ValueError("risultato non reale")
    if abs(esponente) > ESPONENTE_MASSIMO:
        raise ValueError(f"esponente oltre {ESPONENTE_MASSIMO}")
    if abs(esponente) * math.log10(max(abs(base), 2)) > CIFRE_MASSIME:
        raise ValueError("risultato troppo grande")


def _formatta(valore):
    """Interi e float interi senza decimali; gli altri float a 12 cifre significative."""
    if isinstance(valore, float):
        if not math.isfinite(valore):
            raise ValueError("risultato troppo grande")
        if valore.is_integer():
            return str(int(valore))
        return f"{valore:.12g}"
    return str(valore)


def calcola(espressione: str) -> str:
    """Calcola un'espressione aritmetica e restituisce il risultato come testo."""
    if not espressione.strip():
        raise ValueError("espressione vuota")
    if len(espressione) > LUNGHEZZA_MASSIMA:
        raise ValueError(f"espressione troppo lunga (massimo {LUNGHEZZA_MASSIMA} caratteri)")
    sorgente = espressione.strip()
    try:
        albero = ast.parse(sorgente, mode="eval")
    except (SyntaxError, RecursionError):
        raise ValueError("errore di sintassi") from None
    return _formatta(_valuta(albero, sorgente))
