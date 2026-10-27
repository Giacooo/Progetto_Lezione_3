# Assistente LangGraph con orologio e Docker Compose — Piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** applicazione da terminale il cui turno di conversazione è un grafo LangGraph
esplicito (nodo `llm`, nodo `strumenti`, arco condizionale, limite di passaggi) collegato a
LM Studio sull'host, con strumento orologio reale, cronologia di sessione e avvio con
Docker Compose.

**Architecture:** pacchetto `assistente/` con moduli piccoli: configurazione, strumenti,
collegamento al modello, grafo, conversazione (cronologia e errori del turno) e terminale.
Il grafo riceve un modello già "legato" agli strumenti, così nei test si sostituisce con un
modello finto a risposte predefinite. La cronologia vive in `Conversazione` e cambia solo
dopo un turno riuscito.

**Tech Stack:** Python 3.13, `langgraph==1.2.18`, `langchain-openai==1.7.3`
(porta `langchain-core` 1.7.x), `python-dotenv==1.2.4`, `tzdata==2026.5`, `pytest==9.1.1`
(solo sviluppo). Versioni verificate con `pip index versions` il 2026-10-27.

**Spec:** `assistente-laboratorio/docs/superpowers/specs/2026-10-26-assistente-langgraph-orologio-design.md`

## Global Constraints

- Lavorare solo in `lezione_3/repo-lab-llm/assistente-laboratorio/`, branch `main`; non leggere né copiare il codice della lezione 3 alla radice.
- Tutti i percorsi del piano sono relativi a `assistente-laboratorio/`; i comandi si eseguono da lì.
- Python sincrono; separazione tra grafo, collegamento al modello, strumenti e terminale.
- URL e id del modello solo da variabili d'ambiente; nessun id di modello nel codice.
- Variabili: `LM_BASE_URL`, `LM_MODEL`, `FUSO_ORARIO` obbligatorie; `MAX_PASSI` (default `5`), `LOG_LEVEL` (default `INFO`) facoltative. L'ambiente ha precedenza su `.env`.
- Richiesta al modello: temperatura `0.2`, `reasoning_effort="none"`, `max_tokens=1024`, `timeout=120` s, `max_retries=0`.
- Testi fissati dalla specifica (copiare alla lettera):
  - «Limite di passaggi raggiunto: riprova con una domanda diversa.»
  - «Connessione fallita: controllare LM Studio, URL e porta.»
  - «Attesa scaduta: controllare server, carico e tempi.»
  - «Errore dal server:» seguito da codice e testo ricevuto.
- Prompt `Tu> `; comandi di uscita `esci`, Ctrl+C, EOF; righe vuote ignorate.
- Risultato dell'orologio: `AAAA-MM-GGTHH:MM:SS+HH:MM (Nome/Fuso)`, fuso solo da `FUSO_ORARIO`.
- Log con `logging` su stderr, formato `%(levelname)s %(name)s: %(message)s`, logger sotto `assistente.*`.
- Comandi della documentazione per PowerShell; nel piano gli stessi comandi sono scritti come li esegue Claude (Git Bash).
- Commit Conventional Commits in italiano, firmati con l'identità già configurata, che terminano con la riga `Co-Authored-By` della sessione; staging selettivo; mai `.env`, `.venv`, cache. Niente push.

## Review Focus

1. **`.env` sbagliato**: `load_dotenv()` senza percorso risale le cartelle e troverebbe il `.env` della lezione 3 alla radice della repository → si carica solo `./.env` della cartella corrente (test in Task 3).
2. **Risposta vuota del modello** (gemma che consuma i token ragionando): non va stampata una riga vuota come se fosse una risposta → turno fallito con «Il modello ha restituito una risposta vuota.» e cronologia invariata (test in Task 4).
3. **Strumento inesistente richiesto dal modello**: il programma non deve andare in crash → messaggio di tool «Strumento sconosciuto: <nome>» associato alla richiesta, il modello riceve il ritorno (test in Task 6).
4. **`MAX_PASSI` non numerico o minore di 1**: errore di configurazione chiaro all'avvio, non un traceback a metà sessione (test in Task 3).
5. **Ctrl+C durante l'attesa del modello** (non solo al prompt): chiusura pulita come al prompt (test in Task 2/4).

