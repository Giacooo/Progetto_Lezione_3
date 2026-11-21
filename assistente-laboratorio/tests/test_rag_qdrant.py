"""Client REST di Qdrant (lezione 7), provato contro il Qdrant finto in memoria."""

# COSA PROVA QUESTO FILE
# Ogni operazione del client (rag/qdrant.py): percorso e corpo della richiesta, lettura della
# risposta, errori tradotti in messaggi chiari. Il server Qdrant non serve: risponde il Qdrant
# finto di finti_rag.py. Il formato vero delle risposte si verifica nelle prove reali.

import httpx
import pytest
from finti_rag import QdrantFinto, client_finto

from rag.qdrant import ClientQdrant, ErroreQdrant, InfoCollezione, Punto, QdrantNonRaggiungibile

METADATI = {"embedding_modello": "m", "embedding_dimensione": 4}


@pytest.fixture
def finto():
    return QdrantFinto()


@pytest.fixture
def qdrant(finto):
    return client_finto(finto)


def punto(n: int, vettore, capitolo="Fritti") -> Punto:
    return Punto(id=f"00000000-0000-0000-0000-{n:012d}", vettore=vettore, payload={"capitolo": capitolo, "n": n})


def test_collezione_assente(qdrant):
    assert qdrant.info_collezione("c") is None


def test_crea_e_leggi_collezione(qdrant, finto):
    qdrant.crea_collezione("c", 4, METADATI)
    assert qdrant.info_collezione("c") == InfoCollezione(4, METADATI)
    metodo, percorso, corpo = finto.richieste[-2]
    assert (metodo, percorso) == ("PUT", "/collections/c")
    assert corpo == {"vectors": {"size": 4, "distance": "Cosine"}, "metadata": METADATI}


def test_collezione_senza_metadati(qdrant, finto):
    finto.collezioni["c"] = {"dimensione": 4, "metadati": {}, "indici": {}, "punti": {}}
    assert qdrant.info_collezione("c") == InfoCollezione(4, {})


def test_indice_keyword(qdrant, finto):
    qdrant.crea_collezione("c", 4, METADATI)
    qdrant.crea_indice("c", "capitolo")
    metodo, percorso, corpo = finto.richieste[-1]
    assert (metodo, percorso) == ("PUT", "/collections/c/index")
    assert corpo == {"field_name": "capitolo", "field_schema": "keyword"}
    assert finto.collezioni["c"]["indici"] == {"capitolo": "keyword"}


def test_upsert_stesso_id_sostituisce(qdrant, finto):
    qdrant.crea_collezione("c", 4, METADATI)
    qdrant.upsert("c", [punto(1, [1, 0, 0, 0])])
    qdrant.upsert("c", [Punto(punto(1, []).id, [0, 1, 0, 0], {"capitolo": "Umidi"})])
    assert qdrant.conta("c") == 1
    [(vettore, payload)] = finto.collezioni["c"]["punti"].values()
    assert payload == {"capitolo": "Umidi"}
    metodo, percorso, corpo = finto.richieste[-2]
    assert (metodo, percorso) == ("PUT", "/collections/c/points")
    assert corpo["points"][0] == {"id": punto(1, []).id, "vector": [0, 1, 0, 0], "payload": {"capitolo": "Umidi"}}


def test_cerca_ordinata_e_filtrata(qdrant, finto):
    qdrant.crea_collezione("c", 4, METADATI)
    qdrant.upsert("c", [punto(1, [1, 0, 0, 0]), punto(2, [1, 1, 0, 0], "Umidi"), punto(3, [0, 1, 0, 0])])
    tutti = qdrant.cerca("c", [1, 0.2, 0, 0], 10)
    assert [t.payload["n"] for t in tutti] == [1, 2, 3]
    assert tutti[0].score >= tutti[1].score >= tutti[2].score
    fritti = qdrant.cerca("c", [1, 0.2, 0, 0], 10, capitolo="Fritti")
    assert [t.payload["capitolo"] for t in fritti] == ["Fritti", "Fritti"]
    metodo, percorso, corpo = finto.richieste[-1]
    assert (metodo, percorso) == ("POST", "/collections/c/points/query")
    assert corpo == {"query": [1, 0.2, 0, 0], "limit": 10, "with_payload": True,
                     "filter": {"must": [{"key": "capitolo", "match": {"value": "Fritti"}}]}}


