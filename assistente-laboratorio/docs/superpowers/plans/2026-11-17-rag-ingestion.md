# Lezione 7, esercizio 1 — Ingestion e ricerca (RAG) — Piano di implementazione

> **Per chi esegue:** SOTTO-SKILL OBBLIGATORIA: usare superpowers:executing-plans (esecuzione diretta, «Modo di lavoro veloce» di `CLAUDE.local.md`) per eseguire il piano task per task. I passi usano le caselle (`- [ ]`) per il tracciamento.

**Obiettivo:** un indice vettoriale ripetibile del libro di Artusi in Qdrant (`python -m rag.ingestion`), una ricerca con fonte e filtro per capitolo (`python -m rag.ricerca`) e una valutazione di partenza riproducibile (`python -m rag.valutazione`).

**Architettura:** pacchetto `rag/` con una fase della pipeline per modulo (configurazione → corpus → chunking → embedding → Qdrant → ingestion / ricerca / valutazione); Qdrant raggiunto via API REST con `httpx`; LM Studio via `POST {LM_BASE_URL}/embeddings`. In Docker Compose il servizio `qdrant` (immagine ufficiale, volume) e il servizio `ingestion` (profilo `rag`). Test con embedder finto e Qdrant finto in memoria su `httpx.MockTransport`.

**Tecnologie:** Python 3.13, `httpx==0.28.1`, `python-dotenv` (già nel progetto), Qdrant `v1.20.2` (API REST), Docker Compose. **Nessuna dipendenza nuova.**

**Specifica:** `docs/superpowers/specs/2026-11-17-rag-ingestion-design.md` (commit `2c2cc04`, approvata). Chi esegue legge entrambi i documenti.

Percorsi relativi a `assistente-laboratorio/`; comandi PowerShell in quella cartella con `.\.venv\Scripts\python.exe -m pytest ...`. Branch `feat/rag-ingestion` (già creato da `dev` `dc1d777`). Registro: `..\.superpowers\sdd\2026-11-17-rag-ingestion\progress.md` (creato al Task 1, fuori dalla repository).

## Vincoli globali

