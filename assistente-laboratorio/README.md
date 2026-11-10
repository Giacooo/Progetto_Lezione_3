# Assistente del laboratorio

Applicazione da terminale in Python il cui turno di conversazione è un grafo LangGraph
esplicito, collegato a un modello locale servito da LM Studio. Oltre all'orologio interno,
l'assistente usa gli strumenti pubblicati da un server MCP del progetto, che scopre all'avvio.

Tutti i comandi si eseguono da PowerShell nella cartella `assistente-laboratorio`.

## Preparazione

Serve Python 3.13.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

`requirements.txt` contiene le dipendenze dell'applicazione, con versioni fissate: LangGraph e
`langchain-openai` per il grafo e il collegamento a LM Studio, `python-dotenv` e `tzdata` per
configurazione e fusi orari, e per MCP `fastmcp` (il server), `mcp` (il protocollo) e
`langchain-mcp-adapters` (che trasforma gli strumenti scoperti in strumenti del grafo).
`requirements-dev.txt` aggiunge `pytest` per i test.

## Configurazione

Copiare l'esempio e completarlo (il file `.env` resta fuori da Git):

```powershell
Copy-Item .env.example .env
(Invoke-RestMethod "http://localhost:1234/v1/models").data | Select-Object id
```

| Variabile | Obbligatoria | Significato |
|---|---|---|
| `LM_BASE_URL` | sì | indirizzo dell'API di LM Studio, es. `http://localhost:1234/v1` |
| `LM_MODEL` | sì | id del modello come restituito da `/v1/models`, es. `google/gemma-4-e2b` |
| `FUSO_ORARIO` | sì | fuso IANA dell'orologio, es. `Europe/Rome` |
| `MAX_PASSI` | no | chiamate massime al modello per domanda (default `5`) |
| `LOG_LEVEL` | no | `DEBUG`, `INFO` (default), `WARNING`, `ERROR`, `CRITICAL` |

Si legge solo il `.env` della cartella da cui si avvia l'applicazione; le variabili già
impostate nell'ambiente hanno la precedenza. Se la configurazione manca o non è valida,
l'applicazione termina subito con `Configurazione non valida: ...`.

## Test automatici

Non richiedono LM Studio: usano un modello simulato con risposte predefinite e un orologio
con istante fisso. I test del server e del collegamento MCP avviano il server vero del
progetto come processo locale (nessuna rete).

```powershell
python -m pytest
```

Le tre prove reali di `tests/test_reale.py` risultano *skipped*.

`tests/test_calcolatrice.py` controlla risultati ed errori della calcolatrice;
`tests/test_server_mcp.py` controlla la discovery (nomi, descrizioni, schemi) e l'invocazione
diretta degli strumenti, compresi gli errori controllati; `tests/test_collegamento_mcp.py`
avvia il server vero via stdio e verifica discovery, chiamata sincrona, errore dello strumento,
server non avviabile e collegamento caduto durante la chiamata. Solo questi tre file:

```powershell
python -m pytest tests/test_calcolatrice.py tests/test_server_mcp.py tests/test_collegamento_mcp.py -q
```

## Prove reali con LM Studio

Con LM Studio attivo e il `.env` configurato, verificano che il modello vero chieda
`ora_corrente` a una domanda sull'ora, nessuno strumento a una domanda ordinaria e `calcola`
a «Quanto fa 1234 per 5678?» (con `7006652` nella risposta):

```powershell
$env:PROVE_REALI = "1"; python -m pytest -m reale -v; Remove-Item Env:PROVE_REALI
```

## Avvio locale

LM Studio deve essere avviato con il modello indicato in `LM_MODEL` caricato e il server attivo.

```powershell
python -m assistente
```

All'avvio l'applicazione lancia il server MCP e ne legge il catalogo (vedi «Strumenti MCP»).
Al prompt `Tu> ` si scrive la domanda. La sessione si chiude con `esci`, con Ctrl+C o con
la fine dell'input; le righe vuote sono ignorate. La conversazione resta in memoria per tutta
la sessione e si perde alla chiusura.

