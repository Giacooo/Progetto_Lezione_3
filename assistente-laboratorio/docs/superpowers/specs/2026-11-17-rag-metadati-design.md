# Lezione 7, modifica A — Campo `contiene_dosi` e filtro (specifica)

Parte dalla pipeline dell'esercizio 1 (specifica `2026-11-17-rag-ingestion-design.md`, branch
`feat/rag-ingestion`). Branch `feat/rag-metadati`, creato da `feat/rag-ingestion` perché
l'esercizio 1 non è ancora unito in `dev` (mancano le prove reali dell'utente).

## Intento

Poter cercare solo tra i passaggi che contengono le dosi di una ricetta (domande come «quanta
farina per gli gnocchi?»), aggiungendo un metadato al payload, senza ricalcolare gli embedding.

## Requisiti del PDF (pag. 28, alla lettera)

- Campo `contiene_dosi` nel payload (il chunk ha un elenco di ingredienti) e opzione per cercare
  solo tra questi chunk.
- Con il filtro, tutti i risultati hanno il campo vero, al massimo k.
- Si combina con il filtro per capitolo; il campo ha un indice sul payload.
- Tutti i punti esistenti ricevono il campo senza ricalcolare gli embedding.
- Ciclo di Superpowers e nuova valutazione alla fine; test e commit Conventional Commits (pag. 29).

## Obiettivi, non obiettivi, anti-obiettivi

- **Obiettivi:** il campo booleano su ogni punto; l'opzione `--solo-dosi` della ricerca; un modo
  per dare il campo ai punti già presenti senza LM Studio; la valutazione dopo A in
  `docs/retrieval.md`.
- **Non obiettivi:** dosi scritte dentro la prosa (es. «grammi 300 di riso» in una frase): non sono
  un elenco di ingredienti; titolo e capitolo nel testo indicizzato (modifica B); nuove domande di
  valutazione.
- **Anti-obiettivi:** ricalcolare gli embedding o ricreare la collezione per aggiungere il campo;
  marcare come «dosi» le poesie e le lettere rientrate; cambiare il testo dei chunk (cambierebbe gli
  embedding e la valutazione di partenza).

## Decisioni prese con l'utente (2026-11-17)

- **Definizione (scelta 1):** `contiene_dosi` è vero se il chunk contiene almeno una riga di un
  **elenco di ingredienti**: un blocco di righe **rientrate** consecutive della ricetta in cui almeno
  una riga ha una quantità. Le dosi solo nella prosa non contano.
- **Punti esistenti (strada 1):** `python -m rag.ingestion --solo-payload` rilegge il libro,
  ricalcola i chunk e il campo, e scrive solo il payload in Qdrant, senza embedding.
- **Ricerca:** opzione `--solo-dosi`, combinabile con `--capitolo` e `--k`.
- Modo di lavoro veloce; prove reali raggruppate a fine fase.

## Approcci considerati

1. **Dal libro con `--solo-payload` (scelto):** il campo si calcola dalla struttura originale (righe
   rientrate), che solo il libro conserva; gli ID stabili permettono di aggiornare i punti giusti.
2. **Dal testo già salvato in Qdrant:** non serve il libro, ma nel testo salvato le righe rientrate
   non si riconoscono (un elenco di una riga diventa un paragrafo qualsiasi; poesie e ingredienti si
   confondono). Scartato.
3. **Ingestion completa:** ricalcola gli embedding, contro il PDF. Scartato.

## Ricognizione (copia di prova del libro, 2026-11-17)

- 403 blocchi di righe rientrate tra «RICETTE» e «APPENDICE»; circa 20 senza quantità (poesie,
  lettere, versi latini, «_Prima:_», «UN AMMIRATORE»): non sono elenchi di ingredienti.
- 352 ricette hanno un blocco di più righe; 111 ricette danno le dosi solo nella prosa («grammi N»).

## Progetto

### Corpus (`rag/corpus.py`)

