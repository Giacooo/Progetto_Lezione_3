# Specifica — Lezione 6, step 6: l'agente come servizio HTTP

Data: 2026-11-16. Stato: **approvata dall'utente il 2026-11-16**.
Fonte dei requisiti: `LLM_Lez_6.pdf` (pag. 12 «L'applicazione finale: quattro container», pag. 13
«Step 6 · L'agente come servizio HTTP», pag. 17 «Metodo e consegna», pag. 19 «Consegna»),
`assistente-laboratorio/CLAUDE.md`, decisioni dell'utente nel brainstorming del 2026-11-16.

Le voci marcate **[scelta mia]** non sono state decise dall'utente: sono decisioni di chi ha
scritto la specifica, da controllare in lettura. Tutto il resto è richiesto dal PDF o deciso
dall'utente.

---

## 1. Intento

Finora l'agente era un'applicazione da terminale. Per servire più avanti un'interfaccia web
(step 7–9) deve esporre un'API: riceve la conversazione e restituisce la risposta. Obiettivo del
PDF: «lo stesso grafo risponde sia alla CLI sia alle chiamate HTTP, senza duplicare la logica».

Parte dallo step 5 (prompt MCP) funzionante e unito in `dev` (merge `0290b96`).

## 2. Obiettivi (dal PDF, «Cosa realizzare»)

1. **01** — Separare il modulo dell'agente dall'interfaccia: la CLI diventa un client dell'API.
2. **02** — Endpoint che riceve messaggio e cronologia e restituisce risposta e strumenti usati.
3. **03** — Endpoint di stato: agente, server MCP e modello raggiungibili.
4. **04** — Agente senza stato: cronologia ed eventuale riassunto arrivano dal chiamante e
   tornano aggiornati.

Evidenze richieste dal PDF:
- chiamata HTTP con una domanda che usa un tool: risposta e traccia nei log;
- modello o strumenti non disponibili: codice e messaggio di errore comprensibili;
- test dell'API con il grafo simulato; documentazione OpenAPI consultabile.

Consegna (pag. 19): test automatici, prova reale con LM Studio, README aggiornato e commit;
evidenza minima: **«stessa risposta dalla CLI e dall'API»**.

## 3. Non obiettivi e anti-obiettivi

- Niente back-end, PostgreSQL, salvataggio delle chat, front-end, CORS (step 7–9). La conversazione
  continua a non essere salvata: la tiene in memoria il client (la CLI) per la durata della sessione.
- Niente compose a quattro container né «agente non esposto» (step 9).
- Niente streaming (facoltativo del PDF, solo se l'utente lo decide).
- Niente autenticazione, niente Streamable HTTP per MCP (il server MCP resta stdio).
- **Anti-obiettivo:** due copie della logica del turno (una per la CLI, una per l'API), oppure una
  CLI che costruisce ancora grafo, modello o collegamento MCP. Sarebbe «funziona» ma contro il PDF.
- **Anti-obiettivo:** perdere comportamenti degli step 1–5 (router, revisore, riassunto, preferenze,
  `/prompts` e `/prompt`, codici di uscita, messaggi di errore chiari).

## 4. Vincoli

- Modello `google/gemma-4-e2b` in LM Studio sull'host; server MCP FastMCP stdio come oggi.
- Codice sincrono dove possibile; l'asincrono resta isolato in `collegamento_mcp.py`.
- Dipendenze motivate e con versione fissata (vedi §6).
- Test automatici senza modello né rete; prove reali separate (`PROVE_REALI=1`).
- Comandi documentati per PowerShell.
- Si toccano file degli step precedenti (`terminale.py`, `conversazione.py`, `tests/test_reale.py`,
  `tests/test_terminale.py`, `tests/test_conversazione.py`, `compose.yaml`, `Dockerfile`,
  `.env.example`, README): è richiesto dallo step stesso (la CLI diventa client). **Approvando questa
  specifica l'utente approva queste modifiche.** Gli altri moduli (`grafo.py`, `router.py`,
  `revisore.py`, `riassunto.py`, `preferenze.py`, `server_mcp.py`, `strumenti_mcp/`) non cambiano.

## 5. Approcci considerati

Scelta del modo di scrivere il servizio HTTP (decisa dall'utente: **1**):

1. **FastAPI** — modelli pydantic (già presente) da cui nasce da solo il documento OpenAPI con la
   pagina `/docs`; endpoint come funzioni sincrone (`def`), eseguite da FastAPI in un thread a parte,
   quindi il grafo e `asyncio.run` di `collegamento_mcp.py` restano come sono; `TestClient` per i
   test senza aprire porte. Costo: una dipendenza nuova. **Scelto.**
2. **Starlette** (già installato) — nessuna dipendenza nuova, ma OpenAPI scritto a mano e da tenere
   allineato: lavoro doppio proprio sull'evidenza «OpenAPI consultabile».
3. **`http.server` della libreria standard** — zero dipendenze, ma instradamento, JSON, codici e
   OpenAPI tutti a mano: più codice, più fragile.

Altre decisioni dell'utente nel brainstorming:
- **`/prompts` e `/prompt` (strada A):** l'agente espone anche due endpoint per i prompt; la CLI
  parla solo con l'API. (Scartate: B, la CLI tiene una sua connessione MCP; C, `/prompt` tolto.)
- **Docker (scelta a):** due servizi nel compose, `agente` (porta pubblicata per provare `/docs`) e
  `cli` (interattiva, punta all'agente). La sistemazione a quattro container resta allo step 9.
  (Scartata: b, Docker rotto fino allo step 9.)

## 6. Dipendenze

In `requirements.txt`, con versione fissata:
- `fastapi==0.163.1` — servizio HTTP con OpenAPI e `/docs` generati dai modelli pydantic. Verificato
  con `pip install --dry-run`: con le librerie attuali aggiunge solo `fastapi` e `annotated-doc`
  (starlette 1.10.0 e pydantic 2.14.1 già presenti vanno bene).
- `uvicorn==0.54.0` — il server che fa girare l'app. È già installato (lo porta fastmcp), ma
  diventa una dipendenza diretta, quindi la si fissa **[scelta mia]**.

Il client HTTP della CLI usa `httpx==0.28.1`, già presente. `TestClient` di FastAPI usa httpx.

## 7. Architettura

```
CLI (python -m assistente)            Servizio dell'agente (python -m assistente.servizio)
  terminale.py: Tu>, esci,   ──HTTP──▶  servizio.py: FastAPI, endpoint, codici di errore
  /prompts, /prompt                       │
  cliente.py: client httpx,               ▼
  tiene cronologia e riassunto          agente.py: costruzione dei pezzi + turno senza stato
                                          │
                                          ▼
                                        grafo.py (invariato) ── LM Studio (host)
                                        collegamento_mcp.py ── server MCP stdio (sottoprocesso)
```

### 7.1 `assistente/agente.py` (nuovo) — il modulo dell'agente

- `costruisci_agente(config, cartella) -> Agente`: fa ciò che oggi fa `terminale.main()` nei punti
  3–4: connessione stdio, discovery (`ErroreCollegamentoMCP` se il server non parte), preferenze
  (una volta sola), strumenti, modello, router, revisore, riassuntore, grafo. Stesso ordine e stessi
  log di oggi. `Agente` conserva il grafo, la connessione MCP e la configurazione (servono per i
  prompt e per lo stato); **non conserva nessuna conversazione**. La «sessione» dello step 4 diventa
  la vita del servizio: le preferenze si leggono all'avvio del servizio, e dopo una modifica di
  `preferenze.json` basta riavviarlo (nessuna modifica del codice).
- `esegui_turno(grafo, cronologia, nuovi, riassunto) -> EsitoTurno`: la logica che oggi sta in
  `Conversazione.chiedi_messaggi` (invocazione del grafo con `passi=0`, `revisioni=0`; traduzione
  degli errori; controllo «limite di passaggi» e «risposta vuota»), ma restituisce un risultato
  invece di aggiornare una memoria interna. `EsitoTurno` contiene `risposta` (testo),
  `strumenti_usati`, `cronologia` aggiornata e `riassunto` aggiornato.
- **Strumenti usati del turno:** le richieste di tool (`tool_calls` degli `AIMessage`) prodotte
  durante il turno, nell'ordine, ciascuna con `nome`, `argomenti` e `risultato` (il testo del
  `ToolMessage` con lo stesso id). Quelle già presenti nella cronologia ricevuta non contano. Il
  modo di distinguere i messaggi nuovi da quelli ricevuti (anche dopo una compressione del
  riassunto, che toglie messaggi vecchi) è lasciato al piano, ma va coperto da test.
- **Errori classificati** per il servizio: ogni errore del turno porta un «tipo» da cui il servizio
  ricava il codice HTTP (§7.3). Messaggi in italiano uguali a quelli di oggi.
- Le funzioni per i prompt (`elenca_prompt`, `richiama_prompt`) avvolgono quelle di
  `collegamento_mcp.py` con la connessione dell'agente; `richiama_prompt` passa poi i messaggi
  ottenuti a `esegui_turno`, come oggi `chiedi_messaggi`.

`conversazione.py`: `Conversazione` resta come «client in memoria» (usato da test e prove reali):
tiene cronologia e riassunto e per ogni turno chiama `esegui_turno` **[scelta mia]**. Così la logica
del turno esiste in un solo posto e le prove reali esistenti continuano a girare.

### 7.2 Formato della cronologia sull'API

La cronologia viaggia completa, comprese richieste di tool e `ToolMessage`: servono al taglio del
riassunto (step 3), che non separa mai una richiesta dal suo risultato. Ogni messaggio è un oggetto
JSON descritto nello schema OpenAPI **[scelta mia sui nomi]**:

| Campo | Tipo | Significato |
|---|---|---|
| `ruolo` | `"utente"` / `"assistente"` / `"strumento"` | `HumanMessage` / `AIMessage` / `ToolMessage` |
| `testo` | stringa | contenuto del messaggio |
| `nome` | stringa o null | nome del mittente (es. `"revisore"` per le indicazioni del revisore) o dello strumento |
| `richieste_strumenti` | lista di `{id, nome, argomenti}` | solo per `assistente`: le richieste di tool |
| `id_chiamata` | stringa o null | solo per `strumento`: l'id della richiesta a cui risponde |

La conversione LangChain ⇄ JSON sta in `agente.py` (o in un modulo piccolo a parte, a scelta del
piano) e va provata con un giro completo (andata e ritorno identici). Messaggi di sistema non
compaiono: il prompt di sistema lo aggiunge il grafo a ogni chiamata.

### 7.3 `assistente/servizio.py` (nuovo) — l'API

Avvio: `python -m assistente.servizio`. `main()`:
1. legge e controlla la configurazione come oggi (`carica_configurazione`); se non valida stampa il
   motivo su stderr ed esce con **codice 2**;
2. `configura_log`;
3. `costruisci_agente`; se il server MCP non è disponibile stampa «Server MCP non disponibile: …»
   ed esce con **codice 3** (come oggi la CLI);
4. avvia uvicorn su `AGENTE_HOST`:`AGENTE_PORTA` (§8). I log dell'agente (router, strumenti,
   revisore, riassunto, preferenze, prompt) compaiono nella finestra del servizio, nello stesso
   formato di oggi.

Endpoint (tutti con modelli pydantic, quindi descritti nel documento OpenAPI):

| Metodo e percorso | Richiesta | Risposta 200 |
|---|---|---|
| `POST /messaggio` | `messaggio` (stringa non vuota), `cronologia` (lista, predefinita vuota), `riassunto` (stringa, predefinita vuota) | `risposta`, `strumenti_usati`, `cronologia`, `riassunto` |
| `GET /stato` | — | `agente`, `server_mcp`, `modello` (ognuno `ok` o un messaggio di errore) |
| `GET /prompts` | — | elenco dei prompt: `nome`, `descrizione`, `argomenti` (`nome`, `descrizione`, `obbligatorio`) |
| `POST /prompts/{nome}` | `argomenti` (oggetto stringa→stringa), `cronologia`, `riassunto` | come `POST /messaggio` |

- **`/stato`**: `agente` è sempre `ok` se il servizio risponde; `server_mcp` con una `tools/list`
  fresca (nuova sessione stdio); `modello` con `GET {LM_BASE_URL}/models` (timeout breve, 5 s
  **[scelta mia]**) e controllo che `LM_MODEL` sia nell'elenco. Codice **200** se tutto è `ok`,
  **503** se qualcosa non va, con lo stesso corpo. Una riga di log per ogni controllo.
- **`/docs`** (pagina interattiva) e **`/openapi.json`**: generati da FastAPI. Titolo, descrizione e
  descrizione di ogni endpoint in italiano.
- **Log della chiamata** (evidenza «traccia nei log») **[scelta mia sul formato]**: all'arrivo
  `richiesta endpoint=/messaggio messaggi_cronologia=N riassunto=sì|no`; alla fine
  `risposta endpoint=/messaggio strumenti=[...] messaggi_cronologia=M`; in mezzo le righe già
  esistenti del grafo (router, `variant=… tool=…`, revisore).

**Codici di errore** (corpo JSON `{"errore": "<messaggio in italiano>"}`, documentato nello schema
OpenAPI) **[scelta mia sulla corrispondenza]**:

| Caso | Codice | Messaggio (come oggi nella CLI) |
|---|---|---|
| LM Studio non raggiungibile | 503 | «Connessione fallita: controllare LM Studio, URL e porta.» |
| Attesa scaduta | 504 | «Attesa scaduta: controllare server, carico e tempi.» |
| Errore restituito da LM Studio (es. id del modello sbagliato) | 502 | «Errore dal server: …» |
| Risposta vuota del modello | 502 | «Il modello ha restituito una risposta vuota.» |
| Limite di passaggi raggiunto | 500 | «Limite di passaggi raggiunto: riprova con una domanda diversa.» |
| Errore inatteso | 500 | «Errore inatteso: … (dettagli nel log)» |
| Server MCP non disponibile per `/prompts` o `/prompts/{nome}` | 503 | «Server MCP non disponibile: …» |
| Comando prompt non valido (prompt o argomento sconosciuto, obbligatorio mancante) | 400 | messaggio dello step 5 |
| Corpo della richiesta non valido (es. `messaggio` vuoto) | 422 | errore di validazione standard di FastAPI |

**Strumenti non disponibili durante un turno [scelta mia, da controllare per prima]:** oggi, se il
server MCP cade durante una chiamata a uno strumento, il grafo non interrompe il turno: il risultato
dello strumento diventa «Errore di collegamento con il server MCP: …» e il modello risponde di
conseguenza. Questo comportamento resta (cambiarlo vorrebbe dire toccare `grafo.py`). L'evidenza
«strumenti non disponibili: codice e messaggio comprensibili» si mostra quindi così:
(a) servizio che non parte con codice 3 e messaggio chiaro se il server MCP è giù all'avvio;
(b) `GET /stato` → 503 con `server_mcp` che spiega il problema;
(c) `POST /messaggio` → 200 con, in `strumenti_usati`, il `risultato` «Errore di collegamento con il
server MCP: …» ben visibile.

### 7.4 La CLI come client

- `assistente/cliente.py` (nuovo): `ClienteAgente(url)` con `chiedi(domanda)`,
  `elenca_prompt()`, `richiama_prompt(nome, argomenti)`. Tiene **lei** `cronologia` (in formato JSON,
  così come arriva dall'API) e `riassunto`, e li aggiorna solo se la chiamata riesce (stessa «regola
  d'oro» di oggi). Errori → `ErroreTurno` con il messaggio `errore` del servizio; agente non
  raggiungibile → «Agente non raggiungibile: controllare che il servizio sia avviato e AGENTE_URL.»
  Timeout del client: 600 s **[scelta mia]** (un turno può fare più chiamate al modello da 120 s).
- `terminale.py`: `ciclo()` non cambia. `crea_smistamento` riceve il client invece di grafo e
  connessione MCP: `/prompts` → `GET /prompts` (testo formattato come oggi da `testo_elenco_prompt`);
  `/prompt …` → lettura del comando in locale con `leggi_comando_prompt` (solo sintassi: virgolette,
  `=`), poi `POST /prompts/{nome}`; il controllo rispetto a `prompts/list` lo fa l'agente. Il
  WARNING «prompt rifiutato» resta nei log dell'agente per i controlli, e in quelli della CLI per gli
  errori di sintassi (come oggi).
- `main()` della CLI: legge solo la configurazione del client (§8); configurazione non valida →
  codice 2. Non costruisce più nulla dell'agente e non avvia il server MCP. Non controlla l'agente
  all'avvio: se non risponde, lo dice al primo turno e la chat continua **[scelta mia]**.

## 8. Configurazione

Nuove variabili in `.env.example` (il `.env` dell'utente non si tocca: le nuove sono tutte
facoltative con valore predefinito):

| Variabile | Chi la usa | Predefinita | Significato |
|---|---|---|---|
| `AGENTE_URL` | CLI | `http://localhost:8000` | indirizzo del servizio dell'agente |
| `AGENTE_HOST` | servizio | `127.0.0.1` | interfaccia su cui ascolta (in Docker `0.0.0.0`) |
| `AGENTE_PORTA` | servizio | `8000` | porta del servizio |

Il servizio richiede le variabili di oggi (`LM_BASE_URL`, `LM_MODEL`, `FUSO_ORARIO`,
`AMBITO_AGENTE`, …). La CLI richiede solo le sue (`AGENTE_URL`, `LOG_LEVEL`): una funzione di
caricamento separata, con gli stessi controlli di stile di `configurazione.py` (URL che inizia con
`http://` o `https://`, porta intera tra 1 e 65535) **[scelta mia]**.

## 9. Docker

- `Dockerfile`: invariato nella sostanza (stessa immagine per i due servizi) **[scelta mia]**.
- `compose.yaml`: due servizi dalla stessa immagine:
  - `agente`: `command: python -m assistente.servizio`, `env_file: .env`, `LM_BASE_URL` verso
    `host.docker.internal`, `AGENTE_HOST=0.0.0.0`, `ports: "8000:8000"` (per `/docs` dal browser),
    volume `./archivio:/app/archivio` (note e preferenze), `extra_hosts` come oggi;
  - `cli`: `command: python -m assistente`, interattiva (`stdin_open`, `tty`),
    `AGENTE_URL=http://agente:8000`, `depends_on: agente`.
- Uso documentato: `docker compose up -d --build agente`, poi `docker compose run --rm cli`.

## 10. Test

Automatici (senza modello né rete):
- `tests/test_agente.py`: `esegui_turno` senza stato (stesso input → stesso output, l'input non viene
  modificato), cronologia e riassunto restituiti aggiornati, `strumenti_usati` con nome, argomenti e
  risultato (anche dopo una compressione del riassunto, e ignorando i tool dei turni precedenti),
  errori classificati per tipo; conversione JSON ⇄ messaggi (andata e ritorno).
- `tests/test_servizio.py` (`TestClient`, **grafo simulato** con i finti di `tests/finti.py`, nessun
  server MCP vero): `POST /messaggio` con un tool (risposta, `strumenti_usati`, righe di log); con
  cronologia e riassunto in ingresso; codici 503/504/502/500/422 con il messaggio giusto; `/prompts`
  e `/prompts/{nome}` (400 per argomenti non validi, senza chiamare il modello); `/stato` 200 e 503
  con controlli finti; `/openapi.json` contiene i quattro percorsi e lo schema del messaggio.
- `tests/test_cliente.py` (HTTP simulato con `httpx.MockTransport`): cronologia e riassunto
  rimandati e aggiornati solo se la chiamata riesce; messaggi di errore; agente non raggiungibile.
- `tests/test_terminale.py`, `tests/test_conversazione.py`: adattati alla nuova forma.
- `tests/test_configurazione.py`: nuove variabili.

Prove reali (`PROVE_REALI=1`, LM Studio acceso):
- `tests/test_reale.py` usa `costruisci_agente` invece di ripetere il montaggio a mano; le prove
  esistenti continuano a girare.
- Nuove: domanda con tool attraverso `TestClient` con l'agente vero (risposta e `strumenti_usati`);
  **stessa risposta dalla CLI e dall'API**: la stessa domanda deterministica (`calcola`, es. 45/9)
  mandata con `ClienteAgente` e con una chiamata HTTP diretta dà lo stesso risultato e lo stesso
  strumento.

Prove manuali (le fa l'utente, in un unico messaggio di istruzioni): due finestre PowerShell
(servizio e CLI); domanda con tool dalla CLI e la stessa con `Invoke-RestMethod`; `/docs` nel
browser; `/stato` con LM Studio acceso e spento; domanda con LM Studio spento (503); servizio con il
server MCP rotto (codice 3); `/prompts` e `/prompt` dalla CLI. Poi Docker con i due servizi.

## 11. Documentazione

- README: nuova sezione «Agente come servizio HTTP» (avvio in due finestre, endpoint, esempi
  `Invoke-RestMethod`, `/docs`, codici di errore, formato dei log della chiamata); configurazione,
  avvio locale e Docker aggiornati; checklist delle prove (voci nuove dopo la 52); esiti dopo le prove.
- `CLAUDE.md`: architettura (agente come servizio, CLI client) e comandi di avvio, perché cambiano.

## 12. Lasciato a chi implementa

- Come distinguere i messaggi nuovi del turno da quelli ricevuti (vedi §7.1), purché provato.
- Nomi interni di funzioni e classi non citati qui; dove mettere la conversione JSON ⇄ messaggi.
- Ordine dei blocchi e dei commit nel piano.

Già decisi nella rilettura **[scelte mie]**:
- un messaggio `strumento` senza `id_chiamata`, o un `ruolo` sconosciuto, è un corpo non valido →
  422 (validazione pydantic), senza chiamare il modello;
- la CLI ricostruisce dall'elenco JSON di `GET /prompts` gli oggetti che `testo_elenco_prompt` già
  usa, così il testo di `/prompts` resta identico a quello dello step 5;
- due richieste contemporanee sono ammesse (il grafo non ha stato; ogni chiamata a uno strumento apre
  già una sessione MCP propria); non serve nessun blocco;
- i log di uvicorn (avvio, una riga per richiesta) restano al loro livello; i log `assistente.*`
  mantengono il formato di `configura_log`.
