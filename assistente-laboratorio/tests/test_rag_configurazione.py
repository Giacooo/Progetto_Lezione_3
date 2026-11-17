"""Configurazione del pacchetto rag (lezione 7, esercizio 1)."""

# COSA PROVA QUESTO FILE
# Valori predefiniti, variabili obbligatorie, valori non validi e precedenza dell'ambiente sul
# file .env, come per le configurazioni di agente, back-end e front-end. In fondo controlla che
# la cartella dati/ (dove sta il libro scaricato) sia esclusa da Git e dalle immagini Docker.

from pathlib import Path

import pytest

from rag.configurazione import ErroreConfigurazioneRag, carica_configurazione, leggi_ambiente

CARTELLA_PROGETTO = Path(__file__).resolve().parent.parent
MINIME = {"LM_BASE_URL": "http://localhost:1234/v1", "EMBEDDING_MODELLO": "text-embedding-nomic-embed-text-v1.5"}


def test_predefiniti(tmp_path):
    config = carica_configurazione(MINIME, tmp_path)
    assert config.lm_base_url == "http://localhost:1234/v1"
    assert config.embedding_modello == "text-embedding-nomic-embed-text-v1.5"
    assert config.qdrant_url == "http://127.0.0.1:6333"
    assert config.collezione == "ricette"
    assert config.corpus_file == tmp_path / "dati" / "artusi.txt"
    assert config.strategia == "paragrafi"
    assert config.dimensione == 1200
    assert config.overlap == 200
    assert config.log_level == "INFO"


def test_obbligatorie_mancanti(tmp_path):
    with pytest.raises(ErroreConfigurazioneRag) as errore:
        carica_configurazione({}, tmp_path)
    assert "LM_BASE_URL" in str(errore.value)
    assert "EMBEDDING_MODELLO" in str(errore.value)


@pytest.mark.parametrize(
    ("nome", "valore"),
    [
        ("CHUNK_STRATEGIA", "frasi"),
        ("CHUNK_DIMENSIONE", "0"),
        ("CHUNK_DIMENSIONE", "abc"),
        ("CHUNK_OVERLAP", "-1"),
        ("CHUNK_OVERLAP", "1200"),
        ("QDRANT_URL", "localhost:6333"),
        ("LOG_LEVEL", "TROPPO"),
    ],
)
def test_valori_non_validi(tmp_path, nome, valore):
    with pytest.raises(ErroreConfigurazioneRag) as errore:
        carica_configurazione({**MINIME, nome: valore}, tmp_path)
    assert nome in str(errore.value)


def test_valori_impostati(tmp_path):
    config = carica_configurazione(
        {**MINIME, "CHUNK_STRATEGIA": "finestra", "CHUNK_DIMENSIONE": "800", "CHUNK_OVERLAP": "0",
         "CORPUS_FILE": str(tmp_path / "libro.txt"), "QDRANT_COLLEZIONE": "prova"},
        tmp_path,
    )
    assert (config.strategia, config.dimensione, config.overlap) == ("finestra", 800, 0)
    assert config.corpus_file == tmp_path / "libro.txt"
    assert config.collezione == "prova"


def test_barra_finale_tolta(tmp_path):
    config = carica_configurazione(
        {**MINIME, "LM_BASE_URL": "http://x:1234/v1/", "QDRANT_URL": "http://q:6333/"}, tmp_path)
    assert config.lm_base_url == "http://x:1234/v1"
    assert config.qdrant_url == "http://q:6333"


def test_ambiente_prevale_sul_file(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("EMBEDDING_MODELLO=dal-file\nQDRANT_COLLEZIONE=dal-file\n", encoding="utf-8")
    monkeypatch.setenv("EMBEDDING_MODELLO", "dall-ambiente")
    monkeypatch.delenv("QDRANT_COLLEZIONE", raising=False)
    ambiente = leggi_ambiente(tmp_path)
    assert ambiente["EMBEDDING_MODELLO"] == "dall-ambiente"
    assert ambiente["QDRANT_COLLEZIONE"] == "dal-file"


def test_dati_ignorati():
    for nome in (".gitignore", ".dockerignore"):
        righe = (CARTELLA_PROGETTO / nome).read_text(encoding="utf-8").splitlines()
        assert "dati/" in righe, nome
    esempio = (CARTELLA_PROGETTO / ".env.example").read_text(encoding="utf-8")
    assert "EMBEDDING_MODELLO=" in esempio
    assert "QDRANT_URL=" in esempio
