# Assistente del laboratorio: grafo LangGraph con orologio e Docker Compose

Data: 2026-10-26 · Lezione 4 · Stato: approvata il 2026-10-27

## 1. Intento

Trasformare il client della lezione 3 in un'applicazione da terminale il cui flusso è
descritto da un **grafo LangGraph esplicito**: l'utente scrive domande, il grafo interroga
il modello servito da LM Studio sull'host, il modello può richiedere uno **strumento
orologio** che il programma esegue davvero, e la conversazione resta disponibile per tutta
la sessione. L'applicazione si avvia anche in un container tramite **Docker Compose**.

È la base delle lezioni successive (altri strumenti, MCP, workflow, RAG): la struttura deve
rendere naturale aggiungere nodi e strumenti senza riscrivere l'applicazione. Oggi però si
costruisce solo ciò che è descritto qui.

Il risultato deve dimostrare, con prove e non con risposte plausibili, che:
1. la conversazione attraversa il grafo e la cronologia si conserva su più turni;
2. una domanda sull'ora produce una richiesta di tool, un'esecuzione reale e una risposta
   finale che usa il risultato, tutto visibile nei log;
3. il container raggiunge LM Studio sull'host.

## 2. Obiettivi, non obiettivi, anti-obiettivi

**Obiettivi**
- Grafo con stato, nodi e archi riconoscibili: nodo LLM, nodo strumenti, arco condizionale,
  limite di passaggi.
- Cronologia in memoria per la durata della sessione.
- Strumento orologio con fuso orario esplicito nel risultato.
- Log che rendono visibile il percorso: chiamate al modello, richieste di tool, risultati.
- Avvio locale (venv) e con Docker Compose; LM Studio resta sull'host.
- Test automatici che non richiedono il modello; prove reali separate e documentate.

**Non obiettivi (per ora)**
- Persistenza della conversazione (alla chiusura si perde).
- Altri strumenti, MCP, RAG, workflow, interfacce web o grafiche, servizi cloud.
- Streaming della risposta token per token.
- Containerizzare LM Studio.

**Anti-obiettivi (fallimento anche se "funziona")**
- Una risposta sull'ora prodotta dal modello senza traccia di chiamata allo strumento,
  presentata come prova del funzionamento.
- L'applicazione che inventa una risposta quando LM Studio non è raggiungibile.
- Un ciclo modello-strumento che può girare senza fine.
- Fuso orario del container dedotto implicitamente dall'host o assente nel risultato.
- Identificativo del modello scritto nel codice o inventato.

## 3. Vincoli (da CLAUDE.md e dal PDF della lezione 4)

- Lavoro solo in `lezione_3/repo-lab-llm/assistente-laboratorio/`, nel branch corrente;
  il codice della lezione 3 alla radice non si tocca e non si copia.
- Python sincrono, moduli piccoli, separazione tra grafo, collegamento al modello,
  strumenti e interfaccia da terminale.
- LM Studio raggiunto tramite l'API compatibile con OpenAI; URL e identificativo del modello
  solo da variabili d'ambiente (identificativo letto da `GET /v1/models`).
- File di configurazione di esempio senza credenziali; `.env` reale fuori da Git
  (già escluso dal `.gitignore` della radice).
- Dipendenze motivate e con versioni fissate.
- Comandi documentati per PowerShell.
- Commit Conventional Commits in italiano, dopo verifica; push solo su richiesta.
- Ambiente disponibile: Windows 11, Python 3.13, Docker Desktop 29.2,
  modello di riferimento `google/gemma-4-e2b` (4 bit) in LM Studio.

## 4. Comportamento atteso

### 4.1 Sessione da terminale
- All'avvio l'applicazione legge e valida la configurazione; se manca una variabile
  obbligatoria o il fuso orario non è valido, termina subito con un messaggio chiaro
  (nessun traceback grezzo).
- Prompt `Tu> `; la risposta viene stampata intera quando il turno è completato.
- `esci`, Ctrl+C o fine input (EOF) chiudono la sessione in modo pulito.
- Righe vuote ignorate.

### 4.2 Turno di conversazione (il grafo)

```
START → llm ──(richiesta di tool e passi < limite)──→ strumenti ─┐
         ↑ └─(nessuna richiesta di tool)──→ END                   │
         │  └─(richiesta di tool e limite raggiunto)──→ END (turno fallito)
         └────────────────────────────────────────────────────────┘
```

- **Stato**: la lista dei messaggi (con il riduttore che *aggiunge* i messaggi, non li
  sostituisce) e un contatore dei passaggi del turno corrente.
