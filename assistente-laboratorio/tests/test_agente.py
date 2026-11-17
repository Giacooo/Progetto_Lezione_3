"""Test del modulo dell'agente (lezione 6, step 6): turno senza stato, costruzione, prompt e stato."""

# L'agente non ricorda nulla tra un turno e l'altro: riceve cronologia e riassunto, esegue il
# grafo e restituisce tutto aggiornato, insieme agli strumenti usati in QUESTO turno.
# Grafo vero, modello e strumenti finti: nessun LM Studio e nessun server MCP.

from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import openai
import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from mcp.types import Prompt

from assistente.agente import Agente, ErroreTurnoAgente, controlla_modello, costruisci_agente, esegui_turno
from assistente.configurazione import carica_configurazione
from assistente.errori import ErroreCollegamentoMCP, ErroreComandoPrompt
from assistente.formato import StrumentoUsato
from assistente.grafo import costruisci_grafo
from assistente.preferenze import Preferenze, predefinite
from finti import (
    ORA_FISSA,
    PREFERENZE_PREDEFINITE,
    ModelloFinto,
    ModelloInsistente,
    revisore_sempre_coerente,
    richiesta_ora,
    router_sempre_conversazione,
    strumenti_fissi,
)

RICHIESTA = httpx.Request("POST", "http://localhost:1234/v1/chat/completions")
AMBITO = "data e ora, meteo"


# Grafo vero con modello finto a copione; router e revisore finti sempre favorevoli.
def grafo_con(risposte, max_passi=5, riassuntore=None, soglia_riassunto=20, messaggi_da_tenere=6, modello=None):
    modello = modello or ModelloFinto(risposte)
    grafo = costruisci_grafo(
        modello,
        strumenti_fissi(),
        max_passi,
        router_sempre_conversazione(),
        AMBITO,
        revisore_sempre_coerente(),
        2,
        riassuntore if riassuntore is not None else ModelloFinto([]),
        soglia_riassunto,
        messaggi_da_tenere,
        PREFERENZE_PREDEFINITE,
    )
    return grafo, modello


def giro_dell_ora(id_chiamata="c1"):
    return [
        HumanMessage("Che ore sono?"),
        richiesta_ora(id_chiamata),
        ToolMessage(ORA_FISSA, tool_call_id=id_chiamata, name="ora_corrente"),
        AIMessage("Sono le 12."),
    ]


# ---------------- Turno senza stato ----------------


def test_turno_restituisce_cronologia_e_riassunto():
    grafo, _ = grafo_con([AIMessage("ciao")])
    esito = esegui_turno(grafo, [], [HumanMessage("salve")], "")
    assert esito.risposta == "ciao"
    assert [type(m) for m in esito.cronologia] == [HumanMessage, AIMessage]
    assert [m.text for m in esito.cronologia] == ["salve", "ciao"]
    assert esito.riassunto == ""
    assert esito.strumenti_usati == []


# La cronologia ricevuta non viene toccata: l'aggiornamento è solo nell'esito.
def test_turno_non_modifica_la_cronologia_ricevuta():
    grafo, _ = grafo_con([AIMessage("seconda risposta")])
    ricevuta = [HumanMessage("prima"), AIMessage("prima risposta")]
    esito = esegui_turno(grafo, ricevuta, [HumanMessage("seconda")], "")
    assert len(ricevuta) == 2 and [m.text for m in ricevuta] == ["prima", "prima risposta"]
    assert [m.text for m in esito.cronologia] == ["prima", "prima risposta", "seconda", "seconda risposta"]


def test_strumenti_usati_del_turno():
    grafo, _ = grafo_con([richiesta_ora("c1"), AIMessage("Sono le 12")])
    esito = esegui_turno(grafo, [], [HumanMessage("Che ore sono?")], "")
    assert esito.strumenti_usati == [StrumentoUsato(nome="ora_corrente", argomenti={}, risultato=ORA_FISSA)]


