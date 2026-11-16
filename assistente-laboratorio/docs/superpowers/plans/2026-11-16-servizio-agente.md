# Step 6, l'agente come servizio HTTP — Piano di implementazione

> **Per chi esegue:** SOTTO-SKILL OBBLIGATORIA: usare superpowers:executing-plans (esecuzione diretta, modo di lavoro veloce di `CLAUDE.local.md`) per eseguire il piano task per task. I passi usano le caselle (`- [ ]`) per il tracciamento.

**Obiettivo:** lo stesso grafo risponde alla CLI e alle chiamate HTTP: un servizio FastAPI senza stato (`POST /messaggio`, `GET /stato`, `GET /prompts`, `POST /prompts/{nome}`, `/docs`) e una CLI che ne è solo client.

**Architettura:** `assistente/formato.py` (modelli pydantic dei messaggi e conversione LangChain ⇄ JSON) → `assistente/agente.py` (turno senza stato `esegui_turno`, classe `Agente` con prompt e stato, `costruisci_agente` spostato da `terminale.main`) → `assistente/servizio.py` (app FastAPI, codici di errore, `main` con uvicorn) ← `assistente/cliente.py` (client httpx che tiene cronologia e riassunto) ← `assistente/terminale.py` (CLI). `Conversazione` resta come client in memoria e delega a `esegui_turno`.

**Tecnologie:** Python 3.13, `fastapi` 0.163.1 (nuova), `uvicorn` 0.54.0 (fissata), `httpx` 0.28.1, pydantic 2, LangGraph, pytest.

**Specifica:** `docs/superpowers/specs/2026-11-16-servizio-agente-design.md` (commit `b466322` su `feat/servizio-agente`, approvata). Chi esegue legge **entrambi** i documenti; i §n sono della specifica.

Percorsi relativi a `assistente-laboratorio/`; comandi da PowerShell in quella cartella con `.\.venv\Scripts\python.exe -m pytest ...`. Branch: `feat/servizio-agente` (già creato da `dev`).

## Vincoli globali

- **Modo di lavoro veloce** (`CLAUDE.local.md`): i task si eseguono per blocchi senza conferme; ci si ferma solo per merge, push, Docker, prove manuali dell'utente, dipendenze non approvate, cose distruttive o fuori dal piano. Le modifiche ai file degli step precedenti elencati nel §4 sono approvate con la specifica; **`grafo.py`, `router.py`, `revisore.py`, `riassunto.py`, `preferenze.py`, `server_mcp.py`, `strumenti_mcp/`, `modello.py`, `errori.py`, `collegamento_mcp.py`, `prompt_mcp.py` non cambiano.**
- Dipendenze approvate: `fastapi==0.163.1`, `uvicorn==0.54.0`. Nessun'altra.
- Nessun anticipo degli step 7–9: niente database, CORS, front-end, streaming.
- Valori fissati dalla specifica:
  - percorsi `POST /messaggio`, `GET /stato`, `GET /prompts`, `POST /prompts/{nome}`, `/docs`, `/openapi.json`;
  - campi del messaggio: `ruolo` (`utente`/`assistente`/`strumento`), `testo`, `nome`, `richieste_strumenti` (`id`, `nome`, `argomenti`), `id_chiamata`;
  - risposta di un turno: `risposta`, `strumenti_usati` (`nome`, `argomenti`, `risultato`), `cronologia`, `riassunto`;
  - errori `{"errore": "<messaggio>"}`: connessione 503, attesa 504, errore dal server 502, risposta vuota 502, limite di passaggi 500, inatteso 500, server MCP giù per i prompt 503, comando prompt non valido 400, corpo non valido 422 (standard FastAPI);
  - `/stato`: chiavi `agente`, `server_mcp`, `modello`, valore `ok` o messaggio; 200 se tutto `ok`, altrimenti 503; timeout del controllo del modello 5 s;
  - variabili `AGENTE_URL` (predefinita `http://localhost:8000`), `AGENTE_HOST` (`127.0.0.1`), `AGENTE_PORTA` (`8000`);
  - messaggio della CLI senza agente: `Agente non raggiungibile: controllare che il servizio sia avviato e AGENTE_URL.`; timeout del client 600 s;
  - codici di uscita del servizio: 2 configurazione non valida, 3 server MCP non disponibile (stesso testo di oggi `Server MCP non disponibile: <motivo>`);
  - log del servizio (logger `assistente.servizio`, INFO): `richiesta endpoint=<percorso> messaggi_cronologia=<n> riassunto=sì|no` e `risposta endpoint=<percorso> strumenti=<lista dei nomi> messaggi_cronologia=<m>`; per un errore `errore endpoint=<percorso> codice=<codice> messaggio=<messaggio>` (WARNING).
