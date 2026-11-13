# Specifica — Lezione 6, step 2: Revisore (la risposta è coerente con la domanda?)

Data: 2026-11-13. Stato: **bozza, da approvare dall'utente**.
Fonte dei requisiti: `LLM_Lez_6.pdf` (slide «Step 1–3 — Un secondo nodo LLM» con lo schema del
grafo, «Step 2 · Revisore: cosa realizzare», «Metodo e consegna»), `assistente-laboratorio/CLAUDE.md`,
decisioni dell'utente prese nel brainstorming del 2026-11-13.

Le voci marcate **[scelta mia]** non sono state decise dall'utente: sono decisioni di chi ha
scritto la specifica, da controllare in lettura. Tutto il resto è richiesto dal PDF o deciso
dall'utente.

---

## 1. Intento

Oggi la risposta finale dell'agente arriva all'utente così com'è, anche se risponde solo a una
parte della domanda o esce dal tema. Lo step 2 aggiunge, **dopo l'agente**, un **nodo LLM
revisore** che controlla se la risposta è coerente con la domanda: tutte le parti richieste,
nessuna deviazione dal tema. Se non lo è, la risposta torna all'agente con il motivo, finché non
è coerente o si raggiunge un limite (obiettivo del PDF).

Parte dallo step 1 (router) funzionante e unito in `dev` (commit `e1e4565`).

## 2. Obiettivi (dal PDF, «Cosa realizzare»)

1. **01** — Nodo revisore che riceve la domanda dell'utente e la risposta proposta dall'agente.
2. **02** — Output strutturato: **coerente** (sì o no) e **motivo**.
3. **03** — Se non coerente, il motivo entra nella cronologia come indicazione per l'agente.
4. **04** — Limite di revisioni nello stato: al limite si restituisce l'ultima risposta e lo si
   segnala nei log.

Evidenze richieste dal PDF:
- domanda in due parti con risposta parziale: rifiuto motivato e nuova risposta completa;
- risposta coerente: approvata al primo passaggio;
- limite rispettato con un revisore simulato che rifiuta sempre.

Consegna (PDF, «Metodo e consegna»): test automatici, prova reale con LM Studio, README
aggiornato e commit; evidenza minima: «risposta incompleta corretta dopo la revisione, entro il
limite». Il `CLAUDE.md` va aggiornato perché cambia l'architettura del grafo.

## 3. Non obiettivi e anti-obiettivi

- **Non** si anticipano gli step successivi: niente riassunto, resource, prompt, servizio HTTP.
  Lo stato del grafo riceve solo il campo che serve al limite di revisioni.
- **Non** si fa la parte facoltativa del PDF («Se manca»: streaming lungo la catena e scelta
  tra mostrare la bozza o solo la risposta approvata): si affronta solo se l'utente lo decide.
- **Non** si riscrive lo step 1: router, rifiuto, agente, strumenti restano come sono; si
  estendono `costruisci_grafo`, la configurazione e il filtro dei messaggi del router.
- **Non** si cambia il prompt di sistema dell'agente (`PROMPT_SISTEMA`) né i log esistenti.
- **Non** si aggiungono dipendenze.
- Il modello resta `google/gemma-4-e2b`, lo stesso per router, agente e revisore.
- **Anti-obiettivo:** un revisore che giudica se la risposta è *vera* (non vede i risultati
  degli strumenti) o che riscrive lui la risposta: giudica solo la coerenza con la domanda.
- **Anti-obiettivo:** un revisore che boccia risposte buone e fa riscrivere senza motivo: le
  prove reali esistenti devono continuare a passare.

## 4. Decisioni dell'utente (brainstorming del 2026-11-13)

| Tema | Decisione |
|---|---|
| Cronologia dopo il turno | **Resta tutto**: domanda, bozza rifiutata, indicazione del revisore, risposta nuova (lettura letterale del PDF, come il rifiuto dello step 1). |
| Risposta del revisore non valida | La risposta dell'agente è **approvata**, con un **avviso nel log** (stessa regola del router). |
| Prove reali | «Attenersi al PDF»: le scelte di dettaglio della sezione 9 sono **[scelta mia]** fatte con questo criterio. |
| Strada di costruzione | Modulo nuovo `assistente/revisore.py`, gemello di `router.py` (vedi sezione 11). |

## 5. Configurazione

- Nuova variabile **facoltativa `MAX_REVISIONI`** **[scelta mia]**: numero massimo di volte in cui
  il revisore può rimandare la risposta all'agente in un turno. Se manca vale **2**; deve essere
  un intero maggiore di zero, altrimenti l'avvio si ferma con
  `Configurazione non valida: MAX_REVISIONI deve essere un intero maggiore di zero, non '...'`
  (stesso controllo e stesso stile di `MAX_PASSI`).