# Gli strumenti già presenti nella cronologia ricevuta appartengono ai turni precedenti.
def test_strumenti_dei_turni_precedenti_non_contano():
    grafo, _ = grafo_con([AIMessage("Prego.")])
    esito = esegui_turno(grafo, giro_dell_ora(), [HumanMessage("Grazie")], "")
    assert esito.strumenti_usati == []


# Il riassunto toglie il primo turno; il vecchio giro dell'orologio (c1) resta nella cronologia
# perché il taglio non lo separa: negli strumenti usati c'è solo quello del turno in corso (c9).
def test_strumenti_usati_dopo_la_compressione():
    riassuntore = ModelloFinto([AIMessage("riassunto di prova")])
    grafo, _ = grafo_con(
        [richiesta_ora("c9"), AIMessage("Sono le 12 anche adesso.")],
        riassuntore=riassuntore,
        soglia_riassunto=4,
        messaggi_da_tenere=2,
    )
    ricevuta = [HumanMessage("Mi chiamo Luca"), AIMessage("Piacere, Luca."), *giro_dell_ora("c1")]
    esito = esegui_turno(grafo, ricevuta, [HumanMessage("E adesso?")], "")
    assert esito.riassunto == "riassunto di prova"
    assert not any(m.text == "Mi chiamo Luca" for m in esito.cronologia)
    assert any(isinstance(m, ToolMessage) and m.tool_call_id == "c1" for m in esito.cronologia)
    assert esito.strumenti_usati == [StrumentoUsato(nome="ora_corrente", argomenti={}, risultato=ORA_FISSA)]


# Ogni errore porta il suo tipo (il servizio ne ricava il codice HTTP) e il messaggio di sempre.
@pytest.mark.parametrize(
    "risposte, tipo, messaggio",
    [
        ([openai.APIConnectionError(request=RICHIESTA)], "connessione", "Connessione fallita: controllare LM Studio, URL e porta."),
        ([openai.APITimeoutError(request=RICHIESTA)], "attesa", "Attesa scaduta: controllare server, carico e tempi."),
        (
            [openai.APIStatusError("x", response=httpx.Response(404, request=RICHIESTA, text="no"), body=None)],
            "server",
            "Errore dal server: 404 no",
        ),
        ([ValueError("risposta malformata")], "inatteso", "Errore inatteso: risposta malformata (dettagli nel log)"),
        ([AIMessage("")], "risposta_vuota", "Il modello ha restituito una risposta vuota."),
    ],
)
def test_errori_classificati(risposte, tipo, messaggio):
    grafo, _ = grafo_con(risposte)
    with pytest.raises(ErroreTurnoAgente) as errore:
        esegui_turno(grafo, [], [HumanMessage("ciao")], "")
    assert errore.value.tipo == tipo
    assert str(errore.value) == messaggio


def test_limite_passi_classificato():
    grafo, _ = grafo_con([], max_passi=1, modello=ModelloInsistente())
    with pytest.raises(ErroreTurnoAgente) as errore:
        esegui_turno(grafo, [], [HumanMessage("Che ore sono?")], "")
    assert errore.value.tipo == "limite_passi"
    assert str(errore.value) == "Limite di passaggi raggiunto: riprova con una domanda diversa."


# ---------------- Costruzione dell'agente, prompt e stato ----------------

CONFIG = carica_configurazione(
    {
        "LM_BASE_URL": "http://localhost:1234/v1/",
        "LM_MODEL": "modello-di-prova",
        "FUSO_ORARIO": "Europe/Rome",
        "AMBITO_AGENTE": AMBITO,
    }
)


# Un modello finto per costruisci_agente(): si chiede solo bind_tools; router, revisore e grafo
# sono sostituiti, quindi LM Studio non viene contattato.
class ModelloDaLegare:
    nomi_legati = None

    def bind_tools(self, strumenti):
        ModelloDaLegare.nomi_legati = [s.name for s in strumenti]
        return self


