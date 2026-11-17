"""Test del collegamento MCP: avviano davvero il server via stdio (nessuna rete)."""

import codecs
import logging
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from langchain_core.messages import HumanMessage
from langchain_core.tools import StructuredTool

from assistente.collegamento_mcp import (
    carica_preferenze,
    carica_strumenti_mcp,
    connessione_stdio,
    elenca_prompt_mcp,
    leggi_preferenze_mcp,
    rendi_sincrono,
    richiama_prompt_mcp,
)
from assistente.errori import ErroreCollegamentoMCP, ErroreComandoPrompt, ErroreStrumento
from assistente.preferenze import Preferenze, predefinite

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


# ---------------- Lettura della resource utente://preferenze (step 4) ----------------
# Il server parte davvero in sottoprocesso, con la cartella di lavoro in una cartella temporanea
# dove si scrive (o no) archivio/preferenze.json: il file dell'utente non si tocca.
JSON_VALIDO = '{"lingua": "inglese", "fuso_orario": "America/New_York", "stile": "dettagliato"}'
ROMA = ZoneInfo("Europe/Rome")


def cartella_con(tmp_path, contenuto: bytes | str | None):
    if contenuto is not None:
        (tmp_path / "archivio").mkdir()
        dati = contenuto if isinstance(contenuto, bytes) else contenuto.encode("utf-8")
        (tmp_path / "archivio" / "preferenze.json").write_bytes(dati)
    # cwd è la cartella temporanea (per il file delle preferenze): il pacchetto si trova con PYTHONPATH.
    return {**connessione_stdio(tmp_path), "env": {"PYTHONPATH": str(CARTELLA)}}


def righe_del_log(caplog):
    return [r.getMessage() for r in caplog.records if r.name == "assistente.collegamento_mcp"]


def test_leggi_preferenze_mcp_restituisce_il_testo(tmp_path):
    assert leggi_preferenze_mcp(cartella_con(tmp_path, JSON_VALIDO)) == JSON_VALIDO


def test_leggi_preferenze_mcp_file_assente(tmp_path):
    with pytest.raises(ErroreCollegamentoMCP):
        leggi_preferenze_mcp(cartella_con(tmp_path, None))


def test_carica_preferenze_valide(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="assistente")
    preferenze = carica_preferenze(cartella_con(tmp_path, JSON_VALIDO), ROMA)
    assert preferenze == Preferenze("inglese", ZoneInfo("America/New_York"), "dettagliato")
    assert righe_del_log(caplog) == [
        "preferenze lette uri=utente://preferenze lingua=inglese fuso=America/New_York stile=dettagliato"
    ]
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


def test_carica_preferenze_con_bom(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="assistente")
    preferenze = carica_preferenze(cartella_con(tmp_path, codecs.BOM_UTF8 + JSON_VALIDO.encode("utf-8")), ROMA)
    assert preferenze.lingua == "inglese"
    assert righe_del_log(caplog)[0].startswith("preferenze lette ")


PREDEFINITE_ROMA = "valori predefiniti lingua=italiano fuso=Europe/Rome stile=sintetico"


def test_carica_preferenze_file_assente(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="assistente")
    assert carica_preferenze(cartella_con(tmp_path, None), ROMA) == predefinite(ROMA)
    (riga,) = righe_del_log(caplog)
    assert riga.startswith("preferenze non disponibili (") and riga.endswith("): " + PREDEFINITE_ROMA)
    assert caplog.records[-1].levelno == logging.WARNING


@pytest.mark.parametrize(
    ("contenuto", "motivo"),
    [
        ("", "JSON non valido"),
        ("   " + chr(10), "JSON non valido"),
        ('{"lingua": "inglese", "fuso_orario": "America/New_York", "stile": "lungo"}', "stile deve essere"),
        ('{"lingua": "inglese"}', "manca la chiave"),
    ],
)
def test_carica_preferenze_file_non_valido(tmp_path, caplog, contenuto, motivo):
    caplog.set_level(logging.INFO, logger="assistente")
    assert carica_preferenze(cartella_con(tmp_path, contenuto), ROMA) == predefinite(ROMA)
    (riga,) = righe_del_log(caplog)
    assert motivo in riga and riga.endswith("): " + PREDEFINITE_ROMA)