- `Configurazione` riceve il campo `max_revisioni: int`.
- `.env.example`: riga commentata con il valore predefinito, accanto a `MAX_PASSI`.
- Docker: nessuna modifica a `compose.yaml` (la variabile, se c'è, arriva dal `.env`).

## 6. Grafo

Grafo dopo lo step 2 (nodo nuovo in grassetto):

```
START → router ─(fuori ambito)→ rifiuto → END
          └(conversazione, o risposta non valida)→ llm ⇄ strumenti
                                                     └(risposta finale)→ **revisore**
                                                           ├(coerente: sì, o risposta non valida)→ END
                                                           ├(coerente: no, revisioni < limite)→ llm
                                                           └(coerente: no, limite raggiunto)→ END
```

- `instrada` (dopo `llm`) cambia **solo** la destinazione del caso «risposta finale»: prima
  `END`, ora `revisore`. Il caso «limite di passaggi raggiunto con richiesta di strumento aperta»
  resta `END` come oggi (non c'è una risposta da giudicare; il turno fallisce come oggi con
  `Limite di passaggi raggiunto: ...`).
- Il ramo `rifiuto` **non** passa dal revisore (schema del PDF: rifiuto → END).
- Stato: `StatoTurno` riceve il campo **`revisioni: int`** **[scelta mia per il nome]**: quante
  volte, nel turno, il revisore ha rimandato la risposta all'agente. Parte da 0 (lo imposta
  `Conversazione.chiedi`, come `passi`). È il «limite di revisioni nello stato» del PDF.
- **Passi dell'agente** **[scelta mia]**: quando il revisore rimanda la risposta, `passi`
  riparte da 0. Ogni nuovo tentativo dell'agente ha quindi i suoi `MAX_PASSI`; altrimenti un
  tentativo che usa gli strumenti potrebbe trovare i passi esauriti e far fallire tutto il turno.
  Il numero di tentativi resta comunque limitato da `MAX_REVISIONI`.
- La chiamata del revisore **non conta** nei `passi` (come il router).
- **Limite di passaggi in un nuovo tentativo** **[scelta mia]**: se un tentativo dopo una
  revisione si ferma al limite `MAX_PASSI` con una richiesta di strumento aperta, il turno
  fallisce come oggi (`Limite di passaggi raggiunto: ...`, cronologia invariata), anche se una
  bozza precedente esisteva. Motivo: è un caso raro (i passi ripartono da 0 a ogni tentativo) e
  così `Conversazione` non cambia. Un test lo conferma.
- **Limite di ricorsione di LangGraph** **[scelta mia]**: con i nuovi giri il numero di nodi
  eseguiti in un turno può superare il limite predefinito di LangGraph (25 nodi), che oggi
  diventerebbe un «Errore inatteso». Per esempio, con `MAX_PASSI=5` e `MAX_REVISIONI=2` il caso
  peggiore è 1 router + 3 × (5 llm + 4 strumenti + 1 revisore) = 31 nodi. `costruisci_grafo`
  imposta quindi sul grafo compilato un `recursion_limit` calcolato dai due limiti, con un
  piccolo margine; `Conversazione` non cambia. Un test con il revisore che rifiuta sempre e
  l'agente che usa strumenti fino al limite lo conferma.

### 6.1 Conteggio e limite (esempio con `MAX_REVISIONI=2`)

| Tentativo dell'agente | Esito del revisore | `revisioni` dopo | Dove si va |
|---|---|---|---|
| 1 | no | 1 | indicazione → llm |
| 2 | no | 2 | indicazione → llm |
| 3 | no | 2 (limite) | END con la risposta del tentativo 3, avviso nel log |

Al massimo `MAX_REVISIONI + 1` risposte dell'agente e altrettante chiamate al revisore per turno.
Con un revisore simulato che rifiuta sempre e `MAX_REVISIONI=2`: tre chiamate all'agente, tre al
revisore, risposta finale = terza risposta dell'agente.

### 6.2 Nodo revisore

- Usa lo **stesso modello** dell'agente, **senza** `bind_tools`, con un **prompt di sistema
  proprio**: deve dire solo se la risposta risponde a **tutte le parti** della domanda e **resta
  in tema**; non deve giudicare se i dati sono veri, non deve riscrivere la risposta, non nomina
  gli strumenti.
