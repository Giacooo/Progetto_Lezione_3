# Step 3, Riassunto della cronologia — Piano di implementazione

> **Per chi esegue:** SOTTO-SKILL OBBLIGATORIA: usare superpowers:subagent-driven-development (consigliata) o superpowers:executing-plans per eseguire il piano task per task. I passi usano le caselle (`- [ ]`) per il tracciamento.

**Obiettivo:** aggiungere all'inizio del turno un nodo LLM `riassunto` che, oltre `SOGLIA_RIASSUNTO` messaggi, sostituisce i messaggi vecchi con un riassunto (campo `riassunto` dello stato, aggiornato e non accumulato) e conserva gli ultimi `MESSAGGI_DA_TENERE`, senza mai separare una richiesta di strumento dal suo `ToolMessage`.

**Architettura:** nuovo modulo `assistente/riassunto.py`, gemello di `router.py` e `revisore.py` (prompt, punto di taglio, trascrizione, messaggi per il riassuntore, messaggio di sistema con il riassunto) → nodo `riassunto` in `assistente/grafo.py` tra START e `router`, campo di stato `riassunto`, riassunto in coda al messaggio di sistema di agente e router → `Conversazione` conserva il riassunto tra i turni → due variabili in `assistente/configurazione.py` → montaggio in `assistente/terminale.py` e `tests/test_reale.py`.

**Tecnologie:** Python 3.13, LangGraph 1.2.18 (`RemoveMessage` con il reducer `add_messages`), langchain-openai 1.7.3, pytest 9.1.1. Nessuna dipendenza nuova.

**Specifica:** `docs/superpowers/specs/2026-11-13-riassunto-design.md` (approvata il 2026-11-13). Chi esegue legge **entrambi** i documenti; le sezioni citate come §n sono della specifica.

Tutti i percorsi sono relativi a `assistente-laboratorio/`; i comandi si eseguono da PowerShell in quella cartella con `.\.venv\Scripts\python.exe`.

## Vincoli globali