def test_cerca_senza_filtro_non_manda_filter(qdrant, finto):
    qdrant.crea_collezione("c", 4, METADATI)
    qdrant.cerca("c", [1, 0, 0, 0], 3)
    assert "filter" not in finto.richieste[-1][2]


def test_scroll_a_pagine(qdrant, finto):
    qdrant.crea_collezione("c", 4, METADATI)
    qdrant.upsert("c", [punto(n, [1, 0, 0, 0]) for n in range(2500)])
    assert qdrant.ids_presenti("c") == {punto(n, []).id for n in range(2500)}
    pagine = [r for r in finto.richieste if r[1] == "/collections/c/points/scroll"]
    assert len(pagine) == 3
    assert pagine[0][2] == {"limit": 1000, "with_payload": False, "with_vector": False}


def test_elimina_e_conta(qdrant, finto):
    qdrant.crea_collezione("c", 4, METADATI)
    qdrant.upsert("c", [punto(n, [1, 0, 0, 0]) for n in range(5)])
    qdrant.elimina("c", [punto(0, []).id, punto(1, []).id])
    assert qdrant.conta("c") == 3
    assert finto.richieste[-2][2] == {"points": [punto(0, []).id, punto(1, []).id]}
    assert finto.richieste[-1][2] == {"exact": True}


def test_elimina_lista_vuota_nessuna_richiesta(qdrant, finto):
    qdrant.crea_collezione("c", 4, METADATI)
    prima = len(finto.richieste)
    qdrant.elimina("c", [])
    assert len(finto.richieste) == prima


def test_capitoli_distinti_ordinati(qdrant, finto):
    qdrant.crea_collezione("c", 4, METADATI)
    qdrant.crea_indice("c", "capitolo")
    qdrant.upsert("c", [punto(1, [1, 0, 0, 0], "Umidi"), punto(2, [1, 0, 0, 0]), punto(3, [1, 0, 0, 0])])
    assert qdrant.capitoli("c") == ["Fritti", "Umidi"]
    assert finto.richieste[-1][1:] == ("/collections/c/facet", {"key": "capitolo", "limit": 100, "exact": True})


def test_capitoli_senza_indice_errore(qdrant):
    """Come il Qdrant vero: il facet richiede un indice sul campo."""
    qdrant.crea_collezione("c", 4, METADATI)
    qdrant.upsert("c", [punto(1, [1, 0, 0, 0])])
    with pytest.raises(ErroreQdrant, match="Index required"):
        qdrant.capitoli("c")


def test_qdrant_spento():
    def spento(request):
        raise httpx.ConnectError("connessione rifiutata")

    qdrant = ClientQdrant("http://q:6333", client=httpx.Client(transport=httpx.MockTransport(spento)))
    with pytest.raises(QdrantNonRaggiungibile) as e:
        qdrant.info_collezione("c")
    assert "docker compose ps" in str(e.value)
    assert "QDRANT_URL" in str(e.value)


def test_errore_qdrant(qdrant):
    qdrant.crea_collezione("c", 4, METADATI)
    with pytest.raises(ErroreQdrant, match="dimension"):
        qdrant.upsert("c", [punto(1, [1, 0])])


def test_errore_su_collezione_assente(qdrant):
    with pytest.raises(ErroreQdrant, match="404"):
        qdrant.conta("non-esiste")


# --- Modifica A: indice bool, set payload, filtro contiene_dosi, conteggio con filtro ---

DOSI = {"key": "contiene_dosi", "match": {"value": True}}


def test_indice_bool(qdrant, finto):
    qdrant.crea_collezione("c", 4, METADATI)
    qdrant.crea_indice("c", "contiene_dosi", "bool")
    assert finto.richieste[-1][2] == {"field_name": "contiene_dosi", "field_schema": "bool"}
    assert finto.collezioni["c"]["indici"] == {"contiene_dosi": "bool"}