Le righe di log (su stderr, nello stesso terminale) iniziano con livello e componente, per
esempio `INFO assistente.grafo: Inizio chiamata al modello (passo 1/5)`; il resto è la risposta.
All'avvio compaiono anche alcune righe del server MCP (`Starting MCP server 'Strumenti del
laboratorio' with transport 'stdio'`, `Processing request of type ListToolsRequest`).

Se il modello non è raggiungibile l'applicazione non inventa risposte: mostra uno di questi
messaggi e la sessione continua, senza registrare il turno fallito nella cronologia.

- `Connessione fallita: controllare LM Studio, URL e porta.`
- `Attesa scaduta: controllare server, carico e tempi.`
- `Errore dal server: <codice> <testo>` (per esempio un id del modello sbagliato)
- `Il modello ha restituito una risposta vuota.`

Codici di uscita: `0` chiusura normale, `2` configurazione non valida, `3` server MCP non
disponibile.

### Formato dei log degli strumenti

Ogni richiesta di strumento produce tre righe con la stessa `call_id`: la richiesta del
modello, l'esito dell'esecuzione e il ritorno al modello. `variant=local` indica lo strumento
interno (`ora_corrente`), `variant=mcp` uno strumento del server MCP. `execution` vale `ok`,
`tool_error` (lo strumento ha rifiutato l'input), `connection_error` (il server MCP non ha
risposto) oppure `unknown_tool`. Il risultato nel log è troncato a 200 caratteri.

Esempio reale (2026-11-10, `google/gemma-4-e2b`, domanda «Quanto fa 1234 per 5678?»):

```
INFO assistente.grafo: Inizio chiamata al modello (passo 1/5)
INFO assistente.grafo: Fine chiamata al modello (passo 1/5): richieste di strumenti: 1
INFO assistente.grafo: variant=mcp tool=calcola call_id=OwHDidA104YXw3nMALZoiZONunUKJPiw arguments={"espressione": "1234 * 5678"}
INFO assistente.grafo: variant=mcp tool=calcola call_id=OwHDidA104YXw3nMALZoiZONunUKJPiw execution=ok result=7006652
INFO assistente.grafo: tool_message.call_id=OwHDidA104YXw3nMALZoiZONunUKJPiw next_node=llm
INFO assistente.grafo: Inizio chiamata al modello (passo 2/5)
INFO assistente.grafo: Fine chiamata al modello (passo 2/5): risposta finale
```

Una risposta senza queste righe non prova che lo strumento sia stato usato: il testo finale
può sembrare corretto anche se il modello ha risposto a memoria. Se il modello continua a
chiedere strumenti oltre `MAX_PASSI` chiamate, il turno si ferma con
`Limite di passaggi raggiunto: riprova con una domanda diversa.`

### Strumento orologio

Il modello può richiedere lo strumento `ora_corrente` (nessun parametro), che il programma
esegue davvero e che restituisce data e ora nel fuso `FUSO_ORARIO`, per esempio
`2026-11-10T09:31:54+01:00 (Europe/Rome)`. Il fuso non viene mai preso dal sistema.
Nei log compare con `variant=local tool=ora_corrente`.

Lo strumento si può provare da solo, senza modello:

```powershell
python -c "from zoneinfo import ZoneInfo; from assistente.strumenti import crea_strumenti; print(crea_strumenti(ZoneInfo('Europe/Rome'))[0].invoke({}))"
```

### Verifica manuale della cronologia

1. Scrivere `Mi chiamo Luca`, poi `Come mi chiamo?`: la seconda risposta contiene «Luca».
2. Fermare il server in LM Studio e scrivere una domanda: compare `Connessione fallita: ...`.
3. Riavviare il server e chiedere di nuovo `Come mi chiamo?`: il nome è ancora ricordato.
4. Chiudere con `esci` (oppure Ctrl+C).

## Strumenti MCP

Il server `assistente/server_mcp.py` (FastMCP, «Strumenti del laboratorio») pubblica gli
strumenti tramite il protocollo MCP. L'applicazione non ne riscrive l'elenco: all'avvio lancia
il server come sottoprocesso (trasporto stdio, con lo stesso interprete Python), ne chiede il
catalogo (discovery) e passa al modello nome, descrizione e schema di ogni strumento ricevuto.
La discovery produce una riga di log:

```
INFO assistente.collegamento_mcp: discovery server=assistente.server_mcp tools=['calcola']
```

