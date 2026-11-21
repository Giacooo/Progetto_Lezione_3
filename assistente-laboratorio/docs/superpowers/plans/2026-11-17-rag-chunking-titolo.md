# Modifica B (titolo e capitolo nel testo indicizzato) — piano

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ogni chunk arriva all'embedder preceduto da titolo e capitolo della ricetta; payload e ricerca restano col testo originale; l'ingestion completa sostituisce i vettori degli stessi punti senza ricreare la collezione e senza aumentare i punti.

**Architecture:** una funzione pura `testo_da_indicizzare` in `rag/ingestion.py`; `esegui_ingestion` passa all'embedder il suo risultato invece di `payload["testo"]`. Nessun cambio a payload, ID, Qdrant, ricerca, `--solo-payload`.

**Tech Stack:** Python, httpx (API REST di Qdrant), pytest con Qdrant ed embedder finti. Nessuna dipendenza nuova.

**Spec:** `docs/superpowers/specs/2026-11-17-rag-chunking-titolo-design.md`

## Global Constraints

- Branch `feat/rag-chunking-titolo` (da `feat/rag-metadati`). Esecuzione inline (modo di lavoro veloce): blocchi senza conferme; ci si ferma per Docker, prove dell'utente, merge, push.
- Formato esatto: `f"Ricetta: {titolo}\nCapitolo: {capitolo}\n\n{testo}"`; niente numero della ricetta.
- Payload `testo` = chunk originale (invariato rispetto alla modifica A).
- Test sempre con servizi spenti; pytest mirato per task, **serie completa una sola volta a fine fase**.
- Comandi con `.\.venv\Scripts\python.exe`; codici di uscita 0 / 2 / 3 / 4 invariati.
- Git: staging per percorsi espliciti; mai i 4 file della Lezione 3, `HANDOFF*`, `PROMPT-ripresa-*`, `dati/`, `.env`; messaggi senza BOM con `git commit -F`; `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; nessun push.
- Claude non avvia container né costruisce immagini; prove reali tutte alla fine (dall'utente).

## Review Focus

1. **Ingestion B su una collezione costruita prima di B** (stesso modello): nessun «cambio bloccato», collezione non ricreata, stessi ID, punti uguali, vettori sostituiti → `test_ricalcolo_senza_ricreare_la_collezione` (Task 1).
2. **Ricetta divisa in più chunk:** ogni chunk (non solo il primo) ha l'intestazione → `test_testo_passato_all_embedder` controlla tutti i chunk (Task 1).
3. **Risultato della ricerca dopo B:** testo senza intestazione → `test_ricerca_restituisce_il_testo_originale` (Task 1).
4. **`--solo-payload` dopo l'ingestion B:** ancora applicabile, nessun `PayloadNonAggiornabile` → `test_solo_payload_dopo_ingestion_b` (Task 1).
5. **Overlap con l'intestazione:** l'intestazione non entra nel testo dei chunk, quindi non viene ripetuta dall'overlap nel chunk successivo → coperto da `test_testo_passato_all_embedder` (intestazione esattamente una volta, in testa).

---

### Task 1: testo indicizzato con titolo e capitolo

**Files:**
- Modify: `rag/ingestion.py` (commento in testa, nuova funzione, passo 6 di `esegui_ingestion`, righe stampate da `main`)
- Test: `tests/test_rag_ingestion.py`, `tests/test_rag_ricerca.py`

**Interfaces:**
- Produces: `testo_da_indicizzare(titolo: str, capitolo: str, testo: str) -> str` in `rag/ingestion.py`.

- [x] **Step 1: Test che falliscono**

In `tests/test_rag_ingestion.py`:

```python
def test_testo_da_indicizzare():
    assert testo_da_indicizzare("Pollo fritto", "Fritti", "Tagliate il pollo.") == (
        "Ricetta: Pollo fritto\nCapitolo: Fritti\n\nTagliate il pollo.")

def test_testo_passato_all_embedder(tmp_path, qdrant, finto):
    embedder = EmbedderFinto()
    esegui_ingestion(configurazione(tmp_path), embedder, qdrant, ricette_attese=5)
    passati = [t for lotto in embedder.chiamate for t in lotto]
    punti = finto.collezioni["ricette"]["punti"]
    # stesso ordine dei punti preparati; uno per punto; ognuno = intestazione + testo originale
    attesi = [testo_da_indicizzare(p["titolo"], p["capitolo"], p["testo"]) for p in payload_in_ordine]
    assert passati == attesi
    # la ricetta 3 (più chunk): anche il chunk 1 ha l'intestazione, una sola volta
    # payload "testo" senza "Ricetta:" / "Capitolo:"
```

`payload_in_ordine` si ricava da `ingestion.prepara_punti(config, 5)[1]` (stesso ordine dell'embedding). Asserzioni aggiuntive: per ogni testo passato `t.count("Ricetta: ") == 1` e `t.startswith("Ricetta: ")`; per ogni payload salvato `not p["testo"].startswith("Ricetta: ")`.

```python
def test_ricalcolo_senza_ricreare_la_collezione(tmp_path, qdrant, finto, monkeypatch):
    config = configurazione(tmp_path)
    # collezione "prima di B": embedding del solo testo
    monkeypatch.setattr(ingestion, "testo_da_indicizzare", lambda titolo, capitolo, testo: testo)
    esegui_ingestion(config, EmbedderFinto(), qdrant, ricette_attese=5)
    prima = {pid: v for pid, (v, _) in finto.collezioni["ricette"]["punti"].items()}
    monkeypatch.undo()
    n = len(finto.richieste)
    esito = esegui_ingestion(config, EmbedderFinto(), qdrant, ricette_attese=5)
    dopo = {pid: v for pid, (v, _) in finto.collezioni["ricette"]["punti"].items()}
    assert not any(m == "PUT" and p == "/collections/ricette" for m, p, _ in finto.richieste[n:])
    assert dopo.keys() == prima.keys()
    assert esito.punti_prima == esito.punti_dopo == len(prima) and esito.eliminati == 0
    assert all(dopo[pid] != prima[pid] for pid in prima)
