# Retrieval sul libro di Artusi (lezione 7)

Risultati della pipeline di ingestion e ricerca (pacchetto `rag/`) sul libro di Pellegrino Artusi
«La scienza in cucina e l'arte di mangiar bene» (Project Gutenberg n. 59047). Solo recupero:
nessuna risposta generata. Comandi e diagnosi nel README, sezione «RAG: ingestion e ricerca».

> **Stato:** prove reali eseguite il 2026-11-21 con Docker (Qdrant `v1.20.2`, LM Studio sul PC),
> passando dai branch in ordine: esercizio 1 (`feat/rag-ingestion`), modifica A
> (`feat/rag-metadati`), modifica B con le correzioni (`fix/rag-minori`), estensioni
> (`feat/rag-estensioni`). I numeri sotto sono gli output veri.

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

`docker compose run --rm ingestion`, eseguito due volte di fila (branch `feat/rag-ingestion`):

| | Ricette lette | Chunk prodotti | Punti prima | Punti eliminati | Punti dopo |
|---|---|---|---|---|---|
| Prima ingestion | 790 | 1145 | 0 | 0 | 1145 |
| Seconda ingestion | 790 | 1145 | 1145 | 0 | 1145 |

Stesso numero di punti dopo le due ingestion: gli ID sono stabili, la seconda sostituisce i punti
invece di duplicarli. Altre verifiche fatte nella stessa prova:

- dopo `docker compose restart qdrant` la stessa ricerca dà gli stessi risultati (la collezione
  sta nel volume);
- `docker compose run --rm -e EMBEDDING_MODELLO=text-embedding-bge-m3 ingestion` si ferma con
  «la collezione è stata creata con il modello 'text-embedding-nomic-embed-text-v1.5', ma
  EMBEDDING_MODELLO è 'text-embedding-bge-m3': cambio bloccato» e codice di uscita 4; la collezione
  resta di 1145 punti.

## Valutazione di partenza (esercizio 1)

`docker compose run --rm ingestion python -m rag.valutazione` (modello nomic, collezione
`ricette`, paragrafi 1200/200, k = 5):

| # | Domanda | Fonte attesa | Posizione | Score fonte | Score migliore |
|---|---|---|---|---|---|
| 1 | Quanta farina serve per 400 grammi di patate negli gnocchi? | N. 89 | 1 | 0.7712 | 0.7712 |
| 2 | Quanti cappelletti bastano a un mangiatore moderato? | N. 7 | 1 | 0.7750 | 0.7750 |
| 3 | Che vino si usa per il pollo alla cacciatora? | N. 208 | assente | — | 0.7184 |
| 4 | Perché gli gnocchi possono sciogliersi nell'acqua? | N. 89 | 1 | 0.7548 | 0.7548 |
| 5 | Come si chiama il cacciucco sulle coste dell'Adriatico? | N. 455, 456 | 1 | 0.7937 | 0.7937 |
| 6 | Qual è la ricetta del tiramisù? | nessuna | — | — | 0.7145 |
| 7 | Con quale spezia si colora il riso tipico della Lombardia? | N. 78, 79, 80 | assente | — | 0.7388 |
| 8 | Come preparare in estate una scorta di passata rossa da usare tutto l'anno? | N. 732 | assente | — | 0.7357 |
| 9 | Da quale paese arriva la bevanda scura che si beve per svegliarsi? | N. 776 | assente | — | 0.7238 |
| 10 | Quale vino dolce si aggiunge alla crema spumosa fatta con i tuorli? | N. 722 | assente | — | 0.7592 |
| 11 | Qual è la ricetta della carbonara? | nessuna | — | — | 0.7274 |

Fonte attesa trovata in **4 casi su 9**.

Domande in `rag/domande.json`: le sei del PDF (pagine 21–22) e cinque proprie scritte senza copiare
le parole del testo; due non hanno risposta nel libro (tiramisù, carbonara).

Che cosa si vede:

