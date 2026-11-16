# Step 9 — Docker Compose: un container per componente (specifica)

_2026-11-16 · Lezione 6, step 9 (PDF `LLM_Lez_6.pdf`, pag. 16) · branch `feat/docker-compose` da `dev` (`262fed9`)_

## Intento

Con un solo comando (`docker compose up`) parte tutta l'applicazione costruita negli step 6–8
(agente, back-end, front-end, PostgreSQL), pronta all'uso dal browser. Ogni componente ha il suo
container; LM Studio resta sull'host come nella lezione 4. È l'ultimo step della lezione: serve a
mostrare che l'architettura a componenti separati si distribuisce come tale.

## Requisiti del PDF (alla lettera)

1. Quattro servizi in `compose.yaml`: tre con il proprio Dockerfile (front-end, back-end, agente) e
   PostgreSQL con l'immagine ufficiale.
2. Rete: il browser raggiunge il front-end; le chiamate API arrivano al back-end tramite porta
   pubblicata o proxy; l'agente non è esposto.
3. Volume per i dati di PostgreSQL; credenziali in `.env` escluso da Git; back-end avviato a
   database pronto.
4. L'agente raggiunge LM Studio con `host.docker.internal`; i server MCP stdio partono nel suo
   container.

Evidenze richieste:

- E1: `docker compose up` avvia i quattro servizi; `docker compose ps` li mostra attivi.
- E2: chat dal browser con uno strumento, visibile nei log dell'agente (`docker compose logs agente`,
  righe `variant=mcp tool=...`).
- E3: dopo `docker compose down` e `docker compose up` le chat sono ancora presenti.

## Obiettivi, non obiettivi, anti-obiettivi

- Obiettivi: i quattro servizi; `docker compose up` senza altri passi oltre al `.env` già esistente;
  le tre evidenze verificabili nei log, in `ps` e nel browser; test automatici sulla configurazione.
