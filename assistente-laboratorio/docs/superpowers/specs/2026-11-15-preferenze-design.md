# Specifica — Lezione 6, step 4: Resource MCP `utente://preferenze`

Data: 2026-11-15. Stato: **bozza, da approvare dall'utente**.
Fonte dei requisiti: `LLM_Lez_6.pdf` (slide «Step 4–5 — MCP: resource e prompt»: «Resource:
contesto scelto dall'host», «Step 4 · Resource: preferenze dell'utente», «Tre primitive, tre
responsabili diversi», «Metodo e consegna»), `assistente-laboratorio/CLAUDE.md`, decisioni
dell'utente prese nel brainstorming del 2026-11-15.

Le voci marcate **[scelta mia]** non sono state decise dall'utente: sono decisioni di chi ha
scritto la specifica, da controllare in lettura. Tutto il resto è richiesto dal PDF o deciso
dall'utente.

---

## 1. Intento

Finora le istruzioni sul *come rispondere* (lingua, stile, fuso dell'orologio) sono scritte nel
codice (`PROMPT_SISTEMA`) o nel `.env` (`FUSO_ORARIO`). Lo step 4 introduce la prima primitiva MCP
diversa dai tool: una **resource**. Il server pubblica le preferenze dell'utente a un URI; **l'host**
(il programma, non il modello) le legge una volta a inizio sessione e le mette in cima al prompt
di sistema. Il modello le usa come contesto, senza «chiamarle». Obiettivo del PDF: cambiare il
comportamento dell'agente modificando un file, senza toccare il codice.

Parte dallo step 3 (riassunto) funzionante e unito in `dev` (commit `527676f`, poi `077ddec`).

## 2. Obiettivi (dal PDF, «Cosa realizzare»)

1. **01** — Resource `utente://preferenze` con lingua delle risposte, fuso orario predefinito e
   stile (sintetico o dettagliato).
2. **02** — Lettura da parte dell'host a inizio sessione e inserimento in cima al prompt di
   sistema.
3. **03** — La resource non compare tra i tool passati a `bind_tools`.
4. **04** — Resource non disponibile: valori predefiniti, segnalati nei log.

Evidenze richieste dal PDF:
- «Che ore sono?» usa il fuso predefinito senza chiederlo, provato con un fuso non ovvio come
  `America/New_York`;
- cambiando lingua o stile nel file, la sessione successiva risponde di conseguenza;
- la lettura della resource è visibile nei log, separata dalle chiamate ai tool.

Consegna (PDF, «Metodo e consegna»): test automatici, prova reale con LM Studio, README
aggiornato e commit; evidenza minima: «preferenze applicate; modifica del file senza modifica del
codice». Il `CLAUDE.md` va aggiornato perché cambia l'architettura (resource, prompt di sistema,
ruolo di `FUSO_ORARIO`).

## 3. Non obiettivi e anti-obiettivi

- **Non** si anticipano gli step successivi: niente prompt MCP (`spiega`, `riassumi_conversazione`,
  `/prompts`, `/prompt`: step 5), niente servizio HTTP, niente salvataggio delle chat.
- **Nessuno strumento** per leggere o cambiare le preferenze: la resource la legge solo l'host, e
  il modello non può chiamarla (anti-obiettivo: «esporre tutto come tool», slide «Errore comune»).
- **Nessuna rilettura** durante la sessione: si legge una volta a inizio sessione; per vedere una
  modifica si riavvia (è quello che chiede il PDF: «la sessione successiva»).
- **Nessuna nuova dipendenza** (il pacchetto `mcp` è già installato con `fastmcp` e
  `langchain-mcp-adapters`).
- Il testo dei prompt di router, revisore e riassuntore **non cambia**: la lingua delle preferenze
  riguarda solo le risposte dell'agente. **[scelta mia]** Di conseguenza il motivo del router e del
  revisore e il testo del riassunto restano in italiano anche con `lingua` diversa: sono testi
  interni, non risposte all'utente.
