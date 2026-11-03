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

from assistente.strumenti_mcp import calcolatrice

logger = logging.getLogger(__name__)

mcp = FastMCP("Strumenti del laboratorio")


@mcp.tool
def calcola(espressione: str) -> str:
    """Valuta un'espressione aritmetica con numeri, + - * / // % ** e parentesi.

    Usala per ogni calcolo, anche semplice, invece di calcolare a mente.
    """
    try:
        risultato = calcolatrice.calcola(espressione)
    except ValueError as errore:
        logger.info("calcola rifiutata: %s", errore)
        raise ToolError(str(errore)) from errore
    return risultato


if __name__ == "__main__":
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    mcp.run(show_banner=False)