```

(Il punto salvato nel `QdrantFinto` è la coppia `(vettore, payload)`, come in `test_payload_completo`.)

```python
def test_solo_payload_dopo_ingestion_b(tmp_path, qdrant, finto):
    config = configurazione(tmp_path)
    esegui_ingestion(config, EmbedderFinto(), qdrant, ricette_attese=5)
    esito = aggiorna_payload(config, qdrant, ricette_attese=5)
    assert esito.punti_prima == esito.punti_dopo == esito.punti
```

In `tests/test_rag_ricerca.py`:

```python
def test_ricerca_restituisce_il_testo_originale(qdrant):
    risultati = cerca("pollo fritto", EmbedderFinto(), qdrant, "ricette", k=K_MASSIMO)
    assert risultati
    assert all(not r.testo.startswith("Ricetta: ") and "Capitolo: " not in r.testo for r in risultati)
```

- [x] **Step 2: Verificare che falliscono**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_rag_ingestion.py tests/test_rag_ricerca.py -q`
Expected: FAIL (`ImportError: testo_da_indicizzare`); i test della ricerca e di `--solo-payload` possono già passare (documentano l'invariante).

- [x] **Step 3: Implementare**

In `rag/ingestion.py`: `testo_da_indicizzare(titolo, capitolo, testo)` col formato dei Global Constraints; nel passo 6 di `esegui_ingestion` `testi = [testo_da_indicizzare(p["titolo"], p["capitolo"], p["testo"]) for _, p in punti_senza_vettore]` (chiamata attraverso il nome del modulo, così il monkeypatch del test funziona). Commento in testa «Modifica B» (perché, payload invariato, stessi ID → nessun punto in più, stesso modello → nessun blocco). In `main` una riga in più nell'uscita: `"testo indicizzato: titolo e capitolo + chunk (payload con il testo originale)"`.

- [x] **Step 4: Verificare che passano**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_rag_*.py -q`
Expected: tutti passati (1 saltato: `test_libro_vero` senza `dati/artusi.txt`). Se un test esistente confronta l'uscita di `main` riga per riga, aggiornarlo con la nuova riga.

- [x] **Step 5: Commit**

`git add rag/ingestion.py tests/test_rag_ingestion.py tests/test_rag_ricerca.py` — `feat(rag): titolo e capitolo davanti al testo indicizzato`

### Task 2: documentazione e chiusura della fase

**Files:**
- Modify: `README.md` (sezione «RAG: ingestion e ricerca»: cosa cambia con B, comando dell'ingestion completa e cosa aspettarsi: punti prima = punti dopo, eliminati 0; voce nella «Checklist delle prove reali» per B)
- Modify: `docs/retrieval.md` (configurazione: riga «Testo indicizzato»; sezione «Dopo la modifica B»: formato con esempio, motivo, schema del confronto da completare)
- Modify: questo piano (spunte), registro `..\.superpowers\sdd\2026-11-17-rag-chunking-titolo\progress.md`

- [x] **Step 1: README e `docs/retrieval.md`**

In «Dopo la modifica B» di `docs/retrieval.md`: esempio del testo indicizzato; output da completare di `docker compose run --rm ingestion` (punti prima, eliminati, punti dopo: attesi uguali, 0); tabella di confronto da completare con colonne `| # | Domanda | Posizione prima (A) | Posizione dopo (B) | Score fonte prima | Score fonte dopo |`, riga «Fonte attesa trovata: prima X/9, dopo Y/9» e un commento; ricerca `"Come si frigge il pollo?" --k 3` da confrontare. Nessun numero inventato.

- [x] **Step 2: Serie completa (una volta, fine fase)**

Run: `.\.venv\Scripts\python.exe -m pytest -q`
Expected: come a fine fase A più i nuovi test (atteso circa 839 passed, 41 skipped, 1 failed: `test_porta_di_un_altro_servizio[HTTP]`, a tempo, già noto anche su `dev`). Risultato nel registro.

- [x] **Step 3: Commit**

`git add README.md docs/retrieval.md docs/superpowers/plans/2026-11-17-rag-chunking-titolo.md` — `docs(rag): modifica B in README e retrieval.md`

- [ ] **Step 4: Revisione indipendente** del diff `66eda0d..HEAD` (subagente); Critical/Important corretti con TDD, Minor nel registro; `HANDOFF.md` aggiornato (non versionato).

- [ ] **Step 5: Prove reali (alla fine, dall'utente)** — insieme a quelle di esercizio 1 e A, nell'ordine dei branch: sul branch B `docker compose build ingestion`, `docker compose run --rm ingestion` (punti prima = dopo, eliminati 0), valutazione, ricerca di confronto; poi `docs/retrieval.md` completato.