- `Ricetta` riceve il campo `righe_dosi: tuple[str, ...] = ()`: le righe (già pulite, come compaiono
  nel testo della ricetta) dei blocchi rientrati che sono elenchi di ingredienti. Il `testo` della
  ricetta **non cambia** (stessi chunk, stessi embedding dell'esercizio 1).
- Un blocco rientrato è un elenco di ingredienti se almeno una riga contiene una **quantità**: una
  cifra oppure una parola di misura tra `grammi`, `uovo`/`uova`, `mezzo`/`mezza`, `metà`,
  `cucchiai*`, `decilitr*`, `litr*`, `chilogramm*`, `etto`/`etti`, `n.` (senza distinguere
  maiuscole). Regola in una funzione con nome e test; elenco delle parole come costante.

### Ingestion (`rag/ingestion.py`)

- Payload con il nuovo campo `contiene_dosi: bool`: vero se almeno una riga del chunk
  (`testo.split("\n")`) è **uguale** a una delle `righe_dosi` della ricetta (riga intera, così un
  pezzo di riga portato dall'overlap non conta).
- Indice sul payload: `contiene_dosi` con schema `bool`, chiesto a ogni ingestion come quello su
  `capitolo` (`crea_indice` riceve lo schema).
- **`--solo-payload`:** stessi passi 1–5 (libro, ricette, numerazione, chunk, payload), poi:
  la collezione deve esistere (altrimenti codice 4: «eseguire prima l'ingestion completa»); modello
  registrato uguale a `EMBEDDING_MODELLO` (stesso controllo dell'esercizio 1, senza dimensione);
  gli ID calcolati devono essere **esattamente** quelli presenti (`ids_presenti`), altrimenti codice
  4 («il chunking è cambiato: eseguire l'ingestion completa»); poi indici e scrittura del solo campo
  con l'API «set payload» di Qdrant (`POST /collections/{c}/points/payload?wait=true` con
  `{"payload": {"contiene_dosi": v}, "points": [...]}`, una chiamata per valore, a lotti). Nessuna
  chiamata a LM Studio, nessun upsert, nessuna cancellazione. Stampa: punti aggiornati, con dosi,
  senza dosi, punti prima e dopo (uguali).
- Codici di uscita invariati (0 / 2 / 3 / 4).

### Client Qdrant (`rag/qdrant.py`) e finto (`tests/finti_rag.py`)

- `crea_indice(nome, campo, schema="keyword")`; `imposta_payload(nome, payload, ids)`; `cerca` con
  il parametro `solo_dosi: bool = False`, che aggiunge `{"key": "contiene_dosi", "match": {"value":
  true}}` al `must` del filtro (insieme al capitolo, se c'è).
- Il Qdrant finto implementa `points/payload` (unisce il payload, 404 su ID assenti come il vero) e
  il filtro con più condizioni `must`.

### Ricerca (`rag/ricerca.py`)

- Opzione `--solo-dosi`; il filtro si applica durante la ricerca; risultati al massimo k, tutti con
  il campo vero. Il risultato mostra il campo («dosi: sì/no»).
- Se nessun punto ha il campo (collezione dell'esercizio 1 non ancora aggiornata), `--solo-dosi`
  non deve restituire «nessun risultato» in silenzio: messaggio che chiede `--solo-payload`,
  codice 4 (come per un capitolo inesistente).

### Valutazione

- `python -m rag.valutazione` invariato: dopo A la tabella deve risultare **uguale** a quella di
  partenza (cambia il payload, non i vettori); registrata in `docs/retrieval.md` («Dopo la modifica
  A») con due o tre ricerche con `--solo-dosi`, una combinata con `--capitolo`.

## Test (servizi spenti)

- Corpus: blocco con quantità → righe in `righe_dosi`; poesia rientrata → esclusa; dosi solo in
  prosa → `righe_dosi` vuoto; testo della ricetta invariato rispetto a prima; sul libro vero (se
  presente) numero di ricette con elenco e poesie escluse.
- Ingestion: campo nel payload vero/falso; chunk che contiene solo un pezzo di riga per l'overlap →
  falso; indice `bool` creato; `--solo-payload`: nessuna chiamata all'embedder, nessun upsert,
  vettori invariati, campo presente su tutti i punti, conteggio invariato; collezione assente,
  modello diverso, ID diversi → errore codice 4 senza scritture.
- Ricerca: con `--solo-dosi` tutti i risultati hanno il campo vero e sono al massimo k; combinato con
  `--capitolo` entrambe le condizioni; collezione senza il campo → messaggio e codice 4.
- `CORPUS_PROVA` riceve una poesia rientrata e una ricetta con dosi solo in prosa, se mancano.

## Prove reali (dell'utente, a fine fase, insieme a quelle dell'esercizio 1)

Dopo le prove dell'esercizio 1: `docker compose build ingestion`;
`docker compose run --rm ingestion python -m rag.ingestion --solo-payload` (punti uguali, nessun
embedding); ricerca con `--solo-dosi` e con `--solo-dosi --capitolo ...`; valutazione (tabella
uguale); ingestion completa di nuovo (punti uguali, campo presente).

## Documentazione e Git

- README (sezione RAG: campo, `--solo-payload`, `--solo-dosi`), `docs/retrieval.md` («Dopo la
  modifica A»), `.env.example` invariato.
- Commit Conventional Commits in italiano; merge: prima `feat/rag-ingestion` in `dev`, poi
  `feat/rag-metadati`, solo con conferma; nessun push.

## Lasciato al builder

- Nome esatto della funzione che riconosce un elenco di ingredienti e la forma dei messaggi.
- Dimensione dei lotti di `imposta_payload`.
- Come `--solo-dosi` riconosce «nessun punto ha il campo» (per esempio un conteggio con filtro
  sul campo assente).
