# Specifica — Lezione 6, step 8: il front-end (interfaccia di chat)

Data: 2026-11-16. Stato: **approvata dall'utente il 2026-11-16**.
Fonte dei requisiti: `LLM_Lez_6.pdf` (pag. 12 «L'applicazione finale: quattro container», pag. 15
«Step 8 · Front-end: interfaccia di chat», pag. 17 «Metodo e consegna», pag. 19 «Consegna»),
`assistente-laboratorio/CLAUDE.md`, decisioni dell'utente nel brainstorming del 2026-11-16.

Le voci marcate **[scelta mia]** non sono state decise dall'utente: sono decisioni di chi ha
scritto la specifica, da controllare in lettura. Tutto il resto è richiesto dal PDF o deciso
dall'utente.

---

## 1. Intento

Dallo step 7 il back-end (`backend/`, porta 8001) gestisce le chat in PostgreSQL e inoltra le
domande all'agente. Oggi lo si usa solo con `Invoke-RestMethod` o dalla pagina `/docs`. Lo step 8
aggiunge il **front-end**: un'interfaccia di chat nel browser, «utilizzabile da chi non conosce il
progetto, che comunica solo con il back-end» (PDF). Il documento OpenAPI del back-end è il
contratto: le chiamate del front-end si ricavano da lì, senza indovinare gli endpoint.

Parte dallo step 7 funzionante e unito in `dev` (merge `71b2a3b`).

## 2. Obiettivi (dal PDF, «Cosa realizzare»)

1. Elenco delle chat, creazione di una nuova chat ed eliminazione.
2. Vista dei messaggi della chat e invio di una nuova domanda.
3. Stato di attesa durante la risposta ed errori mostrati in modo comprensibile.
4. Indirizzo del back-end da configurazione, non scritto nel codice.

Evidenze richieste dal PDF:

- conversazione completa dal browser, con uso di uno strumento;
- una chat creata dall'interfaccia è ancora presente dopo il riavvio;
- con l'agente spento l'interfaccia mostra l'errore senza bloccarsi.

Evidenza minima (pag. 19): «Conversazione completa dal browser, errori mostrati».

Deciso dall'utente nel brainstorming: elenco delle chat a sinistra (titolo e data dell'ultimo
messaggio), messaggi a destra, **sotto ogni risposta gli strumenti usati** (nome e argomenti).

## 3. Non obiettivi e anti-obiettivi

- Niente streaming (facoltativo del PDF, solo se l'utente lo decide), niente rinomina delle chat,
  niente prompt MCP (`/prompts`, `/prompt`), niente stato dell'agente: il back-end non li offre e
  il PDF non li chiede.
- Niente modifiche al back-end dello step 7 (niente CORS): il browser non lo chiama direttamente.
- Niente Docker per il front-end: il suo container è lo step 9. Lo step 8 non tocca `compose.yaml`
  né il `Dockerfile`.
- Niente autenticazione, niente framework JavaScript, niente fase di compilazione (npm, bundler).
- **Anti-obiettivi:** un front-end che conosce l'agente (indirizzo, formato della cronologia,
  `AGENTE_URL`); un indirizzo del back-end scritto nel codice; un'interfaccia che resta bloccata
  o mostra errori tecnici grezzi (traceback, «Failed to fetch», JSON) a chi non conosce il
  progetto; dipendenze nuove.

## 4. Vincoli

- Solo dentro `assistente-laboratorio/`; nessun file degli step precedenti modificato, salvo
  `README.md`, `CLAUDE.md`, `.env.example`, `pytest.ini` (se serve un marker) e
  `tests/test_reale.py` (aggiunta in fondo, come allo step 7).
- **Nessuna dipendenza nuova:** FastAPI 0.163.1, uvicorn 0.54.0, httpx 0.28.1 e python-dotenv
  sono già in `requirements.txt`; `StaticFiles` di Starlette (1.10.0, già installato con FastAPI)
  non richiede pacchetti aggiuntivi. Node 24 sul PC dell'utente si usa solo, se presente, per
  i test della logica JavaScript con il test runner integrato (`node --test`), senza pacchetti npm.
- Il pacchetto `frontend/` **non importa né `assistente` né `backend`** (verificato da un test,
  come `test_backend_indipendente.py`). Solo i test possono importare `backend` per confrontare
  il contratto (§9).
