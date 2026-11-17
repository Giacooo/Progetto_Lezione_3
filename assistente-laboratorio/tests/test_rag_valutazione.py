"""Valutazione con domande e fonte attesa (lezione 7, esercizio 1; pag. 21-22 e 27)."""

# COSA PROVA QUESTO FILE
# Il file delle 11 domande approvate, il calcolo di posizione e score della fonte attesa, la
# tabella Markdown (riproducibile) e il riepilogo "fonte attesa trovata in X casi su Y".
# Le ricerche sono finte (risultati fissi), tranne l'ultimo test, che usa l'indice finto.

import pytest
from finti_rag import CORPUS_PROVA, EmbedderFinto, QdrantFinto, client_finto

from rag import valutazione
from rag.configurazione import ConfigurazioneRag
from rag.ingestion import esegui_ingestion
from rag.ricerca import Risultato, cerca
from rag.valutazione import Domanda, Riga, carica_domande, tabella_markdown, valuta


def risultato(classifica: int, numero: int, score: float) -> Risultato:
    return Risultato(classifica, score, numero, f"Ricetta {numero}", "Capitolo", 0, "testo")


RISULTATI = [risultato(1, 10, 0.9), risultato(2, 20, 0.8), risultato(3, 89, 0.7), risultato(4, 89, 0.6)]


def test_domande_della_specifica():
    domande = carica_domande()
    assert len(domande) == 11
    assert domande[0] == Domanda("Quanta farina serve per 400 grammi di patate negli gnocchi?", [89])
    assert domande[1].attese == [7]
    assert domande[2] == Domanda("Che vino si usa per il pollo alla cacciatora?", [208])
    assert domande[3].attese == [89]
    assert domande[4] == Domanda("Come si chiama il cacciucco sulle coste dell'Adriatico?", [455, 456])
    assert domande[5] == Domanda("Qual è la ricetta del tiramisù?", [])
    assert domande[6] == Domanda("Con quale spezia si colora il riso tipico della Lombardia?", [78, 79, 80])
    assert domande[7] == Domanda(
        "Come preparare in estate una scorta di passata rossa da usare tutto l'anno?", [732])
    assert domande[8] == Domanda("Da quale paese arriva la bevanda scura che si beve per svegliarsi?", [776])
    assert domande[9] == Domanda("Quale vino dolce si aggiunge alla crema spumosa fatta con i tuorli?", [722])
    assert domande[10] == Domanda("Qual è la ricetta della carbonara?", [])
    assert sum(1 for d in domande if d.attese) == 9


def test_posizione_e_score_della_fonte():
    [riga] = valuta([Domanda("gnocchi?", [89])], lambda testo: RISULTATI)
    assert riga == Riga(Domanda("gnocchi?", [89]), 3, 0.7, 0.9)


def test_fonte_assente():
    [riga] = valuta([Domanda("cacciucco?", [455, 456])], lambda testo: RISULTATI)
    assert riga.posizione is None and riga.score_fonte is None
    assert "| assente |" in tabella_markdown([riga])


def test_domanda_senza_risposta():
    [riga] = valuta([Domanda("tiramisù?", [])], lambda testo: RISULTATI)
    testo = tabella_markdown([riga])
    assert "| nessuna | — | — | 0.9000 |" in testo


def test_tabella_e_riepilogo():
    righe = valuta([Domanda("gnocchi?", [89]), Domanda("cacciucco?", [455, 456]), Domanda("tiramisù?", [])],
                   lambda testo: RISULTATI)
    testo = tabella_markdown(righe)
    linee = testo.splitlines()
    assert linee[0] == "| # | Domanda | Fonte attesa | Posizione | Score fonte | Score migliore |"
    assert linee[2] == "| 1 | gnocchi? | N. 89 | 3 | 0.7000 | 0.9000 |"
    assert linee[3] == "| 2 | cacciucco? | N. 455, 456 | assente | — | 0.9000 |"
    assert linee[-1] == "Fonte attesa trovata in 1 casi su 2."


def test_tabella_riproducibile():
    domande = carica_domande()
    assert tabella_markdown(valuta(domande, lambda t: RISULTATI)) == tabella_markdown(valuta(domande, lambda t: RISULTATI))


def test_nessun_risultato():
    [riga] = valuta([Domanda("tiramisù?", [])], lambda testo: [])
    assert "| nessuna | — | — | — |" in tabella_markdown([riga])


def test_valutazione_sul_qdrant_finto(tmp_path):
    libro = tmp_path / "artusi.txt"
    libro.write_text(CORPUS_PROVA, encoding="utf-8")
    config = ConfigurazioneRag("http://lm:1234/v1", "finto", "http://q:6333", "ricette", libro,
                               "paragrafi", 1200, 200, "INFO")
    qdrant = client_finto(QdrantFinto())
    esegui_ingestion(config, EmbedderFinto(), qdrant, ricette_attese=5)
    righe = valuta(carica_domande(), lambda testo: cerca(testo, EmbedderFinto(), qdrant, "ricette", k=5))
    assert len(righe) == 11
    # Nel libro finto le ricette attese (numeri del libro vero) non ci sono: tutte "assente".
    assert all(r.posizione is None for r in righe)
    testo = tabella_markdown(righe)
    assert len([l for l in testo.splitlines() if l.startswith("| ") and l[2].isdigit()]) == 11


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for nome, valore in {"LM_BASE_URL": "http://lm:1234/v1", "EMBEDDING_MODELLO": "finto"}.items():
        monkeypatch.setenv(nome, valore)


def test_main_ok(ambiente, monkeypatch, capsys):
    monkeypatch.setattr(valutazione, "cerca_con", lambda config: (lambda testo: RISULTATI))
    assert valutazione.main() == 0
    uscita = capsys.readouterr().out
    assert "| # | Domanda |" in uscita
    assert "casi su 9." in uscita


def test_main_collezione_assente(ambiente, monkeypatch, capsys):
    qdrant = client_finto(QdrantFinto())
    monkeypatch.setattr(valutazione, "crea_embedder", lambda config: EmbedderFinto())
    monkeypatch.setattr(valutazione, "crea_qdrant", lambda config: qdrant)
    assert valutazione.main() == 4
    assert "rag.ingestion" in capsys.readouterr().err
