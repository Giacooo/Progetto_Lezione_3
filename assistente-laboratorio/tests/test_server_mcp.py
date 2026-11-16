"""Test del server MCP: discovery e invocazione diretta, senza modello e senza rete."""

# COSA FA QUESTO FILE
# Collega un client FastMCP al server in memoria (nessun sottoprocesso) e controlla
# che il catalogo degli strumenti sia pubblicato e che le chiamate funzionino.
# Le funzioni catalogo() e chiama() sono riusate dai test degli altri strumenti.

import asyncio
import codecs
import json

import pytest
from fastmcp import Client
from fastmcp.client.client import CallToolResult
from mcp.types import GetPromptResult, Prompt, Tool

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
        "meteo_citta",
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


def test_discovery_meteo():
    strumento = catalogo()["meteo_citta"]
    assert strumento.inputSchema["required"] == ["citta"]
    assert strumento.inputSchema["properties"]["citta"]["description"]
    assert '"Che tempo fa a Pordenone?" -> citta="Pordenone"' in strumento.description


def test_errore_controllato_meteo():
    # la città vuota è rifiutata prima di qualunque richiesta: nessuna rete
    risultato = chiama("meteo_citta", {"citta": "  "})
    assert risultato.is_error and "città non indicata" in risultato.content[0].text


# ---------------- Resource utente://preferenze (step 4) ----------------
URI_PREFERENZE = "utente://preferenze"
JSON_PREFERENZE = '{"lingua": "inglese", "fuso_orario": "America/New_York", "stile": "dettagliato"}'


def risorse():
    async def _elenca():
        async with Client(mcp) as client:
            return await client.list_resources()

    return asyncio.run(_elenca())


def leggi_risorsa(uri: str):
    async def _leggi():
        async with Client(mcp) as client:
            return await client.read_resource(uri)

    return asyncio.run(_leggi())


def test_discovery_preferenze():
    trovate = [r for r in risorse() if str(r.uri) == URI_PREFERENZE]
    assert len(trovate) == 1
    assert trovate[0].name == "preferenze"
    assert trovate[0].mimeType == "application/json"


# La resource la legge l'host: non deve essere pubblicata come strumento (punto 03 del PDF).
def test_preferenze_non_sono_un_tool():
    assert "preferenze" not in catalogo()
    assert URI_PREFERENZE not in catalogo()


def test_lettura_preferenze(tmp_path, monkeypatch):
    percorso = tmp_path / "preferenze.json"
    percorso.write_text(JSON_PREFERENZE, encoding="utf-8")
    monkeypatch.setattr(server_mcp, "PERCORSO_PREFERENZE", percorso)
    assert leggi_risorsa(URI_PREFERENZE)[0].text == JSON_PREFERENZE


# Un file scritto da PowerShell 5.1 comincia con il BOM: va letto lo stesso.
def test_lettura_preferenze_con_bom(tmp_path, monkeypatch):
    percorso = tmp_path / "preferenze.json"
    percorso.write_bytes(codecs.BOM_UTF8 + JSON_PREFERENZE.encode("utf-8"))
    monkeypatch.setattr(server_mcp, "PERCORSO_PREFERENZE", percorso)
    testo = leggi_risorsa(URI_PREFERENZE)[0].text
    assert not testo.startswith(codecs.BOM_UTF8.decode("utf-8"))
    assert json.loads(testo)["lingua"] == "inglese"


def test_lettura_preferenze_file_assente(tmp_path, monkeypatch):
    monkeypatch.setattr(server_mcp, "PERCORSO_PREFERENZE", tmp_path / "manca.json")
    with pytest.raises(Exception):
        leggi_risorsa(URI_PREFERENZE)


# ---------------- PROMPT (lezione 6, step 5) ----------------
# I prompt li sceglie l'UTENTE (con /prompt nella CLI): il server pubblica l'elenco
# (prompts/list) e, su richiesta, il testo compilato con gli argomenti (prompts/get).