- Codice Python sincrono dove possibile (endpoint `def`), come nel resto del progetto.
- Comandi documentati per PowerShell; nelle istruzioni `.\.venv\Scripts\python.exe`.
- Smart App Control acceso sul PC dell'utente: nessuna libreria con DLL non firmate (motivo in
  più per escludere Streamlit e simili).

## 5. Approcci considerati e decisioni

| Strada | Com'è | Esito |
|---|---|---|
| **A. Pacchetto Python `frontend/`** | server FastAPI che serve una pagina HTML/CSS/JS semplice e inoltra `/api/...` al back-end (proxy httpx); `BACKEND_URL` da configurazione | **scelta dall'utente** |
| B. Pagina statica + CORS nel back-end | il browser chiama direttamente la 8001 | scartata: modifica lo step 7, l'indirizzo finisce in un file letto dal browser, allo step 9 il back-end va esposto al browser |
| C. Vite + React/Vue (Node) | interfaccia con framework e compilazione | scartata: decine di pacchetti npm, catena di compilazione nuova, in produzione serve comunque un server per il proxy |
| Streamlit / Gradio | interfaccia generata da Python | scartata: dipendenze pesanti, rischio blocco DLL da Smart App Control |

Motivo della scelta A: copre il PDF senza dipendenze nuove e senza toccare lo step 7; il browser
parla solo con il server del front-end (stessa origine, niente CORS); per lo step 9 è già un
componente separato e usa il «proxy» citato dal PDF (pag. 16, «tramite porta pubblicata o proxy»).

## 6. Architettura

```
browser ──HTTP──> front-end (frontend/, porta 8002)
                    ├─ GET /            pagina index.html, stile.css, app.js, logica.js
                    └─ /api/{percorso}  proxy ──HTTP──> back-end (BACKEND_URL, porta 8001) ──> agente
```

| File | Che cosa fa |
|---|---|
| `frontend/__init__.py` | pacchetto |
| `frontend/configurazione.py` | legge `.env` e ambiente: `BACKEND_URL`, `FRONTEND_HOST`, `FRONTEND_PORTA`, `LOG_LEVEL` |
| `frontend/app.py` | `crea_app(client_backend)`: pagina statica + proxy `/api/...`, errori del proxy, log |
| `frontend/__main__.py` | avvio con `python -m frontend` (uscita 2 se la configurazione non è valida) |
| `frontend/statico/index.html` | la pagina (struttura, testi in italiano) |
| `frontend/statico/stile.css` | l'aspetto |
| `frontend/statico/api.js` | le chiamate al back-end, una funzione per operazione del contratto |
| `frontend/statico/logica.js` | funzioni pure (date, testo degli errori, strumenti) testabili con Node |
| `frontend/statico/app.js` | collega pagina, stato e chiamate |
| `frontend/contratto/openapi-backend.json` | copia del documento OpenAPI del back-end: il contratto |

**L'indirizzo del back-end lo conosce solo il server del front-end** (variabile `BACKEND_URL`):
la pagina usa percorsi relativi `/api/...` e non contiene indirizzi. Così il requisito 4 è
soddisfatto senza mandare la configurazione al browser, e allo step 9 basterà
`BACKEND_URL=http://backend:8001`.

### 6.1 Proxy `/api/{percorso}` [scelta mia nei dettagli]

- Metodi `GET`, `POST`, `DELETE`. Inoltra a `BACKEND_URL` + `/{percorso}` metodo, query string,
  corpo e intestazione `Content-Type`; restituisce codice, corpo e `Content-Type` del back-end
  così come sono (204 senza corpo). Il proxy non interpreta le chat: è un passacarte.
