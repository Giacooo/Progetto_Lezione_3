"""Ingestion sul Qdrant finto in memoria (lezione 7, esercizio 1)."""

# COSA PROVA QUESTO FILE
# Lo script di ingestion con embedder finto e Qdrant finto (nessun servizio acceso): un punto
# per chunk, payload completo, ID stabili, due ingestion con lo stesso numero di punti
# (evidenza del PDF), pulizia dei punti avanzati, modello registrato e cambio bloccato, nessuna
# scrittura quando qualcosa va storto. In fondo i codici di uscita di "python -m rag.ingestion".

import pytest
from finti_rag import CORPUS_PROVA, EmbedderFinto, QdrantFinto, client_finto

from rag import ingestion
from rag.configurazione import ConfigurazioneRag
from rag.corpus import ErroreCorpus
from rag.embedding import ErroreEmbedding, LMStudioNonRaggiungibile
from rag.ingestion import FONTE, CambioBloccato, esegui_ingestion, id_punto
from rag.qdrant import QdrantNonRaggiungibile


def configurazione(tmp_path, testo=CORPUS_PROVA, **altro) -> ConfigurazioneRag:
    libro = tmp_path / "artusi.txt"
    libro.write_text(testo, encoding="utf-8")
    valori = dict(lm_base_url="http://lm:1234/v1", embedding_modello="finto", qdrant_url="http://q:6333",
                  collezione="ricette", corpus_file=libro, strategia="paragrafi", dimensione=1200,
                  overlap=200, log_level="INFO")
    return ConfigurazioneRag(**{**valori, **altro})


def senza_ricetta(numero: int) -> str:
    """Il libro finto senza la ricetta `numero` (che è l'ultima del suo capitolo)."""
    righe = CORPUS_PROVA.split("\n")
    inizio = righe.index(f"{numero}. Fritto di cervello") if numero == 5 else None
    assert inizio is not None
    fine = righe.index("APPENDICE")
    return "\n".join(righe[:inizio] + ["", ""] + righe[fine:])


@pytest.fixture
def finto():
    return QdrantFinto()


@pytest.fixture
def qdrant(finto):
    return client_finto(finto)


def scritture(finto, dopo=0):
    """Le richieste che cambiano qualcosa: tutti i PUT (collezione, indice, punti) e le cancellazioni."""
    return [r for r in finto.richieste[dopo:] if r[0] == "PUT" or r[1].endswith("/points/delete")]


def test_un_punto_per_chunk(tmp_path, qdrant):
    esito = esegui_ingestion(configurazione(tmp_path), EmbedderFinto(), qdrant, ricette_attese=5)
    assert esito.ricette == 5
    assert esito.chunk >= 6  # la ricetta 3 è lunga: più di un chunk
    assert (esito.punti_prima, esito.punti_dopo, esito.eliminati) == (0, esito.chunk, 0)


def test_payload_completo(tmp_path, qdrant, finto):
    esegui_ingestion(configurazione(tmp_path), EmbedderFinto(), qdrant, ricette_attese=5)
    _, payload = finto.collezioni["ricette"]["punti"][id_punto("ricetta-004", 0)]
    assert payload == {
        "documento_id": "ricetta-004",
        "numero": 4,
        "titolo": "Pollo fritto",
        "capitolo": "Fritti",
        "posizione": 0,
        "testo": "Tagliate il pollo a pezzi, infarinatelo e friggetelo nell'olio bollente "
                 "finché non prende un bel colore dorato.",
        "fonte": FONTE,
    }
    assert FONTE == "Artusi, La scienza in cucina e l'arte di mangiar bene (1891), Project Gutenberg n. 59047"
    posizioni = sorted(p["posizione"] for _, p in finto.collezioni["ricette"]["punti"].values()
                       if p["numero"] == 3)
    assert posizioni == list(range(len(posizioni))) and len(posizioni) >= 2


