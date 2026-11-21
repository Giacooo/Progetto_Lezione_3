# Retrieval sul libro di Artusi (lezione 7)

Risultati della pipeline di ingestion e ricerca (pacchetto `rag/`) sul libro di Pellegrino Artusi
«La scienza in cucina e l'arte di mangiar bene» (Project Gutenberg n. 59047). Solo recupero:
nessuna risposta generata. Comandi e diagnosi nel README, sezione «RAG: ingestion e ricerca».

> **Stato:** i numeri delle prove reali (ingestion, valutazione, query) sono ancora da riportare:
> le prove con Docker non sono state ancora eseguite. Le parti segnate «_da completare_» si
> riempiono con gli output veri.

## Configurazione usata

| Voce | Valore |
|---|---|
| Modello di embedding | `text-embedding-nomic-embed-text-v1.5` (LM Studio, vettori da 768) |
| Strategia di chunking | `paragrafi` (paragrafi interi, finestra solo per i paragrafi troppo lunghi) |
| Dimensione / overlap | 1200 / 200 caratteri |
| Testo indicizzato | esercizio 1 e modifica A: il chunk; dalla modifica B: `Ricetta:` titolo, `Capitolo:` capitolo, riga vuota, chunk |
| Distanza | coseno |
| k della valutazione | 5 (ricerca: predefinito 5, massimo 20) |
| Soglia sullo score | nessuna |
| Collezione | `ricette` (Qdrant `v1.20.2`, volume `dati-qdrant`) |

- **Niente prefissi del modello nomic** (`search_document:` / `search_query:`): il PDF chiede la
  stessa configurazione per documenti e domande e i suoi risultati di pagina 22 sono il riferimento.
  Il testo dei chunk e delle domande va al modello così com'è.
- Modello e dimensione dei vettori sono registrati nei metadati della collezione: con un altro
  modello ingestion e ricerca si fermano (codice 4).

## Le due ingestion

_Da completare con l'output di `docker compose run --rm ingestion`, eseguito due volte._

| | Ricette lette | Chunk prodotti | Punti prima | Punti eliminati | Punti dopo |
|---|---|---|---|---|---|
| Prima ingestion | | | | | |
| Seconda ingestion | | | | | |

Atteso: 790 ricette; stesso numero di punti dopo le due ingestion (gli ID sono stabili, la seconda
sostituisce i punti invece di duplicarli).

## Valutazione di partenza (esercizio 1)

_Da completare con la tabella di `docker compose run --rm ingestion python -m rag.valutazione`._

Domande in `rag/domande.json`: le sei del PDF (pagine 21–22) e cinque proprie scritte senza copiare
le parole del testo; due non hanno risposta nel libro (tiramisù, carbonara).

## Due query commentate

_Da completare._

1. `"Come si frigge il pollo?" --capitolo Fritti --k 3` (con filtro per capitolo).
2. Una domanda senza filtro, scelta tra quelle della valutazione.

## Nota sui test

I test automatici non usano né LM Studio né il server Qdrant: un Qdrant finto in memoria, scritto
nel progetto su `httpx.MockTransport` (`tests/finti_rag.py`), non è la modalità in memoria della
libreria ufficiale `qdrant-client`, che su questo PC non si importa (Smart App Control blocca una DLL
di `numpy`). L'embedder finto è deterministico: testi con parole in comune danno vettori vicini.

## Dopo la modifica A (metadati)

Campo `contiene_dosi` nel payload: vero se il chunk contiene almeno una riga intera di un elenco di
ingredienti (blocco di righe rientrate con almeno una quantità). Indice `bool` sul payload. Il
testo dei chunk non cambia, quindi gli embedding restano quelli dell'esercizio 1.

Sulla copia di prova del libro: 347 ricette con un elenco di ingredienti (2152 righe); esclusi 16
blocchi rientrati (tutti versi, lettere o titoletti come «Prima:», «Seconda:») e le 13 didascalie
delle figure (`[Illustrazione: … Ø 64 mm …]`), che hanno cifre ma non sono ingredienti.

Nota: una riga intera di ingredienti ripetuta dall'overlap rende vero anche il chunk successivo
(sulla copia di prova 54 chunk su circa 415 con il campo vero): con `--solo-dosi` questi chunk
«di coda» possono occupare posti tra i k risultati.

_Da completare con gli output delle prove reali:_

- `docker compose run --rm ingestion python -m rag.ingestion --solo-payload`: punti aggiornati,
  con dosi, senza dosi, punti prima e dopo (uguali, nessun embedding ricalcolato).
- Valutazione dopo A (attesa identica a quella di partenza: cambia il payload, non i vettori).
- Ricerche con il filtro:
  1. `"Quanta farina serve per 400 grammi di patate negli gnocchi?" --solo-dosi`
  2. `"Quanta farina serve per 400 grammi di patate negli gnocchi?" --solo-dosi --capitolo "Minestre asciutte e di magro"`
  3. stessa domanda senza filtro, per confronto.

## Dopo la modifica B (chunking)

Ogni chunk va al modello di embedding preceduto da titolo e capitolo della ricetta. Esempio (ricetta
«Pollo fritto», capitolo «Fritti»):

```
Ricetta: Pollo fritto
Capitolo: Fritti

<testo originale del chunk>
```

**Perché:** un chunk «di mezzo» di una ricetta lunga spesso non nomina il piatto, e il suo vettore
non sa di che ricetta parla. Con l'intestazione ogni chunk porta con sé il suo contesto. Il numero
della ricetta non c'è: non aiuta la ricerca per significato.

**Che cosa non cambia:** il payload `testo` resta il chunk originale (la ricerca mostra il testo
senza intestazione), come gli ID dei punti (dipendono da ricetta e posizione, non dal testo), la
dimensione e l'overlap dei chunk, il modello e le domande della valutazione.

_Da completare con gli output delle prove reali:_

- Ingestion completa sulla collezione costruita prima di B (`docker compose run --rm ingestion`):

  | Ricette lette | Chunk prodotti | Punti prima | Punti eliminati | Punti dopo |
  |---|---|---|---|---|
  | | | | | |

  Atteso: punti prima = punti dopo, eliminati 0 (vettori sostituiti sugli stessi punti, collezione
  non ricreata).

- Valutazione «prima» (tabella dopo la modifica A) e «dopo» (dopo l'ingestion completa su B), e
  confronto per domanda. La tabella «prima» va misurata **prima** dell'ingestion su B (dal branch
  `feat/rag-metadati`): l'ingestion B sostituisce i vettori.

  | # | Domanda | Posizione prima (A) | Posizione dopo (B) | Score fonte prima | Score fonte dopo |
  |---|---|---|---|---|---|

  Fonte attesa trovata: prima _X_/9, dopo _Y_/9 (le due domande senza risposta nel libro non
  contano).

  Commento: _da completare_.

- Ricerca di confronto `"Come si frigge il pollo?" --k 3`, prima e dopo: _da completare_.
