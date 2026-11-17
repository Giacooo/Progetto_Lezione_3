"""Controlli sui file Docker dei tre componenti (lezione 6, step 9)."""

# COSA PROVA QUESTO FILE
# Legge come testo i tre Dockerfile (agente nella radice, back-end, front-end) e .dockerignore,
# senza usare Docker: ogni immagine deve contenere solo il proprio pacchetto e avviarlo con il
# comando giusto; il file .env (credenziali) non deve finire né nelle immagini né su Git.

import shutil
import subprocess
from pathlib import Path

import pytest

CARTELLA_PROGETTO = Path(__file__).resolve().parent.parent

DOCKERFILE = [
    ("Dockerfile", "assistente"),
    ("backend/Dockerfile", "backend"),
    ("frontend/Dockerfile", "frontend"),
]


def _righe(percorso: str) -> list[str]:
    testo = (CARTELLA_PROGETTO / percorso).read_text(encoding="utf-8")
    return [r.strip() for r in testo.splitlines() if r.strip() and not r.strip().startswith("#")]


@pytest.mark.parametrize(("percorso", "pacchetto"), DOCKERFILE)
def test_dockerfile_copia_solo_il_proprio_pacchetto(percorso, pacchetto):
    righe = _righe(percorso)
    assert righe[0] == "FROM python:3.13-slim"
    assert "WORKDIR /app" in righe
    copie = [r for r in righe if r.startswith("COPY")]
    assert copie == ["COPY requirements.txt .", f"COPY {pacchetto} ./{pacchetto}"]


@pytest.mark.parametrize(("percorso", "pacchetto"), DOCKERFILE)
def test_dockerfile_cmd(percorso, pacchetto):
    assert _righe(percorso)[-1] == f'CMD ["python", "-m", "{pacchetto}"]'


def test_dockerignore():
    righe = _righe(".dockerignore")
    assert ".env" in righe
    assert not [r for r in righe if r.startswith(("frontend", "/frontend", "backend", "/backend"))]


def test_env_ignorato_da_git():
    git = shutil.which("git")
    if git is None:
        pytest.skip("git non installato")
    esito = subprocess.run([git, "check-ignore", "-q", ".env"], cwd=CARTELLA_PROGETTO, timeout=30)
    assert esito.returncode == 0
