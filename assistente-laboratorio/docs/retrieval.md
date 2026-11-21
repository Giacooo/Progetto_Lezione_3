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

Regola dell'overlap (corretta il 2026-11-21): una riga di ingredienti conta solo nel chunk dove è
**nuova**, non in quello successivo dove torna ripetuta dall'overlap. Prima questi chunk «di coda»
avevano il campo vero e con `--solo-dosi` potevano occupare posti tra i k risultati. Sulla copia di
prova (1145 chunk): chunk con il campo vero da 406 a 355; le ricette con almeno un chunk con dosi
restano 347 su 347.

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

## Estensioni (facoltative)

Il PDF (pag. 29) propone due estensioni: un **confronto tra strategie di chunking sulle stesse
domande** e **un modello di embedding multilingue in una seconda collezione**. Non serve codice
nuovo: strategia, modello e collezione sono variabili della configurazione, e con
`docker compose run --rm -e NOME=valore ...` valgono per una sola esecuzione, senza toccare il
`.env`. Le domande sono sempre quelle di `rag/domande.json`.

La **base di confronto** è la tabella «dopo B» (sopra). Ogni estensione cambia **una sola cosa**
rispetto alla base, in una collezione a parte:

| Collezione | Strategia | Modello | Cosa cambia |
|---|---|---|---|
| `ricette` (base) | paragrafi 1200/200 | `text-embedding-nomic-embed-text-v1.5` | — |
| `ricette_finestra` | finestra 1200/200 | `text-embedding-nomic-embed-text-v1.5` | solo il chunking |
| `ricette_bge_m3` | paragrafi 1200/200 | `text-embedding-bge-m3` | solo il modello |

Le prove si fanno sul branch `feat/rag-estensioni`, dopo quelle della modifica B, con l'immagine
ricostruita (`docker compose build ingestion`).

> **Attenzione.**
>
> - **Mai** un'ingestion con un'altra strategia **senza** `-e QDRANT_COLLEZIONE=...`: la
>   collezione registra il modello ma non la strategia, quindi `ricette` verrebbe riscritta con i
>   chunk nuovi **senza nessun errore** e la base di confronto andrebbe persa.
> - Anche **ricerca e valutazione** su `ricette_bge_m3` vogliono
>   `-e EMBEDDING_MODELLO=text-embedding-bge-m3`: le domande vanno trasformate in vettori con lo
>   stesso modello dei documenti. Senza, il programma si ferma con il codice 4 («cambio
>   bloccato»): è l'esito atteso, la prova che il blocco funziona.
> - Dal PC le variabili `$env:...` restano attive in quella finestra di PowerShell: finite le
>   prove, `Remove-Item Env:QDRANT_COLLEZIONE, Env:CHUNK_STRATEGIA, Env:EMBEDDING_MODELLO`
>   (oppure chiudere la finestra), altrimenti i comandi successivi usano la collezione sbagliata.

### Confronto tra strategie di chunking

`paragrafi` (la base) mette insieme paragrafi interi della ricetta fino a 1200 caratteri (un
elenco di ingredienti non si spezza); `finestra` taglia a lunghezza fissa (1200 caratteri, al
massimo 200 ripetuti), tra una parola e l'altra ma anche a metà frase o a metà di un elenco.
Dimensione e overlap restano uguali: cambia solo il modo di tagliare.

Con Docker (modello nomic caricato in LM Studio, `docker compose up -d qdrant`):

```powershell
docker compose run --rm -e QDRANT_COLLEZIONE=ricette_finestra -e CHUNK_STRATEGIA=finestra ingestion
docker compose run --rm -e QDRANT_COLLEZIONE=ricette_finestra -e CHUNK_STRATEGIA=finestra ingestion python -m rag.valutazione
```

Dal PC:

```powershell
$env:QDRANT_COLLEZIONE="ricette_finestra"; $env:CHUNK_STRATEGIA="finestra"
.\.venv\Scripts\python.exe -m rag.ingestion
.\.venv\Scripts\python.exe -m rag.valutazione
Remove-Item Env:QDRANT_COLLEZIONE, Env:CHUNK_STRATEGIA
```

_Da completare con gli output delle prove reali:_