def test_carica_preferenze_server_non_avviabile(caplog):
    caplog.set_level(logging.INFO, logger="assistente")
    rotta = {**connessione_stdio(CARTELLA), "args": ["-m", "modulo_che_non_esiste"]}
    assert carica_preferenze(rotta, ROMA) == predefinite(ROMA)
    assert righe_del_log(caplog)[0].startswith("preferenze non disponibili (")


# Punto 03 del PDF: la resource non è tra gli strumenti passati a bind_tools.
def test_la_discovery_non_include_le_preferenze():
    nomi = {s.name for s in carica_strumenti_mcp(connessione_stdio(CARTELLA))}
    assert "preferenze" not in nomi and len(nomi) == 10


# ---------------- Elenco e richiamo dei prompt (step 5) ----------------
# Il server parte davvero in sottoprocesso; il modello non c'entra.
def test_elenca_prompt_mcp(caplog):
    caplog.set_level(logging.INFO, logger="assistente")
    elenco = elenca_prompt_mcp(connessione_stdio(CARTELLA))
    assert {p.name for p in elenco} == {"spiega", "riassumi_conversazione"}
    (riga,) = [r for r in righe_del_log(caplog) if r.startswith("prompts/list prompts=")]
    assert "'spiega'" in riga and "'riassumi_conversazione'" in riga


def test_richiama_prompt_mcp(caplog):
    caplog.set_level(logging.INFO, logger="assistente")
    messaggi = richiama_prompt_mcp(
        connessione_stdio(CARTELLA),
        "spiega",
        {"argomento": "Model Context Protocol", "livello": "base"},
    )
    (messaggio,) = messaggi
    assert isinstance(messaggio, HumanMessage)
    assert messaggio.content.startswith("Spiegami «Model Context Protocol» a livello base.")
    righe = righe_del_log(caplog)
    assert len(righe) == 3
    assert righe[0].startswith("prompts/list prompts=")
    assert righe[1] == (
        'prompt richiamato nome=spiega argomenti={"argomento": "Model Context Protocol", "livello": "base"}'
    )
    assert righe[2].startswith("prompt messaggi ottenuti numero=1 [user] Spiegami «Model Context Protocol»")


# Punto 04 del PDF: con un controllo fallito non parte prompts/get (né il modello).
def test_richiamo_con_argomento_mancante_non_chiede_il_prompt(monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger="assistente")
    chiamate = []

    async def spia(*args, **kwargs):
        chiamate.append((args, kwargs))
        return []

    monkeypatch.setattr("assistente.collegamento_mcp.load_mcp_prompt", spia)
    with pytest.raises(ErroreComandoPrompt, match="obbligatori mancanti"):
        richiama_prompt_mcp(connessione_stdio(CARTELLA), "spiega", {"livello": "base"})
    assert chiamate == []
    avvisi = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert [r.getMessage() for r in avvisi] == [
        "prompt rifiutato nome=spiega motivo=Argomenti obbligatori mancanti per 'spiega': argomento."
    ]
    assert not [r for r in righe_del_log(caplog) if r.startswith("prompt richiamato")]


def test_richiamo_prompt_sconosciuto():
    with pytest.raises(ErroreComandoPrompt, match="Prompt sconosciuto: 'x'"):
        richiama_prompt_mcp(connessione_stdio(CARTELLA), "x", {})


def test_elenco_e_richiamo_server_non_avviabile():
    rotta = {**connessione_stdio(CARTELLA), "args": ["-m", "modulo_che_non_esiste"]}
    with pytest.raises(ErroreCollegamentoMCP):
        elenca_prompt_mcp(rotta)
    with pytest.raises(ErroreCollegamentoMCP):
        richiama_prompt_mcp(rotta, "spiega", {"argomento": "MCP"})


def test_log_messaggi_ottenuti_troncato(caplog):
    caplog.set_level(logging.INFO, logger="assistente")
    richiama_prompt_mcp(connessione_stdio(CARTELLA), "spiega", {"argomento": "a" * 600})
    (riga,) = [r for r in righe_del_log(caplog) if r.startswith("prompt messaggi ottenuti")]
    prefisso = "prompt messaggi ottenuti numero=1 [user] "
    assert riga.startswith(prefisso)
    assert len(riga) - len(prefisso) <= 500


# I prompt non sono strumenti: non arrivano a bind_tools.
def test_la_discovery_non_include_i_prompt():
    nomi = {s.name for s in carica_strumenti_mcp(connessione_stdio(CARTELLA))}
    assert "spiega" not in nomi and "riassumi_conversazione" not in nomi and len(nomi) == 10
