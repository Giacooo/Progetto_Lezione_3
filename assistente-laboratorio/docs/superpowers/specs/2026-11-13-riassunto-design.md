# Specifica — Lezione 6, step 3: Riassunto della cronologia

Data: 2026-11-13. Stato: **bozza, da approvare dall'utente**.
Fonte dei requisiti: `LLM_Lez_6.pdf` (slide «Step 1–3 — Un secondo nodo LLM» con lo schema del
grafo, «Step 3 · Riassunto della cronologia», «Metodo e consegna»), `assistente-laboratorio/CLAUDE.md`,
decisioni dell'utente prese nel brainstorming del 2026-11-13.

Le voci marcate **[scelta mia]** non sono state decise dall'utente: sono decisioni di chi ha
scritto la specifica, da controllare in lettura. Tutto il resto è richiesto dal PDF o deciso
dall'utente.

---

## 1. Intento

Con un modello locale il contesto è limitato e ogni turno aggiunge messaggi (domande, giri degli
strumenti, bozze e indicazioni del revisore). Lo step 3 aggiunge un **nodo LLM «riassunto»
all'inizio del turno** che, oltre una soglia, sostituisce i messaggi più vecchi con un riassunto e
mantiene intatti gli ultimi. Obiettivo del PDF: la conversazione resta utilizzabile su molti turni
senza perdere le informazioni importanti (per esempio il nome dell'utente).

Parte dallo step 2 (revisore) funzionante e unito in `dev` (commit `ebd80ba`).

## 2. Obiettivi (dal PDF, «Cosa realizzare»)

1. **01** — Soglia configurabile, in numero di messaggi o stima dei token, oltre la quale si
   riassume.
2. **02** — Nodo riassunto all'inizio del turno: comprime i messaggi vecchi e conserva gli
   ultimi N.
3. **03** — Il riassunto è un campo dello stato che viene aggiornato, non accumulato.
4. **04** — Il taglio non separa mai una richiesta di tool dal relativo `ToolMessage`.

Evidenze richieste dal PDF:
- log con numero di messaggi prima e dopo il riassunto;
- un'informazione data al primo turno, come il nome dell'utente, è usata dopo la compressione;
- sotto la soglia il nodo non chiama il modello.

Consegna (PDF, «Metodo e consegna»): test automatici, prova reale con LM Studio, README
aggiornato e commit; evidenza minima: «informazione del primo turno ancora usata dopo la
compressione». Il `CLAUDE.md` va aggiornato perché cambia l'architettura del grafo.

## 3. Non obiettivi e anti-obiettivi

- **Non** si anticipano gli step successivi: niente resource, prompt MCP, servizio HTTP,
  salvataggio delle chat. Lo stato del grafo riceve solo il campo `riassunto`.
- **Non** si fa la parte facoltativa del PDF (streaming lungo la catena).
- **Non** si riscrivono gli step 1 e 2: router, rifiuto, agente, strumenti e revisore restano
  come sono; si estendono `costruisci_grafo`, lo stato, la configurazione, `Conversazione` e i
  messaggi di sistema di agente e router (sezione 6.4).
- **Non** si cambiano i testi di `PROMPT_SISTEMA`, `prompt_router` e `prompt_revisore`, né le
  righe di log esistenti.
- **Non** si aggiungono dipendenze (niente librerie di riassunto già pronte, es. `langmem`:
  approccio scartato, sezione 11).
- Il modello resta `google/gemma-4-e2b`, lo stesso per riassunto, router, agente e revisore.
- **Anti-obiettivo:** un riassunto che perde le informazioni date dall'utente (nome,
  preferenze, cose chieste di ricordare): è proprio l'evidenza del PDF.
- **Anti-obiettivo:** un riassunto che si accumula (un riassunto nuovo aggiunto accanto ai
  vecchi, o messaggi di riassunto che si sommano nella cronologia): il PDF chiede un campo
  aggiornato.
- **Anti-obiettivo:** chiamate al modello quando la cronologia è sotto la soglia (ogni turno
  costerebbe una chiamata in più).

## 4. Decisioni dell'utente (brainstorming del 2026-11-13)

