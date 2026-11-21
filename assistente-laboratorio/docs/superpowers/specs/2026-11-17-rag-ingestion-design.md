# Lezione 7, esercizio 1 — Pipeline di ingestion e ricerca (specifica)

_2026-11-17 · Lezione 7 (PDF `LLM_Lez_7.pdf`, pag. 11–27) · branch `feat/rag-ingestion` da `dev` (`dc1d777`)_

## Intento

Costruire un indice vettoriale ripetibile del libro di Pellegrino Artusi «La scienza in cucina e
l'arte di mangiar bene» (1891) e recuperare i passaggi pertinenti a una domanda, con la loro fonte
(ricetta, capitolo, posizione del chunk). È la prima metà del RAG: **solo recupero, nessuna
generazione** (il modello generativo torna nella lezione 8, quando la ricerca diventerà uno
strumento dell'agente). Il risultato si misura: domande con fonte attesa, posizione e score della
fonte, tabella riproducibile. Questa valutazione è la «situazione di partenza» con cui si
confronteranno le modifiche A e B (esercizio 2, ciascuna con la propria specifica).

## Requisiti del PDF (alla lettera)

Dalla tabella di pag. 25 e dall'esercizio 1 di pag. 27:

| Componente | Requisito | Verifica |
|---|---|---|
| Corpus | Pulizia del testo; ogni ricetta è un documento con numero, titolo e capitolo | 790 ricette, numerazione senza buchi |
| Chunking | Strategia, dimensione e overlap configurabili | Test su una ricetta breve e su una lunga |
| Embedding | Modello di LM Studio letto dalla configurazione, lo stesso per documenti e domande | Modello registrato nella collezione; cambio bloccato |
| Qdrant | Un punto per chunk, ID stabili, payload con testo e metadati, indici sui campi filtrati | Due ingestion: stesso numero di punti |
| Ricerca | Top-k con massimo imposto dal codice; filtro per capitolo durante la ricerca | Risultati tutti del capitolo richiesto |
| Valutazione | Domande con fonte attesa; posizione e score della fonte | Tabella riproducibile |
| Test | Embedder finto e Qdrant in memoria | Test superati con i servizi spenti |

Altre regole del PDF: l'ingestion è uno **script separato** (pag. 11), non uno strumento
dell'agente; un solo modello di embedding, con la stessa configurazione per documenti e domande; la
dimensione dei vettori coincide con quella della collezione; il nome del modello sta nella
configurazione (pag. 10); Qdrant come servizio di Docker Compose con volume persistente, porta 6333
(pag. 16, 19); collezione con distanza coseno; script e applicazione in Docker Compose, LM Studio
sull'host raggiunto con `host.docker.internal` (pag. 19); `dati/` e `.env` fuori da Git (pag. 26,
29).

Evidenze (pag. 27): specifica e piano nella repository; test superati con i servizi spenti; stesso
numero di punti dopo le due ingestion; tabella della valutazione di partenza.

## Obiettivi, non obiettivi, anti-obiettivi

- **Obiettivi:** pacchetto `rag/` con ingestion, ricerca e valutazione; servizi `qdrant` e
  `ingestion` in `compose.yaml`; test senza servizi; ingestion reale eseguita due volte con lo
  stesso numero di punti; tabella di partenza in `docs/retrieval.md`; `CLAUDE.md`, README e
  `.env.example` aggiornati.
- **Non obiettivi (fuori da questo esercizio):** campo `contiene_dosi` e filtro (modifica A); titolo
  e capitolo nel testo indicizzato (modifica B); generazione di risposte; strumento
  `search_documents` e collegamento all'agente (lezione 8); estensioni del PDF (confronto di più
  strategie, modello multilingue, seconda collezione); download automatico del corpus; altri
  formati (PDF, HTML); soglia sullo score.
