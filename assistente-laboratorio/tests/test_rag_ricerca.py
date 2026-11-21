"""Ricerca top-k con filtro per capitolo (lezione 7, esercizio 1), sul Qdrant finto."""

# COSA PROVA QUESTO FILE
# La ricerca su un indice costruito con l'ingestion vera (embedder finto, Qdrant finto):
# risultati ordinati, k predefinito 5 e massimo 20, filtro per capitolo inviato DURANTE la
# ricerca, errori chiari (k fuori intervallo, domanda vuota, capitolo inesistente, collezione
# mancante, modello diverso) senza chiamate inutili. In fondo i codici di uscita del comando.

import pytest
from finti_rag import CORPUS_PROVA, EmbedderFinto, QdrantFinto, client_finto

from rag import ricerca
from rag.configurazione import ConfigurazioneRag
from rag.ingestion import CambioBloccato, esegui_ingestion
from rag.qdrant import QdrantNonRaggiungibile
from rag.ricerca import K_MASSIMO, K_PREDEFINITO, ErroreRicerca, Risultato, cerca, formatta


@pytest.fixture
def finto(tmp_path):
    libro = tmp_path / "artusi.txt"
    libro.write_text(CORPUS_PROVA, encoding="utf-8")
    config = ConfigurazioneRag("http://lm:1234/v1", "finto", "http://q:6333", "ricette", libro,
                               "paragrafi", 400, 80, "INFO")
    finto = QdrantFinto()
    esito = esegui_ingestion(config, EmbedderFinto(), client_finto(finto), ricette_attese=5)
    assert esito.punti_dopo > K_PREDEFINITO
    finto.richieste.clear()
    return finto


@pytest.fixture
def qdrant(finto):
    return client_finto(finto)


def query_inviate(finto):
    return [r for r in finto.richieste if r[1].endswith("/points/query")]


def test_costanti():
    assert (K_PREDEFINITO, K_MASSIMO) == (5, 20)


def test_risultati_ordinati_per_score(qdrant):
    risultati = cerca("Tagliate il pollo a pezzi e infarinatelo", EmbedderFinto(), qdrant, "ricette")
    assert [r.classifica for r in risultati] == list(range(1, len(risultati) + 1))
    score = [r.score for r in risultati]
    assert score == sorted(score, reverse=True)
    assert risultati[0].numero == 4


def test_k_predefinito_5(qdrant):
    assert len(cerca("pollo", EmbedderFinto(), qdrant, "ricette")) == 5


def test_k_massimo_20_accettato(qdrant, finto):
    risultati = cerca("pollo", EmbedderFinto(), qdrant, "ricette", k=20)
    assert query_inviate(finto)[-1][2]["limit"] == 20
    assert len(risultati) == len(finto.collezioni["ricette"]["punti"])


@pytest.mark.parametrize("k", [0, 21, -1])
def test_k_fuori_intervallo(qdrant, finto, k):
    embedder = EmbedderFinto()
    with pytest.raises(ErroreRicerca, match="tra 1 e 20"):
        cerca("pollo", embedder, qdrant, "ricette", k=k)
    assert embedder.chiamate == []
    assert finto.richieste == []


def test_filtro_capitolo_durante_la_ricerca(qdrant, finto):
    risultati = cerca("cappelletti in brodo", EmbedderFinto(), qdrant, "ricette", capitolo="Fritti")
    assert risultati
    assert {r.capitolo for r in risultati} == {"Fritti"}
    corpo = query_inviate(finto)[-1][2]
    assert corpo["filter"]["must"][0] == {"key": "capitolo", "match": {"value": "Fritti"}}


def test_capitolo_inesistente_elenca_i_disponibili(qdrant, finto):
    embedder = EmbedderFinto()
    with pytest.raises(ErroreRicerca) as e:
        cerca("pollo", embedder, qdrant, "ricette", capitolo="fritti")
    assert "Fritti" in str(e.value)
    assert "Minestre in brodo" in str(e.value)
    assert query_inviate(finto) == []
    assert embedder.chiamate == []


def test_domanda_vuota(qdrant, finto):
    embedder = EmbedderFinto()
    with pytest.raises(ErroreRicerca, match="vuota"):
        cerca("   ", embedder, qdrant, "ricette")
    assert embedder.chiamate == []
    assert finto.richieste == []


def test_collezione_assente(qdrant):
    with pytest.raises(ErroreRicerca, match="rag.ingestion"):
        cerca("pollo", EmbedderFinto(), qdrant, "non-esiste")


def test_modello_diverso_bloccato(qdrant, finto):
    embedder = EmbedderFinto(modello="altro")
    with pytest.raises(CambioBloccato):
        cerca("pollo", embedder, qdrant, "ricette")
    assert embedder.chiamate == []
    assert query_inviate(finto) == []


def test_dimensione_diversa_bloccata(qdrant, finto):
    with pytest.raises(CambioBloccato):
        cerca("pollo", EmbedderFinto(dimensione=64), qdrant, "ricette")
    assert query_inviate(finto) == []