## Problema aperto rilevato durante la pianificazione

Il 2026-10-27, con LM Studio attivo, `google/gemma-4-e2b` risponde regolarmente senza
strumenti, ma **ogni richiesta che contiene `tools` fallisce con HTTP 400**:
`Error rendering prompt with jinja template: "Cannot call something that is not a function: got UndefinedValue"`.
È il template del modello in LM Studio, non il nostro codice (prova fatta con richiesta HTTP
diretta, con e senza messaggio di sistema, con e senza parametri). Non cambia l'architettura
(il modello è configurabile), ma blocca la prova reale dell'orologio: va risolto con l'utente
al Task 6 (template corretto da LM Studio, oppure altro modello presente con supporto ai tool,
es. `qwen3-8b`). Fino ad allora l'applicazione mostrerà «Errore dal server: 400 ...».

## Struttura dei file

| File | Responsabilità |
|---|---|
| `requirements.txt` | dipendenze dell'applicazione (anche per Docker) |
| `requirements-dev.txt` | `-r requirements.txt` + `pytest` |
| `pytest.ini` | `testpaths = tests`, `pythonpath = .`, marcatore `reale` |
| `.env.example` | configurazione di esempio senza credenziali |
| `assistente/__init__.py` | vuoto |
| `assistente/__main__.py` | `from assistente.terminale import main` → `raise SystemExit(main())` |
| `assistente/errori.py` | `ErroreConfigurazione`, `ErroreTurno` |
| `assistente/configurazione.py` | lettura e validazione delle variabili; configurazione del logging |
| `assistente/strumenti.py` | strumento `ora_corrente` |
| `assistente/modello.py` | `ChatOpenAI` verso LM Studio; traduzione degli errori |
| `assistente/grafo.py` | stato, nodi, instradamento, compilazione |
| `assistente/conversazione.py` | cronologia di sessione ed esecuzione del turno |
| `assistente/terminale.py` | ciclo `Tu> `, avvio, uscita |
| `tests/finti.py` | `ModelloFinto` con risposte predefinite |
| `tests/test_*.py` | test senza modello |
| `tests/test_reale.py` | prova con LM Studio, solo con `PROVE_REALI=1` |
| `Dockerfile`, `.dockerignore`, `compose.yaml` | avvio con Docker Compose |
| `README.md` | configurazione, avvio, test, prove reali, diagnosi |

---

## Incremento 1 — Grafo con risposta fissa (slide 5–6)

### Task 1: Struttura del progetto e primo grafo senza LLM

**Files:**
- Create: `requirements.txt`, `requirements-dev.txt`, `pytest.ini`, `assistente/__init__.py`, `assistente/grafo.py`, `tests/test_grafo.py`, `README.md`

**Interfaces:**
- Produces: `assistente.grafo.costruisci_grafo_fisso() -> CompiledStateGraph`, stato `StatoFisso(TypedDict)` con `user_text: str`, `answer: str`; `RISPOSTA_FISSA = "Il grafo è in esecuzione."`.

- [ ] **Step 1: File di progetto e venv.** `requirements.txt` con le quattro dipendenze fissate dal Tech Stack; `requirements-dev.txt` con `-r requirements.txt` e `pytest==9.1.1`; `pytest.ini` (`[pytest]`, `testpaths = tests`, `pythonpath = .`, `markers = reale: prova con LM Studio attivo`). Poi:
  Run: `py -3.13 -m venv .venv && .venv/Scripts/python -m pip install -r requirements-dev.txt`
  Expected: installazione completata; `.venv/Scripts/python -m pip show langgraph` riporta `1.2.18`.
- [ ] **Step 2: Test che fallisce.**