- **Anti-obiettivi:** duplicati dopo una seconda ingestion; codice o dati della lezione 6 rotti; il
  testo del libro in Git; modello di embedding scritto nel codice; ricerca che mescola modelli di
  embedding diversi nella stessa collezione.

## Decisioni prese con l'utente

- **Docker come lo schema del PDF (pag. 19), strada 2:** servizio `qdrant` (immagine ufficiale) e
  servizio `ingestion` (immagine propria, `rag/Dockerfile`), che si lancia con
  `docker compose run --rm ingestion`, come la `cli` della lezione 6. Gli stessi comandi funzionano
  anche dal PC con `.\.venv\Scripts\python.exe -m rag...`.
- **Corpus scaricato a mano dall'utente** una volta in `dati/artusi.txt` (comando PowerShell nel
  README); il programma non scarica nulla.
- **Domande di prova:** le sei del PDF più cinque proposte da Claude e approvate dall'utente (tabella
  più sotto).
- **Qdrant via API REST con `httpx`, senza `qdrant-client`** (strada A, dopo il blocco di Smart App
  Control su `numpy`), con un Qdrant finto in memoria per i test; nessuna dipendenza nuova.
- **Approvata la modifica di `test_quattro_servizi`** della lezione 6 (cinque servizi con
  `qdrant`).
- Le scelte di chunking, payload, ID e ripetizioni qui sotto sono state proposte da Claude e
  approvate dall'utente nel brainstorming.

## Approcci considerati

1. **Script solo sul PC, Qdrant in Docker.** Più semplice da provare; si allontana dallo schema di
   pag. 19, che mette lo script di ingestion dentro Docker Compose. Scartato.
2. **Come il PDF: Qdrant + servizio `ingestion` in Docker Compose, script utilizzabili anche dal
   PC.** Un'immagine in più e prove Docker in più, ma segue il PDF alla lettera. **Scelto
   dall'utente.**
3. Strategia di ripetizione «ricostruzione completa» (pag. 18, B): scartata, perché la modifica B
   chiede di ricalcolare tutto **senza ricreare la collezione**; si usa la strategia A (ID stabili e
   upsert).

## Il corpus (ricognizione del 2026-11-17 sul file vero)

File: Project Gutenberg n. 59047, `https://www.gutenberg.org/ebooks/59047.txt.utf-8` (in
manutenzione il 2026-11-17; mirror ufficiale funzionante:
`https://gutenberg.pglaf.org/5/9/0/4/59047/59047-0.txt`, stesso contenuto). UTF-8 con BOM in testa,
23.214 righe, righe lunghe al massimo 75 caratteri, corsivi scritti come `_testo_`.

Regole verificate sul file:

- Le ricette stanno tra la riga `RICETTE` e la riga `APPENDICE`. Prima ci sono prefazioni e note;
  dopo, l'appendice («Cucina per gli stomachi deboli», note di pranzi), che contiene elenchi di
  rimandi del tipo `227. Scaloppine ... p. 228.`: va esclusa.
- **Inizio di ricetta:** riga `N. Titolo` (numero 1–3 cifre, punto, spazio) **preceduta da una riga
  vuota**. Senza questa condizione si contano 791 ricette: c'è un rimando spezzato a capo
  («…_balsamella_ N.» e a capo «137. Mettete il composto…»).
- **Inizio di capitolo:** riga tutta in maiuscolo, senza rientro, **preceduta da due righe vuote**.
  Così si escludono i titoli interni in maiuscolo con una sola riga vuota prima («PASTA FROLLA»,
  «RICETTA A», «QUALITÀ E STAGIONE DEI PESCI», «RICETTA DI DETTA ZUPPA…»), quelli rientrati
  («UN AMMIRATORE») e i rimandi spezzati («N. 94.», «N. 3.»).