Ogni chiamata del modello a uno strumento MCP apre una breve sessione con il server, esegue lo
strumento e chiude la sessione. Se il server non parte o la discovery fallisce, l'applicazione
non apre la chat: scrive su stderr `Server MCP non disponibile: <motivo>` ed esce con codice `3`.
Se il server cade durante una chiamata, il modello riceve un messaggio «Errore di collegamento
con il server MCP: ...» e nel log compare `execution=connection_error`.

Discovery senza modello (stampa i nomi degli strumenti):

```powershell
python -c "from pathlib import Path; from assistente.collegamento_mcp import carica_strumenti_mcp, connessione_stdio; print([s.name for s in carica_strumenti_mcp(connessione_stdio(Path.cwd()))])"
```

Atteso: `['calcola']`.

### `calcola` — calcolatrice sicura

`calcola(espressione)` valuta un'espressione aritmetica e restituisce il risultato. Sono
ammessi numeri interi e decimali (punto decimale), `+ - * /`, `//`, `%`, `**`, segno `+`/`-`
e parentesi. L'espressione viene analizzata come albero sintattico con un elenco chiuso di
costrutti: non si usa mai `eval`. Nomi, funzioni, attributi, stringhe e confronti sono
rifiutati con un messaggio che dice quale costrutto non è ammesso (per esempio
`costrutto non ammesso: Call` per `abs(3)`); anche espressioni vuote o troppo lunghe e
divisioni per zero producono un errore, mai un risultato inventato.

La descrizione dello strumento, letta dal modello, chiede di tradurre le parole italiane negli
operatori («per», «moltiplicato», «x» → `*`; «diviso» → `/`; «più» → `+`; «meno» → `-`).

Esempi di domande: «Quanto fa 1234 per 5678?» (`1234 * 5678` → `7006652`),
«Quanto fa 100 diviso 8?» (`100 / 8` → `12.5`), «Quanto fa (7+5)*3 meno 4?»
(`(7+5)*3-4` → `32`).

Invocazione diretta, senza modello (utile per provocare con certezza un errore: il modello
potrebbe correggere o evitare un input sbagliato prima di chiamare lo strumento):

```powershell
python -c "from pathlib import Path; from assistente.collegamento_mcp import carica_strumenti_mcp, connessione_stdio; c = carica_strumenti_mcp(connessione_stdio(Path.cwd()))[0]; print(c.invoke({'espressione': '2+3*4'}))"
python -c "from pathlib import Path; from assistente.collegamento_mcp import carica_strumenti_mcp, connessione_stdio; c = carica_strumenti_mcp(connessione_stdio(Path.cwd()))[0]; print(c.invoke({'espressione': 'abs(3)'}))"
```

Attesi: `14`, poi un errore che termina con
`assistente.errori.ErroreStrumento: costrutto non ammesso: Call`.

## Avvio con Docker Compose

L'applicazione e il server MCP girano nel container; LM Studio resta sull'host. Nel container
`localhost` è il container stesso, quindi `compose.yaml` sostituisce `LM_BASE_URL` con
`http://host.docker.internal:1234/v1`; le altre variabili arrivano dal `.env`, che non viene
copiato nell'immagine. Nessuna porta viene pubblicata.

Prerequisiti:
- Docker Desktop avviato;
- in LM Studio, nelle impostazioni del server, l'opzione **Serve on Local Network** attiva
  (altrimenti il server ascolta solo su `localhost` e il container non lo raggiunge);
- il firewall di Windows deve permettere le connessioni in ingresso a LM Studio.

```powershell
docker compose build
docker compose run --rm --name assistente-demo assistente
```

Dopo ogni modifica al codice (anche al server MCP) l'immagine va ricostruita con
`docker compose build`.

Da un secondo terminale:

```powershell
docker ps
docker logs -f assistente-demo
```

`--rm` elimina il container alla chiusura. Per analizzare un container che si ferma subito,
avviarlo senza `--rm` e leggere poi `docker logs assistente-demo`; quindi rimuoverlo con
`docker rm assistente-demo`.

Verifiche rapide senza modello:

