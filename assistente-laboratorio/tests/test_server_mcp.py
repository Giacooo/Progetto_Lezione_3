"""Test del server MCP: discovery e invocazione diretta, senza modello e senza rete."""

# COSA FA QUESTO FILE
# Collega un client FastMCP al server in memoria (nessun sottoprocesso) e controlla
# che il catalogo degli strumenti sia pubblicato e che le chiamate funzionino.
# Le funzioni catalogo() e chiama() sono riusate dai test degli altri strumenti.

import asyncio

from fastmcp import Client
from fastmcp.client.client import CallToolResult
from mcp.types import Tool

from assistente import server_mcp
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
    assert set(catalogo()) == {
        "calcola", "converti_unita", "conta_giorni", "aggiungi_giorni_lavorativi",
        "cerca_corsi", "dettaglio_corso", "aggiungi_nota", "elenca_note", "elimina_nota",
    }


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


def test_discovery_giorni():
    elenco = catalogo()
    assert elenco["conta_giorni"].inputSchema["required"] == ["data_inizio", "data_fine"]
    assert elenco["aggiungi_giorni_lavorativi"].inputSchema["required"] == ["data_inizio", "giorni"]
    assert elenco["conta_giorni"].description and elenco["aggiungi_giorni_lavorativi"].description
    assert "festivita" not in elenco["conta_giorni"].inputSchema["properties"]


def test_invocazione_diretta_giorni():
    risultato = chiama("conta_giorni", {"data_inizio": "2026-12-23", "data_fine": "2026-12-28"})
    assert not risultato.is_error and "2 giorni lavorativi" in risultato.content[0].text
    risultato = chiama("aggiungi_giorni_lavorativi", {"data_inizio": "2026-12-23", "giorni": 2})
    assert not risultato.is_error and "2026-12-28" in risultato.content[0].text


def test_errore_controllato_giorni():
    risultato = chiama("conta_giorni", {"data_inizio": "03/11/2026", "data_fine": "2026-11-10"})
    assert risultato.is_error and "AAAA-MM-GG" in risultato.content[0].text


def test_discovery_catalogo():
    elenco = catalogo()
    assert elenco["cerca_corsi"].inputSchema["required"] == ["testo"]
    assert elenco["dettaglio_corso"].inputSchema["required"] == ["codice"]
    assert elenco["cerca_corsi"].description and elenco["dettaglio_corso"].description
    assert elenco["cerca_corsi"].description != elenco["dettaglio_corso"].description
    assert "corsi" not in elenco["cerca_corsi"].inputSchema["properties"]
    assert "corsi" not in elenco["dettaglio_corso"].inputSchema["properties"]
    # gemma legge la descrizione del parametro: senza, passava "Python Udine" in una ricerca
    descrizione = elenco["cerca_corsi"].inputSchema["properties"]["testo"]["description"]
    assert "UNA sola parola" in descrizione


def test_invocazione_diretta_catalogo():
    risultato = chiama("cerca_corsi", {"testo": "Python"})
    assert not risultato.is_error and "ITS-DAT-01" in risultato.content[0].text
    risultato = chiama("dettaglio_corso", {"codice": "ITS-DAT-01"})
    assert not risultato.is_error and "90 ore" in risultato.content[0].text


def test_errore_controllato_catalogo():
    risultato = chiama("dettaglio_corso", {"codice": "ITS-XX-99"})
    assert risultato.is_error and "cerca_corsi" in risultato.content[0].text
    risultato = chiama("cerca_corsi", {"testo": "  "})
    assert risultato.is_error and "testo vuoto" in risultato.content[0].text


def test_discovery_note():
    elenco = catalogo()
    assert elenco["aggiungi_nota"].inputSchema["required"] == ["testo"]
    assert elenco["elimina_nota"].inputSchema["required"] == ["id_nota"]
    assert "percorso" not in elenco["aggiungi_nota"].inputSchema["properties"]
    for nome in ("aggiungi_nota", "elenca_note", "elimina_nota"):
        assert elenco[nome].description
    assert "salva in modo permanente" in elenco["aggiungi_nota"].description
    assert "elimina definitivamente la sola nota con questo ID" in elenco["elimina_nota"].description
    assert '"Quali note ho?" -> elenca_note() senza argomenti' in elenco["elenca_note"].description
    assert elenco["aggiungi_nota"].inputSchema["properties"]["testo"]["description"]
    assert elenco["elenca_note"].inputSchema["properties"]["limite"]["description"]
    assert elenco["elimina_nota"].inputSchema["properties"]["id_nota"]["description"]


def test_invocazione_diretta_note(tmp_path, monkeypatch):
    monkeypatch.setattr(server_mcp, "PERCORSO_NOTE", tmp_path / "note.sqlite")
    risultato = chiama("aggiungi_nota", {"testo": "consegnare il report venerdì"})
    assert not risultato.is_error and risultato.content[0].text.startswith("Nota 1 creata il ")
    risultato = chiama("elenca_note", {})
    assert not risultato.is_error and "consegnare il report venerdì" in risultato.content[0].text
    risultato = chiama("elimina_nota", {"id_nota": 1})
    assert not risultato.is_error and risultato.content[0].text == "Nota 1 eliminata: consegnare il report venerdì"


def test_errore_controllato_note(tmp_path, monkeypatch):
    monkeypatch.setattr(server_mcp, "PERCORSO_NOTE", tmp_path / "note.sqlite")
    risultato = chiama("elimina_nota", {"id_nota": 99})
    assert risultato.is_error and "99" in risultato.content[0].text
    risultato = chiama("aggiungi_nota", {"testo": "   "})
    assert risultato.is_error