def test_id_stabili(tmp_path, qdrant, finto):
    assert id_punto("ricetta-089", 0) == id_punto("ricetta-089", 0)
    assert id_punto("ricetta-089", 0) != id_punto("ricetta-089", 1)
    assert id_punto("ricetta-089", 0) != id_punto("ricetta-090", 0)
    esegui_ingestion(configurazione(tmp_path), EmbedderFinto(), qdrant, ricette_attese=5)
    for pid, (_, payload) in finto.collezioni["ricette"]["punti"].items():
        assert pid == id_punto(payload["documento_id"], payload["posizione"])


def test_due_ingestion_stesso_numero_di_punti(tmp_path, qdrant):
    config = configurazione(tmp_path)
    prima = esegui_ingestion(config, EmbedderFinto(), qdrant, ricette_attese=5)
    seconda = esegui_ingestion(config, EmbedderFinto(), qdrant, ricette_attese=5)
    assert seconda.chunk == prima.chunk
    assert seconda.punti_prima == seconda.punti_dopo == prima.punti_dopo == prima.chunk
    assert seconda.eliminati == 0


def test_punti_avanzati_eliminati(tmp_path, qdrant, finto):
    esegui_ingestion(configurazione(tmp_path, dimensione=400, overlap=80), EmbedderFinto(), qdrant, ricette_attese=5)
    esito = esegui_ingestion(configurazione(tmp_path, dimensione=4000, overlap=80), EmbedderFinto(), qdrant,
                             ricette_attese=5)
    assert esito.eliminati > 0
    assert esito.punti_dopo == esito.chunk == 5
    esito = esegui_ingestion(configurazione(tmp_path, testo=senza_ricetta(5), dimensione=4000, overlap=80),
                             EmbedderFinto(), qdrant, ricette_attese=4)
    assert esito.punti_dopo == 4
    numeri = {p["numero"] for _, p in finto.collezioni["ricette"]["punti"].values()}
    assert numeri == {1, 2, 3, 4}


def test_metadati_e_indice(tmp_path, qdrant, finto):
    esegui_ingestion(configurazione(tmp_path), EmbedderFinto(), qdrant, ricette_attese=5)
    assert finto.collezioni["ricette"]["metadati"] == {"embedding_modello": "finto", "embedding_dimensione": 32}
    assert finto.collezioni["ricette"]["indici"] == {"capitolo": "keyword"}


def test_indice_ricreato_se_manca(tmp_path, qdrant, finto):
    """Se la creazione dell'indice era fallita, l'ingestion successiva lo crea."""
    esegui_ingestion(configurazione(tmp_path), EmbedderFinto(), qdrant, ricette_attese=5)
    finto.collezioni["ricette"]["indici"] = {}
    esegui_ingestion(configurazione(tmp_path), EmbedderFinto(), qdrant, ricette_attese=5)
    assert finto.collezioni["ricette"]["indici"] == {"capitolo": "keyword"}
    assert qdrant.capitoli("ricette")


def test_cambio_bloccato_modello(tmp_path, qdrant, finto):
    esegui_ingestion(configurazione(tmp_path), EmbedderFinto(), qdrant, ricette_attese=5)
    dopo = len(finto.richieste)
    altro = EmbedderFinto(modello="altro-modello")
    with pytest.raises(CambioBloccato) as e:
        esegui_ingestion(configurazione(tmp_path, embedding_modello="altro-modello"), altro, qdrant, ricette_attese=5)
    assert "finto" in str(e.value) and "altro-modello" in str(e.value)
    assert "QDRANT_COLLEZIONE" in str(e.value)
    assert altro.chiamate == []
    assert scritture(finto, dopo) == []


def test_cambio_bloccato_dimensione(tmp_path, qdrant, finto):
    esegui_ingestion(configurazione(tmp_path), EmbedderFinto(), qdrant, ricette_attese=5)
    dopo = len(finto.richieste)
    with pytest.raises(CambioBloccato, match="64"):
        esegui_ingestion(configurazione(tmp_path), EmbedderFinto(dimensione=64), qdrant, ricette_attese=5)
    assert scritture(finto, dopo) == []


