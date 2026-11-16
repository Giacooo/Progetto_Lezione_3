"""Test dell'API del back-end (lezione 6, step 7)."""

# COSA PROVA QUESTO FILE
# L'API FastAPI del back-end con TestClient, l'archivio in memoria (ArchivioMemoria) e un
# agente simulato (AgenteFinto): niente database, niente rete, niente modello.
# Evidenze del PDF provate qui: le cinque operazioni (creare, elencare, leggere, eliminare una
# chat, inviare un messaggio), l'OpenAPI generata, l'errore chiaro quando l'agente non è
# raggiungibile (con la chat lasciata com'era) e i test con l'agente simulato.

import json
import logging

import pytest
from fastapi.testclient import TestClient
from finti_backend import ArchivioGiu, ArchivioMemoria

from backend.agente_remoto import (
    FUORI_TEMPO,
    NON_RAGGIUNGIBILE,
    NON_VALIDA,
    ErroreAgente,
    RispostaAgente,
)
from backend.app import LUNGHEZZA_TITOLO, TITOLO_PREDEFINITO, crea_app, titolo_da_domanda

STRUMENTI = [{"nome": "calcola", "argomenti": {"espressione": "45 / 9"}, "risultato": "5"}]


def risposta_agente(testo="Fa 5.", strumenti=STRUMENTI, cronologia=None, riassunto=""):
    cronologia = cronologia if cronologia is not None else [
        {"ruolo": "utente", "testo": "Quanto fa 45 diviso 9?"}, {"ruolo": "assistente", "testo": testo}
    ]
    return RispostaAgente(testo, strumenti, cronologia, riassunto)


class AgenteFinto:
    """Restituisce le risposte programmate (o lancia l'ErroreAgente) e registra le chiamate."""

    def __init__(self, *risposte):
        self.risposte = list(risposte)
        self.chiamate = []

    def invia(self, messaggio, cronologia, riassunto):
        self.chiamate.append({"messaggio": messaggio, "cronologia": cronologia, "riassunto": riassunto})
        esito = self.risposte.pop(0)
        if isinstance(esito, Exception):
            raise esito
        return esito


def cliente_con(*risposte, archivio=None):
    archivio = archivio if archivio is not None else ArchivioMemoria()
    agente = AgenteFinto(*risposte)
    return TestClient(crea_app(archivio, agente)), archivio, agente


def righe(caplog, livello=logging.INFO):
    return [r.getMessage() for r in caplog.records if r.levelno == livello]


# ---------------- Creare ----------------


def test_crea_201_con_id(caplog):
    cliente, archivio, _ = cliente_con()
    with caplog.at_level(logging.INFO, logger="backend"):
        r = cliente.post("/chat", json={"titolo": "  Compiti di fisica  "})
    assert r.status_code == 201
    corpo = r.json()
    assert corpo["id"] == 1
    assert corpo["titolo"] == "Compiti di fisica"
    assert corpo["creata"].endswith(("Z", "+00:00"))
    assert archivio.leggi(1)[0].titolo == "Compiti di fisica"
    assert "richiesta operazione=crea chat=-" in righe(caplog)


@pytest.mark.parametrize("corpo", [None, {}, {"titolo": None}, {"titolo": "   "}],
                         ids=["senza corpo", "vuoto", "titolo null", "solo spazi"])
def test_crea_senza_titolo(corpo):
    cliente, archivio, _ = cliente_con()
    r = cliente.post("/chat", json=corpo) if corpo is not None else cliente.post("/chat")
    assert r.status_code == 201
    assert r.json()["titolo"] == TITOLO_PREDEFINITO
    assert archivio.leggi(r.json()["id"])[0].titolo is None


# ---------------- Elencare ----------------


def test_elenca(caplog):
    cliente, _, _ = cliente_con(risposta_agente())
    prima = cliente.post("/chat", json={"titolo": "prima"}).json()
    seconda = cliente.post("/chat").json()
    elenco = cliente.get("/chat").json()
    assert [v["id"] for v in elenco] == [seconda["id"], prima["id"]]
    assert elenco[0] == {"id": seconda["id"], "titolo": TITOLO_PREDEFINITO, "ultimo_messaggio": None,
                         "creata": seconda["creata"]}
    inviato = cliente.post(f"/chat/{prima['id']}/messaggi", json={"messaggio": "Quanto fa 45 diviso 9?"}).json()
    with caplog.at_level(logging.INFO, logger="backend"):
        elenco = cliente.get("/chat").json()
    # La chat con il messaggio più recente sale in cima, con la data dell'ultimo messaggio.
    assert [v["id"] for v in elenco] == [prima["id"], seconda["id"]]
    assert elenco[0]["ultimo_messaggio"] == inviato["risposta"]["data"]
    assert "richiesta operazione=elenca chat=-" in righe(caplog)