- **Cosa vede** (PDF, punto 01) **[scelta mia per il dettaglio]**: solo la **domanda
  dell'utente** del turno e la **risposta proposta** (ultima risposta di testo dell'agente). Non
  vede la conversazione precedente, le richieste di strumento, i `ToolMessage` né le indicazioni
  e le bozze precedenti del turno.
  - «Domanda dell'utente del turno» = l'ultimo `HumanMessage` che **non** è un'indicazione del
    revisore.
  - Il modo esatto di presentarle al modello (un messaggio con «Domanda: … / Risposta: …» o due
    messaggi) è del builder.
  - **Domande di seguito** («E domani?», «Come mi chiamo?») **[scelta mia]**: il revisore non
    vede il contesto (PDF, punto 01, alla lettera). Il prompt gli dice che una domanda breve può
    riferirsi a una conversazione precedente che lui non vede: in quel caso giudica solo se la
    risposta prova a rispondere a quello che chiede, e **non** la boccia per mancanza di
    contesto. Le prove manuali (sezione 9) controllano questi casi.
- **Output strutturato** con due campi: `coerente` (solo `sì` o `no`, scritti così, come nel
  PDF) e `motivo` (testo breve). Stessa tecnica del router: `with_structured_output(...,
  method="json_schema", include_raw=True)` **[scelta mia]**.
- **Risposta non valida** (decisione dell'utente): JSON illeggibile, `coerente` diverso da
  `sì`/`no` (anche `si` senza accento, `Sì`, `true`), motivo mancante o vuoto, risposta troncata
  o filtrata (`openai.LengthFinishReasonError`, `openai.ContentFilterFinishReasonError`) → la
  risposta è **approvata** e nel log c'è un avviso. Il turno finisce (END).
- **Errori di collegamento** (LM Studio spento, attesa scaduta, errore dal server) **[scelta
  mia, come il router]**: non si catturano; il turno fallisce con lo stesso messaggio di oggi
  (`Connessione fallita: ...` ecc.), la sessione continua e la cronologia non cambia (regola già
  in `Conversazione.chiedi`).
- **Coerente: sì** → il turno finisce con quella risposta.
- **Coerente: no e `revisioni` < `MAX_REVISIONI`** → il nodo aggiunge l'**indicazione** alla
  conversazione, incrementa `revisioni`, rimette `passi` a 0 e si torna a `llm`.
- **Coerente: no e `revisioni` = `MAX_REVISIONI`** → nessuna indicazione, il turno finisce con
  l'ultima risposta dell'agente (quella appena giudicata) e un avviso nel log (PDF, punto 04).
  L'utente riceve la risposta **senza** avvisi a schermo (il PDF chiede la segnalazione solo nei
  log) **[scelta mia]**.

### 6.3 L'indicazione per l'agente

- È un messaggio aggiunto alla conversazione **dopo** la bozza rifiutata, che l'agente legge alla
  chiamata successiva (PDF, punto 03). Tipo: `HumanMessage` con `name="revisore"` **[scelta
  mia]**: il modello lo legge come un'istruzione nel turno; il campo `name` permette al codice di
  riconoscerlo.
- Testo **[scelta mia per la forma]**:
  ```
  Indicazione del revisore: la risposta precedente non è coerente con la domanda. Motivo: <motivo>. Rispondi di nuovo alla domanda, completa e in tema.
  ```
  (testo esatto lasciato al builder, purché contenga il motivo del revisore).