- Solo i percorsi del contratto: `chat` e `chat/{id}` e `chat/{id}/messaggi` (con i metodi
  dichiarati nell'OpenAPI). Altri percorsi → 404 `{"errore": "Operazione non disponibile."}`
  senza chiamare il back-end. Motivo: il front-end espone solo ciò che il contratto prevede, e
  `/api/docs` o percorsi inventati non arrivano al back-end.
- Attesa massima **630 secondi**: più dei 600 che il back-end concede all'agente, così un 504
  dell'agente arriva al browser con il messaggio del back-end e non viene coperto dal proxy.
- Errori del proxy, sempre nella forma `{"errore"}` del back-end:

| Caso | Codice | Messaggio |
|---|---|---|
| back-end spento o indirizzo sbagliato (errore di connessione) | 503 | `Back-end non raggiungibile: controllare che sia avviato e l'indirizzo BACKEND_URL.` |
| back-end che non risponde entro 630 s | 504 | `Il back-end non ha risposto in tempo.` |

- Log (logger `frontend`): `INFO frontend: inoltro metodo=POST percorso=/chat/3/messaggi codice=200`;
  `WARNING frontend: back-end non raggiungibile metodo=... percorso=...`. Il testo dei messaggi
  non compare mai nei log.

### 6.2 Pagina

```
┌──────────────────────────┬──────────────────────────────────────────────┐
│ Assistente del laboratorio│ Quanto fa 45 diviso 9?                    🗑 │
│ [ + Nuova chat ]          │──────────────────────────────────────────────│
│                           │                      Tu · 16/11 10:02        │
│ ▸ Quanto fa 45 diviso 9?  │                      Quanto fa 45 diviso 9?  │
│   16/11 10:02             │ Assistente · 16/11 10:02                     │
│   Che ore sono a Tokyo?   │ 45 diviso 9 fa 5.                            │
│   15/11 18:40             │ Strumenti usati: calcola (espressione: 45/9) │
│   Nuova chat              │ ┌─────────────────────────────────────────┐  │
│   nessun messaggio        │ │ ⚠ Agente non raggiungibile: la domanda… │  │
│                           │ └─────────────────────────────────────────┘  │
│                           │ [ Scrivi una domanda…               ][Invia] │
└──────────────────────────┴──────────────────────────────────────────────┘
```

- **Elenco (a sinistra):** ordine del back-end (attività più recente in alto); per ogni chat
  titolo e data dell'ultimo messaggio (o «nessun messaggio» se vuota); la chat aperta evidenziata.
  Pulsante «Nuova chat»: `POST /api/chat` senza titolo, la chat nuova si apre subito.
- **Chat aperta (a destra):** titolo, pulsante «Elimina» con conferma (`confirm`, «Eliminare la
  chat "…" e tutti i suoi messaggi?»); messaggi in ordine cronologico, domanda a destra e risposta
  a sinistra, con data e ora locali; sotto ogni risposta con strumenti la riga «Strumenti usati:
  nome (argomento: valore, …)». Il `risultato` degli strumenti non si mostra [scelta mia: è già
  riassunto nella risposta e può essere lungo].
- **Invio:** casella di testo, Invio = invia, Maiusc+Invio = a capo; domanda vuota o di soli spazi
  → il pulsante resta disattivato (il back-end la rifiuterebbe con 422).
- **Stato di attesa:** dopo «Invia» la domanda compare subito in grigio, sotto un segnaposto
  «L'assistente sta rispondendo…» animato; casella e pulsante «Invia» disattivati per quella chat.
  Il resto dell'interfaccia resta utilizzabile (elenco, altre chat, nuova chat). All'arrivo della
  risposta la chat si ricarica dal back-end (`GET /api/chat/{id}`) e l'elenco si aggiorna (titolo
  automatico e data). Se nel frattempo l'utente è passato a un'altra chat, la risposta non
  sovrascrive la vista: si aggiorna solo l'elenco [scelta mia].
- **Chat in attesa [scelta mia]:** lo stato d'attesa è tenuto per chat (in memoria della pagina).
  Mentre una chat aspetta la risposta, il suo pulsante «Elimina» è disattivato: il back-end tiene
  la chat bloccata per tutto il turno e l'eliminazione resterebbe in sospeso fino a 600 s.
  Tornando su una chat ancora in attesa si rivedono la domanda in grigio e il segnaposto; tornando
  su una chat il cui invio è fallito si vedono il riquadro d'errore e la domanda nella casella.
  Un invio o un'eliminazione da un'altra scheda del browser non sono gestiti in modo speciale:
  aspettano il back-end come previsto dallo step 7.
