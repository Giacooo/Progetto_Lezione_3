"""Server MCP con gli strumenti del laboratorio."""

# COSA FA QUESTO FILE
# Pubblica gli strumenti tramite il protocollo MCP. Il programma principale lo avvia come
# sottoprocesso (trasporto stdio) e ne scopre il catalogo (discovery) invece di riscriverlo.
# ATTENZIONE: su stdout passa solo il protocollo, quindi niente print; i log vanno su stderr.
# Convenzione: la funzione registrata ha lo stesso nome dello strumento, la docstring in
# italiano e' la descrizione che vede il modello, e ogni ValueError diventa un ToolError.

import logging
import sys

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from assistente.strumenti_mcp import calcolatrice, convertitore

logger = logging.getLogger(__name__)

mcp = FastMCP("Strumenti del laboratorio")


@mcp.tool
def calcola(espressione: str) -> str:
    """Valuta un'espressione aritmetica con numeri, + - * / // % ** e parentesi.

    Usala per ogni calcolo, anche semplice, invece di calcolare a mente.
    Traduci le parole italiane negli operatori: "per", "moltiplicato", "x" -> *;
    "diviso" -> /; "più" -> +; "meno" -> -. Esempio: "1234 per 5678" -> "1234 * 5678".
    """
    try:
        risultato = calcolatrice.calcola(espressione)
    except ValueError as errore:
        logger.info("calcola rifiutata: %s", errore)
        raise ToolError(str(errore)) from errore
    return risultato


@mcp.tool
def converti_unita(valore: float, da_unita: str, a_unita: str) -> str:
    """Converte un valore da un'unità a un'altra della stessa categoria.

    Passa i SIMBOLI tra virgolette qui sotto (maiuscole comprese), non i nomi in italiano.
    Lunghezza: "mm" = millimetri, "cm" = centimetri, "m" = metri, "km" = chilometri,
    "in" = pollici, "ft" = piedi, "mi" = miglia.
    Massa: "g" = grammi, "kg" = chilogrammi, "lb" = libbre, "oz" = once.
    Temperatura: "C" = gradi Celsius, "F" = gradi Fahrenheit, "K" = kelvin.
    Esempio: "quante miglia sono 10 chilometri" -> valore=10, da_unita="km", a_unita="mi".
    Non si convertono unità di categorie diverse (es. m in kg).
    """
    try:
        risultato = convertitore.converti_unita(valore, da_unita, a_unita)
    except ValueError as errore:
        logger.info("converti_unita rifiutata: %s", errore)
        raise ToolError(str(errore)) from errore
    return risultato


if __name__ == "__main__":
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    mcp.run(show_banner=False)