# ---------------- Leggere ----------------


def test_leggi_in_ordine(caplog):
    cliente, _, _ = cliente_con(risposta_agente("Fa 5."), risposta_agente("Fa 15.", strumenti=[]))
    chat = cliente.post("/chat", json={"titolo": "conti"}).json()
    cliente.post(f"/chat/{chat['id']}/messaggi", json={"messaggio": "Quanto fa 45 diviso 9?"})
    cliente.post(f"/chat/{chat['id']}/messaggi", json={"messaggio": "E se aggiungo 10?"})
    with caplog.at_level(logging.INFO, logger="backend"):
        r = cliente.get(f"/chat/{chat['id']}")
    assert r.status_code == 200
    corpo = r.json()
    assert (corpo["id"], corpo["titolo"], corpo["creata"]) == (chat["id"], "conti", chat["creata"])
    assert [(m["ruolo"], m["testo"]) for m in corpo["messaggi"]] == [
        ("utente", "Quanto fa 45 diviso 9?"), ("assistente", "Fa 5."),
        ("utente", "E se aggiungo 10?"), ("assistente", "Fa 15."),
    ]
    assert corpo["messaggi"][1]["strumenti_usati"] == STRUMENTI
    assert corpo["messaggi"][0]["strumenti_usati"] == []
    date = [m["data"] for m in corpo["messaggi"]]
    assert date == sorted(date)
    assert f"richiesta operazione=leggi chat={chat['id']}" in righe(caplog)


def test_leggi_404(caplog):
    cliente, _, _ = cliente_con()
    with caplog.at_level(logging.INFO, logger="backend"):
        r = cliente.get("/chat/42")
    assert r.status_code == 404
    assert r.json() == {"errore": "Chat non trovata."}
    assert "errore operazione=leggi codice=404 messaggio=Chat non trovata." in righe(caplog, logging.WARNING)


# ---------------- Eliminare ----------------


def test_elimina_204_poi_404(caplog):
    cliente, archivio, _ = cliente_con(risposta_agente())
    chat = cliente.post("/chat").json()
    cliente.post(f"/chat/{chat['id']}/messaggi", json={"messaggio": "Quanto fa 45 diviso 9?"})
    with caplog.at_level(logging.INFO, logger="backend"):
        r = cliente.delete(f"/chat/{chat['id']}")
    assert r.status_code == 204
    assert r.content == b""
    assert archivio.leggi(chat["id"]) is None
    assert cliente.get(f"/chat/{chat['id']}").status_code == 404
    assert cliente.delete(f"/chat/{chat['id']}").json() == {"errore": "Chat non trovata."}
    assert f"richiesta operazione=elimina chat={chat['id']}" in righe(caplog)


# ---------------- Inviare un messaggio ----------------


def test_messaggio_salva_e_restituisce(caplog):
    cliente, archivio, agente = cliente_con(risposta_agente())
    chat = cliente.post("/chat").json()
    with caplog.at_level(logging.INFO, logger="backend"):
        r = cliente.post(f"/chat/{chat['id']}/messaggi", json={"messaggio": "Quanto fa 45 diviso 9?"})
    assert r.status_code == 200
    corpo = r.json()
    assert (corpo["domanda"]["ruolo"], corpo["domanda"]["testo"]) == ("utente", "Quanto fa 45 diviso 9?")
    assert corpo["domanda"]["strumenti_usati"] == []
    assert (corpo["risposta"]["ruolo"], corpo["risposta"]["testo"]) == ("assistente", "Fa 5.")
    assert corpo["risposta"]["strumenti_usati"] == STRUMENTI
    assert corpo["domanda"]["data"] <= corpo["risposta"]["data"]
    # Salvati davvero: la lettura restituisce gli stessi due messaggi.
    assert cliente.get(f"/chat/{chat['id']}").json()["messaggi"] == [corpo["domanda"], corpo["risposta"]]
    assert agente.chiamate == [{"messaggio": "Quanto fa 45 diviso 9?", "cronologia": [], "riassunto": ""}]
    log = righe(caplog)
    assert f"richiesta operazione=messaggio chat={chat['id']}" in log
    assert f"agente chat={chat['id']} strumenti=['calcola']" in log