```python
def test_grafo_fisso_restituisce_la_risposta_prevista():
    chiamate = []
    grafo = costruisci_grafo_fisso(osservatore=chiamate.append)
    risultato = grafo.invoke({"user_text": "ciao"})
    assert risultato["answer"] == "Il grafo è in esecuzione."
    assert risultato["user_text"] == "ciao"
    assert chiamate == ["ciao"]          # nodo eseguito una sola volta, ha letto l'input
```

  (`osservatore: Callable[[str], None] | None = None` è chiamato dal nodo con `user_text`: serve solo a provare che il nodo gira una volta.)
- [ ] **Step 3:** Run `.venv/Scripts/python -m pytest tests/test_grafo.py -v` → FAIL (import).
- [ ] **Step 4: Implementare** `StatoFisso`, nodo `rispondi(stato) -> {"answer": RISPOSTA_FISSA}`, `costruisci_grafo_fisso(osservatore=None)` con `StateGraph` → `add_node` → `START→rispondi→END` → `compile()`.
- [ ] **Step 5:** Run i test → PASS.
- [ ] **Step 6: README iniziale**: scopo, creazione del venv e installazione (PowerShell: `py -3.13 -m venv .venv`, `.\.venv\Scripts\Activate.ps1`, `python -m pip install -r requirements-dev.txt`), `python -m pytest`.
- [ ] **Step 7: Commit** `feat(grafo): aggiunge il primo grafo con risposta fissa` (requirements, pytest.ini, assistente/, tests/, README.md).

### Task 2: Terminale sul grafo fisso

**Files:**
- Create: `assistente/terminale.py`, `assistente/__main__.py`, `tests/test_terminale.py`

**Interfaces:**
- Produces: `ciclo(rispondi: Callable[[str], str], leggi: Callable[[str], str] = input, scrivi: Callable[[str], None] = print) -> None`; `main() -> int`. In questo task `main` usa il grafo fisso; dal Task 4 usa `Conversazione.chiedi`.

- [ ] **Step 1: Test che falliscono** (con `leggi` che restituisce righe da una lista e poi solleva `EOFError`, e `scrivi` che accumula):
  - `test_risponde_e_chiude_con_esci`: righe `["ciao", "esci"]` → `rispondi` chiamato con `"ciao"`, la risposta è scritta, nessun'altra chiamata.
  - `test_ignora_righe_vuote`: `["", "   ", "esci"]` → `rispondi` mai chiamato.
  - `test_eof_chiude_senza_errori`: `[]` → ritorna normalmente.
  - `test_ctrl_c_al_prompt_chiude`: `leggi` solleva `KeyboardInterrupt` → ritorna normalmente.
  - `test_ctrl_c_durante_la_risposta_chiude`: `rispondi` solleva `KeyboardInterrupt` → ritorna normalmente (Review Focus 5).
  - `test_esci_ignora_maiuscole_e_spazi`: `["  ESCI "]` → chiude.
- [ ] **Step 2:** Run `.venv/Scripts/python -m pytest tests/test_terminale.py -v` → FAIL.
- [ ] **Step 3: Implementare** `ciclo` (prompt `Tu> `, strip, `esci` case-insensitive, `EOFError`/`KeyboardInterrupt` → saluto «Arrivederci.» e ritorno) e `main()` che collega `ciclo` al grafo fisso; `__main__.py`.
- [ ] **Step 4:** Run tutti i test → PASS.
- [ ] **Step 5: Verifica reale.** Run `printf 'ciao\nesci\n' | .venv/Scripts/python -m assistente` → stampa «Il grafo è in esecuzione.» e «Arrivederci.».
- [ ] **Step 6:** README: sezione «Avvio» con `python -m assistente`. **Commit** `feat(terminale): collega il ciclo da terminale al grafo`.

---

## Incremento 2 — Collegamento a LM Studio e cronologia

### Task 3: Configurazione e logging

**Files:**
- Create: `assistente/errori.py`, `assistente/configurazione.py`, `.env.example`, `tests/test_configurazione.py`
- Modify: `assistente/terminale.py`