def test_formatta_mostra_la_fonte():
    testo = formatta([Risultato(1, 0.87654, 4, "Pollo fritto", "Fritti", 0, "Tagliate il pollo a pezzi.")])
    for atteso in ("1", "0.8765", "N. 4", "Pollo fritto", "Fritti", "chunk 0", "Tagliate il pollo a pezzi."):
        assert atteso in testo


def test_formatta_nessun_risultato():
    assert "Nessun risultato" in formatta([])


@pytest.fixture
def ambiente(tmp_path, monkeypatch, finto):
    monkeypatch.chdir(tmp_path)
    valori = {"LM_BASE_URL": "http://lm:1234/v1", "EMBEDDING_MODELLO": "finto", "QDRANT_URL": "http://q:6333",
              "QDRANT_COLLEZIONE": "ricette", "LOG_LEVEL": "INFO"}
    for nome, valore in valori.items():
        monkeypatch.setenv(nome, valore)
    monkeypatch.setattr(ricerca, "crea_embedder", lambda config: EmbedderFinto())
    monkeypatch.setattr(ricerca, "crea_qdrant", lambda config: client_finto(finto))


def test_main_ok(ambiente, capsys):
    assert ricerca.main(["Come si frigge il pollo?", "--capitolo", "Fritti", "--k", "3"]) == 0
    uscita = capsys.readouterr().out
    assert "Pollo fritto" in uscita
    assert "Minestre in brodo" not in uscita


def test_main_k_troppo_grande(ambiente, capsys):
    assert ricerca.main(["pollo", "--k", "25"]) == 4
    assert "tra 1 e 20" in capsys.readouterr().err


def test_main_qdrant_spento(ambiente, monkeypatch, capsys):
    def spento(*args, **kwargs):
        raise QdrantNonRaggiungibile("Qdrant non raggiungibile: controllare docker compose ps e QDRANT_URL")

    monkeypatch.setattr(ricerca, "cerca", spento)
    assert ricerca.main(["pollo"]) == 3
    assert "docker compose ps" in capsys.readouterr().err


def test_main_configurazione_non_valida(ambiente, monkeypatch):
    monkeypatch.setenv("QDRANT_URL", "senza-schema")
    assert ricerca.main(["pollo"]) == 2


# --- Modifica A: filtro --solo-dosi ---

def test_solo_dosi(qdrant, finto):
    risultati = cerca("dosi della gelatina", EmbedderFinto(), qdrant, "ricette", k=5, solo_dosi=True)
    assert 1 <= len(risultati) <= 5
    assert all(r.contiene_dosi is True for r in risultati)
    assert {"key": "contiene_dosi", "match": {"value": True}} in query_inviate(finto)[-1][2]["filter"]["must"]


def test_solo_dosi_e_capitolo(qdrant):
    risultati = cerca("ricotta e parmigiano", EmbedderFinto(), qdrant, "ricette", k=5,
                      capitolo="Minestre in brodo", solo_dosi=True)
    assert risultati
    assert all(r.capitolo == "Minestre in brodo" and r.contiene_dosi for r in risultati)


def test_senza_filtro_anche_chunk_senza_dosi(qdrant):
    risultati = cerca("pollo", EmbedderFinto(), qdrant, "ricette", k=20)
    assert {r.contiene_dosi for r in risultati} == {True, False}


def test_solo_dosi_senza_campo(qdrant, finto, capsys):
    punti = finto.collezioni["ricette"]["punti"]
    for i, (v, p) in list(punti.items()):
        punti[i] = (v, {k: x for k, x in p.items() if k != "contiene_dosi"})
    with pytest.raises(ErroreRicerca, match="--solo-payload"):
        cerca("gelatina", EmbedderFinto(), qdrant, "ricette", solo_dosi=True)
    assert query_inviate(finto) == []


def test_formatta_mostra_dosi():
    assert "dosi: sì" in formatta([Risultato(1, 0.5, 2, "Gelatina", "Brodi", 0, "testo", True)])
    assert "dosi: no" in formatta([Risultato(1, 0.5, 4, "Pollo fritto", "Fritti", 0, "testo", False)])


def test_main_solo_dosi(ambiente, capsys):
    assert ricerca.main(["ricotta", "--solo-dosi", "--capitolo", "Minestre in brodo", "--k", "3"]) == 0
    uscita = capsys.readouterr().out
    assert "Cappelletti" in uscita and "dosi: no" not in uscita


def test_main_solo_dosi_senza_campo(ambiente, finto, capsys):
    punti = finto.collezioni["ricette"]["punti"]
    for i, (v, p) in list(punti.items()):
        punti[i] = (v, {k: x for k, x in p.items() if k != "contiene_dosi"})
    assert ricerca.main(["ricotta", "--solo-dosi"]) == 4
    assert "--solo-payload" in capsys.readouterr().err


def test_ricerca_restituisce_il_testo_originale(qdrant):
    # Modifica B: l'intestazione va solo all'embedder, i risultati mostrano il chunk originale.
    risultati = cerca("pollo fritto", EmbedderFinto(), qdrant, "ricette", k=K_MASSIMO)
    assert risultati
    assert all(not r.testo.startswith("Ricetta: ") and "Capitolo: " not in r.testo for r in risultati)
