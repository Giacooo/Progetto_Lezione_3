# Lezione 7, modifica B — Titolo e capitolo nel testo indicizzato (specifica)

Parte dalla modifica A (specifica `2026-11-17-rag-metadati-design.md`, branch `feat/rag-metadati`).
Branch `feat/rag-chunking-titolo`, creato da `feat/rag-metadati` perché esercizio 1 e modifica A non
sono ancora uniti in `dev` (mancano le prove reali, rimandate dall'utente alla fine).

## Intento

Un chunk «di mezzo» di una ricetta lunga spesso non nomina il piatto: il suo vettore non sa di che
ricetta parla. Mettendo titolo e capitolo davanti al testo che va al modello di embedding, ogni
chunk porta con sé il suo contesto; chi legge i risultati vede comunque il testo originale.

## Requisiti del PDF (pag. 28, alla lettera)

- Ogni chunk viene indicizzato preceduto da titolo e capitolo della ricetta.
- La ricerca restituisce il testo originale.
- Un test verifica il testo passato all'embedder.
- L'ingestion ricalcola tutti i chunk senza ricreare la collezione, e i punti non aumentano.
- Valutazione prima e dopo, confronto registrato. Test e commit Conventional Commits (pag. 29).

## Obiettivi, non obiettivi, anti-obiettivi

- **Obiettivi:** testo indicizzato = intestazione + chunk; payload `testo` invariato (originale);
  ingestion completa che sostituisce i vettori degli stessi punti; confronto della valutazione in
  `docs/retrieval.md`.
- **Non obiettivi:** cambiare dimensione, overlap o strategia di chunking; nuove domande di
  valutazione; un interruttore per spegnere l'intestazione; estensioni del PDF (confronto di
  strategie, modello multilingue).
- **Anti-obiettivi:** ricreare la collezione o aumentare i punti; mostrare l'intestazione nei
  risultati della ricerca; far scattare il «cambio bloccato» per un testo indicizzato diverso con lo
  stesso modello; rompere `--solo-payload` della modifica A.

## Approcci considerati

1. **Scelto:** intestazione solo nel testo passato all'embedder; il payload resta quello della
   modifica A. Nessun dato in più, la ricerca non cambia.
2. Salvare anche il testo indicizzato nel payload (`testo_indicizzato`): scartato, è ricavabile da
   titolo, capitolo e testo, e occupa spazio senza servire alla ricerca.
3. Interruttore nel `.env` per accendere/spegnere l'intestazione: scartato, il PDF dice «ogni chunk»
   e la valutazione «prima» si misura dal branch `feat/rag-metadati`.

L'utente ha approvato l'approccio 1 e il formato dell'intestazione (2026-11-17).

## Design

- **Formato** (funzione `testo_da_indicizzare(titolo, capitolo, testo)` in `rag/ingestion.py`):

  ```
  Ricetta: <titolo>
  Capitolo: <capitolo>

  <testo originale del chunk>
  ```

  Titolo e capitolo come nel payload (es. `Pollo fritto`, `Fritti`). Niente numero della ricetta: il
  PDF chiede titolo e capitolo, e il numero non aiuta la ricerca per significato.
- **Ingestion completa** (`python -m rag.ingestion`): l'embedder riceve `testo_da_indicizzare(...)`
  per ogni chunk; l'upsert usa gli stessi ID stabili (dipendono da ricetta e posizione, non dal
  testo), quindi su una collezione esistente i vettori vengono sostituiti, la collezione non viene
  ricreata e il numero di punti resta uguale (stampato come «punti prima» / «punti dopo»). Il
  controllo del modello resta com'è: stesso modello, nessun blocco.
- **Payload:** invariato (`testo` = chunk originale), quindi la ricerca restituisce il testo
  originale senza modifiche al codice di `rag/ricerca.py`, e `--solo-payload` continua a confrontare
  il testo originale salvato in Qdrant.
- **Log/uscita dell'ingestion:** una riga che dice che il testo indicizzato ha davanti titolo e
  capitolo (per riconoscere dall'output la versione usata).
- **Valutazione:** «prima» = tabella dopo la modifica A (stessi vettori dell'esercizio 1); «dopo» =
  tabella dopo l'ingestion completa sul branch B. In `docs/retrieval.md`, sezione «Dopo la modifica
  B»: le due tabelle e un confronto per domanda (posizione e score della fonte, prima e dopo), con
  un commento. I numeri si riempiono con le prove reali finali.

## Test (TDD, servizi spenti)

- Il testo passato all'embedder finto (che registra le chiamate) è esattamente intestazione + chunk
  per ogni punto, nell'ordine.
- Il payload `testo` e il testo dei risultati di `rag.ricerca.cerca` non contengono l'intestazione.
- Ingestion su una collezione già piena (riempita con vettori «vecchi»): nessuna creazione della
  collezione, stessi ID, punti prima = punti dopo, vettori cambiati.
- `--solo-payload` dopo l'ingestion B: ancora applicabile (nessun `PayloadNonAggiornabile`).
- Serie completa una volta a fine fase; revisione indipendente finale.

## Lasciato a chi implementa

Nome esatto della riga di log, struttura dei test, testo dei commenti nel README e in
`docs/retrieval.md`.