- **Prima di ogni task: avviso all'utente** (che cosa, su quale branch, quali file) e **attesa del via libera**. Conferma esplicita anche prima di prove reali (LM Studio, Docker, rete), commit e merge. A task concluso, spuntare le caselle in questo file.
- Seguire il PDF alla lettera: niente resource, prompt MCP, API, streaming, salvataggio delle chat (§3). Lo stato riceve **un solo** campo nuovo (`riassunto: str`).
- Non cambiano: i testi di `PROMPT_SISTEMA`, `prompt_router`, `prompt_revisore`; i nodi `rifiuto`, `strumenti`, `revisore`; `messaggi_per_router`, `domanda_e_risposta`; le righe di log esistenti. Nei nodi `llm` e `router` cambia **solo** il messaggio di sistema (§6.4).
- Modello `google/gemma-4-e2b` per riassunto, router, agente e revisore; nessuna dipendenza nuova.
- Valori fissati dalla specifica:
  - `SOGLIA_RIASSUNTO` facoltativa, predefinita `20`, intero > 0; errore `SOGLIA_RIASSUNTO deve essere un intero maggiore di zero, non '<valore>'`;
  - `MESSAGGI_DA_TENERE` facoltativa, predefinita `6`, intero > 0; errore `MESSAGGI_DA_TENERE deve essere un intero maggiore di zero, non '<valore>'`;
  - controllo incrociato: errore `MESSAGGI_DA_TENERE (<n>) deve essere minore di SOGLIA_RIASSUNTO (<s>)` se `n >= s`;
  - si riassume solo se `numero di messaggi > SOGLIA_RIASSUNTO` (messaggi dello stato all'inizio del turno, domanda nuova compresa);
  - paragrafo del riassunto nei messaggi di sistema: `"\n\nRiassunto della conversazione precedente: <riassunto>"` in coda al prompt, un solo `SystemMessage`; con riassunto vuoto il prompt resta identico a oggi;
  - righe di log (logger `assistente.grafo`) della §8:
    - INFO `riassunto non necessario messaggi=<m> soglia=<s>` (sotto o uguale alla soglia);
    - INFO `riassunto non necessario messaggi=<m> soglia=<s> da_togliere=0` (sopra la soglia, niente da togliere);
    - INFO `Inizio chiamata al riassunto (messaggi=<m> soglia=<s> da_togliere=<t>)`;
    - INFO `riassunto messaggi prima=<p> dopo=<d> caratteri=<c>`;
    - DEBUG `riassunto testo=<riassunto troncato a 500 caratteri>`;
    - WARNING `riassunto vuoto: messaggi non compressi (messaggi=<m>)`.
- Codice sincrono; commenti didattici in italiano nello stesso stile dei file esistenti.
- Git: `feat/riassunto` da `dev`; staging **per percorsi espliciti**, mai `git add -A`/`git add .`; mai nello staging i file della Lezione 3 in radice (`../client.py`, `../requirements.txt`, `../.env.example`, `../.gitignore`), `HANDOFF*.md`, `PROMPT-ripresa-*.txt`; Conventional Commits in italiano terminati da `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; messaggio in un file nello scratchpad e `git commit -F <file>`; merge `--no-ff` in `dev` solo a step verificato e con conferma; nessun push.
- Prove reali: criterio della §10 (serie completa ripetuta dopo ogni correzione del prompt del riassunto; esiti, anche intermedi, nel README con data).

## Punti di attenzione (Review Focus)

1. **Taglio che cade su una richiesta di strumento, un `ToolMessage`, un'indicazione del revisore o la bozza che la precede**: va spostato indietro alla domanda dell'utente che apre il turno; i tenuti iniziano sempre con un `HumanMessage` che non è un'indicazione (§6.2). Test nel Task 2.
2. **Turno unico più lungo della soglia** (nessuna domanda dell'utente prima dell'ultima utile): niente da togliere, nessuna chiamata al modello (§6.1). Test nei Task 2 e 3.
3. **Due compressioni di seguito**: il secondo riassunto riceve il primo e lo sostituisce; nessun messaggio di riassunto nella lista (§6.3, punto 03 del PDF). Test nel Task 3.
4. **LM Studio spento proprio durante il riassunto**: `Connessione fallita: ...`, cronologia **e** riassunto di `Conversazione` invariati (§6.3, §7). Test nel Task 3.
5. **Riassunto vuoto** (solo spazi): nessun taglio, avviso, il turno continua e risponde (§6.3). Test nel Task 3.

---

## Task 0: Preparazione del branch

**Files:** `docs/superpowers/specs/2026-11-13-riassunto-design.md`, questo piano, `docs/superpowers/plans/2026-11-13-revisore.md` (casella «Task 6 Step 5»; «Task 5 Step 6» solo se l'utente ha già cancellato `archivio\note.sqlite`).

- [x] **Step 1:** spuntare nel piano del revisore la casella «Task 6 Step 5» (merge fatto, `ebd80ba`) e, se il file non esiste più, «Task 5 Step 6».
- [ ] **Step 2:** commit su `dev` con il via libera dell'utente: `git add docs/superpowers/specs/2026-11-13-riassunto-design.md docs/superpowers/plans/2026-11-13-riassunto.md docs/superpowers/plans/2026-11-13-revisore.md` → `docs: specifica e piano dello step 3, riassunto`.
- [ ] **Step 3:** `git switch -c feat/riassunto` da `dev`.
- [ ] **Step 4:** `.\.venv\Scripts\python.exe -m pytest -q` → atteso `268 passed, 12 skipped` (punto di partenza).

---

## Task 1: Soglia e messaggi da tenere in configurazione

**Files:**
- Modify: `assistente/configurazione.py` (`Configurazione`, `carica_configurazione`)
- Modify: `.env.example`
- Modify: `tests/test_configurazione.py`, `tests/test_modello.py` (costruisce `Configurazione` a mano: aggiungere i due campi con i predefiniti)

**Interfaces:**
- Produces: `Configurazione.soglia_riassunto: int` (predefinito 20), `Configurazione.messaggi_da_tenere: int` (predefinito 6), campi in coda dopo `max_revisioni`.

- [ ] **Step 1: test che falliscono** in `tests/test_configurazione.py`:
  - `test_configurazione_completa`: con `"SOGLIA_RIASSUNTO": "10"` e `"MESSAGGI_DA_TENERE": "4"` → `config.soglia_riassunto == 10`, `config.messaggi_da_tenere == 4`;
  - `test_default`: `config.soglia_riassunto == 20`, `config.messaggi_da_tenere == 6`;
  - `test_soglia_riassunto_non_valida` parametrizzato su `"zero"`, `"0"`, `"-1"` → `ErroreConfigurazione` con `match="SOGLIA_RIASSUNTO"`;
  - `test_messaggi_da_tenere_non_valido` parametrizzato su `"zero"`, `"0"`, `"-1"` → `ErroreConfigurazione` con `match="MESSAGGI_DA_TENERE"`;
  - `test_messaggi_da_tenere_non_minore_della_soglia` parametrizzato su `("5", "5")`, `("5", "8")` (soglia, da tenere) → `ErroreConfigurazione` con `match=r"MESSAGGI_DA_TENERE \(\d+\) deve essere minore di SOGLIA_RIASSUNTO \(5\)"`.
- [ ] **Step 2:** `.\.venv\Scripts\python.exe -m pytest tests/test_configurazione.py -q` → FAIL.
- [ ] **Step 3:** in `configurazione.py` i due campi e i controlli «3 ter» e «3 quater» identici a quello di `MAX_REVISIONI` (predefiniti `"20"` e `"6"`, messaggi dei Vincoli globali), poi il controllo incrociato. Aggiornare `tests/test_modello.py`.
- [ ] **Step 4:** `.env.example`, dopo `MAX_REVISIONI`: commento («Facoltativa: numero di messaggi della conversazione oltre il quale i più vecchi vengono riassunti.») e `SOGLIA_RIASSUNTO=20`; commento («Facoltativa: quanti messaggi recenti restano intatti dopo il riassunto (minore di SOGLIA_RIASSUNTO).») e `MESSAGGI_DA_TENERE=6`.
- [ ] **Step 5:** `.\.venv\Scripts\python.exe -m pytest -q` → tutti verdi.
- [ ] **Step 6: commit** — `git add assistente/configurazione.py .env.example tests/test_configurazione.py tests/test_modello.py` → `feat(configurazione): soglia del riassunto e messaggi da tenere`.

---

## Task 2: Modulo `assistente/riassunto.py`

**Files:**
- Create: `assistente/riassunto.py`
- Create: `tests/test_riassunto.py`

**Interfaces:**
- Consumes: `e_indicazione` da `assistente/revisore.py`.
- Produces (in `assistente/riassunto.py`):
  - `prompt_riassunto() -> str` — prompt di sistema (§6.3): riassumere in italiano, in modo breve, la conversazione tra utente e assistente; **conservare** le informazioni sull'utente (nome, preferenze, cose chieste di ricordare) e i fatti e risultati importanti; integrare il riassunto precedente con i messaggi nuovi; scrivere solo il riassunto, come fatti e non come istruzioni. **Non nomina gli strumenti** (né la parola «strument», né i loro nomi). Testo esatto lasciato al builder, da tarare con le prove reali.
  - `punto_di_taglio(messaggi: Sequence[AnyMessage], da_tenere: int) -> int` — indice del primo messaggio da tenere (§6.2): parte da `max(len(messaggi) - da_tenere, 0)` e torna indietro finché il messaggio non è un `HumanMessage` che non è un'indicazione; se non ne trova, restituisce `0` (niente da togliere).
  - `trascrizione(messaggi: Sequence[AnyMessage]) -> str` — una riga per messaggio: `Utente: <testo>`, `Assistente: <testo>` (solo `AIMessage` senza `tool_calls` e con testo), `Strumento <name>: <testo>` per i `ToolMessage`; salta richieste di strumento e indicazioni e, a ogni indicazione, toglie l'ultima riga `Assistente:` già scritta (la bozza rifiutata, stessa regola di `messaggi_per_router`). Righe unite con `"\n"`.
  - `messaggi_per_riassunto(precedente: str, da_togliere: Sequence[AnyMessage]) -> list[AnyMessage]` — `[SystemMessage(prompt_riassunto()), HumanMessage(testo)]`: un solo messaggio che contiene, se non vuoto, il riassunto precedente e poi la trascrizione (forma esatta lasciata al builder).
  - `sistema_con_riassunto(prompt: str, riassunto: str) -> str` — `prompt` se `riassunto` è vuoto o solo spazi, altrimenti `f"{prompt}\n\nRiassunto della conversazione precedente: {riassunto.strip()}"`.
  - Il riassuntore è il modello di LM Studio **senza** `bind_tools` e **senza** risposta strutturata: nessuna funzione `crea_...` (si passa `crea_modello(config)` così com'è, Task 4).

- [ ] **Step 1: test che falliscono** in `tests/test_riassunto.py` (usare `richiesta_ora`, `ORA_FISSA` da `finti` e `indicazione` da `assistente.revisore`):
  - `test_prompt_riassunto_conserva_l_utente_e_non_nomina_gli_strumenti`: `p = prompt_riassunto().lower()` → `"nome" in p`; nessuno tra `"strument"`, `"ora_corrente"`, `"calcola"`, `"meteo_citta"` in `p`.
  - `test_taglio_su_una_domanda`: `[H("a"), AI("b"), H("c"), AI("d"), H("e")]`, `da_tenere=3` → `2`.
  - `test_taglio_su_un_tool_message_torna_alla_domanda`: l'esempio della §6.2 (`[H("Mi chiamo Luca"), AI("Piacere, Luca"), H("Che ore sono?"), richiesta_ora("c1"), ToolMessage(ORA_FISSA, tool_call_id="c1"), AI("Sono le 12."), H("Come mi chiamo?")]`), `da_tenere=3` → `2`.
  - `test_taglio_su_una_richiesta_di_strumento_torna_alla_domanda`: stessi messaggi, `da_tenere=4` → `2`.
  - `test_taglio_su_indicazione_o_bozza_torna_alla_domanda`: `[H("a"), AI("b"), H("Che ore e che tempo?"), AI("Sono le 12."), indicazione("manca il meteo"), AI("Sono le 12 e piove."), H("Grazie")]` con `da_tenere=3` (parte dall'indicazione) e `da_tenere=4` (parte dalla bozza) → `2` in entrambi i casi.
  - `test_turno_unico_lungo_niente_da_togliere`: `[H("x"), richiesta_ora("c1"), ToolMessage(...,"c1"), richiesta_ora("c2"), ToolMessage(...,"c2"), AI("fine")]`, `da_tenere=2` → `0`.
  - `test_tenere_un_messaggio`: `[H("a"), AI("b"), H("c")]`, `da_tenere=1` → `2`.
  - `test_taglio_non_separa_mai_strumento_e_risultato`: per ogni `da_tenere` da 1 a `len(m)` sulla lista dell'esempio della §6.2 → `messaggi[taglio]` è un `HumanMessage` non indicazione **oppure** `taglio == 0`, e nessun `ToolMessage` tra i tenuti ha la sua richiesta tra i tolti.
  - `test_trascrizione`: `[H("Mi chiamo Luca"), AI("Piacere"), H("Che ore e che tempo?"), richiesta_ora("c1"), ToolMessage(ORA_FISSA, tool_call_id="c1", name="ora_corrente"), AI("Sono le 12."), indicazione("manca il meteo"), AI("Sono le 12 e piove.")]` → `"Utente: Mi chiamo Luca\nAssistente: Piacere\nUtente: Che ore e che tempo?\nStrumento ora_corrente: " + ORA_FISSA + "\nAssistente: Sono le 12 e piove."`.
  - `test_messaggi_per_riassunto`: `m = messaggi_per_riassunto("L'utente si chiama Luca.", [H("Che ore sono?"), AI("Sono le 12.")])` → `len(m) == 2`, `m[0]` è `SystemMessage` con `prompt_riassunto()`, `m[1]` è `HumanMessage` e contiene `"L'utente si chiama Luca."`, `"Utente: Che ore sono?"`, `"Assistente: Sono le 12."`; con precedente `""` il testo non contiene `"riassunto precedente"` (maiuscole ignorate).
  - `test_sistema_con_riassunto`: `sistema_con_riassunto("P", "") == "P"`, `sistema_con_riassunto("P", "  ") == "P"`, `sistema_con_riassunto("P", " R ") == "P\n\nRiassunto della conversazione precedente: R"`.
- [ ] **Step 2:** `.\.venv\Scripts\python.exe -m pytest tests/test_riassunto.py -q` → FAIL (modulo mancante).
- [ ] **Step 3:** scrivere `assistente/riassunto.py` secondo le Interfaces, con l'intestazione «COSA FA QUESTO FILE» come `router.py` e `revisore.py`.
- [ ] **Step 4:** `.\.venv\Scripts\python.exe -m pytest -q` → tutti verdi.
- [ ] **Step 5: commit** — `git add assistente/riassunto.py tests/test_riassunto.py` → `feat(riassunto): prompt, punto di taglio e trascrizione`.

---

## Task 3: Nodo `riassunto` nel grafo e riassunto nella `Conversazione`

**Files:**
- Modify: `assistente/grafo.py` (docstring e «mappa della metropolitana», `StatoTurno`, `costruisci_grafo`, nodi `llm` e `router` solo per il messaggio di sistema, nodo nuovo, arco, `recursion_limit`)
- Modify: `assistente/conversazione.py` (`self.riassunto`, stato iniziale, aggiornamento insieme alla cronologia)
- Modify: `tests/test_grafo.py`, `tests/test_conversazione.py`

**Interfaces:**
- Consumes: da Task 2 `punto_di_taglio`, `messaggi_per_riassunto`, `sistema_con_riassunto`.
- Produces:
  - `StatoTurno` con il campo nuovo `riassunto: str`;
  - `costruisci_grafo(modello, strumenti, max_passi, router, ambito, revisore, max_revisioni, riassuntore: Runnable, soglia_riassunto: int, messaggi_da_tenere: int)` — tre parametri nuovi in coda, obbligatori;
  - grafo: `START → riassunto → router`; gli altri archi invariati;
  - `recursion_limit = 2 + (max_revisioni + 1) * (2 * max_passi + 1) + 5`;
  - `Conversazione.riassunto: str` (iniziale `""`); `chiedi` invoca il grafo con `{"messages": [...], "passi": 0, "revisioni": 0, "riassunto": self.riassunto}` e, se il turno riesce, aggiorna insieme `self.cronologia` e `self.riassunto = risultato["riassunto"]`.
- Comportamento del nodo `riassunto`:
  1. `m = len(stato["messages"])`; se `m <= soglia_riassunto`: log `riassunto non necessario messaggi=<m> soglia=<s>`, restituisce `{}`;
  2. `taglio = punto_di_taglio(stato["messages"], messaggi_da_tenere)`; se `taglio == 0`: log `... da_togliere=0`, restituisce `{}`;
  3. log `Inizio chiamata al riassunto (messaggi=<m> soglia=<s> da_togliere=<taglio>)`; `testo = riassuntore.invoke(messaggi_per_riassunto(stato["riassunto"], stato["messages"][:taglio])).text.strip()`; gli errori **non** si catturano;
  4. testo vuoto: WARNING `riassunto vuoto: messaggi non compressi (messaggi=<m>)`, restituisce `{}`;
  5. altrimenti: log `riassunto messaggi prima=<m> dopo=<m - taglio> caratteri=<len(testo)>` e DEBUG `riassunto testo=<testo[:500]>`; restituisce `{"messages": [RemoveMessage(id=messaggio.id) for messaggio in stato["messages"][:taglio]], "riassunto": testo}`.
- Nodi `llm` e `router`: `SystemMessage(sistema_con_riassunto(PROMPT_SISTEMA, stato["riassunto"]))` e `SystemMessage(sistema_con_riassunto(prompt_router(ambito), stato["riassunto"]))`; il resto invariato. Il revisore non cambia.

- [ ] **Step 1: adattare gli helper** senza cambiare cosa verificano i test esistenti: `esegui(...)` in `test_grafo.py` riceve `riassuntore=None, soglia_riassunto=20, messaggi_da_tenere=6, riassunto=""` (predefinito `ModelloFinto([])`, che non viene chiamato perché le cronologie dei test sono sotto la soglia) e passa `"riassunto": riassunto` nello stato; `conversazione_con(...)` in `test_conversazione.py` riceve `riassuntore=None, soglia_riassunto=20, messaggi_da_tenere=6` e restituisce come oggi `(Conversazione, modello)`; la chiamata diretta di `test_limite_passi_lascia_la_cronologia_invariata` si adatta allo stesso modo.
- [ ] **Step 2: test nuovi che falliscono** in `tests/test_grafo.py` (cronologie costruite con `HumanMessage`/`AIMessage` alternati; `riassuntore = ModelloFinto([AIMessage("L'utente si chiama Luca.")])`):
  - `test_sotto_la_soglia_non_chiama_il_modello(caplog)` (evidenza PDF): cronologia di 4 messaggi, `soglia_riassunto=5` (5 messaggi con la domanda) → `riassuntore.chiamate == []`; log `"riassunto non necessario messaggi=5 soglia=5"`; `risultato["riassunto"] == ""`; tutti i messaggi presenti.
  - `test_sopra_la_soglia_riassume(caplog)` (evidenza PDF): cronologia `[H("Mi chiamo Luca"), AI("Piacere, Luca"), H("Che ore sono?"), AI("Sono le 12.")]`, domanda `"Come mi chiamo?"`, `soglia_riassunto=4`, `messaggi_da_tenere=2` → riassuntore 1 chiamata; il suo `HumanMessage` contiene `"Utente: Mi chiamo Luca"`; nel risultato non c'è più `"Mi chiamo Luca"` tra i messaggi e il primo messaggio è `H("Che ore sono?")`; `risultato["riassunto"] == "L'utente si chiama Luca."`; log `"Inizio chiamata al riassunto (messaggi=5 soglia=4 da_togliere=2)"` e `"riassunto messaggi prima=5 dopo=3 caratteri=24"`; le righe del riassunto vengono **prima** di `"Inizio chiamata al router"`.
  - `test_nome_usato_dopo_la_compressione` (evidenza PDF, simulata): stesso scenario → il `SystemMessage` della prima chiamata all'agente e quello della chiamata al router contengono `"Riassunto della conversazione precedente: L'utente si chiama Luca."` e sono gli **unici** `SystemMessage` della loro chiamata; i messaggi del revisore sono `messaggi_per_revisore("Come mi chiamo?", <risposta>)`.
  - `test_riassunto_aggiornato_non_accumulato`: stato iniziale con `riassunto="Riassunto vecchio."` e cronologia sopra la soglia → il riassuntore riceve `"Riassunto vecchio."` nel suo `HumanMessage`; `risultato["riassunto"] == "L'utente si chiama Luca."` (sostituito, non concatenato); nessun messaggio dei risultati contiene `"Riassunto vecchio."`.
  - `test_niente_da_togliere_non_chiama_il_modello(caplog)`: sopra la soglia ma con l'unica domanda dell'utente all'indice 0 (`taglio == 0`). Grafo costruito con `soglia_riassunto=2`, `messaggi_da_tenere=1`, modello `[AIMessage("fine")]`, e invocato **direttamente** (senza `esegui`) con `messages=[H("domanda"), richiesta_ora("c1"), ToolMessage(ORA_FISSA, tool_call_id="c1", name="ora_corrente")]`, `passi=1`, `revisioni=0`, `riassunto=""` → `riassuntore.chiamate == []`; log `"riassunto non necessario messaggi=3 soglia=2 da_togliere=0"`; ultima risposta `"fine"`.
  - `test_riassunto_vuoto_non_taglia(caplog)`: riassuntore `[AIMessage("   ")]`, scenario di `test_sopra_la_soglia_riassume` → WARNING `"riassunto vuoto: messaggi non compressi (messaggi=5)"`; tutti i 5 messaggi iniziali presenti; `risultato["riassunto"] == ""`; il turno risponde.
  - `test_taglio_non_separa_strumento_e_risultato_nel_grafo`: cronologia con un giro di strumento a cavallo del taglio (l'esempio della §6.2 senza l'ultima domanda), `soglia_riassunto=4`, `messaggi_da_tenere=3` → nei messaggi del risultato ogni `ToolMessage` ha la sua richiesta (stesso `tool_call_id`) presente, e il primo messaggio è un `HumanMessage`.
  - `test_nessun_errore_di_ricorsione_al_caso_peggiore`: il test esistente passa invariato (verifica del nuovo `recursion_limit`).
- [ ] **Step 3: test nuovi che falliscono** in `tests/test_conversazione.py`:
  - `test_riassunto_conservato_tra_i_turni`: `soglia_riassunto=4`, `messaggi_da_tenere=2`, riassuntore `[AIMessage("L'utente si chiama Luca."), AIMessage("L'utente si chiama Luca. Ha chiesto l'ora.")]`, risposte `[AIMessage("Piacere, Luca"), AIMessage("Sono le 12."), AIMessage("Ti chiami Luca."), AIMessage("Prego.")]`; quattro `chiedi`: «Mi chiamo Luca» (1 messaggio), «Che ore sono?» (3), «Come mi chiamo?» (5 > 4: compressione, si tolgono i 2 del primo turno), «Grazie» (di nuovo 5: compressione). Dopo il terzo: `chiedi` ha restituito `"Ti chiami Luca."`, `conv.riassunto == "L'utente si chiama Luca."`, nessun messaggio di `conv.cronologia` ha testo `"Mi chiamo Luca"` e il primo è `HumanMessage` «Che ore sono?». Dopo il quarto: il `HumanMessage` della seconda chiamata al riassuntore contiene `"L'utente si chiama Luca."` (riassunto salvato e passato al grafo) e `conv.riassunto == "L'utente si chiama Luca. Ha chiesto l'ora."`.
  - `test_errore_durante_il_riassunto_lascia_tutto_invariato`: `soglia_riassunto=4`, `messaggi_da_tenere=2`, riassuntore `[openai.APIConnectionError(request=RICHIESTA)]`; due turni riusciti, il terzo → `ErroreTurno` con `"Connessione fallita: controllare LM Studio, URL e porta."`; `conv.cronologia` identica a prima del terzo turno e `conv.riassunto == ""`.
- [ ] **Step 4:** `.\.venv\Scripts\python.exe -m pytest tests/test_grafo.py tests/test_conversazione.py -q` → FAIL sui test nuovi.
- [ ] **Step 5:** implementare in `assistente/grafo.py` e `assistente/conversazione.py` secondo le Interfaces; aggiornare docstring, schema e commenti con la stazione nuova.
- [ ] **Step 6:** `.\.venv\Scripts\python.exe -m pytest -q` → tutti verdi tranne quelli di `test_terminale.py`/`test_reale.py` che montano il grafo (Task 4), se falliscono.
- [ ] **Step 7: commit** — `git add assistente/grafo.py assistente/conversazione.py tests/test_grafo.py tests/test_conversazione.py` → `feat(grafo): riassunto della cronologia all'inizio del turno`.

---

## Task 4: Montaggio nell'applicazione e nelle prove reali

**Files:**
- Modify: `assistente/terminale.py` (`main`)
- Modify: `tests/test_reale.py` (fixture e una prova nuova)

**Interfaces:**
- Consumes: `costruisci_grafo(..., riassuntore, soglia_riassunto, messaggi_da_tenere)` (Task 3), `config.soglia_riassunto`, `config.messaggi_da_tenere` (Task 1).

- [ ] **Step 1:** in `main()`: `riassuntore = crea_modello(config)` (senza `bind_tools`, senza risposta strutturata) passato con `config.soglia_riassunto, config.messaggi_da_tenere` a `costruisci_grafo`. Commento: stesso modello, prompt diverso, nessuno strumento, testo libero.
- [ ] **Step 2:** in `tests/test_reale.py` una funzione `crea_conversazione(config) -> Conversazione` con lo stesso montaggio di `main()`, usata dalla fixture `conversazione`.
- [ ] **Step 3:** prova nuova `test_nome_usato_dopo_la_compressione(caplog)`: `config = dataclasses.replace(carica_configurazione(leggi_ambiente(Path.cwd())), soglia_riassunto=4, messaggi_da_tenere=2)`; `caplog.set_level(logging.INFO, logger="assistente")`; `chiedi` in sequenza «Mi chiamo Luca», «Che ore sono?», «Quanto fa 12 per 3?», poi `risposta = chiedi("Come mi chiamo?")` → almeno una riga che inizia con `"riassunto messaggi prima="`; nessun messaggio di `conv.cronologia` ha testo `"Mi chiamo Luca"`; `"luca" in risposta.lower()`.
- [ ] **Step 4:** `.\.venv\Scripts\python.exe -m pytest -q` → tutti verdi, prove reali `skipped` (diventano 13).
- [ ] **Step 5: commit** — `git add assistente/terminale.py tests/test_reale.py` → `feat(terminale): riassunto collegato all'applicazione`.

---

## Task 5: Prove reali con LM Studio (con conferma dell'utente)

**Files:** nessun file di codice; se serve tarare il riassunto, solo il testo di `prompt_riassunto` in `assistente/riassunto.py`.

- [ ] **Step 1:** chiedere conferma; LM Studio acceso con `google/gemma-4-e2b`, rete accesa (meteo).
- [ ] **Step 2:** `$env:PROVE_REALI = "1"; .\.venv\Scripts\python.exe -m pytest -m reale -v; Remove-Item Env:PROVE_REALI` → atteso **13 passed**. Registrare dal log della prova nuova le righe `riassunto messaggi prima=... dopo=...` e la risposta finale.
- [ ] **Step 3:** se una prova fallisce: registrare domanda, riassunto prodotto (log DEBUG o stampa nel test) e risposta; se il problema è il riassunto, correggere solo `prompt_riassunto` (con via libera), poi `pytest -q` e **tutta** la serie reale. Ogni correzione è un commit `fix(riassunto): ...` con via libera.
- [ ] **Step 4:** prove manuali guidate (§10) con `SOGLIA_RIASSUNTO=4` e `MESSAGGI_DA_TENERE=2` nel `.env` e `.\.venv\Scripts\python.exe -m assistente`: «Mi chiamo Luca» (`riassunto non necessario`); «Che ore sono?»; «Quanto fa 12 per 3?» (`Inizio chiamata al riassunto`, `riassunto messaggi prima=... dopo=...`); «Come mi chiamo?» (Luca); «Che tempo fa a Pordenone?» (strumento funzionante dopo la compressione); server fermo alla domanda successiva (`Connessione fallita: ...`, sessione continua), riavvio; `esci`. L'utente esegue, Claude legge l'output incollato. Alla fine l'utente rimette i valori predefiniti nel `.env`.
- [ ] **Step 5:** Docker (solo che non si rompa): `docker compose build` (Claude, con conferma) e `docker compose run --rm --name assistente-demo assistente` fino a `Tu>`, poi `esci` (utente).
- [ ] **Step 6:** far cancellare all'utente `archivio\note.sqlite`, se la prova delle note lo ha ricreato.

---

## Task 6: Documentazione, CLAUDE.md e merge

**Files:**
- Modify: `README.md`, `CLAUDE.md`, questo piano (caselle)

- [ ] **Step 1: README.md** — in «Configurazione» `SOGLIA_RIASSUNTO` (facoltativa, default 20) e `MESSAGGI_DA_TENERE` (facoltativa, default 6, minore della soglia); prove saltate «tredici»; descrizione dei test del riassunto; grafo con il riassunto e spiegazione (taglio sicuro, campo aggiornato, chi lo legge); sottosezione «Formato dei log del riassunto» con le righe della §8; in «Prove reali con LM Studio» la prova nuova; nella checklist le voci del Task 5 Step 4 (numerate dopo la 31); in «Diagnosi» le righe delle due variabili non valide, del controllo incrociato e del nome perso dopo la compressione (correggere `prompt_riassunto`, non il modello); in «Esiti delle prove reali» la sezione `Lezione 6 — step 3, riassunto (<data>)` con comandi eseguiti, esiti (anche intermedi) e cosa non è stato provato.
- [ ] **Step 2: CLAUDE.md** — nell'«Obiettivo» una riga: nodo riassunto all'inizio del turno (stesso modello, senza strumenti, testo libero), oltre `SOGLIA_RIASSUNTO` messaggi comprime i vecchi e tiene gli ultimi `MESSAGGI_DA_TENERE` con taglio alla domanda che apre il turno, campo di stato `riassunto` aggiornato e conservato da `Conversazione`, letto da agente e router; prompt in `assistente/riassunto.py`.
- [ ] **Step 3:** `.\.venv\Scripts\python.exe -m pytest -q` → tutti verdi.
- [ ] **Step 4: commit** — `git add README.md CLAUDE.md docs/superpowers/plans/2026-11-13-riassunto.md` → `docs: riassunto nel README e nel CLAUDE.md, esiti delle prove`.
- [ ] **Step 5:** revisione finale indipendente del branch (sotto-agente con il modello più capace), correzioni con TDD solo con il via libera dell'utente.
- [ ] **Step 6:** con la conferma dell'utente, `git switch dev` e `git merge --no-ff feat/riassunto` (`merge: lezione 6, step 3 riassunto`). Il merge di `dev` in `main` e il push solo se l'utente li chiede.