- Ingestion (nell'uscita la riga `chunking: finestra, dimensione 1200, overlap 200`):

  | Collezione | Ricette lette | Chunk prodotti | Punti dopo |
  |---|---|---|---|
  | `ricette` (dopo B) | | | |
  | `ricette_finestra` | | | |

- Valutazione per domanda (k = 5):

  | # | Domanda | Posizione paragrafi (B) | Posizione finestra | Score fonte paragrafi | Score fonte finestra |
  |---|---|---|---|---|---|

  Fonte attesa trovata: paragrafi _X_/9, finestra _Y_/9.

  Commento: _da completare_.

### Modello multilingue (seconda collezione)

`text-embedding-nomic-embed-text-v1.5` è addestrato soprattutto su testi inglesi;
`text-embedding-bge-m3` è un modello **multilingue** (anche italiano). Produce vettori da 1024
numeri invece di 768: per questo deve stare in una **seconda collezione**, e il cambio bloccato
impedisce di scriverlo per sbaglio in `ricette`. Strategia e dimensione dei chunk restano quelle
della base.

1. In LM Studio caricare anche `text-embedding-bge-m3` (l'id è quello di `GET /v1/models`).
2. Con Docker:

   ```powershell
   docker compose run --rm -e QDRANT_COLLEZIONE=ricette_bge_m3 -e EMBEDDING_MODELLO=text-embedding-bge-m3 ingestion
   docker compose run --rm -e QDRANT_COLLEZIONE=ricette_bge_m3 -e EMBEDDING_MODELLO=text-embedding-bge-m3 ingestion python -m rag.valutazione
   ```

   Dal PC:

   ```powershell
   $env:QDRANT_COLLEZIONE="ricette_bge_m3"; $env:EMBEDDING_MODELLO="text-embedding-bge-m3"
   .\.venv\Scripts\python.exe -m rag.ingestion
   .\.venv\Scripts\python.exe -m rag.valutazione
   Remove-Item Env:QDRANT_COLLEZIONE, Env:EMBEDDING_MODELLO
   ```

   Nel log della prima ingestion: `creata la collezione ricette_bge_m3 (coseno, dimensione 1024,
   modello text-embedding-bge-m3)`.
3. Prova del blocco (deve fallire con il codice 4, «cambio bloccato»):

   ```powershell
   docker compose run --rm -e QDRANT_COLLEZIONE=ricette_bge_m3 ingestion python -m rag.valutazione
   $LASTEXITCODE
   ```

_Da completare con gli output delle prove reali:_

- Ingestion:

  | Collezione | Modello | Dimensione vettori | Chunk prodotti | Punti dopo |
  |---|---|---|---|---|
  | `ricette` (dopo B) | nomic | 768 | | |
  | `ricette_bge_m3` | bge-m3 | | | |

- Valutazione per domanda (k = 5):

  | # | Domanda | Posizione nomic (B) | Posizione bge-m3 | Score fonte nomic | Score fonte bge-m3 |
  |---|---|---|---|---|---|

  Fonte attesa trovata: nomic _X_/9, bge-m3 _Y_/9. Gli score dei due modelli **non sono
  confrontabili tra loro** (scale diverse): si confrontano le posizioni.

- Prova del blocco: codice di uscita _da completare_ (atteso 4).

  Commento: _da completare_.

### Riepilogo delle estensioni

| Collezione | Strategia | Modello | Punti | Fonte attesa trovata |
|---|---|---|---|---|
| `ricette` | paragrafi 1200/200 | nomic | | /9 |
| `ricette_finestra` | finestra 1200/200 | nomic | | /9 |
| `ricette_bge_m3` | paragrafi 1200/200 | bge-m3 | | /9 |

Ricerca di confronto `"Come si frigge il pollo?" --k 3` sulle tre collezioni (per le due nuove
aggiungere le stesse `-e` dei comandi sopra, per esempio
`docker compose run --rm -e QDRANT_COLLEZIONE=ricette_finestra -e CHUNK_STRATEGIA=finestra ingestion python -m rag.ricerca "Come si frigge il pollo?" --k 3`):
_da completare_.

Commento finale (quale configurazione funziona meglio su queste domande e perché): _da
completare_.