- Con queste regole: **790 ricette, da 1 a 790, senza buchi né doppioni**, in **23 capitoli con
  ricette** (`MINESTRE` è un titolo generale senza ricette proprie, seguito da `MINESTRE IN BRODO`).
  I capitoli: Brodi, gelatina e sughi · Minestre in brodo · Minestre asciutte e di magro · Principii
  · Salse · Uova · Paste e pastelle · Ripieni · Fritti · Lesso · Tramessi · Umidi · Rifreddi ·
  Erbaggi e legumi · Piatti di pesce · Arrosti · Pasticceria · Torte e dolci al cucchiaio · Siroppi
  · Conserve · Liquori · Gelati · Cose diverse.
- **Introduzioni di capitolo:** il testo tra il titolo del capitolo e la prima ricetta (es. «I
  siroppi di frutta acidule…») non appartiene a nessuna ricetta: non va attaccato all'ultima ricetta
  del capitolo precedente e non viene indicizzato.
- Gli **ingredienti** sono righe rientrate (`  Farina, grammi 230.`): restano righe separate, non si
  uniscono al paragrafo.

## Configurazione (nel `.env`, modello in `.env.example`)

Nuova sezione «RAG (lezione 7)» in `.env.example`; il pacchetto `rag/` legge `.env` e ambiente come
gli altri (`{**valori_del_file, **os.environ}`), con una sua `rag/configurazione.py` che non importa
`assistente` (come `backend/` e `frontend/`).

| Variabile | Obbligatoria | Predefinito | Uso |
|---|---|---|---|
| `LM_BASE_URL` | sì | — | già esistente: server di LM Studio (endpoint `/v1/embeddings`) |
| `EMBEDDING_MODELLO` | sì | — | id del modello di embedding in LM Studio, es. `text-embedding-nomic-embed-text-v1.5` |
| `QDRANT_URL` | no | `http://127.0.0.1:6333` | dove risponde Qdrant (nome del PDF, pag. 23) |
| `QDRANT_COLLEZIONE` | no | `ricette` | nome della collezione (pag. 19) |
| `CORPUS_FILE` | no | `dati/artusi.txt` | il file del libro |
| `CHUNK_STRATEGIA` | no | `paragrafi` | `paragrafi` oppure `finestra` |
| `CHUNK_DIMENSIONE` | no | `1200` | lunghezza massima di un chunk, in caratteri |
| `CHUNK_OVERLAP` | no | `200` | caratteri ripetuti tra chunk consecutivi; minore della dimensione |
| `LOG_LEVEL` | no | `INFO` | già esistente |

I valori predefiniti del chunking sono quelli dei risultati di pag. 22 («chunk per paragrafi, 1200
caratteri, overlap 200»), così i numeri si possono confrontare con quelli del PDF. Valori non validi
→ messaggio che nomina la variabile e uscita con codice 2, come negli altri pacchetti.

## La pipeline (pag. 11), modulo per modulo

Pacchetto `rag/` (nomi dei moduli: scelta del builder, purché ogni fase sia separata e
ispezionabile):

1. **Caricare** il file indicato da `CORPUS_FILE`, ricordandone la provenienza.
2. **Pulire:** togliere BOM e intestazione/licenza di Gutenberg (si tengono solo le righe tra
   `RICETTE` e `APPENDICE`); ricongiungere le righe spezzate di un paragrafo in una sola riga con
   spazi normalizzati; lasciare separate le righe rientrate degli ingredienti; togliere i
   trattini bassi dei corsivi (`_balsamella_` → `balsamella`); conservare titoli e capitoli come
   metadati; togliere caratteri di controllo.
3. **Dividere in documenti:** una ricetta = un documento con `numero`, `titolo` (testo dopo
   `N. `), `capitolo` (in forma leggibile: prima lettera maiuscola, il resto come nel libro in
   minuscolo, es. `Minestre asciutte e di magro`, `Fritti`) e testo pulito. Il testo del documento
   **comincia dopo la riga del titolo** (il titolo non è nel testo indicizzato: lo aggiungerà la
   modifica B).