def test_imposta_payload(qdrant, finto):
    qdrant.crea_collezione("c", 4, METADATI)
    qdrant.upsert("c", [punto(1, [1, 0, 0, 0]), punto(2, [0, 1, 0, 0])])
    id1 = punto(1, []).id
    qdrant.imposta_payload("c", {"contiene_dosi": True}, [id1])
    metodo, percorso, corpo = finto.richieste[-1]
    assert (metodo, percorso) == ("POST", "/collections/c/points/payload")
    assert corpo == {"payload": {"contiene_dosi": True}, "points": [id1]}
    vettore, payload = finto.collezioni["c"]["punti"][id1]
    assert vettore == [1, 0, 0, 0]
    assert payload == {"capitolo": "Fritti", "n": 1, "contiene_dosi": True}
    assert "contiene_dosi" not in finto.collezioni["c"]["punti"][punto(2, []).id][1]


def test_imposta_payload_id_assente(qdrant):
    qdrant.crea_collezione("c", 4, METADATI)
    with pytest.raises(ErroreQdrant, match="404"):
        qdrant.imposta_payload("c", {"contiene_dosi": True}, [punto(9, []).id])


def test_imposta_payload_lista_vuota_nessuna_richiesta(qdrant, finto):
    qdrant.crea_collezione("c", 4, METADATI)
    prima = len(finto.richieste)
    qdrant.imposta_payload("c", {"contiene_dosi": True}, [])
    assert len(finto.richieste) == prima


def test_imposta_payload_a_lotti(qdrant, finto):
    qdrant.crea_collezione("c", 4, METADATI)
    qdrant.upsert("c", [punto(n, [1, 0, 0, 0]) for n in range(600)])
    qdrant.imposta_payload("c", {"contiene_dosi": False}, [punto(n, []).id for n in range(600)])
    lotti = [r for r in finto.richieste if r[1] == "/collections/c/points/payload"]
    assert [len(r[2]["points"]) for r in lotti] == [256, 256, 88]


def test_cerca_solo_dosi_e_capitolo(qdrant, finto):
    qdrant.crea_collezione("c", 4, METADATI)
    qdrant.upsert("c", [punto(1, [1, 0, 0, 0]), punto(2, [1, 0, 0, 0], "Umidi"), punto(3, [1, 0, 0, 0])])
    qdrant.imposta_payload("c", {"contiene_dosi": True}, [punto(1, []).id, punto(2, []).id])
    trovati = qdrant.cerca("c", [1, 0, 0, 0], 10, capitolo="Fritti", solo_dosi=True)
    assert [t.payload["n"] for t in trovati] == [1]
    assert finto.richieste[-1][2]["filter"] == {
        "must": [{"key": "capitolo", "match": {"value": "Fritti"}}, DOSI]}
    trovati = qdrant.cerca("c", [1, 0, 0, 0], 10, solo_dosi=True)
    assert sorted(t.payload["n"] for t in trovati) == [1, 2]
    assert finto.richieste[-1][2]["filter"] == {"must": [DOSI]}


def test_conta_con_filtro(qdrant, finto):
    qdrant.crea_collezione("c", 4, METADATI)
    qdrant.upsert("c", [punto(n, [1, 0, 0, 0]) for n in range(1, 4)])
    qdrant.imposta_payload("c", {"contiene_dosi": True}, [punto(1, []).id])
    assert qdrant.conta("c", {"must": [DOSI]}) == 1
    assert finto.richieste[-1][2] == {"exact": True, "filter": {"must": [DOSI]}}
    assert qdrant.conta("c") == 3
    assert finto.richieste[-1][2] == {"exact": True}


def test_testi_presenti(qdrant, finto):
    qdrant.crea_collezione("c", 4, METADATI)
    qdrant.upsert("c", [Punto(punto(n, []).id, [1, 0, 0, 0], {"testo": f"t{n}", "n": n}) for n in range(1500)])
    assert qdrant.testi_presenti("c") == {punto(n, []).id: f"t{n}" for n in range(1500)}
    pagine = [r for r in finto.richieste if r[1] == "/collections/c/points/scroll"]
    assert len(pagine) == 2
    assert pagine[0][2]["with_payload"] == ["testo"] and pagine[0][2]["with_vector"] is False