- Il rifiuto del router (`testo_rifiuto`) resta in italiano (testo fisso dello step 1).
- Anti-obiettivo: un file delle preferenze rotto non deve mai impedire l'avvio né far crollare il
  turno: si torna ai predefiniti e lo si dice nei log.

## 4. Decisioni dell'utente (brainstorming del 2026-11-15)

- **A — chi decide il fuso dell'orologio:** l'host passa il fuso delle preferenze a `ora_corrente`.
  `FUSO_ORARIO` resta come valore di ripiego (se la resource non è disponibile). Il modello non
  decide nulla. Scartata la variante B (parametro opzionale `fuso` in `ora_corrente`, con il prompt
  che dice al modello di usarlo): cambia lo strumento della lezione 4 e un modello piccolo
  potrebbe non passarlo.
- **Il file sta in `archivio/preferenze.json`**: cartella già ignorata da Git e montata come volume
  nel container, quindi la modifica sul PC vale subito anche in Docker, senza ricostruire
  l'immagine. Scartata `assistente/dati/preferenze.json` (versionato ma, in Docker, finirebbe
  nell'immagine e ogni modifica richiederebbe `docker compose build`).
- Il disegno complessivo (resource sul server, lettura dell'host, predefiniti, paragrafo in cima al
  prompt dell'agente, log, esclusioni) è stato approvato nel brainstorming.

## 5. Il file delle preferenze

`archivio/preferenze.json` (relativo alla cartella di lavoro, come le note; non versionato):

```json
{"lingua": "italiano", "fuso_orario": "America/New_York", "stile": "sintetico"}
```

- `lingua`: testo libero non vuoto (es. `italiano`, `inglese`, `francese`).
- `fuso_orario`: nome IANA valido (es. `Europe/Rome`, `America/New_York`).
- `stile`: esattamente `sintetico` o `dettagliato`.
- Le tre chiavi sono obbligatorie; chiavi in più sono ignorate **[scelta mia]**.
- **Predefiniti** quando la resource non è disponibile **[scelta mia]**: lingua `italiano`, fuso
  uguale a `FUSO_ORARIO`, stile `sintetico`. Sono gli stessi valori del comportamento di oggi
  («rispondi in italiano, in modo breve e chiaro», orologio nel fuso del `.env`), quindi senza
  file l'agente si comporta come prima.
- **Tutto o niente** **[scelta mia]**: se il file manca, non è JSON, non è un oggetto o anche una
  sola chiave manca o ha un valore non valido, si usano **tutti** i predefiniti (non una miscela).
  È più semplice da spiegare e da provare, e il WARNING dice quale controllo è fallito.
- Un file creato dall'utente su una copia pulita del progetto: il README ne mostra il contenuto da
  copiare. Non si versiona un file di esempio (meno file; il contenuto sta nel README).

## 6. Il server MCP

In `assistente/server_mcp.py`, come nel frammento del PDF:

```python
@mcp.resource("utente://preferenze", name="preferenze", mime_type="application/json")
def preferenze() -> str:
    """Preferenze dell'utente per le risposte."""
    return PERCORSO_PREFERENZE.read_text(encoding="utf-8")
```

- `PERCORSO_PREFERENZE = Path("archivio/preferenze.json")`, costante di modulo come
  `PERCORSO_NOTE` (i test la puntano a una cartella temporanea).
- Il server **non valida**: restituisce il testo del file. La validazione sta nell'host
  (§7), dove stanno anche i predefiniti. Se il file non esiste, la lettura della resource fallisce
  (errore MCP) e l'host passa ai predefiniti.
- La resource compare in `resources/list`, **non** in `tools/list`. Nessun tool nuovo: il catalogo
  resta di dieci strumenti sul server (più `ora_corrente` locale).

## 7. L'host: lettura e validazione

**Modulo nuovo `assistente/preferenze.py`** (funzioni pure, testabili senza LM Studio né server),
gemello di `router.py`, `revisore.py`, `riassunto.py`, con l'intestazione «COSA FA QUESTO FILE»:

- `Preferenze`: dataclass congelata con `lingua: str`, `fuso: ZoneInfo`, `stile: str`.
- `predefinite(fuso: ZoneInfo) -> Preferenze`: i predefiniti della §5 con il fuso di ripiego.
- `leggi_preferenze_da_testo(testo: str) -> Preferenze`: valida (§5) e solleva
  `ErrorePreferenze` con il motivo (`JSON non valido`, `manca la chiave 'stile'`, `fuso_orario non
  valido: 'Europa/Roma'`, `stile deve essere 'sintetico' o 'dettagliato', non 'lungo'`, ...).
  Eccezione nuova in `assistente/errori.py`.
- `prompt_agente(preferenze: Preferenze) -> str`: il prompt di sistema dell'agente con il
  paragrafo delle preferenze **in cima** (§8).

**Lettura della resource** in `assistente/collegamento_mcp.py` (l'altro punto asincrono, isolato
come la discovery): `leggi_preferenze_mcp(connessione: dict) -> str` apre una sessione stdio, fa
`resources/read` su `utente://preferenze`, restituisce il testo e chiude (`asyncio.run`). Gli errori
diventano `ErroreCollegamentoMCP` con il motivo. Il modo di leggere (`read_resource` sulla sessione
come nel PDF, oppure l'helper di `langchain-mcp-adapters`) lo sceglie il builder.

**Orchestrazione in `main()`** **[scelta mia]**, in quest'ordine:
1. discovery degli strumenti MCP (come oggi: se il server non c'è, `Server MCP non disponibile`,
   codice 3, senza contattare LM Studio);
2. lettura della resource; qualunque problema (`ErroreCollegamentoMCP`, `ErrorePreferenze`) →
   `predefinite(config.fuso_orario)` e WARNING (§9); la sessione parte comunque;
3. `crea_strumenti(preferenze.fuso)` per l'orologio locale, e la lista strumenti come oggi
   (orologio + strumenti MCP);
4. `costruisci_grafo(..., preferenze)`.

Leggere dopo la discovery distingue «server giù» (fatale, come oggi) da «resource non
disponibile» (non fatale, predefiniti): se la lettura fosse prima, le due cose sarebbero
indistinguibili.

`FUSO_ORARIO` resta variabile **obbligatoria** (è il ripiego e il fuso dei predefiniti); la sua
descrizione in `.env.example` e README dice «fuso di ripiego, usato se le preferenze non sono
disponibili». Nessuna nuova variabile d'ambiente.

## 8. Il prompt di sistema dell'agente

Le preferenze vanno **in cima** (PDF: «meglio in cima»), come un unico `SystemMessage`:

```
Preferenze dell'utente: rispondi in <lingua>. Stile: <descrizione dello stile>. Il fuso orario
predefinito è <fuso>: lo strumento ora_corrente lo usa già, non chiederlo all'utente.

<PROMPT_SISTEMA senza la frase su lingua e stile>
```

- Descrizione dello stile **[scelta mia, testo da tarare con le prove reali]**: `sintetico` →
  «risposte brevi e chiare, in poche frasi»; `dettagliato` → «risposte complete, con
  spiegazioni e passaggi».
- **Modifica di `PROMPT_SISTEMA`** **[scelta mia]**: oggi comincia con «Rispondi in italiano, in
  modo breve e chiaro.», che contraddirebbe una lingua o uno stile diversi nel file. Quella frase
  esce da `PROMPT_SISTEMA` ed entra nel paragrafo delle preferenze (con i predefiniti il senso
  complessivo resta lo stesso di oggi). Il resto di `PROMPT_SISTEMA` (strumenti, orologio, altri
  strumenti) non cambia. I test che confrontano `PROMPT_SISTEMA` (`tests/test_grafo.py`) si adattano
  a `prompt_agente(...)`.
- Il riassunto (step 3) resta **in coda**: `sistema_con_riassunto(prompt_agente(preferenze),
  riassunto)`. Un solo `SystemMessage`, come oggi.
- Il **router** (`prompt_router`), il **revisore** e il **riassuntore** non ricevono le preferenze.
- `costruisci_grafo` riceve un parametro nuovo in coda, obbligatorio, `preferenze: Preferenze`; il
  nodo `llm` usa `prompt_agente(preferenze)` al posto della costante. Nessun altro cambiamento al
  grafo, allo stato o a `Conversazione`.
- La resource **non** passa da `bind_tools`: `carica_strumenti_mcp` carica solo i tool, quindi
  non cambia (e un test lo verifica).

## 9. Log

Logger `assistente.collegamento_mcp` per la lettura, separato dalle righe dei tool
(`assistente.grafo`, `variant=... tool=...`):

- INFO `preferenze lette uri=utente://preferenze lingua=<l> fuso=<f> stile=<s>`;
- WARNING `preferenze non disponibili (<motivo>): valori predefiniti lingua=<l> fuso=<f> stile=<s>`.

La lettura compare **una volta**, prima della prima domanda (slide: «resources/read una volta,
prima della prima domanda»). Il server stampa già su stderr `Processing request of type
ReadResourceRequest`.

## 10. Test automatici (senza LM Studio)

- `tests/test_preferenze.py`: `leggi_preferenze_da_testo` con file valido; con ciascun difetto
  (non JSON, non un oggetto, chiave mancante, fuso inesistente, stile sconosciuto, lingua vuota) →
  `ErrorePreferenze` con il motivo; chiavi in più ignorate; `predefinite`; `prompt_agente`: il
  paragrafo è all'inizio, contiene lingua, descrizione dello stile e fuso, e **non** contiene
  «Rispondi in italiano» fisso; con predefiniti e con valori diversi (inglese, dettagliato,
  `America/New_York`).
- `tests/test_server_mcp.py`: la resource è in `resources/list` con URI `utente://preferenze` e
  tipo `application/json`; `read_resource` restituisce il testo del file temporaneo
  (`PERCORSO_PREFERENZE` puntato a `tmp_path`); **non** compare in `tools/list`; con file assente
  la lettura fallisce.
- `tests/test_collegamento_mcp.py` (o dove stanno i test del collegamento): `leggi_preferenze_mcp`
  con il server vero in sottoprocesso o in memoria e un file temporaneo; il log
  `preferenze lette ...`.
- `tests/test_grafo.py`: il `SystemMessage` della chiamata all'agente **inizia** con il paragrafo
  delle preferenze e termina, se c'è un riassunto, con il riassunto; router, revisore e
  riassuntore non lo ricevono; adattare i test esistenti su `PROMPT_SISTEMA`.
- `tests/test_terminale.py` (o equivalente): con le preferenze `America/New_York`, l'orologio
  locale costruito in `main()` risponde nel fuso delle preferenze; con la resource non disponibile,
  nel fuso di `FUSO_ORARIO` e con il WARNING. Se testare `main()` richiede troppa impalcatura, lo
  decide il builder (come nella `Ruling` del Task 4 dello step 3) e lo dichiara.
- Regressione: tutti i test esistenti passano (`pytest -q`), salvo gli adattamenti dichiarati.

## 11. Prove reali con LM Studio

Da eseguire con l'esplicita conferma dell'utente (LM Studio, `google/gemma-4-e2b`):

1. **Fuso non ovvio.** `archivio/preferenze.json` con `America/New_York`: «Che ore sono?» →
   `tool=ora_corrente ... result=...(America/New_York)` nel log, senza che il modello chieda il
   fuso. **Il test reale non deve distruggere il file dell'utente**: se esiste, lo salva e lo
   ripristina (o usa un file temporaneo se il builder trova il modo).
2. **Lingua e stile.** Cambiando `lingua` (es. `inglese`) e `stile` (`dettagliato`) nel file e
   riavviando, la risposta cambia di conseguenza (osservata a mano; il test automatico reale
   controlla ciò che è controllabile, per esempio il fuso, non la lingua del modello).
3. **Resource non disponibile.** Senza file: la sessione parte, WARNING nei log, orologio nel
   fuso di `FUSO_ORARIO`.
4. **Log.** La riga `preferenze lette ...` compare una volta, prima della prima domanda, e le
   righe `variant=...` dei tool restano distinte.
5. **Nessuna regressione.** Tutta la serie reale esistente (13 prove) ripetuta dopo ogni
   correzione del paragrafo delle preferenze.

Criterio: lo step non si unisce in `dev` finché tutte le prove automatiche, reali e manuali non
passano. Se il modello non rispetta lingua o stile in modo affidabile, è un limite di
`gemma-4-e2b` da registrare nel README (come gli altri), non motivo per cambiare modello.

## 12. Approcci considerati

- **Fuso dell'orologio:** (A) l'host lo passa a `ora_corrente` [scelto]; (B) parametro opzionale
  `fuso` nello strumento [scartato, §4].
- **Posizione del file:** `archivio/preferenze.json` [scelto]; `assistente/dati/` [scartato, §4];
  radice del progetto [scartato: sporcherebbe Git a ogni prova e non è montata in Docker].
- **Validazione:** nell'host [scelto: dove stanno i predefiniti, testabile senza server]; nel
  server [scartato: il server non conosce il fuso di ripiego e restituirebbe già «sistemato» ciò
  che l'host deve poter segnalare].
- **Predefiniti:** tutti o niente [scelto]; per chiave [scartato: più casi da provare e spiegare].
- **Lettura prima o dopo la discovery:** dopo [scelto, §7].

## 13. Documentazione e Git

- **README**: sezione «Preferenze dell'utente (resource MCP)»: contenuto del file e come crearlo,
  predefiniti, cosa succede se è rotto (tabella «Diagnosi»), formato dei log, tabella delle tre
  primitive (tool/resource/prompt: chi, quando, nei log), comandi di prova, voci della checklist
  manuale numerate dopo la 38, esiti delle prove reali con data, `FUSO_ORARIO` come ripiego, nota
  Docker (stessa cartella `archivio` montata).
- **`CLAUDE.md`**: riga dello step 4 nell'«Obiettivo» e aggiornamento di `ora_corrente` («fuso da
  `FUSO_ORARIO`, o dalle preferenze se disponibili»); la riga di «Scelte tecniche» sulle
  primitive MCP resta valida.
- **`.env.example`**: descrizione di `FUSO_ORARIO` come fuso di ripiego.
- **`.gitignore`**: `archivio/` è già ignorata, nulla da aggiungere.
- Git: branch `feat/preferenze` da `dev`; Conventional Commits in italiano (`feat(preferenze): ...`,
  `test(...)`, `docs: ...`); staging per percorsi espliciti; mai nello staging i file della Lezione 3
  nella radice, `HANDOFF*.md`, `PROMPT-ripresa-*.txt`; merge `--no-ff` in `dev` solo a step
  verificato e con conferma; nessun push.

## 14. Lasciato al builder

- Il modo esatto di leggere la resource (`session.read_resource` o helper dell'adattatore) e come
  testarlo senza sottoprocesso.
- Il testo esatto del paragrafo delle preferenze e delle descrizioni di stile, da tarare con le
  prove reali, e se le preferenze vanno in un solo blocco o in più righe.
- Dove stanno nei file i punti dei test (§10) e i nomi esatti delle funzioni dei test.
- Come far leggere un file temporaneo alle prove reali senza toccare quello dell'utente.
- Il messaggio esatto delle eccezioni, purché dica quale controllo è fallito (§7).