# La memoria dell'agente (cronologia e riassunto) restituita a un turno torna all'agente al turno dopo.
def test_memoria_rimandata_al_turno_dopo():
    memoria = [{"ruolo": "utente", "testo": "Mi chiamo Carlo"}, {"ruolo": "assistente", "testo": "Ciao Carlo!"}]
    cliente, _, agente = cliente_con(
        risposta_agente("Ciao Carlo!", strumenti=[], cronologia=memoria, riassunto="L'utente si chiama Carlo."),
        risposta_agente("Ti chiami Carlo.", strumenti=[]),
    )
    chat = cliente.post("/chat").json()
    cliente.post(f"/chat/{chat['id']}/messaggi", json={"messaggio": "Mi chiamo Carlo"})
    cliente.post(f"/chat/{chat['id']}/messaggi", json={"messaggio": "Come mi chiamo?"})
    assert agente.chiamate[1] == {"messaggio": "Come mi chiamo?", "cronologia": memoria,
                                  "riassunto": "L'utente si chiama Carlo."}


def test_titolo_automatico():
    cliente, _, _ = cliente_con(risposta_agente(), risposta_agente())
    chat = cliente.post("/chat").json()
    cliente.post(f"/chat/{chat['id']}/messaggi", json={"messaggio": "Quanto fa 45 diviso 9?"})
    cliente.post(f"/chat/{chat['id']}/messaggi", json={"messaggio": "Un'altra domanda"})
    assert cliente.get(f"/chat/{chat['id']}").json()["titolo"] == "Quanto fa 45 diviso 9?"
    assert cliente.get("/chat").json()[0]["titolo"] == "Quanto fa 45 diviso 9?"


def test_titolo_automatico_lungo():
    domanda = "Spiegami bene\ncome funziona la fotosintesi nelle piante verdi 😀 adesso"
    assert len(domanda) > LUNGHEZZA_TITOLO
    cliente, _, _ = cliente_con(risposta_agente())
    chat = cliente.post("/chat").json()
    cliente.post(f"/chat/{chat['id']}/messaggi", json={"messaggio": domanda})
    titolo = cliente.get(f"/chat/{chat['id']}").json()["titolo"]
    assert titolo == "Spiegami bene come funziona la fotosintesi nelle p…"
    assert len(titolo) == LUNGHEZZA_TITOLO + 1
    assert "\n" not in titolo


def test_titolo_da_domanda():
    assert titolo_da_domanda("  Ciao\r\n  mondo  ") == "Ciao mondo"
    assert titolo_da_domanda("x" * LUNGHEZZA_TITOLO) == "x" * LUNGHEZZA_TITOLO
    assert titolo_da_domanda("x" * (LUNGHEZZA_TITOLO + 1)) == "x" * LUNGHEZZA_TITOLO + "…"


def test_titolo_dato_non_cambia():
    cliente, _, _ = cliente_con(risposta_agente())
    chat = cliente.post("/chat", json={"titolo": "Il mio titolo"}).json()
    cliente.post(f"/chat/{chat['id']}/messaggi", json={"messaggio": "Quanto fa 45 diviso 9?"})
    assert cliente.get(f"/chat/{chat['id']}").json()["titolo"] == "Il mio titolo"


