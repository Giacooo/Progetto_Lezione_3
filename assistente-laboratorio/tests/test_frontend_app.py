"""Test del server del front-end: pagina statica e proxy verso il back-end (lezione 6, step 8)."""

# COSA PROVA QUESTO FILE
# frontend/app.py con TestClient e un back-end simulato (httpx.MockTransport): niente rete,
# niente database, niente agente. Il proxy /api/... inoltra al back-end solo le operazioni del
# contratto e restituisce le sue risposte così come sono; se il back-end è spento o lento
# risponde lui, con un errore nella stessa forma {"errore": ...} del back-end.

import logging

import httpx
import pytest
from fastapi.testclient import TestClient

from frontend.app import BACKEND_FUORI_TEMPO, BACKEND_GIU, NON_DISPONIBILE, crea_app


class BackendFinto:
    """Registra le richieste ricevute e risponde con la funzione indicata."""

    def __init__(self, risposta=None):
        self.richieste: list[httpx.Request] = []
        self.risposta = risposta or (lambda r: httpx.Response(200, json={"ok": True}))

    def __call__(self, richiesta: httpx.Request) -> httpx.Response:
        richiesta.read()
        self.richieste.append(richiesta)
        return self.risposta(richiesta)


def cliente(backend: BackendFinto) -> TestClient:
    client_backend = httpx.Client(transport=httpx.MockTransport(backend), base_url="http://backend")
    return TestClient(crea_app(client_backend))


def test_pagina_servita():
    r = cliente(BackendFinto()).get("/")
    assert r.status_code == 200
    assert r.headers["content-type"] == "text/html; charset=utf-8"
    assert "<html" in r.text


def test_file_statici_content_type():
    c = cliente(BackendFinto())
    assert c.get("/index.html").headers["content-type"] == "text/html; charset=utf-8"


@pytest.mark.parametrize("metodo, percorso, corpo", [
    ("GET", "/chat", None),
    ("POST", "/chat", {}),
    ("GET", "/chat/3", None),
    ("DELETE", "/chat/3", None),
    ("POST", "/chat/3/messaggi", {"messaggio": "Quanto fa 45 diviso 9?"}),
])
def test_inoltro_operazioni(metodo, percorso, corpo):
    backend = BackendFinto(lambda r: httpx.Response(201, json={"id": 3, "titolo": "Nuova chat"}))
    r = cliente(backend).request(metodo, "/api" + percorso, json=corpo)
    assert (r.status_code, r.json()) == (201, {"id": 3, "titolo": "Nuova chat"})
    (ricevuta,) = backend.richieste
    assert (ricevuta.method, ricevuta.url.path) == (metodo, percorso)
    if corpo is not None:
        assert ricevuta.headers["content-type"] == "application/json"
        assert httpx.Response(200, content=ricevuta.content).json() == corpo


def test_inoltro_query_string():
    backend = BackendFinto()
    cliente(backend).get("/api/chat?x=1")
    assert backend.richieste[0].url.params["x"] == "1"


def test_elimina_204_senza_corpo():
    r = cliente(BackendFinto(lambda r: httpx.Response(204))).delete("/api/chat/3")
    assert r.status_code == 204
    assert r.content == b""


@pytest.mark.parametrize("codice", [404, 422, 502, 503, 504])
def test_errori_backend_passano(codice):
    backend = BackendFinto(lambda r: httpx.Response(codice, json={"errore": "Chat non trovata."}))
    r = cliente(backend).get("/api/chat/9")
    assert (r.status_code, r.json()) == (codice, {"errore": "Chat non trovata."})


def test_content_type_del_backend_restituito():
    backend = BackendFinto(lambda r: httpx.Response(
        200, content='{"a": "è"}'.encode(), headers={"content-type": "application/json; charset=utf-8"}))
    r = cliente(backend).get("/api/chat")
    assert r.headers["content-type"] == "application/json; charset=utf-8"


def test_inoltro_utf8():
    domanda = '{"messaggio": "Perché è così? 😀"}'.encode("utf-8")
    risposta = '{"risposta": "Perché sì 😀"}'.encode("utf-8")
    backend = BackendFinto(lambda r: httpx.Response(200, content=risposta,
                                                    headers={"content-type": "application/json; charset=utf-8"}))
    r = cliente(backend).post("/api/chat/1/messaggi", content=domanda,
                              headers={"content-type": "application/json; charset=utf-8"})
    assert backend.richieste[0].content == domanda
    assert r.content == risposta


def test_backend_giu_503(caplog):
    def giu(richiesta):
        raise httpx.ConnectError("connessione rifiutata")

    with caplog.at_level(logging.INFO, logger="frontend"):
        r = cliente(BackendFinto(giu)).get("/api/chat")
    assert (r.status_code, r.json()) == (503, {"errore": BACKEND_GIU})
    assert BACKEND_GIU == "Back-end non raggiungibile: controllare che sia avviato e l'indirizzo BACKEND_URL."
    assert "back-end non raggiungibile metodo=GET percorso=/chat" in caplog.text


def test_backend_fuori_tempo_504(caplog):
    def lento(richiesta):
        raise httpx.ReadTimeout("troppo lento")

    with caplog.at_level(logging.INFO, logger="frontend"):
        r = cliente(BackendFinto(lento)).post("/api/chat/1/messaggi", json={"messaggio": "ciao"})
    assert (r.status_code, r.json()) == (504, {"errore": BACKEND_FUORI_TEMPO})
    assert BACKEND_FUORI_TEMPO == "Il back-end non ha risposto in tempo."
    assert "back-end fuori tempo metodo=POST percorso=/chat/1/messaggi" in caplog.text


@pytest.mark.parametrize("metodo, percorso", [
    ("GET", "/api/docs"),
    ("GET", "/api/openapi.json"),
    ("GET", "/api/chat/1/messaggi/2"),
    ("PUT", "/api/chat"),
    ("GET", "/api/chat/7/messaggi"),
    ("GET", "/api/"),
])
def test_fuori_contratto_404(metodo, percorso):
    backend = BackendFinto()
    r = cliente(backend).request(metodo, percorso)
    assert (r.status_code, r.json()) == (404, {"errore": NON_DISPONIBILE})
    assert NON_DISPONIBILE == "Operazione non disponibile."
    assert backend.richieste == []


def test_log_inoltro(caplog):
    with caplog.at_level(logging.INFO, logger="frontend"):
        cliente(BackendFinto()).post("/api/chat/3/messaggi", json={"messaggio": "domanda segreta"})
    assert "inoltro metodo=POST percorso=/chat/3/messaggi codice=200" in caplog.text
    assert "domanda segreta" not in caplog.text