**Interfaces:**
- Produces: `class ErroreConfigurazione(Exception)`, `class ErroreTurno(Exception)` in `errori.py`;
  `@dataclass(frozen=True) class Configurazione: lm_base_url: str; lm_model: str; fuso_orario: ZoneInfo; max_passi: int; log_level: str`;
  `carica_configurazione(ambiente: Mapping[str, str]) -> Configurazione`;
  `leggi_ambiente(cartella: Path) -> dict[str, str]` (valori di `cartella/.env` via `dotenv_values`, sovrascritti da `os.environ`);
  `configura_log(livello: str) -> None` (stderr, formato dei Global Constraints).

- [ ] **Step 1: Test che falliscono:**
  - `test_configurazione_completa`: ambiente con le tre obbligatorie + `MAX_PASSI="3"` → campi corretti, `fuso_orario == ZoneInfo("Europe/Rome")`, `max_passi == 3`.
  - `test_default`: senza `MAX_PASSI`/`LOG_LEVEL` → `5` e `"INFO"`.
  - `test_variabile_mancante` (parametrizzato sulle tre obbligatorie, anche valore vuoto) → `ErroreConfigurazione` il cui messaggio contiene il nome della variabile.
  - `test_fuso_non_valido`: `FUSO_ORARIO="Europa/Roma"` → `ErroreConfigurazione` con «FUSO_ORARIO».
  - `test_max_passi_non_valido` (parametrizzato `"zero"`, `"0"`, `"-1"`) → `ErroreConfigurazione` con «MAX_PASSI» (Review Focus 4).
  - `test_log_level_non_valido`: `"CHIACCHIERE"` → `ErroreConfigurazione`.
  - `test_ambiente_prevale_su_env` (con `tmp_path` e `monkeypatch.setenv`): `.env` con `LM_MODEL=dal-file`, ambiente `LM_MODEL=da-ambiente` → `"da-ambiente"`.
  - `test_legge_solo_env_della_cartella`: `.env` nella cartella madre e non in `tmp_path/figlia` → la chiave non compare (Review Focus 1).
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3: Implementare.** Nel terminale: `main()` legge `leggi_ambiente(Path.cwd())`, chiama `carica_configurazione` e `configura_log`; su `ErroreConfigurazione` scrive su stderr `Configurazione non valida: <messaggio>` e ritorna `2`.
- [ ] **Step 4:** Run tutti i test → PASS.
- [ ] **Step 5:** `.env.example`:

```
# Copiare in .env e completare. L'id del modello si legge con:
# (Invoke-RestMethod "http://localhost:1234/v1/models").data | Select-Object id
LM_BASE_URL=http://localhost:1234/v1
LM_MODEL=ID_MODELLO_REALE
FUSO_ORARIO=Europe/Rome
MAX_PASSI=5
LOG_LEVEL=INFO
```

  Creare il `.env` locale (non versionato) con `LM_MODEL=google/gemma-4-e2b`.
- [ ] **Step 6: Verifica reale.** Run `LM_MODEL= .venv/Scripts/python -m assistente < /dev/null; echo $?` → «Configurazione non valida: ... LM_MODEL ...», codice `2`.
- [ ] **Step 7:** README: sezione «Configurazione». **Commit** `feat(configurazione): legge e valida la configurazione da ambiente e .env`.

### Task 4: Nodo LLM, cronologia ed errori del modello

**Files:**
- Create: `assistente/modello.py`, `assistente/conversazione.py`, `tests/finti.py`, `tests/test_modello.py`, `tests/test_conversazione.py`
- Modify: `assistente/grafo.py` (il grafo fisso viene sostituito), `tests/test_grafo.py`, `assistente/terminale.py`