- **Errori:** riquadro rosso nella chat aperta (o in cima all'elenco per gli errori dell'elenco),
  con un pulsante per chiuderlo. Testo:
  - corpo `{"errore": "..."}` → quel testo, così com'è (i messaggi del back-end sono già
    comprensibili, in italiano);
  - nessuna risposta (rete, front-end spento) → `Il front-end non risponde: controllare che sia
    avviato.`;
  - altro (corpo non JSON o senza `errore`, es. 404/405 di FastAPI) → `Errore imprevisto (codice
    N).`.
  - Dopo un errore di invio la domanda non resta in grigio: si toglie e **il testo torna nella
    casella**, pronto da rimandare, perché il back-end non l'ha salvata [scelta mia].
  - Chat non trovata (404, per esempio eliminata da un'altra scheda) → messaggio e l'elenco si
    ricarica.
- **Avvio della pagina:** carica l'elenco; se ci sono chat apre la prima, altrimenti mostra
  «Nessuna chat: premi "Nuova chat" per cominciare.». Se l'elenco non arriva (back-end giù) si
  vede il riquadro d'errore e un pulsante «Riprova».
- Pagina in italiano, `lang="it"`, adattata anche a finestre strette (sotto ~700 px l'elenco va
  sopra la chat) [scelta mia]. Nessuna risorsa esterna (font, CDN): tutto servito dal front-end.

## 7. Configurazione

Nuove variabili, tutte facoltative, sezione «Front-end» di `.env.example`:

| Variabile | Predefinito | Note |
|---|---|---|
| `BACKEND_URL` | `http://127.0.0.1:8001` | deve cominciare con `http://` o `https://`, altrimenti uscita 2; `127.0.0.1` e non `localhost` per lo stesso motivo IPv6 di `POSTGRES_HOST` [scelta mia] |
| `FRONTEND_HOST` | `127.0.0.1` | interfaccia su cui ascolta il front-end |
| `FRONTEND_PORTA` | `8002` | intero 1..65535, altrimenti uscita 2 |
| `LOG_LEVEL` | `INFO` | già esistente, stessa validazione degli altri componenti |

Il front-end legge il `.env` della cartella corrente sovrascritto dall'ambiente, come il
back-end. Il `.env` dell'utente non viene modificato: l'utente aggiunge le righe se vuole valori
diversi dai predefiniti (con i predefiniti non serve aggiungere nulla).

## 8. Contratto OpenAPI

- `frontend/contratto/openapi-backend.json` è la copia del documento `/openapi.json` del back-end
  (generato da `backend.app.crea_app`), salvata nel repository e scritta in modo stabile (JSON
  indentato, chiavi nell'ordine di FastAPI, UTF-8 senza BOM).
- `frontend/statico/api.js` contiene una funzione per ogni operazione del contratto (`elencaChat`,
  `creaChat`, `leggiChat`, `eliminaChat`, `inviaMessaggio`), con metodo e percorso dichiarati in
  una tabella in cima al file.
- Il proxy (§6.1) ammette solo metodi e percorsi presenti nel contratto: li legge dal file
  `openapi-backend.json` all'avvio, non da una lista scritta a mano [scelta mia].
- Test (§10): il contratto salvato è uguale all'OpenAPI attuale del back-end (se il back-end
  cambia, il test lo segnala); ogni metodo e percorso di `api.js` esiste nel contratto; i campi
  letti dalla pagina (`id`, `titolo`, `ultimo_messaggio`, `messaggi`, `ruolo`, `testo`,
  `strumenti_usati`, `nome`, `argomenti`, `data`, `domanda`, `risposta`, `errore`) esistono negli
  schemi del contratto.
- Il file si rigenera con `python -m frontend.contratto` [scelta mia]: **scarica** `/openapi.json`
  dal back-end in esecuzione all'indirizzo `BACKEND_URL` (httpx) e lo riscrive. Così anche il
  comando rispetta il vincolo «`frontend/` non importa `backend`»: il front-end riceve il
  contratto dal back-end come un qualunque cliente. Serve il back-end avviato (quindi anche il
  container `db`); con il back-end spento il comando esce con codice 1 e il messaggio
  `Back-end non raggiungibile: ...`, senza toccare il file. Il confronto offline con
  `backend.app.crea_app` resta nei test (§9.1), che possono importare `backend`.

## 9. Test e prove

### 9.1 Test automatici (suite normale, niente rete, database o modello)

- `tests/test_frontend_configurazione.py`: predefiniti, porte e `BACKEND_URL` non validi
  (messaggio che nomina la variabile), `.env` sovrascritto dall'ambiente.
- `tests/test_frontend_app.py` con `TestClient` e un back-end simulato (`httpx.MockTransport`):
  pagina e file statici serviti (`/`, `/app.js`, … con `Content-Type` giusto e `charset=utf-8`);
  inoltro di ogni operazione del contratto (metodo, percorso, query, corpo, codice, corpo di
  ritorno, 204 senza corpo); errori del back-end restituiti così come sono (404, 422, 502, 503,
  504 con `{"errore"}`); back-end non raggiungibile → 503 del proxy; tempo scaduto → 504 del
  proxy; percorsi fuori contratto → 404 senza chiamare il back-end; righe di log.
- `tests/test_frontend_avvio.py`: `python -m frontend` con configurazione non valida → uscita 2;
  `frontend.contratto` con back-end simulato (scrive il file) e con back-end giù (uscita 1, file
  intatto).
- `tests/test_frontend_indipendente.py`: nessun file di `frontend/` importa `assistente` o `backend`;
  nessun file di `frontend/statico/` contiene `8000`, `8001`, `localhost`, `127.0.0.1` o
  `AGENTE` (indirizzi non scritti nel codice della pagina).
- `tests/test_frontend_contratto.py`: i controlli del §8.
- `tests/test_frontend_js.py`: esegue `node --test tests/js/` se Node è installato, altrimenti
  `skip` con il motivo. `tests/js/logica.test.mjs` prova le funzioni pure di `logica.js`: testo
  dell'errore dalle tre forme di risposta, formato di date e strumenti, domanda vuota.

### 9.2 Prova reale (marker `reale`, con `PROVE_REALI=1` e `PROVE_POSTGRES=1`)

`test_frontend_chat_con_strumento` in fondo a `tests/test_reale.py`: front-end in-process
(`TestClient`) collegato a un back-end vero (in-process, database `<POSTGRES_DB>_prove`) e
all'agente vero già avviato: crea una chat via `/api/chat`, invia «Quanto fa 45 diviso 9?»,
verifica risposta con `5` e `calcola` tra gli strumenti, legge la chat, la elimina. Dimostra la
catena front-end → back-end → agente → strumento senza browser.

### 9.3 Prove manuali dal browser (le fa l'utente, un unico messaggio dopo l'implementazione)

1. Conversazione completa dal browser con uno strumento (evidenza 1): nuova chat, domanda con
   calcolo, risposta con «Strumenti usati: calcola»; seconda domanda nella stessa chat.
2. Riavvio (evidenza 2): chiudere front-end e back-end, `docker compose restart db`, riavviare
   back-end e front-end, ricaricare la pagina: la chat c'è ancora con i suoi messaggi.
3. Agente spento (evidenza 3): fermare l'agente, inviare una domanda: riquadro «Agente non
   raggiungibile…», la domanda torna nella casella, l'elenco e le altre chat restano usabili;
   riaccendere l'agente e rimandare: risposta.
4. Back-end spento: la pagina mostra «Back-end non raggiungibile…» e «Riprova» funziona dopo il
   riavvio del back-end.
5. Eliminazione dall'interfaccia con conferma.

Gli esiti vanno nel README («Esiti delle prove reali», step 8).

## 10. Documentazione

- README: sezione «Front-end (interfaccia di chat)» dopo «Back-end»: file, avvio in quattro
  finestre (agente, back-end, front-end, browser su `http://localhost:8002`), configurazione,
  errori, log, rigenerazione del contratto, test; voce nella checklist delle prove reali; esiti.
- `CLAUDE.md`: punto «(lezione 6, step 8)» nell'obiettivo; riga sulle prove dal browser.
- `.env.example`: sezione «Front-end».

## 11. Git

Branch `feat/frontend` da `dev`. Commit per incremento verificato (Conventional Commits in
italiano, scope `frontend`). Merge `--no-ff` in `dev` solo con conferma dell'utente; niente push.

## 12. Lasciato al builder

- Nomi interni di funzioni Python e JavaScript, struttura del CSS e aspetto grafico (sobrio,
  leggibile, contrasto adeguato), animazione del segnaposto d'attesa.
- Come caricare i moduli JavaScript (`<script type="module">` consigliato).
- Suddivisione dei test in file, purché i casi del §9.1 ci siano.
