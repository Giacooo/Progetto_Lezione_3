# Sei strumenti MCP — Piano di implementazione

> **Per chi esegue:** SOTTO-SKILL OBBLIGATORIA: usare superpowers:subagent-driven-development (consigliata) o superpowers:executing-plans per eseguire il piano task per task. I passi usano le caselle (`- [ ]`) per il tracciamento.

**Obiettivo:** aggiungere all'assistente della lezione 4 un server FastMCP con i sei strumenti del blocco 5 del PDF, scoperti con `tools/list` ed eseguiti dal grafo esistente.

**Architettura:** logica di dominio pura in `assistente/strumenti_mcp/` → registrazione nel server `assistente/server_mcp.py` (stdio) → collegamento `assistente/collegamento_mcp.py` (discovery con `langchain-mcp-adapters`, strumenti resi sincroni con `asyncio.run`, una sessione stdio per chiamata) → grafo invariato nella forma, con log `variant=… execution=…` ed errori classificati.

**Tecnologie:** Python 3.13, LangGraph 1.2.18, langchain-openai 1.7.3, fastmcp 3.4.11, mcp 1.30.0, langchain-mcp-adapters 0.3.2, httpx 0.28.1, SQLite (`sqlite3`), pytest 9.1.1.

**Specifica:** `docs/superpowers/specs/2026-11-03-mcp-strumenti-design.md` (approvata il 2026-11-03). Chi esegue legge **entrambi** i documenti.

Tutti i percorsi sono relativi a `assistente-laboratorio/`; i comandi si eseguono da PowerShell in quella cartella.

## Vincoli globali

- **Prima di ogni task: avviso all'utente** (che cosa, su quale branch, quali file). A task concluso, spuntare le caselle in questo file.
- Nomi di strumenti, argomenti, moduli e messaggi **in italiano** (come `ora_corrente`).
- Solo quanto chiede la specifica; niente Streamable HTTP, più server, prompt/resource MCP, varianti FastAPI, variabili d'ambiente nuove. `ora_corrente` resta invariato nel comportamento.
- Codice sincrono; l'asincronia sta solo in `collegamento_mcp.py` e nei test che usano il client in memoria (con `asyncio.run`, **senza** aggiungere `pytest-asyncio`).
- Mai `eval`/`exec` nella calcolatrice.
- Il server scrive log solo su stderr; stdout è del protocollo.
- Dipendenze fissate: `fastmcp==3.4.11`, `mcp==1.30.0`, `langchain-mcp-adapters==0.3.2`, `httpx==0.28.1`.
- Test automatici senza LM Studio né rete. Il test `tests/test_modello.py::test_crea_modello_usa_la_configurazione` fallisce in locale per il blocco di Windows su `jiter`: è noto, non va «aggiustato».
- Git: `dev` da `main`; ogni `feat/<nome>` da `dev` aggiornato; merge in `dev` con `git merge --no-ff`; nessun push senza richiesta dell'utente; staging **per percorsi espliciti**, mai `git add -A`/`git add .`; i file della Lezione 3 in radice (`../client.py`, `../requirements.txt`, `../.env.example`, `../.gitignore`) non entrano mai nello staging; `HANDOFF*.md` non si committano.
- Conventional Commits in italiano con la riga `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Prova reale fallita: si registra nel README con il punto esatto e si fa comunque il merge in `dev` se i test automatici sono verdi (decisione dell'utente).
- Prove reali: in locale se l'app parte (`python -m assistente`); se è ancora bloccata da `jiter`, con Docker Compose (`docker compose run --rm --name assistente-demo assistente` e, in un secondo terminale, `docker logs -f assistente-demo`).

## Punti critici da sorvegliare

1. **Server che scrive su stdout** (print, banner, log su stdout): rompe il protocollo stdio. Test: avvio reale via stdio con discovery riuscita (Task 3).
2. **Eccezioni di trasporto che sfuggono al nodo strumenti**: il turno morirebbe con «Errore inatteso» invece di un `ToolMessage` correlato. Test: strumento finto che solleva `ErroreCollegamentoMCP` (Task 4).
3. **Calcolatrice con potenze enormi** (`(10**100)**100`, `9**9**9`): blocco o memoria. Test con rifiuto (Task 1).
4. **Note: eliminazione con ID inesistente o testo di soli spazi**: nessuna modifica e messaggio chiaro. Test (Task 9).
5. **Meteo: rete assente confusa con città non trovata**. Test con trasporto simulato che solleva `httpx.ConnectError` (Task 10).

---

## Task 0: Preparazione di `dev`

**Branch:** `main` → `dev`. **File:** commenti già presenti (nessuna modifica di contenuto), `CLAUDE.md`, specifica, piano.

- [ ] **Passo 1: creare `dev` da `main`**

Run: `git switch -c dev main`
Atteso: `Switched to a new branch 'dev'`; `git status` mostra ancora le modifiche non committate.

- [ ] **Passo 2: verificare che le modifiche dei file di progetto siano solo commenti**

Run (Git Bash): `git diff -- . ':!CLAUDE.md' | grep -E '^[-+]' | grep -vE '^(\+\+\+|---)' | grep -vE '^\+\s*#' | grep -vE '^\+\s*$'`
Atteso: solo le 5 righe dei campi di `Configurazione` (stesso codice con commento in coda). Se compare altro, fermarsi e avvisare l'utente.

- [ ] **Passo 3: commit dei commenti**

```powershell
git add -- .dockerignore .env.example .gitignore Dockerfile compose.yaml pytest.ini requirements.txt requirements-dev.txt assistente tests
git diff --cached --stat
```
Atteso: solo file sotto `assistente-laboratorio/` (nessun `../client.py` ecc.), nessun `.env`.
`git commit -m "docs: aggiunge commenti esplicativi al codice della lezione 4"`

- [ ] **Passo 4: commit di CLAUDE.md, specifica e piano**

```powershell
git add -- CLAUDE.md docs/superpowers/specs/2026-11-03-mcp-strumenti-design.md docs/superpowers/plans/2026-11-03-mcp-strumenti.md
git commit -m "docs: regole, specifica e piano della lezione 5 (strumenti MCP)"
```

- [ ] **Passo 5: test di partenza**

Run: `.\.venv\Scripts\python.exe -m pytest -q`
Atteso: `54 passed, 2 skipped`, 1 failed (solo `test_crea_modello_usa_la_configurazione`, `jiter`).

---

## `feat/calcolatrice` (base MCP + calcolatrice)

Prima del Task 1: `git switch -c feat/calcolatrice dev`.

### Task 1: Logica della calcolatrice

**File:**
- Crea: `assistente/strumenti_mcp/__init__.py` (docstring di una riga), `assistente/strumenti_mcp/calcolatrice.py`
- Test: `tests/test_calcolatrice.py`

**Interfacce:**
- Produce: `calcola(espressione: str) -> str` — restituisce il risultato formattato; solleva `ValueError` con messaggio in italiano per ogni input rifiutato. Convenzione per **tutti** i moduli di dominio: errore dell'utente = `ValueError`.

- [ ] **Passo 1: scrivere i test**

```python
import pytest
from assistente.strumenti_mcp.calcolatrice import calcola