- **Nodo `llm`**: invia al modello il messaggio di sistema, la cronologia e la descrizione
  dello strumento; aggiunge allo stato il messaggio di risposta; incrementa il contatore.
- **Arco condizionale**: guarda se l'ultimo messaggio del modello contiene richieste
  strutturate di tool.
- **Nodo `strumenti`**: esegue ogni tool richiesto e aggiunge il risultato come messaggio
  di tool associato alla richiesta corrispondente; torna sempre a `llm`.
- **Limite di passaggi**: massimo `MAX_PASSI` chiamate al modello per turno (default 5).
  Se il modello chiede ancora un tool quando il limite è raggiunto, il turno termina senza
  eseguirlo, il terminale mostra «Limite di passaggi raggiunto: riprova con una domanda
  diversa.» e il log registra un avviso.
- Il messaggio di sistema (in italiano, indica che per data e ora va usato lo strumento)
  è aggiunto a ogni chiamata dal nodo `llm` e **non** fa parte della cronologia.

### 4.3 Cronologia
- La cronologia vive in memoria nel programma da terminale e viene passata al grafo a ogni
  turno; il grafo restituisce la cronologia aggiornata.
- Un turno riuscito aggiunge: domanda dell'utente, eventuali richieste di tool e relativi
  risultati, risposta finale. Nessuna duplicazione.
- Un turno fallito (errore di connessione, errore HTTP, timeout, limite di passaggi)
  **non** modifica la cronologia: la conversazione riprende dallo stato precedente
  (come faceva il client della lezione 3).

### 4.4 Errori del modello
Messaggi riconoscibili, mai una risposta inventata:
- server non raggiungibile → «Connessione fallita: controllare LM Studio, URL e porta.»
- timeout → «Attesa scaduta: controllare server, carico e tempi.»
- errore HTTP (es. modello sbagliato) → «Errore dal server:» con codice e testo ricevuto.

Dopo un errore la sessione continua.

### 4.5 Strumento orologio (contratto)

| Parte | Decisione |
|---|---|
| Nome | `ora_corrente` |
| Descrizione | Restituisce data e ora correnti nel fuso orario configurato. Da usare ogni volta che servono data, ora o giorno della settimana attuali. |
| Parametri | Nessuno (fuso fisso dalla configurazione) — *scelta mia, vedi §8* |
| Risultato | Testo con data e ora ISO 8601 con offset e nome del fuso, per esempio `2026-10-26T18:05:12+01:00 (Europe/Rome)` |
| Errori | Il fuso è validato all'avvio (§4.1); a runtime lo strumento non ha casi d'errore previsti |

- Il fuso viene da `FUSO_ORARIO` (nome IANA), mai dal sistema operativo; il risultato è lo
  stesso in locale e nel container.
- La funzione deve permettere di iniettare l'istante corrente, così i test confrontano
  valori fissi.

### 4.6 Log
- Modulo `logging` standard verso stderr, livello da `LOG_LEVEL` (default `INFO`).
- A livello INFO devono comparire almeno: inizio e fine di ogni chiamata al modello
  (con numero del passaggio), ogni richiesta di tool con nome e argomenti, ogni risultato
  del tool, l'avviso di limite raggiunto, gli errori.
- I log compaiono nello stesso terminale della chat e in `docker logs`; devono essere
  distinguibili dalle risposte (prefisso con livello e nome del componente).

## 5. Configurazione

`.env.example` (versionato) e `.env` (locale, escluso):

| Variabile | Obbligatoria | Esempio / default |
|---|---|---|
| `LM_BASE_URL` | sì | `http://localhost:1234/v1` |
| `LM_MODEL` | sì | `ID_MODELLO_REALE` (da `GET /v1/models`) |
| `FUSO_ORARIO` | sì | `Europe/Rome` |
| `MAX_PASSI` | no | `5` |
| `LOG_LEVEL` | no | `INFO` |

Le variabili già presenti nell'ambiente hanno precedenza su `.env`.
Parametri della richiesta al modello mantenuti dalla lezione 3: temperatura bassa e
`reasoning_effort: "none"` (senza, gemma consuma i token ragionando e risponde vuoto).

## 6. Scelte tecniche

- **LangGraph** per il grafo (richiesto dal corso).
- **langchain-openai** (`ChatOpenAI` con `base_url` di LM Studio) come collegamento al
  modello: converte la descrizione dello strumento e le richieste di tool nel formato
  dell'API compatibile con OpenAI, che è ciò che LM Studio espone. *Scelta mia.*
- **python-dotenv** per leggere `.env` (già usato nella lezione 3).
- **tzdata** (pacchetto Python) perché l'immagine Docker slim non contiene il database dei
  fusi orari, necessario a `zoneinfo`.