**Interfaces:**
- Consumes: `Configurazione`, `ErroreTurno`.
- Produces:
  - `modello.crea_modello(config: Configurazione) -> ChatOpenAI` con i parametri dei Global Constraints e `api_key="lm-studio"`.
  - `modello.traduci_errore(exc: Exception) -> ErroreTurno | None`: `openai.APITimeoutError` → messaggio di attesa scaduta (va controllato **prima** di `APIConnectionError`, di cui è sottoclasse); `APIConnectionError` → connessione fallita; `APIStatusError` → `f"Errore dal server: {exc.status_code} {exc.response.text}"`; altro → `None`.
  - `grafo.StatoTurno(TypedDict)`: `messages: Annotated[list[AnyMessage], add_messages]`, `passi: int`; `grafo.PROMPT_SISTEMA: str` (italiano; dice di usare lo strumento `ora_corrente` per data, ora e giorno); `grafo.costruisci_grafo(modello: Runnable) -> CompiledStateGraph` con `START → llm → END`. Il nodo `llm` chiama `modello.invoke([SystemMessage(PROMPT_SISTEMA), *stato["messages"]])`, logga inizio/fine con il numero del passo, restituisce `{"messages": [risposta], "passi": stato["passi"] + 1}`.
  - `conversazione.Conversazione(grafo)`: attributo `cronologia: list[BaseMessage]`; `chiedi(domanda: str) -> str` invoca il grafo con `{"messages": [*cronologia, HumanMessage(domanda)], "passi": 0}`; in caso di eccezione tradotta da `traduci_errore` solleva `ErroreTurno`; se la risposta finale ha testo vuoto solleva `ErroreTurno("Il modello ha restituito una risposta vuota.")`; solo in caso di successo sostituisce `cronologia` con i messaggi restituiti e ritorna il testo finale.
  - `tests/finti.ModelloFinto(risposte: list[AIMessage | BaseException])`: `invoke(messaggi)` registra la copia dei messaggi in `self.chiamate` e restituisce (o solleva) la risposta successiva.

- [ ] **Step 1: Test che falliscono.**
  - `test_modello.py`:
    - `test_crea_modello_usa_la_configurazione`: `crea_modello(cfg)._get_request_payload([HumanMessage("x")])` contiene `model == cfg.lm_model`, `temperature == 0.2`, `reasoning_effort == "none"`, `max_tokens == 1024`; `str(modello.openai_api_base) == cfg.lm_base_url`.
    - `test_traduci_errori`: con `httpx.Request("POST", "http://x")` costruire `APIConnectionError(request=...)`, `APITimeoutError(request=...)`, `APIStatusError("x", response=httpx.Response(404, request=..., text="model not found"), body=None)` → i tre messaggi esatti (il terzo `"Errore dal server: 404 model not found"`); `ValueError()` → `None`.
  - `test_grafo.py` (riscritto):
    - `test_domanda_ordinaria_una_chiamata`: `ModelloFinto([AIMessage("Parigi")])` → una chiamata; primo messaggio inviato è `SystemMessage` con `PROMPT_SISTEMA`; risultato `messages[-1].content == "Parigi"`, `passi == 1`.
  - `test_conversazione.py`:
    - `test_cronologia_dopo_due_turni`: risposte `"Ciao Luca"`, `"Ti chiami Luca"`; dopo `chiedi("Mi chiamo Luca")` e `chiedi("Come mi chiamo?")` la cronologia è esattamente `[Human, AI, Human, AI]` con quei testi; la seconda chiamata al modello ha ricevuto system + i 3 messaggi precedenti; nessun `SystemMessage` in cronologia.
    - `test_errore_lascia_la_cronologia_invariata` (parametrizzato sulle tre eccezioni openai): un turno riuscito, poi uno con eccezione → `ErroreTurno` col messaggio previsto, cronologia uguale a prima; un terzo turno riesce.
    - `test_risposta_vuota_e_un_errore`: `AIMessage("")` → `ErroreTurno("Il modello ha restituito una risposta vuota.")`, cronologia invariata (Review Focus 2).
    - `test_log_chiamata_al_modello` (`caplog` a INFO): compaiono righe di inizio e fine chiamata con «passo 1».
  - `test_terminale.py`: `test_errore_turno_viene_mostrato_e_la_sessione_continua`: `rispondi` solleva `ErroreTurno("Connessione fallita: ...")` alla prima domanda e risponde alla seconda → entrambi i testi scritti.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3: Implementare** modello, grafo, conversazione; `ciclo` stampa il messaggio di `ErroreTurno` e continua; `main()` costruisce `Conversazione(costruisci_grafo(crea_modello(cfg)))` e passa `conversazione.chiedi` a `ciclo`. Rimuovere grafo fisso e relativo test.
