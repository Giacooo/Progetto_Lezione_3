# Specifica — Lezione 6, step 7: il back-end (API e salvataggio delle chat)

Data: 2026-11-16. Stato: **approvata dall'utente il 2026-11-16**.
Fonte dei requisiti: `LLM_Lez_6.pdf` (pag. 12 «L'applicazione finale: quattro container», pag. 14
«Step 7 · Back-end: API e salvataggio delle chat», pag. 17 «Metodo e consegna», pag. 19 «Consegna»),
`assistente-laboratorio/CLAUDE.md`, decisioni dell'utente nel brainstorming del 2026-11-16.

Le voci marcate **[scelta mia]** non sono state decise dall'utente: sono decisioni di chi ha
scritto la specifica, da controllare in lettura. Tutto il resto è richiesto dal PDF o deciso
dall'utente.

---

## 1. Intento

Dallo step 6 l'agente è un servizio HTTP senza stato: la conversazione la tiene chi lo chiama (oggi
la CLI, in memoria, persa all'uscita). Lo step 7 aggiunge il **back-end**, l'unico punto di contatto
del futuro front-end (step 8): gestisce le chat, le salva in PostgreSQL e inoltra le domande
all'agente. Obiettivo del PDF: **«le conversazioni restano disponibili dopo il riavvio e il front-end
non conosce l'agente»**.

Parte dallo step 6 funzionante e unito in `dev` (merge `074cf7d`).

## 2. Obiettivi (dal PDF, tabella «Operazione / Comportamento atteso»)

| Operazione | Comportamento atteso (PDF) |
|---|---|
| Creare una chat | Restituisce l'identificativo della nuova chat |
| Elencare le chat | Titolo e data dell'ultimo messaggio |
| Leggere una chat | Messaggi in ordine cronologico |
| Inviare un messaggio | Salva la domanda, chiama l'agente, salva e restituisce la risposta |
| Eliminare una chat | Rimuove la chat e i suoi messaggi |

Evidenze richieste dal PDF:
- documentazione OpenAPI generata e consultabile;
- agente non raggiungibile: errore chiaro e comportamento documentato;
- test con l'agente simulato; chat ancora presenti dopo il riavvio.

Consegna (pag. 19): test automatici, prova reale con LM Studio, README aggiornato e commit;
evidenza minima: **«chat persistenti dopo il riavvio; OpenAPI consultabile»**.

## 3. Non obiettivi e anti-obiettivi

- Niente front-end, niente CORS (servono al browser: step 8).
- Niente Dockerfile del back-end, niente compose a quattro servizi, niente «agente non esposto»,
  niente healthcheck / avvio a database pronto (step 9). Nello step 7 il back-end gira sul PC.
- Niente prompt MCP nel back-end: il PDF elenca solo le cinque operazioni sopra. `/prompts` e
  `/prompt` restano nella CLI, che continua a parlare direttamente con l'agente (step 6).