- **pytest** per i test (dipendenza di sviluppo, separata da quelle dell'applicazione).
- Versioni fissate nel piano, dopo aver verificato le ultime disponibili e compatibili con
  Python 3.13.
- Avvio locale come modulo (`python -m assistente`) da un venv dedicato in
  `assistente-laboratorio/.venv`.

## 7. Docker

- `Dockerfile` su immagine Python 3.13 slim; installa solo le dipendenze
  dell'applicazione; avvia `python -m assistente`.
- `.dockerignore` che esclude `.env`, `.venv`, cache, test e documentazione non necessari.
- `compose.yaml` con un servizio `assistente`:
  - `build: .`, `stdin_open: true`, `tty: true` (sessione interattiva);
  - `env_file: .env` e, in `environment`, `LM_BASE_URL=http://host.docker.internal:1234/v1`
    che sovrascrive l'indirizzo locale;
  - `extra_hosts: host.docker.internal:host-gateway` (innocuo su Docker Desktop, utile su Linux);
  - nessuna porta pubblicata.
- Avvio documentato: `docker compose build` poi
  `docker compose run --rm --name assistente-demo assistente`; da un secondo terminale
  `docker logs -f assistente-demo`.
- LM Studio deve accettare connessioni dalla rete locale (opzione "Serve on Local
  Network" o equivalente) perché il container lo raggiunga: va scritto nel README.

## 8. Decisioni prese da me (da controllare)

1. **Fuso fisso senza parametri** per l'orologio: più semplice per un modello piccolo e
   per i test; un parametro validato si potrà aggiungere in seguito.
2. **langchain-openai** invece di chiamate HTTP scritte a mano.
3. **Niente streaming**: la risposta finale arriva intera; nel grafo con tool lo streaming
   complicherebbe il codice senza servire ai requisiti.
4. **`MAX_PASSI = 5`** chiamate al modello per turno.
5. **Turno fallito scartato** dalla cronologia (errore o limite).
6. **Cronologia tenuta dal programma da terminale** e passata al grafo, invece di un
   checkpointer: nessuna persistenza richiesta e il comportamento sui turni falliti resta
   semplice.

## 9. Verifica

### 9.1 Test automatici (senza modello, `pytest`)
Modello simulato con risposte predefinite (anche richieste di tool) e istante controllato.
Coprono almeno:
- orologio: valore atteso per un istante fisso in `Europe/Rome`, ora legale e solare,
  presenza di offset e nome del fuso;
- configurazione: variabili mancanti e fuso non valido producono un errore chiaro;
- grafo, domanda ordinaria: una sola chiamata al modello, nessun tool, risposta aggiunta;
- grafo, domanda sull'ora: richiesta di tool → esecuzione → risultato associato alla
  richiesta corretta → seconda chiamata → risposta finale;
- cronologia: dopo due turni contiene entrambe le domande e risposte, senza duplicati;
- limite: un modello che chiede sempre il tool si ferma a `MAX_PASSI` chiamate;
- errori: connessione/timeout/HTTP simulati danno il messaggio previsto e lasciano
  invariata la cronologia;
- log: la richiesta di tool e il risultato compaiono nei log catturati.

### 9.2 Prove reali (attivate esplicitamente, descritte nel README)
- Una prova automatica con LM Studio attivo, saltata a meno di una variabile esplicita
  (es. `PROVE_REALI=1`), che verifica che il modello reale chieda `ora_corrente` a una
  domanda sull'ora e non a una domanda ordinaria.
- Checklist manuale, in locale e con Docker Compose: domanda ordinaria; «Che ore sono?»
  con richiesta, esecuzione e risultato visibili nei log; «Mi chiamo Luca» poi
  «Come mi chiamo?»; LM Studio fermo e poi riacceso; `esci` e Ctrl+C; da un secondo
  terminale `docker ps` e `docker logs -f assistente-demo`.
- Rischio noto: non è ancora provato che `google/gemma-4-e2b` richieda strumenti in modo
  affidabile. Se non lo fa, si annota come problema aperto e si discute (prompt di sistema,
  altro modello) prima di cambiare l'architettura.

## 10. Lasciato a chi costruisce

- Nomi e suddivisione esatta dei moduli, nel rispetto della separazione del §3.
- Testi esatti di prompt di sistema e messaggi a terminale (in italiano), salvo quelli
  fissati sopra.
- `max_tokens` e timeout della richiesta.
- Tecnica per simulare il modello nei test.
- Formato preciso delle righe di log.
- Struttura del README, purché contenga configurazione, avvio locale e Docker, test,
  prove reali e diagnosi con comandi verificati.