- le domande che usano **le parole del libro** (gnocchi, cappelletti, cacciucco) trovano la ricetta
  al primo posto;
- falliscono le domande **parafrasate** (7–10: «spezia» e «riso della Lombardia» invece di
  zafferano e risotto alla milanese, «bevanda scura» invece di caffè) e la 3, dove la parola
  decisiva («cacciatora») sta solo nel **titolo**, che all'esercizio 1 non è nel testo indicizzato;
- le domande senza risposta (tiramisù 0.7145, carbonara 0.7274) hanno lo score migliore **più alto**
  di alcune domande con risposta trovata: nessuna soglia sullo score separa «trovato» da «non c'è».

## Due query commentate

1. `"Come si frigge il pollo?" --capitolo Fritti --k 3` (con filtro per capitolo):

   | # | Score | Ricetta | Capitolo | Chunk |
   |---|---|---|---|---|
   | 1 | 0.7294 | N. 209 Pollo fritto coi pomodori | Fritti | 0 |
   | 2 | 0.7055 | N. 176 Fritto alla romana I | Fritti | 1 |
   | 3 | 0.7020 | N. 216 Testicciuola d'agnello | Fritti | 0 |

   Il filtro funziona: tutti i risultati sono del capitolo «Fritti». Il primo è la risposta giusta
   (il pollo «si taglia a piccoli pezzi, si mette in padella ... con sufficiente quantità di
   lardo»). Il secondo e il terzo parlano di friggere ma non di pollo: il chunk 1 del fritto alla
   romana è un pezzo «di mezzo» che non nomina il piatto («Friggetelo nell'olio o nel lardo»), e
   viene scelto solo per il verbo. Il «Pollo alla cacciatora» (N. 208), anch'esso nei Fritti, non
   compare: il suo testo dice «pollastro» e «friggetelo», ma «pollo» c'è solo nel titolo.
   Ogni risultato si riconduce a ricetta, capitolo e posizione del chunk (criterio di
   completamento del PDF).

2. `"Che vino si usa per il pollo alla cacciatora?" --k 5` (senza filtro, domanda 3 della
   valutazione):

   | # | Score | Ricetta | Capitolo | Chunk |
   |---|---|---|---|---|
   | 1 | 0.7184 | N. 264 Pollo colla marsala | Umidi | 0 |
   | 2 | 0.7160 | N. 209 Pollo fritto coi pomodori | Fritti | 0 |
   | 3 | 0.7122 | N. 455 Cacciucco I | Piatti di pesce | 0 |
   | 4 | 0.7054 | N. 624 Tortelli di ceci | Pasticceria | 0 |
   | 5 | 0.6984 | N. 270 Germano ossia anatra selvatica I | Umidi | 1 |

   La ricetta giusta (N. 208, «mezzo bicchiere di San Giovese od altro vino rosso») manca. Arrivano
   ricette con **pollo + vino** (marsala), con pollo, e perfino il cacciucco, probabilmente per la
   somiglianza tra «cacciatora» e «cacciucco». È il caso tipico che la modifica B vuole correggere:
   la parola che identifica la ricetta è nel titolo, non nel testo del chunk (dopo B la N. 208 sale
   al primo posto, vedi sotto).

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

Prove reali (branch `feat/rag-metadati`, regola vecchia dell'overlap):

- `docker compose run --rm ingestion python -m rag.ingestion --solo-payload`:

  | Punti aggiornati | Con dosi | Senza dosi | Punti prima | Punti dopo |
  |---|---|---|---|---|
  | 1145 | 406 | 739 | 1145 | 1145 |

  Nessun embedding ricalcolato (pochi secondi, nessuna chiamata a LM Studio), stessi punti.
- Valutazione dopo A: **identica** a quella di partenza, riga per riga e score per score (4 casi su
  9): cambia il payload, non i vettori.
- Ricerche con il filtro, domanda `"Quanta farina serve per 400 grammi di patate negli gnocchi?"`:

  | # | `--solo-dosi` | `--solo-dosi --capitolo "Minestre asciutte e di magro"` | senza filtro |
  |---|---|---|---|
  | 1 | N. 89 Gnocchi di patate (0.7712) | N. 89 Gnocchi di patate (0.7712) | N. 89 Gnocchi di patate (0.7712) |
  | 2 | N. 158 Pasta per pasticci diacci di carne (0.7546) | N. 77 Risotto coi pomodori (0.7170) | N. 158 (0.7546) |
  | 3 | N. 156 Pastella per le fritture (0.7463) | N. 101 Spaghetti coi naselli (0.7136) | N. 156 (0.7463) |
  | 4 | N. 229 Donzelline aromatiche (0.7453) | N. 106 Spaghetti con la balsamella (0.7116) | N. 229 (0.7453) |
  | 5 | N. 561 Kugelhupf (0.7427) | N. 95 Pappardelle colla lepre I, chunk 1 (0.7055) | N. 561 (0.7427) |

  Tutti i risultati delle due ricerche filtrate hanno `dosi: sì`, e con `--capitolo` sono tutti
  del capitolo indicato: i due filtri si combinano. Il primo posto è sempre la risposta giusta
  («Patate grosse e gialle, grammi 400. Farina di grano, grammi 150.»).

  Commento: per questa domanda **il filtro sulle dosi da solo non cambia niente**, perché senza
  filtro i primi 5 sono già tutti chunk con un elenco di ingredienti (la domanda parla di grammi e
  farina, e gli elenchi che contengono «Farina, grammi …» sono i testi più vicini). Il filtro serve
  quando la domanda è sulle quantità ma il testo narrativo della ricetta è più vicino
  dell'elenco; combinato con il capitolo restringe davvero i candidati (risultati 2–5 diversi).

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

Prove reali (branch `fix/rag-minori`: modifica B più le correzioni dei Minor):

- Ingestion completa sulla collezione costruita prima di B (`docker compose run --rm ingestion`;
  nell'uscita la riga `testo indicizzato: titolo e capitolo + chunk (payload con il testo
  originale)`):

  | Ricette lette | Chunk prodotti | Punti prima | Punti eliminati | Punti dopo |
  |---|---|---|---|---|
  | 790 | 1145 | 1145 | 0 | 1145 |

  Vettori sostituiti sugli stessi punti, collezione non ricreata, nessun «cambio bloccato».
- `--solo-payload` con la regola nuova dell'overlap: 1145 punti aggiornati, **355 con dosi** (406
  con la regola vecchia), 790 senza, punti prima = dopo = 1145.
- Valutazione «prima» (dopo A, misurata su `feat/rag-metadati` prima dell'ingestion B) e «dopo»:

  | # | Domanda | Posizione prima (A) | Posizione dopo (B) | Score fonte prima | Score fonte dopo |
  |---|---|---|---|---|---|
  | 1 | Quanta farina serve per 400 grammi di patate negli gnocchi? | 1 | 1 | 0.7712 | 0.7908 |
  | 2 | Quanti cappelletti bastano a un mangiatore moderato? | 1 | 1 | 0.7750 | 0.7665 |
  | 3 | Che vino si usa per il pollo alla cacciatora? | assente | **1** | — | 0.7407 |
  | 4 | Perché gli gnocchi possono sciogliersi nell'acqua? | 1 | 1 | 0.7548 | 0.7885 |
  | 5 | Come si chiama il cacciucco sulle coste dell'Adriatico? | 1 | 1 | 0.7937 | 0.7767 |
  | 7 | Con quale spezia si colora il riso tipico della Lombardia? | assente | assente | — | — |
  | 8 | Come preparare in estate una scorta di passata rossa da usare tutto l'anno? | assente | assente | — | — |
  | 9 | Da quale paese arriva la bevanda scura che si beve per svegliarsi? | assente | assente | — | — |
  | 10 | Quale vino dolce si aggiunge alla crema spumosa fatta con i tuorli? | assente | assente | — | — |

  Fonte attesa trovata: prima **4/9**, dopo **5/9** (le due domande senza risposta nel libro non
  contano). Score migliore delle domande senza risposta: tiramisù 0.7145 → 0.7703, carbonara
  0.7274 → 0.7706.

  Commento: B recupera proprio il caso previsto, la domanda 3: «cacciatora» compare solo nel
  titolo, e con l'intestazione il chunk della N. 208 sale dal fuori classifica al primo posto. Le
  domande parafrasate (7–10) restano assenti: l'intestazione aggiunge il nome del piatto, ma la
  domanda non lo usa («spezia», «bevanda scura»), quindi non aiuta. Effetto collaterale:
  l'intestazione rende tutti i chunk più «da ricettario», e lo score delle domande senza risposta
  sale (circa 0.77, più di alcune risposte giuste): una soglia sullo score è ancora meno
  praticabile.
- Ricerca di confronto `"Come si frigge il pollo?" --k 3` (dopo B, **senza** filtro):

  | # | Score | Ricetta | Capitolo | Chunk |
  |---|---|---|---|---|
  | 1 | 0.7550 | N. 209 Pollo fritto coi pomodori | Fritti | 0 |
  | 2 | 0.7201 | N. 264 Pollo colla marsala | Umidi | 0 |
  | 3 | 0.7181 | N. 208 Pollo alla cacciatora | Fritti | 0 |

  Prima di B la stessa domanda era stata provata con `--capitolo Fritti` (prima query commentata):
  i risultati 2 e 3 erano fritti senza pollo. Dopo B, anche senza filtro, i tre risultati sono
  tutti **ricette di pollo**: il titolo nel testo indicizzato porta il vettore verso «pollo». Il
  secondo però è un umido (pollo colla marsala): il modello pesa più «pollo» che «friggere». I
  testi mostrati non iniziano con `Ricetta:`: la ricerca restituisce il testo originale del
  payload. Dal PC (`.\.venv\Scripts\python.exe -m rag.ricerca "Come si frigge il pollo?"
  --capitolo Fritti --k 3`) dopo B: N. 209 (0.7550), N. 208 (0.7181), N. 206 Pollo dorato II
  (0.7046), tutti pollo fritto.

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

Prove reali (2026-11-21):

- Ingestion (nell'uscita `collezione: ricette_finestra`, `chunking: finestra, dimensione 1200,
  overlap 200`, `punti prima: 0`):

  | Collezione | Ricette lette | Chunk prodotti | Punti dopo |
  |---|---|---|---|
  | `ricette` (dopo B) | 790 | 1145 | 1145 |
  | `ricette_finestra` | 790 | 1086 | 1086 |

  Controllo: subito dopo, la valutazione su `ricette` senza `-e` ha dato di nuovo la tabella «dopo
  B», identica: la base non è stata toccata.
- Valutazione per domanda (k = 5):

  | # | Domanda | Posizione paragrafi (B) | Posizione finestra | Score fonte paragrafi | Score fonte finestra |
  |---|---|---|---|---|---|
  | 1 | Quanta farina serve per 400 grammi di patate negli gnocchi? | 1 | 1 | 0.7908 | 0.7903 |
  | 2 | Quanti cappelletti bastano a un mangiatore moderato? | 1 | **2** | 0.7665 | 0.7495 |
  | 3 | Che vino si usa per il pollo alla cacciatora? | 1 | 1 | 0.7407 | 0.7407 |
  | 4 | Perché gli gnocchi possono sciogliersi nell'acqua? | 1 | 1 | 0.7885 | 0.7667 |
  | 5 | Come si chiama il cacciucco sulle coste dell'Adriatico? | 1 | 1 | 0.7767 | 0.7738 |
  | 7 | Con quale spezia si colora il riso tipico della Lombardia? | assente | assente | — | — |
  | 8 | Come preparare in estate una scorta di passata rossa da usare tutto l'anno? | assente | assente | — | — |
  | 9 | Da quale paese arriva la bevanda scura che si beve per svegliarsi? | assente | assente | — | — |
  | 10 | Quale vino dolce si aggiunge alla crema spumosa fatta con i tuorli? | assente | assente | — | — |

  Fonte attesa trovata: paragrafi **5/9**, finestra **5/9**.

  Commento: sulle stesse domande le due strategie trovano le stesse fonti; `finestra` perde solo
  il primo posto della domanda 2 (cappelletti, al secondo posto) e ha score un po' più bassi sulle
  ricette lunghe (gnocchi, domanda 4). Le ricette fino a 1200 caratteri danno **lo stesso chunk**
  con tutte e due le strategie (per esempio la ricerca sul pollo fritto dà risultati e score
  identici sulle due collezioni): le differenze nascono solo nelle ricette lunghe. `finestra`
  produce meno chunk (1086 contro 1145) perché riempie ogni pezzo fino a 1200 caratteri, mentre
  `paragrafi` si ferma alla fine di un paragrafo; in cambio taglia a metà frase o a metà di un
  elenco di ingredienti. Si resta su `paragrafi`: risultati uguali o migliori, e gli elenchi di
  ingredienti interi servono al campo `contiene_dosi` della modifica A.

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
   modello text-embedding-bge-m3)` (con Docker la riga può essere coperta dall'avanzamento; in
   alternativa `(Invoke-RestMethod http://localhost:6333/collections/ricette_bge_m3).result.config`
   mostra `size` 1024 e il modello nei metadati).
3. Prova del blocco (deve fallire con il codice 4, «cambio bloccato»):

   ```powershell
   docker compose run --rm -e QDRANT_COLLEZIONE=ricette_bge_m3 ingestion python -m rag.valutazione
   $LASTEXITCODE
   ```

Prove reali (2026-11-21):

- Ingestion (`collezione: ricette_bge_m3`, `punti prima: 0`). La riga di log «creata la
  collezione» non si è vista a schermo (coperta dall'avanzamento di Docker); dimensione e modello
  sono stati verificati leggendo la collezione da Qdrant (`GET /collections/ricette_bge_m3`:
  `size` 1024, metadati `{"embedding_modello": "text-embedding-bge-m3", "embedding_dimensione":
  1024}`):

  | Collezione | Modello | Dimensione vettori | Chunk prodotti | Punti dopo |
  |---|---|---|---|---|
  | `ricette` (dopo B) | nomic | 768 | 1145 | 1145 |
  | `ricette_bge_m3` | bge-m3 | 1024 | 1145 | 1145 |

- Valutazione per domanda (k = 5):

  | # | Domanda | Posizione nomic (B) | Posizione bge-m3 | Score fonte nomic | Score fonte bge-m3 |
  |---|---|---|---|---|---|
  | 1 | Quanta farina serve per 400 grammi di patate negli gnocchi? | 1 | 1 | 0.7908 | 0.7206 |
  | 2 | Quanti cappelletti bastano a un mangiatore moderato? | 1 | 1 | 0.7665 | 0.5768 |
  | 3 | Che vino si usa per il pollo alla cacciatora? | 1 | 1 | 0.7407 | 0.6266 |
  | 4 | Perché gli gnocchi possono sciogliersi nell'acqua? | 1 | 1 | 0.7885 | 0.6286 |
  | 5 | Come si chiama il cacciucco sulle coste dell'Adriatico? | 1 | 1 | 0.7767 | 0.5782 |
  | 7 | Con quale spezia si colora il riso tipico della Lombardia? | assente | **2** | — | 0.5006 |
  | 8 | Come preparare in estate una scorta di passata rossa da usare tutto l'anno? | assente | assente | — | — |
  | 9 | Da quale paese arriva la bevanda scura che si beve per svegliarsi? | assente | **1** | — | 0.4783 |
  | 10 | Quale vino dolce si aggiunge alla crema spumosa fatta con i tuorli? | assente | assente | — | — |

  Fonte attesa trovata: nomic **5/9**, bge-m3 **7/9**. Gli score dei due modelli **non sono
  confrontabili tra loro** (scale diverse): si confrontano le posizioni. Domande senza risposta
  con bge-m3: tiramisù 0.5091, carbonara 0.5320.

- Prova del blocco: `docker compose run --rm ingestion python -m rag.valutazione` con
  `-e QDRANT_COLLEZIONE=ricette_bge_m3` ma senza `-e EMBEDDING_MODELLO` → «Valutazione non
  eseguita: la collezione è stata creata con il modello 'text-embedding-bge-m3', ma
  EMBEDDING_MODELLO è 'text-embedding-nomic-embed-text-v1.5': cambio bloccato», codice di uscita
  **4**.

  Commento: bge-m3 tiene tutte le fonti già trovate da nomic e recupera due domande
  **parafrasate**: la 9 («bevanda scura per svegliarsi» → caffè, primo posto) e la 7 («spezia del
  riso lombardo» → zafferano, secondo posto). È l'effetto atteso da un modello addestrato anche
  sull'italiano: collega parole diverse con lo stesso significato, dove nomic si appoggia di più
  alle parole uguali. Restano assenti la 8 (passata) e la 10 (zabaione). Anche con bge-m3 nessuna
  soglia funziona: la risposta giusta della domanda 9 ha 0.4783, meno del tiramisù (0.5091), che
  nel libro non c'è. Costi: vettori da 1024 invece di 768 (più spazio in Qdrant) e ingestion più
  lenta.

### Riepilogo delle estensioni

| Collezione | Strategia | Modello | Punti | Fonte attesa trovata |
|---|---|---|---|---|
| `ricette` | paragrafi 1200/200 | nomic | 1145 | 5/9 |
| `ricette_finestra` | finestra 1200/200 | nomic | 1086 | 5/9 |
| `ricette_bge_m3` | paragrafi 1200/200 | bge-m3 | 1145 | 7/9 |

Ricerca di confronto `"Come si frigge il pollo?" --k 3` sulle tre collezioni (per le due nuove
aggiungere le stesse `-e` dei comandi sopra, per esempio
`docker compose run --rm -e QDRANT_COLLEZIONE=ricette_finestra -e CHUNK_STRATEGIA=finestra ingestion python -m rag.ricerca "Come si frigge il pollo?" --k 3`):

| # | `ricette` (paragrafi, nomic) | `ricette_finestra` (finestra, nomic) | `ricette_bge_m3` (paragrafi, bge-m3) |
|---|---|---|---|
| 1 | N. 209 Pollo fritto coi pomodori (0.7550) | N. 209 Pollo fritto coi pomodori (0.7550) | N. 206 Pollo dorato II (0.6362) |
| 2 | N. 264 Pollo colla marsala, Umidi (0.7201) | N. 264 Pollo colla marsala, Umidi (0.7201) | N. 208 Pollo alla cacciatora (0.6193) |
| 3 | N. 208 Pollo alla cacciatora (0.7181) | N. 208 Pollo alla cacciatora (0.7181) | N. 209 Pollo fritto coi pomodori (0.6014) |

Le due collezioni nomic danno risultati identici (ricette corte: stesso chunk con le due
strategie). Con bge-m3 i tre risultati sono **tutti ricette di pollo fritto** del capitolo «Fritti»
(il primo, «friggetelo in padella», risponde in modo diretto); nomic mette al secondo posto un
pollo in umido.

Commento finale: su queste domande la configurazione migliore è **paragrafi 1200/200 con
`text-embedding-bge-m3`** (7/9 contro 5/9): a parità di chunking, il modello multilingue capisce
meglio le domande in italiano scritte con parole diverse da quelle del libro. Il chunking conta
meno: `finestra` non trova niente in più e peggiora un caso. Limiti del confronto: solo 9 domande
con risposta, una sola esecuzione, e la configurazione del progetto resta quella della specifica
(nomic, collezione `ricette`): cambiarla è una decisione da prendere a parte (la lezione 8 userà
l'indice per generare le risposte).
