"""Test del collegamento MCP: avviano davvero il server via stdio (nessuna rete)."""

from pathlib import Path

import pytest
from langchain_core.tools import StructuredTool

from assistente.collegamento_mcp import carica_strumenti_mcp, connessione_stdio, rendi_sincrono
from assistente.errori import ErroreCollegamentoMCP, ErroreStrumento

CARTELLA = Path(__file__).resolve().parent.parent


def test_discovery_dal_server_reale():
    strumenti = {s.name: s for s in carica_strumenti_mcp(connessione_stdio(CARTELLA))}
    assert "calcola" in strumenti
    assert strumenti["calcola"].metadata == {"variante": "mcp"}
    assert "espressione" in strumenti["calcola"].args  # schema venuto dal server


def test_invocazione_sincrona():
    calcola = {s.name: s for s in carica_strumenti_mcp(connessione_stdio(CARTELLA))}["calcola"]
    assert calcola.invoke({"espressione": "2+3*4"}) == "14"


def test_errore_dello_strumento():
    calcola = {s.name: s for s in carica_strumenti_mcp(connessione_stdio(CARTELLA))}["calcola"]
    with pytest.raises(ErroreStrumento, match="non ammess"):
        calcola.invoke({"espressione": "abs(1)"})


def test_server_non_avviabile():
    rotta = {**connessione_stdio(CARTELLA), "args": ["-m", "modulo_che_non_esiste"]}
    with pytest.raises(ErroreCollegamentoMCP):
        carica_strumenti_mcp(rotta)


def test_collegamento_caduto_durante_la_chiamata():
    async def cade(**_):
        raise RuntimeError("Connection closed")
    originale = StructuredTool.from_function(coroutine=cade, name="calcola", description="d",
                                             args_schema={"type": "object", "properties": {}})
    with pytest.raises(ErroreCollegamentoMCP, match="Connection closed"):
        rendi_sincrono(originale).invoke({})