| Tema | Decisione |
|---|---|
| «Ultimi N» | **N messaggi** (lettura letterale del punto 02 e del punto 04 del PDF), con il taglio spostato a un punto sicuro (sezione 6.2). |
| Proposte del brainstorming | Approvate in blocco: soglia in messaggi, due variabili facoltative, taglio spostato indietro alla domanda che apre il turno, nodo prima del router, riassunto riscritto (vecchio riassunto + messaggi tolti), riassunto letto da agente e router ma non dal revisore, `Conversazione` che conserva il riassunto, riassunto vuoto → nessun taglio con avviso, prova reale del nome con soglia bassa. |
| Strada di costruzione | Modulo nuovo `assistente/riassunto.py`, gemello di `router.py` e `revisore.py` (sezione 11). |

## 5. Configurazione

Due nuove variabili **facoltative** **[scelta mia per nomi e valori predefiniti]**:

- **`SOGLIA_RIASSUNTO`** — numero di messaggi della conversazione oltre il quale si riassume.
  Se manca vale **20**. Intero maggiore di zero, altrimenti l'avvio si ferma con
  `Configurazione non valida: SOGLIA_RIASSUNTO deve essere un intero maggiore di zero, non '...'`.
- **`MESSAGGI_DA_TENERE`** — gli ultimi N messaggi conservati così come sono. Se manca vale
  **6**. Intero maggiore di zero, altrimenti
  `Configurazione non valida: MESSAGGI_DA_TENERE deve essere un intero maggiore di zero, non '...'`.
- Controllo incrociato: `MESSAGGI_DA_TENERE` deve essere **minore** di `SOGLIA_RIASSUNTO`,
  altrimenti `Configurazione non valida: MESSAGGI_DA_TENERE (<n>) deve essere minore di SOGLIA_RIASSUNTO (<s>)`.
- `Configurazione` riceve i campi `soglia_riassunto: int` e `messaggi_da_tenere: int`.
- Stesso stile di `MAX_PASSI` e `MAX_REVISIONI` (stringa vuota → predefinito; testo non numerico
  → trattato come 0 e rifiutato).
- `.env.example`: due righe commentate con i valori predefiniti, dopo `MAX_REVISIONI`.
- Docker: nessuna modifica a `compose.yaml`.
- **Perché i messaggi e non i token** **[scelta mia]**: il PDF ammette entrambi; con i messaggi
  il conteggio è esatto, i test sono deterministici e il log «prima e dopo» si legge subito.
  Valori predefiniti: 20 messaggi corrispondono a circa 4–7 turni con strumenti; con il contesto
  di gemma in LM Studio non è stato misurato un limite: i valori si potranno tarare.

## 6. Grafo

Grafo dopo lo step 3 (nodo nuovo in grassetto):

```
START → **riassunto** → router ─(fuori ambito)→ rifiuto → END
                          └(conversazione, o risposta non valida)→ llm ⇄ strumenti
                                                                     └(risposta finale)→ revisore → END / llm
```

- Arco fisso `START → riassunto → router` (schema di pagina 3 del PDF). Gli altri archi non
  cambiano. Cambiano invece, in `grafo.py`, i nodi `llm` e `router` (solo il messaggio di sistema,
  sezione 6.4), la docstring con lo schema e i commenti della «mappa della metropolitana».
- **Campo obbligatorio** **[scelta mia]**: `riassunto` si passa sempre esplicitamente nello stato
  iniziale, come `passi` e `revisioni` (`Conversazione.chiedi`, l'helper `esegui` di
  `tests/test_grafo.py` e ogni altra chiamata diretta del grafo); i nodi lo leggono con
  `stato["riassunto"]`.
- **Parametri nuovi di `costruisci_grafo`** (riassuntore, soglia, N) in coda e obbligatori
  **[scelta mia]**: vanno aggiornate tutte le chiamate (`terminale.main`, le fixture di
  `tests/test_reale.py`, gli helper e le chiamate dirette in `tests/test_grafo.py` e
  `tests/test_conversazione.py`).