```powershell
# Orologio nel container: il fuso viene da FUSO_ORARIO, non dall'host
docker compose run --rm -T assistente python -c "from zoneinfo import ZoneInfo; from assistente.strumenti import crea_strumenti; print(crea_strumenti(ZoneInfo('Europe/Rome'))[0].invoke({}))"
# Il container raggiunge LM Studio sull'host (atteso: 200)
docker compose run --rm -T assistente python -c "import urllib.request; print(urllib.request.urlopen('http://host.docker.internal:1234/v1/models', timeout=5).status)"
# Discovery MCP nel container (atteso: ['calcola'])
docker compose run --rm -T assistente python -c "from pathlib import Path; from assistente.collegamento_mcp import carica_strumenti_mcp, connessione_stdio; print([s.name for s in carica_strumenti_mcp(connessione_stdio(Path.cwd()))])"
```

## Checklist delle prove reali

Da eseguire in locale (`python -m assistente`) e con Docker Compose (secondo terminale con
`docker logs -f assistente-demo`):

1. Domanda ordinaria: risposta senza righe `variant=...` nei log.
2. `Che ore sono?`: nei log `variant=local tool=ora_corrente`, `execution=ok`,
   `tool_message.call_id=... next_node=llm` e una seconda chiamata al modello; la risposta
   riporta l'ora del risultato.
3. `Quanto fa 1234 per 5678?`: nei log `variant=mcp tool=calcola` con
   `arguments={"espressione": "1234 * 5678"}`, `execution=ok result=7006652`, la riga
   `tool_message.call_id=... next_node=llm` con la stessa `call_id` e una seconda chiamata al
   modello; la risposta contiene 7006652 (anche scritto 7.006.652).
4. `Quanto fa abs(3)?`: se il modello chiama `calcola`, nei log `execution=tool_error` e nessun
   risultato inventato; se non lo chiama, annotarlo (l'errore si verifica con l'invocazione
   diretta della sezione «Strumenti MCP»).
5. `Mi chiamo Luca`, poi `Come mi chiamo?`: la risposta contiene «Luca».
6. LM Studio fermo: `Connessione fallita: ...`; riacceso: la conversazione prosegue.
7. Le lettere accentate sono mostrate correttamente.
8. Chiusura con `esci` e con Ctrl+C, anche mentre si attende la risposta del modello.

## Diagnosi

Problemi dell'applicazione e del modello:

| Sintomo | Cosa controllare |
|---|---|
| `Configurazione non valida: ...` all'avvio | il `.env` nella cartella da cui si avvia e le variabili indicate |
| `Connessione fallita: ...` | server di LM Studio avviato, `LM_BASE_URL` e porta; in Docker anche "Serve on Local Network" e firewall |
| `Attesa scaduta: ...` | modello caricato, carico della macchina (il primo caricamento è lento) |
| `Errore dal server: 404 ...` o simili | `LM_MODEL` uguale a un id restituito da `/v1/models` |
| `Errore dal server: 400 ... jinja template ...` | il template del modello in LM Studio non supporta gli strumenti: aggiornare LM Studio e il runtime llama.cpp |
| risposta senza righe `variant=...` nei log | il modello non ha usato lo strumento: la risposta non è affidabile |
| il container termina subito | avviarlo senza `--rm` e leggere `docker logs assistente-demo`; con `docker compose run` serve un terminale interattivo |

Il collegamento MCP si diagnostica per livelli (tabella di p. 24 della lezione 5, adattata al
trasporto stdio del progetto): così non si cambia il prompt quando il problema è nell'avvio.
La riga del PDF «Server HTTP avviato, client senza risposta» non si applica: il server non usa
HTTP, ma comunica con l'applicazione attraverso stdin/stdout del sottoprocesso.

| Sintomo | Controllo prioritario |
|---|---|
| `Server MCP non disponibile: ...`, processo non avviato | interprete (`.venv` o immagine Docker), dipendenze installate, cartella di avvio; provare la discovery senza modello |
| processo attivo, catalogo assente o vuoto | trasporto stdio e stdout del server non contaminato (il server non deve usare `print`) |
| strumento nel catalogo (riga `discovery ... tools=[...]`), ma nessuna riga `variant=mcp` | descrizione dello strumento e supporto del modello al tool calling; prompt di sistema |
| `execution=connection_error` | il server è caduto durante la chiamata: rieseguire la discovery e l'invocazione diretta |
| `execution=tool_error` | input rifiutato dallo strumento: è il comportamento atteso per input non validi |
| `execution=ok` con risultato corretto, risposta errata | `ToolMessage`, cronologia e interpretazione del modello (confrontare `result=` con la risposta) |
| argomenti sbagliati (es. `1234 / 5678` per «1234 per 5678») | interpretazione della domanda da parte del modello: descrizione dello strumento |

