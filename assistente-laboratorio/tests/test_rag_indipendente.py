"""Il pacchetto rag non dipende dall'agente né dalle API (lezione 7)."""

# COSA PROVA QUESTO FILE
# rag/ è un pacchetto a sé, come backend/ e frontend/: nessun suo modulo importa assistente,
# backend o frontend. Lo si verifica leggendo il codice con il modulo ast, senza eseguirlo.

from pathlib import Path

from test_backend_indipendente import moduli_importati

CARTELLA_RAG = Path(__file__).resolve().parent.parent / "rag"
VIETATI = ("assistente", "backend", "frontend")


def test_rag_non_importa_gli_altri_pacchetti():
    file = sorted(CARTELLA_RAG.glob("*.py"))
    assert {f.name for f in file} >= {"configurazione.py", "corpus.py", "chunking.py", "embedding.py",
                                      "qdrant.py", "ingestion.py", "ricerca.py", "valutazione.py"}
    for f in file:
        vietati = [m for m in moduli_importati(f) if m.split(".")[0] in VIETATI]
        assert vietati == [], f"{f.name} importa {vietati}"