- I messaggi si tolgono solo con id presi dallo stato (`add_messages` dà un id a ogni messaggio
  già all'ingresso nel grafo; un id inesistente farebbe sollevare un errore).
- Stato: `StatoTurno` riceve il campo **`riassunto: str`**: il testo del riassunto della parte
  di conversazione tolta; stringa vuota se non c'è ancora. È il campo del PDF, punto 03: il nodo
  lo **sostituisce**, non lo allunga (vedi 6.3).
- Il nodo riassunto **non conta** nei `passi` (come router e revisore).
- `recursion_limit`: la formula dello step 2 riceve **+1** per il nodo nuovo.

### 6.1 Quando si riassume

- Si contano i messaggi dello stato all'inizio del turno, **compresa** la domanda nuova
  (sono quelli che `Conversazione.chiedi` passa al grafo).
- **Sotto la soglia o uguale** (`numero di messaggi <= SOGLIA_RIASSUNTO`): il nodo **non chiama
  il modello**, scrive una riga di log e restituisce `{}` (evidenza del PDF).
- **Sopra la soglia**: si calcola il punto di taglio (6.2). Se non c'è niente da togliere
  (taglio all'indice 0, per esempio un unico turno lunghissimo), il nodo non chiama il modello e
  scrive una riga di log. Altrimenti chiama il modello (6.3).

### 6.2 Il punto di taglio

Funzione pura, testabile senza modello **[scelta mia per la regola esatta]**:

1. si parte dall'indice `len(messaggi) - MESSAGGI_DA_TENERE` (gli ultimi N messaggi);
2. se il messaggio a quell'indice **non** è una domanda dell'utente (un `HumanMessage` che non è
   un'indicazione del revisore, `e_indicazione` dello step 2), il taglio si sposta **indietro**,
   un messaggio alla volta, fino alla domanda dell'utente che apre quel turno;
3. i messaggi prima del taglio sono quelli **da togliere**, quelli dal taglio in poi sono quelli
   **da tenere**.

Conseguenze:
- una richiesta di strumento non è mai separata dal suo `ToolMessage` (punto 04 del PDF): stanno
  sempre nello stesso turno, dopo la domanda che lo apre;
- un'indicazione del revisore non resta senza la sua bozza;
- i messaggi tenuti iniziano sempre con una domanda dell'utente: ai modelli Gemma serve che i
  turni si alternino a partire dall'utente;
- si tengono **almeno** N messaggi, a volte di più. La domanda nuova (ultimo messaggio) è
  sempre tenuta, quindi il taglio non supera mai l'ultima domanda.

Esempio con `MESSAGGI_DA_TENERE=3`:

```
0 Human «Mi chiamo Luca»          ← da togliere
1 AI    «Piacere, Luca»           ← da togliere
2 Human «Che ore sono?»           ← taglio spostato qui (apre il turno)
3 AI    [richiesta ora_corrente]
4 Tool  «12:00»                   ← indice di partenza: 7 messaggi - 3 = 4, non è una domanda
5 AI    «Sono le 12.»
6 Human «Come mi chiamo?»         (domanda nuova)
```

(l'indice di partenza 4 è un `ToolMessage`: tagliare lì separerebbe il risultato dalla sua
richiesta; il taglio torna all'indice 2, si tolgono 2 messaggi e se ne tengono 5).

### 6.3 Il nodo riassunto

- Usa lo **stesso modello**, **senza** `bind_tools` e **senza** risposta strutturata: il
  riassunto è testo libero **[scelta mia]**. Prompt di sistema proprio
  (`prompt_riassunto()` in `assistente/riassunto.py`): riassumere in italiano, in modo breve, la
  conversazione tra utente e assistente; **conservare** le informazioni sull'utente (nome,
  preferenze, cose chieste di ricordare) e i fatti e risultati importanti; integrare il
  riassunto precedente con i messaggi nuovi; scrivere solo il riassunto. Non nomina gli
  strumenti per nome. Testo esatto lasciato al builder, da tarare con le prove reali.
- **Cosa riceve** **[scelta mia]**: un solo messaggio dell'utente che contiene il **riassunto
  precedente** (se c'è) e la **trascrizione** dei messaggi da togliere, una riga per messaggio:
  - domanda dell'utente → `Utente: <testo>`;
  - risposta di testo dell'assistente → `Assistente: <testo>`;
  - risultato di uno strumento → `Strumento <nome>: <testo>` (contiene dati utili, es. la nota
    salvata, il meteo);
  - si saltano le richieste di strumento (non hanno testo utile), le indicazioni del revisore e
    le bozze rifiutate (stessa regola di `messaggi_per_router`: la bozza che precede
    un'indicazione).
  Un solo messaggio evita problemi di alternanza dei turni con i template di Gemma. Forma esatta
  del testo lasciata al builder.
- **Aggiornato, non accumulato** (punto 03): il modello riceve il vecchio riassunto e scrive il
  riassunto **nuovo e completo**, che **sostituisce** il campo `riassunto`. I messaggi tolti
  escono dallo stato. Nello stato c'è sempre un solo riassunto e nessun messaggio di riassunto
  nella lista dei messaggi.
- **Come si tolgono i messaggi**: con `RemoveMessage` di LangGraph (già incluso, nessuna
  dipendenza), che funziona con il reducer `add_messages` dello stato. Dettaglio (un
  `RemoveMessage` per id oppure «togli tutto e rimetti i tenuti») lasciato al builder.
- **Riassunto vuoto** (testo vuoto o solo spazi): nessun taglio, il campo `riassunto` resta
  com'era, avviso nel log; il turno continua. Stessa regola delle risposte non valide di router
  e revisore: un problema del modello secondario non blocca la conversazione.
- **Errori di collegamento** (LM Studio spento, attesa scaduta, errore dal server): non si
  catturano, come per router e revisore; il turno fallisce con i messaggi di oggi
  (`Connessione fallita: ...` ecc.), la sessione continua, cronologia **e riassunto** restano
  com'erano.
- Risposta troncata dal limite di token (`max_tokens` del modello): con testo libero la libreria
  non solleva errori; il testo troncato si usa così com'è **[scelta mia]** (evento raro con un
  riassunto breve).

### 6.4 Chi legge il riassunto

- **Agente** (nodo `llm`): se il riassunto non è vuoto, il messaggio di sistema diventa
  `PROMPT_SISTEMA` seguito da un paragrafo
  `Cosa sai già della conversazione con l'utente (usalo per rispondere): <riassunto>`
  **[scelta mia per il testo]**. Un solo messaggio di sistema (i template di Gemma non accettano
  più messaggi di sistema). Con riassunto vuoto il messaggio di sistema è identico a oggi.
  *Modifica del 2026-11-13, approvata dall'utente durante le prove reali (Task 5):* il testo
  iniziale era `Riassunto della conversazione precedente: <riassunto>`; con quel testo gemma, in
  3 esecuzioni su 3 della prova del nome, rispondeva «Non mi hai detto come ti chiami» pur con il
  nome nel riassunto (quando tra i messaggi tenuti c'era una revisione); l'intestazione che chiede
  di usare il riassunto ha tenuto il nome in 6 chiamate su 6 nella prova di confronto.
- **Router**: stesso paragrafo dopo `prompt_router(ambito)`, perché il router deve riconoscere
  «il seguito di un argomento già presente nella conversazione» anche dopo la compressione
  **[scelta mia]**. Con riassunto vuoto identico a oggi.
- **Revisore**: **non** legge il riassunto (vede solo domanda e risposta, decisione dello
  step 2).
- `messaggi_per_router`, `domanda_e_risposta` e il nodo `strumenti` non cambiano: lavorano sui
  messaggi tenuti.

## 7. `Conversazione`

- Nuovo attributo `self.riassunto: str = ""` accanto a `self.cronologia`.
- `chiedi` passa al grafo anche `"riassunto": self.riassunto`; se il turno riesce aggiorna
  **insieme** `self.cronologia = risultato["messages"]` e `self.riassunto = risultato["riassunto"]`.
- Regola d'oro invariata: se il turno fallisce (anche durante il riassunto) cronologia e
  riassunto restano com'erano.
- Conseguenza: la compressione decisa in un turno riuscito resta per i turni successivi; in un
  turno fallito si ripeterà al turno dopo.

## 8. Log

Logger `assistente.grafo`, stile `chiave=valore` dei nodi precedenti **[scelta mia per il formato]**:

```
INFO assistente.grafo: riassunto non necessario messaggi=8 soglia=20
```

```
INFO assistente.grafo: Inizio chiamata al riassunto (messaggi=22 soglia=20 da_togliere=15)
INFO assistente.grafo: riassunto messaggi prima=22 dopo=7 caratteri=<lunghezza del riassunto>
```

```
INFO assistente.grafo: riassunto non necessario messaggi=23 soglia=20 da_togliere=0
```

```
WARNING assistente.grafo: riassunto vuoto: messaggi non compressi (messaggi=22)
```

- `prima` e `dopo` sono il numero di messaggi dello stato prima e dopo il taglio (evidenza del
  PDF). Il riassunto stesso non va nel log a livello INFO (può essere lungo); a livello DEBUG
  sì, troncato a 500 caratteri **[scelta mia]**.
- Le righe esistenti di router, agente, strumenti e revisore non cambiano.

## 9. Test automatici (senza LM Studio)

Con modelli simulati (`tests/finti.py`): un **riassuntore finto** (testi decisi dal test,
chiamate registrate; può riusare `ModelloFinto`).

- **Sotto la soglia** (evidenza PDF): cronologia corta → riassuntore **mai chiamato**, riga
  `riassunto non necessario`, messaggi e `riassunto` invariati.
- **Sopra la soglia**: riassuntore chiamato una volta; nello stato restano solo i messaggi da
  tenere; `riassunto` = testo del finto; log `riassunto messaggi prima=<p> dopo=<d>`.
- **Punto di taglio** (funzione pura): casi con taglio su una domanda; su una richiesta di
  strumento; su un `ToolMessage`; su un'indicazione del revisore e sulla bozza che la precede;
  turno unico lunghissimo (niente da togliere); `MESSAGGI_DA_TENERE=1`. In tutti: nessuna
  richiesta di strumento separata dal suo `ToolMessage`, i tenuti iniziano con una domanda
  dell'utente che non è un'indicazione.
- **Aggiornato, non accumulato**: due compressioni di seguito → il secondo riassuntore riceve il
  primo riassunto nel messaggio; il campo contiene solo il secondo testo; nessun messaggio di
  riassunto nella lista dei messaggi.
- **Trascrizione**: contiene `Utente:`, `Assistente:`, `Strumento <nome>:`; non contiene
  indicazioni, bozze rifiutate né richieste di strumento.
- **Chi legge il riassunto**: con riassunto non vuoto, la prima chiamata all'agente e quella al
  router hanno **un solo** `SystemMessage` che contiene il prompt di oggi e il riassunto; il
  revisore riceve gli stessi messaggi di oggi. Con riassunto vuoto i messaggi di sistema sono
  identici a oggi.
- **Nome dopo la compressione** (evidenza PDF, versione simulata): «Mi chiamo Luca» al primo
  turno, compressione con riassunto finto «L'utente si chiama Luca.», poi la chiamata all'agente
  contiene «Luca» nel messaggio di sistema anche se il primo turno non è più tra i messaggi.
- **Riassunto vuoto**: nessun taglio, avviso, il turno continua e risponde.
- **Errore di collegamento durante il riassunto**: `ErroreTurno` con `Connessione fallita: ...`;
  cronologia e riassunto di `Conversazione` invariati.
- **`Conversazione`**: dopo un turno con compressione `cronologia` e `riassunto` sono aggiornati
  insieme; il turno dopo passa al grafo il riassunto salvato.
- **Prompt del riassunto**: chiede di conservare le informazioni sull'utente; non nomina gli
  strumenti.
- **Configurazione**: predefiniti 20 e 6; valori non validi (0, negativo, testo) → errore con il
  nome della variabile; `MESSAGGI_DA_TENERE >= SOGLIA_RIASSUNTO` → errore.
- **Limite di ricorsione**: il test del caso peggiore dello step 2 passa con il nodo in più.
- I test esistenti si adattano al nuovo grafo (riassuntore finto che non viene chiamato perché le
  cronologie dei test sono sotto la soglia predefinita, `"riassunto": ""` nello stato) senza
  cambiare ciò che verificano.

## 10. Prove reali con LM Studio

Criterio: attenersi al PDF (prova reale con LM Studio; evidenze verificabili nei log o nei
test). Dettagli **[scelta mia]**.

**Prove reali automatiche** (`tests/test_reale.py`, con `PROVE_REALI=1`):
- le dodici esistenti devono continuare a passare con il nodo riassunto (con la soglia
  predefinita non dovrebbero mai superarla: sono turni singoli);
- nuova: **nome dopo la compressione** (evidenza minima del PDF), con una conversazione
  costruita con soglia bassa (es. `SOGLIA_RIASSUNTO=4`, `MESSAGGI_DA_TENERE=2`, impostati dal
  test, non dal `.env`): «Mi chiamo Luca», poi due domande dell'ambito (es. «Che ore sono?»,
  «Quanto fa 12 per 3?»), poi «Come mi chiamo?» → nel log almeno una riga
  `riassunto messaggi prima=... dopo=...`, il primo turno non è più nella cronologia, la
  risposta contiene «Luca».

**Prove manuali** (aggiunte alla checklist del README), con `SOGLIA_RIASSUNTO=4` e
`MESSAGGI_DA_TENERE=2` nel `.env`:
- prime domande: righe `riassunto non necessario` e nessuna chiamata in più;
- dopo qualche turno: `Inizio chiamata al riassunto` e `riassunto messaggi prima=... dopo=...`;
- «Come mi chiamo?» dopo la compressione: «Luca»;
- domanda con strumento dopo la compressione: funziona (il taglio non ha rotto i giri degli
  strumenti);
- LM Studio spento al momento di un riassunto: `Connessione fallita: ...`, la sessione continua.
Alla fine si rimettono i valori predefiniti nel `.env` (o si tolgono le due righe).

**Docker:** come negli step 1 e 2, solo verifica che non si rompa: `docker compose build` e
avvio fino a `Tu>`.

**Criterio di superamento** (come gli step 1 e 2): le prove reali si eseguono una volta; se una
fallisce si registra il punto esatto, si corregge **solo il prompt del riassunto** (gemma resta)
e si ripete l'intera serie. Lo step non si unisce in `dev` finché tutte le prove reali,
automatiche e manuali, non passano dopo l'ultima modifica. Gli esiti, anche intermedi, vanno nel
README con la data.

**Rischio noto:** gemma potrebbe scrivere un riassunto che perde il nome o che contiene
istruzioni («Rispondi…») invece di fatti. Se succede si registra il caso e si corregge il prompt
del riassunto con il via libera dell'utente.

## 11. Approcci considerati

1. **Modulo nuovo `assistente/riassunto.py`, gemello di `router.py` e `revisore.py`** —
   **scelto dall'utente**. Prompt, punto di taglio, trascrizione, testo per il messaggio di
   sistema e creazione del riassuntore in un file; in `grafo.py` il nodo, il campo `riassunto` e
   l'arco; in `conversazione.py` la conservazione del riassunto. Estende senza riscrivere e
   permette di testare il taglio da solo.
2. Compressione dentro `Conversazione`, prima di chiamare il grafo: meno codice nel grafo, ma il
   PDF chiede un **nodo** all'inizio del turno. Scartato.
3. Nodo di riassunto già pronto da una libreria (es. `langmem`): dipendenza nuova da concordare e
   niente parte didattica (taglio sicuro, campo aggiornato). Scartato.

## 12. Documentazione e Git

- **README:** variabili `SOGLIA_RIASSUNTO` e `MESSAGGI_DA_TENERE`, grafo con il riassunto,
  sottosezione «Formato dei log del riassunto», prova reale nuova, voci nuove della checklist,
  diagnosi (variabili non valide; nome perso dopo la compressione), esiti con data (solo comandi
  eseguiti davvero).
- **CLAUDE.md:** una riga nell'«Obiettivo» sul nodo riassunto all'inizio del turno, con le due
  variabili e il campo `riassunto`.
- **Git:** specifica e piano committati su `dev` (nel primo commit anche la casella «Task 6
  Step 5» del piano dello step 2 e, se l'utente ha già cancellato `archivio\note.sqlite`,
  «Task 5 Step 6»; decisione dell'utente); poi branch
  `feat/riassunto` da `dev`; Conventional Commits in italiano, un commit per incremento
  verificato; merge `--no-ff` in `dev` a step verificato e con conferma; nessun push.

## 13. Lasciato al builder

- Il testo esatto del prompt del riassunto, da tarare con le prove reali.
- La forma esatta della trascrizione e del messaggio con il riassunto precedente.
- Come togliere i messaggi con `RemoveMessage` (uno per id, oppure togli tutto e rimetti i tenuti).
- I nomi interni (funzioni, finti per i test) e come passare riassuntore, soglia e N a
  `costruisci_grafo` estendendolo (parametri nuovi in coda).
