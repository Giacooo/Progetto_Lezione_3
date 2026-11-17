# Step 9, Docker Compose (un container per componente) — Piano di implementazione

> **Per chi esegue:** SOTTO-SKILL OBBLIGATORIA: usare superpowers:executing-plans (esecuzione diretta, modo di lavoro veloce di `CLAUDE.local.md`) per eseguire il piano task per task. I passi usano le caselle (`- [ ]`) per il tracciamento.

**Obiettivo:** `docker compose up -d --build` avvia quattro servizi (`agente`, `backend`, `frontend`, `db`) e l'applicazione è pronta su `http://localhost:8002`.

**Architettura:** tre Dockerfile (radice = agente, invariato; nuovi `backend/Dockerfile` e `frontend/Dockerfile`, contesto di build la radice, stesso `requirements.txt`) e `compose.yaml` esteso: agente senza porte, back-end senza porte, front-end su `127.0.0.1:8002`, `db` con healthcheck, back-end avviato a `db` e `agente` «healthy», `cli` sotto il profilo `cli`.

**Tecnologie:** Docker Compose v2 (sul PC v5.0.2), `python:3.13-slim`, `postgres:17.12-alpine`. **Nessuna dipendenza nuova.**

**Specifica:** `docs/superpowers/specs/2026-11-16-docker-compose-design.md` (commit `e8a0ee1`, approvata). Chi esegue legge entrambi i documenti.

Percorsi relativi a `assistente-laboratorio/`; comandi PowerShell in quella cartella con `.\.venv\Scripts\python.exe -m pytest ...`. Branch `feat/docker-compose` (già creato da `dev` `262fed9`).

## Vincoli globali

- Modo di lavoro veloce. **Nessun file Python in `assistente/`, `backend/`, `frontend/` cambia.** File toccati: `compose.yaml`, `Dockerfile` (solo commenti), nuovi `backend/Dockerfile`, `frontend/Dockerfile`, `tests/test_docker.py`, `tests/test_docker_compose.py`, `.env.example` (solo commenti), `README.md`, `CLAUDE.md`. `.gitignore` e `.dockerignore` non si toccano.
- **Claude non avvia container né costruisce immagini** (`up`, `build`, `run`, `down`): lo fa l'utente con le istruzioni del Task 4. `docker compose config` (solo lettura della configurazione, nessun container) è ammesso nei test.
- Valori fissati dalla specifica:
  - `agente`: `build: .`, `command: ["python", "-m", "assistente.servizio"]`, `env_file: .env`, `LM_BASE_URL: http://host.docker.internal:1234/v1`, `AGENTE_HOST: 0.0.0.0`, `extra_hosts: ["host.docker.internal:host-gateway"]`, volume `./archivio:/app/archivio`, **nessuna `ports`**, healthcheck `["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/openapi.json', timeout=3)"]` (mai `/stato`);
  - `backend`: `build: {context: ., dockerfile: backend/Dockerfile}`, `env_file: .env`, `POSTGRES_HOST: db`, `POSTGRES_PORTA: "5432"`, `BACKEND_HOST: 0.0.0.0`, `AGENTE_URL: http://agente:8000`, **nessuna `ports`**, `depends_on: {db: {condition: service_healthy}, agente: {condition: service_healthy}}`;
  - `frontend`: `build: {context: ., dockerfile: frontend/Dockerfile}`, `env_file: .env`, `BACKEND_URL: http://backend:8001`, `FRONTEND_HOST: 0.0.0.0`, `ports: ["127.0.0.1:8002:8002"]`, `depends_on: [backend]`;
  - `db`: immagine, credenziali `${POSTGRES_*}`, porta `127.0.0.1:${POSTGRES_PORTA:-5432}:5432` e volume `dati-postgres:/var/lib/postgresql/data` **invariati**; healthcheck `["CMD-SHELL", "pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}"]`;
  - `cli`: come oggi più `profiles: ["cli"]`.
  - Intervalli (scelta del builder): `db` interval 5s, timeout 5s, retries 12, start_period 10s; `agente` interval 5s, timeout 5s, retries 24, start_period 30s.
