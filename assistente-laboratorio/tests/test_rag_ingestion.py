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
from rag.ingestion import (FONTE, CambioBloccato, PayloadNonAggiornabile, aggiorna_payload, contiene_dosi,
                           esegui_ingestion, id_punto)
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
        "contiene_dosi": False,
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


INDICI = {"capitolo": "keyword", "contiene_dosi": "bool"}


def test_metadati_e_indice(tmp_path, qdrant, finto):
    esegui_ingestion(configurazione(tmp_path), EmbedderFinto(), qdrant, ricette_attese=5)
    assert finto.collezioni["ricette"]["metadati"] == {"embedding_modello": "finto", "embedding_dimensione": 32}
    assert finto.collezioni["ricette"]["indici"] == INDICI


def test_indice_ricreato_se_manca(tmp_path, qdrant, finto):
    """Se la creazione dell'indice era fallita, l'ingestion successiva lo crea."""
    esegui_ingestion(configurazione(tmp_path), EmbedderFinto(), qdrant, ricette_attese=5)
    finto.collezioni["ricette"]["indici"] = {}
    esegui_ingestion(configurazione(tmp_path), EmbedderFinto(), qdrant, ricette_attese=5)
    assert finto.collezioni["ricette"]["indici"] == INDICI
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
    assert "testo indicizzato: titolo e capitolo + chunk" in uscita


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


# --- Modifica A: campo contiene_dosi e --solo-payload ---

def punti_per_ricetta(finto, numero):
    return [(v, p) for v, p in finto.collezioni["ricette"]["punti"].values() if p["numero"] == numero]


def test_campo_contiene_dosi(tmp_path, qdrant, finto):
    esegui_ingestion(configurazione(tmp_path), EmbedderFinto(), qdrant, ricette_attese=5)
    assert all(isinstance(p["contiene_dosi"], bool) for _, p in finto.collezioni["ricette"]["punti"].values())
    assert all(p["contiene_dosi"] for _, p in punti_per_ricetta(finto, 2))
    for numero in (1, 4, 5):
        assert not any(p["contiene_dosi"] for _, p in punti_per_ricetta(finto, numero))


def test_overlap_parziale_non_conta():
    riga = "Parmigiano grattato, grammi 30."
    assert not contiene_dosi("grammi 30.\nUova, uno intero e un rosso.", (riga,))
    assert contiene_dosi(f"Ricotta.\n{riga}\nUova.", (riga,))
    assert not contiene_dosi(riga, ())


def togli_campo(finto):
    punti = finto.collezioni["ricette"]["punti"]
    for i, (v, p) in list(punti.items()):
        punti[i] = (v, {k: x for k, x in p.items() if k != "contiene_dosi"})
    finto.collezioni["ricette"]["indici"].pop("contiene_dosi", None)


def test_solo_payload_aggiunge_il_campo(tmp_path, qdrant, finto):
    config = configurazione(tmp_path)
    esegui_ingestion(config, EmbedderFinto(), qdrant, ricette_attese=5)
    atteso = {i: p["contiene_dosi"] for i, (_, p) in finto.collezioni["ricette"]["punti"].items()}
    vettori = {i: v for i, (v, _) in finto.collezioni["ricette"]["punti"].items()}
    togli_campo(finto)
    dopo = len(finto.richieste)
    esito = aggiorna_payload(config, qdrant, ricette_attese=5)
    punti = finto.collezioni["ricette"]["punti"]
    assert {i: p["contiene_dosi"] for i, (_, p) in punti.items()} == atteso
    assert {i: v for i, (v, _) in punti.items()} == vettori
    nuove = finto.richieste[dopo:]
    assert not any(r[1].endswith("/points") or r[1].endswith("/points/delete") for r in nuove)
    assert esito.punti_prima == esito.punti_dopo == esito.punti == len(punti)
    assert esito.con_dosi + esito.senza_dosi == esito.punti
    assert esito.con_dosi == sum(atteso.values()) > 0
    assert finto.collezioni["ricette"]["indici"] == INDICI


def test_solo_payload_collezione_assente(tmp_path, qdrant, finto):
    with pytest.raises(PayloadNonAggiornabile, match="ingestion completa"):
        aggiorna_payload(configurazione(tmp_path), qdrant, ricette_attese=5)
    assert scritture(finto) == []


def test_solo_payload_id_diversi(tmp_path, qdrant, finto):
    esegui_ingestion(configurazione(tmp_path, dimensione=4000), EmbedderFinto(), qdrant, ricette_attese=5)
    dopo = len(finto.richieste)
    with pytest.raises(PayloadNonAggiornabile, match="ingestion completa"):
        aggiorna_payload(configurazione(tmp_path, dimensione=400, overlap=80), qdrant, ricette_attese=5)
    assert scritture(finto, dopo) == []
    assert not any(r[1].endswith("/points/payload") for r in finto.richieste[dopo:])


def test_solo_payload_modello_diverso(tmp_path, qdrant, finto):
    esegui_ingestion(configurazione(tmp_path), EmbedderFinto(), qdrant, ricette_attese=5)
    dopo = len(finto.richieste)
    with pytest.raises(CambioBloccato):
        aggiorna_payload(configurazione(tmp_path, embedding_modello="altro-modello"), qdrant, ricette_attese=5)
    assert scritture(finto, dopo) == []
    assert not any(r[1].endswith("/points/payload") for r in finto.richieste[dopo:])


