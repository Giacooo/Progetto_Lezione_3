# Specifica — Lezione 6, step 1: Router (conversazione o fuori ambito)

Data: 2026-11-13. Stato: **approvata dall'utente il 2026-11-13**.
Fonte dei requisiti: `LLM_Lez_6.pdf` (slide «Step 1–3 — Un secondo nodo LLM», «Step 1 · Router:
cosa realizzare», «Metodo e consegna»), `assistente-laboratorio/CLAUDE.md` (commit `0345583`),
decisioni dell'utente prese nel brainstorming del 2026-11-13.

Le voci marcate **[scelta mia]** non sono state decise dall'utente: sono decisioni di chi ha
scritto la specifica, da controllare in lettura. Tutto il resto è richiesto dal PDF o deciso
dall'utente.

---

## 1. Intento

Oggi ogni domanda arriva all'agente (nodo `llm` con gli strumenti), qualunque sia l'argomento.
Lo step 1 dà all'agente un **ambito dichiarato** e aggiunge, prima dell'agente, un **nodo LLM
router** che decide se la domanda rientra nell'ambito. Le domande fuori ambito ricevono un
rifiuto **senza raggiungere l'agente** (obiettivo del PDF). La scelta degli strumenti resta
all'agente, come prima.

È il primo dei nove step della lezione 6; l'utente ha chiesto di realizzarli tutti, seguendo il
PDF alla lettera e senza aggiungere nulla.

## 2. Obiettivi (dal PDF, «Cosa realizzare»)

1. **01** — Ambito dell'agente descritto in configurazione, non nel codice.
2. **02** — Nodo router con output strutturato: **categoria** (`conversazione` o
   `fuori ambito`) e **motivo**.
3. **03** — Arco condizionale: `conversazione` → agente; `fuori ambito` → nodo di rifiuto → fine.
4. **04** — Il router non valuta gli strumenti: se servono, lo decide l'agente come prima.

Evidenze richieste dal PDF:
- domanda in ambito: log con categoria, motivo e passaggio all'agente;
- domanda fuori ambito: rifiuto, **nessuna esecuzione del nodo agente** nei log;
- test con risposte del router simulate per entrambi i percorsi.

Consegna (PDF, «Metodo e consegna»): test automatici, prova reale con LM Studio, README
aggiornato e commit; evidenza minima: «domanda fuori ambito rifiutata senza passare
dall'agente». Il `CLAUDE.md` va aggiornato perché cambia l'architettura del grafo.

## 3. Non obiettivi e anti-obiettivi

- **Non** si anticipano gli step successivi: niente revisore, riassunto, resource, prompt,
  servizio HTTP. Lo stato del grafo non riceve campi per gli step futuri.
- **Non** si cambia il comportamento dell'agente: stesso nodo `llm`, stesso prompt di sistema,
  stessi strumenti, stesso limite `MAX_PASSI`, stesso formato dei log degli strumenti.
- **Non** si aggiungono dipendenze: bastano `langgraph` e `langchain-openai` già presenti.
- Il modello resta `google/gemma-4-e2b`, lo stesso per router e agente (il PDF: «lo stesso
  modello viene usato con prompt di sistema diversi»).
- **Anti-obiettivo:** un router che rifiuta domande legittime dell'ambito (es. «Che ore sono?»)
  o la normale conversazione (saluti, «Mi chiamo Luca», «Come mi chiamo?»). Le prove reali
  esistenti devono continuare a passare.
- **Anti-obiettivo:** un router che decide quali strumenti usare o che risponde lui alla domanda.

## 4. Decisioni dell'utente (brainstorming del 2026-11-13)

| Tema | Decisione |
|---|---|
| Ambito | data e ora, calcoli, conversioni di unità, giorni lavorativi e scadenze, corsi del catalogo, note, meteo; più saluti e conversazione normale. Tutto il resto è fuori ambito (es. «Raccontami la storia di Roma», «Parlami di Forlì e del caffè»). |
| Testo del rifiuto | **fisso**: dice che la domanda è fuori ambito e che cosa l'assistente può fare. |
| Motivo del router | **solo nei log**, non mostrato all'utente. |
| Risposta del router non valida | la domanda **passa all'agente**, con un **avviso nel log**. |

