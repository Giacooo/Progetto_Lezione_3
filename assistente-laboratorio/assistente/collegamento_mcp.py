"""Collegamento al server MCP: discovery, strumenti sincroni, preferenze e prompt."""

# COSA FA QUESTO FILE
# È l'unico punto del programma che usa codice asincrono. Gli strumenti prodotti da
# langchain-mcp-adapters sono solo asincroni, quindi qui li avvolgiamo in strumenti
# sincroni: ogni chiamata esegue asyncio.run(...), apre una sessione stdio nuova (un nuovo
# processo del server), chiama lo strumento e chiude. Il resto del programma resta sincrono.
# Qui si legge anche, una volta a inizio sessione, la resource delle preferenze
# (utente://preferenze), con il ripiego sui valori predefiniti se non è disponibile.
# Infine (step 5) qui si elencano e si richiamano i prompt del server, su comando dell'utente.

import asyncio
import json
import logging
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

from langchain_core.messages import BaseMessage
from langchain_core.tools import BaseTool, StructuredTool, ToolException
from langchain_mcp_adapters.prompts import load_mcp_prompt
from langchain_mcp_adapters.sessions import create_session
from langchain_mcp_adapters.tools import load_mcp_tools
from mcp.types import Prompt

from assistente.errori import (
    ErroreCollegamentoMCP,
    ErroreComandoPrompt,
    ErrorePreferenze,
    ErroreStrumento,
)
from assistente.preferenze import Preferenze, leggi_preferenze_da_testo, predefinite
from assistente.prompt_mcp import controlla_argomenti

logger = logging.getLogger(__name__)

URI_PREFERENZE = "utente://preferenze"


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


# Legge la resource delle preferenze (step 4): una sessione stdio, resources/read, chiusura.
# La resource la sceglie e la legge l'HOST: il modello non la vede e non è tra gli strumenti.
# Restituisce il testo così com'è (non lo controlla: lo fa preferenze.py).
def leggi_preferenze_mcp(connessione: dict) -> str:
    async def _leggi() -> str:
        async with create_session(connessione) as sessione:
            await sessione.initialize()  # la sessione va inizializzata prima di ogni richiesta
            risposta = await sessione.read_resource(URI_PREFERENZE)
        return "".join(getattr(contenuto, "text", "") or "" for contenuto in risposta.contents)

    try:
        return asyncio.run(_leggi())
    except Exception as errore:
        raise ErroreCollegamentoMCP(_motivo(_eccezione_di_fondo(errore))) from errore


# Legge le preferenze e le controlla. Se la resource non c'è o non è valida NON si ferma:
# usa i valori predefiniti (con il fuso di ripiego, quello di FUSO_ORARIO) e lo scrive nei log.
# Va chiamata una sola volta, a inizio sessione, prima della prima domanda.
def carica_preferenze(connessione: dict, fuso_ripiego: ZoneInfo) -> Preferenze:
    try:
        preferenze = leggi_preferenze_da_testo(leggi_preferenze_mcp(connessione))
    except (ErroreCollegamentoMCP, ErrorePreferenze) as errore:
        preferenze = predefinite(fuso_ripiego)
        logger.warning(
            "preferenze non disponibili (%s): valori predefiniti lingua=%s fuso=%s stile=%s",
            errore, preferenze.lingua, preferenze.fuso.key, preferenze.stile,
        )
        return preferenze
    logger.info(
        "preferenze lette uri=%s lingua=%s fuso=%s stile=%s",
        URI_PREFERENZE, preferenze.lingua, preferenze.fuso.key, preferenze.stile,
    )
    return preferenze


# ---------------- Prompt (step 5) ----------------
# Il prompt è la terza primitiva MCP: un modello di istruzioni salvato sul server che
# richiama l'UTENTE con un comando (/prompts, /prompt). Non è uno strumento: il modello non
# lo vede e non può chiamarlo. L'elenco (prompts/list) si legge a ogni comando, con una
# sessione stdio nuova, come per strumenti e preferenze: nessuna copia tenuta in memoria.

MAX_CARATTERI_LOG = 500  # testo di ogni messaggio ottenuto, nel log


# Elenco dei prompt: una sessione, prompts/list, chiusura.
def elenca_prompt_mcp(connessione: dict) -> list[Prompt]:
    async def _elenca() -> list[Prompt]:
        async with create_session(connessione) as sessione:
            await sessione.initialize()
            return await _elenco_prompt(sessione)

    try:
        return asyncio.run(_elenca())
    except Exception as errore:
        raise ErroreCollegamentoMCP(_motivo(_eccezione_di_fondo(errore))) from errore


async def _elenco_prompt(sessione) -> list[Prompt]:
    elenco = (await sessione.list_prompts()).prompts
    logger.info("prompts/list prompts=%s", [p.name for p in elenco])
    return elenco


# Ruolo MCP del messaggio ottenuto, per il log: HumanMessage → user, AIMessage → assistant.
def _ruolo(messaggio: BaseMessage) -> str:
    return {"human": "user", "ai": "assistant"}.get(messaggio.type, messaggio.type)


def _testo_per_log(messaggio: BaseMessage) -> str:
    return f"[{_ruolo(messaggio)}] {str(messaggio.content)[:MAX_CARATTERI_LOG]}"


# Richiamo di un prompt: UNA sola sessione che, nell'ordine,
#   1. legge l'elenco dei prompt (prompts/list);
#   2. controlla nome e argomenti rispetto a quell'elenco (prompt_mcp.controlla_argomenti);
#   3. solo se il controllo passa, chiede il prompt al server (prompts/get) e lo converte in
#      messaggi LangChain (HumanMessage per il ruolo user).
# Se il controllo fallisce, prompts/get non parte e il modello non è coinvolto: l'errore
# (ErroreComandoPrompt) sale fino al terminale, che lo stampa, e la chat continua.
def richiama_prompt_mcp(
    connessione: dict, nome: str, argomenti: dict[str, str]
) -> list[BaseMessage]:
    async def _richiama() -> list[BaseMessage]:
        async with create_session(connessione) as sessione:
            await sessione.initialize()
            elenco = await _elenco_prompt(sessione)
            controlla_argomenti(elenco, nome, argomenti)
            logger.info(
                "prompt richiamato nome=%s argomenti=%s",
                nome, json.dumps(argomenti, ensure_ascii=False),
            )
            messaggi = await load_mcp_prompt(sessione, nome, arguments=argomenti)
        logger.info(
            "prompt messaggi ottenuti numero=%d %s",
            len(messaggi), " | ".join(_testo_per_log(m) for m in messaggi),
        )
        return messaggi

    try:
        return asyncio.run(_richiama())
    except Exception as errore:
        # L'errore del controllo, sollevato dentro la sessione, può arrivare dentro un
        # ExceptionGroup: lo si cerca "sul fondo" e lo si rilancia così com'è.
        fondo = _eccezione_di_fondo(errore)
        if isinstance(fondo, ErroreComandoPrompt):
            logger.warning("prompt rifiutato nome=%s motivo=%s", nome, fondo)
            raise fondo from None
        raise ErroreCollegamentoMCP(_motivo(fondo)) from errore
