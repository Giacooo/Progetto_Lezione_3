"""Test del client HTTP con cui il back-end chiama l'agente (lezione 6, step 7)."""

# COSA PROVA QUESTO FILE
# Il back-end parla con l'agente dello step 6 solo via HTTP (POST /messaggio). Qui l'agente è
# simulato con httpx.MockTransport: nessuna porta aperta, nessun modello. Si controlla che il
# corpo inviato sia quello giusto e che ogni guasto dell'agente diventi un ErroreAgente con il
# codice e il messaggio del §9.1 della specifica.

import json

import httpx
import pytest

from backend.agente_remoto import ATTESA_MASSIMA, AgenteRemoto, ErroreAgente, RispostaAgente

CRONOLOGIA = [{"ruolo": "utente", "testo": "Ciao"}, {"ruolo": "assistente", "testo": "Ciao!"}]
RISPOSTA_OK = {
    "risposta": "Fa 5.",
    "strumenti_usati": [{"nome": "calcola", "argomenti": {"espressione": "45 / 9"}, "risultato": "5"}],
    "cronologia": CRONOLOGIA + [{"ruolo": "utente", "testo": "Quanto fa 45 diviso 9?"}],
    "riassunto": "",
}
NON_SALVATA = "La domanda non è stata salvata."


def agente_finto(gestore) -> AgenteRemoto:
    client = httpx.Client(transport=httpx.MockTransport(gestore), base_url="http://agente")
    return AgenteRemoto("http://agente", client=client)


def risponde(codice, corpo=None, testo=None):
    def gestore(richiesta):
        if testo is not None:
            return httpx.Response(codice, text=testo)
        return httpx.Response(codice, json=corpo)
    return gestore


def solleva(eccezione):
    def gestore(richiesta):
        raise eccezione("guasto", request=richiesta)
    return gestore


def test_corpo_inviato():
    ricevute = []

    def gestore(richiesta):
        ricevute.append(richiesta)
        return httpx.Response(200, json=RISPOSTA_OK)

    agente_finto(gestore).invia("Quanto fa 45 diviso 9?", CRONOLOGIA, "Si chiama Carlo.")
    (richiesta,) = ricevute
    assert richiesta.method == "POST"
    assert richiesta.url.path == "/messaggio"
    assert json.loads(richiesta.content) == {
        "messaggio": "Quanto fa 45 diviso 9?", "cronologia": CRONOLOGIA, "riassunto": "Si chiama Carlo."
    }


def test_risposta_valida():
    risposta = agente_finto(risponde(200, RISPOSTA_OK)).invia("Quanto fa 45 diviso 9?", CRONOLOGIA, "")
    assert risposta == RispostaAgente(**RISPOSTA_OK)


def test_attesa_massima_del_client_predefinito():
    agente = AgenteRemoto("http://localhost:8000/")
    assert ATTESA_MASSIMA == 600
    assert agente.client.timeout.read == 600
    assert str(agente.client.base_url) == "http://localhost:8000"


def test_connessione_rifiutata():
    with pytest.raises(ErroreAgente) as e:
        agente_finto(solleva(httpx.ConnectError)).invia("Ciao", [], "")
    assert e.value.codice == 503
    assert str(e.value) == "Agente non raggiungibile: la domanda non è stata salvata, riprovare più tardi."


def test_connessione_interrotta():
    with pytest.raises(ErroreAgente) as e:
        agente_finto(solleva(httpx.RemoteProtocolError)).invia("Ciao", [], "")
    assert e.value.codice == 503


def test_attesa_scaduta():
    with pytest.raises(ErroreAgente) as e:
        agente_finto(solleva(httpx.ReadTimeout)).invia("Ciao", [], "")
    assert e.value.codice == 504
    assert str(e.value) == "L'agente non ha risposto in tempo: la domanda non è stata salvata."


def test_errore_con_messaggio():
    with pytest.raises(ErroreAgente) as e:
        agente_finto(risponde(503, {"errore": "Connessione fallita: LM Studio"})).invia("Ciao", [], "")
    assert e.value.codice == 502
    assert str(e.value) == f"Errore dell'agente: Connessione fallita: LM Studio. {NON_SALVATA}"


def test_errore_senza_json():
    with pytest.raises(ErroreAgente) as e:
        agente_finto(risponde(500, testo="Internal Server Error")).invia("Ciao", [], "")
    assert e.value.codice == 502
    assert str(e.value) == f"Errore dell'agente: codice 500. {NON_SALVATA}"


def test_errore_422_dell_agente():
    # Il 422 standard di FastAPI ({"detail": [...]}) non ha "errore": si mostra il codice.
    with pytest.raises(ErroreAgente) as e:
        agente_finto(risponde(422, {"detail": [{"msg": "campo mancante"}]})).invia("Ciao", [], "")
    assert str(e.value) == f"Errore dell'agente: codice 422. {NON_SALVATA}"


@pytest.mark.parametrize("gestore", [
    risponde(200, testo="non è JSON"),
    risponde(200, ["una", "lista"]),
    risponde(200, {**RISPOSTA_OK, "cronologia": "non una lista"}),
    risponde(200, {**RISPOSTA_OK, "risposta": 5}),
    risponde(200, {k: v for k, v in RISPOSTA_OK.items() if k != "strumenti_usati"}),
    risponde(200, {**RISPOSTA_OK, "riassunto": None}),
    risponde(200, {**RISPOSTA_OK, "strumenti_usati": ["non un dizionario"]}),
    risponde(200, {**RISPOSTA_OK, "cronologia": ["non un dizionario"]}),
], ids=["non JSON", "lista", "cronologia non lista", "risposta non str", "strumenti mancanti",
        "riassunto None", "strumento non dict", "messaggio non dict"])
def test_forma_sbagliata(gestore):
    with pytest.raises(ErroreAgente) as e:
        agente_finto(gestore).invia("Ciao", [], "")
    assert e.value.codice == 502
    assert str(e.value) == f"Risposta non valida dall'agente: controllare AGENTE_URL. {NON_SALVATA}"


def test_errore_con_punto_finale_non_raddoppia():
    with pytest.raises(ErroreAgente) as e:
        agente_finto(risponde(500, {"errore": "Errore interno dell'agente."})).invia("Ciao", [], "")
    assert str(e.value) == f"Errore dell'agente: Errore interno dell'agente. {NON_SALVATA}"