- Codice sincrono; gli endpoint sono `def`, non `async def`. Commenti didattici in italiano nello stile dei file esistenti; intestazione «COSA FA QUESTO FILE» nei moduli nuovi.
- Git: staging per percorsi espliciti; mai nello staging i 4 file della Lezione 3 in radice, `HANDOFF*.md`, `HANDOFF_PROMPT.txt`, `PROMPT-ripresa-*.txt`; Conventional Commits in italiano con `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; messaggio scritto senza BOM (`[IO.File]::WriteAllText($f, $testo, [Text.UTF8Encoding]::new($false))`) e `git commit -F`; nessun push, nessun merge senza conferma.
- Mai distruggere `archivio/preferenze.json` (prove reali con `preferenze_protette`); il `.env` dell'utente non si tocca.

## Punti da sorvegliare (Review Focus)

1. **Cronologia incoerente dal chiamante** (un messaggio `strumento` il cui `id_chiamata` non corrisponde a nessuna richiesta precedente): 422 senza chiamare il modello → test in Task 1 (`test_strumento_senza_richiesta_e_rifiutato`) e Task 4.
2. **Accenti e caratteri come «» nel messaggio**: andata e ritorno JSON identici e log leggibile → test in Task 1 e Task 4.
3. **Compressione del riassunto durante il turno**: `strumenti_usati` deve contenere solo i tool del turno, anche se il riassunto ha tolto messaggi vecchi → test in Task 2.
4. **Risposta dell'agente non JSON o con un codice inatteso** (es. 404 per un `AGENTE_URL` con il percorso sbagliato): la CLI mostra un messaggio e continua, senza traceback → test in Task 5.
5. **Servizio avviato con LM Studio spento**: il servizio parte (la discovery non usa il modello) e `/stato` risponde 503 con `modello` che spiega → test in Task 3 e Task 4.

---

### Task 1: dipendenze e formato dei messaggi sull'API

**File:**
- Modificare: `requirements.txt` (aggiungere, con un commento di motivazione come le righe esistenti, `fastapi==0.163.1` e `uvicorn==0.54.0`)
- Creare: `assistente/formato.py`
- Test: `tests/test_formato.py`

**Interfacce:**
- Produce:
  - `class RichiestaStrumento(BaseModel)`: `id: str`, `nome: str`, `argomenti: dict[str, Any] = {}`
  - `class Messaggio(BaseModel)`: `ruolo: Literal["utente", "assistente", "strumento"]`, `testo: str = ""`, `nome: str | None = None`, `richieste_strumenti: list[RichiestaStrumento] = []`, `id_chiamata: str | None = None`; validatore: `strumento` richiede `id_chiamata`
  - `class StrumentoUsato(BaseModel)`: `nome: str`, `argomenti: dict[str, Any]`, `risultato: str`
  - `def controlla_cronologia(cronologia: Sequence[Messaggio]) -> None`: `ValueError` se un `strumento` risponde a un id mai richiesto prima nella lista
  - `def in_json(messaggi: Sequence[BaseMessage]) -> list[Messaggio]` (`HumanMessage`→utente, `AIMessage`→assistente con `tool_calls`, `ToolMessage`→strumento con `name` e `tool_call_id`; altri tipi → `ValueError`; testo da `.text`)
  - `def da_json(messaggi: Sequence[Messaggio]) -> list[BaseMessage]` (l'inverso; `nome` → `name`)

- [ ] **Passo 1: installare le dipendenze** — `.\.venv\Scripts\python.exe -m pip install fastapi==0.163.1 uvicorn==0.54.0`; atteso: installati solo `fastapi` e `annotated-doc` (uvicorn già presente).
- [ ] **Passo 2: test che falliscono** in `tests/test_formato.py`:
  - `test_andata_e_ritorno_di_un_giro_con_strumento`: `[HumanMessage("Quanto fa 45/9?"), AIMessage("", tool_calls=[{"name": "calcola", "args": {"espressione": "45/9"}, "id": "c1"}]), ToolMessage("5", tool_call_id="c1", name="calcola"), AIMessage("Fa 5.")]` → `da_json(in_json(m))` ha stessi tipi, testi, `tool_calls` (nome, argomenti, id), `tool_call_id`, `name`.
  - `test_indicazione_del_revisore_conserva_il_nome`: `HumanMessage("manca il meteo", name="revisore")` → `Messaggio(ruolo="utente", nome="revisore", ...)` e ritorno con `name == "revisore"`.
  - `test_accenti_e_virgolette_restano_uguali`: testo `«Perché» la città è così?` identico dopo `in_json` → `model_dump_json` → `model_validate_json` → `da_json`.
  - `test_messaggio_di_sistema_non_ammesso`: `in_json([SystemMessage("x")])` → `ValueError`.
  - `test_strumento_senza_id_chiamata_e_rifiutato`: `Messaggio(ruolo="strumento", testo="5")` → `ValidationError`.
  - `test_strumento_senza_richiesta_e_rifiutato`: `controlla_cronologia([Messaggio(ruolo="strumento", testo="5", id_chiamata="zzz")])` → `ValueError` con `zzz` nel messaggio; con la richiesta `zzz` prima nella lista → nessun errore.
  - `test_ruolo_sconosciuto_e_rifiutato`: `Messaggio(ruolo="sistema")` → `ValidationError`.
- [ ] **Passo 3: verificare che falliscano** — `-m pytest tests/test_formato.py -q`; atteso: errore di import di `assistente.formato`.
- [ ] **Passo 4: implementare `assistente/formato.py`** con le interfacce sopra.
- [ ] **Passo 5: verificare** — `-m pytest tests/test_formato.py -q` tutti verdi; `-m pytest -q` → 423 + nuovi passed, 17 skipped.
- [ ] **Passo 6: commit** — `requirements.txt`, `assistente/formato.py`, `tests/test_formato.py`; messaggio `feat(formato): messaggi della cronologia in JSON per l'API`.