4. **Suddividere in chunk** (strategia da configurazione):
   - `paragrafi` («combinazione frequente», pag. 15): una ricetta lunga al massimo `CHUNK_DIMENSIONE`
     resta un solo chunk; una più lunga si divide accumulando paragrafi interi finché si sta nella
     dimensione; un paragrafo da solo più lungo della dimensione si taglia a finestra. Dal secondo
     chunk in poi, il chunk comincia con la coda (al massimo `CHUNK_OVERLAP` caratteri, tagliata a
     inizio parola) del chunk precedente.
   - `finestra` (pag. 15): finestre di `CHUNK_DIMENSIONE` caratteri sul testo della ricetta, ognuna
     che ricomincia `CHUNK_OVERLAP` caratteri prima della fine della precedente; i tagli cadono a
     inizio parola.
   - In entrambe nessun chunk vuoto, nessun chunk più lungo di `CHUNK_DIMENSIONE` (più al massimo
     una parola, per non spezzarla) e chunk sempre all'interno di una sola ricetta.
5. **Arricchire:** ogni chunk riceve il payload qui sotto.
6. **Embedding:** chiamata `POST {LM_BASE_URL}/embeddings` con il modello `EMBEDDING_MODELLO`, a
   lotti (dimensione del lotto: scelta del builder, costante nel codice), con `httpx` (già nel
   progetto) e timeout. Lo stesso modulo calcola l'embedding della domanda nella ricerca. Il testo
   va al modello così com'è, senza prefissi (vedi «Lasciato al builder»).
7. **Salvare:** upsert dei punti nella collezione Qdrant (vettore + payload).

### Payload (pag. 13 e 16)

| Campo | Esempio | A che cosa serve |
|---|---|---|
| `documento_id` | `ricetta-089` | identificare la ricetta (numero a tre cifre) |
| `numero` | `89` | citare la ricetta; confrontare con la fonte attesa |
| `titolo` | `Gnocchi di patate` | mostrare la fonte in forma leggibile |
| `capitolo` | `Minestre asciutte e di magro` | filtro durante la ricerca |
| `posizione` | `0` | ordine del chunk nella ricetta (0, 1, 2…): ritrovare i chunk adiacenti |
| `testo` | testo del chunk | ciò che la ricerca restituisce |
| `fonte` | `Artusi, La scienza in cucina e l'arte di mangiar bene (1891), Project Gutenberg n. 59047` | citare la fonte |

Indice sul payload: `capitolo` (keyword), l'unico campo filtrato in questo esercizio.

### Collezione, ID e ripetizioni (pag. 16, 18)

- Collezione `QDRANT_COLLEZIONE`, distanza coseno, dimensione = lunghezza del primo vettore
  calcolato. Nei **metadati della collezione** si registrano il modello di embedding e la
  dimensione.
- Se la collezione esiste già: se modello o dimensione registrati sono diversi da quelli attuali,
  l'ingestion **si ferma** con un messaggio che indica il modello registrato e quello configurato e
  suggerisce un'altra `QDRANT_COLLEZIONE` («cambio bloccato»), senza toccare niente. La ricerca fa
  lo stesso controllo prima di interrogare.
- **ID stabile:** UUID versione 5 ricavato da `documento_id` e `posizione` (lo stesso chunk ha
  sempre lo stesso ID) → upsert, quindi una seconda ingestion sostituisce i punti invece di
  aggiungerli.
- **Pulizia dei punti avanzati** (avvertenza di pag. 18): dopo l'upsert si eliminano i punti con
  `posizione` oltre l'ultimo chunk di ciascuna ricetta e i punti di ricette che non esistono più.
  Così anche cambiando dimensione o overlap la collezione resta coerente.
- L'ingestion stampa (e scrive nei log) ricette lette, chunk prodotti, punti nella collezione prima
  e dopo: è il conteggio dell'evidenza «stesso numero di punti dopo le due ingestion».
