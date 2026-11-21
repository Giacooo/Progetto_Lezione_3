# Lezione 7 — correzione dei Minor rinviati (piano)

Richiesta dell'utente (2026-11-21): correggere, prima delle prove reali, i Minor rinviati dalle
revisioni di esercizio 1, modifica A e modifica B (registri in `..\.superpowers\sdd\`). Branch
`fix/rag-minori`, da `feat/rag-chunking-titolo`. Nessuna dipendenza nuova; codici di uscita
0/2/3/4 invariati; payload, ID e formato del testo indicizzato invariati.

## Global Constraints

- TDD per ogni cambio di comportamento; test con servizi spenti; serie completa una volta alla fine.
- Staging per percorsi espliciti; Conventional Commits in italiano senza BOM; nessun push.

## Task 1: errori chiari invece dei traceback (esercizio 1: M1, M3, M5, M6)

- [x] `rag/qdrant.py`: una risposta di Qdrant di forma inattesa (JSON non valido, campi mancanti)
  diventa `ErroreQdrant` («risposta di forma inattesa»), quindi codice 4 con messaggio, non un
  traceback. Test parametrizzato su tutte le operazioni che leggono la risposta.
- [x] `rag/corpus.py`: libro non UTF-8, percorso che è una cartella, permessi → `ErroreCorpus`.
- [x] `rag/ricerca.py`: `--k` non numerico → codice 4 con «k deve essere un numero intero tra 1 e
  20» (prima: codice 2 di argparse, confuso con «configurazione non valida»).
- [x] `rag/ingestion.py`: ricetta che non produce chunk → WARNING nel log con numero e titolo.

## Task 2: pulizie (A: filtro in due punti; B: M1, M2, M5)

- [x] Condizione «contiene_dosi vero» definita una volta sola in `rag/qdrant.py`
  (`CONDIZIONE_DOSI`), usata da `qdrant.cerca` e da `ricerca.FILTRO_DOSI`.
- [x] Test della modifica B più severi: la ricerca controlla anche che il vettore salvato sia quello
  del testo con l'intestazione; l'atteso del testo passato all'embedder scritto per esteso.
- [x] Commenti di testa dei test che citano la modifica B; commento sul monkeypatch più breve.

## Task 3: documentazione (esercizio 1: M4; A: elenco del codice 4; B: M3)

- [x] `compose.yaml`: commenti «quattro servizi» aggiornati (con Qdrant `up -d` ne avvia cinque).
- [x] README: elenco completo dei casi del codice 4 (chunking cambiato, collezione non aggiornata,
  `--k` non numerico, risposta di Qdrant inattesa); `--solo-payload` non applica la modifica B.
- [x] Serie completa, registro, `HANDOFF.md`.

## Task 4: Minor della revisione dei Minor (richiesta dell'utente, 2026-11-21)

- [x] `--k` controllato in `main` prima della configurazione: non numerico o fuori da 1–20 → sempre
  codice 4; ammesse solo cifre 0-9 con un `+` facoltativo (niente `1_0` né cifre non ASCII).
- [x] `condizione_dosi()` e `filtro_dosi()` funzioni che danno un dizionario nuovo a ogni chiamata
  (prima un dizionario condiviso e modificabile).
- [x] Test di regressione: un 500 di Qdrant resta «Qdrant ha risposto 500», non «forma inattesa».
- [x] `compose.yaml`: porte aperte e nomi dei servizi citano anche Qdrant e `ingestion`.
- [x] Serie completa: 890 passed, 41 skipped, 0 failed.

## Task 5: regola dell'overlap per `contiene_dosi` (richiesta dell'utente, 2026-11-21)

- [x] Una riga di ingredienti conta solo nel chunk dove è nuova: `lunghezza_overlap` in
  `rag/chunking.py` (parte iniziale del chunk uguale alla fine del precedente, al massimo
  `CHUNK_OVERLAP`), `contiene_dosi(..., ripetuti)` e `dosi_per_chunk` in `rag/ingestion.py`.
  Chunking, testi, ID ed embedding invariati; `--solo-payload` aggiorna il campo.
- [x] Copia di prova: chunk con dosi da 406 a 355; ricette con almeno un chunk con dosi 347/347.
- [x] README e `docs/retrieval.md`; serie completa.

## Non corretti qui

- Esercizio 1, M2 (test del client ancorati a una risposta vera di Qdrant 1.20): richiede le prove
  reali; si fa dopo, con l'output vero.
