# Step 4, Resource MCP `utente://preferenze` — Piano di implementazione

> **Per chi esegue:** SOTTO-SKILL OBBLIGATORIA: usare superpowers:executing-plans (esecuzione diretta, scelta dell'utente per gli step precedenti) o superpowers:subagent-driven-development per eseguire il piano task per task. I passi usano le caselle (`- [ ]`) per il tracciamento.

**Obiettivo:** il server MCP pubblica la resource `utente://preferenze` (lingua, fuso orario, stile); l'host la legge una volta a inizio sessione, la valida, la mette in cima al prompt di sistema dell'agente e ne usa il fuso per `ora_corrente`; se la resource non è disponibile o non è valida, valori predefiniti segnalati nei log.

**Architettura:** nuovo modulo `assistente/preferenze.py` (dataclass `Preferenze`, validazione, predefiniti, paragrafo del prompt: funzioni pure) → resource in `assistente/server_mcp.py` (restituisce il testo del file `archivio/preferenze.json`) → lettura isolata e asincrona in `assistente/collegamento_mcp.py`, con log e ripiego sui predefiniti → `costruisci_grafo` riceve `preferenze` e il nodo `llm` usa `prompt_agente(...)` → `main()` legge le preferenze dopo la discovery e passa il fuso a `crea_strumenti`.

**Tecnologie:** Python 3.13, `mcp`/`fastmcp` e `langchain-mcp-adapters` già installati (nessuna dipendenza nuova), pytest 9.1.1.

**Specifica:** `docs/superpowers/specs/2026-11-15-preferenze-design.md` (commit `177a4d3` su `dev`; **da approvare nel suo insieme insieme a questo piano**). Chi esegue legge **entrambi** i documenti; le sezioni citate come §n sono della specifica.

Tutti i percorsi sono relativi a `assistente-laboratorio/`; i comandi si eseguono da PowerShell in quella cartella con `.\.venv\Scripts\python.exe`. Branch: `feat/preferenze` (già creato da `dev`, HEAD `177a4d3`).

## Vincoli globali

- **Prima di ogni task: avviso all'utente** (che cosa, su quale branch, quali file) e **attesa del via libera**. Conferma esplicita anche prima di prove reali (LM Studio, Docker, rete), commit e merge. A task concluso, spuntare le caselle in questo file.
- Seguire il PDF alla lettera: niente prompt MCP (`spiega`, `/prompts`: step 5), niente HTTP, niente salvataggio chat, **nessuno strumento** per leggere o cambiare le preferenze, nessuna rilettura durante la sessione (§3). Il modello resta `google/gemma-4-e2b`. Nessuna dipendenza nuova, nessuna variabile d'ambiente nuova.
- Valori fissati dalla specifica:
  - URI `utente://preferenze`, `name="preferenze"`, `mime_type="application/json"`; costante `PERCORSO_PREFERENZE = Path("archivio/preferenze.json")` in `server_mcp.py`;
  - chiavi obbligatorie `lingua` (testo non vuoto), `fuso_orario` (nome IANA valido), `stile` (esattamente `sintetico` o `dettagliato`); chiavi in più ignorate;
  - predefiniti **tutto o niente**: lingua `italiano`, fuso = `FUSO_ORARIO`, stile `sintetico`;
  - descrizioni dello stile: `sintetico` → `risposte brevi e chiare, in poche frasi`; `dettagliato` → `risposte complete, con spiegazioni e passaggi`;
  - paragrafo in cima al prompt: `Preferenze dell'utente: rispondi in <lingua>. Stile: <descrizione dello stile>. Il fuso orario predefinito è <fuso>: lo strumento ora_corrente lo usa già, non chiederlo all'utente.` seguito da riga vuota e da `PROMPT_SISTEMA` **senza** «Rispondi in italiano, in modo breve e chiaro.»; il riassunto resta in coda (un solo `SystemMessage`);
  - router, revisore, riassuntore e `testo_rifiuto` **non cambiano**;
  - log (logger `assistente.collegamento_mcp`): INFO `preferenze lette uri=utente://preferenze lingua=<l> fuso=<f> stile=<s>`; WARNING `preferenze non disponibili (<motivo>): valori predefiniti lingua=<l> fuso=<f> stile=<s>`; la lettura compare una volta, prima della prima domanda;
  - ordine in `main()`: discovery (server giù → codice 3 come oggi), poi preferenze, poi `crea_strumenti(preferenze.fuso)`.
- Codice sincrono (solo `collegamento_mcp.py` è asincrono); moduli piccoli; commenti didattici in italiano nello stile dei file esistenti, intestazione «COSA FA QUESTO FILE» nei moduli nuovi.
- Git: staging **per percorsi espliciti**, mai `git add -A`/`git add .`; mai nello staging i file della Lezione 3 in radice (`../client.py`, `../requirements.txt`, `../.env.example`, `../.gitignore`), `HANDOFF*.md`, `PROMPT-ripresa-*.txt`; Conventional Commits in italiano terminati da `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`; messaggio in un file nello scratchpad scritto **senza BOM** (`[IO.File]::WriteAllText($percorso, $testo, [Text.UTF8Encoding]::new($false))`) e `git commit -F <file>`; merge `--no-ff` in `dev` solo a step verificato e con conferma; nessun push.
- **Mai distruggere `archivio/preferenze.json` dell'utente** (se esiste): ogni test e prova che lo scrive lo salva e lo ripristina, o usa una cartella temporanea.
- Scostamenti dalla specifica, da far approvare con il piano (dettaglio dove compaiono):
  1. `prompt_agente(preferenze, prompt_base)` riceve il prompt di base come parametro (Task 1): `PROMPT_SISTEMA` resta in `grafo.py`, che importa `preferenze.py`; senza il parametro l'importazione sarebbe circolare.
  2. Nuova funzione `carica_preferenze(connessione, fuso_ripiego) -> Preferenze` in `collegamento_mcp.py` (Task 3), oltre a `leggi_preferenze_mcp`: legge, valida, ripiega sui predefiniti e scrive i due log previsti dalla §9 (il log INFO contiene i valori validati, quindi non può stare solo nella lettura grezza). `main()` ne chiama una sola.
  3. Il server legge il file con `utf-8-sig` invece di `utf-8` (Task 2): un file scritto da PowerShell 5.1 ha il BOM e `json.loads` lo rifiuterebbe.

## Punti di attenzione (Review Focus)

1. **File con BOM** (scritto da PowerShell 5.1 con `-Encoding utf8`): deve essere letto, non scartato. Test nel Task 2 (server) e nel Task 3 (`carica_preferenze`).
2. **File vuoto o solo spazi**: predefiniti con WARNING, la sessione parte. Test nel Task 1 (`ErrorePreferenze`) e nel Task 3 (log).
3. **Valori del tipo sbagliato** (`"fuso_orario": 5`, `"stile": null`, `"lingua": ["it"]`, radice JSON che è una lista): `ErrorePreferenze` con il motivo, mai `TypeError`. Test nel Task 1.
4. **Fuso che `ZoneInfo` accetta male o rifiuta con un'altra eccezione** (`"Europe"` è una cartella, `""`, `"../x"`, `"Europa/Roma"`): `ErrorePreferenze`, non un crash. Test nel Task 1.
5. **`lingua` su più righe** (un a-capo nel valore finirebbe dentro il prompt di sistema): rifiutata con `ErrorePreferenze`. Test nel Task 1.

---

## Task 1: Modulo `preferenze.py` e `ErrorePreferenze`

**Branch:** `feat/preferenze`.

**Files:**
- Create: `assistente/preferenze.py`, `tests/test_preferenze.py`
- Modify: `assistente/errori.py` (nuova eccezione, con commento nello stile del file)

**Interfaces:**
- Produces (`errori.py`): `class ErrorePreferenze(Exception)`.
- Produces (`preferenze.py`):
  - `@dataclass(frozen=True) class Preferenze: lingua: str; fuso: ZoneInfo; stile: str`
  - `STILI: dict[str, str]` (`sintetico`/`dettagliato` → descrizione della Vincoli globali)
  - `predefinite(fuso: ZoneInfo) -> Preferenze`
  - `leggi_preferenze_da_testo(testo: str) -> Preferenze` (solleva `ErrorePreferenze`)
  - `prompt_agente(preferenze: Preferenze, prompt_base: str) -> str` (paragrafo + riga vuota + `prompt_base`)

- [x] **Step 1: Scrivere i test (devono fallire)** in `tests/test_preferenze.py`. Valori e asserzioni:
  - `test_file_valido`: `'{"lingua": "inglese", "fuso_orario": "America/New_York", "stile": "dettagliato"}'` → `Preferenze("inglese", ZoneInfo("America/New_York"), "dettagliato")`.
  - `test_chiavi_in_piu_ignorate` e `test_spazi_attorno_alla_lingua_tolti` (`" inglese "` → `"inglese"`).
  - `test_difetti` parametrizzato, ciascuno con `pytest.raises(ErrorePreferenze)` e frammento atteso in `str(errore.value)`: `""` e `"   "` (`JSON non valido`); `"{"` (`JSON non valido`); `"[]"` (`oggetto`); chiave mancante, una per chiave (`manca la chiave 'stile'`, e analoghi per `lingua`, `fuso_orario`); `"fuso_orario": "Europa/Roma"` (`fuso_orario non valido: 'Europa/Roma'`); `"Europe"`, `""` e `"../x"` come fuso (`fuso_orario non valido`); `"stile": "lungo"` (`stile deve essere 'sintetico' o 'dettagliato', non 'lungo'`); `"lingua": ""` e `"lingua": "a\nb"` (`lingua`); tipi sbagliati `"fuso_orario": 5`, `"stile": null`, `"lingua": ["it"]` (la chiave nel messaggio).
  - `test_predefinite`: `predefinite(ZoneInfo("Europe/Rome")) == Preferenze("italiano", ZoneInfo("Europe/Rome"), "sintetico")`.
  - `test_prompt_agente_inizia_con_il_paragrafo`: con `prompt_base="BASE"` il risultato è esattamente `"Preferenze dell'utente: rispondi in inglese. Stile: risposte complete, con spiegazioni e passaggi. Il fuso orario predefinito è America/New_York: lo strumento ora_corrente lo usa già, non chiederlo all'utente.\n\nBASE"`; un secondo caso con i predefiniti (`italiano`, `risposte brevi e chiare, in poche frasi`, `Europe/Rome`).
- [x] **Step 2: Eseguire** `.\.venv\Scripts\python.exe -m pytest tests/test_preferenze.py -q` → deve fallire (`ModuleNotFoundError`).
- [x] **Step 3: Implementare** `ErrorePreferenze` e `preferenze.py` con le firme sopra. Approccio: `json.loads`, controllo che sia un `dict`, poi un controllo per chiave nell'ordine `lingua`, `fuso_orario`, `stile`, con il tipo verificato prima del valore; il fuso con `ZoneInfo(...)` dentro `try` che cattura `Exception` (un nome non valido può dare `ZoneInfoNotFoundError`, `ValueError`, `IsADirectoryError`, `PermissionError`...) e lo trasforma in `ErrorePreferenze`.
- [x] **Step 4: Eseguire** `pytest tests/test_preferenze.py -q` → tutti passano; poi `pytest -q` → **300 passed, 13 skipped** + i nuovi.
- [x] **Step 5: Commit** (con conferma): `feat(preferenze): modulo delle preferenze, validazione e prompt dell'agente`; staging: `assistente/errori.py assistente/preferenze.py tests/test_preferenze.py` (e questo piano, se ancora non committato).

## Task 2: Resource sul server MCP

**Branch:** `feat/preferenze`.

**Files:**
- Modify: `assistente/server_mcp.py` (costante `PERCORSO_PREFERENZE` accanto a `PERCORSO_NOTE`; nuova resource dopo i tool)
- Modify: `tests/test_server_mcp.py`

**Interfaces:**
- Consumes: nulla.
- Produces: resource `utente://preferenze` (`name="preferenze"`, `mime_type="application/json"`) la cui lettura restituisce il testo del file `PERCORSO_PREFERENZE` letto con `encoding="utf-8-sig"`; `server_mcp.PERCORSO_PREFERENZE: Path`.

- [x] **Step 1: Scrivere i test (devono fallire)** in `tests/test_server_mcp.py`, con lo stesso stile degli altri (client in memoria, `asyncio.run`), e `monkeypatch.setattr(server_mcp, "PERCORSO_PREFERENZE", tmp_path / "preferenze.json")`:
  - `test_discovery_preferenze`: `list_resources()` contiene la resource con URI `utente://preferenze`, nome `preferenze`, tipo `application/json`.
  - `test_preferenze_non_sono_un_tool`: `utente://preferenze` / `preferenze` **non** è tra i nomi di `tools/list`; `test_catalogo_completo` esistente resta valido (dieci tool).
  - `test_lettura_preferenze`: file scritto con un JSON valido → `read_resource("utente://preferenze")` restituisce lo stesso testo.
  - `test_lettura_preferenze_con_bom`: file scritto in bytes con `b"\xef\xbb\xbf"` davanti → il testo restituito non comincia con il BOM e `json.loads` lo accetta.
  - `test_lettura_preferenze_file_assente`: con file inesistente la lettura solleva un'eccezione (`pytest.raises(Exception)`).
- [x] **Step 2: Eseguire** `pytest tests/test_server_mcp.py -q` → i nuovi falliscono.
- [x] **Step 3: Implementare** in `server_mcp.py`: `PERCORSO_PREFERENZE = Path("archivio/preferenze.json")` e `@mcp.resource("utente://preferenze", name="preferenze", mime_type="application/json") def preferenze() -> str:` con docstring `Preferenze dell'utente per le risposte.`; nessuna validazione (§6). Se l'intestazione del file elenca i tool, aggiungere una riga sulla resource.
- [x] **Step 4: Eseguire** `pytest tests/test_server_mcp.py -q` e `pytest -q` → tutto verde.
- [ ] **Step 5: Commit** (con conferma): `feat(server_mcp): resource utente://preferenze`; staging: `assistente/server_mcp.py tests/test_server_mcp.py`.

## Task 3: Lettura della resource da parte dell'host, con log e predefiniti

**Branch:** `feat/preferenze`.

**Files:**
- Modify: `assistente/collegamento_mcp.py`
- Modify: `tests/test_collegamento_mcp.py`

**Interfaces:**
- Consumes: `Preferenze`, `predefinite`, `leggi_preferenze_da_testo`, `ErrorePreferenze` (Task 1); resource del Task 2.
- Produces:
  - `leggi_preferenze_mcp(connessione: dict) -> str`: apre una sessione stdio, `resources/read` su `utente://preferenze`, restituisce il testo, chiude (`asyncio.run`); qualunque errore → `ErroreCollegamentoMCP(motivo)` (stessi `_eccezione_di_fondo`/`_motivo` della discovery);
  - `carica_preferenze(connessione: dict, fuso_ripiego: ZoneInfo) -> Preferenze`: chiama `leggi_preferenze_mcp` e `leggi_preferenze_da_testo`; se solleva `ErroreCollegamentoMCP` o `ErrorePreferenze` restituisce `predefinite(fuso_ripiego)` e scrive il WARNING; altrimenti scrive l'INFO. **Non solleva mai** per problemi di lettura o di contenuto. Log nei formati della Vincoli globali, logger del modulo.

- [x] **Step 1: Scrivere i test (devono fallire)** in `tests/test_collegamento_mcp.py`. Il server parte davvero in sottoprocesso con `cwd` = una cartella temporanea (`connessione_stdio(tmp_path)`) in cui si scrive `archivio/preferenze.json`; `caplog` a livello INFO per `assistente`:
  - `test_leggi_preferenze_mcp_restituisce_il_testo`: il testo del file arriva intatto.
  - `test_leggi_preferenze_mcp_file_assente`: `pytest.raises(ErroreCollegamentoMCP)`.
  - `test_carica_preferenze_valide`: file `America/New_York`/`inglese`/`dettagliato` → `Preferenze` corrispondente e **una sola** riga INFO `preferenze lette uri=utente://preferenze lingua=inglese fuso=America/New_York stile=dettagliato`, nessun WARNING.
  - `test_carica_preferenze_con_bom`: file con BOM → valide, riga INFO.
  - `test_carica_preferenze_file_assente`: `== predefinite(ZoneInfo("Europe/Rome"))` e riga WARNING che comincia con `preferenze non disponibili (` e finisce con `): valori predefiniti lingua=italiano fuso=Europe/Rome stile=sintetico`.
  - `test_carica_preferenze_file_non_valido` e `test_carica_preferenze_file_vuoto`: predefiniti, WARNING con il motivo di `ErrorePreferenze` (per esempio `stile deve essere`, `JSON non valido`).
  - `test_carica_preferenze_server_non_avviabile`: connessione con comando inesistente (come in `test_server_non_avviabile`) → predefiniti + WARNING, nessuna eccezione.
  - `test_carica_preferenze_non_e_un_tool`: `carica_strumenti_mcp(...)` restituisce gli stessi dieci nomi di prima, senza `preferenze` (punto 03 del PDF).
- [x] **Step 2: Eseguire** `pytest tests/test_collegamento_mcp.py -q` → i nuovi falliscono.
- [x] **Step 3: Implementare** le due funzioni. Per la lettura: sessione stdio del pacchetto `mcp` (`stdio_client` + `ClientSession`, `read_resource`) o l'helper di `langchain-mcp-adapters`, a scelta di chi esegue (§14); il testo si ricava dal primo contenuto testuale della risposta. Commento didattico in testa: la resource la legge l'host, il modello non la vede.
- [x] **Step 4: Eseguire** `pytest tests/test_collegamento_mcp.py -q` e `pytest -q` → tutto verde.
- [ ] **Step 5: Commit** (con conferma): `feat(collegamento_mcp): lettura delle preferenze con ripiego sui predefiniti`; staging: `assistente/collegamento_mcp.py tests/test_collegamento_mcp.py`.

## Task 4: Le preferenze in cima al prompt dell'agente

**Branch:** `feat/preferenze`.

**Files:**
- Modify: `assistente/grafo.py` (`PROMPT_SISTEMA`, firma di `costruisci_grafo`, nodo `llm`, docstring/intestazione)
- Modify: `assistente/terminale.py` (solo il montaggio minimo: `main()` passa `predefinite(config.fuso_orario)`, così il programma continua a partire; il montaggio vero è il Task 5)
- Modify: `tests/test_grafo.py`, `tests/test_conversazione.py`, `tests/test_reale.py` (chiamate a `costruisci_grafo` e confronti con `PROMPT_SISTEMA`)

**Interfaces:**
- Consumes: `Preferenze`, `predefinite`, `prompt_agente` (Task 1).
- Produces: `costruisci_grafo(modello, strumenti, max_passi, router, ambito, revisore, max_revisioni, riassuntore, soglia_riassunto, messaggi_da_tenere, preferenze: Preferenze)` (parametro nuovo **in coda, obbligatorio**); il messaggio di sistema dell'agente è `sistema_con_riassunto(prompt_agente(preferenze, PROMPT_SISTEMA), stato["riassunto"])`; `PROMPT_SISTEMA` non contiene più «Rispondi in italiano, in modo breve e chiaro.» e per il resto è invariato.

- [x] **Step 1: Scrivere/adattare i test (devono fallire)** in `tests/test_grafo.py`:
  - l'helper `esegui(...)` e `conversazione_con(...)` (in `test_conversazione.py`) ricevono `preferenze=PREFERENZE_PREDEFINITE` (costante di test: `predefinite(ZoneInfo("Europe/Rome"))`) e la passano a `costruisci_grafo`; idem le chiamate dirette a `costruisci_grafo` nei due file e in `test_reale.py`;
  - `test_domanda_ordinaria_una_chiamata` (riga ~88): il `SystemMessage` inviato all'agente è `prompt_agente(PREFERENZE_PREDEFINITE, PROMPT_SISTEMA)`;
  - nuovo `test_preferenze_in_cima_al_prompt_dell_agente`: con `Preferenze("inglese", ZoneInfo("America/New_York"), "dettagliato")` il contenuto del `SystemMessage` dell'agente **comincia con** `"Preferenze dell'utente: rispondi in inglese."`, contiene `risposte complete, con spiegazioni e passaggi` e `America/New_York`, e **non** contiene `Rispondi in italiano`;
  - nuovo `test_preferenze_e_riassunto_in_un_solo_messaggio`: con `riassunto="Riassunto X."` nello stato, il messaggio di sistema comincia con il paragrafo delle preferenze e termina con il paragrafo del riassunto (un solo `SystemMessage`);
  - nuovo `test_router_revisore_riassuntore_non_ricevono_le_preferenze`: nessun prompt di sistema di router, revisore e riassuntore contiene `Preferenze dell'utente`;
  - adattare il test alla riga ~559 (confronto con `PROMPT_SISTEMA`) a `prompt_agente(PREFERENZE_PREDEFINITE, PROMPT_SISTEMA)`.
- [x] **Step 2: Eseguire** `pytest tests/test_grafo.py tests/test_conversazione.py -q` → falliscono (parametro non accettato).
- [x] **Step 3: Implementare** le modifiche in `grafo.py` (parametro, docstring con una riga su `preferenze`, nodo `llm`, `PROMPT_SISTEMA` senza la frase); in `main()` solo `predefinite(config.fuso_orario)` come ultimo argomento.
- [x] **Step 4: Eseguire** `pytest -q` → **tutta la suite verde** (i 300 esistenti, adattati, più i nuovi), 13 skipped.
- [ ] **Step 5: Commit** (con conferma): `feat(grafo): preferenze in cima al prompt dell'agente`; staging: `assistente/grafo.py assistente/terminale.py tests/test_grafo.py tests/test_conversazione.py tests/test_reale.py`.

## Task 5: Montaggio in `main()` e orologio nel fuso delle preferenze

**Branch:** `feat/preferenze`.

**Files:**
- Modify: `assistente/terminale.py` (`main()`)
- Modify: `tests/test_terminale.py`, `tests/test_reale.py` (stesso montaggio di `main()` e prove reali delle preferenze)

**Interfaces:**
- Consumes: `carica_preferenze` (Task 3), `costruisci_grafo(..., preferenze)` (Task 4), `crea_strumenti(fuso, adesso=...)` (invariato).
- Produces: `main()` con l'ordine della §7: (1) `carica_strumenti_mcp(connessione_stdio(Path.cwd()))`, errore → `Server MCP non disponibile`, codice 3, senza leggere preferenze né contattare LM Studio; (2) `preferenze = carica_preferenze(connessione, config.fuso_orario)`; (3) `strumenti = crea_strumenti(preferenze.fuso) + strumenti_mcp`; (4) `costruisci_grafo(..., preferenze)`.

- [ ] **Step 1: Scrivere i test (devono fallire)** in `tests/test_terminale.py`, sullo stile di `test_main_server_mcp_non_disponibile` (monkeypatch di `carica_strumenti_mcp`, `carica_preferenze`, `crea_modello`, `crea_router`, `crea_revisore`, `ciclo` e `.env` in `tmp_path`); se montare `main()` richiede troppa impalcatura lo decide chi esegue e lo dichiara nel resoconto (come nel Task 4 dello step 3):
  - `test_main_usa_il_fuso_delle_preferenze`: `carica_preferenze` finta restituisce `Preferenze("inglese", ZoneInfo("America/New_York"), "dettagliato")`, con `FUSO_ORARIO=Europe/Rome` nel `.env`; lo strumento `ora_corrente` passato al grafo (spia su `crea_strumenti` o sul grafo costruito) riceve il fuso `America/New_York`, e `costruisci_grafo` riceve quelle preferenze;
  - `test_main_con_preferenze_non_disponibili_usa_il_fuso_di_ripiego`: `carica_preferenze` finta restituisce i predefiniti con `Europe/Rome` → orologio in `Europe/Rome`;
  - `test_main_server_giu_non_legge_le_preferenze`: con discovery che fallisce, `main() == 3` e `carica_preferenze` **non** è stata chiamata.
- [ ] **Step 2: Eseguire** `pytest tests/test_terminale.py -q` → i nuovi falliscono.
- [ ] **Step 3: Implementare** in `main()` l'ordine sopra, con commento didattico sul perché la lettura sta dopo la discovery (distingue «server giù» da «resource non disponibile»). In `tests/test_reale.py`, `crea_conversazione(config)` ricalca `main()`: discovery, `carica_preferenze`, `crea_strumenti(preferenze.fuso)`, `costruisci_grafo(..., preferenze)`.
- [ ] **Step 4: Prove reali automatiche nuove** in `tests/test_reale.py` (saltate senza `PROVE_REALI=1`): fixture che **salva e ripristina** `archivio/preferenze.json` dell'utente (o lo cancella a fine prova se non esisteva); `test_ora_nel_fuso_delle_preferenze`: file con `America/New_York`, domanda «Che ore sono?», nella cronologia il `ToolMessage` di `ora_corrente` contiene `(America/New_York)` e il modello non ha chiesto il fuso; `test_preferenze_assenti_usano_il_fuso_del_env`: senza file il risultato contiene `(` + `FUSO_ORARIO` + `)`. Non si eseguono ora (serve conferma, §Task 7): in Step 5 basta che vengano raccolte e saltate.
- [ ] **Step 5: Eseguire** `pytest tests/test_terminale.py -q`, `pytest -q` (esito atteso: tutto verde, le prove reali `skipped`) e `pytest tests/test_reale.py --collect-only -q` (le prove nuove sono raccolte).
- [ ] **Step 6: Commit** (con conferma): `feat(terminale): preferenze lette a inizio sessione e fuso dell'orologio`; staging: `assistente/terminale.py tests/test_terminale.py tests/test_reale.py`.

## Task 6: Documentazione

**Branch:** `feat/preferenze`.

**Files:**
- Modify: `README.md`, `CLAUDE.md`
- Nota: **`.env.example` non si tocca** (nella radice è già modificato per la Lezione 3 e non va nello staging): il ruolo di `FUSO_ORARIO` come fuso di ripiego si documenta nella tabella delle variabili del README (riga 45). Se l'utente preferisce toccarlo, lo decide lui prima di questo task.

- [ ] **Step 1: README.** Sezione «Preferenze dell'utente (resource MCP)» con: contenuto del file `archivio/preferenze.json` da copiare e dove crearlo (`New-Item`/editor, **senza BOM se possibile**, ma un BOM è tollerato); i tre campi e i valori ammessi; predefiniti e regola «tutto o niente»; che cosa succede con il file rotto (nuove righe della tabella «Diagnosi» con il WARNING di esempio); formato dei due log; tabella delle tre primitive (tool = il modello, resource = l'host, prompt = l'utente; dove si vedono nei log); nota Docker (la cartella `archivio` è già montata: modifica sul PC, riavvio del servizio, nessuna ricostruzione); `FUSO_ORARIO` descritta come fuso di ripiego (tabella variabili); voci della checklist manuale numerate dopo la 38 (§11 punti 1–4); comandi di prova verificati; **«Esiti delle prove reali» dello step 4 compilato solo dopo il Task 7**, con data e limiti.
- [ ] **Step 2: CLAUDE.md** (del progetto): nell'«Obiettivo» una riga per lo step 4 (resource letta dall'host a inizio sessione, validata, in cima al prompt dell'agente, predefiniti con WARNING) e `ora_corrente` «fuso dalle preferenze, o da `FUSO_ORARIO` se non disponibili». Nessun'altra modifica.
- [ ] **Step 3: Verificare** che ogni comando scritto nel README sia stato eseguito (nessun comando non provato); `pytest -q` invariato.
- [ ] **Step 4: Commit** (con conferma): `docs: preferenze dell'utente, resource MCP (step 4)`; staging: `README.md CLAUDE.md`.

## Task 7: Prove reali, prove manuali, revisione e merge

**Branch:** `feat/preferenze`. **Ogni prova reale richiede la conferma dell'utente** (LM Studio, Docker); nessun merge senza conferma.

- [ ] **Step 1: Prove reali automatiche** (`$env:PROVE_REALI="1"; .\.venv\Scripts\python.exe -m pytest -m reale -q`, in background, output nella cartella del registro `..\.superpowers\sdd\2026-11-15-preferenze\`): le 2 prove nuove del Task 5 e la serie esistente (13). Criterio §11: nessuna regressione; se il modello non rispetta la lingua o lo stile, è un limite di `gemma-4-e2b` da registrare nel README (non cambiare modello). Se si ritocca il paragrafo delle preferenze o le descrizioni di stile, si ripete tutta la serie e si annotano gli esiti, anche intermedi.
- [ ] **Step 2: Prove manuali guidate** (istruzioni numerate «scrivi X, premi Invio, deve succedere Y», lettura dell'output riga per riga) per le evidenze del PDF: (a) `America/New_York` nel file, «Che ore sono?» → `tool=ora_corrente ... (America/New_York)` senza che il modello chieda il fuso; (b) `lingua: inglese`, `stile: dettagliato`, riavvio → risposta di conseguenza; (c) senza file: sessione avviata, WARNING nei log, orologio nel fuso di `FUSO_ORARIO`; (d) la riga `preferenze lette ...` compare una volta, prima della prima domanda, distinta dalle righe `variant=...`; (e) avvio in Docker fino a `Tu>` con `archivio/preferenze.json` montato. Nel resoconto: cosa eseguito, esito, cosa non provato.
- [ ] **Step 3: Revisione indipendente** (sotto-agente Opus con `review-package`, come per gli step 2 e 3) sul diff `dev...feat/preferenze`; correzioni con TDD; i difetti degli altri step si registrano, non si correggono qui.
- [ ] **Step 4: Chiusura.** Esiti nel README e nel registro; spuntare tutte le caselle; `pytest -q` finale; con la conferma dell'utente merge `--no-ff` di `feat/preferenze` in `dev` (messaggio `merge: lezione 6, step 4 preferenze`, senza BOM); aggiornare `CLAUDE.local.md` e `HANDOFF.md` (step 4 unito, prossimo step 5). Nessun push.

---

## Verifica del piano rispetto alla specifica

| Specifica | Task |
|---|---|
| §5 file e predefiniti, §7 validazione | 1 |
| §6 resource sul server, non tra i tool | 2 |
| §7 lettura nell'host, §9 log | 3 |
| §8 prompt di sistema, parametro `preferenze`, riassunto in coda, altri nodi esclusi | 4 |
| §7 orchestrazione in `main()`, decisione A (fuso all'orologio), `FUSO_ORARIO` ripiego | 5 |
| §13 documentazione e Git | 6 |
| §10 test automatici | 1–5 |
| §11 prove reali e manuali, criterio di unione | 7 |