# Prepara costruisci_agente() senza LM Studio né server: discovery finta (nessuno strumento MCP),
# preferenze finte, grafo "spia". Restituisce le chiamate a carica_preferenze e al grafo.
def prepara_costruzione(monkeypatch, preferenze):
    chiamate_preferenze, chiamate_grafo = [], []

    def carica_preferenze_finta(connessione, fuso_ripiego):
        chiamate_preferenze.append(fuso_ripiego)
        return preferenze

    def costruisci_grafo_spia(*argomenti):
        chiamate_grafo.append(argomenti)
        return "grafo finto"

    monkeypatch.setattr(ModelloDaLegare, "nomi_legati", None)
    monkeypatch.setattr("assistente.agente.carica_strumenti_mcp", lambda connessione: [])
    monkeypatch.setattr("assistente.agente.carica_preferenze", carica_preferenze_finta)
    monkeypatch.setattr("assistente.agente.crea_modello", lambda config: ModelloDaLegare())
    monkeypatch.setattr("assistente.agente.crea_router", lambda modello: modello)
    monkeypatch.setattr("assistente.agente.crea_revisore", lambda modello: modello)
    monkeypatch.setattr("assistente.agente.costruisci_grafo", costruisci_grafo_spia)
    return chiamate_preferenze, chiamate_grafo


def ora_dal_grafo(argomenti_grafo):
    orologio = next(s for s in argomenti_grafo[1] if s.name == "ora_corrente")
    return orologio.invoke({})


# Server giù: ci si ferma durante la discovery, PRIMA di leggere le preferenze.
def test_costruisci_agente_server_giu(monkeypatch):
    chiamate_preferenze, _ = prepara_costruzione(monkeypatch, predefinite(ZoneInfo("Europe/Rome")))

    def carica_che_fallisce(connessione):
        raise ErroreCollegamentoMCP("prova")

    monkeypatch.setattr("assistente.agente.carica_strumenti_mcp", carica_che_fallisce)
    with pytest.raises(ErroreCollegamentoMCP, match="prova"):
        costruisci_agente(CONFIG, Path("."))
    assert chiamate_preferenze == []


# Step 4: l'orologio risponde nel fuso delle preferenze; a bind_tools arrivano solo gli strumenti.
def test_costruisci_agente_usa_il_fuso_delle_preferenze(monkeypatch, tmp_path):
    preferenze = Preferenze("inglese", ZoneInfo("America/New_York"), "dettagliato")
    chiamate_preferenze, chiamate_grafo = prepara_costruzione(monkeypatch, preferenze)
    agente = costruisci_agente(CONFIG, tmp_path)
    assert agente.grafo == "grafo finto"
    assert agente.connessione["args"] == ["-m", "assistente.server_mcp"]
    assert agente.connessione["cwd"] == str(tmp_path)
    assert chiamate_preferenze == [ZoneInfo("Europe/Rome")]
    assert chiamate_grafo[0][-1] == preferenze
    assert ora_dal_grafo(chiamate_grafo[0]).endswith("(America/New_York)")
    assert ModelloDaLegare.nomi_legati == ["ora_corrente"]


def test_costruisci_agente_preferenze_non_disponibili_usa_il_fuso_di_ripiego(monkeypatch):
    preferenze = predefinite(ZoneInfo("Europe/Rome"))
    _, chiamate_grafo = prepara_costruzione(monkeypatch, preferenze)
    costruisci_agente(CONFIG, Path("."))
    assert chiamate_grafo[0][-1] == preferenze
    assert ora_dal_grafo(chiamate_grafo[0]).endswith("(Europe/Rome)")


# Una lettura HTTP finta di LM Studio per controlla_modello.
def lettura(codice=200, ids=("modello-di-prova",), eccezione=None):
    indirizzi = []

    def leggi(url, timeout):
        indirizzi.append((url, timeout))
        if eccezione is not None:
            raise eccezione
        return httpx.Response(codice, json={"data": [{"id": i} for i in ids]}, request=httpx.Request("GET", url))

    leggi.indirizzi = indirizzi
    return leggi