- Nessuna credenziale in `compose.yaml` o nelle immagini; vietato suggerire `down -v`.
- Commenti didattici in italiano semplice nei file Docker, nello stile attuale.
- Git: staging per percorsi espliciti; mai i 4 file della Lezione 3, `HANDOFF*`, `HANDOFF_PROMPT.txt`, `PROMPT-ripresa-*`; Conventional Commits in italiano (scope `docker`) con `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; messaggio senza BOM e `git commit -F`; nessun push, nessun merge senza conferma. Mai distruggere `archivio/preferenze.json`; il `.env` dell'utente non si legge né si tocca.

## Punti da sorvegliare (Review Focus)

1. **Il `.env` dell'utente con valori pensati per il PC** (`POSTGRES_PORTA=5433`, `POSTGRES_HOST=127.0.0.1`, `AGENTE_URL=http://localhost:8000`, `BACKEND_URL=http://127.0.0.1:8001`, `*_HOST=127.0.0.1`): nel container valgono i valori di `compose.yaml` → `test_variabili_sostituite_nei_container` con un `.env` di prova che contiene proprio quei valori (Task 2).
2. **LM Studio spento all'avvio**: l'applicazione parte lo stesso (healthcheck dell'agente su `/openapi.json`, non `/stato`) → `test_healthcheck_agente_non_usa_stato` (Task 2) e prova manuale (Task 4).
3. **Porta 8002 occupata da un `python -m frontend` lasciato aperto sul PC**: `up` fallisce sul front-end → voce di diagnosi nel README e passo «chiudi le finestre» nelle istruzioni (Task 3, 4).
4. **Chat esistenti perse** (volume ricreato o nome di progetto cambiato): nessun `name:` in `compose.yaml`, volume `dati-postgres` invariato → `test_volume_postgres` (Task 2) e prova manuale «chat 1 e 2 visibili» (Task 4).
5. **Immagine di un componente con il codice di un altro** (es. `assistente/` nel back-end): ogni Dockerfile copia solo il proprio pacchetto → `test_dockerfile_copia_solo_il_proprio_pacchetto` (Task 1).

---

### Task 1: Dockerfile di back-end e front-end

**Files:**
- Create: `backend/Dockerfile`, `frontend/Dockerfile`
- Modify: `Dockerfile` (solo commenti: «immagine dell'agente», dallo step 9 una per componente)
- Test: `tests/test_docker.py`

**Interfaces:** Produces: i percorsi `backend/Dockerfile`, `frontend/Dockerfile` usati da `compose.yaml` (Task 2).

- [x] **Step 1: Test che falliscono** (`tests/test_docker.py`, solo lettura di testo, nessun Docker):
  - `test_dockerfile_copia_solo_il_proprio_pacchetto` parametrizzato su `("Dockerfile", "assistente")`, `("backend/Dockerfile", "backend")`, `("frontend/Dockerfile", "frontend")`: le righe `COPY` sono esattamente `COPY requirements.txt .` e `COPY <pacchetto> ./<pacchetto>`; `FROM python:3.13-slim`; `WORKDIR /app`.
  - `test_dockerfile_cmd` : `CMD ["python", "-m", "backend"]` e `CMD ["python", "-m", "frontend"]` (l'agente resta `CMD ["python", "-m", "assistente"]`).
  - `test_dockerignore`: le righe di `.dockerignore` comprendono `.env`; nessuna riga che escluda `frontend/` o sue sottocartelle.
  - `test_env_ignorato_da_git`: `git check-ignore -q .env` dalla cartella del progetto → uscita 0 (saltato se `shutil.which("git")` è `None`).
- [x] **Step 2:** `.\.venv\Scripts\python.exe -m pytest tests/test_docker.py -q` → falliscono i casi `backend`/`frontend` (file mancanti).
- [x] **Step 3:** scrivere i due Dockerfile (struttura del Dockerfile della radice: `ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1`, install delle librerie prima del codice) e aggiornare i commenti del `Dockerfile` della radice.
- [x] **Step 4:** stesso comando → tutti superati.
- [x] **Step 5: Commit** `feat(docker): Dockerfile del back-end e del front-end (step 9)` (file: i tre Dockerfile, `tests/test_docker.py`).

### Task 2: `compose.yaml` con i quattro servizi

**Files:**
- Modify: `compose.yaml`
- Test: `tests/test_docker_compose.py`

**Interfaces:** Consumes: Task 1. Produces: fixture `configurazione(profilo: str | None = None) -> dict` interna al file di test.

- [x] **Step 1: Test che falliscono.** Helper: copia `compose.yaml` in `tmp_path`, scrive `tmp_path/.env` = testo di `.env.example` + righe che simulano un `.env` da PC (`POSTGRES_PORTA=5433`, `POSTGRES_HOST=127.0.0.1`, `AGENTE_URL=http://localhost:8000`, `BACKEND_URL=http://127.0.0.1:8001`, `AGENTE_HOST=127.0.0.1`, `BACKEND_HOST=127.0.0.1`, `FRONTEND_HOST=127.0.0.1`; le ultime righe vincono), esegue `docker compose [--profile cli] config --format json` con `cwd=tmp_path` (timeout 60 s) e restituisce il JSON; tutto il modulo saltato se `shutil.which("docker")` è `None` o se il comando non riesce per assenza di Compose. Test:
  - `test_quattro_servizi`: `set(services) == {"agente", "backend", "frontend", "db"}`.
  - `test_cli_solo_con_profilo`: con `--profile cli` compare `cli` e `services["cli"]["profiles"] == ["cli"]`.
  - `test_porte`: `agente` e `backend` senza chiave `ports`; `frontend` una sola porta con `host_ip == "127.0.0.1"`, `published == "8002"`, `target == 8002`; `db` una sola porta con `host_ip == "127.0.0.1"`, `target == 5432`.
  - `test_tre_dockerfile_e_immagine_ufficiale`: `build.dockerfile` di agente/backend/frontend sono `Dockerfile`, `backend/Dockerfile`, `frontend/Dockerfile` (confronto sul nome finale del percorso normalizzato); `db` senza `build` e `image == "postgres:17.12-alpine"`.
  - `test_avvio_a_database_pronto`: `backend.depends_on.db.condition == "service_healthy"`, `backend.depends_on.agente.condition == "service_healthy"`; `"frontend".depends_on` contiene `backend`; `db.healthcheck.test` contiene `pg_isready`.
  - `test_healthcheck_agente_non_usa_stato`: il comando contiene `/openapi.json` e non `/stato`.
  - `test_volume_postgres`: in `db.volumes` un volume `type == "volume"`, `source == "dati-postgres"`, `target == "/var/lib/postgresql/data"`; `"dati-postgres" in config["volumes"]`.
  - `test_variabili_sostituite_nei_container`: agente `LM_BASE_URL == "http://host.docker.internal:1234/v1"`, `AGENTE_HOST == "0.0.0.0"`, `extra_hosts` con `host-gateway`, volume bind con target `/app/archivio`; backend `POSTGRES_HOST == "db"`, `POSTGRES_PORTA == "5432"`, `BACKEND_HOST == "0.0.0.0"`, `AGENTE_URL == "http://agente:8000"`; frontend `BACKEND_URL == "http://backend:8001"`, `FRONTEND_HOST == "0.0.0.0"`.
  - `test_nessuna_password_in_compose` (senza Docker, sul testo di `compose.yaml`): ogni riga che contiene `POSTGRES_PASSWORD` contiene anche `${POSTGRES_PASSWORD}`.
- [x] **Step 2:** `.\.venv\Scripts\python.exe -m pytest tests/test_docker_compose.py -q` → falliscono (servizi mancanti, porta 8000 dell'agente, ecc.).
- [x] **Step 3:** riscrivere `compose.yaml` con i valori dei Vincoli globali e il commento in testa aggiornato (quattro servizi; `docker compose up -d --build`, `ps`, `logs agente`, `down`; `run --rm cli`; avviso su `down -v` mantenuto).
- [x] **Step 4:** stesso comando → tutti superati; poi `.\.venv\Scripts\python.exe -m pytest -q` → 678 + nuovi superati, 40 saltati.
- [x] **Step 5: Commit** `feat(docker): quattro servizi in compose.yaml (step 9)`.

### Task 3: Documentazione

**Files:** Modify: `README.md`, `.env.example` (commenti), `CLAUDE.md`.

- [x] **Step 1: README:** sezione Docker per lo step 9 (prima di `up` chiudere le finestre con agente/back-end/front-end sul PC; `docker compose up -d --build`; `docker compose ps` con `db` e `agente` `healthy`; `http://localhost:8002`; `docker compose logs agente`; `down`/`up`; CLI con `docker compose run --rm cli`; agente e back-end non esposti, per `/docs` gli avvii sul PC); test nuovi (`tests/test_docker*.py`, saltati senza Docker/git); checklist dello step 9; diagnosi: servizio `unhealthy` (`docker compose logs <servizio>`), porta 8002 occupata, LM Studio spento → 503 nella pagina; rimandi allo step 9 nei passaggi degli step 6–7 che citano `http://localhost:8000/docs` in Docker o il back-end solo sul PC.
- [x] **Step 2: `.env.example`:** commento in testa alle sezioni step 6–8: in Docker `compose.yaml` sostituisce indirizzi e porte (`*_HOST`, `*_URL`, `POSTGRES_HOST`, `POSTGRES_PORTA`); nessuna variabile nuova.
- [x] **Step 3: `CLAUDE.md`:** punto «(lezione 6, step 9)» tra gli obiettivi e riga Docker aggiornata (quattro servizi, `cli` con profilo).
- [x] **Step 4:** `.\.venv\Scripts\python.exe -m pytest -q` → verde.
- [x] **Step 5: Commit** `docs: Docker Compose con un container per componente (step 9)`.

### Task 4: Prove, revisione ed esiti

- [ ] **Step 1:** serie reale completa una volta (`PROVE_REALI=1`, `PROVE_POSTGRES=1`, in background; avvisare l'utente di non caricare il PC).
- [ ] **Step 2:** revisione indipendente del branch; Critical/Important corretti con TDD, Minor nel registro `..\.superpowers\sdd\2026-11-16-docker-compose\progress.md`.
- [ ] **Step 3:** istruzioni Docker per l'utente in un unico messaggio (cartella `assistente-laboratorio`, finestre, ordine): chiudere agente/back-end/front-end sul PC; LM Studio con `google/gemma-4-e2b`; `docker compose up -d --build` (E1); `docker compose ps` → quattro servizi, `db` e `agente` `healthy`; browser `http://localhost:8002`: chat 1 e 2 presenti, nuova chat «Quanto fa 45 diviso 9?» → «Strumenti usati: calcola» (E2); `docker compose logs agente` con `variant=mcp tool=calcola` (E2); `Invoke-WebRequest http://localhost:8000/stato` e `http://localhost:8001/chat` → errore di connessione (non esposti); `docker compose down`, `docker compose up -d`, F5 → chat ancora presenti (E3); `docker compose run --rm cli` → una domanda, `esci`; alla fine `docker compose down` (mai `-v`).
- [ ] **Step 4:** esiti nel README («Esiti delle prove reali», step 9), piano segnato; commit `docs: esiti delle prove dello step 9 (Docker Compose)`.