### 4.1 Casi attesi per la classificazione [scelta mia, derivata dall'ambito deciso]

Servono a tarare il prompt del router e a scegliere le prove; il router vede la conversazione
precedente (sezione 6.1), quindi le domande di seguito si giudicano nel loro contesto.

| Domanda | Categoria attesa |
|---|---|
| «Ciao, come stai?», «Grazie», «Mi chiamo Luca», «Come mi chiamo?» | conversazione |
| «Cosa sai fare?» (domande sull'assistente stesso) | conversazione |
| «Che ore sono?», «Quanto fa 1234 per 5678?», «Quanti miglia sono 10 km?», «Quanto dura il corso di Python a Udine?», «Ricordami di ...», «Che tempo fa a Pordenone?» | conversazione |
| Seguito di un tema in ambito: «e in Fahrenheit?» dopo una conversione, «e domani?» dopo il meteo | conversazione |
| «Raccontami la storia di Roma», «Parlami di Forlì e del caffè», «Qual è la capitale della Francia?» | fuori ambito |
| Spiegazioni generiche non legate all'ambito (es. «Spiegami la fotosintesi») | fuori ambito |
| Casi misti (es. «Quanti km ci sono tra Roma e Milano, in miglia?»): contengono una parte in ambito | conversazione (l'agente decide se e come rispondere) |

Nota per lo step 5 (non si anticipa ora): il PDF chiede che `/prompt spiega argomento="Model
Context Protocol"` passi dal router. Con l'ambito attuale sarebbe fuori ambito; poiché l'ambito
sta in configurazione, se ne riparla nel brainstorming dello step 5.

## 5. Configurazione

- Nuova variabile **`AMBITO_AGENTE`** nel `.env` e in `.env.example` **[scelta mia]**: elenco
  degli argomenti dell'ambito separati da virgola. Valore di esempio:
  ```
  AMBITO_AGENTE=data e ora, calcoli, conversioni di unità, giorni lavorativi e scadenze, corsi del catalogo, note, meteo
  ```
- Saluti e conversazione normale sono **sempre** in ambito: lo dice il prompt del router, non la
  variabile **[scelta mia]**.
- La variabile è **obbligatoria** **[scelta mia]**: se manca o è vuota, l'avvio si ferma con
  `Configurazione non valida: variabili mancanti: AMBITO_AGENTE` e codice di uscita 2, come le
  altre obbligatorie. Motivo: il PDF chiede che l'ambito stia in configurazione, quindi non
  esiste un ambito «di riserva» nel codice. Il `.env` reale dell'utente va aggiornato a mano
  (il README lo dice).
- La configurazione (`Configurazione`) riceve un campo con l'ambito già letto.
- Docker: nessuna modifica a `compose.yaml`; la variabile arriva dal `.env` tramite `env_file`.

## 6. Grafo

Grafo dopo lo step 1 (nodi nuovi in grassetto):

```
START → **router** ─(conversazione, o risposta non valida)→ llm ⇄ strumenti → END
                 └─(fuori ambito)→ **rifiuto** → END
```

- Il nodo `llm`, il nodo `strumenti`, la funzione `instrada` e `MAX_PASSI` restano come sono.
- Stato: per l'arco condizionale serve sapere la decisione del router nel turno. Lo stato
  `StatoTurno` riceve **un campo** con la categoria decisa (es. `categoria`) **[scelta mia]**; il
  motivo va solo nel log e non nello stato.
- La chiamata del router **non conta** nei `passi` del limite `MAX_PASSI`, che resta il limite
  dell'agente **[scelta mia]**.

### 6.1 Nodo router

- Usa lo **stesso modello** dell'agente, **senza** `bind_tools`, con un **prompt di sistema
  proprio** che contiene l'ambito letto dalla configurazione e le due categorie ammesse. Il
  prompt non nomina gli strumenti e chiede solo se la domanda rientra nell'ambito (requisito 04).
- **Output strutturato** con due campi: `categoria` (solo `conversazione` o `fuori ambito`) e
  `motivo` (testo breve). Si usa l'output strutturato di LangChain sul modello di LM Studio
  (schema JSON) **[scelta mia]**; la tecnica esatta è del builder (sezione 11).
- **Cosa vede il router** **[scelta mia]**: i messaggi della conversazione ridotti al testo,
  cioè le domande dell'utente e le risposte finali dell'assistente, più la domanda nuova; **non**
  le richieste di strumento né i `ToolMessage`. Motivo: per capire domande che dipendono dal
  contesto («Come mi chiamo?», «e domani?») serve la conversazione, ma il router non deve
  valutare gli strumenti.
- **Risposta non valida** (decisione dell'utente): se l'output non si può leggere o la categoria
  non è una delle due ammesse, il nodo registra un avviso e la domanda **passa all'agente**,
  come se fosse `conversazione`.
- **Errori di collegamento** (LM Studio spento, attesa scaduta, errore dal server): non sono
  «risposte non valide». Si comportano come oggi per l'agente: il turno fallisce con lo stesso
  messaggio (`Connessione fallita: ...` ecc.), la sessione continua e la cronologia non cambia
  **[scelta mia]**. Il router quindi non deve catturare queste eccezioni.

### 6.2 Nodo rifiuto

- Non chiama il modello. Aggiunge alla conversazione una risposta dell'assistente con testo
  **fisso**, costruito con l'ambito della configurazione (decisione dell'utente):
  ```
  Questa domanda è fuori dal mio ambito. Posso aiutarti con: <AMBITO_AGENTE>.
  ```
  La parte «Posso aiutarti con» riusa la stessa variabile dell'ambito **[scelta mia]**: se cambia
  l'ambito, cambia anche il rifiuto senza toccare il codice.
- Il rifiuto **entra nella cronologia** come una risposta normale (domanda + rifiuto)
  **[scelta mia]**, così i turni successivi vedono che cosa è successo.
- Il terminale lo stampa come qualunque risposta; `conversazione.py` non ha bisogno di casi
  speciali.

## 7. Log

Logger `assistente.grafo`, livello INFO, stesso stile `chiave=valore` della lezione 5
**[scelta mia per il formato]**:

```
INFO assistente.grafo: Inizio chiamata al router
INFO assistente.grafo: router categoria=conversazione motivo=<motivo> next_node=llm (agente)
INFO assistente.grafo: Inizio chiamata al modello (passo 1/5)
...
```

```
INFO assistente.grafo: Inizio chiamata al router
INFO assistente.grafo: router categoria=fuori ambito motivo=<motivo> next_node=rifiuto
INFO assistente.grafo: rifiuto inviato, nodo agente non eseguito
```

```
WARNING assistente.grafo: router risposta non valida (<dettaglio>): passaggio all'agente next_node=llm (agente)
```

- `next_node=llm (agente)`: `llm` è il nome interno del nodo dell'agente; la parola «agente»
  rende leggibile nel log l'evidenza «passaggio all'agente» chiesta dal PDF.
- Nel percorso fuori ambito **non** compare alcuna riga `Inizio chiamata al modello (passo ...)`:
  è l'evidenza «nessuna esecuzione del nodo agente».
- Le righe esistenti di agente e strumenti non cambiano.

## 8. Test automatici (senza LM Studio)

Con modelli simulati (`tests/finti.py`): uno per il router, che restituisce l'output
strutturato deciso dal test, e uno per l'agente.

- **Percorso conversazione:** router simulato → `conversazione`; il modello dell'agente viene
  chiamato; nel log categoria, motivo e `next_node=llm (agente)`.
- **Percorso fuori ambito:** router simulato → `fuori ambito`; il modello dell'agente **non**
  viene mai chiamato (zero chiamate registrate); la risposta è il testo fisso con l'ambito; nel
  log categoria, motivo e `next_node=rifiuto`, e nessuna riga `Inizio chiamata al modello`.
- **Risposta non valida:** router simulato con categoria sconosciuta o output illeggibile →
  l'agente viene chiamato e nel log c'è l'avviso.
- **Strumenti dopo il router:** domanda in ambito che richiede `ora_corrente` → giro completo
  `router → llm → strumenti → llm` come oggi.
- **Prompt del router:** contiene l'ambito della configurazione e non nomina gli strumenti.
- **Cosa vede il router:** con una cronologia che contiene un giro di strumento, al router
  arrivano solo domande e risposte di testo.
- **Cronologia:** dopo un rifiuto contiene domanda e rifiuto; dopo un errore di collegamento del
  router resta invariata.
- **Configurazione:** `AMBITO_AGENTE` mancante o vuota → errore con il nome della variabile.
- I test esistenti vanno adattati al nuovo grafo (router simulato che risponde
  `conversazione`) senza cambiare ciò che verificano.

## 9. Prove reali con LM Studio

**Prove reali automatiche** (`tests/test_reale.py`, attivate con `PROVE_REALI=1`):
- nuova: una domanda **fuori ambito** (es. «Raccontami la storia di Roma») → rifiuto fisso e
  nessuna chiamata all'agente;
- le otto esistenti devono continuare a passare, quindi il router deve classificarle
  `conversazione`.
- **Attenzione:** la prova esistente «domanda ordinaria senza strumento» usa «Qual è la capitale
  della Francia?», che con l'ambito deciso è **fuori ambito**. Proposta **[scelta mia]**:
  cambiarla in una domanda di conversazione normale (es. «Ciao, come stai?»), che verifica
  ancora «nessuno strumento» ed è in ambito.

**Prove manuali** (aggiunte alla checklist del README):
- domanda in ambito (es. «Che ore sono?»): nel log riga del router con
  `categoria=conversazione`, poi il giro dell'agente come oggi;
- domanda fuori ambito (es. «Raccontami la storia di Roma»): rifiuto fisso, riga del router con
  `categoria=fuori ambito` e `next_node=rifiuto`, nessuna riga `Inizio chiamata al modello`;
- «Mi chiamo Luca» → «Come mi chiamo?»: entrambe in ambito, la risposta contiene «Luca»;
- LM Studio spento: `Connessione fallita: ...`, la sessione continua.

**Docker:** per lo step 1 il PDF chiede solo la prova reale con LM Studio, quindi le prove in
Docker **non** fanno parte delle evidenze. Si verifica soltanto che l'applicazione esistente non
si rompa: `docker compose build` riuscito e avvio del container fino al prompt `Tu>` (con
`AMBITO_AGENTE` presente nel `.env`).

Una risposta simulata non dimostra che gemma sappia classificare: l'evidenza vale solo con la
prova reale. Se gemma classifica male una domanda, si corregge il **prompt del router**, tenendo
gemma.

**Criterio di superamento [scelta mia, come nella lezione 5]:** le prove reali automatiche si
eseguono una volta; se una fallisce, si registra il punto esatto, si corregge il prompt del
router e si ripete l'intera serie. Lo step non si dichiara completo (né si unisce in `dev`)
finché tutte le prove reali, automatiche e manuali, non passano in una stessa esecuzione dopo
l'ultima modifica. Gli esiti, anche i fallimenti intermedi, vanno nel README con la data.
Le domande della tabella 4.1 sono la guida per le prove manuali aggiuntive.

## 10. Documentazione e Git

- **README:** variabile `AMBITO_AGENTE`, grafo con router e rifiuto, formato dei log del router,
  voci nuove della checklist, esiti delle prove reali con data (solo comandi eseguiti davvero).
- **CLAUDE.md:** aggiornamento breve della parte sull'architettura (grafo con router e rifiuto,
  ambito in configurazione).
- **Git:** branch `feat/router` da `dev`; Conventional Commits in italiano, un commit per ogni
  incremento verificato; merge in `dev` a step verificato; `dev` in `main` solo con conferma
  dell'utente; push solo su richiesta. Questa specifica e il piano si committano su `dev` prima
  di creare il branch **[scelta mia, come nella lezione 5]**.

## 11. Lasciato al builder

- La tecnica esatta dell'output strutturato (`with_structured_output` con schema JSON o modo
  equivalente supportato da LM Studio con gemma), purché valgano le regole della sezione 6.1.
- Il testo esatto del prompt di sistema del router, da sistemare con le prove reali.
- I nomi interni (funzioni, campo dello stato) e come passare al grafo il secondo modello e
  l'ambito, estendendo `costruisci_grafo` senza riscriverlo.
- La lunghezza massima del motivo nel log.