@pytest.mark.parametrize("espressione, atteso", [
    ("2+3*4", "14"), ("(1.5+2)/7", "0.5"), ("10/4", "2.5"), ("10/2", "5"),
    ("7//2", "3"), ("7%3", "1"), ("-3+ +2", "-1"), ("2**10", "1024"),
])
def test_espressioni_valide(espressione, atteso):
    assert calcola(espressione) == atteso

@pytest.mark.parametrize("espressione, frammento", [
    ("", "vuota"), ("   ", "vuota"),
    ("__import__('os')", "non ammess"), ("abs(-1)", "non ammess"), ("x+1", "non ammess"),
    ("'a'*3", "non ammess"), ("1<2", "non ammess"), ("2+", "sintassi"),
    ("10/0", "zero"), ("5//0", "zero"), ("5%0", "zero"),
    ("1+" * 100 + "1", "200"), ("2**10000", "esponente"), ("(10**100)**100", "troppo grande"),
    ("9**9**9", "esponente"),
])
def test_input_rifiutati(espressione, frammento):
    with pytest.raises(ValueError, match=frammento):
        calcola(espressione)

def test_nessun_eval():
    import inspect, assistente.strumenti_mcp.calcolatrice as m
    sorgente = inspect.getsource(m)
    assert "eval(" not in sorgente and "exec(" not in sorgente
```

- [ ] **Passo 2: eseguire i test e vederli fallire**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_calcolatrice.py -q` — Atteso: errore di import.

- [ ] **Passo 3: implementare `calcola`**

`ast.parse(espressione, mode="eval")` e visita ricorsiva con elenco chiuso: `Expression`, `Constant` (solo `int`/`float`, non `bool`), `BinOp` con `Add Sub Mult Div FloorDiv Mod Pow`, `UnaryOp` con `UAdd USub`. Qualsiasi altro nodo → `ValueError("costrutto non ammesso: <NomeNodo>")`. Limiti: lunghezza > 200 → errore che cita 200; `**` con |esponente| > 100 → errore «esponente oltre 100»; prima di `**` stimare `abs(esponente) * log10(max(abs(base), 2)) > 300` → «risultato troppo grande»; risultato `float` non finito → «risultato troppo grande»; divisione/modulo per zero → «divisione per zero». `SyntaxError` → «errore di sintassi». Formato: `float` intero → senza decimali (`"5"`); altrimenti `repr` arrotondato a 12 cifre significative (`f"{x:.12g}"`).

- [ ] **Passo 4: test verdi**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_calcolatrice.py -q` — Atteso: tutti passati.

- [ ] **Passo 5: commit**

```powershell
git add -- assistente/strumenti_mcp/__init__.py assistente/strumenti_mcp/calcolatrice.py tests/test_calcolatrice.py
git commit -m "feat(calcolatrice): valuta espressioni aritmetiche senza eval"
```

### Task 2: Server MCP con `calcola` e dipendenze

**File:**
- Modifica: `requirements.txt` (aggiunge `fastmcp==3.4.11`, `mcp==1.30.0`, `langchain-mcp-adapters==0.3.2`, ognuno con una riga di commento che lo motiva)
- Crea: `assistente/server_mcp.py`
- Test: `tests/test_server_mcp.py`

**Interfacce:**
- Consuma: `calcola` (Task 1).
- Produce: `mcp: FastMCP` (nome `"Strumenti del laboratorio"`) a livello di modulo; avvio con `python -m assistente.server_mcp` → `mcp.run(show_banner=False)` (stdio). Convenzione per tutti gli strumenti: la funzione registrata con `@mcp.tool` ha **lo stesso nome** dello strumento, docstring in italiano = descrizione, e converte `ValueError` in `fastmcp.exceptions.ToolError(str(errore))`. Log del server: `logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")` dentro il blocco `__main__`, logger `assistente.server_mcp`.
- Test helper (in `tests/test_server_mcp.py`, riusato dai task successivi): `catalogo() -> dict[str, Tool]` e `chiama(nome: str, argomenti: dict) -> CallToolResult` che usano `fastmcp.Client(mcp)` in memoria con `asyncio.run`, `raise_on_error=False`.