### Task 2: turno senza stato (`esegui_turno`) e `Conversazione` che delega

**File:**
- Creare: `assistente/agente.py` (prima parte)
- Modificare: `assistente/conversazione.py` (`chiedi_messaggi` delega a `esegui_turno`; la logica del turno e i suoi log si spostano in `agente.py`)
- Test: `tests/test_agente.py`; `tests/test_conversazione.py` deve restare verde **senza modifiche**

**Interfacce:**
- Consuma: `StrumentoUsato` (Task 1); `traduci_errore` di `modello.py`.
- Produce:
  - `class ErroreTurnoAgente(ErroreTurno)`: `__init__(self, messaggio: str, tipo: str)`, attributo `tipo` in `{"connessione", "attesa", "server", "risposta_vuota", "limite_passi", "inatteso"}`; `str()` uguale al messaggio di oggi
  - `@dataclass(frozen=True) class EsitoTurno`: `risposta: str`, `strumenti_usati: list[StrumentoUsato]`, `cronologia: list[BaseMessage]`, `riassunto: str`
  - `def esegui_turno(grafo, cronologia: Sequence[BaseMessage], nuovi: Sequence[BaseMessage], riassunto: str) -> EsitoTurno`

Messaggi e log restano quelli di oggi (`Turno fallito: …` ERROR per gli errori tradotti, WARNING per la risposta vuota, `log.exception` per l'inatteso), ora dal logger `assistente.agente`. Tipo dall'eccezione originale: `APITimeoutError`→`attesa` (controllata prima di `APIConnectionError`→`connessione`), `APIStatusError`→`server`, non tradotta→`inatteso`.

**Algoritmo dei messaggi nuovi** (non lo determina la firma): prima di invocare, a ogni messaggio di `nuovi` senza `id` si assegna una copia con `id=str(uuid4())`; dopo, i messaggi del turno sono quelli del risultato dalla posizione del primo di `nuovi` (cercato per `id`) in poi. `strumenti_usati` = per ogni `AIMessage` del turno, nell'ordine, ogni `tool_call` abbinata al `ToolMessage` del turno con lo stesso `tool_call_id` (`risultato` = il suo testo; richiesta senza risultato → non contata).

- [ ] **Passo 1: test che falliscono** in `tests/test_agente.py` (stesso aiuto `grafo_con(...)` di `conversazione_con` in `test_conversazione.py`, ma restituisce il grafo):
  - `test_turno_restituisce_cronologia_e_riassunto`: risposta `"ciao"`, cronologia `[HumanMessage, AIMessage]`, riassunto `""`.
  - `test_turno_non_modifica_la_cronologia_ricevuta`: lista di 2 messaggi passata → stessa lunghezza e stessi testi dopo il turno; la cronologia dell'esito ne ha 4.
  - `test_strumenti_usati_del_turno`: modello `[richiesta_ora("c1"), AIMessage("Sono le 12")]` → `strumenti_usati == [StrumentoUsato(nome="ora_corrente", argomenti={}, risultato=ORA_FISSA)]`.
  - `test_strumenti_dei_turni_precedenti_non_contano`: cronologia ricevuta che contiene già un giro di `ora_corrente`, turno senza strumenti → `strumenti_usati == []`.
  - `test_strumenti_usati_dopo_la_compressione`: `soglia_riassunto=4`, `messaggi_da_tenere=2`, riassuntore `ModelloFinto([AIMessage("riassunto di prova")])`, cronologia di 4 messaggi con un giro di strumento vecchio, turno con `richiesta_ora("c9")` → solo `c9` in `strumenti_usati`, `riassunto == "riassunto di prova"`.
  - `test_errori_classificati` (parametrizzato): `APIConnectionError`→`connessione`, `APITimeoutError`→`attesa`, `APIStatusError` 404→`server`, `ValueError`→`inatteso`, `AIMessage("")`→`risposta_vuota`, `ModelloInsistente` con `max_passi=1`→`limite_passi`; messaggi uguali a quelli di `test_conversazione.py`.
- [ ] **Passo 2: verificare che falliscano** — `-m pytest tests/test_agente.py -q`.
- [ ] **Passo 3: implementare** `esegui_turno` ed `ErroreTurnoAgente`, `EsitoTurno` in `assistente/agente.py`; `Conversazione.chiedi_messaggi` = `esito = esegui_turno(self.grafo, self.cronologia, messaggi, self.riassunto)`, poi aggiorna `cronologia`/`riassunto` e restituisce `esito.risposta`.
- [ ] **Passo 4: verificare** — `-m pytest tests/test_agente.py tests/test_conversazione.py -q` verdi; suite completa verde.
- [ ] **Passo 5: commit** — `assistente/agente.py`, `assistente/conversazione.py`, `tests/test_agente.py`; `feat(agente): turno senza stato con gli strumenti usati`.

### Task 3: `Agente`, `costruisci_agente`, prompt e stato

**File:**
- Modificare: `assistente/agente.py` (seconda parte)
- Modificare: `tests/test_reale.py` (`crea_conversazione(config)` usa `costruisci_agente(config, Path.cwd())` e restituisce `Conversazione(agente.grafo)`; nessuna prova cambia)
- Test: `tests/test_agente.py`

**Interfacce:**
- Consuma: `esegui_turno`, `EsitoTurno` (Task 2); `connessione_stdio`, `carica_strumenti_mcp`, `carica_preferenze`, `elenca_prompt_mcp`, `richiama_prompt_mcp` di `collegamento_mcp.py`; `Configurazione`.
- Produce:
  - `@dataclass class Agente`: `grafo`, `connessione: dict`, `config: Configurazione`; metodi
    - `turno(self, cronologia: Sequence[BaseMessage], nuovi: Sequence[BaseMessage], riassunto: str) -> EsitoTurno`
    - `elenca_prompt(self) -> list[Prompt]` (rilancia `ErroreCollegamentoMCP`)
    - `richiama_prompt(self, nome: str, argomenti: dict[str, str], cronologia, riassunto) -> EsitoTurno` (rilancia `ErroreComandoPrompt` e `ErroreCollegamentoMCP` prima di chiamare il modello)
    - `stato(self) -> dict[str, str]` con chiavi `agente` (`"ok"`), `server_mcp`, `modello`
  - `def costruisci_agente(config: Configurazione, cartella: Path) -> Agente` — montaggio identico a `terminale.main()` punti 3–4 (stesso ordine: discovery, preferenze, strumenti, modelli, grafo); rilancia `ErroreCollegamentoMCP`
  - `def controlla_modello(config: Configurazione, leggi=httpx.get) -> str` — `GET {lm_base_url senza "/" finale}/models`, timeout 5: `"ok"` se `lm_model` è tra gli `id` di `data`; `"modello <id> non caricato in LM Studio"`; `"LM Studio non raggiungibile: controllare URL e porta"` per errori di rete; `"risposta non valida da LM Studio: <codice>"` per codici ≠ 200
  - `server_mcp` nello stato: `"ok"` se `carica_strumenti_mcp(connessione)` riesce, altrimenti `"non raggiungibile: <motivo>"`. Ogni controllo scrive una riga INFO `stato <voce>=<valore>`.

- [ ] **Passo 1: test che falliscono** (con `monkeypatch` sulle funzioni di `assistente.agente`, nessun server vero):
  - `test_costruisci_agente_server_giu`: `carica_strumenti_mcp` che lancia `ErroreCollegamentoMCP("prova")` → `costruisci_agente` lo rilancia e `carica_preferenze` non viene chiamata.
  - `test_costruisci_agente_usa_il_fuso_delle_preferenze` e `…_preferenze_non_disponibili_usa_il_fuso_di_ripiego`: spostati da `test_terminale.py` (`test_main_usa_il_fuso_delle_preferenze`, `test_main_con_preferenze_non_disponibili_usa_il_fuso_di_ripiego`) con le stesse asserzioni.
  - `test_controlla_modello` (parametrizzato con un `leggi` finto): elenco con il modello → `"ok"`; senza → `"modello modello-di-prova non caricato in LM Studio"`; `httpx.ConnectError` → `"LM Studio non raggiungibile: controllare URL e porta"`; codice 500 → `"risposta non valida da LM Studio: 500"`.
  - `test_stato_con_lm_studio_spento`: server MCP finto ok, modello spento → `{"agente": "ok", "server_mcp": "ok", "modello": "LM Studio non raggiungibile: controllare URL e porta"}`.
  - `test_richiama_prompt_passa_dal_grafo`: `richiama_prompt_mcp` finto che restituisce `[HumanMessage("Spiegami MCP")]` → `EsitoTurno` con la domanda nella cronologia.
  - `test_richiama_prompt_non_valido_non_chiama_il_modello`: `richiama_prompt_mcp` finto che lancia `ErroreComandoPrompt` → rilanciato, `ModelloFinto.chiamate == []`.
- [ ] **Passo 2: verificare che falliscano.**
- [ ] **Passo 3: implementare**; aggiornare `tests/test_reale.py` come sopra.
- [ ] **Passo 4: verificare** — suite completa verde; `-m pytest tests/test_reale.py --collect-only -q` senza errori di import.
- [ ] **Passo 5: prova reale mirata** — `$env:PROVE_REALI="1"; .\.venv\Scripts\python.exe -m pytest tests/test_reale.py -q -k "calcolo or sull_ora" ; Remove-Item Env:PROVE_REALI` (1 ripetizione): le prove esistenti girano con `costruisci_agente`.
- [ ] **Passo 6: commit** — `assistente/agente.py`, `tests/test_agente.py`, `tests/test_reale.py`; `feat(agente): costruzione dell'agente, prompt e controllo dello stato`.

### Task 4: il servizio FastAPI

**File:**
- Creare: `assistente/servizio.py`
- Modificare: `assistente/configurazione.py` (aggiungere la lettura di `AGENTE_HOST`/`AGENTE_PORTA`)
- Test: `tests/test_servizio.py`, `tests/test_configurazione.py`

**Interfacce:**
- Consuma: `Agente`, `EsitoTurno`, `ErroreTurnoAgente` (Task 2–3); `Messaggio`, `StrumentoUsato`, `in_json`, `da_json`, `controlla_cronologia` (Task 1).
- Produce:
  - in `configurazione.py`: `@dataclass(frozen=True) class IndirizzoServizio`: `host: str`, `porta: int`; `def carica_indirizzo_servizio(ambiente: Mapping[str, str]) -> IndirizzoServizio` (predefiniti `127.0.0.1` e `8000`; porta non intera o fuori 1–65535 → `ErroreConfigurazione("AGENTE_PORTA deve essere un intero tra 1 e 65535, non '<valore>'")`)
  - in `servizio.py`: modelli `RichiestaMessaggio` (`messaggio: str` con `min_length=1` dopo `strip`, `cronologia: list[Messaggio] = []`, `riassunto: str = ""`; validatore che chiama `controlla_cronologia`), `RichiestaPrompt` (`argomenti: dict[str, str] = {}`, `cronologia`, `riassunto`), `RispostaTurno`, `RispostaStato`, `ArgomentoPrompt`, `DescrizionePrompt`, `RispostaErrore` (`errore: str`)
  - `def crea_app(agente: Agente) -> FastAPI` — titolo `Agente del laboratorio`, descrizioni in italiano; ogni endpoint dichiara nei `responses` i codici di errore che può dare con il modello `RispostaErrore`
  - `CODICI: dict[str, int]` = `{"connessione": 503, "attesa": 504, "server": 502, "risposta_vuota": 502, "limite_passi": 500, "inatteso": 500}`
  - `def main() -> int` — §7.3: configurazione (2), `configura_log`, `costruisci_agente(config, Path.cwd())` (3), `uvicorn.run(crea_app(agente), host=..., port=...)`, poi 0
  - `assistente/servizio.py` eseguibile con `python -m assistente.servizio` (`if __name__ == "__main__": raise SystemExit(main())`)

- [ ] **Passo 1: test che falliscono** in `tests/test_servizio.py` (`TestClient(crea_app(Agente(grafo_finto, {}, config_di_prova)))`; per prompt e stato `monkeypatch` sui metodi dell'agente o sulle funzioni di `assistente.agente`):
  - `test_messaggio_con_uno_strumento`: modello `[richiesta(...calcola...)]`, strumento finto `calcola` → 200, `risposta`, `strumenti_usati[0] == {"nome": "calcola", "argomenti": {...}, "risultato": "5"}`, `cronologia` di 4 messaggi in JSON; in `caplog` le righe `richiesta endpoint=/messaggio messaggi_cronologia=0 riassunto=no` e `risposta endpoint=/messaggio strumenti=['calcola'] messaggi_cronologia=4`, più la riga `variant=mcp tool=calcola` del grafo.
  - `test_messaggio_con_cronologia_e_riassunto`: la cronologia JSON di un turno precedente e `riassunto="Luca"` arrivano al modello (controllare `ModelloFinto.chiamate[0]`: c'è la prima domanda e il messaggio di sistema contiene `Luca`).
  - `test_messaggio_con_accenti`: `«Perché»` torna identico nella cronologia; log senza eccezioni.
  - `test_codici_di_errore` (parametrizzato sulle 6 voci di `CODICI`): codice e `{"errore": <messaggio di oggi>}`; riga WARNING `errore endpoint=/messaggio codice=<n> ...`.
  - `test_corpo_non_valido`: `messaggio` vuoto o di soli spazi, `ruolo` sconosciuto, `strumento` senza richiesta → 422 e `ModelloFinto.chiamate == []`.
  - `test_prompts_elenco`: `GET /prompts` → nomi, descrizioni, argomenti con `obbligatorio`.
  - `test_prompt_valido`, `test_prompt_non_valido` (400 con il messaggio dello step 5, modello non chiamato), `test_prompt_server_giu` (503 `Server MCP non disponibile: prova`), `test_prompts_server_giu` (503).
  - `test_stato_tutto_ok` (200) e `test_stato_con_lm_studio_spento` (503, stesso corpo con la voce `modello` che spiega).
  - `test_openapi_consultabile`: `GET /openapi.json` contiene i 4 percorsi e lo schema `Messaggio` con il campo `richieste_strumenti`; `GET /docs` → 200.
  - `test_main_configurazione_non_valida` (2) e `test_main_server_mcp_non_disponibile` (3, `Server MCP non disponibile: prova` su stderr, `uvicorn.run` non chiamato); `test_main_avvia_uvicorn` con `uvicorn.run` finto: riceve `host="127.0.0.1"`, `port=8000`.
  - in `tests/test_configurazione.py`: predefiniti, valori letti, porta `abc` / `0` / `70000` rifiutate.
- [ ] **Passo 2: verificare che falliscano.**
- [ ] **Passo 3: implementare** `servizio.py` e `carica_indirizzo_servizio`.
- [ ] **Passo 4: verificare** — suite completa verde.
- [ ] **Passo 5: prova reale mirata** — in background: `python -m assistente.servizio` con output su file nello scratchpad; `Invoke-RestMethod -Method Post http://127.0.0.1:8000/messaggio -ContentType "application/json; charset=utf-8" -Body '{"messaggio":"Quanto fa 45 diviso 9?"}'`; `Invoke-RestMethod http://127.0.0.1:8000/stato`; `Invoke-WebRequest http://127.0.0.1:8000/docs`. Atteso: risposta con `calcola` in `strumenti_usati`, righe `richiesta`/`variant=mcp tool=calcola`/`risposta` nel log, stato tutto `ok`, `/docs` 200. Poi fermare il servizio.
- [ ] **Passo 6: commit** — `assistente/servizio.py`, `assistente/configurazione.py`, `tests/test_servizio.py`, `tests/test_configurazione.py`; `feat(servizio): API HTTP dell'agente con stato e OpenAPI`.

### Task 5: la CLI diventa client dell'API

**File:**
- Creare: `assistente/cliente.py`
- Modificare: `assistente/terminale.py` (`crea_smistamento(cliente)`, `main()` della sola CLI), `assistente/configurazione.py` (configurazione del client)
- Test: `tests/test_cliente.py`, `tests/test_terminale.py` (adattare smistamento e `main`; i test di `ciclo()` restano invariati; i test di `main` sul montaggio dell'agente sono già passati in `test_agente.py` al Task 3 e si tolgono da qui), `tests/test_configurazione.py`

**Interfacce:**
- Consuma: i percorsi e i formati JSON del Task 4; `leggi_comando_prompt`, `testo_elenco_prompt` di `prompt_mcp.py`; `mcp.types.Prompt`, `PromptArgument`.
- Produce:
  - in `configurazione.py`: `@dataclass(frozen=True) class ConfigurazioneCliente`: `agente_url: str`, `log_level: str`; `def carica_configurazione_cliente(ambiente: Mapping[str, str]) -> ConfigurazioneCliente` (predefinito `http://localhost:8000`; URL che non comincia con `http://` o `https://` → `ErroreConfigurazione("AGENTE_URL deve cominciare con http:// o https://, non '<valore>'")`; `LOG_LEVEL` come oggi)
  - `class ClienteAgente`: `__init__(self, url: str, client: httpx.Client | None = None)` (predefinito `httpx.Client(base_url=url, timeout=600)`); attributi `cronologia: list[dict]`, `riassunto: str`; metodi `chiedi(self, domanda: str) -> str`, `elenca_prompt(self) -> list[Prompt]`, `richiama_prompt(self, nome: str, argomenti: dict[str, str]) -> str`. Aggiorna `cronologia` e `riassunto` **solo** dopo un 200. Errori → `ErroreTurno`: corpo con `errore` → quel messaggio; 400 su un prompt → `ErroreComandoPrompt` con il messaggio; corpo non JSON o senza `errore` → `Errore dall'agente: <codice>`; `httpx.ConnectError` → `Agente non raggiungibile: controllare che il servizio sia avviato e AGENTE_URL.`; `httpx.TimeoutException` → `Attesa scaduta: l'agente non ha risposto entro 600 secondi.`
  - `def crea_smistamento(cliente: ClienteAgente) -> Callable[[str], str]` — stessi comandi di oggi; `/prompts` → `testo_elenco_prompt(cliente.elenca_prompt())`; `/prompt` → `leggi_comando_prompt` (WARNING `prompt rifiutato nome=- motivo=…` dal logger `assistente.terminale` per gli errori di sintassi, come oggi) poi `cliente.richiama_prompt`; il resto → `cliente.chiedi`
  - `main() -> int`: `carica_configurazione_cliente(leggi_ambiente(Path.cwd()))` (2 se non valida), `configura_log`, `ciclo(crea_smistamento(ClienteAgente(config.agente_url)))`, 0. Nessun import di grafo, modello o `collegamento_mcp`.

- [ ] **Passo 1: test che falliscono** in `tests/test_cliente.py` (`httpx.Client(transport=httpx.MockTransport(gestore), base_url="http://agente")`):
  - `test_chiedi_rimanda_cronologia_e_riassunto`: due domande; la seconda richiesta contiene in `cronologia` la cronologia restituita dalla prima e il `riassunto` restituito.
  - `test_errore_lascia_la_memoria_invariata`: 503 `{"errore": "Connessione fallita: …"}` → `ErroreTurno` con quel testo; `cronologia` e `riassunto` invariati.
  - `test_risposta_non_json`: 404 testo semplice → `ErroreTurno("Errore dall'agente: 404")`.
  - `test_agente_non_raggiungibile`: il gestore lancia `httpx.ConnectError` → il messaggio fissato.
  - `test_attesa_scaduta`: `httpx.ReadTimeout` → `Attesa scaduta: l'agente non ha risposto entro 600 secondi.`
  - `test_elenca_prompt_ricostruisce_gli_oggetti`: JSON di `GET /prompts` → `testo_elenco_prompt(cliente.elenca_prompt())` uguale a `testo_elenco_prompt(ELENCO)` con l'`ELENCO` di `test_terminale.py`.
  - `test_prompt_non_valido`: 400 → `ErroreComandoPrompt` con il messaggio, memoria invariata.
  - in `tests/test_terminale.py`: smistamento con un `ClienteAgente` finto (stessi casi di oggi: `/prompts`, `/prompts x`, `/prompt` valido, non valido, scritto male senza chiamata al cliente, `/Prompts` come domanda); `test_main_configurazione_non_valida` (`AGENTE_URL=localhost:8000` → 2); `test_main_passa_lo_smistamento` con `ciclo` finto e `AGENTE_URL` di prova (nessun server MCP avviato).
  - in `tests/test_configurazione.py`: predefinito, valore letto, URL senza schema rifiutato.
- [ ] **Passo 2: verificare che falliscano.**
- [ ] **Passo 3: implementare.**
- [ ] **Passo 4: verificare** — suite completa verde.
- [ ] **Passo 5: prova reale mirata** — servizio in background; CLI con input da pipe: `"Quanto fa 45 diviso 9?","/prompts","esci" | .\.venv\Scripts\python.exe -m assistente`. Atteso: risposta con 5, elenco dei prompt, `Arrivederci.`; nel log del servizio `richiesta endpoint=/messaggio` e `tool=calcola`. Poi CLI con il servizio fermo: `Agente non raggiungibile: …` e `Arrivederci.`
- [ ] **Passo 6: commit** — `assistente/cliente.py`, `assistente/terminale.py`, `assistente/configurazione.py`, `tests/test_cliente.py`, `tests/test_terminale.py`, `tests/test_configurazione.py`; `feat(terminale): la CLI diventa client dell'API dell'agente`.

### Task 6: prove reali dell'API, Docker e documentazione

**File:**
- Modificare: `tests/test_reale.py` (prove nuove), `compose.yaml`, `.env.example`, `README.md`, `CLAUDE.md`
- `Dockerfile`: invariato salvo i commenti (CMD resta la CLI; il servizio `agente` usa `command:`)

**Interfacce:**
- Consuma: `costruisci_agente`, `crea_app`, `ClienteAgente`.

- [ ] **Passo 1: prove reali nuove** in `tests/test_reale.py` (marcate come le altre):
  - `test_api_domanda_con_strumento`: `TestClient(crea_app(costruisci_agente(config, Path.cwd())))`, `POST /messaggio` «Quanto fa 45 diviso 9?» → 200, `calcola` in `strumenti_usati`, `"5"` nella risposta.
  - `test_stessa_risposta_da_cli_e_api`: con lo stesso `TestClient`, la domanda mandata con `ClienteAgente("http://testserver", client=<il TestClient>)` e con un `POST /messaggio` diretto → stesso strumento (`calcola`, stessi argomenti), stesso `risultato` (`5`), entrambe le risposte contengono `5`.
  - `test_api_stato_ok`: `GET /stato` → 200, tre voci `ok`.
- [ ] **Passo 2: eseguirle** (`-k "api or stessa_risposta"`, 1 ripetizione) e registrare l'esito nel registro.
- [ ] **Passo 3: `compose.yaml`** come §9: servizi `agente` (`command: ["python", "-m", "assistente.servizio"]`, `env_file: .env`, `LM_BASE_URL` verso `host.docker.internal`, `AGENTE_HOST: 0.0.0.0`, `ports: ["8000:8000"]`, `extra_hosts`, volume `./archivio:/app/archivio`) e `cli` (`build: .`, `stdin_open`, `tty`, `env_file: .env`, `AGENTE_URL: http://agente:8000`, `depends_on: [agente]`); commenti didattici aggiornati. `docker compose config` deve uscire senza errori (lettura, nessun avvio).
- [ ] **Passo 4: `.env.example`** — le tre variabili facoltative con commento; **README** — sezione «Agente come servizio HTTP» (§11), configurazione, avvio locale in due finestre, Docker (`docker compose up -d --build agente`, poi `docker compose run --rm cli`), «Diagnosi» (porta occupata, agente non raggiungibile), checklist voci 53 e seguenti; **CLAUDE.md** — obiettivo dello step 6 nell'elenco «Obiettivo», scelte tecniche (servizio FastAPI, CLI client) e comandi di avvio.
- [ ] **Passo 5: verificare** — suite completa verde; i comandi nuovi del README provati (quelli locali) o segnati come «da provare» (Docker).
- [ ] **Passo 6: commit** — `tests/test_reale.py`, `compose.yaml`, `Dockerfile` (se cambiato), `.env.example`, `README.md`, `CLAUDE.md`; `docs: agente come servizio HTTP, compose con due servizi (step 6)` (le prove in un commit `test(reale): …` a parte se comodo).

### Task 7: chiusura dello step

- [ ] **Passo 1: serie reale completa una volta** (`$env:PROVE_REALI="1"`, tutto `tests/test_reale.py`, in background con output su file); instabilità di gemma che non tocca un'evidenza dello step 6 → solo registro e README.
- [ ] **Passo 2: revisione indipendente** dell'intero branch (`dev..feat/servizio-agente`); Critical e Important corretti con TDD; Minor solo nel registro.
- [ ] **Passo 3: prove manuali e Docker** — un unico messaggio all'utente con istruzioni numerate (due finestre PowerShell; domanda con tool dalla CLI e con `Invoke-RestMethod`; `/docs` nel browser; `/stato` con LM Studio acceso e spento; domanda con LM Studio spento → 503; servizio con il server MCP rotto → codice 3; `/prompts` e `/prompt`; poi Docker con i due servizi fino a `Tu>`). **Fermarsi** e attendere l'output.
- [ ] **Passo 4: esiti nel README** («Esiti delle prove reali», sezione «Lezione 6 — step 6») e commit `docs: esiti delle prove dello step 6 (servizio)`.
- [ ] **Passo 5: aggiornare** registro (`..\.superpowers\sdd\2026-11-16-servizio-agente\progress.md`), `CLAUDE.local.md`, `HANDOFF.md`; **fermarsi** per la conferma del merge `--no-ff` in `dev`.
