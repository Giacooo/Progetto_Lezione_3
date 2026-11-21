"""Embedding con LM Studio (lezione 7, pipeline fase 6), con HTTP simulato."""

# COSA PROVA QUESTO FILE
# La chiamata POST {LM_BASE_URL}/embeddings: corpo, lotti, ordine dei vettori ed errori tradotti
# in messaggi chiari. LM Studio non serve: risponde un trasporto finto di httpx (MockTransport).
# In fondo, che l'embedder finto usato dagli altri test sia davvero deterministico.

import json
import math

import httpx
import pytest
from finti_rag import EmbedderFinto

from rag.embedding import EmbedderLMStudio, ErroreEmbedding, LMStudioNonRaggiungibile


def embedder_con(risposta, richieste=None, modello="m"):
    def gestore(request: httpx.Request) -> httpx.Response:
        corpo = json.loads(request.content)
        if richieste is not None:
            richieste.append((request.url.path, corpo))
        return risposta(corpo)

    client = httpx.Client(transport=httpx.MockTransport(gestore))
    return EmbedderLMStudio("http://lm:1234/v1", modello, client=client)


def risposta_ok(corpo):
    dati = [{"object": "embedding", "index": i, "embedding": [float(i), float(len(t))]}
            for i, t in enumerate(corpo["input"])]
    return httpx.Response(200, json={"object": "list", "data": dati, "model": corpo["model"]})


def test_corpo_della_richiesta():
    richieste = []
    vettori = embedder_con(risposta_ok, richieste).calcola(["a", "bb"])
    assert richieste == [("/v1/embeddings", {"model": "m", "input": ["a", "bb"]})]
    assert vettori == [[0.0, 1.0], [1.0, 2.0]]


def test_lotti():
    richieste = []
    testi = [f"testo {n}" for n in range(70)]
    vettori = embedder_con(risposta_ok, richieste).calcola(testi)
    assert [len(corpo["input"]) for _, corpo in richieste] == [32, 32, 6]
    assert [v[1] for v in vettori] == [float(len(t)) for t in testi]


def test_ordine_secondo_index():
    def al_contrario(corpo):
        risposta = risposta_ok(corpo).json()
        risposta["data"].reverse()
        return httpx.Response(200, json=risposta)

    assert embedder_con(al_contrario).calcola(["a", "bb", "ccc"]) == [[0.0, 1.0], [1.0, 2.0], [2.0, 3.0]]


def test_errore_lm_studio_cita_il_modello():
    def errore(corpo):
        return httpx.Response(400, json={"error": {"message": "model not found"}})

    with pytest.raises(ErroreEmbedding) as e:
        embedder_con(errore, modello="text-embedding-sbagliato").calcola(["a"])
    assert "text-embedding-sbagliato" in str(e.value)
    assert "model not found" in str(e.value)
    assert not isinstance(e.value, LMStudioNonRaggiungibile)


def test_errore_lm_studio_testo_semplice():
    with pytest.raises(ErroreEmbedding, match="500"):
        embedder_con(lambda corpo: httpx.Response(500, text="guasto")).calcola(["a"])


def test_lm_studio_spento():
    def spento(request):
        raise httpx.ConnectError("connessione rifiutata")

    embedder = EmbedderLMStudio("http://lm:1234/v1", "m", client=httpx.Client(transport=httpx.MockTransport(spento)))
    with pytest.raises(LMStudioNonRaggiungibile, match="LM_BASE_URL"):
        embedder.calcola(["a"])


def test_numero_di_vettori_sbagliato():
    def pochi(corpo):
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [1.0]}]})

    with pytest.raises(ErroreEmbedding):
        embedder_con(pochi).calcola(["a", "b"])


def test_lista_vuota_nessuna_chiamata():
    richieste = []
    assert embedder_con(risposta_ok, richieste).calcola([]) == []
    assert richieste == []


def coseno(a, b):
    return sum(x * y for x, y in zip(a, b))


def test_embedder_finto_deterministico():
    finto = EmbedderFinto()
    assert finto.calcola(["gnocchi di patate"]) == EmbedderFinto().calcola(["gnocchi di patate"])
    [v] = finto.calcola(["gnocchi di patate"])
    assert math.isclose(sum(x * x for x in v), 1.0)
    [a, b, c] = finto.calcola(["gnocchi di patate", "patate e gnocchi", "vino rosso"])
    assert coseno(a, b) > coseno(a, c)