def elenco_prompt() -> dict[str, Prompt]:
    """Chiede al server l'elenco dei prompt e lo indicizza per nome."""

    async def _elenca() -> list[Prompt]:
        async with Client(mcp) as client:
            return await client.list_prompts()

    return {prompt.name: prompt for prompt in asyncio.run(_elenca())}


def prendi_prompt(nome: str, argomenti: dict[str, str]) -> GetPromptResult:
    """Chiede al server il prompt compilato con gli argomenti."""

    async def _prendi() -> GetPromptResult:
        async with Client(mcp) as client:
            return await client.get_prompt(nome, argomenti)

    return asyncio.run(_prendi())


# (nome, obbligatorio, descrizione) di ogni argomento, così come li pubblica il server.
def argomenti_di(prompt: Prompt) -> list[tuple[str, bool, str]]:
    return [(a.name, bool(a.required), a.description) for a in prompt.arguments or []]


def messaggio_unico(risultato: GetPromptResult) -> str:
    """Il prompt deve dare UN solo messaggio, con ruolo "user": ne restituisce il testo."""
    (messaggio,) = risultato.messages
    assert messaggio.role == "user"
    return messaggio.content.text


def test_discovery_prompt():
    prompt = elenco_prompt()
    assert set(prompt) == {"spiega", "riassumi_conversazione"}
    assert prompt["spiega"].description == "Spiega un argomento al livello richiesto."
    assert argomenti_di(prompt["spiega"]) == [
        ("argomento", True, "concetto da spiegare"),
        ("livello", False, "base, intermedio o avanzato"),
    ]
    assert prompt["riassumi_conversazione"].description == (
        "Riassume i turni della conversazione della sessione corrente."
    )
    assert argomenti_di(prompt["riassumi_conversazione"]) == [("stile", False, "sintetico o dettagliato")]


def test_prompt_spiega():
    risultato = prendi_prompt("spiega", {"argomento": "Model Context Protocol", "livello": "avanzato"})
    assert messaggio_unico(risultato).startswith("Spiegami «Model Context Protocol» a livello avanzato.")


def test_prompt_spiega_livello_predefinito():
    assert "a livello base." in messaggio_unico(prendi_prompt("spiega", {"argomento": "MCP"}))


def test_prompt_riassumi_conversazione():
    assert messaggio_unico(prendi_prompt("riassumi_conversazione", {"stile": "dettagliato"})) == (
        "Riassumi in stile dettagliato i turni di questa conversazione (domande e risposte), "
        "senza aggiungere informazioni nuove."
    )
    assert "in stile sintetico " in messaggio_unico(prendi_prompt("riassumi_conversazione", {}))


# Il testo descrive SOLO il livello richiesto: con la descrizione di tutti e tre, nelle prove reali
# gemma-4-e2b spiegava l'argomento a tutti e tre i livelli (motivo del revisore, 10 volte su 10).
@pytest.mark.parametrize(
    ("livello", "atteso"),
    [
        ("base", "Spiegami «MCP» a livello base. Usa parole semplici, senza gergo tecnico, con un esempio concreto."),
        ("intermedio", "Spiegami «MCP» a livello intermedio. Puoi usare i termini tecnici, spiegandoli."),
        ("avanzato", "Spiegami «MCP» a livello avanzato. Entra nei dettagli tecnici."),
    ],
)
def test_prompt_spiega_descrive_solo_il_livello_richiesto(livello, atteso):
    assert messaggio_unico(prendi_prompt("spiega", {"argomento": "MCP", "livello": livello})) == atteso


# Il server NON controlla i valori (decisione dell'utente): un livello fuori elenco passa così com'è,
# senza descrizione (non ce n'è una da dare).
def test_prompt_valore_non_controllato():
    assert messaggio_unico(prendi_prompt("spiega", {"argomento": "MCP", "livello": "pippo"})) == (
        "Spiegami «MCP» a livello pippo."
    )


# I prompt non sono strumenti: il modello non li vede in tools/list (anti-obiettivo del PDF).
def test_prompt_non_sono_tool():
    strumenti = catalogo()
    assert "spiega" not in strumenti
    assert "riassumi_conversazione" not in strumenti