## Esiti delle prove reali

### Lezione 5 — calcolatrice e base MCP (2026-11-10)

Eseguite il 2026-11-10 con `google/gemma-4-e2b` in LM Studio, in locale e con Docker Compose.

- Discovery: `['calcola']` in locale e nel container.
- Prima prova di «Quanto fa 1234 per 5678?»: gemma chiamava sempre `calcola` con
  `{"espressione": "1234 / 5678"}` (5 tentativi su 5: 4 con il test reale, 1 in Docker), cioè leggeva «per» come divisione, e
  rispondeva «circa 0.2173». Il collegamento era corretto (`execution=ok`, `next_node=llm`,
  seconda chiamata al modello): l'errore era nell'interpretazione del modello. Dopo l'aggiunta
  alla descrizione di `calcola` della traduzione delle parole italiane negli operatori, gemma
  chiama `1234 * 5678` e risponde 7.006.652 (3 tentativi su 3 nel test reale, più le sessioni
  in locale e in Docker).
- Prove reali automatiche (`PROVE_REALI=1`, in locale): 3 superate su 3.
- Checklist, con sessioni pilotate da input da script e log letti sull'output del comando
  (non con `docker logs -f assistente-demo`, non provato in questa lezione):
  - in locale: voci 1, 2 e 3 superate; inoltre «Quanto fa (7+5)*3 meno 4?» → `(7+5)*3-4` → 32;
  - in Docker: voci 2, 3 e 5 superate e chiusura con `esci`; inoltre
    «Quanto fa 100 diviso 8?» → `100 / 8` → 12.5.
- Voce 4 (`abs(3)`): gemma **non** chiama lo strumento. Prima della correzione rispondeva «3»
  da solo; dopo, risponde di non avere uno strumento per quella funzione. Nessun risultato
  inventato dallo strumento, ma `execution=tool_error` non è stato osservato nella chat.
  L'errore controllato è stato verificato con l'invocazione diretta
  (`costrutto non ammesso: Call`).
- `Server MCP non disponibile` con codice 3 è verificato solo dal test automatico
  `test_main_server_mcp_non_disponibile`, non con un server realmente guasto.
- Voci 6 e 7 e il Ctrl+C della voce 8 non ripetuti in questa lezione (superati il 2026-10-28,
  vedi sotto).

### Lezione 4 — orologio (2026-10-28)

Eseguite il 2026-10-28 con `google/gemma-4-e2b` in LM Studio.

- Il 2026-10-27 ogni richiesta con strumenti falliva con
  `Errore dal server: 400 ... Error rendering prompt with jinja template ...`, anche con una
  richiesta HTTP diretta: dopo l'aggiornamento di LM Studio e del runtime l'errore non compare più.
- Con il prompt di sistema precedente gemma invitava l'utente a usare lo strumento invece di
  chiamarlo; con la formulazione attuale lo chiama.
- Prove reali automatiche (`PROVE_REALI=1`): 2 superate su 2, in tre esecuzioni.
- Checklist di allora: voci su domanda ordinaria, ora, cronologia, LM Studio fermo, accenti e
  chiusura superate in locale e con Docker Compose. In Docker la sessione è stata pilotata con
  input da script (`docker compose run -T`) e i log letti in parallelo con
  `docker logs -f assistente-demo`; LM Studio è stato fermato e riavviato con
  `lms server stop` / `lms server start`; il Ctrl+C nel container è stato inviato come SIGINT
  (`docker kill --signal=SIGINT assistente-demo`). Il Ctrl+C in locale durante l'attesa del
  modello è stato provato a mano: compare «Arrivederci.».

## Problemi aperti

- Con `abs(3)` gemma non chiama `calcola` (vedi esiti): il rifiuto dello strumento è provato
  solo con l'invocazione diretta.