- [ ] **Step 4:** Run tutti i test → PASS.
- [ ] **Step 5: Prova reale (LM Studio attivo, gemma senza strumenti).** Run da Git Bash `printf 'Mi chiamo Luca\nCome mi chiamo?\nesci\n' | .venv/Scripts/python -m assistente` → due risposte, la seconda contiene «Luca»; su stderr le righe `INFO assistente.grafo: ...` di inizio/fine per ogni chiamata. Con `LM_BASE_URL=http://localhost:1299/v1` → «Connessione fallita: ...» e la sessione prosegue.
- [ ] **Step 6:** README: avvio con LM Studio, verifica manuale della cronologia. **Commit** `feat(grafo): collega il nodo LLM a LM Studio con cronologia di sessione`.

---

## Incremento 3 — Strumento orologio e instradamento

### Task 5: Strumento `ora_corrente`

**Files:**
- Create: `assistente/strumenti.py`, `tests/test_strumenti.py`

**Interfaces:**
- Produces: `formatta_ora(fuso: ZoneInfo, istante: datetime) -> str` (istante con tzinfo, convertito nel fuso; `isoformat(timespec="seconds")` + `f" ({fuso.key})"`); `crea_strumenti(fuso: ZoneInfo, adesso: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> list[BaseTool]` che restituisce un solo `StructuredTool` di nome `ora_corrente`, descrizione della specifica §4.5, senza parametri.

- [ ] **Step 1: Test che falliscono:**
  - `test_ora_solare`: `formatta_ora(ZoneInfo("Europe/Rome"), datetime(2026, 1, 15, 11, 0, 0, tzinfo=timezone.utc)) == "2026-01-15T12:00:00+01:00 (Europe/Rome)"`.
  - `test_ora_legale`: `datetime(2026, 7, 15, 11, 0, 0, tzinfo=timezone.utc)` → `"2026-07-15T13:00:00+02:00 (Europe/Rome)"`.
  - `test_altro_fuso`: `ZoneInfo("America/New_York")`, stesso istante di gennaio → `"2026-01-15T06:00:00-05:00 (America/New_York)"`.
  - `test_strumento_contratto`: `crea_strumenti(...)[0]` ha `name == "ora_corrente"`, nessuna proprietà in `tool.args`, descrizione che inizia con «Restituisce data e ora correnti».
  - `test_strumento_usa_l_istante_iniettato`: `tool.invoke({})` con `adesso` fisso → stringa dell'ora solare sopra.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implementare. **Step 4:** Run → PASS.
- [ ] **Step 5: Verifica diretta** (slide: prima eseguire lo strumento da solo). Run `.venv/Scripts/python -c "from zoneinfo import ZoneInfo; from assistente.strumenti import crea_strumenti; print(crea_strumenti(ZoneInfo('Europe/Rome'))[0].invoke({}))"` → ora attuale con `+01:00 (Europe/Rome)`.
- [ ] **Step 6: Commit** `feat(strumenti): aggiunge lo strumento orologio con fuso esplicito`.

### Task 6: Nodo strumenti, arco condizionale e limite di passaggi

**Files:**
- Modify: `assistente/grafo.py`, `assistente/conversazione.py`, `assistente/terminale.py`, `tests/test_grafo.py`, `tests/test_conversazione.py`
- Create: `tests/test_reale.py`