- Controlli prima di salvare: 790 ricette numerate da 1 a 790 senza buchi; se no, l'ingestion si
  ferma con l'elenco dei numeri mancanti o doppi (verifica del corpus di pag. 25).

## Ricerca (pag. 17, 20)

`python -m rag.ricerca "domanda" [--capitolo NOME] [--k N]`:

- embedding della domanda con lo stesso modello; query a Qdrant con i `k` punti più vicini;
- `--k` predefinito **5** (la valutazione del PDF usa top-k = 5); **massimo imposto dal codice: 20**
  (costante); valore fuori da 1–20 → errore chiaro, nessuna chiamata;
- `--capitolo`: filtro **durante** la ricerca (condizione `must` / `match` sul campo `capitolo`,
  come pag. 17); il valore va scritto come nel payload (`Fritti`); se nessun punto ha quel capitolo,
  messaggio che elenca i capitoli disponibili (errore tipico di pag. 23);
- per ogni risultato: posizione nella classifica, score, numero e titolo della ricetta, capitolo,
  posizione del chunk e testo (criterio di completamento, pag. 29);
- nessuna soglia sullo score (pag. 9 e 22).

## Valutazione (pag. 21–22, 27)

- File versionato delle domande (formato e posizione: scelta del builder, per esempio JSON nel
  pacchetto) con, per ciascuna, il testo e i numeri delle ricette attese (lista vuota = il libro non
  contiene la risposta).
- `python -m rag.valutazione` esegue tutte le domande con `k = 5` e stampa una **tabella Markdown**:
  domanda, fonte attesa, posizione del primo chunk di una ricetta attesa (o «assente»), score di
  quel chunk, score migliore; per le domande senza risposta, lo score migliore. In fondo: «fonte
  attesa trovata in X casi su Y». Stessi indice e domande → stessa tabella (ricerca deterministica,
  pag. 6).
- Domande:

| # | Domanda | Ricette attese | Origine |
|---|---|---|---|
| 1 | Quanta farina serve per 400 grammi di patate negli gnocchi? | 89 | PDF pag. 21–22 |
| 2 | Quanti cappelletti bastano a un mangiatore moderato? | 7 | PDF pag. 22 |
| 3 | Che vino si usa per il pollo alla cacciatora? | 208 | PDF pag. 21–22 |
| 4 | Perché gli gnocchi possono sciogliersi nell'acqua? | 89 | PDF pag. 22 |
| 5 | Come si chiama il cacciucco sulle coste dell'Adriatico? | 455, 456 | PDF pag. 21 |
| 6 | Qual è la ricetta del tiramisù? | nessuna | PDF pag. 21–22 |
| 7 | Con quale spezia si colora il riso tipico della Lombardia? | 78, 79, 80 | proposta, approvata |
| 8 | Come preparare in estate una scorta di passata rossa da usare tutto l'anno? | 732 | proposta, approvata |
| 9 | Da quale paese arriva la bevanda scura che si beve per svegliarsi? | 776 | proposta, approvata |
| 10 | Quale vino dolce si aggiunge alla crema spumosa fatta con i tuorli? | 722 | proposta, approvata |
| 11 | Qual è la ricetta della carbonara? | nessuna | proposta, approvata |

  Nove con fonte attesa e due senza risposta, come la struttura di pag. 22. Numeri verificati sul
  file (7 = «Cappelletti all'uso di Romagna», 89 = «Gnocchi di patate», 208 = «Pollo alla
  cacciatora», 455–456 = «Cacciucco I/II», 78–80 = «Risotto alla milanese I–III», 722 =
  «Zabaione», 732 = «Conserva di pomodoro senza sale», 776 = «Caffè»).