- Modo di lavoro veloce. **Nessun file di `assistente/`, `backend/`, `frontend/` cambia.** Unico file della lezione 6 toccato: `tests/test_docker_compose.py::test_quattro_servizi` (modifica approvata). Altri file esistenti toccati: `compose.yaml`, `.gitignore`, `.dockerignore`, `.env.example`, `README.md`, `CLAUDE.md` (solo se cambia una convenzione).
- `rag/` non importa `assistente`, `backend`, `frontend`. Configurazione propria in `rag/configurazione.py` (stesso schema di `backend/configurazione.py`: `leggi_ambiente(cartella)` = `{**valori_del_file, **os.environ}`).
- Variabili (dalla specifica): `LM_BASE_URL` (obbligatoria), `EMBEDDING_MODELLO` (obbligatoria), `QDRANT_URL` = `http://127.0.0.1:6333`, `QDRANT_COLLEZIONE` = `ricette`, `CORPUS_FILE` = `dati/artusi.txt`, `CHUNK_STRATEGIA` = `paragrafi` (oppure `finestra`), `CHUNK_DIMENSIONE` = `1200`, `CHUNK_OVERLAP` = `200` (0 ≤ overlap < dimensione), `LOG_LEVEL` = `INFO`.
- Codici di uscita di tutti e tre i comandi: **0** ok; **2** configurazione non valida (messaggio che nomina la variabile); **3** servizio non raggiungibile (Qdrant: «Qdrant non raggiungibile: controllare `docker compose ps` e `QDRANT_URL`»; LM Studio: «LM Studio non raggiungibile: controllare `LM_BASE_URL` e il modello di embedding caricato»); **4** errore sui dati (corpus non valido, cambio bloccato, collezione mancante, capitolo inesistente, `--k` fuori intervallo). Messaggi di errore su stderr, nessun traceback.
- Costanti nel codice: `K_PREDEFINITO = 5`, `K_MASSIMO = 20`, `RICETTE_ATTESE = 790`, lotto di embedding `32` testi, timeout `httpx` `60` s (embedding) e `10` s (Qdrant), lotto di upsert `256` punti, `FONTE = "Artusi, La scienza in cucina e l'arte di mangiar bene (1891), Project Gutenberg n. 59047"`.
- Collezione: distanza `Cosine`; `metadata` = `{"embedding_modello": <EMBEDDING_MODELLO>, "embedding_dimensione": <int>}`; indice keyword su `capitolo`.
- Niente prefissi `search_document:` / `search_query:`: il testo va al modello così com'è (scelta da scrivere in `docs/retrieval.md`).
- Commenti didattici in italiano semplice in testa a ogni file, nello stile di `backend/` («COSA FA QUESTO FILE»).
- **Claude non avvia container né costruisce immagini** (`up`, `build`, `run`, `down`): lo fa l'utente con le istruzioni del Task 10. `docker compose config` nei test è ammesso. Il corpus `dati/artusi.txt` lo scarica l'utente; **`dati/` mai nello staging**.
- Git: staging per percorsi espliciti; mai i 4 file della Lezione 3, `HANDOFF*`, `HANDOFF_PROMPT.txt`, `PROMPT-ripresa-*`, `dati/`, `.env`; Conventional Commits in italiano (scope `rag`, `docker`, `docs`) con `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; messaggio senza BOM in un file e `git commit -F`; nessun push, merge solo con conferma. Il `.env` dell'utente non si legge (al massimo i nomi delle variabili) né si tocca.

## Punti da sorvegliare (Review Focus)

1. **File del libro con fine riga Windows (`\r\n`) o senza BOM** (riscaricato con un altro programma): stesse 790 ricette → `test_fine_riga_windows_e_senza_bom` (Task 2).
2. **`EMBEDDING_MODELLO` scritto con un modello non caricato o un id sbagliato in LM Studio** (risposta 400/404 con `{"error": ...}`): messaggio che cita il modello configurato, codice 4, collezione non toccata → `test_errore_lm_studio_cita_il_modello` (Task 4) e `test_ingestion_lm_studio_in_errore_non_tocca_la_collezione` (Task 6).
3. **Ingestion interrotta a metà** (LM Studio che cade durante il calcolo): gli embedding si calcolano **tutti prima** di creare la collezione o scrivere punti, quindi nessuna collezione mezza vuota con metadati validi → stesso test del punto 2 (Task 6).
4. **Capitolo scritto in minuscolo o senza accenti** (`--capitolo fritti`): nessun risultato silenzioso, ma messaggio con i capitoli disponibili, codice 4 → `test_capitolo_inesistente_elenca_i_disponibili` con `"fritti"` (Task 7).
5. **Domanda vuota o fatta di soli spazi**: errore chiaro senza chiamare LM Studio né Qdrant, codice 4 → `test_domanda_vuota` (Task 7).

---

### Task 1: Configurazione del pacchetto `rag/`

**Files:**
- Create: `rag/__init__.py`, `rag/configurazione.py`, `tests/test_rag_configurazione.py`
- Modify: `.gitignore` e `.dockerignore` (riga `dati/` con commento), `.env.example` (sezione «RAG (lezione 7)» con tutte le variabili sopra, `EMBEDDING_MODELLO=text-embedding-nomic-embed-text-v1.5`)
- Create (fuori repo): registro `..\.superpowers\sdd\2026-11-17-rag-ingestion\progress.md`

**Interfaces:**
- Produces:
  - `ErroreConfigurazioneRag(Exception)`
  - `@dataclass(frozen=True) ConfigurazioneRag: lm_base_url: str; embedding_modello: str; qdrant_url: str; collezione: str; corpus_file: Path; strategia: str; dimensione: int; overlap: int; log_level: str`
  - `leggi_ambiente(cartella: Path) -> dict[str, str]`
  - `carica_configurazione(ambiente: Mapping[str, str], cartella: Path) -> ConfigurazioneRag` (`corpus_file` relativo risolto rispetto a `cartella`; `lm_base_url` e `qdrant_url` senza `/` finale)
  - `configura_log(livello: str) -> None` (logger `rag`)

- [ ] **Step 1: Test che falliscono** (`tests/test_rag_configurazione.py`):
  - `test_predefiniti`: con solo `LM_BASE_URL` e `EMBEDDING_MODELLO` → `qdrant_url == "http://127.0.0.1:6333"`, `collezione == "ricette"`, `corpus_file == cartella / "dati" / "artusi.txt"`, `strategia == "paragrafi"`, `dimensione == 1200`, `overlap == 200`, `log_level == "INFO"`.
  - `test_obbligatorie_mancanti`: senza le due → `ErroreConfigurazioneRag` il cui messaggio contiene `LM_BASE_URL` e `EMBEDDING_MODELLO`.
  - `test_valori_non_validi` parametrizzato: `CHUNK_STRATEGIA=frasi`, `CHUNK_DIMENSIONE=0`, `CHUNK_DIMENSIONE=abc`, `CHUNK_OVERLAP=-1`, `CHUNK_OVERLAP=1200` (uguale alla dimensione), `QDRANT_URL=localhost:6333`, `LOG_LEVEL=TROPPO` → errore che nomina la variabile.
  - `test_barra_finale_tolta`: `LM_BASE_URL=http://x:1234/v1/` → `"http://x:1234/v1"`.
  - `test_ambiente_prevale_sul_file` (con `.env` in `tmp_path` e `monkeypatch.setenv`).
  - `test_dati_ignorati`: `.gitignore` e `.dockerignore` contengono la riga `dati/`; `.env.example` contiene `EMBEDDING_MODELLO=` e `QDRANT_URL=`.
- [ ] **Step 2:** `.\.venv\Scripts\python.exe -m pytest tests/test_rag_configurazione.py -q` → FAIL (`rag` non esiste).
- [ ] **Step 3:** implementare `rag/configurazione.py` (schema di `backend/configurazione.py`) e le righe di `.gitignore`, `.dockerignore`, `.env.example`; creare il registro.
- [ ] **Step 4:** stesso comando → PASS.
- [ ] **Step 5: Commit** `feat(rag): configurazione del pacchetto rag (lezione 7)`.

### Task 2: Corpus — pulizia e divisione in ricette

**Files:**
- Create: `rag/corpus.py`, `tests/finti_rag.py` (per ora solo `CORPUS_PROVA: str`), `tests/test_rag_corpus.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) Ricetta: numero: int; titolo: str; capitolo: str; testo: str` con proprietà `documento_id -> str` (`f"ricetta-{numero:03d}"`)
  - `ErroreCorpus(Exception)`
  - `leggi_file(percorso: Path) -> str` (UTF-8, BOM tolto; file mancante → `ErroreCorpus` con il percorso e il suggerimento di scaricarlo come da README)
  - `estrai_ricette(testo: str) -> list[Ricetta]`
  - `controlla_numerazione(ricette: list[Ricetta], attese: int = 790) -> None` (`ErroreCorpus` con «mancanti: …» e/o «doppie: …»)
  - `paragrafi(testo: str) -> list[str]` (divide `Ricetta.testo` sui `"\n\n"`)