**Interfaces:**
- Consumes: `crea_strumenti`, `crea_modello`, `ModelloFinto`.
- Produces:
  - `costruisci_grafo(modello: Runnable, strumenti: Sequence[BaseTool], max_passi: int) -> CompiledStateGraph` (sostituisce la firma del Task 4; aggiornare i chiamanti). Nodi `llm` e `strumenti`; `START → llm`; `add_conditional_edges("llm", instrada)`; `strumenti → llm`.
  - `instrada(stato) -> Literal["strumenti", "__end__"]` (chiusura su `max_passi`): nessuna `tool_calls` nell'ultimo messaggio → `END`; `tool_calls` e `passi < max_passi` → `"strumenti"`; `tool_calls` e `passi >= max_passi` → log WARNING «Limite di passaggi raggiunto (N)» e `END`.
  - Nodo `strumenti`: per ogni richiesta dell'ultimo `AIMessage` logga INFO `Richiesta strumento <nome> con argomenti <args>`, esegue lo strumento per nome, logga INFO `Risultato strumento <nome>: <risultato>`, aggiunge `ToolMessage(content=risultato, tool_call_id=id, name=nome)`; nome sconosciuto → contenuto `Strumento sconosciuto: <nome>` e log WARNING.
  - `Conversazione.chiedi`: se il messaggio finale ha ancora `tool_calls` → `ErroreTurno("Limite di passaggi raggiunto: riprova con una domanda diversa.")`, cronologia invariata.
  - `main()`: `strumenti = crea_strumenti(cfg.fuso_orario)`; `costruisci_grafo(crea_modello(cfg).bind_tools(strumenti), strumenti, cfg.max_passi)`.

- [ ] **Step 1: Test che falliscono** (richiesta di tool finta: `AIMessage("", tool_calls=[{"name": "ora_corrente", "args": {}, "id": "call_1"}])`, strumenti con istante fisso di gennaio):
  - `test_domanda_sull_ora_giro_completo`: risposte `[richiesta, AIMessage("Sono le 12:00.")]` → due chiamate al modello; i messaggi del risultato sono `[Human, AI(tool_calls), Tool, AI]`; il `ToolMessage` ha `tool_call_id == "call_1"` e contenuto `"2026-01-15T12:00:00+01:00 (Europe/Rome)"`; la seconda chiamata al modello ha ricevuto quel `ToolMessage`; `passi == 2`.
  - `test_domanda_ordinaria_nessuno_strumento`: una sola chiamata, nessun `ToolMessage`.
  - `test_due_richieste_nello_stesso_messaggio`: `tool_calls` con id `"a"` e `"b"` → due `ToolMessage` con gli id giusti, nell'ordine.
  - `test_strumento_sconosciuto`: richiesta `"meteo"` → `ToolMessage` «Strumento sconosciuto: meteo» con l'id della richiesta, il grafo prosegue fino alla risposta finale (Review Focus 3).
  - `test_limite_passi`: modello che chiede sempre lo strumento, `max_passi=3` → esattamente 3 chiamate al modello, 2 esecuzioni dello strumento; `Conversazione.chiedi` solleva `ErroreTurno` con il testo del limite; cronologia invariata.
  - `test_log_strumento` (`caplog`): compaiono «Richiesta strumento ora_corrente con argomenti {}» e «Risultato strumento ora_corrente: 2026-01-15T12:00:00+01:00 (Europe/Rome)»; nel caso del limite, un WARNING.
  - `test_cronologia_conserva_il_giro_dello_strumento`: dopo un turno con strumento e uno ordinario la cronologia è `[Human, AI(tool_calls), Tool, AI, Human, AI]`.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implementare. **Step 4:** Run tutti i test → PASS.
- [ ] **Step 5: Prova reale automatica** `tests/test_reale.py`, marcata `reale` e saltata se `os.environ.get("PROVE_REALI") != "1"`: costruisce la conversazione come `main()` (configurazione da `leggi_ambiente(Path.cwd())`), poi
  - `test_domanda_sull_ora_usa_lo_strumento`: `chiedi("Che ore sono adesso?")` → nella cronologia c'è un `ToolMessage` con `name == "ora_corrente"` e la risposta finale non è vuota;
  - `test_domanda_ordinaria_senza_strumento`: `chiedi("Qual è la capitale della Francia?")` → nessun `ToolMessage`.
  Run `.venv/Scripts/python -m pytest` → i due test risultano *skipped*.