def test_collezione_senza_metadati_bloccata(tmp_path, qdrant, finto):
    finto.collezioni["ricette"] = {"dimensione": 32, "metadati": {}, "indici": {}, "punti": {}}
    embedder = EmbedderFinto()
    with pytest.raises(CambioBloccato):
        esegui_ingestion(configurazione(tmp_path), embedder, qdrant, ricette_attese=5)
    assert embedder.chiamate == []
    assert scritture(finto) == []


def test_corpus_con_buchi(tmp_path, qdrant, finto):
    embedder = EmbedderFinto()
    with pytest.raises(ErroreCorpus, match="mancanti: 6"):
        esegui_ingestion(configurazione(tmp_path), embedder, qdrant, ricette_attese=6)
    assert embedder.chiamate == []
    assert finto.richieste == []


def test_ingestion_lm_studio_in_errore_non_tocca_la_collezione(tmp_path, qdrant, finto):
    class EmbedderCheCade(EmbedderFinto):
        def calcola(self, testi):
            if self.chiamate:
                raise ErroreEmbedding("LM Studio ha risposto 400 per il modello 'finto'")
            return super().calcola(testi)

    with pytest.raises(ErroreEmbedding):
        esegui_ingestion(configurazione(tmp_path, dimensione=200, overlap=20), EmbedderCheCade(), qdrant,
                         ricette_attese=5, lotto_embedding=2)
    assert finto.collezioni == {}
    assert scritture(finto) == []


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    (tmp_path / "dati").mkdir()
    (tmp_path / "dati" / "artusi.txt").write_text(CORPUS_PROVA, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    valori = {"LM_BASE_URL": "http://lm:1234/v1", "EMBEDDING_MODELLO": "finto", "QDRANT_URL": "http://q:6333",
              "QDRANT_COLLEZIONE": "ricette", "CORPUS_FILE": "dati/artusi.txt", "CHUNK_STRATEGIA": "paragrafi",
              "CHUNK_DIMENSIONE": "1200", "CHUNK_OVERLAP": "200", "LOG_LEVEL": "INFO"}
    for nome, valore in valori.items():
        monkeypatch.setenv(nome, valore)
    monkeypatch.setattr(ingestion, "RICETTE_ATTESE", 5)
    finto = QdrantFinto()
    monkeypatch.setattr(ingestion, "crea_embedder", lambda config: EmbedderFinto())
    monkeypatch.setattr(ingestion, "crea_qdrant", lambda config: client_finto(finto))
    return finto


def test_main_ok(ambiente, capsys):
    assert ingestion.main() == 0
    uscita = capsys.readouterr().out
    assert "ricette lette: 5" in uscita
    assert "punti dopo:" in uscita


def test_main_configurazione_non_valida(ambiente, monkeypatch, capsys):
    monkeypatch.setenv("CHUNK_DIMENSIONE", "0")
    assert ingestion.main() == 2
    assert "CHUNK_DIMENSIONE" in capsys.readouterr().err


@pytest.mark.parametrize("errore", [QdrantNonRaggiungibile("Qdrant non raggiungibile"),
                                    LMStudioNonRaggiungibile("LM Studio non raggiungibile")])
def test_main_servizio_spento(ambiente, monkeypatch, capsys, errore):
    def fallisce(*args, **kwargs):
        raise errore

    monkeypatch.setattr(ingestion, "esegui_ingestion", fallisce)
    assert ingestion.main() == 3
    assert "non raggiungibile" in capsys.readouterr().err


def test_main_cambio_bloccato(ambiente, monkeypatch, capsys):
    assert ingestion.main() == 0
    monkeypatch.setattr(ingestion, "crea_embedder", lambda config: EmbedderFinto(modello="altro"))
    monkeypatch.setenv("EMBEDDING_MODELLO", "altro")
    assert ingestion.main() == 4
    assert "altro" in capsys.readouterr().err