@pytest.mark.parametrize(
    "leggi, atteso",
    [
        (lettura(), "ok"),
        (lettura(ids=("altro",)), "modello modello-di-prova non caricato in LM Studio"),
        (lettura(eccezione=httpx.ConnectError("rifiutata")), "LM Studio non raggiungibile: controllare URL e porta"),
        (lettura(codice=500), "risposta non valida da LM Studio: 500"),
    ],
)
def test_controlla_modello(leggi, atteso):
    assert controlla_modello(CONFIG, leggi=leggi) == atteso


# L'indirizzo è LM_BASE_URL senza la "/" finale, più /models; attesa massima 5 secondi.
def test_controlla_modello_indirizzo_e_attesa():
    leggi = lettura()
    controlla_modello(CONFIG, leggi=leggi)
    assert leggi.indirizzi == [("http://localhost:1234/v1/models", 5)]


# Il servizio con LM Studio spento: l'agente c'è, il server MCP risponde, il modello no.
def test_stato_con_lm_studio_spento(monkeypatch):
    monkeypatch.setattr("assistente.agente.carica_strumenti_mcp", lambda connessione: [])
    monkeypatch.setattr("assistente.agente.httpx.get", lettura(eccezione=httpx.ConnectError("rifiutata")))
    assert Agente("grafo", {}, CONFIG).stato() == {
        "agente": "ok",
        "server_mcp": "ok",
        "modello": "LM Studio non raggiungibile: controllare URL e porta",
    }


def test_stato_con_server_mcp_giu(monkeypatch):
    def carica_che_fallisce(connessione):
        raise ErroreCollegamentoMCP("processo terminato")

    monkeypatch.setattr("assistente.agente.carica_strumenti_mcp", carica_che_fallisce)
    monkeypatch.setattr("assistente.agente.httpx.get", lettura())
    assert Agente("grafo", {}, CONFIG).stato()["server_mcp"] == "non raggiungibile: processo terminato"


def test_elenca_prompt_usa_la_connessione_dell_agente(monkeypatch):
    connessioni = []
    elenco = [Prompt(name="spiega", description="Spiega un argomento al livello richiesto.")]
    monkeypatch.setattr("assistente.agente.elenca_prompt_mcp", lambda c: connessioni.append(c) or elenco)
    assert Agente("grafo", {"cwd": "x"}, CONFIG).elenca_prompt() == elenco
    assert connessioni == [{"cwd": "x"}]


# I messaggi del prompt passano dal grafo come una domanda.
def test_richiama_prompt_passa_dal_grafo(monkeypatch):
    grafo, _ = grafo_con([AIMessage("MCP è un protocollo.")])
    richiesti = []

    def richiama_finto(connessione, nome, argomenti):
        richiesti.append((nome, argomenti))
        return [HumanMessage("Spiegami MCP")]

    monkeypatch.setattr("assistente.agente.richiama_prompt_mcp", richiama_finto)
    esito = Agente(grafo, {}, CONFIG).richiama_prompt("spiega", {"argomento": "MCP"}, [], "")
    assert richiesti == [("spiega", {"argomento": "MCP"})]
    assert [m.text for m in esito.cronologia] == ["Spiegami MCP", "MCP è un protocollo."]
    assert esito.risposta == "MCP è un protocollo."


def test_richiama_prompt_non_valido_non_chiama_il_modello(monkeypatch):
    grafo, modello = grafo_con([AIMessage("non deve arrivare")])

    def richiama_che_rifiuta(connessione, nome, argomenti):
        raise ErroreComandoPrompt("Prompt sconosciuto: pippo")

    monkeypatch.setattr("assistente.agente.richiama_prompt_mcp", richiama_che_rifiuta)
    with pytest.raises(ErroreComandoPrompt, match="pippo"):
        Agente(grafo, {}, CONFIG).richiama_prompt("pippo", {}, [], "")
    assert modello.chiamate == []
