# Estensioni della lezione 7: confronto delle strategie e modello multilingue (specifica breve)

_2026-11-21 · branch `feat/rag-estensioni` (da `fix/rag-minori`)_

## Intento

Completare le due estensioni del PDF (pag. 29): «confronto tra strategie di chunking sulle stesse
domande» e «un modello di embedding multilingue in una seconda collezione». Scopo dichiarato
dall'utente: **solo completare il PDF**, cioè una procedura documentata e le tabelle con i
risultati, non uno strumento per scegliere la configurazione.

- **Obiettivi:** comandi esatti per creare due collezioni nuove e valutarle con le stesse domande
  (`rag/domande.json`); tabelle da completare in `docs/retrieval.md`; voci nella checklist del
  README.
- **Non obiettivi:** codice nuovo; un comando che confronta più collezioni; cambiare la
  configurazione predefinita (`ricette`, paragrafi 1200/200, nomic).
- **Anti-obiettivo:** rovinare la collezione `ricette` (stato «dopo B»), che serve alle tabelle già
  previste.

## Approcci considerati

1. **Solo documentazione** (scelto dall'utente): le variabili esistenti (`QDRANT_COLLEZIONE`,
   `CHUNK_STRATEGIA`, `EMBEDDING_MODELLO`) bastano; si passano per una sola esecuzione con
   `docker compose run --rm -e ...`. Rapido, nessun rischio per il codice revisionato; la
   protezione di `ricette` dipende dalla procedura.
2. Documentazione + strategia di chunking registrata nei metadati e bloccata come il modello:
   protegge da un comando sbagliato, ma richiede codice, test, revisione e una regola per le
   collezioni già create senza quei metadati. Scartato: va oltre il PDF.

Le due estensioni sono unite in un'unica specifica e un solo branch (decisione dell'utente), perché
con l'approccio 1 sono lo stesso tipo di lavoro.

## Disegno

**Base di confronto:** la tabella «dopo B» (collezione `ricette`, paragrafi 1200/200, nomic). Ogni
estensione cambia **una sola cosa** rispetto alla base:

| Collezione | Strategia | Modello | Cosa cambia |
|---|---|---|---|
| `ricette` (base) | paragrafi 1200/200 | nomic | — |
| `ricette_finestra` | finestra 1200/200 | nomic | solo il chunking |
| `ricette_bge_m3` | paragrafi 1200/200 | `text-embedding-bge-m3` | solo il modello |

**Procedura** (Docker; equivalente dal PC con `$env:...` e `.\.venv\Scripts\python.exe -m rag...`),
sul branch `feat/rag-estensioni`, dopo le prove di B:

1. `docker compose run --rm -e QDRANT_COLLEZIONE=ricette_finestra -e CHUNK_STRATEGIA=finestra ingestion`
   → annotare punti e chunk; poi la stessa riga con `python -m rag.valutazione` in coda.
2. In LM Studio caricare `text-embedding-bge-m3`; poi
   `docker compose run --rm -e QDRANT_COLLEZIONE=ricette_bge_m3 -e EMBEDDING_MODELLO=text-embedding-bge-m3 ingestion`
   → annotare punti e dimensione dei vettori (attesa 1024); poi la stessa riga con
   `python -m rag.valutazione` in coda.
3. Una query di confronto per estensione (la stessa sulle tre collezioni), con breve commento.

**Avvisi da scrivere in evidenza** nella procedura:
- mai lanciare un'ingestion con una strategia diversa **senza** `-e QDRANT_COLLEZIONE=...`: la
  collezione `ricette` verrebbe riscritta senza errori;
- anche **valutazione e ricerca** su `ricette_bge_m3` vogliono `-e EMBEDDING_MODELLO=...bge-m3`
  (le domande vanno trasformate con lo stesso modello; altrimenti il cambio bloccato dà codice 4,
  ed è la prova attesa che il blocco funziona).

**Documenti da modificare:**
- `docs/retrieval.md`: nuova sezione «Estensioni» con la procedura, la tabella riassuntiva
  (collezione, punti, fonte attesa trovata X su Y: i valori che la valutazione stampa già) e le
  due tabelle di valutazione
  da completare, più un commento finale da scrivere dopo le prove;
- `README.md`: nella sezione RAG un paragrafo breve che rimanda a `docs/retrieval.md`; nella
  checklist delle prove nuove voci (69, 70) per le due estensioni, dopo la 68.

## Lasciato a chi costruisce

Formulazione esatta dei testi, scelta delle query di confronto (tra le domande di
`rag/domande.json`), numerazione definitiva delle voci della checklist. Nessun test nuovo (niente
codice): la serie completa si riesegue comunque a fine fase per conferma.