# Evidenza del PDF: agente non raggiungibile → errore chiaro, e la chat resta com'era (decisione A).
@pytest.mark.parametrize("errore", [
    ErroreAgente(503, NON_RAGGIUNGIBILE),
    ErroreAgente(504, FUORI_TEMPO),
    ErroreAgente(502, "Errore dell'agente: Connessione fallita: LM Studio. La domanda non è stata salvata."),
    ErroreAgente(502, NON_VALIDA),
], ids=["503 non raggiungibile", "504 fuori tempo", "502 errore", "502 forma"])
def test_errori_agente_chat_invariata(errore, caplog):
    memoria = [{"ruolo": "utente", "testo": "Ciao"}, {"ruolo": "assistente", "testo": "Ciao!"}]
    cliente, archivio, agente = cliente_con(
        risposta_agente("Ciao!", strumenti=[], cronologia=memoria, riassunto="r"), errore
    )
    chat = cliente.post("/chat").json()
    cliente.post(f"/chat/{chat['id']}/messaggi", json={"messaggio": "Ciao"})
    prima = cliente.get(f"/chat/{chat['id']}").json()
    with caplog.at_level(logging.INFO, logger="backend"):
        r = cliente.post(f"/chat/{chat['id']}/messaggi", json={"messaggio": "Che ore sono?"})
    assert r.status_code == errore.codice
    assert r.json() == {"errore": str(errore)}
    assert cliente.get(f"/chat/{chat['id']}").json() == prima
    with archivio.turno(chat["id"]) as turno:
        assert (turno.cronologia, turno.riassunto) == (memoria, "r")
    assert f"errore operazione=messaggio codice={errore.codice} messaggio={errore}" in righe(caplog, logging.WARNING)


def test_errore_agente_titolo_non_scritto():
    cliente, archivio, _ = cliente_con(ErroreAgente(503, NON_RAGGIUNGIBILE))
    chat = cliente.post("/chat").json()
    cliente.post(f"/chat/{chat['id']}/messaggi", json={"messaggio": "Che ore sono?"})
    assert archivio.leggi(chat["id"])[0].titolo is None


def test_messaggio_chat_inesistente_404_senza_agente():
    cliente, _, agente = cliente_con(risposta_agente())
    r = cliente.post("/chat/7/messaggi", json={"messaggio": "Ciao"})
    assert r.status_code == 404
    assert r.json() == {"errore": "Chat non trovata."}
    assert agente.chiamate == []


@pytest.mark.parametrize("corpo", [{"messaggio": ""}, {"messaggio": "   \n"}],
                         ids=["vuoto", "solo spazi"])
def test_messaggio_vuoto_422_senza_agente(corpo, caplog):
    cliente, _, agente = cliente_con(risposta_agente())
    chat = cliente.post("/chat").json()
    with caplog.at_level(logging.INFO, logger="backend"):
        r = cliente.post(f"/chat/{chat['id']}/messaggi", json=corpo)
    assert r.status_code == 422
    assert r.json() == {"errore": "Corpo non valido: il messaggio non può essere vuoto."}
    assert agente.chiamate == []
    assert any(riga.startswith("errore operazione=messaggio codice=422") for riga in righe(caplog, logging.WARNING))


@pytest.mark.parametrize("richiesta, atteso", [
    ({}, "Corpo non valido: manca il campo «messaggio»."),
    ({"messaggio": 5}, "Corpo non valido: il campo «messaggio» deve essere un testo."),
    ({"content": "{non json"}, "Corpo non valido: il JSON non è valido."),
], ids=["campo mancante", "non testo", "JSON rotto"])
def test_corpo_non_valido_422(richiesta, atteso):
    cliente, _, agente = cliente_con()
    chat = cliente.post("/chat").json()
    if "content" in richiesta:
        r = cliente.post(f"/chat/{chat['id']}/messaggi", content=richiesta["content"],
                         headers={"content-type": "application/json"})
    else:
        r = cliente.post(f"/chat/{chat['id']}/messaggi", json=richiesta)
    assert r.status_code == 422
    assert r.json() == {"errore": atteso}
    assert agente.chiamate == []


def test_titolo_non_testo_422():
    cliente, _, _ = cliente_con()
    r = cliente.post("/chat", json={"titolo": 5})
    assert r.status_code == 422
    assert r.json() == {"errore": "Corpo non valido: il campo «titolo» deve essere un testo."}


@pytest.mark.parametrize("percorso", ["/chat/abc", "/chat/0", "/chat/-1", "/chat/99999999999999999999"])
def test_id_non_numerico_422(percorso):
    cliente, _, agente = cliente_con(risposta_agente())
    for r in (cliente.get(percorso), cliente.delete(percorso),
              cliente.post(f"{percorso}/messaggi", json={"messaggio": "Ciao"})):
        assert r.status_code == 422
        assert r.json() == {"errore": "Richiesta non valida: l'identificativo della chat deve essere un numero intero positivo."}
    assert agente.chiamate == []


# ---------------- Database non disponibile ----------------