- `docs/retrieval.md` (consegna, pag. 29), in questo esercizio: conteggi delle due ingestion;
  configurazione usata (modello, strategia, dimensione, overlap, k); tabella di partenza; due query
  commentate (una con filtro per capitolo). Le sezioni «dopo A» e «dopo B» si aggiungeranno nelle
  modifiche.

## Docker Compose (pag. 16, 19)

- **`qdrant`**: immagine ufficiale `qdrant/qdrant:v1.20.2`; porta `127.0.0.1:6333:6333` (API e
  dashboard web `http://localhost:6333/dashboard`, solo da questo PC come il database); volume
  `dati-qdrant:/qdrant/storage` (la collezione sopravvive al riavvio, pag. 16 e 23). Senza profilo:
  parte con `docker compose up -d` insieme ai servizi della lezione 6.
- **`ingestion`**: immagine da `rag/Dockerfile` (stessa struttura degli altri Dockerfile: Python
  3.13 slim, `requirements.txt`, solo il pacchetto `rag`), `command` `python -m rag.ingestion`,
  profilo `rag` (`docker compose up` non lo avvia; si usa `docker compose run --rm ingestion`, e con
  la stessa immagine `docker compose run --rm ingestion python -m rag.ricerca "..."` e
  `python -m rag.valutazione`); `env_file: .env`; in `environment` `QDRANT_URL:
  http://qdrant:6333`, `LM_BASE_URL: http://host.docker.internal:1234/v1`, `CORPUS_FILE:
  dati/artusi.txt`; `extra_hosts` `host.docker.internal:host-gateway`; volume `./dati:/app/dati:ro`
  (il libro resta sul PC, non nell'immagine); `depends_on: qdrant`.
- Commento in testa a `compose.yaml` aggiornato (lezione 7: `qdrant` e `ingestion`).
- `.dockerignore`: aggiungere `dati/`. `.gitignore` del progetto: aggiungere `dati/`.
- **Modifica a un test della lezione 6 (approvata dall'utente il 2026-11-17):**
  `tests/test_docker_compose.py::test_quattro_servizi` verifica che i servizi siano esattamente
  quattro; con `qdrant` senza profilo diventano cinque. Il test diventa «i quattro servizi della
  lezione 6 più `qdrant`»; i nuovi test di `compose.yaml` per `qdrant` e `ingestion` stanno in un
  file nuovo. Nessun altro file della lezione 6 cambia.

## Dipendenze e collegamento a Qdrant (decisione dell'utente, strada A)

- **Nessuna dipendenza nuova.** Il client ufficiale `qdrant-client==1.20.0` è stato provato
  (2026-11-17, venv di prova fuori dal progetto): richiede `numpy`, e **Smart App Control di
  Windows ne blocca una DLL** (`ImportError: DLL load failed while importing _umath_linalg: Un
  criterio di controllo dell'applicazione ha bloccato il file`), lo stesso motivo per cui nello step
  7 si è scelto `pg8000`. Strade scartate: client solo in Docker (test e script inutilizzabili dal
  PC, ogni giro di test in un container); disattivare Smart App Control (scelta di sicurezza
  dell'utente, non reversibile).
- **Scelta dell'utente:** il pacchetto `rag/` parla con Qdrant attraverso la sua **API REST** con
  `httpx` (già nel progetto), in un modulo dedicato (es. `rag/qdrant.py`) che espone solo le
  operazioni usate: leggere/creare la collezione (distanza `Cosine`, `metadata`), creare l'indice
  sul payload (`PUT /collections/{c}/index`), upsert dei punti, ricerca (`POST
  /collections/{c}/points/query` con `filter`, `limit`, `with_payload`), cancellazione con filtro,
  conteggio esatto dei punti, valori distinti di `capitolo` (facet). Errori di rete → messaggio
  «Qdrant non raggiungibile: controllare `docker compose ps` e `QDRANT_URL`» (pag. 23).
- **Qdrant in memoria per i test (pag. 25):** un Qdrant **finto** scritto nei test, montato su
  `httpx.MockTransport`, che risponde agli stessi percorsi REST con lo stato in memoria
  (collezioni con metadati, punti, similarità del coseno in Python puro, filtro `must`/`match` sul
  payload, cancellazione, conteggio, facet) e registra le richieste ricevute (per verificare che
  l'indice sul capitolo e il filtro durante la ricerca vengano davvero inviati). Non è il «Qdrant in
  memoria» della libreria ufficiale: lo si dice nel README e in `docs/retrieval.md`. Il formato delle
  richieste e delle risposte REST si verifica sul Qdrant vero nelle prove reali.

## Test (pag. 24–25: «senza bisogno di LM Studio né del server Qdrant»)

Tutti con **embedder finto** (vettori deterministici ricavati dal testo, dimensione piccola) e
**Qdrant finto in memoria** (vedi «Dipendenze e collegamento a Qdrant»); nessuna rete. Il corpus dei test è un piccolo estratto costruito nei test,
con le stesse particolarità del file vero (BOM, intestazione Gutenberg, `RICETTE`/`APPENDICE`,
introduzione di capitolo, titolo finto in maiuscolo, rimando spezzato `N.` + `137. ...`, righe di
ingredienti rientrate, corsivi).

- **Configurazione:** obbligatorie mancanti, valori non validi (strategia sconosciuta, dimensione
  non positiva, overlap ≥ dimensione), predefiniti.
- **Corpus:** numeri, titoli e capitoli corretti; introduzioni escluse; rimando spezzato non preso
  per una ricetta; titoli finti non presi per capitoli; buchi e doppioni segnalati; con il file vero
  presente in `dati/artusi.txt`: 790 ricette senza buchi e 23 capitoli (test saltato se il file
  manca, perché `dati/` non è in Git).
- **Chunking** (verifica di pag. 25): una ricetta breve → un chunk; una lunga → più chunk, ciascuno
  entro la dimensione, con overlap tra consecutivi, posizioni 0, 1, 2…; stesse prove con la
  strategia `finestra`.
- **Embedding:** chiamata all'endpoint con `httpx.MockTransport` (corpo, lotti, ordine dei vettori,
  errori di LM Studio tradotti in messaggi chiari).
- **Client REST di Qdrant:** corpo e percorso di ogni richiesta, risposte di errore e Qdrant
  irraggiungibile tradotti in messaggi chiari.
- **Ingestion sul Qdrant finto in memoria:** un punto per chunk; payload completo; ID stabili;
  **due ingestion → stesso numero di punti**; punti avanzati eliminati quando una ricetta si
  accorcia; modello registrato nei metadati della collezione e **cambio bloccato** (modello o
  dimensione diversi; collezione esistente senza metadati trattata come non compatibile); richiesta
  di indice sul capitolo inviata alla creazione.
- **Ricerca:** risultati ordinati per score; `k` predefinito 5, massimo 20, fuori intervallo →
  errore; con `--capitolo` **tutti i risultati del capitolo richiesto** e la condizione inviata
  durante la ricerca; capitolo inesistente → messaggio con i capitoli disponibili.
- **Valutazione:** tabella con posizione/«assente» e score, riepilogo X su Y, domande senza
  risposta.
- **Indipendenza:** nessun file di `rag/` importa `assistente`, `backend` o `frontend`.
- **Docker** (file nuovo, come `tests/test_docker_compose.py`, con `docker compose config`, saltato
  senza Docker): `qdrant` con immagine ufficiale, porta solo `127.0.0.1:6333`, volume
  `dati-qdrant`; `ingestion` con profilo `rag`, `rag/Dockerfile`, `QDRANT_URL` e `LM_BASE_URL`
  della rete di Docker, `./dati` montato in sola lettura. `rag/Dockerfile` copia solo
  `requirements.txt` e `rag`. `.gitignore` e `.dockerignore` escludono `dati/`.

## Prove reali (le esegue l'utente dove serve Docker; istruzioni in un unico messaggio)

1. LM Studio con il modello di embedding caricato; `dati/artusi.txt` scaricato.
2. `docker compose up -d qdrant`; dashboard su `http://localhost:6333/dashboard`.
3. `docker compose run --rm ingestion` **due volte**: stesse ricette (790), stessi chunk, **stesso
   numero di punti** prima/dopo (evidenza).
4. `docker compose run --rm ingestion python -m rag.ricerca "Come si frigge il pollo?" --capitolo
   Fritti --k 3`: tutti i risultati del capitolo Fritti.
5. `docker compose run --rm ingestion python -m rag.valutazione` → tabella di partenza in
   `docs/retrieval.md`.
6. `docker compose restart qdrant` → la collezione c'è ancora (volume).
7. Prova del cambio bloccato con un altro modello di embedding nel `.env` (es. `text-embedding-bge-m3`,
   già in LM Studio) → l'ingestion si ferma senza toccare la collezione; poi si rimette il modello.

Claude esegue da solo le prove reali mirate dal PC (ingestion e ricerca con
`.\.venv\Scripts\python.exe`, quando Qdrant è acceso) e i test.

## Documentazione

- `CLAUDE.md`: nuova sezione «Lezione 7 — RAG: ingestion e ricerca» (obiettivo, tre parti:
  esercizio 1, modifiche A e B), regole stabili chieste dal PDF (pag. 24: ingestion come script
  separato, modello di embedding dalla configurazione, Qdrant con Docker Compose, dati scaricati
  fuori da Git); in «Confini» il RAG passa da «fuori perimetro» a «solo quanto chiede il PDF della
  lezione 7»; Project Gutenberg come fonte del corpus (download manuale); il modello generativo
  resta `google/gemma-4-e2b`.
- README: sezione «RAG: ingestion e ricerca» (download del corpus con il mirror alternativo, avvio
  di Qdrant, ingestion, ricerca, valutazione, dashboard, diagnosi dalla tabella degli errori di pag.
  23), test nuovi, esiti delle prove reali.
- `.env.example`: sezione «RAG (lezione 7)».
- `docs/retrieval.md`: come sopra.

## Git

Branch `feat/rag-ingestion` da `dev`; commit Conventional Commits in italiano (scope `rag`,
`docker`, `docs`), staging per percorsi espliciti, messaggi senza BOM; mai `dati/`, `.env`, i 4 file
della lezione 3 nella radice, `HANDOFF*`, `PROMPT-ripresa-*`. Merge in `dev` solo con conferma,
nessun push senza richiesta.

## Scelte del builder già fissate (dalla verifica della specifica)

- Righe degli ingredienti: un blocco di righe rientrate consecutive è **un paragrafo** per il
  chunking (non si spezza un elenco di ingredienti tra due chunk, salvo che da solo superi la
  dimensione).
- Collezione esistente senza metadati del modello: trattata come «cambio bloccato» (non si sa con
  quale modello è stata creata).
- Qdrant non raggiungibile all'avvio dell'ingestion: un solo messaggio chiaro e uscita con codice
  3, come il back-end con il database; nessun nuovo tentativo automatico.

## Lasciato al builder

- Nomi dei moduli di `rag/` e ordine dei task (TDD).
- Dimensione dei lotti di embedding e timeout.
- Formato e posizione del file delle domande.
- Funzione dell'embedder finto (purché deterministica).
- Healthcheck di `qdrant` (se serve a `depends_on`) o un messaggio chiaro «Qdrant non
  raggiungibile» dall'ingestion.
- Prefissi di task del modello nomic (`search_document:` / `search_query:`): **non** si usano, perché
  il PDF chiede la stessa configurazione per documenti e domande e i suoi risultati di pag. 22 sono
  il riferimento; la scelta va scritta in `docs/retrieval.md`.