- Non obiettivi: streaming, HTTPS, immagini ottimizzate per dimensione, CI, pubblicazione delle
  immagini, LM Studio in container, riavvio automatico (`restart:`), modifiche al codice Python di
  agente, back-end e front-end (salvo un difetto che emerga dalle prove, da chiedere all'utente).
- Anti-obiettivi: credenziali scritte in `compose.yaml` o nelle immagini; agente o back-end
  raggiungibili dalla rete del PC; perdere le chat esistenti (il volume `dati-postgres` attuale va
  riusato, mai ricreato; vietato `down -v` nelle istruzioni, salvo l'avviso già presente).

## Strade considerate

- **A (scelta dall'utente):** il `Dockerfile` nella radice resta quello dell'agente (usato anche da
  `cli`); nuovi `backend/Dockerfile` e `frontend/Dockerfile`; tutti installano lo stesso
  `requirements.txt`; contesto di build la radice del progetto. Tocca poco, versioni in un solo posto;
  immagini di back-end e front-end più pesanti (contengono librerie che non usano).
- B: come A con un file di dipendenze per componente. Immagini leggere, ma versioni ripetute in più
  file con rischio di disallineamento. Scartata dall'utente.
- C: un'unica immagine con tre comandi. Esclusa dal PDF («tre con il proprio Dockerfile»).

## Progetto

### Dockerfile

- `Dockerfile` (radice, agente): invariato nel contenuto funzionale (copia `assistente/`, avvia la
  CLI di default; il servizio `agente` lo sostituisce con `python -m assistente.servizio`). Si
  aggiornano solo i commenti.
- `backend/Dockerfile`: `python:3.13-slim`, stesse `ENV` del Dockerfile dell'agente, `WORKDIR /app`,
  `COPY requirements.txt` + `pip install`, `COPY backend ./backend`, `CMD ["python", "-m", "backend"]`.
- `frontend/Dockerfile`: come sopra con `COPY frontend ./frontend` (comprende `statico/` e
  `contratto/openapi-backend.json`) e `CMD ["python", "-m", "frontend"]`.
- Ogni immagine contiene solo il proprio pacchetto: il back-end non contiene `assistente`, il
  front-end non contiene né `assistente` né `backend` (stessa separazione dei test
  `test_*_indipendente`).
- `.dockerignore` invariato (esclude già `.env`, `.venv`, test, documenti, `archivio/`); va
  verificato che non escluda `frontend/statico` né `frontend/contratto`.
- Commenti didattici in italiano semplice, nello stile dei file Docker attuali.

### `compose.yaml`

Servizi (il progetto Compose resta `assistente-laboratorio`, così il volume
`assistente-laboratorio_dati-postgres` con le chat esistenti viene riusato):

| Servizio | Immagine | Porte pubblicate | Note |
|---|---|---|---|
| `agente` | `build: .` (Dockerfile radice) | **nessuna** (tolta la `8000:8000` dello step 6) | come oggi: `LM_BASE_URL=http://host.docker.internal:1234/v1`, `AGENTE_HOST=0.0.0.0`, `extra_hosts` `host-gateway`, volume `./archivio:/app/archivio` (note, preferenze; server MCP stdio nel container); healthcheck |
| `backend` | `build: {context: ., dockerfile: backend/Dockerfile}` | nessuna | `POSTGRES_HOST=db`, `POSTGRES_PORTA=5432`, `BACKEND_HOST=0.0.0.0`, `AGENTE_URL=http://agente:8000`; `depends_on` `db: service_healthy`, `agente: service_healthy` |
| `frontend` | `build: {context: ., dockerfile: frontend/Dockerfile}` | `127.0.0.1:8002:8002` | `BACKEND_URL=http://backend:8001`, `FRONTEND_HOST=0.0.0.0`; `depends_on` `backend` (avviato) |
| `db` | `postgres:17.12-alpine` (invariata) | `127.0.0.1:${POSTGRES_PORTA:-5432}:5432` (invariata: serve ai test `PROVE_POSTGRES` e al lavoro sul PC) | credenziali `${POSTGRES_*}` dal `.env`; volume `dati-postgres`; healthcheck |
| `cli` | come oggi | nessuna | `profiles: ["cli"]`: `docker compose up` non la avvia; `docker compose run --rm cli` funziona ancora |

- Tutti i servizi costruiti usano `env_file: .env`; le righe `environment:` di `compose.yaml` hanno la
  precedenza e sostituiscono i valori pensati per il PC (nel `.env` dell'utente `POSTGRES_PORTA=5433`,
  `POSTGRES_HOST=127.0.0.1`, `AGENTE_URL=http://localhost:8000`, ecc.). Il codice legge
  `{**da_file, **os.environ}`: nel container non c'è `.env` nell'immagine, valgono le variabili di
  Compose.
- Healthcheck di `db`: `pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}` (variabili del
  container), con intervallo breve e `start_period` (valori scelti dal builder, ragionevoli per un PC
  di laboratorio). È il punto «back-end avviato a database pronto»: senza, `python -m backend` esce
  con codice 3 se il database non accetta ancora connessioni.
- Healthcheck di `agente`: un comando Python (nessun `curl` nell'immagine slim) che chiede
  `http://127.0.0.1:8000/openapi.json` e riesce se arriva una risposta HTTP. Non si usa `/stato`,
  perché risponde 503 quando LM Studio è spento e bloccherebbe l'avvio di tutto: con LM Studio spento
  l'applicazione deve partire e mostrare l'errore «Agente non raggiungibile»/503 già previsto.
- Rete: quella predefinita di Compose; i servizi si chiamano per nome (`db`, `agente`, `backend`).
- Commento in testa al file aggiornato: i quattro servizi, i comandi (`docker compose up -d --build`,
  `ps`, `logs agente`, `down`), l'avviso su `down -v`, la CLI con `run --rm cli`.

### Documentazione

- README: sezione Docker riscritta per lo step 9 (avvio completo, apertura di
  `http://localhost:8002`, log dell'agente, `down`/`up`; prima di `up` chiudere eventuali
  `python -m frontend` sul PC, che occupano la porta 8002; l'agente non ha più `/docs` dal browser in
  Docker; per `/docs` di agente e back-end si usano gli avvii sul PC); checklist, diagnosi
  (servizio `unhealthy`, porta 8002 occupata, LM Studio spento → 503); test nuovi; esiti.
- Aggiornati i passaggi del README degli step 6–7 che citano `http://localhost:8000/docs` in Docker o
  il back-end che gira solo sul PC, con un rimando allo step 9 (testo, non codice).
- `.env.example`: commenti che spiegano che in Docker `compose.yaml` sostituisce gli indirizzi
  (nessuna variabile nuova).
- `CLAUDE.md`: punto step 9 tra gli obiettivi e la riga Docker (quattro servizi + `cli` con profilo).

## Test

Test automatici (nessun modello, nessuna rete, nessun container avviato):

- `tests/test_docker_compose.py`, configurazione risolta con `docker compose config --format json`
  (Docker Compose v2 sul PC; test saltati se il comando `docker` manca). Il comando va eseguito in una
  cartella temporanea con una copia di `compose.yaml` e un `.env` ricavato da `.env.example`, così non
  dipende dal `.env` dell'utente né ne mostra i valori. Verifica:
  - servizi attivi senza profili esattamente `agente`, `backend`, `frontend`, `db`; `cli` solo con il
    profilo `cli`;
  - `agente` e `backend` senza porte pubblicate; `frontend` solo `127.0.0.1:8002`; `db` solo su
    `127.0.0.1`;
  - tre servizi costruiti con tre Dockerfile diversi; `db` con l'immagine ufficiale `postgres:`;
  - `backend.depends_on.db.condition == service_healthy` (e agente `service_healthy`); healthcheck
    presenti su `db` e `agente`;
  - volume con nome montato su `/var/lib/postgresql/data`;
  - variabili: `LM_BASE_URL` con `host.docker.internal`, `extra_hosts` con `host-gateway`, `AGENTE_URL`
    e `BACKEND_URL` con i nomi dei servizi, `POSTGRES_HOST=db`, `POSTGRES_PORTA=5432`, `*_HOST=0.0.0.0`;
  - nessun valore di `POSTGRES_PASSWORD` scritto in `compose.yaml` (solo `${...}`).
- Test sul testo dei Dockerfile (senza Docker): ognuno copia solo il proprio pacchetto e ha il `CMD`
  giusto; `.dockerignore` esclude `.env` e non esclude `frontend/statico`/`frontend/contratto`;
  `.env` è ignorato da Git, verificato con `git check-ignore` (l'esclusione sta nel `.gitignore`
  della radice della repository, non in quello del progetto: nessuno dei due si modifica; test
  saltato se `git` manca).
- La suite esistente deve restare verde (678 passed, 40 skipped prima dello step).

Prove reali con Docker (le esegue l'utente, istruzioni in un unico messaggio; Claude non avvia
container senza conferma): `docker compose up -d --build` → quattro servizi; `docker compose ps` con
`db` e `agente` `healthy`; browser su `http://localhost:8002`: «Quanto fa 45 diviso 9?» →
«Strumenti usati: calcola»; `docker compose logs agente` con `variant=mcp tool=calcola`; chat 1 e 2
degli step precedenti visibili (volume riusato); `docker compose down`, `docker compose up -d`, chat
ancora presenti; verifica che `http://localhost:8000` e `http://localhost:8001` non rispondano
(agente e back-end non esposti, con i servizi sul PC spenti); `docker compose run --rm cli` funziona.
Esiti nel README.

## Verifiche fatte sul codice (revisione della specifica)

- L'agente si avvia e serve `/openapi.json` anche con LM Studio spento (esce con codice 3 solo se il
  server MCP non risponde).
- Back-end e front-end leggono prima il `.env` e poi l'ambiente, che ha la precedenza: valgono le
  variabili di `compose.yaml`.
- Il front-end trova `statico/` rispetto al proprio codice; `.dockerignore` non esclude
  `frontend/statico` né `frontend/contratto`.
- Nessun test esistente controlla la vecchia porta `8000:8000` dell'agente.

## Lasciato al builder

Nomi esatti e intervalli degli healthcheck, testo dei commenti, struttura interna dei test, ordine
dei commit (TDD: prima i test della configurazione, poi i file Docker), formulazione del README.