@pytest.mark.parametrize("metodo, percorso, corpo", [
    ("POST", "/chat", None),
    ("GET", "/chat", None),
    ("GET", "/chat/1", None),
    ("DELETE", "/chat/1", None),
    ("POST", "/chat/1/messaggi", {"messaggio": "Ciao"}),
], ids=["crea", "elenca", "leggi", "elimina", "messaggio"])
def test_database_giu_503(metodo, percorso, corpo, caplog):
    cliente, _, agente = cliente_con(risposta_agente(), archivio=ArchivioGiu())
    with caplog.at_level(logging.INFO, logger="backend"):
        r = cliente.request(metodo, percorso, json=corpo)
    assert r.status_code == 503
    assert r.json() == {"errore": "Database non disponibile."}
    assert agente.chiamate == []
    assert any("codice=503 messaggio=Database non disponibile." in riga for riga in righe(caplog, logging.WARNING))


# ---------------- OpenAPI e codifica ----------------


def test_openapi():
    cliente, _, _ = cliente_con()
    r = cliente.get("/openapi.json")
    assert r.status_code == 200
    doc = r.json()
    assert doc["info"]["title"] == "Back-end del laboratorio"
    percorsi = doc["paths"]
    attesi = {
        ("/chat", "post"): {"201", "422", "503"},
        ("/chat", "get"): {"200", "503"},
        ("/chat/{chat_id}", "get"): {"200", "404", "422", "503"},
        ("/chat/{chat_id}", "delete"): {"204", "404", "422", "503"},
        ("/chat/{chat_id}/messaggi", "post"): {"200", "404", "422", "502", "503", "504"},
    }
    for (percorso, metodo), codici in attesi.items():
        risposte = percorsi[percorso][metodo]["responses"]
        assert set(risposte) == codici, (percorso, metodo)
        for codice in codici - {"200", "201", "204"}:
            # Un solo tipo di contenuto JSON (con o senza "; charset=utf-8"), con lo schema dell'errore.
            ((tipo, contenuto),) = risposte[codice]["content"].items()
            assert tipo.startswith("application/json"), (percorso, metodo, codice)
            schema = contenuto["schema"]
            assert schema == {"$ref": "#/components/schemas/RispostaErrore"}, (percorso, metodo, codice)
    assert set(doc["components"]["schemas"]["RispostaErrore"]["properties"]) == {"errore"}
    assert cliente.get("/docs").status_code == 200


def test_utf8():
    testo = "È già l'ora? «Sì» 😀"
    cliente, _, _ = cliente_con(risposta_agente(testo, strumenti=[]))
    chat = cliente.post("/chat", json={"titolo": testo})
    assert chat.headers["content-type"] == "application/json; charset=utf-8"
    r = cliente.post(f"/chat/{chat.json()['id']}/messaggi", json={"messaggio": testo})
    assert r.headers["content-type"] == "application/json; charset=utf-8"
    assert r.json()["risposta"]["testo"] == testo
    assert cliente.get("/chat/999").headers["content-type"] == "application/json; charset=utf-8"
    assert cliente.get("/chat/abc").headers["content-type"] == "application/json; charset=utf-8"
    letta = cliente.get(f"/chat/{chat.json()['id']}").json()
    assert letta["titolo"] == testo
    assert [m["testo"] for m in letta["messaggi"]] == [testo, testo]


# Un carattere NUL o mezza emoji (surrogato isolato) non si può salvare né inviare: 422, non 500.
@pytest.mark.parametrize("testo", ["a\x00b", "mezza emoji \ud83d"], ids=["NUL", "surrogato"])
def test_caratteri_non_validi_422(testo):
    cliente, archivio, agente = cliente_con(risposta_agente())
    chat = cliente.post("/chat").json()
    # Il corpo come lo manda un browser: JSON con gli escape (\u0000, \ud83d).
    intestazioni = {"content-type": "application/json"}
    r = cliente.post(f"/chat/{chat['id']}/messaggi", content=json.dumps({"messaggio": testo}), headers=intestazioni)
    assert r.status_code == 422
    assert r.json() == {"errore": "Corpo non valido: il messaggio contiene caratteri non validi."}
    assert agente.chiamate == []
    r = cliente.post("/chat", content=json.dumps({"titolo": testo}), headers=intestazioni)
    assert r.status_code == 422
    assert r.json() == {"errore": "Corpo non valido: il titolo contiene caratteri non validi."}
    assert len(archivio.elenca()) == 1
