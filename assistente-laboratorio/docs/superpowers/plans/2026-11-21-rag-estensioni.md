# Estensioni della lezione 7 — piano

> **Per chi esegue:** skill richiesta: superpowers:executing-plans (esecuzione nella sessione, modo
> di lavoro veloce). Passi con caselle (`- [ ]`).

**Obiettivo:** documentare procedura e tabelle per le due estensioni del PDF (pag. 29): confronto
tra strategie di chunking e modello multilingue in una seconda collezione.

**Architettura:** nessun codice. Si usano le variabili esistenti (`QDRANT_COLLEZIONE`,
`CHUNK_STRATEGIA`, `EMBEDDING_MODELLO`) passate per una sola esecuzione con
`docker compose run --rm -e ...`. Base di confronto: la tabella «dopo B» della collezione `ricette`.

**Strumenti:** Markdown; pytest solo per la serie completa di fine fase.

**Specifica:** `docs/superpowers/specs/2026-11-21-rag-estensioni-design.md`

## Vincoli globali

- Branch `feat/rag-estensioni` (da `fix/rag-minori`); nessun file in `rag/` o `tests/` modificato.
- Collezioni: `ricette_finestra` (`CHUNK_STRATEGIA=finestra`, 1200/200, nomic) e `ricette_bge_m3`
  (paragrafi 1200/200, `EMBEDDING_MODELLO=text-embedding-bge-m3`, vettori attesi da 1024).
- Comandi Docker come quelli già nel README (`docker compose run --rm ingestion ...`); equivalenti
  dal PC con `$env:...` e `.\.venv\Scripts\python.exe -m rag...`.
- Commit Conventional Commits in italiano, messaggio senza BOM con `git commit -F`, staging per
  percorsi espliciti, `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Punti di attenzione (Review Focus)

1. Ingestion `finestra` senza `-e QDRANT_COLLEZIONE=...` → riscrive `ricette` senza errori: avviso
   in grassetto prima dei comandi, in `docs/retrieval.md` e nella voce 69 del README.
2. Ricerca o valutazione su `ricette_bge_m3` senza `-e EMBEDDING_MODELLO=text-embedding-bge-m3` →
   codice 4 «cambio bloccato»: scriverlo come esito atteso (prova che il blocco funziona), non come
   guasto.
3. Dal PC, le `$env:...` restano attive nella finestra di PowerShell: i comandi successivi
   finirebbero sulla collezione sbagliata → dopo le prove `Remove-Item Env:QDRANT_COLLEZIONE,
   Env:CHUNK_STRATEGIA, Env:EMBEDDING_MODELLO` (oppure chiudere la finestra).
4. `text-embedding-bge-m3` non caricato in LM Studio → codice 3: nella voce 70 il passo «caricare il
   modello» prima dell'ingestion.
5. Immagine `ingestion` non ricostruita sul branch → codice vecchio: `docker compose build
   ingestion` dopo il `git switch` (voce 69).

---

### Task 1: sezione «Estensioni» in `docs/retrieval.md`

**File:** Modifica: `docs/retrieval.md` (nuova sezione in fondo, dopo «Dopo la modifica B»).

- [x] **Step 1: scrivere la sezione** con, in quest'ordine:
  - perché (PDF pag. 29) e la tabella delle tre collezioni della specifica (collezione, strategia,
    modello, cosa cambia);
  - avvisi dei punti 1–3 del Review Focus;
  - «Confronto tra strategie di chunking»: comandi Docker e dal PC per ingestion e valutazione di
    `ricette_finestra`; tabella ingestion (ricette lette, chunk prodotti, punti dopo) da completare;
    tabella per domanda `| # | Domanda | Posizione paragrafi (B) | Posizione finestra | Score fonte
    paragrafi | Score fonte finestra |`; riga «Fonte attesa trovata: paragrafi _X_/9, finestra
    _Y_/9»; commento _da completare_;
  - «Modello multilingue»: caricare `text-embedding-bge-m3` in LM Studio; comandi per ingestion e
    valutazione di `ricette_bge_m3` (sempre con entrambe le `-e`); riga attesa nell'uscita
    `creata la collezione ricette_bge_m3 (coseno, dimensione 1024, modello text-embedding-bge-m3)`;
    tabella ingestion e tabella per domanda come sopra (nomic / bge-m3); prova del blocco:
    valutazione su `ricette_bge_m3` senza `-e EMBEDDING_MODELLO` → codice 4; commento _da
    completare_;
  - «Riepilogo»: `| Collezione | Strategia | Modello | Punti | Fonte attesa trovata |` con le tre
    righe vuote; query di confronto `"Come si frigge il pollo?" --k 3` sulle tre collezioni, commento
    _da completare_.
- [x] **Step 2: verificare** che ogni comando con `ricette_finestra` contenga
  `QDRANT_COLLEZIONE=ricette_finestra` e ogni comando con `ricette_bge_m3` contenga sia
  `QDRANT_COLLEZIONE=ricette_bge_m3` sia `EMBEDDING_MODELLO=text-embedding-bge-m3` (tranne la prova
  del blocco, dichiarata). Comando: `Select-String -Path docs\retrieval.md -Pattern "ricette_"`.
- [x] **Step 3: commit** `docs(rag): procedura e tabelle delle estensioni in retrieval.md`
  (`git add docs/retrieval.md docs/superpowers/specs/2026-11-21-rag-estensioni-design.md
  docs/superpowers/plans/2026-11-21-rag-estensioni.md`).

### Task 2: README, serie completa, chiusura

**File:** Modifica: `README.md` (sezione «RAG: ingestion e ricerca» e checklist dopo la voce 68).

- [x] **Step 1: README, sezione RAG:** un paragrafo «Estensioni (facoltative)» di 3–5 righe che
  spiega le due collezioni e rimanda a `docs/retrieval.md`, con l'avviso del punto 1.
- [x] **Step 2: README, checklist:** intestazione «Lezione 7, estensioni (branch
  `feat/rag-estensioni`, dopo la voce 68)»; voce **69** (strategie: `git switch
  feat/rag-estensioni`, `docker compose build ingestion`, ingestion e valutazione su
  `ricette_finestra`; esito: collezione nuova creata, `ricette` invariata — `docker compose run
  --rm ingestion python -m rag.valutazione` dà ancora la tabella «dopo B»); voce **70** (bge-m3:
  modello caricato, ingestion e valutazione su `ricette_bge_m3` con dimensione 1024; senza
  `-e EMBEDDING_MODELLO` → codice 4).
- [x] **Step 3: serie completa** (fine fase):
  `.\.venv\Scripts\python.exe -m pytest -q` → atteso **894 passed, 41 skipped, 0 failed** (nessun
  codice cambiato).
- [x] **Step 4: commit** `docs(rag): estensioni nel README e nella checklist delle prove`
  (`git add README.md docs/superpowers/plans/2026-11-21-rag-estensioni.md`), poi aggiornare
  `HANDOFF.md` (non versionato).