def test_main_solo_payload_senza_embedder(ambiente, monkeypatch, capsys):
    assert ingestion.main([]) == 0
    togli_campo(ambiente)

    def vietato(config):
        raise AssertionError("--solo-payload non deve creare l'embedder")

    monkeypatch.setattr(ingestion, "crea_embedder", vietato)
    assert ingestion.main(["--solo-payload"]) == 0
    uscita = capsys.readouterr().out
    assert "punti aggiornati:" in uscita and "con dosi:" in uscita and "senza dosi:" in uscita
    assert all("contiene_dosi" in p for _, p in ambiente.collezioni["ricette"]["punti"].values())


def test_main_solo_payload_collezione_assente(ambiente, capsys):
    assert ingestion.main(["--solo-payload"]) == 4
    assert "ingestion completa" in capsys.readouterr().err


def test_solo_payload_stessi_id_testo_diverso(tmp_path, qdrant, finto):
    """Overlap appena diverso: stessi ID ma testi diversi -> serve l'ingestion completa."""
    esegui_ingestion(configurazione(tmp_path, dimensione=400, overlap=80), EmbedderFinto(), qdrant, ricette_attese=5)
    ids = set(finto.collezioni["ricette"]["punti"])
    punti = finto.collezioni["ricette"]["punti"]
    primo = sorted(ids)[0]
    vettore, payload = punti[primo]
    punti[primo] = (vettore, {**payload, "testo": payload["testo"] + " (versione vecchia)"})
    dopo = len(finto.richieste)
    with pytest.raises(PayloadNonAggiornabile, match="ingestion completa"):
        aggiorna_payload(configurazione(tmp_path, dimensione=400, overlap=80), qdrant, ricette_attese=5)
    assert scritture(finto, dopo) == []
    assert not any(r[1].endswith("/points/payload") for r in finto.richieste[dopo:])


# --- Modifica B: titolo e capitolo davanti al testo indicizzato ---

def test_testo_da_indicizzare():
    assert ingestion.testo_da_indicizzare("Pollo fritto", "Fritti", "Tagliate il pollo.") == (
        "Ricetta: Pollo fritto\nCapitolo: Fritti\n\nTagliate il pollo.")


def test_testo_passato_all_embedder(tmp_path, qdrant, finto):
    config = configurazione(tmp_path)
    embedder = EmbedderFinto()
    esegui_ingestion(config, embedder, qdrant, ricette_attese=5)
    passati = [t for lotto in embedder.chiamate for t in lotto]
    # Stesso ordine dei punti preparati, uno per punto: intestazione + testo originale.
    payload_in_ordine = [p for _, p in ingestion.prepara_punti(config, 5)[1]]
    assert passati == [ingestion.testo_da_indicizzare(p["titolo"], p["capitolo"], p["testo"]) for p in payload_in_ordine]
    # Ogni chunk (anche quelli dopo il primo della ricetta 3) ha l'intestazione una volta sola, in testa:
    # l'overlap non la ripete, perché non fa parte del testo del chunk.
    assert sum(1 for p in payload_in_ordine if p["numero"] == 3) >= 2
    assert all(t.startswith("Ricetta: ") and t.count("Ricetta: ") == 1 and t.count("Capitolo: ") == 1
               for t in passati)
    # Il payload salvato in Qdrant ha il testo originale, senza intestazione.
    salvati = [p for _, p in finto.collezioni["ricette"]["punti"].values()]
    assert all(not p["testo"].startswith("Ricetta: ") and "Capitolo: " not in p["testo"] for p in salvati)


def test_ricalcolo_senza_ricreare_la_collezione(tmp_path, qdrant, finto, monkeypatch):
    config = configurazione(tmp_path)
    # Collezione "prima di B": embedding del solo testo, con lo stesso modello.
    monkeypatch.setattr(ingestion, "testo_da_indicizzare", lambda titolo, capitolo, testo: testo)
    esegui_ingestion(config, EmbedderFinto(), qdrant, ricette_attese=5)
    prima = {pid: v for pid, (v, _) in finto.collezioni["ricette"]["punti"].items()}
    monkeypatch.undo()
    n = len(finto.richieste)
    esito = esegui_ingestion(config, EmbedderFinto(), qdrant, ricette_attese=5)
    dopo = {pid: v for pid, (v, _) in finto.collezioni["ricette"]["punti"].items()}
    assert not any(m == "PUT" and p == "/collections/ricette" for m, p, _ in finto.richieste[n:])
    assert dopo.keys() == prima.keys()
    assert esito.punti_prima == esito.punti_dopo == len(prima) and esito.eliminati == 0
    assert all(dopo[pid] != prima[pid] for pid in prima)


def test_solo_payload_dopo_ingestion_b(tmp_path, qdrant, finto):
    config = configurazione(tmp_path)
    esegui_ingestion(config, EmbedderFinto(), qdrant, ricette_attese=5)
    esito = aggiorna_payload(config, qdrant, ricette_attese=5)
    assert esito.punti_prima == esito.punti_dopo == esito.punti


def test_ricetta_senza_chunk_segnalata(tmp_path, qdrant, caplog):
    corpo = "Il cervello si lessa, si taglia a pezzetti e si frigge nell'olio\ndopo averlo passato nell'uovo e nel pangrattato.\n"
    assert corpo in CORPUS_PROVA
    with caplog.at_level("WARNING", logger="rag.ingestion"):
        esito = esegui_ingestion(configurazione(tmp_path, CORPUS_PROVA.replace(corpo, "")), EmbedderFinto(), qdrant,
                                 ricette_attese=5)
    assert esito.ricette == 5
    assert "ricetta 5 (Fritto di cervello): nessun chunk" in caplog.text
