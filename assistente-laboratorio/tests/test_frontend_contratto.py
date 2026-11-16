"""Test del contratto OpenAPI tra front-end e back-end (lezione 6, step 8)."""

# COSA PROVA QUESTO FILE
# Il PDF chiede che il documento OpenAPI del back-end sia il contratto del front-end. Il
# front-end ne tiene una copia (frontend/contratto/openapi-backend.json) e:
#   - il proxy ammette solo le operazioni scritte nel contratto;
#   - un test confronta la copia con l'OpenAPI attuale del back-end: se il back-end cambia,
#     il test lo segnala (rigenerare con python -m frontend.contratto).
# Solo i test importano backend: il pacchetto frontend/ no.

import json
import re
from pathlib import Path

import httpx
import pytest
from finti_backend import ArchivioMemoria

from backend.app import crea_app as crea_app_backend
from frontend import contratto
from frontend.contratto import (
    ErroreContratto,
    ammessa,
    carica_contratto,
    operazioni,
    scarica_contratto,
)


def test_contratto_uguale_al_backend():
    attuale = crea_app_backend(ArchivioMemoria(), object()).openapi()
    assert carica_contratto() == attuale, "contratto non aggiornato: rigenerare con python -m frontend.contratto"


def test_operazioni_del_contratto():
    ammesse = operazioni(carica_contratto())
    assert len(ammesse) == 5
    for metodo, percorso in [("GET", "/chat"), ("POST", "/chat"), ("GET", "/chat/7"),
                             ("DELETE", "/chat/7"), ("POST", "/chat/7/messaggi")]:
        assert ammessa(ammesse, metodo, percorso), (metodo, percorso)
    for metodo, percorso in [("GET", "/chat/7/messaggi"), ("PUT", "/chat"), ("GET", "/docs"),
                             ("GET", "/openapi.json"), ("GET", "/chat/1/messaggi/2"), ("GET", "/chat/")]:
        assert not ammessa(ammesse, metodo, percorso), (metodo, percorso)


def test_ammessa_ignora_maiuscole_del_metodo():
    assert ammessa(operazioni(carica_contratto()), "get", "/chat")


def client_con(gestore) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(gestore), base_url="http://backend")


def test_scarica_contratto_scrive_il_file(tmp_path):
    documento = {"openapi": "3.1.0", "info": {"title": "è"}}
    richieste = []

    def gestore(richiesta):
        richieste.append(richiesta.url.path)
        return httpx.Response(200, json=documento)

    destinazione = tmp_path / "contratto.json"
    scarica_contratto(client_con(gestore), destinazione)
    assert richieste == ["/openapi.json"]
    byte = destinazione.read_bytes()
    assert not byte.startswith(b"\xef\xbb\xbf")
    assert json.loads(byte.decode("utf-8")) == documento
    assert "è" in byte.decode("utf-8")


def test_scarica_contratto_backend_giu(tmp_path):
    def gestore(richiesta):
        raise httpx.ConnectError("rifiutata")

    destinazione = tmp_path / "contratto.json"
    destinazione.write_text("vecchio", encoding="utf-8")
    with pytest.raises(ErroreContratto, match="Back-end non raggiungibile"):
        scarica_contratto(client_con(gestore), destinazione)
    assert destinazione.read_text(encoding="utf-8") == "vecchio"


def test_scarica_contratto_codice_500(tmp_path):
    destinazione = tmp_path / "contratto.json"
    with pytest.raises(ErroreContratto, match="500"):
        scarica_contratto(client_con(lambda r: httpx.Response(500, text="no")), destinazione)
    assert not destinazione.exists()


def test_scarica_contratto_json_non_valido(tmp_path):
    destinazione = tmp_path / "contratto.json"
    with pytest.raises(ErroreContratto):
        scarica_contratto(client_con(lambda r: httpx.Response(200, text="<html>")), destinazione)
    assert not destinazione.exists()


def test_main_backend_giu(tmp_path, monkeypatch, capsys):
    (tmp_path / ".env").write_text("BACKEND_URL=http://127.0.0.1:1\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("BACKEND_URL", raising=False)
    destinazione = tmp_path / "contratto.json"
    monkeypatch.setattr(contratto, "FILE_CONTRATTO", destinazione)
    assert contratto.main() == 1
    assert "Back-end non raggiungibile:" in capsys.readouterr().err
    assert not destinazione.exists()


def test_main_configurazione_non_valida(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("BACKEND_URL", "ftp://x")
    monkeypatch.setattr(contratto, "FILE_CONTRATTO", tmp_path / "contratto.json")
    assert contratto.main() == 2
    assert "Configurazione non valida:" in capsys.readouterr().err


# ---------------- Le chiamate della pagina (frontend/statico/api.js) ----------------

FILE_API_JS = Path(__file__).resolve().parent.parent / "frontend" / "statico" / "api.js"


def test_api_js_usa_solo_il_contratto():
    coppie = re.findall(r'\["(GET|POST|DELETE)",\s*"([^"]+)"\]', FILE_API_JS.read_text(encoding="utf-8"))
    assert sorted(coppie) == sorted([("GET", "/chat"), ("POST", "/chat"), ("GET", "/chat/{chat_id}"),
                                     ("DELETE", "/chat/{chat_id}"), ("POST", "/chat/{chat_id}/messaggi")])
    percorsi = carica_contratto()["paths"]
    for metodo, percorso in coppie:
        assert metodo.lower() in percorsi.get(percorso, {}), f"{metodo} {percorso} non è nel contratto"


# I campi che la pagina legge, schema per schema del contratto.
CAMPI_LETTI = {
    "ChatCreata": {"id", "titolo"},
    "VoceChat": {"id", "titolo", "ultimo_messaggio"},
    "ChatCompleta": {"id", "titolo", "messaggi"},
    "Messaggio": {"ruolo", "testo", "strumenti_usati", "data"},
    "StrumentoUsato": {"nome", "argomenti"},
    "Scambio": {"domanda", "risposta"},
    "RispostaErrore": {"errore"},
}


def test_campi_letti_esistono_nel_contratto():
    schemi = carica_contratto()["components"]["schemas"]
    for schema, campi in CAMPI_LETTI.items():
        mancanti = campi - set(schemi[schema]["properties"])
        assert mancanti == set(), f"{schema}: mancano {mancanti}"


# Revisione finale: segmenti "." e "..", "?" e "#" codificati o un a capo finale non devono
# trasformare un percorso inventato in un'operazione ammessa (il back-end li normalizzerebbe).
@pytest.mark.parametrize("metodo, percorso", [
    ("GET", "/chat/.."), ("GET", "/chat/."), ("POST", "/chat/../messaggi"),
    ("GET", "/chat/?x"), ("GET", "/chat/#x"), ("GET", "/chat/7\n"), ("GET", "/chat\n"),
])
def test_ammessa_rifiuta_segmenti_pericolosi(metodo, percorso):
    assert not ammessa(operazioni(carica_contratto()), metodo, percorso)
