"""Servizi qdrant e ingestion in compose.yaml e immagine del RAG (lezione 7)."""

# COSA PROVA QUESTO FILE
# Come tests/test_docker_compose.py (di cui riusa la lettura della configurazione risolta con
# "docker compose config", solo lettura): Qdrant con l'immagine ufficiale, la porta solo su
# 127.0.0.1 e il volume; il servizio di ingestion con il profilo "rag", gli indirizzi della rete
# di Docker e il libro montato in sola lettura. Senza Docker questi test vengono saltati, tranne
# quello sul testo di rag/Dockerfile.

from pathlib import Path, PurePosixPath

from test_docker_compose import _configurazione

CARTELLA_PROGETTO = Path(__file__).resolve().parent.parent


def test_qdrant(tmp_path):
    config = _configurazione(tmp_path)
    qdrant = config["services"]["qdrant"]
    assert qdrant["image"] == "qdrant/qdrant:v1.20.2"
    assert "build" not in qdrant
    assert "profiles" not in qdrant
    [porta] = qdrant["ports"]
    assert (porta["host_ip"], str(porta["published"]), porta["target"]) == ("127.0.0.1", "6333", 6333)
    [volume] = qdrant["volumes"]
    assert (volume["type"], volume["source"], volume["target"]) == ("volume", "dati-qdrant", "/qdrant/storage")
    assert "dati-qdrant" in config["volumes"]


def test_ingestion_non_parte_con_up(tmp_path):
    assert "ingestion" not in _configurazione(tmp_path)["services"]


def test_ingestion_con_profilo(tmp_path):
    ingestion = _configurazione(tmp_path, "rag")["services"]["ingestion"]
    assert ingestion["profiles"] == ["rag"]
    assert PurePosixPath(ingestion["build"]["dockerfile"].replace("\\", "/")).as_posix() == "rag/Dockerfile"
    assert ingestion["command"] == ["python", "-m", "rag.ingestion"]
    ambiente = ingestion["environment"]
    assert ambiente["QDRANT_URL"] == "http://qdrant:6333"
    assert ambiente["LM_BASE_URL"] == "http://host.docker.internal:1234/v1"
    assert ambiente["CORPUS_FILE"] == "dati/artusi.txt"
    assert any("host-gateway" in str(voce) for voce in ingestion["extra_hosts"])
    [libro] = [v for v in ingestion["volumes"] if v["type"] == "bind"]
    assert libro["target"] == "/app/dati"
    assert libro["read_only"] is True
    assert "qdrant" in ingestion["depends_on"]
    assert "ports" not in ingestion


def test_dockerfile_rag():
    righe = [r.strip() for r in (CARTELLA_PROGETTO / "rag" / "Dockerfile").read_text(encoding="utf-8").splitlines()]
    assert "FROM python:3.13-slim" in righe
    assert "WORKDIR /app" in righe
    assert [r for r in righe if r.startswith("COPY")] == ["COPY requirements.txt .", "COPY rag ./rag"]
    assert 'CMD ["python", "-m", "rag.ingestion"]' in righe
