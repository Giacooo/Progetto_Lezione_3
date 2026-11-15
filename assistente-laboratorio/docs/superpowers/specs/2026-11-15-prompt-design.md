# Specifica — Lezione 6, step 5: Prompt MCP e comandi `/prompts`, `/prompt`

Data: 2026-11-15. Stato: **approvata dall'utente il 2026-11-15**.
Fonte dei requisiti: `LLM_Lez_6.pdf` (slide «Step 4–5 — MCP: resource e prompt»: «Prompt: istruzioni
scelte dall'utente», «Step 5 · Prompt: comandi riusabili nella CLI», «Tre primitive, tre
responsabili diversi», «Metodo e consegna»), `assistente-laboratorio/CLAUDE.md`, decisioni
dell'utente prese nel brainstorming del 2026-11-15.

Le voci marcate **[scelta mia]** non sono state decise dall'utente: sono decisioni di chi ha
scritto la specifica, da controllare in lettura. Tutto il resto è richiesto dal PDF o deciso
dall'utente.

---

## 1. Intento

Dopo i tool (li attiva il modello) e la resource (la legge l'host, step 4), lo step 5 introduce la
terza primitiva MCP: il **prompt**, un modello di istruzioni con argomenti salvato sul server e
richiamato **dall'utente**, in modo esplicito. MCP non prevede un comando standard: i comandi li
definisce la CLI. Obiettivo del PDF: «un prompt richiamato dall'utente passa dal grafo come
qualsiasi altra domanda, compresi router, strumenti e revisore».

Parte dallo step 4 (preferenze) funzionante e unito in `dev` (merge `7e12270`).

## 2. Obiettivi (dal PDF, «Cosa realizzare»)

1. **01** — Prompt `spiega(argomento, livello)` e `riassumi_conversazione(stile)` sul server.
2. **02** — Comando `/prompts` con nome, descrizione e argomenti di ogni prompt.
3. **03** — Comando `/prompt nome argomento=valore`: i messaggi ottenuti si aggiungono alla
   cronologia e vanno al grafo.
4. **04** — Controllo nell'host rispetto a `prompts/list`: argomenti obbligatori mancanti o
   sconosciuti bloccano la richiesta, senza chiamare il modello.

Evidenze richieste dal PDF:
- `/prompt spiega argomento="Model Context Protocol" livello=base`: risposta adeguata al livello;
- `riassumi_conversazione` riassume i turni della sessione corrente;
- log con prompt richiamato, argomenti e messaggi ottenuti dal server.

Consegna (PDF, «Metodo e consegna»): test automatici, prova reale con LM Studio, README aggiornato e
commit; evidenza minima: «/prompts e /prompt funzionanti, con argomenti validati». Il `CLAUDE.md`
va aggiornato perché cambia l'architettura (prompt MCP, comandi della CLI).

## 3. Non obiettivi e anti-obiettivi

- **Non** si anticipano gli step successivi: niente servizio HTTP, niente salvataggio delle chat.
- **I prompt non sono strumenti**: non passano da `bind_tools`, il modello non può richiamarli
  (anti-obiettivo della slide «Errore comune»: «esporre tutto come tool»).
- **Nessun controllo dei valori** (decisione dell'utente, §4): `livello=pippo` non viene bloccato; i
  valori ammessi stanno solo nella descrizione degli argomenti.
- **Nessuna copia dell'elenco dei prompt** tenuta in memoria e nessuna lettura all'avvio (decisione
  dell'utente, §4): `main()` e l'avvio dello step 4 restano identici.
- **Il codice di router, revisore e riassunto non cambia** (difetti di altri step: si registrano,
  non si correggono qui). In particolare l'esempio del router «Spiegami come funziona un vulcano →
  fuori ambito» resta.
- **Nessun altro comando** oltre `/prompts` e `/prompt` (niente `/help`, `/tools`, ecc.).
- **Nessuna nuova dipendenza**: `fastmcp`, `mcp` e `langchain-mcp-adapters` (con `load_mcp_prompt`)
  sono già installati; `shlex` è della libreria standard.
- Il `.env` dell'utente **non si tocca** (lo aggiorna l'utente, §9).
- I limiti noti degli step 1–4 registrati nel README non si correggono.

## 4. Decisioni dell'utente (brainstorming del 2026-11-15)

1. **Router e `spiega` — strada A:** si allarga l'ambito **solo nella configurazione**
   (`AMBITO_AGENTE` in `assistente-laboratorio/.env.example` e nel README), senza toccare il codice
   del router. Scartate: B (non cambiare niente e registrare l'eventuale rifiuto come limite) e C
   (cambiare il prompt del router, codice dello step 1).
2. **Valori degli argomenti — strada 1:** solo i controlli del PDF (obbligatori mancanti,
   sconosciuti). Scartata la 2 (il server rifiuta i valori non ammessi).
3. **Lettura di `prompts/list` — approccio A:** a ogni comando, con una sessione stdio nuova (come
   strumenti e preferenze). Scartato B (una volta all'avvio, elenco in memoria).
4. Le parti «come si usano i comandi» e «testo dei prompt, log e prove» proposte nel brainstorming
   sono state lette dall'utente senza obiezioni; le singole scelte restano marcate **[scelta mia]**
   qui sotto.

## 5. Il server MCP: i due prompt

In `assistente/server_mcp.py`, con `@mcp.prompt`, nella forma del frammento del PDF. La docstring dà
la descrizione del prompt (prima riga) e quella degli argomenti (sezione `Args:`): FastMCP le
pubblica in `prompts/list` (verificato nel sorgente di `fastmcp` 3.4.11,
`prompts/function_prompt.py`). Entrambi restituiscono una stringa, cioè **un solo messaggio con
ruolo `user`**.

```python
@mcp.prompt
def spiega(argomento: str, livello: str = "base") -> str:
    """Spiega un argomento al livello richiesto.

    Args:
        argomento: concetto da spiegare
        livello: base, intermedio o avanzato
    """
    return f"Spiegami «{argomento}» a livello {livello}. ..."


@mcp.prompt
def riassumi_conversazione(stile: str = "sintetico") -> str:
    """Riassume i turni della conversazione della sessione corrente.

    Args:
        stile: sintetico o dettagliato
    """
    return f"Riassumi in stile {stile} i turni di questa conversazione ..."
```

- `argomento` obbligatorio; `livello` facoltativo con predefinito `base` (dal frammento del PDF).
- `stile` facoltativo con predefinito `sintetico` **[scelta mia]**, per simmetria con `livello`.
- **Testo di `spiega` [scelta mia]:** dopo «Spiegami «{argomento}» a livello {livello}.» una frase
  che dice che cosa vuol dire ogni livello: base = parole semplici, senza gergo tecnico, con un
  esempio concreto; intermedio = termini tecnici spiegati; avanzato = dettagli tecnici. Serve perché
  `gemma-4-e2b` si adatti al livello. Il testo esatto si tara con le prove reali.
- **Testo di `riassumi_conversazione` [scelta mia]:** «Riassumi in stile {stile} i turni di questa
  conversazione (domande e risposte), senza aggiungere informazioni nuove.» Il server **non** vede la
  conversazione: la vede l'agente, che ha la cronologia e, dopo una compressione dello step 3, il
  riassunto in coda al messaggio di sistema.
- I prompt **non** controllano i valori (§4.2): un valore fuori elenco finisce così com'è nel testo.
- I prompt non compaiono in `tools/list` (da verificare con un test).

## 6. Il collegamento MCP (host)

In `assistente/collegamento_mcp.py`, due funzioni **sincrone** sullo schema di
`leggi_preferenze_mcp`: `asyncio.run(...)`, `create_session(connessione)`, `initialize()`, richiesta,
chiusura; ogni errore di collegamento diventa `ErroreCollegamentoMCP` con il motivo «di fondo».

- **Elenco**: una sessione, `list_prompts()`, restituisce l'elenco dei prompt (oggetti `Prompt` di
  `mcp.types`: `name`, `description`, `arguments` con `name`, `description`, `required`).
- **Richiamo**: **una sola sessione** che fa, nell'ordine:
  1. `list_prompts()`;
  2. il controllo degli argomenti (funzione pura del §7) sull'elenco appena ricevuto; se fallisce, la
     sessione si chiude **senza** `prompts/get` e l'errore sale fino al terminale;
  3. `load_mcp_prompt(sessione, nome, arguments=argomenti)` (di `langchain-mcp-adapters`), che fa
     `prompts/get` e converte i messaggi in `HumanMessage`/`AIMessage`;
  4. restituisce i messaggi.

Errori:
- server non avviabile o caduto, oppure errore del server in `prompts/get` → `ErroreCollegamentoMCP`;
- controllo fallito → l'errore del controllo (§7), distinto da quello di collegamento.

Nessuno dei due casi chiama il modello.

## 7. Il nuovo modulo `assistente/prompt_mcp.py`

Funzioni **pure**, testabili senza server e senza modello **[scelta mia]** (nome del modulo e
suddivisione):

- **Lettura del comando** `/prompt nome chiave=valore ...` → `(nome, argomenti: dict[str, str])`.
  - Le parole si separano come in una shell: `shlex.split` in modalità POSIX, così
    `argomento="Model Context Protocol"` diventa un valore unico senza virgolette (come nel PDF).
  - Errori (ognuno con un messaggio chiaro) **[scelta mia]**: nome del prompt mancante
    (`/prompt` da solo); virgolette non chiuse; parola senza `=`; chiave vuota (`=valore`); valore
    vuoto (`livello=`); stessa chiave ripetuta.
  - Chiave e valore si separano al **primo** `=` (`argomento="a=b"` → valore `a=b`).
  - Le chiavi sono confrontate così come sono scritte (maiuscole comprese).
- **Controllo rispetto a `prompts/list`** (obiettivo 04):
  - nome del prompt non presente nell'elenco → errore con i nomi disponibili;
  - argomenti sconosciuti (non tra quelli del prompt) → errore con l'elenco degli argomenti
    ammessi;
  - argomenti obbligatori (`required=True`) mancanti → errore con i loro nomi.
  - **[scelta mia]** Si controllano prima gli sconosciuti, poi i mancanti; ogni messaggio elenca
    tutti i nomi in difetto, non solo il primo.
- **Testo di `/prompts`**: per ogni prompt, nome e descrizione; per ogni argomento, nome,
  «obbligatorio»/«facoltativo» e descrizione, tutti presi dall'elenco del server. Forma indicativa:

  ```
  spiega: Spiega un argomento al livello richiesto.
    argomento (obbligatorio): concetto da spiegare
    livello (facoltativo): base, intermedio o avanzato
  riassumi_conversazione: Riassume i turni della conversazione della sessione corrente.
    stile (facoltativo): sintetico o dettagliato
  ```

  Server senza prompt → una riga che lo dice.

Le eccezioni del controllo e della lettura sono un nuovo tipo in `assistente/errori.py`
**[scelta mia]**, figlio di `ErroreTurno`: così il ciclo del terminale le stampa già e la chat
continua, senza cambiare `ciclo()`.

## 8. La conversazione

In `assistente/conversazione.py`, un metodo nuovo che esegue un turno a partire da **messaggi già
pronti** invece che da un testo **[scelta mia]** (nome indicativo `chiedi_messaggi`); `chiedi(domanda)`
diventa la sua forma breve con `[HumanMessage(domanda)]`. Restano tutte le regole attuali:
- il grafo riceve `[*cronologia, *messaggi]`, `passi = 0`, `revisioni = 0` e il riassunto;
- cronologia e riassunto cambiano **solo se il turno riesce**;
- stessi errori del turno (`ErroreTurno` tradotti con `traduci_errore`).

Effetti voluti, già garantiti dal codice esistente (nessuna modifica a grafo, router, revisore,
riassunto):
- il messaggio del prompt è un `HumanMessage` come una domanda scritta a mano: il router lo
  classifica, l'agente può usare gli strumenti, il revisore lo considera «la domanda del turno»
  (`domanda_e_risposta`), il nodo riassunto taglia correttamente perché il turno si apre con un
  messaggio dell'utente;
- dopo il turno il messaggio compilato resta nella cronologia, come una domanda.

## 9. Il terminale e la configurazione

**Terminale** (`assistente/terminale.py`) **[scelta mia]**: `ciclo()` resta com'è. In `main()`,
invece di passare `conversazione.chiedi`, si passa una funzione che smista la riga:
- prima parola `/prompts` (esatta, minuscole) → elenco dei prompt (§6–§7), stampato; con parole in
  più → messaggio d'uso;
- prima parola `/prompt` (esatta, minuscole) → lettura, richiamo con controllo, poi turno nel
  grafo con i messaggi ottenuti; stampa la risposta;
- qualunque altra riga (anche un altro `/qualcosa`) → domanda normale, come oggi.

`/prompts` e i comandi bloccati **non** entrano nella cronologia e **non** chiamano il modello. Se
il server MCP non risponde durante un comando, compare `Server MCP non disponibile: <motivo>` e la
chat continua (come per un turno fallito); non si esce con il codice 3, che resta solo per
l'avvio.

**Configurazione** (decisione dell'utente, §4.1): in `assistente-laboratorio/.env.example` (il file
del progetto, **non** quello della radice della Lezione 3) e nell'esempio della tabella del README,
`AMBITO_AGENTE` si allunga con i concetti del corso, testo indicativo **[scelta mia]**:
`..., meteo, concetti del corso (LLM, agenti, MCP)`. Il testo esatto si tara con la prova reale di
`spiega`.

**Azione dell'utente prima delle prove reali**: le prove reali leggono il `.env` dell'utente, quindi
l'utente aggiorna lì `AMBITO_AGENTE`. Nel brainstorming è emerso che nel `.env` attuale la parola
«unità» è salvata con una codifica rovinata due volte (byte `C3 83 C6 92 C3 82 C2 A0` al posto di
`C3 A0`): finisce nel prompt del router e nel testo del rifiuto. È un problema del file locale
dell'utente, non del codice; la correzione la fa l'utente, si registra nel README tra i problemi di
diagnosi solo se l'utente lo chiede.

## 10. Log

Logger `assistente.collegamento_mcp`, livello INFO, distinto dalle righe dei tool
(`assistente.grafo`, `variant=... tool=...`) **[scelta mia per il formato]**:

```
prompts/list prompts=['spiega', 'riassumi_conversazione']
prompt richiamato nome=spiega argomenti={"argomento": "Model Context Protocol", "livello": "base"}
prompt messaggi ottenuti numero=1 [user] Spiegami «Model Context Protocol» a livello base. ...
```

- `argomenti` in JSON con `ensure_ascii=False` (come gli argomenti dei tool);
- i messaggi con ruolo e testo, al massimo 500 caratteri ciascuno;
- comando bloccato: WARNING `prompt rifiutato nome=<nome> motivo=<motivo>`, nessuna riga del grafo
  dopo (nessuna chiamata al modello);
- il server stampa già su stderr `Processing request of type ListPromptsRequest` /
  `GetPromptRequest`.

Le righe del turno che segue (`router categoria=...`, `variant=...`, `revisore coerente=...`) sono
quelle già esistenti: mostrano che il prompt passa dal grafo.

## 11. Test automatici (senza LM Studio)

- `tests/test_server_mcp.py` (client FastMCP in memoria, come i test esistenti): i due prompt sono
  in `prompts/list` con descrizione e argomenti (`argomento` obbligatorio, `livello` e `stile`
  facoltativi, descrizioni dalla docstring); `get_prompt` restituisce un messaggio `user` con
  argomento e livello nel testo, e con i predefiniti se omessi; i prompt non sono in `tools/list`.
- `tests/test_prompt_mcp.py` (nuovo): lettura del comando (virgolette, più argomenti, ognuno dei
  casi d'errore del §7); controllo (prompt sconosciuto, argomento sconosciuto, obbligatorio
  mancante, tutto valido, facoltativo omesso); testo di `/prompts` (anche elenco vuoto).
- `tests/test_collegamento_mcp.py`: elenco e richiamo con il server vero in sottoprocesso (come i
  test esistenti del collegamento); richiamo con argomento mancante → errore e **nessun**
  `prompts/get` (verificabile dai log o da un doppio); server non avviabile →
  `ErroreCollegamentoMCP`; righe di log del §10.
- `tests/test_conversazione.py`: il turno con messaggi pronti li manda al grafo dopo la cronologia,
  li conserva nella cronologia se il turno riesce e non cambia nulla se fallisce; `chiedi` continua
  a funzionare come prima.
- `tests/test_terminale.py`: lo smistamento — `/prompts` stampa l'elenco senza chiamare la
  conversazione; `/prompt` valido chiama il turno con i messaggi; `/prompt` non valido stampa
  l'errore e **il modello finto non viene chiamato**; un altro `/qualcosa` è una domanda normale;
  server giù durante un comando → messaggio e la chat continua. Le funzioni del collegamento si
  sostituiscono con doppi.
- `tests/test_grafo.py` (se serve): un turno aperto dal messaggio di un prompt passa da router,
  agente e revisore, e il revisore riceve come domanda il testo compilato.
- Regressione: tutti i test esistenti passano (`pytest -q`).

## 12. Prove reali con LM Studio

Da eseguire con l'esplicita conferma dell'utente (LM Studio, `google/gemma-4-e2b`), dopo che
l'utente ha aggiornato `AMBITO_AGENTE` nel proprio `.env` (§9):

1. **`spiega`** (in `tests/test_reale.py`): `/prompt spiega argomento="Model Context Protocol"
   livello=base` → nel log `router categoria=conversazione`, `revisore`, nessun rifiuto; risposta
   non vuota. L'«adeguatezza al livello» si osserva a mano (il test controlla ciò che è
   controllabile).
2. **`riassumi_conversazione`** (in `tests/test_reale.py`): dopo «Mi chiamo Luca» e «Quanto fa 45
   diviso 9?», il richiamo con `stile=sintetico` → la risposta cita Luca e il risultato 5.
3. **Prove manuali in locale** (voci della checklist del README numerate dopo la 44): `/prompts`;
   i tre errori (obbligatorio mancante, sconosciuto, prompt inesistente) senza righe del grafo nel
   log; i due prompt; `riassumi_conversazione` con `stile=dettagliato` mentre le preferenze dicono
   `sintetico` (si osserva quale prevale).
4. **Docker**: build, avvio fino a `Tu>`, un `/prompts` e un `/prompt spiega ...` nel container.
5. **Nessuna regressione**: tutta la serie reale esistente ripetuta.

Criterio: lo step non si unisce in `dev` finché le prove automatiche, reali e manuali non passano.
Se il router respinge ancora `spiega` con l'ambito allargato, o il modello non rispetta livello o
stile in modo affidabile, si registra il punto esatto e decide l'utente (per esempio la strada C
scartata nel §4.1); non si cambia modello.

## 13. Approcci considerati

- **Router e `spiega`:** (A) ambito allargato in configurazione [scelto]; (B) nessuna modifica,
  rifiuto registrato come limite [scartato: lascerebbe senza evidenza un punto del PDF]; (C) prompt
  del router modificato [scartato: codice dello step 1]; saltare il router per i prompt [scartato:
  il PDF dice «compresi router»].
- **Valori degli argomenti:** (1) solo controlli del PDF [scelto]; (2) valori controllati dal
  server [scartato: non richiesto dal PDF e non fatto dall'host tramite `prompts/list`].
- **Quando leggere `prompts/list`:** (A) a ogni comando [scelto: l'avvio resta identico, l'elenco è
  sempre quello del server, attesa uguale a quella degli strumenti]; (B) una volta all'avvio
  [scartato: una sessione in più all'avvio, modifiche a `main()` e un caso di errore nuovo da
  progettare].
- **Dove gestire `/prompt`:** nell'host, prima del grafo [scelto: il PDF dice che l'host ottiene i
  messaggi e li invia al grafo]; nodo del grafo [scartato]. `MultiServerMCPClient.get_prompt`
  [scartato: il progetto usa già `create_session` direttamente].

## 14. Documentazione e Git

- **README**: sezione «Prompt MCP e comandi della CLI»: i due prompt, `/prompts`, `/prompt` con la
  regola delle virgolette, i controlli e i loro messaggi, formato dei log, tabella delle tre
  primitive con la riga «Prompt» completata; esempio di `AMBITO_AGENTE` aggiornato; voci della
  checklist manuale; esiti delle prove reali con data; tabella «Diagnosi» (comando bloccato, server
  giù durante un comando).
- **`CLAUDE.md`**: riga «(lezione 6, step 5)» nell'«Obiettivo»; la riga di «Scelte tecniche» sulle
  primitive MCP resta valida.
- **`.env.example`** del progetto: `AMBITO_AGENTE` allungato (§9).
- Git: branch `feat/prompt` da `dev` **[scelta mia per il nome]**; questa specifica si committa su
  `dev` (come quella dello step 4), con conferma; Conventional Commits in italiano
  (`feat(prompt): ...`, `test(...)`, `docs: ...`) con la riga `Co-Authored-By`; staging per percorsi
  espliciti; mai nello staging i file della Lezione 3 nella radice, `HANDOFF*.md`,
  `HANDOFF_PROMPT.txt`, `PROMPT-ripresa-*.txt`; messaggio senza BOM; merge `--no-ff` in `dev` solo a
  step verificato e con conferma; nessun push.

## 15. Rischi e limiti da osservare

- Il router può respingere `spiega` anche con l'ambito allargato (esempio del vulcano nel suo
  prompt) e, meno probabile, `riassumi_conversazione` (dovrebbe rientrare in «domanda sull'assistente
  stesso o seguito di un argomento»). Si vede solo nelle prove reali.
- Lo stile chiesto dal prompt può scontrarsi con lo stile delle preferenze (step 4) nel messaggio
  di sistema.
- Il revisore vede il testo compilato del prompt come domanda: per `riassumi_conversazione` non può
  controllare che il riassunto sia fedele (vede solo domanda e risposta, step 2).
- `shlex` in modalità POSIX tratta `\` come carattere di escape: un valore con barre rovesciate
  (percorsi di Windows) va messo tra apici singoli. Si documenta nel README.

## 16. Lasciato al builder

- Nomi esatti delle funzioni, del metodo della conversazione e del nuovo tipo di errore.
- Il testo esatto dei due prompt e dei messaggi d'errore, purché dicano quale controllo è fallito e
  quali nomi.
- Come verificare nei test che, con un controllo fallito, non parte `prompts/get` né il modello.
- Se lo smistamento dei comandi sta in `terminale.py` o in `prompt_mcp.py`, purché `ciclo()` non
  cambi.
- Dove stanno nei file i punti dei test (§11).
