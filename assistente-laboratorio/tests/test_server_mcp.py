"""Test del server MCP: discovery e invocazione diretta, senza modello e senza rete."""

# COSA FA QUESTO FILE
# Collega un client FastMCP al server in memoria (nessun sottoprocesso) e controlla
# che il catalogo degli strumenti sia pubblicato e che le chiamate funzionino.
# Le funzioni catalogo() e chiama() sono riusate dai test degli altri strumenti.

import asyncio

from fastmcp import Client
from fastmcp.client.client import CallToolResult
from mcp.types import Tool

from assistente.server_mcp import mcp


def catalogo() -> dict[str, Tool]:
    """Chiede al server l'elenco degli strumenti (discovery) e lo indicizza per nome."""

    async def _elenca() -> list[Tool]:
        async with Client(mcp) as client:
            return await client.list_tools()

    return {strumento.name: strumento for strumento in asyncio.run(_elenca())}


def chiama(nome: str, argomenti: dict) -> CallToolResult:
    """Invoca uno strumento; un errore dello strumento non solleva, ma imposta is_error."""

    async def _chiama() -> CallToolResult:
        async with Client(mcp) as client:
            return await client.call_tool(nome, argomenti, raise_on_error=False)

    return asyncio.run(_chiama())


def test_discovery_calcola():
    strumento = catalogo()["calcola"]
    assert "espressione" in strumento.inputSchema["properties"]
    assert strumento.inputSchema["required"] == ["espressione"]
    assert strumento.description  # descrizione pubblicata dal server


def test_invocazione_diretta_calcola():
    risultato = chiama("calcola", {"espressione": "2+3*4"})
    assert not risultato.is_error and risultato.content[0].text == "14"


def test_errore_controllato_calcola():
    risultato = chiama("calcola", {"espressione": "__import__('os')"})
    assert risultato.is_error and "non ammess" in risultato.content[0].text


def test_catalogo_completo():
    assert set(catalogo()) == {"calcola", "converti_unita"}


def test_discovery_converti_unita():
    strumento = catalogo()["converti_unita"]
    assert strumento.inputSchema["required"] == ["valore", "da_unita", "a_unita"]
    assert strumento.description


def test_invocazione_diretta_converti_unita():
    risultato = chiama("converti_unita", {"valore": 10, "da_unita": "km", "a_unita": "mi"})
    assert not risultato.is_error and risultato.content[0].text == "10 km = 6.2137 mi"


def test_errore_controllato_converti_unita():
    risultato = chiama("converti_unita", {"valore": 5, "da_unita": "m", "a_unita": "kg"})
    assert risultato.is_error and "incompatibil" in risultato.content[0].text