- [ ] **Step 6: Prova reale con LM Studio.** Prima risolvere con l'utente il **problema aperto** (gemma rifiuta le richieste con `tools`): un passo alla volta, mostrando l'errore. Poi `PROVE_REALI=1 .venv/Scripts/python -m pytest -m reale -v` → 2 passed; e manualmente «Che ore sono?» → nei log richiesta, risultato e seconda chiamata. Se resta bloccata, annotarlo nel README come verifica da completare, senza cambiare architettura.
- [ ] **Step 7:** README: strumento, log da leggere, prove reali (`$env:PROVE_REALI="1"; python -m pytest -m reale -v`). **Commit** `feat(grafo): instrada le richieste allo strumento orologio con limite di passaggi`.

---

## Incremento 4 — Docker Compose e verifica completa

### Task 7: Container con Docker Compose

**Files:**
- Create: `Dockerfile`, `.dockerignore`, `compose.yaml`
- Modify: `README.md`

**Interfaces:**
- Consumes: `python -m assistente`, `requirements.txt`, `.env`.

- [ ] **Step 1: `Dockerfile`**: `FROM python:3.13-slim`; `ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1`; `WORKDIR /app`; copia e installa `requirements.txt` con `pip install --no-cache-dir`; copia `assistente/`; `CMD ["python", "-m", "assistente"]`.
- [ ] **Step 2: `.dockerignore`**: `.env`, `.venv/`, `__pycache__/`, `.pytest_cache/`, `tests/`, `docs/`, `.git*`, `.claude/`, `CLAUDE*.md`, `README.md`.
- [ ] **Step 3: `compose.yaml`**: servizio `assistente` con `build: .`, `stdin_open: true`, `tty: true`, `env_file: .env`, `environment: LM_BASE_URL: http://host.docker.internal:1234/v1`, `extra_hosts: ["host.docker.internal:host-gateway"]`, nessuna porta.
- [ ] **Step 4: Verifiche senza LM Studio.** Run `docker compose config` → `LM_BASE_URL` vale `http://host.docker.internal:1234/v1`, nessuna sezione `ports`. Run `docker compose build` → immagine costruita. Run `docker compose run --rm -T assistente python -c "from zoneinfo import ZoneInfo; from assistente.strumenti import crea_strumenti; print(crea_strumenti(ZoneInfo('Europe/Rome'))[0].invoke({}))"` → ora con `(Europe/Rome)` (prova che `tzdata` è presente e il fuso non dipende dall'host). Run `docker compose run --rm -T assistente python -c "import pathlib; print(pathlib.Path('.env').exists())"` → `False`.
- [ ] **Step 5: Prova reale con l'utente** (LM Studio su rete locale; un passo alla volta): `docker compose run --rm --name assistente-demo assistente`; da un secondo terminale `docker ps` e `docker logs -f assistente-demo`; checklist della specifica §9.2.
- [ ] **Step 6:** README: sezione Docker (abilitare "Serve on Local Network" in LM Studio, firewall, comandi, `--rm` e come analizzare un arresto senza). **Commit** `feat(docker): avvia l'assistente con Docker Compose`.

### Task 8: Verifica completa e documentazione finale

**Files:**
- Modify: `README.md`, `CLAUDE.md`

- [ ] **Step 1:** Run `.venv/Scripts/python -m pytest -v` → tutti verdi, prove reali *skipped*; riportare il conteggio.
- [ ] **Step 2:** Rieseguire da zero i comandi del README in un terminale pulito (venv, `.env` da `.env.example`, test, avvio locale, Docker) e correggere il README dove diverge.
- [ ] **Step 3:** README: sezione «Diagnosi» (container che termina subito → output e input interattivo; nessuna connessione → server, URL, rete locale, firewall; risposta senza orologio → righe «Richiesta strumento» nei log; errore 400 del template → problema aperto) e «Problemi aperti».
- [ ] **Step 4:** `CLAUDE.md`: aggiornare la sezione struttura con moduli e comandi di test effettivi (solo convenzioni stabili).
- [ ] **Step 5: Commit** `docs: completa README e CLAUDE.md con comandi verificati`.
- [ ] **Step 6:** Passare alla Fase D (review e verifica finale) dell'handoff.