- **Resta nella cronologia** della sessione alla fine del turno, insieme alla bozza rifiutata
  (decisione dell'utente). `Conversazione` non cambia: salva già tutti i messaggi del turno e
  prende come risposta l'ultimo messaggio.
- **Router** (estensione dello step 1) **[scelta mia]**: `messaggi_per_router` **salta** gli
  `HumanMessage` con `name="revisore"` **e** la bozza rifiutata che li precede (l'ultima
  risposta di testo dell'agente prima dell'indicazione). Così nei turni successivi il router non
  scambia l'indicazione per una domanda dell'utente e vede domande e risposte che si alternano
  (utente, assistente, utente, ...), senza due risposte dell'assistente di fila: alcuni modelli
  di chat, come i template di Gemma, non accettano turni che non si alternano. Il router vede
  quindi solo la risposta approvata (o l'ultima, al limite) di ogni turno.
- **Agente:** vede tutta la cronologia, bozze e indicazioni comprese (serve per correggersi e
  sono nella cronologia per decisione dell'utente); i messaggi si alternano già (bozza,
  indicazione, nuova risposta).

## 7. Log

Logger `assistente.grafo`, stesso stile `chiave=valore` del router **[scelta mia per il formato]**:

```
INFO assistente.grafo: Inizio chiamata al revisore
INFO assistente.grafo: revisore coerente=sì motivo=<motivo> next_node=END
```

```
INFO assistente.grafo: Inizio chiamata al revisore
INFO assistente.grafo: revisore coerente=no motivo=<motivo> next_node=llm (agente) revisione=1/2
INFO assistente.grafo: Inizio chiamata al modello (passo 1/5)
...
```

```
INFO assistente.grafo: revisore coerente=no motivo=<motivo> next_node=END revisione=2/2
WARNING assistente.grafo: limite di revisioni raggiunto (2): restituita l'ultima risposta
```

```
WARNING assistente.grafo: revisore risposta non valida (<dettaglio>): risposta approvata next_node=END
```

- `revisione=n/m`: `n` è il valore di `revisioni` **dopo** la decisione, `m` è `MAX_REVISIONI`.
- Motivo e dettaglio troncati a 200 caratteri, come nel router.
- Le righe esistenti di router, agente e strumenti non cambiano. Dopo un rifiuto del revisore il
  contatore dei passi nel log riparte da `passo 1/5`.

## 8. Test automatici (senza LM Studio)

Con modelli simulati (`tests/finti.py`): un **revisore finto** analogo a `RouterFinto` (uscite
decise dal test, chiamate registrate) e un aiuto per costruire una valutazione
(`{"raw": None, "parsed": {"coerente": ..., "motivo": ...}, "parsing_error": None}`).

- **Approvata al primo passaggio** (evidenza PDF): revisore `sì` → agente chiamato una volta,
  revisore una volta; risposta = prima risposta; `revisioni == 0`; nel log `coerente=sì`.
- **Risposta parziale corretta** (evidenza PDF): domanda in due parti; agente simulato che
  risponde prima a una parte e poi a entrambe; revisore `no` poi `sì` → due risposte
  dell'agente; la seconda chiamata all'agente contiene l'indicazione con il motivo; risposta
  finale = seconda risposta; nel log `coerente=no ... revisione=1/2` e poi `coerente=sì`.
- **Limite rispettato** (evidenza PDF): revisore simulato che **rifiuta sempre**,
  `MAX_REVISIONI=2` → tre risposte dell'agente, tre chiamate al revisore, risposta finale = terza
  risposta; avviso `limite di revisioni raggiunto (2)`; il grafo termina.
- **Risposta non valida**: `coerente` sconosciuto, motivo vuoto, `parsing_error`, risposta
  troncata → approvata, avviso nel log, nessuna nuova chiamata all'agente.
- **Cosa vede il revisore**: con cronologia precedente, giro di strumento e un'indicazione già
  presente, il revisore riceve solo il prompt di sistema, la domanda del turno e l'ultima
  risposta di testo.
- **Passi azzerati**: dopo un rifiuto del revisore, il nuovo tentativo dell'agente può usare uno
  strumento anche se il primo tentativo aveva usato passi.
- **Rifiuto del router**: il revisore non viene chiamato.
- **Limite di passaggi** (richiesta di strumento aperta): il revisore non viene chiamato; il
  turno fallisce come oggi.
- **Errore di collegamento del revisore**: `ErroreTurno` con `Connessione fallita: ...`;
  cronologia invariata.
- **Cronologia**: dopo una revisione contiene domanda, bozza, indicazione, risposta nuova.
- **Router**: `messaggi_per_router` scarta gli `HumanMessage` con `name="revisore"` e la bozza
  che li precede; i messaggi risultanti si alternano utente/assistente.
- **Limite di ricorsione**: revisore che rifiuta sempre e agente che usa strumenti in ogni
  tentativo fino a `MAX_PASSI` → il turno termina senza `GraphRecursionError`.
- **Limite di passaggi in un nuovo tentativo**: il turno fallisce con `Limite di passaggi
  raggiunto: ...` e la cronologia resta invariata.
- **Prompt del revisore**: non nomina gli strumenti; schema con `coerente` = `["sì", "no"]` e
  campi obbligatori `coerente` e `motivo`.
- **Configurazione**: `MAX_REVISIONI` predefinito 2; valori non validi (0, negativo, testo) →
  errore con il nome della variabile.
- I test esistenti si adattano al nuovo grafo (revisore simulato che risponde sempre `sì`)
  senza cambiare ciò che verificano.

## 9. Prove reali con LM Studio

Criterio dell'utente: attenersi al PDF (prova reale con LM Studio; evidenze verificabili nei log
o nei test). Dettagli **[scelta mia]**.

**Prove reali automatiche** (`tests/test_reale.py`, con `PROVE_REALI=1`):
- le nove esistenti devono continuare a passare con il revisore attivo;
- nuova: **domanda in due parti** nel grafo intero (es. «Che ore sono e che tempo fa a
  Pordenone?») → risposta non vuota; nel log almeno una riga `revisore coerente=`; il test
  riporta nel log se c'è stato un rifiuto e una correzione. Passa se il turno finisce con
  `coerente=sì` (al primo passaggio o dopo una revisione) entro il limite;
- nuova: **approvata al primo passaggio** (es. «Ciao, come stai?») → una sola riga del revisore,
  con `coerente=sì`;
- nuova: **revisore vero davanti a una risposta parziale** preparata dal test (domanda in due
  parti, risposta che ne copre una sola), chiamando direttamente il revisore → `coerente=no` con
  un motivo non vuoto. Serve a mostrare l'evidenza minima con il modello vero anche se gemma, nel
  grafo intero, risponde bene al primo colpo.

**Prove manuali** (aggiunte alla checklist del README):
- domanda semplice («Che ore sono?»): router, agente, `revisore coerente=sì`;
- domanda in due parti: righe del revisore; se c'è un rifiuto, indicazione e nuova risposta;
- «Mi chiamo Luca» → «Come mi chiamo?»: ancora «Luca» (il revisore non rompe la memoria);
- domanda di seguito («Che tempo fa a Pordenone?» → «E domani?»): il revisore non la boccia
  per mancanza di contesto;
- domanda fuori ambito: rifiuto del router, **nessuna** riga del revisore;
- LM Studio spento: `Connessione fallita: ...`, la sessione continua.

**Docker:** come nello step 1, solo verifica che non si rompa: `docker compose build` e avvio
fino a `Tu>`.

**Criterio di superamento** (come lo step 1): le prove reali si eseguono una volta; se una
fallisce si registra il punto esatto, si corregge **solo il prompt del revisore** (gemma resta)
e si ripete l'intera serie. Lo step non si unisce in `dev` finché tutte le prove reali,
automatiche e manuali, non passano dopo l'ultima modifica. Gli esiti, anche intermedi e anche se
gemma non produce mai una risposta parziale nel grafo intero, vanno nel README con la data.

**Rischio noto:** le prove esistenti che controllano gli strumenti usati (es.
`strumenti_usati(...) == ["ora_corrente"]`) potrebbero vedere uno strumento ripetuto se il
revisore fa riscrivere la risposta. Se succede si registra il caso e si decide con l'utente
(prima si guarda il prompt del revisore; non si allentano i test senza via libera).

## 10. Documentazione e Git

- **README:** variabile `MAX_REVISIONI`, grafo con il revisore, formato dei log del revisore,
  prove reali nuove, voci nuove della checklist, diagnosi (`MAX_REVISIONI` non valida), esiti
  con data (solo comandi eseguiti davvero).
- **CLAUDE.md:** una riga nell'«Obiettivo» sul revisore dopo l'agente e sul limite in
  `MAX_REVISIONI`.
- **Git:** specifica e piano committati su `dev` (nel primo commit anche la casella «Task 6
  Step 5» del piano dello step 1, decisione dell'utente); poi branch `feat/revisore` da `dev`;
  Conventional Commits in italiano, un commit per incremento verificato; merge `--no-ff` in
  `dev` a step verificato e con conferma; nessun push.

## 11. Approcci considerati

1. **Modulo nuovo `assistente/revisore.py`, gemello di `router.py`** — **scelto dall'utente**.
   Prompt, schema, lettura della valutazione, testo dell'indicazione e creazione del revisore
   in un file; in `grafo.py` il nodo, il campo `revisioni` e l'arco. Estende lo step 1 senza
   riscriverlo.
2. Modulo unico per router e revisore («secondi LLM» generici): meno righe doppie, ma riscrive
   lo step 1 già verificato (contro la regola «estendere senza riscrivere»).
3. Revisore come sotto-grafo: più complicato del necessario per un nodo, e il PDF lo disegna
   come un nodo normale.

## 12. Lasciato al builder

- Il testo esatto del prompt del revisore, da tarare con le prove reali.
- Come presentare domanda e risposta al revisore (un messaggio o due).
- Il testo esatto dell'indicazione (deve contenere il motivo).
- I nomi interni (funzioni, finti per i test) e come passare revisore e limite a
  `costruisci_grafo` estendendolo (parametri nuovi in coda).