Regole (dalla specifica, verificate sul file vero; nel file di ricognizione `RICETTE` è alla riga 940 e `APPENDICE` alla 20074, mentre più avanti nell'indice compaiono **rientrati**: si cercano solo le righe **esattamente** `RICETTE` e `APPENDICE`, senza rientro, la prima `APPENDICE` dopo `RICETTE`):
- righe ottenute con `splitlines()` (così `\r\n` è gestito), caratteri di controllo tolti, BOM tolto;
- **capitolo:** riga non vuota, senza rientro, con `riga == riga.upper()` e almeno una lettera, preceduta da **due** righe vuote; forma leggibile `riga.capitalize()` (es. `MINESTRE ASCIUTTE E DI MAGRO` → `Minestre asciutte e di magro`);
- **ricetta:** riga che corrisponde a `^(\d{1,3})\. (.+)$`, senza rientro, preceduta da **una riga vuota**; il titolo è il gruppo 2 (corsivi tolti);
- testo della ricetta: le righe dopo il titolo fino alla ricetta o al capitolo successivo; righe senza rientro consecutive unite con uno spazio (spazi normalizzati) in un paragrafo; righe rientrate consecutive = un paragrafo con le righe separate da `"\n"` e il rientro tolto; paragrafi separati da `"\n\n"`; `_testo_` → `testo`;
- il testo tra un titolo di capitolo e la sua prima ricetta (introduzione) non va in nessuna ricetta; un capitolo senza ricette (`MINESTRE`) non compare.

- [ ] **Step 1: Test che falliscono.** In `tests/finti_rag.py` scrivere `CORPUS_PROVA`: BOM, intestazione Gutenberg, riga `RICETTE`, capitolo `BRODI, GELATINA E SUGHI` (due righe vuote prima) con introduzione e ricette 1–2, titolo generale `MINESTRE` senza ricette seguito da `MINESTRE IN BRODO` con ricetta 3 lunga (> 1200 caratteri, più paragrafi e un blocco di ingredienti rientrati, un corsivo `_balsamella_`, un rimando spezzato «…vedi il N.» a capo «137. Mettete…» **senza** riga vuota prima, un titolo finto `PASTA FROLLA` con una sola riga vuota prima, un `  UN AMMIRATORE` rientrato), capitolo `FRITTI` con introduzione e ricette 4–5, poi `APPENDICE` con `227. Scaloppine ... p. 228.`, poi `  RICETTE` rientrato. Test in `tests/test_rag_corpus.py`:
  - `test_numeri_titoli_capitoli`: numeri `[1, 2, 3, 4, 5]`; capitoli `["Brodi, gelatina e sughi", "Brodi, gelatina e sughi", "Minestre in brodo", "Fritti", "Fritti"]`; titoli attesi.
  - `test_introduzione_esclusa`: il testo dell'introduzione di `FRITTI` non è in nessuna `Ricetta.testo` (in particolare non nella 3).
  - `test_rimando_spezzato_e_titoli_finti`: nessuna ricetta 137; `PASTA FROLLA` e `UN AMMIRATORE` restano nel testo della 3 e non sono capitoli.
  - `test_appendice_esclusa`: nessuna ricetta 227.
  - `test_testo_pulito`: nessun `_` nel testo; il titolo non è nel testo; le righe di ingredienti sono un paragrafo con le righe separate da `"\n"` e senza rientro; le righe di un paragrafo normale sono unite in una sola riga.
  - `test_fine_riga_windows_e_senza_bom` (Review Focus 1): `CORPUS_PROVA` senza BOM e con `\r\n` → stesse ricette.
  - `test_numerazione`: `controlla_numerazione` con attese 5 passa; con una ricetta tolta → messaggio con `mancanti: 3`; con un doppione → `doppie: 4`.
  - `test_file_mancante`: `leggi_file(tmp_path / "x.txt")` → `ErroreCorpus` con il percorso.
  - `test_libro_vero` (saltato se `dati/artusi.txt` manca): 790 ricette, `controlla_numerazione` passa, 23 capitoli distinti, il primo `Brodi, gelatina e sughi` e l'ultimo `Cose diverse`; ricetta 89 titolo `Gnocchi di patate`, capitolo `Minestre asciutte e di magro`.
- [ ] **Step 2:** `.\.venv\Scripts\python.exe -m pytest tests/test_rag_corpus.py -q` → FAIL.
- [ ] **Step 3:** implementare `rag/corpus.py` con le regole sopra.
- [ ] **Step 4:** stesso comando → PASS (il test del libro vero risulta saltato finché l'utente non scarica il file; si riesegue al Task 10).
- [ ] **Step 5: Commit** `feat(rag): pulizia del corpus e divisione in ricette`.

### Task 3: Chunking

**Files:**
- Create: `rag/chunking.py`, `tests/test_rag_chunking.py`

**Interfaces:**
- Consumes: `paragrafi(testo)` (Task 2).
- Produces: `dividi(testo: str, strategia: str, dimensione: int, overlap: int) -> list[str]` (indice nella lista = `posizione` del chunk).

Algoritmo `paragrafi`: se `len(testo) <= dimensione` → `[testo]`. Altrimenti si accumulano paragrafi interi (uniti da `"\n\n"`) finché il chunk resta entro la dimensione; un paragrafo da solo più lungo della dimensione si taglia con la stessa finestra di `finestra`. Ogni chunk dal secondo in poi comincia con la coda del chunk precedente: al massimo `overlap` caratteri, tagliata a inizio parola; la coda conta nella dimensione del nuovo chunk. Algoritmo `finestra`: finestre di `dimensione` caratteri; la successiva ricomincia `overlap` caratteri prima della fine della precedente; ogni taglio si sposta in avanti alla fine della parola in corso (chunk al massimo `dimensione` + una parola); deve sempre avanzare (nessun ciclo infinito con `overlap` vicino alla dimensione).

- [ ] **Step 1: Test che falliscono** (`tests/test_rag_chunking.py`, per **entrambe** le strategie, parametrizzati):
  - `test_ricetta_breve_un_chunk`: testo di 300 caratteri → un chunk uguale al testo.
  - `test_ricetta_lunga_piu_chunk`: ricetta 3 di `CORPUS_PROVA` con `dimensione=400, overlap=80` → almeno 3 chunk, nessuno vuoto, ognuno lungo al massimo `400 + len(parola più lunga) + 1`.
  - `test_overlap_tra_consecutivi`: per ogni coppia consecutiva, il chunk successivo comincia con un pezzo (≥ 1 parola, ≤ 80 caratteri + una parola) che è la fine del precedente.
  - `test_overlap_zero`: nessuna ripetizione; la concatenazione delle parole ricostruisce tutte le parole del testo.
  - `test_nessuna_parola_spezzata`: ogni parola di ogni chunk è una parola del testo.
  - Solo `paragrafi`: `test_ingredienti_non_spezzati` (il blocco di ingredienti rientrati sta intero in un solo chunk); `test_paragrafo_troppo_lungo` (un paragrafo di 1000 caratteri con `dimensione=300` → spezzato a finestra, tutti entro il limite).
  - `test_strategia_sconosciuta` → `ValueError`.
- [ ] **Step 2:** `.\.venv\Scripts\python.exe -m pytest tests/test_rag_chunking.py -q` → FAIL.
- [ ] **Step 3:** implementare `rag/chunking.py`.
- [ ] **Step 4:** stesso comando → PASS.
- [ ] **Step 5: Commit** `feat(rag): chunking per paragrafi e a finestra con overlap`.

### Task 4: Embedding con LM Studio

**Files:**
- Create: `rag/embedding.py`, `tests/test_rag_embedding.py`
- Modify: `tests/finti_rag.py` (aggiungere `EmbedderFinto`)

**Interfaces:**
- Produces:
  - `class ErroreEmbedding(Exception)`; `class LMStudioNonRaggiungibile(ErroreEmbedding)`
  - `class EmbedderLMStudio: __init__(self, base_url: str, modello: str, client: httpx.Client | None = None)`; attributo `modello: str`; `calcola(self, testi: list[str]) -> list[list[float]]` (lotti da 32, un `POST {base_url}/embeddings` con `{"model": modello, "input": [...]}` per lotto; vettori riordinati secondo il campo `index` della risposta; timeout 60 s)
  - in `tests/finti_rag.py`: `class EmbedderFinto` con `modello = "finto"`, `dimensione` (predefinita 32), `chiamate: list[list[str]]` e `calcola(testi)` deterministico: «sacco di parole» con hash stabile (`zlib.crc32` della parola in minuscolo, modulo `dimensione`), vettore normalizzato; testo senza parole → vettore con un 1 nella prima componente. Così testi con parole in comune risultano vicini.

- [ ] **Step 1: Test che falliscono** (`tests/test_rag_embedding.py`, con `httpx.MockTransport`):
  - `test_corpo_della_richiesta`: percorso `/v1/embeddings`, corpo `{"model": "m", "input": ["a", "b"]}`.
  - `test_lotti`: 70 testi → 3 richieste (32, 32, 6); 70 vettori nell'ordine dei testi.
  - `test_ordine_secondo_index`: risposta con `data` in ordine inverso e `index` corretto → vettori riordinati.
  - `test_errore_lm_studio_cita_il_modello` (Review Focus 2): risposta 400 `{"error": {"message": "model not found"}}` → `ErroreEmbedding` il cui messaggio contiene `m` e `model not found`.
  - `test_lm_studio_spento`: il trasporto solleva `httpx.ConnectError` → `LMStudioNonRaggiungibile`.
  - `test_numero_di_vettori_sbagliato`: risposta con meno vettori → `ErroreEmbedding`.
  - `test_embedder_finto_deterministico`: due chiamate uguali → stessi vettori; norma 1; «gnocchi di patate» più vicino a «patate e gnocchi» che a «vino rosso».
- [ ] **Step 2:** `.\.venv\Scripts\python.exe -m pytest tests/test_rag_embedding.py -q` → FAIL.
- [ ] **Step 3:** implementare `rag/embedding.py` ed `EmbedderFinto`.
- [ ] **Step 4:** stesso comando → PASS.
- [ ] **Step 5: Commit** `feat(rag): embedding con LM Studio a lotti`.

### Task 5: Client REST di Qdrant e Qdrant finto in memoria

**Files:**
- Create: `rag/qdrant.py`, `tests/test_rag_qdrant.py`
- Modify: `tests/finti_rag.py` (aggiungere `QdrantFinto`)

**Interfaces:**
- Produces in `rag/qdrant.py`:
  - `class ErroreQdrant(Exception)`; `class QdrantNonRaggiungibile(ErroreQdrant)` (messaggio della specifica)
  - `@dataclass(frozen=True) InfoCollezione: dimensione: int; metadati: dict`
  - `@dataclass(frozen=True) Punto: id: str; vettore: list[float]; payload: dict`
  - `@dataclass(frozen=True) Trovato: score: float; payload: dict`
  - `class ClientQdrant: __init__(self, url: str, client: httpx.Client | None = None)` con i metodi (operazione REST tra parentesi):
    - `info_collezione(nome: str) -> InfoCollezione | None` (`GET /collections/{nome}`; 404 → `None`; dimensione da `result.config.params.vectors.size`, metadati da `result.config.metadata`, `{}` se assenti)
    - `crea_collezione(nome: str, dimensione: int, metadati: dict) -> None` (`PUT /collections/{nome}` con `{"vectors": {"size": d, "distance": "Cosine"}, "metadata": metadati}`)
    - `crea_indice(nome: str, campo: str) -> None` (`PUT /collections/{nome}/index?wait=true` con `{"field_name": campo, "field_schema": "keyword"}`)
    - `upsert(nome: str, punti: list[Punto]) -> None` (`PUT /collections/{nome}/points?wait=true` con `{"points": [{"id", "vector", "payload"}]}`)
    - `cerca(nome: str, vettore: list[float], limite: int, capitolo: str | None = None) -> list[Trovato]` (`POST /collections/{nome}/points/query` con `{"query": vettore, "limit": limite, "with_payload": true}` e, se `capitolo`, `"filter": {"must": [{"key": "capitolo", "match": {"value": capitolo}}]}`)
    - `ids_presenti(nome: str) -> set[str]` (`POST /collections/{nome}/points/scroll` con `{"limit": 1000, "with_payload": false, "with_vector": false}` e `offset` = `next_page_offset` finché non è `null`)
    - `elimina(nome: str, ids: list[str]) -> None` (`POST /collections/{nome}/points/delete?wait=true` con `{"points": ids}`; lista vuota → nessuna richiesta)
    - `conta(nome: str) -> int` (`POST /collections/{nome}/points/count` con `{"exact": true}`)
    - `capitoli(nome: str) -> list[str]` (`POST /collections/{nome}/facet` con `{"key": "capitolo", "limit": 100, "exact": true}`, valori ordinati)
  - Ogni `httpx.TransportError` → `QdrantNonRaggiungibile`; risposta non 2xx (salvo il 404 di `info_collezione`) → `ErroreQdrant` con stato e `status.error` della risposta.
  - Nota: per la «pulizia dei punti avanzati» si usa `ids_presenti` + `elimina` per ID invece della cancellazione con filtro citata come esempio nella specifica: un solo passaggio copre sia le posizioni in più sia le ricette sparite.
- Produces in `tests/finti_rag.py`: `class QdrantFinto` con `transport() -> httpx.MockTransport`, `richieste: list[tuple[str, str, dict | None]]` (metodo, percorso, corpo JSON), stato `collezioni: dict[str, {"dimensione", "metadati", "indici": set, "punti": dict[id, (vettore, payload)]}]`; risponde con la stessa forma JSON di Qdrant (`{"result": ..., "status": "ok"}`, errori `{"status": {"error": ...}}`) ai percorsi sopra; similarità coseno in Python puro, risultati ordinati per score decrescente; filtro `must`/`match`; vettore di dimensione sbagliata → 400. Funzione di comodo `client_finto(qdrant: QdrantFinto) -> ClientQdrant`.

- [ ] **Step 1: Test che falliscono** (`tests/test_rag_qdrant.py`, tutti contro `QdrantFinto`):
  - `test_collezione_assente` → `info_collezione` restituisce `None`.
  - `test_crea_e_leggi_collezione`: dopo `crea_collezione("c", 4, {"embedding_modello": "m", "embedding_dimensione": 4})` → `InfoCollezione(4, {...})`; corpo inviato con `"distance": "Cosine"`.
  - `test_indice_keyword`: richiesta `PUT /collections/c/index...` con `field_schema` `keyword`.
  - `test_upsert_stesso_id_sostituisce`: due upsert dello stesso ID → `conta == 1`, payload del secondo.
  - `test_cerca_ordinata_e_filtrata`: risultati in score decrescente; con `capitolo="Fritti"` il corpo contiene il `filter` della specifica e tutti i payload hanno `capitolo == "Fritti"`.
  - `test_scroll_a_pagine`: 2500 punti → `ids_presenti` restituisce 2500 ID (tre pagine).
  - `test_elimina_e_conta`, `test_elimina_lista_vuota_nessuna_richiesta`, `test_capitoli_distinti_ordinati`.
  - `test_qdrant_spento`: trasporto che solleva `httpx.ConnectError` → `QdrantNonRaggiungibile` con `docker compose ps` nel messaggio.
  - `test_errore_qdrant`: dimensione sbagliata nell'upsert → `ErroreQdrant` con il testo dell'errore.
- [ ] **Step 2:** `.\.venv\Scripts\python.exe -m pytest tests/test_rag_qdrant.py -q` → FAIL.
- [ ] **Step 3:** implementare `rag/qdrant.py` e `QdrantFinto`.
- [ ] **Step 4:** stesso comando → PASS.
- [ ] **Step 5: Commit** `feat(rag): client REST di Qdrant e Qdrant finto per i test`.

### Task 6: Ingestion

**Files:**
- Create: `rag/ingestion.py`, `tests/test_rag_ingestion.py`

**Interfaces:**
- Consumes: Task 1–5.
- Produces:
  - `class CambioBloccato(Exception)`
  - `id_punto(documento_id: str, posizione: int) -> str` (`str(uuid.uuid5(SPAZIO_ID, f"{documento_id}#{posizione}"))`, `SPAZIO_ID` = UUID costante scritto nel modulo)
  - `controlla_compatibilita(info: InfoCollezione, modello: str, dimensione: int | None) -> None` (metadati assenti, modello diverso o, se `dimensione` non è `None`, dimensione diversa → `CambioBloccato` con modello registrato, modello configurato e il suggerimento di usare un'altra `QDRANT_COLLEZIONE`)
  - `@dataclass(frozen=True) EsitoIngestion: ricette: int; chunk: int; punti_prima: int; punti_dopo: int; eliminati: int`
  - `esegui_ingestion(config: ConfigurazioneRag, embedder, qdrant: ClientQdrant, ricette_attese: int = 790) -> EsitoIngestion`
  - `main() -> int` e `if __name__ == "__main__"` (`python -m rag.ingestion`)

Ordine (fissato, per non toccare la collezione in caso di errore): leggere il file → estrarre e controllare la numerazione → dividere in chunk e preparare i payload (`documento_id`, `numero`, `titolo`, `capitolo`, `posizione`, `testo`, `fonte`) → se la collezione esiste, `controlla_compatibilita(info, modello, None)` → calcolare **tutti** gli embedding → controllare la dimensione (`controlla_compatibilita` con la dimensione, se la collezione esiste) → se non esiste, `crea_collezione` + `crea_indice(…, "capitolo")` → `punti_prima = conta` → upsert a lotti di 256 → eliminare `ids_presenti − ID calcolati` → `punti_dopo = conta`. `main` stampa e scrive nel log: ricette lette, chunk prodotti, punti prima, punti eliminati, punti dopo, modello, strategia, dimensione, overlap; codici di uscita dei Vincoli globali.

- [ ] **Step 1: Test che falliscono** (`tests/test_rag_ingestion.py`; corpus di prova scritto in `tmp_path`, `ricette_attese=5`, `EmbedderFinto`, `QdrantFinto`):
  - `test_un_punto_per_chunk`: `punti_dopo == chunk` e `punti_prima == 0`.
  - `test_payload_completo`: il punto di `ricetta-004` posizione 0 ha tutti e sette i campi con i valori attesi (`numero == 4`, `capitolo == "Fritti"`, `fonte == FONTE`).
  - `test_id_stabili`: `id_punto("ricetta-089", 0)` uguale a sé stesso tra due chiamate e diverso da `id_punto("ricetta-089", 1)`; gli ID nel Qdrant finto sono quelli di `id_punto`.
  - `test_due_ingestion_stesso_numero_di_punti` (evidenza del PDF): seconda esecuzione → `punti_prima == punti_dopo ==` chunk della prima, `eliminati == 0`.
  - `test_punti_avanzati_eliminati`: prima ingestion con `dimensione=1200`, seconda con `dimensione=4000` → `eliminati > 0`, `punti_dopo == chunk` della seconda; poi corpus senza la ricetta 5 (e `ricette_attese=4`) → nessun punto di `ricetta-005`.
  - `test_metadati_e_indice`: metadati della collezione `{"embedding_modello": "finto", "embedding_dimensione": 32}`; tra le richieste c'è l'indice su `capitolo`.
  - `test_cambio_bloccato_modello` / `test_cambio_bloccato_dimensione` / `test_collezione_senza_metadati_bloccata`: `CambioBloccato`; nessuna richiesta di scrittura (`PUT .../points`, `.../delete`) registrata dopo; per il modello diverso **nessuna chiamata** all'embedder.
  - `test_corpus_con_buchi`: ricetta tolta → `ErroreCorpus`, nessuna richiesta a Qdrant e all'embedder.
  - `test_ingestion_lm_studio_in_errore_non_tocca_la_collezione` (Review Focus 2 e 3): embedder che solleva `ErroreEmbedding` al secondo lotto → nessuna collezione creata.
  - `test_main_codici_di_uscita` (con `monkeypatch` sulle fabbriche di embedder e client usate da `main`): configurazione non valida → 2; `QdrantNonRaggiungibile` → 3; `LMStudioNonRaggiungibile` → 3; `CambioBloccato` → 4; ok → 0 con «punti dopo» nell'output.
- [ ] **Step 2:** `.\.venv\Scripts\python.exe -m pytest tests/test_rag_ingestion.py -q` → FAIL.
- [ ] **Step 3:** implementare `rag/ingestion.py` (in `main` le dipendenze si creano con due funzioni del modulo, `crea_embedder(config)` e `crea_qdrant(config)`, così i test le sostituiscono).
- [ ] **Step 4:** stesso comando → PASS.
- [ ] **Step 5: Commit** `feat(rag): ingestion con ID stabili, upsert e cambio bloccato`.

### Task 7: Ricerca

**Files:**
- Create: `rag/ricerca.py`, `tests/test_rag_ricerca.py`

**Interfaces:**
- Consumes: Task 4–6 (`controlla_compatibilita`, `crea_embedder`, `crea_qdrant`).
- Produces:
  - `K_PREDEFINITO = 5`, `K_MASSIMO = 20`
  - `class ErroreRicerca(Exception)`
  - `@dataclass(frozen=True) Risultato: classifica: int; score: float; numero: int; titolo: str; capitolo: str; posizione: int; testo: str`
  - `cerca(domanda: str, embedder, qdrant: ClientQdrant, collezione: str, k: int = K_PREDEFINITO, capitolo: str | None = None) -> list[Risultato]`
  - `formatta(risultati: list[Risultato]) -> str`
  - `main(argv: list[str] | None = None) -> int` (`argparse`: `domanda`, `--capitolo`, `--k`)

Ordine dentro `cerca`, prima di ogni embedding: domanda vuota → `ErroreRicerca`; `k` fuori da 1–`K_MASSIMO` → `ErroreRicerca` («k deve essere tra 1 e 20»); collezione assente → `ErroreRicerca` («eseguire prima `python -m rag.ingestion`»); `controlla_compatibilita(info, embedder.modello, None)`; se `capitolo` non è in `qdrant.capitoli(collezione)` → `ErroreRicerca` con l'elenco dei capitoli disponibili. Poi embedding della domanda (stesso embedder dell'ingestion), controllo della dimensione, `qdrant.cerca`. `formatta` stampa per ogni risultato: classifica, score con 4 decimali, `N. numero titolo`, capitolo, posizione del chunk e testo.

- [ ] **Step 1: Test che falliscono** (`tests/test_rag_ricerca.py`; collezione popolata con `esegui_ingestion` sul corpus di prova):
  - `test_risultati_ordinati_per_score` e `test_k_predefinito_5` (con almeno 6 chunk nell'indice → 5 risultati).
  - `test_k_fuori_intervallo` parametrizzato `0`, `21`, `-1` → `ErroreRicerca`, nessuna chiamata all'embedder.
  - `test_k_massimo_20_accettato`.
  - `test_filtro_capitolo_durante_la_ricerca`: `capitolo="Fritti"` → tutti i risultati con capitolo `Fritti`; l'ultima richiesta `.../points/query` contiene `filter.must[0] == {"key": "capitolo", "match": {"value": "Fritti"}}`.
  - `test_capitolo_inesistente_elenca_i_disponibili` (Review Focus 4): `capitolo="fritti"` → `ErroreRicerca` il cui messaggio contiene `Fritti` e `Minestre in brodo`; nessuna chiamata `points/query`.
  - `test_domanda_vuota` (Review Focus 5): `"   "` → `ErroreRicerca`, nessuna richiesta all'embedder né a Qdrant.
  - `test_collezione_assente` e `test_modello_diverso_bloccato` (stesso controllo dell'ingestion).
  - `test_formatta_mostra_la_fonte`: l'output contiene score, `N. 4`, il titolo, `Fritti`, la posizione e il testo.
  - `test_main_codici_di_uscita`: ok → 0; `--k 25` → 4; `QdrantNonRaggiungibile` → 3.
- [ ] **Step 2:** `.\.venv\Scripts\python.exe -m pytest tests/test_rag_ricerca.py -q` → FAIL.
- [ ] **Step 3:** implementare `rag/ricerca.py`.
- [ ] **Step 4:** stesso comando → PASS.
- [ ] **Step 5: Commit** `feat(rag): ricerca top-k con filtro per capitolo`.

### Task 8: Valutazione

**Files:**
- Create: `rag/valutazione.py`, `rag/domande.json`, `tests/test_rag_valutazione.py`

**Interfaces:**
- Consumes: `cerca`, `Risultato` (Task 7).
- Produces:
  - `rag/domande.json`: lista di 11 oggetti `{"domanda": str, "attese": [int, ...]}` con testi e numeri **esattamente** come nella tabella della specifica (domande 1–11; 6 e 11 con `[]`)
  - `@dataclass(frozen=True) Domanda: testo: str; attese: list[int]`
  - `carica_domande(percorso: Path = <rag/domande.json>) -> list[Domanda]`
  - `@dataclass(frozen=True) Riga: domanda: Domanda; posizione: int | None; score_fonte: float | None; score_migliore: float`
  - `valuta(domande: list[Domanda], cerca_fn: Callable[[str], list[Risultato]]) -> list[Riga]` (posizione = classifica del primo risultato il cui `numero` è tra le `attese`)
  - `tabella_markdown(righe: list[Riga]) -> str`
  - `main() -> int` (`k = 5`, stessi codici di uscita)

Tabella: colonne `| # | Domanda | Fonte attesa | Posizione | Score fonte | Score migliore |`; fonte attesa come `N. 455, 456` o `nessuna`; posizione numero o `assente`; per le domande senza risposta `—` in posizione e score fonte; score con 4 decimali. Ultima riga dopo la tabella: `Fonte attesa trovata in X casi su Y.` (Y = domande con fonte attesa).

- [ ] **Step 1: Test che falliscono** (`tests/test_rag_valutazione.py`, con una `cerca_fn` finta che restituisce risultati fissi):
  - `test_domande_della_specifica`: 11 domande; la 1 ha `attese == [89]`, la 5 `[455, 456]`, la 7 `[78, 79, 80]`, la 6 e la 11 `[]`; 9 con fonte attesa.
  - `test_posizione_e_score_della_fonte`: fonte al 3° posto → `posizione == 3`, `score_fonte` del 3° risultato, `score_migliore` del 1°.
  - `test_fonte_assente` → `posizione is None`; nella tabella `assente`.
  - `test_domanda_senza_risposta`: nella tabella `nessuna`, `—` e lo score migliore.
  - `test_riepilogo`: `Fonte attesa trovata in 1 casi su 2.` per un caso con una trovata e una assente.
  - `test_tabella_riproducibile`: due chiamate con gli stessi risultati → stessa stringa.
  - `test_valutazione_sul_qdrant_finto`: `main`-equivalente su corpus di prova con `EmbedderFinto` e `QdrantFinto` produce una tabella con 11 righe.
- [ ] **Step 2:** `.\.venv\Scripts\python.exe -m pytest tests/test_rag_valutazione.py -q` → FAIL.
- [ ] **Step 3:** implementare `rag/valutazione.py` e `rag/domande.json`.
- [ ] **Step 4:** stesso comando → PASS.
- [ ] **Step 5: Commit** `feat(rag): valutazione con domande e fonte attesa`.

### Task 9: Indipendenza e Docker (`rag/Dockerfile`, `compose.yaml`)

**Files:**
- Create: `rag/Dockerfile`, `tests/test_rag_indipendente.py`, `tests/test_rag_docker.py`
- Modify: `compose.yaml` (servizi `qdrant` e `ingestion`, volume `dati-qdrant`, commento in testa), `tests/test_docker_compose.py` (solo `test_quattro_servizi`, modifica approvata)

**Interfaces:**
- Produces: servizi `qdrant` e `ingestion` con i valori della specifica (sezione «Docker Compose»).

- [ ] **Step 1: Test che falliscono:**
  - `tests/test_rag_indipendente.py::test_rag_non_importa_gli_altri_pacchetti` (stesso metodo `ast` di `tests/test_backend_indipendente.py`): nessun modulo di `rag/` importa `assistente`, `backend`, `frontend`; l'elenco dei file comprende `configurazione.py`, `corpus.py`, `chunking.py`, `embedding.py`, `qdrant.py`, `ingestion.py`, `ricerca.py`, `valutazione.py`.
  - `tests/test_rag_docker.py` (riusa `_configurazione` importandola da `tests/test_docker_compose.py`, saltato senza Docker):
    - `test_qdrant`: `image == "qdrant/qdrant:v1.20.2"`, nessun `build`, unica porta `("127.0.0.1", "6333", 6333)`, volume `("volume", "dati-qdrant", "/qdrant/storage")`, `"dati-qdrant"` nei volumi, nessun `profiles`.
    - `test_ingestion_con_profilo` (con `--profile rag`): `profiles == ["rag"]`; dockerfile `rag/Dockerfile`; `command == ["python", "-m", "rag.ingestion"]`; `environment` con `QDRANT_URL == "http://qdrant:6333"`, `LM_BASE_URL == "http://host.docker.internal:1234/v1"`, `CORPUS_FILE == "dati/artusi.txt"`; `host-gateway` in `extra_hosts`; volume bind con target `/app/dati` e `read_only` vero; `qdrant` in `depends_on`; nessuna `ports`.
    - `test_ingestion_non_parte_con_up`: senza profilo `ingestion` non è nei servizi.
    - `test_dockerfile_rag` (solo testo, senza Docker): `FROM python:3.13-slim`, `WORKDIR /app`, righe `COPY` esattamente `COPY requirements.txt .` e `COPY rag ./rag`, `CMD ["python", "-m", "rag.ingestion"]`.
  - `tests/test_docker_compose.py::test_quattro_servizi` diventa: `assert set(servizi) == {"agente", "backend", "frontend", "db", "qdrant"}` con commento «i quattro servizi della lezione 6 più qdrant (lezione 7)» (nome della funzione invariato).
- [ ] **Step 2:** `.\.venv\Scripts\python.exe -m pytest tests/test_rag_indipendente.py tests/test_rag_docker.py tests/test_docker_compose.py -q` → FAIL sui test nuovi e su `test_quattro_servizi`.
- [ ] **Step 3:** scrivere `rag/Dockerfile` (struttura di `backend/Dockerfile`) e i due servizi in `compose.yaml` con commenti didattici (dashboard `http://localhost:6333/dashboard`, `docker compose run --rm ingestion`, avvertenza che `down -v` cancella anche la collezione). Nessun healthcheck su `qdrant`: l'ingestion che parte prima di Qdrant pronto esce con codice 3 e il messaggio chiaro (scelta lasciata al builder).
- [ ] **Step 4:** stesso comando → PASS; poi `.\.venv\Scripts\python.exe -m pytest -q` (tutta la suite: nessun test della lezione 6 rotto).
- [ ] **Step 5: Commit** `feat(docker): servizi qdrant e ingestion in compose.yaml (lezione 7)` (file: `rag/Dockerfile`, `compose.yaml`, i tre file di test).

### Task 10: Documentazione, prova mirata e istruzioni per l'utente

**Files:**
- Modify: `README.md` (sezione «RAG: ingestion e ricerca»: download del corpus, avvio di Qdrant, ingestion, ricerca, valutazione, dashboard, diagnosi dalla tabella di pag. 23, test nuovi; nota che il «Qdrant in memoria» dei test è un finto scritto nel progetto, non quello della libreria ufficiale), `CLAUDE.md` (solo se manca una convenzione stabile)

- [ ] **Step 1:** scrivere la sezione del README con comandi PowerShell e Docker. Download del corpus (dalla cartella `assistente-laboratorio`):
  ```powershell
  New-Item -ItemType Directory -Force dati
  Invoke-WebRequest "https://www.gutenberg.org/ebooks/59047.txt.utf-8" -OutFile dati\artusi.txt
  # se Gutenberg è in manutenzione, il mirror ufficiale:
  Invoke-WebRequest "https://gutenberg.pglaf.org/5/9/0/4/59047/59047-0.txt" -OutFile dati\artusi.txt
  ```
- [ ] **Step 2: Prova mirata di Claude** (con LM Studio acceso, se il modello di embedding è caricato): una sola chiamata `EmbedderLMStudio(...).calcola(["prova"])` dal PC con `.\.venv\Scripts\python.exe` → un vettore (dimensione attesa 768 per nomic) e conferma del formato della risposta. Se LM Studio è spento, annotarlo nel registro e passare oltre.
- [ ] **Step 3: Commit** `docs: README della lezione 7 (ingestion e ricerca)`.
- [ ] **Step 4: Fermarsi.** Un unico messaggio all'utente con le istruzioni numerate (cartella `assistente-laboratorio`, finestra PowerShell, ordine): scaricare il libro; caricare in LM Studio `text-embedding-nomic-embed-text-v1.5`; aggiungere al proprio `.env` `EMBEDDING_MODELLO=text-embedding-nomic-embed-text-v1.5`; `docker compose up -d qdrant`; dashboard; `docker compose build ingestion`; `docker compose run --rm ingestion` **due volte** (annotare i conteggi); ricerca `"Come si frigge il pollo?" --capitolo Fritti --k 3`; `python -m rag.valutazione` (copiare la tabella); `docker compose restart qdrant` e ricerca di nuovo; prova del cambio bloccato con `docker compose run --rm -e EMBEDDING_MODELLO=text-embedding-bge-m3 ingestion` (senza toccare il `.env`; deve fermarsi con codice 4 e lasciare uguale il conteggio). Con, per ogni passo, «deve succedere Y». Dopo che il libro è scaricato, Claude esegue `tests/test_rag_corpus.py::test_libro_vero` e, a Qdrant acceso, ricerca e valutazione anche dal PC.

### Task 11: Consegna, revisione e chiusura

**Files:**
- Create: `docs/retrieval.md`
- Modify: `README.md` («Esiti delle prove reali» della lezione 7), piano (caselle), registro

- [ ] **Step 1:** scrivere `docs/retrieval.md` con gli esiti dell'utente: conteggi delle due ingestion; configurazione (modello, strategia, dimensione 1200, overlap 200, k = 5, niente prefissi nomic e perché); tabella di partenza; due query commentate (una con `--capitolo`); nota sul Qdrant finto dei test; sezioni vuote «Dopo la modifica A» e «Dopo la modifica B» da completare nelle parti successive.
- [ ] **Step 2:** esiti nel README; commit `docs: valutazione di partenza e esiti della lezione 7, esercizio 1`.
- [ ] **Step 3:** revisione indipendente dell'intero branch (un revisore nuovo, con specifica e piano); Critical e Important corretti con TDD, Minor nel registro.
- [ ] **Step 4:** serie completa `.\.venv\Scripts\python.exe -m pytest -q` → tutto superato (attesi i 695 + i nuovi, skipped dichiarati).
- [ ] **Step 5:** aggiornare `HANDOFF.md`, `CLAUDE.local.md`, registro; **fermarsi e chiedere** il merge `--no-ff` di `feat/rag-ingestion` in `dev`.
