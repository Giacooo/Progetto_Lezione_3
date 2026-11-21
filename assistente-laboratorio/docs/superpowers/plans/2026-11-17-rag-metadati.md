# Modifica A (campo `contiene_dosi` e filtro) — piano

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ogni punto di Qdrant ha `contiene_dosi` (il chunk contiene una riga di un elenco di ingredienti); la ricerca può filtrare su questo campo, anche insieme al capitolo; i punti esistenti ricevono il campo senza ricalcolare gli embedding.

**Architecture:** il corpus individua le righe degli elenchi di ingredienti (blocchi rientrati con quantità) senza cambiare il testo; l'ingestion calcola il campo per chunk e crea un indice `bool`; `--solo-payload` riscrive solo il payload via «set payload» di Qdrant; la ricerca aggiunge una condizione `must`.

**Tech Stack:** Python, httpx (API REST di Qdrant), pytest con Qdrant ed embedder finti. Nessuna dipendenza nuova.

**Spec:** `docs/superpowers/specs/2026-11-17-rag-metadati-design.md`

## Global Constraints

- Branch `feat/rag-metadati` (da `feat/rag-ingestion`). Modo di lavoro veloce: blocchi senza conferme; ci si ferma per Docker, prove dell'utente, merge, push.
- Test sempre con servizi spenti; pytest mirato per task, **serie completa una sola volta a fine fase** (preferenza dell'utente).
- Il `testo` di ricette e chunk **non cambia** (stessi embedding dell'esercizio 1).
- Comandi con `.\.venv\Scripts\python.exe`; codici di uscita 0 / 2 / 3 / 4 invariati.
- Git: staging per percorsi espliciti; mai i 4 file della Lezione 3, `HANDOFF*`, `PROMPT-ripresa-*`, `dati/`, `.env`; messaggi senza BOM con `git commit -F`; `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; nessun push.
- Claude non avvia container né costruisce immagini.

## Review Focus

1. **Poesia o lettera rientrata** nella stessa ricetta di un elenco: solo le righe dell'elenco contano → `test_poesia_esclusa` (Task 1).
2. **Pezzo di riga di ingredienti portato dall'overlap** all'inizio del chunk successivo: non rende vero il campo → `test_overlap_parziale_non_conta` (Task 3).
3. **`--solo-payload` dopo un cambio di `CHUNK_DIMENSIONE`** (ID diversi da quelli presenti): si ferma con codice 4 senza scritture → `test_solo_payload_id_diversi` (Task 3).
4. **`--solo-dosi` su una collezione dell'esercizio 1 non aggiornata:** messaggio che chiede `--solo-payload`, codice 4, nessuna lista vuota silenziosa → `test_solo_dosi_senza_campo` (Task 4).
5. **`--solo-payload` con `EMBEDDING_MODELLO` diverso da quello registrato:** cambio bloccato anche senza embedding, nessuna scrittura → `test_solo_payload_modello_diverso` (Task 3).

---

### Task 1: Corpus — righe degli elenchi di ingredienti

**Files:** Modify `rag/corpus.py`; Test `tests/test_rag_corpus.py`

**Interfaces:**
- Produces: `PAROLE_QUANTITA: tuple[str, ...]`; `e_elenco_ingredienti(righe: list[str]) -> bool`; `Ricetta.righe_dosi: tuple[str, ...] = ()` (righe pulite con `_pulisci`, come compaiono nel `testo`).

- [x] **Step 1: test che falliscono**
  - `test_elenco_con_quantita`: `e_elenco_ingredienti(["Ricotta, grammi 180.", "Petto di cappone, mezzo."])` → True; `["Acqua, litri 2."]` → True; `["Uova, uno intero e un rosso."]` → True.
  - `test_poesia_esclusa`: `e_elenco_ingredienti(["UN AMMIRATORE"])` → False; `["_Quando Sol est in leone,_", "_Bonum vinum cum popone,_"]` → False.
  - `test_righe_dosi_corpus_prova`: con `estrai_ricette(CORPUS_PROVA)`: ricetta 2 → `("Zampa di vitello, una.", "Acqua, litri 2.")`; ricetta 3 → le 4 righe da «Ricotta, grammi 180.» a «Uova, uno intero e un rosso.» (non «UN AMMIRATORE»); ricette 1, 4, 5 → `()`.
  - `test_dosi_solo_in_prosa`: una ricetta di prova con «grammi 300 di riso» dentro una frase non rientrata → `righe_dosi == ()`.
  - `test_testo_invariato`: il `testo` delle ricette di `CORPUS_PROVA` è identico a prima (confronto con valore atteso della ricetta 2).
  - In `test_libro_vero` (saltato senza libro): almeno 340 ricette con `righe_dosi` non vuote; nessuna riga di dosi uguale a «UN AMMIRATORE».
- [x] **Step 2:** `.\.venv\Scripts\python.exe -m pytest tests/test_rag_corpus.py -q` → FAIL.
- [x] **Step 3:** implementare. Quantità = una cifra o, senza distinguere maiuscole, una parola che inizia con `grammi`, `uovo`, `uova`, `mezzo`, `mezza`, `metà`, `cucchiai`, `decilitr`, `litr`, `chilogramm`, `etto`, `etti`, oppure `n.` seguito da spazio o cifra. In `_testo_ricetta` (o accanto) raccogliere le righe dei gruppi rientrati per cui `e_elenco_ingredienti` è vero.
- [x] **Step 4:** stesso comando → PASS. Verifica extra sulla copia di ricognizione (`%TEMP%\claude\artusi-ricognizione\artusi.txt`): ricette con elenco e blocchi esclusi, annotati nel registro.
- [x] **Step 5: Commit** `feat(rag): righe degli elenchi di ingredienti nel corpus`.

### Task 2: Client Qdrant e Qdrant finto

**Files:** Modify `rag/qdrant.py`, `tests/finti_rag.py`; Test `tests/test_rag_qdrant.py`

**Interfaces:**
- Produces: `crea_indice(nome, campo, schema: str = "keyword")`; `imposta_payload(nome: str, payload: dict, ids: list[str]) -> None` (lotti da 256, nessuna richiesta con lista vuota); `cerca(nome, vettore, limite, capitolo=None, solo_dosi: bool = False)`; `conta(nome, filtro: dict | None = None) -> int`.
- Finto: `POST points/payload` (unisce il payload; 404 se un ID non esiste), `points/count` con `filter`.

- [x] **Step 1: test che falliscono**
  - `test_indice_bool`: `crea_indice("c", "contiene_dosi", "bool")` → richiesta `{"field_name": "contiene_dosi", "field_schema": "bool"}`.
  - `test_imposta_payload`: dopo upsert, `imposta_payload("c", {"contiene_dosi": True}, [id1])` → payload di id1 ha il campo e conserva gli altri; vettore invariato; percorso `/collections/c/points/payload`, corpo `{"payload": {...}, "points": [id1]}`.
  - `test_imposta_payload_lista_vuota_nessuna_richiesta`.
  - `test_cerca_solo_dosi_e_capitolo`: corpo con `filter.must` = condizione capitolo + `{"key": "contiene_dosi", "match": {"value": True}}`; solo `solo_dosi` → una condizione.
  - `test_conta_con_filtro`: `conta("c", {"must": [{"key": "contiene_dosi", "match": {"value": True}}]})` → conteggio dei soli punti con il campo vero.
- [x] **Step 2:** `.\.venv\Scripts\python.exe -m pytest tests/test_rag_qdrant.py -q` → FAIL.
- [x] **Step 3:** implementare client e finto.
- [x] **Step 4:** stesso comando → PASS.
- [x] **Step 5: Commit** `feat(rag): set payload, filtro contiene_dosi e conteggio con filtro nel client Qdrant`.

### Task 3: Ingestion — campo, indice e `--solo-payload`

**Files:** Modify `rag/ingestion.py`; Test `tests/test_rag_ingestion.py`

**Interfaces:**
- Consumes: `Ricetta.righe_dosi` (Task 1); `crea_indice`, `imposta_payload` (Task 2).
- Produces: `contiene_dosi(testo_chunk: str, righe_dosi: tuple[str, ...]) -> bool`; `aggiorna_payload(config, qdrant, ricette_attese=RICETTE_ATTESE) -> EsitoPayload` con `@dataclass(frozen=True) EsitoPayload: punti: int; con_dosi: int; senza_dosi: int; punti_prima: int; punti_dopo: int`; `main(argv: list[str] | None = None)` con `--solo-payload`.
- I passi 1–5 (libro → payload con ID) diventano una funzione comune usata da `esegui_ingestion` e `aggiorna_payload`.

- [x] **Step 1: test che falliscono**
  - `test_campo_contiene_dosi`: dopo `esegui_ingestion` su `CORPUS_PROVA`: i punti della ricetta 2 → True; ricette 1, 4, 5 → False; ogni punto ha il campo (bool).
  - `test_overlap_parziale_non_conta`: `contiene_dosi("grammi 30.\nUova, uno intero e un rosso.", ("Parmigiano grattato, grammi 30.",))` → False; con la riga intera → True.
  - `test_indici`: indici `{"capitolo": "keyword", "contiene_dosi": "bool"}`.
  - `test_solo_payload_aggiunge_il_campo`: collezione creata con payload senza `contiene_dosi` (togliere il campo dai punti nel finto dopo un'ingestion); `aggiorna_payload` → tutti i punti hanno il campo corretto; vettori identici a prima; nessun `PUT .../points` e nessun `points/delete` dopo l'inizio; `punti_prima == punti_dopo == punti`; `con_dosi + senza_dosi == punti`; indice `bool` presente.
  - `test_solo_payload_senza_embedder`: `aggiorna_payload` non riceve embedder (firma) e `main(["--solo-payload"])` non costruisce `EmbedderLMStudio` (monkeypatch di `crea_embedder` che fallisce se chiamato).
  - `test_solo_payload_collezione_assente` → `ErroreQdrant`/errore dati con «ingestion completa», codice 4 da `main`.
  - `test_solo_payload_id_diversi`: ingestion con `dimensione=4000`, poi `aggiorna_payload` con la configurazione predefinita → errore che cita «ingestion completa», `scritture(finto, dopo) == []`.
  - `test_solo_payload_modello_diverso`: config con `embedding_modello="altro-modello"` → `CambioBloccato`, nessuna scrittura.
- [x] **Step 2:** `.\.venv\Scripts\python.exe -m pytest tests/test_rag_ingestion.py -q` → FAIL.
- [x] **Step 3:** implementare. `imposta_payload` una volta per gli ID con True e una per quelli con False. Stampa di `--solo-payload`: `modello di embedding`, `collezione`, `punti aggiornati`, `con dosi`, `senza dosi`, `punti prima`, `punti dopo`.
- [x] **Step 4:** stesso comando → PASS.
- [x] **Step 5: Commit** `feat(rag): campo contiene_dosi, indice e ingestion --solo-payload`.

### Task 4: Ricerca con `--solo-dosi`

**Files:** Modify `rag/ricerca.py`; Test `tests/test_rag_ricerca.py`

**Interfaces:**
- Consumes: `cerca(..., solo_dosi)` e `conta(nome, filtro)` (Task 2).
- Produces: `cerca(domanda, embedder, qdrant, collezione, k=K_PREDEFINITO, capitolo=None, solo_dosi: bool = False)`; `Risultato.contiene_dosi: bool | None`; opzione CLI `--solo-dosi`.

- [x] **Step 1: test che falliscono**
  - `test_solo_dosi`: dopo l'ingestion di `CORPUS_PROVA`, `cerca("dosi della gelatina", ..., k=5, solo_dosi=True)` → al massimo 5 risultati, tutti con `contiene_dosi` True, almeno uno.
  - `test_solo_dosi_e_capitolo`: `capitolo="Minestre in brodo", solo_dosi=True` → tutti del capitolo e con il campo vero.
  - `test_solo_dosi_senza_campo`: punti senza il campo → errore che cita `--solo-payload`, `main` restituisce 4, nessuna query (`points/query` non chiamato).
  - `test_formatta_mostra_dosi`: la riga del risultato contiene `dosi: sì` o `dosi: no`.
  - `test_main_solo_dosi` (argv con `--solo-dosi`) → codice 0.
- [x] **Step 2:** `.\.venv\Scripts\python.exe -m pytest tests/test_rag_ricerca.py -q` → FAIL.
- [x] **Step 3:** implementare: con `solo_dosi`, prima della query `conta` con filtro `contiene_dosi = true`; se 0 → errore.
- [x] **Step 4:** stesso comando → PASS.
- [x] **Step 5: Commit** `feat(rag): filtro --solo-dosi nella ricerca`.

### Task 5: Documentazione, verifica di fase e chiusura

**Files:** Modify `README.md` (sezione RAG: campo, `--solo-payload`, `--solo-dosi`, test nuovi), `docs/retrieval.md` (sezione «Dopo la modifica A»: cosa registrare), piano, registro `..\.superpowers\sdd\2026-11-17-rag-metadati\progress.md`.

- [x] **Step 1:** README e `docs/retrieval.md` (struttura; i numeri arrivano dalle prove reali).
- [x] **Step 2:** serie completa `.\.venv\Scripts\python.exe -m pytest -q` → tutto superato (unica esecuzione completa della fase).
- [x] **Step 3: Commit** `docs: README e retrieval della modifica A`.
- [x] **Step 4:** revisione indipendente del branch (`c42619a..HEAD`), Critical/Important con TDD, Minor nel registro.
- [ ] **Step 5:** aggiornare `HANDOFF.md`; istruzioni per le prove reali dell'utente (esercizio 1 + modifica A) in un unico messaggio quando l'utente decide di farle; merge solo con conferma.