- Niente streaming (facoltativo del PDF, solo se l'utente lo decide), niente autenticazione,
  niente modifica o rinomina delle chat, niente paginazione.
- **Anti-obiettivo:** un back-end che importa il grafo, il modello o il collegamento MCP
  (`assistente.*`): deve parlare con l'agente solo via HTTP.
- **Anti-obiettivo:** chat che dopo il riavvio si vedono ma per l'agente sono «vuote» (il back-end
  deve conservare anche la memoria dell'agente: cronologia completa e riassunto, §7.2).
- **Anti-obiettivo:** una chat lasciata a metà (domanda salvata senza risposta) quando l'agente non
  risponde (decisione dell'utente, §5).
- **Anti-obiettivo:** la suite normale (`pytest -q`) che richiede Docker o PostgreSQL acceso.
- Gli step 1–6 non cambiano: nessun file in `assistente/` viene modificato.

## 4. Vincoli

- Modello `google/gemma-4-e2b` in LM Studio sull'host; agente dello step 6 invariato.
- PostgreSQL dell'applicazione gira in un container (sul PC c'è anche un PostgreSQL 18 nativo
  sulla 5432, non usato: il container si pubblica su un'altra porta, §10) con l'immagine ufficiale
  (`postgres:17.12-alpine`, **[scelta mia]**: la 18 cambia la cartella dei dati sul volume), avviato
  con Docker Compose. Le prove Docker le fa l'utente.
- Codice sincrono; endpoint `def` come nello step 6.
- Dipendenza nuova: **`pg8000==1.31.6`** (driver PostgreSQL per Python, sincrono, scritto solo in
  Python: niente librerie native da installare). **Approvata dall'utente il 2026-11-16** al posto di
  `psycopg[binary]==3.3.9`, approvato con la specifica ma inutilizzabile sul PC: Smart App Control di
  Windows blocca le DLL non firmate di `psycopg-binary`. Va in `requirements.txt` (unico file per ora; la
  separazione per container è dello step 9). Nessun pool di connessioni (sarebbe un'altra dipendenza).
- Test automatici senza modello, rete né database; prove con PostgreSQL vero e prove reali separate
  e attivate esplicitamente.
- Il `.env` dell'utente non si tocca: le variabili nuove vanno in `.env.example` e l'utente le copia
  (istruzioni nelle prove manuali).
- File degli step precedenti toccati: `requirements.txt`, `compose.yaml` (solo un servizio nuovo
  `db` e un volume), `.env.example`, `pytest.ini` (un marker), README, `CLAUDE.md`. **Approvando
  questa specifica l'utente approva queste modifiche.** Nessun file Python esistente cambia.

## 5. Approcci considerati e decisioni

Decisione dell'utente nel brainstorming:
- **Agente non raggiungibile (strada A):** se la chiamata all'agente fallisce **non si salva
  niente**: il back-end restituisce l'errore e la chat resta com'era. Il front-end potrà tenere la
  domanda per riprovare. (Scartata B: domanda salvata senza risposta, con domande «orfane» da gestire
  al tentativo successivo.) L'ordine del PDF «salva la domanda, chiama l'agente, salva la risposta»
  resta visibile nei dati: la domanda porta l'ora in cui è arrivata, la risposta l'ora in cui è
  tornata; si scrivono insieme, in un'unica transazione, solo a risposta ottenuta.

Scelte del «come», lasciate dall'utente a chi scrive la specifica (**[scelta mia]**):

1. **Accesso a PostgreSQL — pg8000 (in origine psycopg 3, vedi §4) con SQL scritto a mano. Scelto.** Due tabelle, cinque
   operazioni: le query si leggono. Scartato SQLAlchemy: un ORM intero per cinque query.
2. **Dove sta il back-end — pacchetto nuovo `backend/` accanto ad `assistente/`. Scelto.** Non
   importa nulla di `assistente`: che il front-end non conosca l'agente si vede anche dal codice, e
   allo step 9 avrà il suo Dockerfile senza toccare nulla. Scartato un modulo dentro `assistente/`.
3. **Test — API con agente simulato e archivio in memoria; PostgreSQL vero in test a parte.
   Scelto.** Scartato «tutti i test su PostgreSQL»: la suite normale richiederebbe Docker.
4. **Dove gira PostgreSQL nello step 7 — servizio `db` in `compose.yaml`. Scelto.** Allo step 9 si
   aggiungono gli altri servizi. Scartato un `docker run` nel README, da rifare allo step 9.

## 6. Architettura

```
CLI (step 6) ──HTTP──► agente :8000 ◄──HTTP── back-end :8001 ◄──HTTP── (front-end, step 8)
                                                  │
                                                  ▼
                                        PostgreSQL :5432 (container "db", volume)
```

Pacchetto `backend/` (nomi dei file **[scelta mia]**, il builder può affinarli):

| File | Responsabilità |
|---|---|
| `backend/configurazione.py` | legge `.env` + ambiente (python-dotenv), valida le variabili del §8 |
| `backend/archivio.py` | interfaccia dell'archivio delle chat + implementazione PostgreSQL (pg8000) |
| `backend/agente_remoto.py` | chiamata HTTP `POST /messaggio` all'agente (httpx), errori tradotti |
| `backend/app.py` | app FastAPI: endpoint, modelli pydantic, codici di errore, log |
| `backend/__main__.py` | avvio `python -m backend`: configurazione, creazione tabelle, uvicorn |

Regola: **nessun `import assistente`** in `backend/` (verificata da un test, come
`test_la_cli_non_conosce_l_agente` dello step 6). Il formato JSON dei messaggi dell'agente è
trattato come dato opaco (§7.2): il back-end non ha bisogno delle classi di `assistente/formato.py`.

## 7. Dati

### 7.1 Tabelle (create all'avvio con `CREATE TABLE IF NOT EXISTS`, nessuno strumento di migrazione)

```sql
CREATE TABLE IF NOT EXISTS chat (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    titolo      TEXT,                                  -- NULL finché non c'è (vedi 7.3)
    creata      TIMESTAMPTZ NOT NULL DEFAULT now(),
    cronologia  JSONB NOT NULL DEFAULT '[]'::jsonb,    -- memoria dell'agente (7.2)
    riassunto   TEXT  NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS messaggi (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    chat_id         BIGINT NOT NULL REFERENCES chat(id) ON DELETE CASCADE,
    ruolo           TEXT NOT NULL CHECK (ruolo IN ('utente', 'assistente')),
    testo           TEXT NOT NULL,
    strumenti_usati JSONB NOT NULL DEFAULT '[]'::jsonb, -- solo per 'assistente'
    data            TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS messaggi_chat_id ON messaggi (chat_id, id);
```

- «Eliminare una chat rimuove la chat e i suoi messaggi»: `ON DELETE CASCADE`.
- «Messaggi in ordine cronologico»: `ORDER BY data, id` (l'`id` decide a parità di istante).
- id interi **[scelta mia]**: semplici da leggere nelle prove manuali.

### 7.2 Due viste della stessa chat

- **`messaggi`** — quello che vede il front-end: per ogni turno la domanda dell'utente e la risposta
  finale, con gli strumenti usati. Non compaiono richieste/risultati di strumento né le indicazioni
  del revisore.
- **`chat.cronologia` + `chat.riassunto`** — la memoria dell'agente, così come la restituisce
  `POST /messaggio` dello step 6 (cronologia completa con strumenti, già compressa dal riassunto
  dello step 3). Il back-end la salva e la rimanda **senza interpretarla** al turno successivo.
  Così dopo il riavvio l'agente ritrova il filo esattamente come se la chat non si fosse mai
  interrotta, e il riassunto non viene ricalcolato a ogni turno.

### 7.3 Titolo **[scelta mia]**

- `POST /chat` accetta un corpo facoltativo `{"titolo": "..."}` (spazi ai bordi tolti; vuoto =
  assente).
- Senza titolo, al **primo messaggio** il titolo diventa l'inizio della domanda (prime 50 lettere,
  `…` se tagliata, a capo sostituiti da spazi).
- Finché il titolo è `NULL` l'API mostra `"Nuova chat"`.

## 8. Configurazione

Variabili nuove (in `.env.example`, sezione «Back-end (lezione 6, step 7)»):

| Variabile | Obbl. | Predefinito | Note |
|---|---|---|---|
| `POSTGRES_USER` | sì | — | usata anche dal container `db` (immagine ufficiale) |
| `POSTGRES_PASSWORD` | sì | — | in `.env.example` un segnaposto, mai una password vera |
| `POSTGRES_DB` | sì | — | es. `chat` |
| `POSTGRES_HOST` | no | `127.0.0.1` | allo step 9 sarà `db`; in origine `localhost`, cambiato il 2026-11-16 con l'approvazione dell'utente: su Windows `localhost` prova prima `::1`, dove il container non ascolta, e ogni connessione perde ~2 s |
| `POSTGRES_PORTA` | no | `5432` | intero 1–65535 |
| `BACKEND_HOST` | no | `127.0.0.1` | come `AGENTE_HOST` |
| `BACKEND_PORTA` | no | `8001` | intero 1–65535; l'agente resta su 8000 |
| `AGENTE_URL` | no | `http://localhost:8000` | **già esistente** (step 6), stesso significato |
| `LOG_LEVEL` | no | `INFO` | già esistente |

Le credenziali stanno una volta sola nel `.env`: le legge sia il container `db` sia il back-end
**[scelta mia]** (niente `DATABASE_URL` separata da tenere allineata). Configurazione non valida →
messaggio su stderr e **codice di uscita 2** (come agente e CLI).

## 9. API del back-end

Titolo OpenAPI «Back-end del laboratorio»; `/docs` e `/openapi.json` generati da FastAPI; risposte
`application/json; charset=utf-8` (come lo step 6, per PowerShell 5.1). Errori sempre nella forma
`{"errore": "messaggio in italiano"}`, dichiarati nell'OpenAPI di ogni endpoint, **anche il 422**
**[scelta mia]**: un gestore di `RequestValidationError` lo traduce (es. `Corpo non valido: il
messaggio non può essere vuoto.`), così il front-end dello step 8 ha una sola forma di errore nel
contratto OpenAPI. (Diverso dallo step 6, che lascia il 422 standard `{"detail": [...]}`: l'agente
non cambia.)

| Metodo e percorso | Corpo | Risposta OK | Errori |
|---|---|---|---|
| `POST /chat` | `{"titolo": str}` facoltativo | **201** `{"id", "titolo", "creata"}` | 422, 503 db |
| `GET /chat` | — | 200 `[{"id", "titolo", "ultimo_messaggio", "creata"}]` | 503 db |
| `GET /chat/{id}` | — | 200 `{"id", "titolo", "creata", "messaggi": [Messaggio]}` | 404, 503 db |
| `DELETE /chat/{id}` | — | **204** senza corpo | 404, 503 db |
| `POST /chat/{id}/messaggi` | `{"messaggio": str}` non vuoto | 200 `{"domanda": Messaggio, "risposta": Messaggio}` | 404, 422, 502, 503, 504 |

`Messaggio` = `{"ruolo": "utente"|"assistente", "testo", "strumenti_usati": [{"nome", "argomenti",
"risultato"}], "data"}` (date ISO 8601 con fuso).

- **Elenco:** `ultimo_messaggio` = data del messaggio più recente, `null` se la chat è vuota;
  ordine: prima le chat con attività più recente (`COALESCE(ultimo_messaggio, creata) DESC`)
  **[scelta mia]**.
- **Chat inesistente:** 404 `Chat non trovata.`
- **Inviare un messaggio** (in quest'ordine):
  1. apre una transazione e blocca la riga della chat (`SELECT … FOR UPDATE`; 404 se non c'è):
     due messaggi contemporanei alla stessa chat vengono serviti uno dopo l'altro e nessuno perde la
     memoria dell'altro **[scelta mia]**;
  2. annota l'ora della domanda **dopo** aver ottenuto il blocco **[scelta mia]**: così con due
     messaggi contemporanei i turni non si intrecciano nell'ordine cronologico (domanda A,
     risposta A, domanda B, risposta B) e `data` resta il criterio d'ordine del PDF;
  3. chiama l'agente con `{"messaggio", "cronologia", "riassunto"}` della chat;
  4. se l'agente risponde: inserisce domanda e risposta in `messaggi`, aggiorna `cronologia`,
     `riassunto` ed eventuale titolo, chiude la transazione, restituisce 200;
  5. se l'agente non risponde: annulla la transazione (**niente salvato**, decisione A) e
     restituisce l'errore.

### 9.1 Errori dell'agente (evidenza «errore chiaro e comportamento documentato»)

| Situazione | Codice | Messaggio |
|---|---|---|
| agente spento / indirizzo sbagliato (connessione rifiutata, DNS) | **503** | `Agente non raggiungibile: la domanda non è stata salvata, riprovare più tardi.` |
| agente che non risponde entro 600 s (come la CLI dello step 6) | **504** | `L'agente non ha risposto in tempo: la domanda non è stata salvata.` |
| agente che risponde con un errore (es. LM Studio fermo, 503/502/500 dello step 6) | **502** | `Errore dell'agente: <messaggio dell'agente>. La domanda non è stata salvata.` |
| risposta 200 che non ha la forma di quelle dell'agente | **502** | `Risposta non valida dall'agente: controllare AGENTE_URL. La domanda non è stata salvata.` |

Ogni caso scrive una riga WARNING nel log. Il comportamento si documenta nel README: chat invariata,
la domanda va rimandata.

### 9.2 Database non raggiungibile **[scelta mia]**

- All'avvio (`python -m backend`): creazione tabelle impossibile → `Database non disponibile: …` su
  stderr, **codice di uscita 3** (lo stesso «servizio necessario non disponibile» dell'agente).
- Durante il funzionamento: **503** `Database non disponibile.` con riga WARNING nel log.

### 9.3 Log (logger `backend`)

Righe INFO per ogni operazione (`richiesta operazione=… chat=…`), per la chiamata all'agente
(`agente chat=… strumenti=[…]`) e WARNING per gli errori; mai il testo completo della cronologia.
Formato uguale a quello dell'agente (`LIVELLO nome: messaggio`).

## 10. Docker Compose (solo il database)

In `compose.yaml` si aggiunge **[scelta mia]**:
- servizio `db`: `image: postgres:17.12-alpine`; `environment` con `POSTGRES_USER`,
  `POSTGRES_PASSWORD`, `POSTGRES_DB` presi dal `.env` (interpolazione `${…}` di Compose);
  `ports: "127.0.0.1:${POSTGRES_PORTA:-5432}:5432"` (raggiungibile solo da questo PC, serve al
  back-end locale; la porta sul PC è la stessa `POSTGRES_PORTA` letta dal back-end). Decisione
  dell'utente del 2026-11-16: sul PC è installato un PostgreSQL 18 nativo (servizio
  `postgresql-x64-18`) che occupa la 5432, quindi nel `.env` dell'utente `POSTGRES_PORTA=5433`;
  volume nominato `dati-postgres:/var/lib/postgresql/data`;
- `volumes: dati-postgres:` in fondo al file.

I servizi `agente` e `cli` non cambiano. Avvio: `docker compose up -d db`. «Chat ancora presenti
dopo il riavvio» si mostra fermando e riavviando **sia il back-end sia il container `db`**
(`docker compose restart db`, poi anche `down` / `up -d db`: il volume resta). `down -v` cancella i
dati: nel README come avvertenza, mai nelle istruzioni.

## 11. Test e prove

### 11.1 Test automatici (suite normale, niente rete né database)

- `test_backend_app.py` — API con `TestClient`, **archivio in memoria** e **agente simulato**
  (oggetto finto iniettato in `crea_app`): le cinque operazioni; 201/204/404/422; ordine dei
  messaggi; titolo automatico e `Nuova chat`; elenco con `ultimo_messaggio` e ordinamento;
  invio con agente che fallisce nei quattro modi del §9.1 → codice e messaggio giusti **e chat
  invariata** (nessun messaggio, memoria uguale); memoria dell'agente rimandata al turno dopo
  (l'agente simulato riceve la cronologia e il riassunto restituiti al turno prima); database giù
  → 503; OpenAPI con i cinque percorsi e i codici di errore dichiarati; `charset=utf-8`.
- `test_backend_agente_remoto.py` — client HTTP verso un agente finto (`httpx.MockTransport`):
  corpo inviato, risposta valida, connessione rifiutata, timeout, errore con `{"errore"}`, errore
  senza corpo JSON, 200 di forma sbagliata.
- `test_backend_configurazione.py` — obbligatorie mancanti, porte non valide, predefiniti,
  `AGENTE_URL` non http.
- `test_backend_indipendente.py` — nessun modulo di `backend/` importa `assistente`.
- L'archivio in memoria e quello PostgreSQL rispettano la stessa interfaccia; gli stessi casi di
  comportamento dell'archivio (crea, elenca, leggi, elimina a cascata, salva turno, blocco) girano
  su entrambi (test parametrizzati: PostgreSQL solo se attivato, sotto).

### 11.2 Test con PostgreSQL vero (marker `postgres`, attivati con `PROVE_POSTGRES=1`)

- Usano un **database separato `<POSTGRES_DB>_prove`**, creato se manca (l'utente dell'immagine
  ufficiale può farlo) e svuotato a ogni test: **le chat vere dell'utente non vengono mai toccate**.
- Casi: i comportamenti dell'archivio del §11.1; `ON DELETE CASCADE`; **persistenza dopo il
  riavvio** (crea chat e turno con un'app, poi una **nuova** app con un nuovo archivio sullo stesso
  database → elenco e messaggi ancora presenti); due turni contemporanei sulla stessa chat (blocco).
- Senza `PROVE_POSTGRES=1` sono saltati (come le prove reali).

### 11.3 Prova reale (marker `reale`, `PROVE_REALI=1` e `PROVE_POSTGRES=1`)

- back-end vero + agente vero (servizio dello step 6 avviato) + LM Studio + PostgreSQL: crea chat,
  «Quanto fa 45 diviso 9?» → risposta con `calcola` negli `strumenti_usati`, salvata; secondo turno
  che usa il primo («e se aggiungo 10?») → la memoria dell'agente arriva dal database.

### 11.4 Prove manuali e Docker dell'utente (un unico messaggio, dopo l'implementazione)

`docker compose up -d db`; agente e back-end in due finestre; dal browser `/docs` del back-end;
con `Invoke-RestMethod`: crea, elenca, invia (con strumento), leggi, elimina; agente spento →
503 con messaggio e chat invariata; **riavvio di back-end e `db` → chat ancora presenti**; database
fermo → 503 / codice 3 all'avvio.

## 12. Documentazione

- README: sezione «Back-end (step 7)» con preparazione (`.env`, `docker compose up -d db`), avvio in
  tre finestre (agente, back-end, prove), tabella degli endpoint, comportamento con agente o
  database non raggiungibili, formato dei log, test (`PROVE_POSTGRES`), checklist delle prove,
  diagnosi, esiti; avvertenza su `down -v`.
- `CLAUDE.md`: punto «(lezione 6, step 7)» nell'obiettivo e comandi.
- `.env.example`, `pytest.ini` (marker `postgres`), `compose.yaml` commentati come i precedenti.

## 13. Lasciato al builder

- Nomi interni di funzioni e classi, divisione fine dei test, testo esatto dei commenti.
- Come esporre la transazione con blocco dall'archivio (es. un context manager `turno(chat_id)`),
  purché l'archivio in memoria offra la stessa interfaccia.
- Gestione dei tipi `datetime` tra pg8000 e pydantic.

Versioni verificate il 2026-11-16: `pg8000 1.31.6` su PyPI (`pip index versions`), tag
`postgres:17.12-alpine` su Docker Hub.