- [ ] **Passo 1: installare e verificare le dipendenze**

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -c "import fastmcp, mcp, langchain_mcp_adapters; print(fastmcp.__version__)"
```
Atteso: `3.4.11`. Se Windows blocca una DLL («criterio di controllo dell'applicazione»), **fermarsi e avvisare l'utente** con il nome del file.

- [ ] **Passo 2: scrivere i test**

```python
def test_discovery_calcola():
    strumento = catalogo()["calcola"]
    assert "espressione" in strumento.inputSchema["properties"]
    assert strumento.inputSchema["required"] == ["espressione"]
    assert strumento.description  # descrizione pubblicata dal server

def test_invocazione_diretta_calcola():
    risultato = chiama("calcola", {"espressione": "2+3*4"})
    assert not risultato.is_error and risultato.content[0].text == "14"

def test_errore_controllato_calcola():
    risultato = chiama("calcola", {"espressione": "__import__('os')"})
    assert risultato.is_error and "non ammess" in risultato.content[0].text
```

- [ ] **Passo 3: test che falliscono** — `.\.venv\Scripts\python.exe -m pytest tests/test_server_mcp.py -q` → import error.

- [ ] **Passo 4: implementare `assistente/server_mcp.py`** secondo le interfacce. Descrizione di `calcola`: dice che valuta espressioni aritmetiche con numeri, `+ - * / // % **` e parentesi, e che va usata per ogni calcolo.

- [ ] **Passo 5: test verdi** — stesso comando, tutti passati; poi l'intera suite (atteso: solo il fallimento noto di `jiter`).

- [ ] **Passo 6: commit**

```powershell
git add -- requirements.txt assistente/server_mcp.py tests/test_server_mcp.py
git commit -m "feat(mcp): server FastMCP con lo strumento calcola"
```

### Task 3: Collegamento MCP (discovery e strumenti sincroni)

**File:**
- Modifica: `assistente/errori.py` (due nuove classi)
- Crea: `assistente/collegamento_mcp.py`
- Test: `tests/test_collegamento_mcp.py`

