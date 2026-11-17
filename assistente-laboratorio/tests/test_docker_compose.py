"""Controlli su compose.yaml: quattro servizi, rete, volume, avvio a database pronto (lezione 6, step 9)."""

# COSA PROVA QUESTO FILE
# Chiede a Docker Compose la configurazione "risolta" (docker compose config --format json): è
# solo lettura, non costruisce immagini e non avvia container. Il comando gira in una cartella
# temporanea con una copia di compose.yaml e un .env di prova ricavato da .env.example, così non
# dipende dal .env vero (e non ne mostra i valori). In fondo al .env di prova ci sono gli
# indirizzi pensati per il PC (porta 5433, 127.0.0.1, localhost): i test controllano che nei
# container valgano invece quelli scritti in compose.yaml.
# Senza Docker (comando "docker" assente o senza Compose) questi test vengono saltati, tranne
# quello sul testo della password.

import json
import shutil
import subprocess
from pathlib import Path, PurePosixPath

import pytest

CARTELLA_PROGETTO = Path(__file__).resolve().parent.parent

# Valori come nel .env di chi lavora sul PC: compose.yaml li deve sostituire nei container.
ENV_DA_PC = """
POSTGRES_PORTA=5433
POSTGRES_HOST=127.0.0.1
AGENTE_URL=http://localhost:8000
BACKEND_URL=http://127.0.0.1:8001
AGENTE_HOST=127.0.0.1
BACKEND_HOST=127.0.0.1
FRONTEND_HOST=127.0.0.1
"""


def _configurazione(cartella: Path, profilo: str | None = None) -> dict:
    docker = shutil.which("docker")
    if docker is None:
        pytest.skip("Docker non installato: test di compose.yaml saltati")
    shutil.copy(CARTELLA_PROGETTO / "compose.yaml", cartella / "compose.yaml")
    esempio = (CARTELLA_PROGETTO / ".env.example").read_text(encoding="utf-8")
    (cartella / ".env").write_text(esempio + ENV_DA_PC, encoding="utf-8")
    comando = [docker, "compose"] + (["--profile", profilo] if profilo else []) + ["config", "--format", "json"]
    esito = subprocess.run(comando, cwd=cartella, capture_output=True, text=True, encoding="utf-8", timeout=60)
    if esito.returncode != 0 and "compose" in esito.stderr and "is not a docker command" in esito.stderr:
        pytest.skip("Docker Compose non disponibile")
    assert esito.returncode == 0, esito.stderr
    return json.loads(esito.stdout)


@pytest.fixture
def config(tmp_path):
    return _configurazione(tmp_path)


@pytest.fixture
def servizi(config):
    return config["services"]


def test_quattro_servizi(servizi):
    assert set(servizi) == {"agente", "backend", "frontend", "db"}


def test_cli_solo_con_profilo(tmp_path):
    servizi = _configurazione(tmp_path, "cli")["services"]
    assert servizi["cli"]["profiles"] == ["cli"]
    assert servizi["cli"]["environment"]["AGENTE_URL"] == "http://agente:8000"


def test_porte(servizi):
    assert "ports" not in servizi["agente"]
    assert "ports" not in servizi["backend"]
    [fe] = servizi["frontend"]["ports"]
    assert (fe["host_ip"], str(fe["published"]), fe["target"]) == ("127.0.0.1", "8002", 8002)
    [db] = servizi["db"]["ports"]
    assert (db["host_ip"], db["target"]) == ("127.0.0.1", 5432)


def test_tre_dockerfile_e_immagine_ufficiale(servizi):
    def dockerfile(nome):
        return PurePosixPath(servizi[nome]["build"]["dockerfile"].replace("\\", "/")).as_posix()

    assert dockerfile("agente") == "Dockerfile"
    assert dockerfile("backend") == "backend/Dockerfile"
    assert dockerfile("frontend") == "frontend/Dockerfile"
    assert "build" not in servizi["db"]
    assert servizi["db"]["image"] == "postgres:17.12-alpine"


def test_avvio_a_database_pronto(servizi):
    dipende = servizi["backend"]["depends_on"]
    assert dipende["db"]["condition"] == "service_healthy"
    assert dipende["agente"]["condition"] == "service_healthy"
    assert "backend" in servizi["frontend"]["depends_on"]
    assert "pg_isready" in " ".join(servizi["db"]["healthcheck"]["test"])


def test_healthcheck_agente_non_usa_stato(servizi):
    comando = " ".join(servizi["agente"]["healthcheck"]["test"])
    assert "/openapi.json" in comando
    assert "/stato" not in comando


def test_volume_postgres(config):
    [volume] = config["services"]["db"]["volumes"]
    assert (volume["type"], volume["source"], volume["target"]) == (
        "volume", "dati-postgres", "/var/lib/postgresql/data")
    assert "dati-postgres" in config["volumes"]


def test_variabili_sostituite_nei_container(servizi):
    agente = servizi["agente"]
    assert agente["environment"]["LM_BASE_URL"] == "http://host.docker.internal:1234/v1"
    assert agente["environment"]["AGENTE_HOST"] == "0.0.0.0"
    assert any("host-gateway" in str(voce) for voce in agente["extra_hosts"])
    assert [v["target"] for v in agente["volumes"] if v["type"] == "bind"] == ["/app/archivio"]
    backend = servizi["backend"]["environment"]
    assert backend["POSTGRES_HOST"] == "db"
    assert backend["POSTGRES_PORTA"] == "5432"
    assert backend["BACKEND_HOST"] == "0.0.0.0"
    assert backend["AGENTE_URL"] == "http://agente:8000"
    frontend = servizi["frontend"]["environment"]
    assert frontend["BACKEND_URL"] == "http://backend:8001"
    assert frontend["FRONTEND_HOST"] == "0.0.0.0"


def test_nessuna_password_in_compose():
    righe = (CARTELLA_PROGETTO / "compose.yaml").read_text(encoding="utf-8").splitlines()
    con_password = [r for r in righe if "POSTGRES_PASSWORD" in r and not r.strip().startswith("#")]
    assert con_password
    assert all("${POSTGRES_PASSWORD}" in r for r in con_password)
