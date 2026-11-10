"""Collegamento al server MCP: discovery e strumenti sincroni."""

# COSA FA QUESTO FILE
# È l'unico punto del programma che usa codice asincrono. Gli strumenti prodotti da
# langchain-mcp-adapters sono solo asincroni, quindi qui li avvolgiamo in strumenti
# sincroni: ogni chiamata esegue asyncio.run(...), apre una sessione stdio nuova (un nuovo
# processo del server), chiama lo strumento e chiude. Il resto del programma resta sincrono.

import asyncio
import logging
import sys
from pathlib import Path

from langchain_core.tools import BaseTool, StructuredTool, ToolException
from langchain_mcp_adapters.tools import load_mcp_tools

from assistente.errori import ErroreCollegamentoMCP, ErroreStrumento

logger = logging.getLogger(__name__)


# Descrive come avviare il server: stesso interprete del programma, stessa cartella.
def connessione_stdio(cartella: Path) -> dict:
    return {
        "transport": "stdio",
        "command": sys.executable,
        "args": ["-m", "assistente.server_mcp"],
        "cwd": str(cartella),
    }


# Le eccezioni dei task asincroni arrivano spesso dentro un ExceptionGroup
# ("unhandled errors in a TaskGroup"): scendiamo alla prima eccezione vera.
def _eccezione_di_fondo(errore: BaseException) -> BaseException:
    while isinstance(errore, BaseExceptionGroup) and errore.exceptions:
        errore = errore.exceptions[0]
    return errore


def _motivo(errore: BaseException) -> str:
    return str(errore) or type(errore).__name__


# Il risultato di uno strumento MCP è una stringa oppure una lista di blocchi:
# ne estraiamo il testo concatenando i blocchi {"type": "text"}.
def _testo(contenuto) -> str:
    if isinstance(contenuto, str):
        return contenuto
    return "".join(
        blocco.get("text", "")
        for blocco in contenuto
        if isinstance(blocco, dict) and blocco.get("type") == "text"
    )


# Discovery: una connessione, tools/list, conversione in strumenti LangChain, chiusura.
def carica_strumenti_mcp(connessione: dict) -> list[BaseTool]:
    try:
        originali = asyncio.run(
            load_mcp_tools(None, connection=connessione, handle_tool_errors=False)
        )
    except Exception as errore:
        raise ErroreCollegamentoMCP(_motivo(_eccezione_di_fondo(errore))) from errore
    strumenti = [rendi_sincrono(s) for s in originali]
    logger.info(
        "discovery server=assistente.server_mcp tools=%s", [s.name for s in strumenti]
    )
    return strumenti


# Stessi nome, descrizione e schema dell'originale (scoperti dal server, non riscritti);
# cambia solo che si può invocare senza "await".
def rendi_sincrono(strumento: BaseTool) -> BaseTool:
    def esegui(**argomenti) -> str:
        try:
            return _testo(asyncio.run(strumento.ainvoke(argomenti)))
        except Exception as errore:
            fondo = _eccezione_di_fondo(errore)
            if isinstance(fondo, ToolException):
                raise ErroreStrumento(_motivo(fondo)) from errore
            raise ErroreCollegamentoMCP(_motivo(fondo)) from errore

    return StructuredTool.from_function(
        func=esegui,
        name=strumento.name,
        description=strumento.description,
        args_schema=strumento.args_schema,
        metadata={"variante": "mcp"},
    )