**Interfacce:**
- Produce in `errori.py`: `class ErroreStrumento(Exception)` (lo strumento ha rifiutato l'input: il messaggio è per il modello) e `class ErroreCollegamentoMCP(Exception)` (server non avviabile o caduto).
- Produce in `collegamento_mcp.py`:
  - `connessione_stdio(cartella: Path) -> dict` → `{"transport": "stdio", "command": sys.executable, "args": ["-m", "assistente.server_mcp"], "cwd": str(cartella)}`;
  - `carica_strumenti_mcp(connessione: dict) -> list[BaseTool]` → `asyncio.run(load_mcp_tools(None, connection=connessione, handle_tool_errors=False))`, poi `rendi_sincrono` su ciascuno; registra `INFO assistente.collegamento_mcp: discovery server=assistente.server_mcp tools=[…]`; qualunque eccezione → `ErroreCollegamentoMCP(<motivo leggibile>)`;
  - `rendi_sincrono(strumento: BaseTool) -> BaseTool` → `StructuredTool` con **stessi** `name`, `description`, `args_schema` dell'originale e `metadata={"variante": "mcp"}`; la funzione esegue `asyncio.run(strumento.ainvoke(argomenti))`, restituisce il testo concatenato dei blocchi `{"type": "text"}` (o la stringa se già stringa); `ToolException` → `ErroreStrumento(<testo dei blocchi>)`; ogni altra eccezione → `ErroreCollegamentoMCP(str(e) o nome della classe)`.

- [ ] **Passo 1: scrivere i test** (avviano davvero il server via stdio: nessuna rete)

```python
CARTELLA = Path(__file__).resolve().parent.parent

def test_discovery_dal_server_reale():
    strumenti = {s.name: s for s in carica_strumenti_mcp(connessione_stdio(CARTELLA))}
    assert "calcola" in strumenti
    assert strumenti["calcola"].metadata == {"variante": "mcp"}
    assert "espressione" in strumenti["calcola"].args  # schema venuto dal server

def test_invocazione_sincrona():
    calcola = {s.name: s for s in carica_strumenti_mcp(connessione_stdio(CARTELLA))}["calcola"]
    assert calcola.invoke({"espressione": "2+3*4"}) == "14"

def test_errore_dello_strumento():
    calcola = {s.name: s for s in carica_strumenti_mcp(connessione_stdio(CARTELLA))}["calcola"]
    with pytest.raises(ErroreStrumento, match="non ammess"):
        calcola.invoke({"espressione": "abs(1)"})

def test_server_non_avviabile():
    rotta = {**connessione_stdio(CARTELLA), "args": ["-m", "modulo_che_non_esiste"]}
    with pytest.raises(ErroreCollegamentoMCP):
        carica_strumenti_mcp(rotta)

def test_collegamento_caduto_durante_la_chiamata():
    async def cade(**_):
        raise RuntimeError("Connection closed")
    originale = StructuredTool.from_function(coroutine=cade, name="calcola", description="d",
                                             args_schema={"type": "object", "properties": {}})
    with pytest.raises(ErroreCollegamentoMCP, match="Connection closed"):
        rendi_sincrono(originale).invoke({})
```

- [ ] **Passo 2: test che falliscono** — `.\.venv\Scripts\python.exe -m pytest tests/test_collegamento_mcp.py -q`.
- [ ] **Passo 3: implementare** `errori.py` e `collegamento_mcp.py` secondo le interfacce.
- [ ] **Passo 4: test verdi** (stesso comando) e suite completa.
- [ ] **Passo 5: commit**

```powershell
git add -- assistente/errori.py assistente/collegamento_mcp.py tests/test_collegamento_mcp.py
git commit -m "feat(mcp): discovery via stdio e strumenti MCP sincroni"
```

### Task 4: Grafo — log per variante ed errori correlati

**File:**
- Modifica: `assistente/grafo.py` (`esegui_strumenti`, `PROMPT_SISTEMA`)
- Modifica: `tests/finti.py` (strumenti finti MCP), `tests/test_grafo.py`

**Interfacce:**
- Consuma: `ErroreStrumento`, `ErroreCollegamentoMCP`, `metadata["variante"]` (Task 3).
- Produce: righe di log (logger `assistente.grafo`, INFO) esattamente:
  - `variant=<local|mcp> tool=<nome> call_id=<id> arguments=<json.dumps(args, ensure_ascii=False)>`
  - `variant=<…> tool=<nome> call_id=<id> execution=<ok|tool_error|connection_error|unknown_tool> result=<testo troncato a 200 caratteri>`
  - `tool_message.call_id=<id> next_node=llm`
  La variante è `strumento.metadata.get("variante", "local")` se `metadata` non è `None`, altrimenti `local`; per strumento sconosciuto `variant=unknown`.
- Contenuto del `ToolMessage`: successo → risultato; `ErroreStrumento` → `Errore dello strumento: <msg>`; `ErroreCollegamentoMCP` → `Errore di collegamento con il server MCP: <msg>`; sconosciuto → `Strumento sconosciuto: <nome>` (invariato). Sempre `tool_call_id` della richiesta e `name`.
- `PROMPT_SISTEMA`: mantiene la frase su `ora_corrente` e aggiunge che gli altri strumenti disponibili (calcoli, conversioni di unità, giorni e scadenze, catalogo dei corsi, note, meteo) vanno chiamati quando la domanda li riguarda, invece di rispondere a memoria. Gli elenchi degli strumenti non ancora presenti sono innocui: il modello vede solo quelli ricevuti con `bind_tools`.
- `tests/finti.py` produce: `strumento_finto(nome: str, comportamento: Callable[[dict], str], variante: str = "mcp") -> StructuredTool` e `richiesta(nome: str, argomenti: dict, id_chiamata: str) -> AIMessage`.

- [ ] **Passo 1: scrivere i test** in `tests/test_grafo.py`:
  - `test_log_strumento_locale` — giro con `ora_corrente`: caplog contiene `variant=local tool=ora_corrente call_id=call_1 arguments={}`, `execution=ok result=` + `ORA_FISSA`, `tool_message.call_id=call_1 next_node=llm`.
  - `test_strumento_mcp_ok` — strumento finto `calcola` che restituisce `"14"`: `ToolMessage(content="14", tool_call_id="c1")`, log `variant=mcp tool=calcola call_id=c1 arguments={"espressione": "2+3*4"}` ed `execution=ok`.
  - `test_errore_dello_strumento_correlato` — finto che solleva `ErroreStrumento("costrutto non ammesso: Call")`: `ToolMessage.content == "Errore dello strumento: costrutto non ammesso: Call"`, stesso `tool_call_id`, `execution=tool_error`, il grafo torna a `llm` (2 chiamate al modello) e la risposta finale è quella del modello.
  - `test_errore_di_collegamento_correlato` — finto che solleva `ErroreCollegamentoMCP("processo terminato")`: contenuto `Errore di collegamento con il server MCP: processo terminato`, `execution=connection_error`, turno non interrotto.
  - `test_limite_passi_con_strumento_mcp` — modello che chiede sempre `calcola`: con `max_passi=3` il grafo si ferma con 3 chiamate al modello.
  - i test esistenti restano verdi (aggiornare solo quelli che controllano le vecchie righe di log).
- [ ] **Passo 2: test che falliscono** — `.\.venv\Scripts\python.exe -m pytest tests/test_grafo.py -q`.
- [ ] **Passo 3: implementare** in `grafo.py` secondo le interfacce (try/except attorno a `strumento.invoke`).
- [ ] **Passo 4: test verdi** e suite completa.
- [ ] **Passo 5: commit**

```powershell
git add -- assistente/grafo.py tests/finti.py tests/test_grafo.py
git commit -m "feat(grafo): log per variante e ToolMessage correlato anche per gli errori MCP"
```

### Task 5: Avvio dell'applicazione, prova reale e merge

**File:**
- Modifica: `assistente/terminale.py` (`main`), `tests/test_terminale.py`, `tests/test_reale.py`, `README.md`

**Interfacce:**
- Consuma: `carica_strumenti_mcp`, `connessione_stdio`, `ErroreCollegamentoMCP`.
- `main()`: dopo la configurazione e i log, `strumenti = crea_strumenti(config.fuso_orario) + carica_strumenti_mcp(connessione_stdio(Path.cwd()))`; su `ErroreCollegamentoMCP` stampa su stderr `Server MCP non disponibile: <motivo>` e restituisce `3`.
- `tests/test_reale.py`: la fixture `conversazione` usa gli stessi strumenti di `main` (orologio + MCP). Helper `strumenti_usati` invariato.

- [ ] **Passo 1: test** in `tests/test_terminale.py`: `test_main_server_mcp_non_disponibile` — con `monkeypatch` su `assistente.terminale.carica_strumenti_mcp` che solleva `ErroreCollegamentoMCP("prova")` e un `.env` valido in `tmp_path` (`monkeypatch.chdir`), `main()` restituisce `3` e `capsys` mostra `Server MCP non disponibile: prova` su stderr. Il modello non va creato prima di caricare gli strumenti MCP (così il test non tocca `jiter`).
  In `tests/test_reale.py`: `test_calcolo_usa_calcola` — «Quanto fa 1234 per 5678?» → `strumenti_usati == ["calcola"]` e `"7006652"` nella risposta privata di spazi e punti.
- [ ] **Passo 2: test che falliscono** — `.\.venv\Scripts\python.exe -m pytest tests/test_terminale.py -q`.
- [ ] **Passo 3: implementare** `main()`.
- [ ] **Passo 4: test verdi** e suite completa.
- [ ] **Passo 5: Docker** — `docker compose build`, poi
  `docker compose run --rm -T assistente python -c "from pathlib import Path; from assistente.collegamento_mcp import carica_strumenti_mcp, connessione_stdio; print([s.name for s in carica_strumenti_mcp(connessione_stdio(Path.cwd()))])"`
  Atteso: `['calcola']`.
- [ ] **Passo 6: prova reale** (con LM Studio; in locale `$env:PROVE_REALI = "1"; .\.venv\Scripts\python.exe -m pytest -m reale -v; Remove-Item Env:PROVE_REALI`, oppure in Docker come nei vincoli globali). Domande: «Quanto fa 1234 per 5678?», «Quanto fa abs(3)?», «Che ore sono?», «Mi chiamo Luca» / «Come mi chiamo?». Evidenze nei log: `variant=mcp tool=calcola … arguments=…`, `execution=ok`, `tool_message.call_id=… next_node=llm`, seconda chiamata al modello; per `abs(3)` `execution=tool_error` senza un risultato inventato (se il modello corregge l'input da solo, annotarlo); orologio e cronologia ancora funzionanti.
- [ ] **Passo 7: README** — sezioni aggiornate: preparazione (nuove dipendenze), «Strumenti MCP» (server, discovery all'avvio, errore `Server MCP non disponibile`, codice 3), nuovo formato dei log con esempio reale, `calcola` con esempi, test del server e del collegamento, diagnosi per livelli (tabella di p. 24 del PDF adattata), checklist con le domande del Passo 6, esiti reali con data. Solo comandi eseguiti davvero.
- [ ] **Passo 8: commit e merge**

```powershell
git add -- assistente/terminale.py tests/test_terminale.py tests/test_reale.py README.md
git commit -m "feat(terminale): avvia il server MCP e carica il catalogo all'avvio"
git switch dev; git merge --no-ff feat/calcolatrice -m "merge: calcolatrice e base MCP"
```

---

## Struttura comune dei task 6–10

Ogni strumento: `git switch dev; git switch -c feat/<nome>` → modulo di dominio + test → registrazione in `server_mcp.py` + test in `tests/test_server_mcp.py` (discovery: nomi e `required` dello schema; invocazione diretta con input noto; errore controllato) → test reale in `tests/test_reale.py` → prova reale e README (descrizione dello strumento, esempi, casi d'errore, checklist, esito) → commit → `git switch dev; git merge --no-ff feat/<nome>`. Test di discovery aggiuntivo comune: `test_catalogo_completo` in `tests/test_server_mcp.py` aggiornato a ogni strumento con l'insieme esatto dei nomi presenti.

### Task 6: Convertitore di unità — `feat/convertitore`

**File:** crea `assistente/strumenti_mcp/convertitore.py`, `tests/test_convertitore.py`; modifica `assistente/server_mcp.py`, `tests/test_server_mcp.py`, `tests/test_reale.py`, `README.md`.

**Interfacce:** `converti_unita(valore: float, da_unita: str, a_unita: str) -> str` → `"<valore> <da_unita> = <risultato> <a_unita>"`, numeri con al massimo 4 decimali senza zeri finali. Unità (simboli esatti, sensibili alle maiuscole): lunghezza `mm cm m km in ft mi` (fattori in metri 0.001, 0.01, 1, 1000, 0.0254, 0.3048, 1609.344); massa `g kg lb oz` (in kg 0.001, 1, 0.45359237, 0.028349523125); temperatura `C F K` (via kelvin). La descrizione dello strumento elenca tutte le unità.

- [ ] **Passo 1: test** — `converti_unita(10, "km", "mi") == "10 km = 6.2137 mi"`; `converti_unita(100, "C", "F") == "100 C = 212 F"`; `converti_unita(0, "K", "C") == "0 K = -273.15 C"`; `converti_unita(1, "lb", "g") == "1 lb = 453.5924 g"`; errori `ValueError`: `"parsec"` (messaggio con l'elenco delle unità ammesse), `"m"→"kg"` («incompatibil»), `-300 C` («zero assoluto»), `-1 K` («zero assoluto»). Server: discovery `converti_unita` con `required == ["valore", "da_unita", "a_unita"]`, invocazione diretta, errore `m→kg`. Reale: «Quanti miglia sono 10 km?» → `strumenti_usati == ["converti_unita"]`.
- [ ] **Passo 2: fallimento** — `.\.venv\Scripts\python.exe -m pytest tests/test_convertitore.py tests/test_server_mcp.py -q`.
- [ ] **Passo 3: implementare** dominio e registrazione.
- [ ] **Passo 4: test verdi** e suite completa.
- [ ] **Passo 5: prova reale** («Quanti miglia sono 10 km?», «Converti 5 metri in chilogrammi»: errore senza numero inventato) e README.
- [ ] **Passo 6: commit e merge**

```powershell
git add -- assistente/strumenti_mcp/convertitore.py tests/test_convertitore.py assistente/server_mcp.py tests/test_server_mcp.py tests/test_reale.py README.md
git commit -m "feat(convertitore): conversione di unità da elenco chiuso via MCP"
git switch dev; git merge --no-ff feat/convertitore -m "merge: convertitore di unità"
```

### Task 7: Giorni e scadenze — `feat/giorni-scadenze`

**File:** crea `assistente/strumenti_mcp/giorni.py`, `assistente/dati/festivita.json`, `tests/test_giorni.py`; modifica server, `tests/test_server_mcp.py`, `tests/test_reale.py`, `README.md`.

**Interfacce:**
- `conta_giorni(data_inizio: str, data_fine: str, festivita: dict[date, str]) -> str` e `aggiungi_giorni_lavorativi(data_inizio: str, giorni: int, festivita: dict[date, str]) -> str`; `carica_festivita(percorso: Path) -> dict[date, str]`. Il server carica una volta `assistente/dati/festivita.json` (percorso relativo a `server_mcp.py`) e espone i due strumenti **senza** il parametro `festivita`.
- `festivita.json`: `{"anni": [2026, 2027], "festivita": [{"data": "2026-01-01", "nome": "Capodanno"}, …]}` con, per ciascun anno: Capodanno 1/1, Epifania 6/1, Pasqua (2026-04-05; 2027-03-28), Lunedì dell'Angelo (2026-04-06; 2027-03-29), Liberazione 25/4, Lavoro 1/5, Repubblica 2/6, Ferragosto 15/8, San Francesco 4/10, Ognissanti 1/11, Immacolata 8/12, Natale 25/12, Santo Stefano 26/12. Verificare le date di Pasqua su una fonte affidabile durante il task.
- Regole: specifica §7.3 (inizio escluso, fine inclusa; partenza mai contata; lavorativo = lun–ven non festivo). Ogni risultato termina con `(calcolo indicativo, non normativo)`.

- [ ] **Passo 1: test** —
  - `conta_giorni("2026-12-23", "2026-12-28", F)`: 5 giorni di calendario, 2 lavorativi (24 e 28), festività incluse Natale e Santo Stefano;
  - stessa data → 0 e 0;
  - `aggiungi_giorni_lavorativi("2026-12-23", 2, F)` → `2026-12-28`;
  - partenza di sabato `2026-11-07`, 1 giorno → `2026-11-09`;
  - `aggiungi_giorni_lavorativi("2026-10-02", 1, F)` → `2026-10-05` (il 4/10 cade di domenica: nessun effetto);
  - errori `ValueError`: `"03/11/2026"` (ISO), `"2026-02-30"` (inesistente), fine prima dell'inizio, `"2025-12-31"` o scadenza che supera il 2027-12-31 (anni non disponibili), `giorni` 0 e 366;
  - ogni risultato contiene `non normativo`.
  Server: discovery dei due nomi con i rispettivi `required`, invocazione diretta, errore ISO. Reale: «Quanti giorni lavorativi ci sono tra il 23 e il 28 dicembre 2026?» → `"conta_giorni" in strumenti_usati`.
- [ ] **Passo 2: fallimento** — `.\.venv\Scripts\python.exe -m pytest tests/test_giorni.py tests/test_server_mcp.py -q`.
- [ ] **Passo 3: implementare** dominio, file dati, registrazione.
- [ ] **Passo 4: test verdi** e suite completa; Docker: `docker compose build` e discovery nel container (comando del Task 5, Passo 5) con i tre strumenti.
- [ ] **Passo 5: prova reale** (domanda sopra; «Che data è 10 giorni lavorativi dopo il 2026-12-20?») e README.
- [ ] **Passo 6: commit e merge** (`feat(giorni): conteggio di giorni e scadenze con festività locali`; merge `giorni e scadenze`), con staging dei soli file elencati sopra.

### Task 8: Catalogo locale — `feat/catalogo`

**File:** crea `assistente/strumenti_mcp/catalogo.py`, `assistente/dati/catalogo.json`, `tests/test_catalogo.py`; modifica server, `tests/test_server_mcp.py`, `tests/test_reale.py`, `README.md`.

**Interfacce:**
- `carica_catalogo(percorso: Path) -> list[dict]`; `cerca_corsi(testo: str, max_risultati: int, corsi: list[dict]) -> str`; `dettaglio_corso(codice: str, corsi: list[dict]) -> str`. Il server espone `cerca_corsi(testo: str, max_risultati: int = 5)` e `dettaglio_corso(codice: str)`.
- `catalogo.json`: lista di 10 corsi inventati `{"codice", "titolo", "sede", "durata_ore"}`; codici `ITS-<AREA>-<NN>`, sedi tra Pordenone, Udine, Trieste; almeno due corsi con «Python» nel titolo e uno con codice `ITS-AI-01`.
- Ricerca: sottostringa senza distinzione di maiuscole in titolo, codice o sede, ordine del file. Nessun risultato → `Nessun corso trovato per "<testo>".` (non è un errore). Descrizioni chiaramente diverse: ricerca per parole → elenco breve; dettaglio completo dato un codice esatto.

- [ ] **Passo 1: test** —
  - `cerca_corsi("python", 5, C)` elenca i corsi con Python;
  - `cerca_corsi("python", 1, C)` ne elenca uno solo;
  - `cerca_corsi("astronautica", 5, C)` → `Nessun corso trovato`;
  - `dettaglio_corso("ITS-AI-01", C)` contiene titolo, sede e durata;
  - errori `ValueError`: testo vuoto, `max_risultati` 0 e 21, codice inesistente.
  Server: discovery dei due strumenti, invocazione diretta, errore codice inesistente. Reale: «Quanto dura il corso di Python a Udine?» → `strumenti_usati == ["cerca_corsi", "dettaglio_corso"]` (se il modello ne usa uno solo, registrarlo come esito).
- [ ] **Passo 2–4:** fallimento, implementazione, test verdi (come sopra, con `tests/test_catalogo.py`).
- [ ] **Passo 5: prova reale** (domanda sopra; «Ci sono corsi di astronautica?» → risposta senza corsi inventati; nei log quale strumento viene scelto) e README.
- [ ] **Passo 6: commit e merge** (`feat(catalogo): ricerca e dettaglio sul catalogo locale dei corsi`; merge `catalogo locale`).

### Task 9: Note persistenti — `feat/note`

**File:** crea `assistente/strumenti_mcp/note.py`, `tests/test_note.py`; modifica server, `tests/test_server_mcp.py`, `tests/test_reale.py`, `.gitignore` (`archivio/`), `.dockerignore` (`archivio/`), `compose.yaml` (volume `./archivio:/app/archivio`), `README.md`.

**Interfacce:**
- `aggiungi_nota(testo: str, percorso: Path) -> str`, `elenca_note(limite: int, percorso: Path) -> str`, `elimina_nota(id_nota: int, percorso: Path) -> str`. Tabella creata al primo uso: `note(id INTEGER PRIMARY KEY AUTOINCREMENT, testo TEXT NOT NULL, creata TEXT NOT NULL)`; `creata = datetime.now().astimezone().isoformat(timespec="seconds")`; cartella creata se manca. Ogni `sqlite3.Error` → `ValueError("Archivio delle note non accessibile: …")`.
- Server: `PERCORSO_NOTE = Path("archivio/note.sqlite")` (relativo alla cartella di lavoro); strumenti `aggiungi_nota(testo)`, `elenca_note(limite: int = 10)`, `elimina_nota(id_nota: int)`; log su stderr `nota creata id=<id>`, `nota eliminata id=<id>`, `eliminazione rifiutata id=<id> inesistente`. Descrizioni: «salva in modo permanente», «elimina definitivamente la sola nota con questo ID».
- Risultati: `Nota <id> creata il <creata>: <testo>`; elenco ordinato per ID crescente, `Nessuna nota salvata.` se vuoto; `Nota <id> eliminata: <testo>`.

- [ ] **Passo 1: test** (`tmp_path`) —
  - aggiunta → ID 1, poi 2;
  - elenco ordinato;
  - `limite` 1 restituisce la prima;
  - eliminazione della 1 → conferma con il testo; la 2 resta;
  - persistenza: nuova chiamata con lo stesso percorso vede le note;
  - errori: testo vuoto, testo di soli spazi, 501 caratteri, `limite` 0 e 51;
  - `elimina_nota(99)` → errore e il numero di note non cambia;
  - percorso che è una cartella → «non accessibile».
  Server: discovery dei tre strumenti, invocazione diretta, errore ID 99, con `monkeypatch.setattr(server_mcp, "PERCORSO_NOTE", tmp_path / "note.sqlite")` (le funzioni del server leggono `PERCORSO_NOTE` al momento della chiamata). Reale: «Ricordami di consegnare il report venerdì» → `strumenti_usati == ["aggiungi_nota"]`; usa l'archivio vero del progetto (la cartella di lavoro deve restare quella del progetto, altrimenti il sottoprocesso non trova il pacchetto `assistente`): il README dice di eliminare la nota di prova o il file dopo la prova.
- [ ] **Passo 2–4:** fallimento, implementazione, test verdi; `git status` non deve mostrare `archivio/`.
- [ ] **Passo 5: prova reale** — i tre casi del PDF: una sola `aggiungi_nota`; «Elimina la nota 99» → errore, nessuna eliminazione; chiusura e riavvio dell'applicazione (anche Docker con `--rm`) → «Quali note ho?» le mostra. README (dove stanno le note, come cancellarle: eliminare `archivio\note.sqlite`).
- [ ] **Passo 6: commit e merge** (`feat(note): note persistenti su SQLite via MCP`; merge `note persistenti`), con `.gitignore`, `.dockerignore`, `compose.yaml` nello staging.

### Task 10: Meteo — `feat/meteo`

**File:** crea `assistente/strumenti_mcp/meteo.py`, `tests/test_meteo.py`; modifica `requirements.txt` (`httpx==0.28.1` con commento), server, `tests/test_server_mcp.py`, `tests/test_reale.py`, `README.md`.

**Interfacce:**
- `meteo_citta(citta: str, client: httpx.Client) -> str`; il server crea `httpx.Client(timeout=10.0)` ed espone `meteo_citta(citta: str)`.
- Chiamate: `GET https://geocoding-api.open-meteo.com/v1/search` con `name`, `count=5`, `language=it`, `format=json`; poi `GET https://api.open-meteo.com/v1/forecast` con `latitude`, `longitude`, `current=temperature_2m,weather_code`, `timezone=auto`.
- Risultato: `Meteo a <nome>, <admin1>, <paese> (<lat>, <lon>) alle <current.time> (<timezone>): <temperatura> <current_units.temperature_2m>, <condizione>.`; se il geocoding ha più risultati aggiunge `Scelta la prima corrispondenza; altre: <nome, admin1, paese>; …`.
- Condizioni WMO in italiano: 0 sereno; 1 prevalentemente sereno; 2 parzialmente nuvoloso; 3 coperto; 45, 48 nebbia; 51, 53, 55 pioviggine; 61, 63, 65 pioggia; 71, 73, 75 neve; 80, 81, 82 rovesci; 95 temporale; 96, 99 temporale con grandine; altro → `condizione non riconosciuta (codice <n>)`.
- Errori (`ValueError`, messaggi distinti): città vuota → «città non indicata»; nessun `results` → «Città non trovata: <citta>»; `httpx.TimeoutException` → «Servizio meteo: attesa scaduta»; `httpx.TransportError` → «Servizio meteo non raggiungibile»; stato HTTP ≥ 400 → «Servizio meteo: errore HTTP <codice>»; JSON non valido o campi mancanti → «Servizio meteo: risposta non valida».

- [ ] **Passo 1: test** con `httpx.Client(transport=httpx.MockTransport(gestore))` —
  - città unica → risultato con temperatura, unità `°C`, condizione e ora;
  - città con due risultati → testo con `altre:`;
  - nessun risultato → «Città non trovata»;
  - `ConnectError` → «non raggiungibile» e **non** «non trovata»;
  - `ReadTimeout` → «attesa scaduta»;
  - 503 → «errore HTTP 503»;
  - corpo non JSON → «risposta non valida»;
  - codice WMO 999 → «non riconosciuta».
  Server: discovery `meteo_citta` (`required == ["citta"]`) e errore città vuota (senza rete). Reale (richiede rete): «Che tempo fa a Pordenone?» → `strumenti_usati == ["meteo_citta"]`.
- [ ] **Passo 2–4:** fallimento, implementazione, test verdi (nessun test automatico usa la rete).
- [ ] **Passo 5: prova reale** — in locale/Docker: domanda sopra; città inesistente; rete scollegata (o Wi-Fi spento) → errore di rete distinto. In Docker verificare che il container raggiunga Open-Meteo: `docker compose run --rm -T assistente python -c "import httpx; print(httpx.get('https://api.open-meteo.com/v1/forecast?latitude=46&longitude=12.6&current=temperature_2m', timeout=10).status_code)"` → `200`. README.
- [ ] **Passo 6: commit e merge** (`feat(meteo): meteo attuale da Open-Meteo via MCP`; merge `meteo`).

---

## Task 11: Verifica complessiva e passaggio a `main`

**Branch:** `dev`.

- [ ] **Passo 1:** `.\.venv\Scripts\python.exe -m pytest -q` → tutti verdi tranne il fallimento noto di `jiter` (se ancora presente).
- [ ] **Passo 2:** `docker compose build` e discovery nel container → i 10 strumenti MCP (`calcola`, `converti_unita`, `conta_giorni`, `aggiungi_giorni_lavorativi`, `cerca_corsi`, `dettaglio_corso`, `aggiungi_nota`, `elenca_note`, `elimina_nota`, `meteo_citta`).
- [ ] **Passo 3:** checklist completa del README in una sola sessione (locale o Docker): uno strumento per tipo, orologio, cronologia («Mi chiamo Luca» / «Come mi chiamo?»), LM Studio fermo e riavviato, `esci` e Ctrl+C, accenti. Esiti con data nel README; `git add -- README.md; git commit -m "docs: esiti delle prove reali della lezione 5"`.
- [ ] **Passo 4:** presentare all'utente l'elenco degli esiti (riusciti / falliti con il punto esatto / non eseguiti) e **chiedere conferma** per il merge in `main`.
- [ ] **Passo 5 (solo con conferma):** `git switch main; git merge --no-ff dev -m "merge: lezione 5, sei strumenti MCP"`. Nessun push senza richiesta esplicita.
