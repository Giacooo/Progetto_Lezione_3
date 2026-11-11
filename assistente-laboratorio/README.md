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
`langchain-mcp-adapters` (che trasforma gli strumenti scoperti in strumenti del grafo), e
`httpx` per le richieste al servizio meteo Open-Meteo.
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

Non richiedono LM Studio né la rete: usano un modello simulato con risposte predefinite, un
orologio con istante fisso e risposte HTTP simulate per il meteo. I test del server e del
collegamento MCP avviano il server vero del progetto come processo locale.

```powershell
python -m pytest
```

Le otto prove reali di `tests/test_reale.py` risultano *skipped*.

`tests/test_calcolatrice.py`, `tests/test_convertitore.py`, `tests/test_giorni.py`,
`tests/test_catalogo.py`, `tests/test_note.py` e `tests/test_meteo.py` controllano risultati
ed errori della calcolatrice, del convertitore, di giorni e scadenze (con le festività del file
locale), del catalogo dei corsi, delle note (su un archivio SQLite temporaneo, mai quello del
progetto) e del meteo (con `httpx.MockTransport`, senza rete);
`tests/test_server_mcp.py` controlla il catalogo
completo, la discovery (nomi, descrizioni, schemi) e l'invocazione diretta degli strumenti,
compresi gli errori controllati; `tests/test_collegamento_mcp.py` avvia il server vero via
stdio e verifica discovery, chiamata sincrona, errore dello strumento, server non avviabile e
collegamento caduto durante la chiamata. Solo questi file:

```powershell
python -m pytest tests/test_calcolatrice.py tests/test_convertitore.py tests/test_giorni.py tests/test_catalogo.py tests/test_note.py tests/test_meteo.py tests/test_server_mcp.py tests/test_collegamento_mcp.py -q
```

## Prove reali con LM Studio

Con LM Studio attivo e il `.env` configurato, verificano che il modello vero chieda
`ora_corrente` a una domanda sull'ora, nessuno strumento a una domanda ordinaria, `calcola`
a «Quanto fa 1234 per 5678?» (con `7006652` nella risposta), `converti_unita` a «Quanti
miglia sono 10 km?», `conta_giorni` a «Quanti giorni lavorativi ci sono tra il 23 e il 28
dicembre 2026?», nello stesso turno `cerca_corsi` poi `dettaglio_corso` a «Quanto dura il
corso di Python a Udine?», una sola `aggiungi_nota` a «Ricordami di consegnare il report
venerdì» e `meteo_citta` a «Che tempo fa a Pordenone?» (questa prova usa anche la rete):

```powershell
$env:PROVE_REALI = "1"; python -m pytest -m reale -v; Remove-Item Env:PROVE_REALI
```

La prova delle note scrive nell'archivio vero del progetto (`archivio\note.sqlite`): dopo la
prova eliminare la nota creata oppure il file (vedi «Note persistenti»).

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
INFO assistente.collegamento_mcp: discovery server=assistente.server_mcp tools=['calcola', 'converti_unita', 'conta_giorni', 'aggiungi_giorni_lavorativi', 'cerca_corsi', 'dettaglio_corso', 'aggiungi_nota', 'elenca_note', 'elimina_nota', 'meteo_citta']
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

Atteso: `['calcola', 'converti_unita', 'conta_giorni', 'aggiungi_giorni_lavorativi',
'cerca_corsi', 'dettaglio_corso', 'aggiungi_nota', 'elenca_note', 'elimina_nota',
'meteo_citta']`.

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

### `converti_unita` — convertitore di unità

`converti_unita(valore, da_unita, a_unita)` converte un valore fra unità di un elenco chiuso e
restituisce il risultato con le due unità esplicite, con al massimo 4 decimali, per esempio
`10 km = 6.2137 mi`. Unità ammesse (simboli esatti, maiuscole comprese):

| Categoria | Simboli |
|---|---|
| lunghezza | `mm` millimetri, `cm` centimetri, `m` metri, `km` chilometri, `in` pollici, `ft` piedi, `mi` miglia |
| massa | `g` grammi, `kg` chilogrammi, `lb` libbre, `oz` once |
| temperatura | `C` gradi Celsius, `F` gradi Fahrenheit, `K` kelvin |

Errori, sempre senza un risultato inventato: unità non ammessa (il messaggio elenca quelle
ammesse), unità di categorie diverse (per esempio metri in chilogrammi), temperatura sotto lo
zero assoluto. La descrizione dello strumento elenca i simboli tra virgolette con il nome
italiano e chiede al modello di passare i simboli, non i nomi.

Esempi di domande: «Quanti miglia sono 10 km?» (`km` → `mi`, `10 km = 6.2137 mi`),
«Quanti pollici sono 30 centimetri?» (`cm` → `in`, `30 cm = 11.811 in`),
«Quanti gradi Fahrenheit sono 100 gradi Celsius?» (`C` → `F`, 212).

Invocazione diretta, senza modello:

```powershell
python -c "from pathlib import Path; from assistente.collegamento_mcp import carica_strumenti_mcp, connessione_stdio; c = {s.name: s for s in carica_strumenti_mcp(connessione_stdio(Path.cwd()))}['converti_unita']; print(c.invoke({'valore': 10, 'da_unita': 'km', 'a_unita': 'mi'}))"
python -c "from pathlib import Path; from assistente.collegamento_mcp import carica_strumenti_mcp, connessione_stdio; c = {s.name: s for s in carica_strumenti_mcp(connessione_stdio(Path.cwd()))}['converti_unita']; print(c.invoke({'valore': 5, 'da_unita': 'm', 'a_unita': 'kg'}))"
```

Attesi: `10 km = 6.2137 mi`, poi un errore che termina con
`assistente.errori.ErroreStrumento: unità incompatibili: m è lunghezza, kg è massa`.
Con `parsec` l'errore è `unità non ammessa: 'parsec'. Unità ammesse (maiuscole comprese): ...`;
con `-300` `C` è `temperatura sotto lo zero assoluto`.

### `conta_giorni` e `aggiungi_giorni_lavorativi` — giorni e scadenze

- `conta_giorni(data_inizio, data_fine)` restituisce i giorni di calendario
  (`data_fine − data_inizio`, stessa data → 0) e i giorni lavorativi dell'intervallo, con la
  data iniziale esclusa e quella finale inclusa, più l'elenco delle festività che vi cadono.
- `aggiungi_giorni_lavorativi(data_inizio, giorni)` restituisce la scadenza dopo `giorni`
  giorni lavorativi (da 1 a 365). La data di partenza non conta mai, anche se è lavorativa.

Un giorno è lavorativo se è dal lunedì al venerdì e non è festivo. Le festività nazionali
italiane del 2026 e del 2027 (13 per anno, compreso San Francesco il 4 ottobre, senza patroni
locali) sono nel file locale `assistente/dati/festivita.json`, letto una volta all'avvio del
server. Le date di Pasqua (2026-04-05, 2027-03-28) sono state verificate il 2026-11-10 con
l'algoritmo gregoriano e con fonti pubbliche.
Le date si scrivono solo nel formato `AAAA-MM-GG`. Ogni risultato termina con
`(calcolo indicativo, non normativo)`.

Errori, sempre senza un risultato inventato:
- data non in formato `AAAA-MM-GG` o inesistente (per esempio `23/12/2026` o `2026-02-30`);
- data finale prima di quella iniziale;
- `giorni` minore di 1 o maggiore di 365;
- intervallo o scadenza fuori dagli anni presenti nel file. In questo caso lo strumento dà un
  errore esplicito invece di calcolare senza festività.

La descrizione degli strumenti chiede al modello di passare le date in formato `AAAA-MM-GG`,
con un esempio di traduzione («23 dicembre 2026» → `2026-12-23`).

Esempi di domande:
- «Quanti giorni lavorativi ci sono tra il 23 e il 28 dicembre 2026?»: 5 giorni di calendario,
  2 lavorativi; Natale e Santo Stefano nell'intervallo.
- «Che data è 10 giorni lavorativi dopo il 2026-12-20?»: `2027-01-05`.
- «Che data è 15 giorni lavorativi dopo il 3 aprile 2026?»: `2026-04-27`.

Invocazione diretta, senza modello:

```powershell
python -c "from pathlib import Path; from assistente.collegamento_mcp import carica_strumenti_mcp, connessione_stdio; c = {s.name: s for s in carica_strumenti_mcp(connessione_stdio(Path.cwd()))}['conta_giorni']; print(c.invoke({'data_inizio': '2026-12-23', 'data_fine': '2026-12-28'}))"
python -c "from pathlib import Path; from assistente.collegamento_mcp import carica_strumenti_mcp, connessione_stdio; c = {s.name: s for s in carica_strumenti_mcp(connessione_stdio(Path.cwd()))}['conta_giorni']; print(c.invoke({'data_inizio': '23/12/2026', 'data_fine': '2026-12-28'}))"
python -c "from pathlib import Path; from assistente.collegamento_mcp import carica_strumenti_mcp, connessione_stdio; c = {s.name: s for s in carica_strumenti_mcp(connessione_stdio(Path.cwd()))}['aggiungi_giorni_lavorativi']; print(c.invoke({'data_inizio': '2027-12-20', 'giorni': 10}))"
```

Attesi:
1. `Da 2026-12-23 (escluso) a 2026-12-28 (incluso): 5 giorni di calendario, 2 giorni
   lavorativi. Festività nell'intervallo: 2026-12-25 Natale; 2026-12-26 Santo Stefano.
   (calcolo indicativo, non normativo)`.
2. Un errore che termina con `assistente.errori.ErroreStrumento: data non valida:
   '23/12/2026'. Usa solo il formato AAAA-MM-GG (esempio: 2026-12-23) e una data che esista`.
3. Un errore `anno 2028 non disponibile: le festività sono presenti solo per 2026, 2027`.

### `cerca_corsi` e `dettaglio_corso` — catalogo locale dei corsi

Il catalogo è il file locale `assistente/dati/catalogo.json`, letto una volta all'avvio del
server. Contiene 10 corsi **inventati**, ciascuno con codice (`ITS-<AREA>-<NN>`), titolo,
sede (Pordenone, Udine o Trieste) e durata in ore.

- `cerca_corsi(testo, max_risultati=5)` restituisce un elenco breve con codice, titolo e sede
  dei corsi il cui titolo, codice o sede contiene `testo`. La ricerca non distingue le
  maiuscole e segue l'ordine del file. `max_risultati` va da 1 a 20. Se non trova nulla
  risponde `Nessun corso trovato per "<testo>".`, che non è un errore.
- `dettaglio_corso(codice)` restituisce tutti i campi di un corso dato il suo codice; il
  codice è accettato anche in minuscolo.

Errori, sempre senza un corso inventato: `testo` vuoto; `max_risultati` fuori intervallo;
codice inesistente (il messaggio suggerisce di usare `cerca_corsi`).

`testo` viene cercato per intero in un campo alla volta, quindi «Python Udine» non trova
nulla. Per questo la descrizione del parametro `testo` chiede al modello **una sola parola**,
la materia oppure la sede. La descrizione dello strumento dice anche di cercare prima e poi
chiedere il dettaglio con il codice trovato.

Esempi di domande:
- «Quanto dura il corso di Python a Udine?»: `cerca_corsi` con `Python`, poi
  `dettaglio_corso` con `ITS-DAT-01`; risposta 90 ore.
- «Ci sono corsi di astronautica?»: `Nessun corso trovato per "astronautica".`

Invocazione diretta, senza modello:

```powershell
python -c "from pathlib import Path; from assistente.collegamento_mcp import carica_strumenti_mcp, connessione_stdio; c = {s.name: s for s in carica_strumenti_mcp(connessione_stdio(Path.cwd()))}['cerca_corsi']; print(c.invoke({'testo': 'Python'}))"
python -c "from pathlib import Path; from assistente.collegamento_mcp import carica_strumenti_mcp, connessione_stdio; c = {s.name: s for s in carica_strumenti_mcp(connessione_stdio(Path.cwd()))}['dettaglio_corso']; print(c.invoke({'codice': 'ITS-DAT-01'}))"
python -c "from pathlib import Path; from assistente.collegamento_mcp import carica_strumenti_mcp, connessione_stdio; c = {s.name: s for s in carica_strumenti_mcp(connessione_stdio(Path.cwd()))}['dettaglio_corso']; print(c.invoke({'codice': 'ITS-XYZ-99'}))"
```

Attesi:
1. Le righe `- ITS-DAT-01: Programmazione Python per l'analisi dei dati (Udine)` e
   `- ITS-AUT-01: Python per l'automazione industriale (Pordenone)`.
2. `Codice: ITS-DAT-01`, `Titolo: Programmazione Python per l'analisi dei dati`,
   `Sede: Udine`, `Durata: 90 ore`.
3. Un errore che termina con `assistente.errori.ErroreStrumento: codice corso 'ITS-XYZ-99'
   inesistente: usa cerca_corsi per trovare i codici validi`.

### `aggiungi_nota`, `elenca_note` e `elimina_nota` — note persistenti

Le note sono l'unico dato che l'applicazione conserva fra una sessione e l'altra. Stanno nel
file SQLite `archivio\note.sqlite`, relativo alla cartella da cui si avvia l'applicazione (la
cartella del progetto). Il file e la cartella `archivio` vengono creati al primo uso e sono
esclusi da Git (`.gitignore`) e dall'immagine Docker (`.dockerignore`).

- `aggiungi_nota(testo)` salva in modo permanente il testo (spazi iniziali e finali tolti) e
  restituisce ID e data/ora di creazione, per esempio
  `Nota 1 creata il 2026-11-10T12:55:18+01:00: consegnare il report venerdì`.
- `elenca_note(limite=10)` restituisce le note in ordine di ID crescente, una per riga
  (`Nota <id> del <data>: <testo>`), al massimo `limite` (da 1 a 50); senza note risponde
  `Nessuna nota salvata.`.
- `elimina_nota(id_nota)` elimina definitivamente la sola nota con quell'ID e la riporta,
  per esempio `Nota 1 eliminata: consegnare il report venerdì`.

Errori, senza alcuna modifica all'archivio: testo vuoto o di soli spazi; testo oltre 500
caratteri; `limite` fuori intervallo; ID inesistente (`Nota 99 inesistente: usa elenca_note per
vedere gli ID.`); archivio non accessibile (`Archivio delle note non accessibile: ...`).

Ogni modifica produce una riga di log del server: `nota creata id=<id>`,
`nota eliminata id=<id>` oppure `eliminazione rifiutata id=<id> inesistente`.

Le descrizioni degli strumenti contengono esempi di traduzione per il modello: «Ricordami di
consegnare il report venerdì» → `testo="consegnare il report venerdì"`; «Elimina la nota 99» →
`id_nota=99`; «Quali note ho?» → `elenca_note()` senza argomenti (il limite è facoltativo e il
modello non deve chiederlo).

Invocazione diretta, senza modello (scrive nell'archivio vero):

```powershell
python -c "from pathlib import Path; from assistente.collegamento_mcp import carica_strumenti_mcp, connessione_stdio; c = {s.name: s for s in carica_strumenti_mcp(connessione_stdio(Path.cwd()))}['aggiungi_nota']; print(c.invoke({'testo': 'consegnare il report venerdì'}))"
python -c "from pathlib import Path; from assistente.collegamento_mcp import carica_strumenti_mcp, connessione_stdio; c = {s.name: s for s in carica_strumenti_mcp(connessione_stdio(Path.cwd()))}['elenca_note']; print(c.invoke({}))"
python -c "from pathlib import Path; from assistente.collegamento_mcp import carica_strumenti_mcp, connessione_stdio; c = {s.name: s for s in carica_strumenti_mcp(connessione_stdio(Path.cwd()))}['elimina_nota']; print(c.invoke({'id_nota': 99}))"
python -c "from pathlib import Path; from assistente.collegamento_mcp import carica_strumenti_mcp, connessione_stdio; c = {s.name: s for s in carica_strumenti_mcp(connessione_stdio(Path.cwd()))}['elimina_nota']; print(c.invoke({'id_nota': 1}))"
```

Attesi, con l'archivio inizialmente vuoto:
1. `Nota 1 creata il <data e ora>: consegnare il report venerdì`.
2. `Nota 1 del <data e ora>: consegnare il report venerdì`.
3. Un errore che termina con `assistente.errori.ErroreStrumento: Nota 99 inesistente: usa
   elenca_note per vedere gli ID.`
4. `Nota 1 eliminata: consegnare il report venerdì`.

Per cancellare tutte le note, con l'applicazione chiusa:

```powershell
Remove-Item archivio\note.sqlite
```

### `meteo_citta` — meteo attuale da Open-Meteo

`meteo_citta(citta)` restituisce temperatura e condizione attuali di una città. È l'unico
strumento che usa la rete, e l'unico servizio esterno è l'API pubblica Open-Meteo (senza
chiave). Lo strumento fa due richieste HTTP, ciascuna con un timeout di 10 secondi:
1. geocoding (`geocoding-api.open-meteo.com`): dal nome della città alle coordinate;
2. previsioni (`api.open-meteo.com`): temperatura e codice meteo WMO attuali, nel fuso orario
   del luogo.

Il risultato riporta nome, regione e paese della località scelta, coordinate, ora della
misura con il fuso, temperatura e condizione in italiano, per esempio
`Meteo a Pordenone, Friuli Venezia Giulia, Italia (45.95689, 12.66051) alle 2026-11-11T09:45
(Europe/Rome): 11.1 °C, pioggia.` Se il nome corrisponde a più località (città ambigua),
lo strumento sceglie la prima e le altre vengono elencate in coda
(`Scelta la prima corrispondenza; altre: Pordenone, Veneto, Italia.`). Un codice WMO sconosciuto
diventa `condizione non riconosciuta (codice <n>)`.

Errori, distinti fra loro e sempre senza un dato meteo inventato:
- città vuota: `città non indicata: scrivi il nome di una città.`;
- città non trovata: `Città non trovata: <città>`;
- rete assente: `Servizio meteo non raggiungibile: controlla la connessione.`;
- attesa oltre 10 secondi: `Servizio meteo: attesa scaduta.`;
- risposta HTTP di errore: `Servizio meteo: errore HTTP <codice>.`;
- risposta non interpretabile (JSON non valido o campi mancanti):
  `Servizio meteo: risposta non valida.`.

La descrizione dello strumento chiede al modello il solo nome della città, con un esempio di
traduzione («Che tempo fa a Pordenone?» → `citta="Pordenone"`).

Invocazione diretta, senza modello (richiede la rete):

```powershell
python -c "from pathlib import Path; from assistente.collegamento_mcp import carica_strumenti_mcp, connessione_stdio; c = {s.name: s for s in carica_strumenti_mcp(connessione_stdio(Path.cwd()))}['meteo_citta']; print(c.invoke({'citta': 'Pordenone'}))"
python -c "from pathlib import Path; from assistente.collegamento_mcp import carica_strumenti_mcp, connessione_stdio; c = {s.name: s for s in carica_strumenti_mcp(connessione_stdio(Path.cwd()))}['meteo_citta']; print(c.invoke({'citta': 'Valbruniforte'}))"
python -c "from pathlib import Path; from assistente.collegamento_mcp import carica_strumenti_mcp, connessione_stdio; c = {s.name: s for s in carica_strumenti_mcp(connessione_stdio(Path.cwd()))}['meteo_citta']; print(c.invoke({'citta': ''}))"
```

Attesi:
1. `Meteo a Pordenone, Friuli Venezia Giulia, Italia (...) alle <ora> (Europe/Rome): <t> °C,
   <condizione>. Scelta la prima corrispondenza; altre: Pordenone, Veneto, Italia.`
2. Un errore che termina con `assistente.errori.ErroreStrumento: Città non trovata: Valbruniforte`.
3. Un errore che termina con `assistente.errori.ErroreStrumento: città non indicata: scrivi il
   nome di una città.`

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

`--rm` elimina il container alla chiusura, ma non le note: `compose.yaml` monta la cartella
`archivio` del progetto sull'host in `/app/archivio` del container (volume
`./archivio:/app/archivio`), quindi locale e Docker usano lo stesso `archivio\note.sqlite`.
Nel container la data delle note è in UTC (`+00:00`), in locale nel fuso del computer.

Per analizzare un container che si ferma subito,
avviarlo senza `--rm` e leggere poi `docker logs assistente-demo`; quindi rimuoverlo con
`docker rm assistente-demo`.

Verifiche rapide senza modello:

```powershell
# Orologio nel container: il fuso viene da FUSO_ORARIO, non dall'host
docker compose run --rm -T assistente python -c "from zoneinfo import ZoneInfo; from assistente.strumenti import crea_strumenti; print(crea_strumenti(ZoneInfo('Europe/Rome'))[0].invoke({}))"
# Il container raggiunge LM Studio sull'host (atteso: 200)
docker compose run --rm -T assistente python -c "import urllib.request; print(urllib.request.urlopen('http://host.docker.internal:1234/v1/models', timeout=5).status)"
# Discovery MCP nel container (atteso: ['calcola', 'converti_unita', 'conta_giorni', 'aggiungi_giorni_lavorativi', 'cerca_corsi', 'dettaglio_corso', 'aggiungi_nota', 'elenca_note', 'elimina_nota', 'meteo_citta'])
docker compose run --rm -T assistente python -c "from pathlib import Path; from assistente.collegamento_mcp import carica_strumenti_mcp, connessione_stdio; print([s.name for s in carica_strumenti_mcp(connessione_stdio(Path.cwd()))])"
# Il container raggiunge Open-Meteo (atteso: 200)
docker compose run --rm -T assistente python -c "import httpx; print(httpx.get('https://api.open-meteo.com/v1/forecast?latitude=46&longitude=12.6&current=temperature_2m', timeout=10).status_code)"
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
9. `Quanti miglia sono 10 km?`: nei log `variant=mcp tool=converti_unita` con
   `arguments={"a_unita": "mi", "da_unita": "km", "valore": 10}`, `execution=ok
   result=10 km = 6.2137 mi` e il ritorno al modello; la risposta riporta 6.2137 miglia.
10. `Converti 5 metri in chilogrammi`: nessun numero inventato. Se il modello chiama
    `converti_unita`, nei log `execution=tool_error`; se non lo chiama, annotarlo (l'errore si
    verifica con l'invocazione diretta).
11. `Quanti giorni lavorativi ci sono tra il 23 e il 28 dicembre 2026?`: nei log
    `variant=mcp tool=conta_giorni` con `arguments={"data_fine": "2026-12-28", "data_inizio":
    "2026-12-23"}`, `execution=ok` con 2 giorni lavorativi e il ritorno al modello; la risposta
    riporta 2 giorni lavorativi.
12. `Che data è 10 giorni lavorativi dopo il 2026-12-20?`: nei log
    `variant=mcp tool=aggiungi_giorni_lavorativi` con `arguments={"data_inizio": "2026-12-20",
    "giorni": 10}`, `execution=ok result=Scadenza: 2027-01-05 ...`; la risposta riporta il
    2027-01-05.
13. `Quanto dura il corso di Python a Udine?`: nei log, nello stesso turno, `variant=mcp
    tool=cerca_corsi` con `arguments={"testo": "Python"}`, poi `variant=mcp
    tool=dettaglio_corso` con `arguments={"codice": "ITS-DAT-01"}`, entrambi `execution=ok`;
    la risposta riporta 90 ore. Nel log `result=` mostra solo la prima riga del risultato.
14. `Ci sono corsi di astronautica?`: nei log `tool=cerca_corsi` con
    `result=Nessun corso trovato per "astronautica".`; la risposta non inventa corsi.
15. `Ricordami di consegnare il report venerdì`: nei log una sola `variant=mcp
    tool=aggiungi_nota` con `arguments={"testo": "consegnare il report venerdì"}`, la riga
    `nota creata id=<id>` e `execution=ok`; la risposta riporta l'ID.
16. `Elimina la nota 99` (nota inesistente): nei log `tool=elimina_nota` con
    `arguments={"id_nota": 99}`, `eliminazione rifiutata id=99 inesistente` e
    `execution=tool_error`; nessuna nota eliminata.
17. Chiudere con `esci`, riavviare l'applicazione (in Docker con un nuovo `docker compose run
    --rm`) e chiedere `Quali note ho?`: nei log `tool=elenca_note` con `arguments={}`; la
    risposta mostra le note salvate prima. Alla fine eliminare `archivio\note.sqlite`.
18. `Che tempo fa a Pordenone?`: nei log una sola `variant=mcp tool=meteo_citta` con
    `arguments={"citta": "Pordenone"}`, le due richieste HTTP a Open-Meteo con esito `200 OK` e
    `execution=ok result=Meteo a Pordenone, ...`; la risposta riporta temperatura e condizione
    del risultato.
19. Città inesistente (per esempio `Che tempo fa a Valbruniforte?`): nei log `tool=meteo_citta`
    e `execution=tool_error result=Errore dello strumento: Città non trovata: ...`; nessun dato
    meteo inventato. Se il modello non chiama lo strumento, annotarlo (l'errore si verifica
    con l'invocazione diretta).
20. Rete scollegata (Wi-Fi e cavo spenti, LM Studio acceso), `Che tempo fa a Pordenone?`: nei
    log `execution=tool_error` con `Servizio meteo non raggiungibile: controlla la
    connessione.`, distinto da «Città non trovata»; nessun dato meteo inventato.

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

### Lezione 5 — meteo (2026-11-11)

Eseguite il 2026-11-11 con `google/gemma-4-e2b` in LM Studio, in locale e con Docker Compose.

- Discovery: i 10 strumenti, da `calcola` a `meteo_citta`, nel container e nelle sessioni in
  locale. Dal container Open-Meteo risponde `200`.
- Prove reali automatiche (`PROVE_REALI=1`, in locale): 8 superate su 8. Dopo la prova è stato
  eliminato `archivio\note.sqlite`, che conteneva solo la nota creata dal test.
- Voce 18, con input da script e log letti sull'output del comando, in locale (1 sessione) e
  in Docker (1 sessione): gemma chiama una sola volta `meteo_citta` con
  `{"citta": "Pordenone"}`. Le due richieste a Open-Meteo rispondono `200 OK` e il risultato è
  `Meteo a Pordenone, Friuli Venezia Giulia, Italia (45.95689, 12.66051) alle 2026-11-11T09:45
  (Europe/Rome): 11.1 °C, pioggia.`, con l'omonima località del Veneto fra le alternative.
  Gemma risponde «Il tempo a Pordenone è di 11.1 °C con pioggia.».
- Voce 19:
  - con un nome chiaramente impossibile («Zzyxqwopolis», 1 tentativo in locale) gemma **non**
    chiama lo strumento e chiede di verificare l'ortografia;
  - con nomi plausibili ma inesistenti («Valbruniforte» e «Castelmorvano» in locale,
    «Valbruniforte» in Docker) gemma chiama `meteo_citta` con la città esatta. Nei log compare
    `execution=tool_error` con `Città non trovata: <città>` e gemma risponde di non aver
    trovato informazioni, senza dati inventati.
- Invocazione diretta, in locale: Pordenone, `Valbruniforte` e città vuota con i risultati
  attesi della sezione «Meteo».
- Non provati in questo task:
  - **voce 20, rete scollegata** (rinviata): l'errore `Servizio meteo non raggiungibile` è
    coperto finora solo dai test automatici con HTTP simulato;
  - attesa scaduta, errore HTTP e risposta non valida in reale (coperti dai test automatici);
  - le voci 1–17 della checklist in sessioni dell'app (le prove reali automatiche hanno
    ricontrollato orologio, `calcola`, `converti_unita`, `conta_giorni`, il catalogo e
    `aggiungi_nota`).

### Lezione 5 — note persistenti (2026-11-10)

Eseguite il 2026-11-10 con `google/gemma-4-e2b` in LM Studio, in locale e con Docker Compose.

- Discovery: i 9 strumenti, da `calcola` a `elimina_nota`, nel container e nelle sessioni in
  locale.
- Prove reali automatiche (`PROVE_REALI=1`, in locale): 7 superate su 7, prima e dopo la
  correzione descritta sotto. Per «Ricordami di consegnare il report venerdì» gemma chiama una
  sola volta `aggiungi_nota` con `{"testo": "consegnare il report venerdì"}`.
- Voci 15 e 16, in locale (1 sessione) e in Docker (1 sessione): una sola `aggiungi_nota`,
  risposta «La nota è stata salvata con l'ID ...». Per «Elimina la nota 99» gemma chiama
  `elimina_nota` con `{"id_nota": 99}`. Lo strumento rifiuta (`eliminazione rifiutata id=99
  inesistente`, `execution=tool_error`) e gemma risponde «Non è stata trovata la nota con l'ID
  99.»; le note salvate restano tutte.
- Voce 17, prima prova: dopo il riavvio, a «Quali note ho?» gemma **non chiamava**
  `elenca_note` e chiedeva all'utente quante note mostrare: nella prima sessione e in 2 delle 3
  ripetizioni successive. Nella terza ripetizione la chiamava e mostrava le note delle sessioni precedenti, quindi la persistenza funzionava. La
  descrizione di `elenca_note` non aveva un esempio di domanda e non diceva che `limite` è
  facoltativo.
  - Dopo l'aggiunta di due righe alla descrizione («Il limite è facoltativo: non chiederlo
    all'utente se non lo indica.» ed `Esempio: "Quali note ho?" -> elenca_note() senza
    argomenti.`): 3 sessioni su 3 in locale con `elenca_note` e `arguments={}`, con le note
    salvate prima.
  - In Docker, con l'immagine ricostruita: la nota creata in un container con `--rm` compare
    in un nuovo container (volume `./archivio`).
- Invocazione diretta, in locale: creazione, elenco, errore per l'ID 99 ed eliminazione
  dell'ID 1 con i risultati attesi della sezione «Note persistenti».
- Dopo le prove `archivio\note.sqlite` è stato eliminato; `git check-ignore -v
  archivio/note.sqlite` indica la regola `archivio/` di `.gitignore`.
- Non provati in questo task:
  - testo vuoto o troppo lungo, `limite` fuori intervallo e archivio non accessibile posti al
    modello (coperti dai test automatici);
  - un'eliminazione riuscita chiesta al modello (provata solo con l'invocazione diretta, che
    produce `nota eliminata id=1`);
  - Ctrl+C durante una chiamata agli strumenti delle note;
  - le voci 1–14 della checklist in sessioni dell'app (le prove reali automatiche hanno
    ricontrollato orologio, `calcola`, `converti_unita`, `conta_giorni` e il catalogo).

### Lezione 5 — catalogo locale (2026-11-10)

Eseguite il 2026-11-10 con `google/gemma-4-e2b` in LM Studio, in locale e con Docker Compose.

- Discovery: `['calcola', 'converti_unita', 'conta_giorni', 'aggiungi_giorni_lavorativi',
  'cerca_corsi', 'dettaglio_corso']` nel container e nelle sessioni in locale.
- Prima prova di «Quanto dura il corso di Python a Udine?»: la prova reale automatica è
  **fallita** (`['cerca_corsi']` invece di `['cerca_corsi', 'dettaglio_corso']`).
  - Gemma chiamava `cerca_corsi` con `{"testo": "Python Udine"}` (3 tentativi su 3 anche
    nell'app, in locale), riceveva `Nessun corso trovato per "Python Udine".` e si fermava. In
    2 casi su 3 proponeva di cercare solo «Python».
  - Il collegamento era corretto. La descrizione completa arrivava al modello e conteneva
    già l'esempio `cerca_corsi(testo="Python")`, ma il parametro `testo` non aveva una
    descrizione propria.
  - Dopo l'aggiunta della descrizione del parametro («UNA sola parola: la materia ... OPPURE
    la sede ..., mai entrambe insieme»), gemma cerca `Python` e poi chiede `dettaglio_corso`
    con `ITS-DAT-01`.
- Prove reali automatiche dopo la correzione (`PROVE_REALI=1`, in locale): 6 superate su 6.
- Voci 13 e 14, con input da script e log letti sull'output del comando: superate in locale
  (3 sessioni su 3) e in Docker (1 sessione), con gli stessi argomenti e le stesse risposte.
  - Voce 13: «dura 90 ore», con le due chiamate nello stesso turno.
  - Voce 14: `cerca_corsi` con `astronautica`, risposta senza corsi inventati.
- Errori controllati verificati con l'invocazione diretta, in locale: codice `ITS-XYZ-99`
  inesistente e `max_risultati` 21.
- Non provati in questo task:
  - `testo` vuoto e codice inesistente posti al modello (coperti dai test automatici e
    dall'invocazione diretta);
  - le voci 1–12 della checklist in sessioni dell'app (le prove reali automatiche hanno
    ricontrollato orologio, `calcola`, `converti_unita` e `conta_giorni`).

### Lezione 5 — giorni e scadenze (2026-11-10)

Eseguite il 2026-11-10 con `google/gemma-4-e2b` in LM Studio, in locale e con Docker Compose.

- Discovery: `['calcola', 'converti_unita', 'conta_giorni', 'aggiungi_giorni_lavorativi']` in
  locale e nel container.
- Prove reali automatiche (`PROVE_REALI=1`, in locale): 5 superate su 5. Per «Quanti giorni
  lavorativi ci sono tra il 23 e il 28 dicembre 2026?» gemma chiama `conta_giorni` con
  `{"data_fine": "2026-12-28", "data_inizio": "2026-12-23"}`. Risultato: 5 giorni di
  calendario, 2 lavorativi, Natale e Santo Stefano.
- Voci 11 e 12, con input da script e log letti sull'output del comando: superate in locale
  e in Docker, con gli stessi argomenti e gli stessi risultati in entrambi gli ambienti.
  «10 giorni lavorativi dopo il 2026-12-20» dà `2027-01-05`, verificato a mano: il 25/12 e
  l'1/1 sono festivi.
- In locale, 3 tentativi su 3 per ciascuna domanda:
  - «Che data è 15 giorni lavorativi dopo il 3 aprile 2026?» (data scritta a parole): gemma
    passa `{"data_inizio": "2026-04-03", "giorni": 15}` e lo strumento risponde `2026-04-27`.
  - «Quanti giorni lavorativi ci sono tra il 20 dicembre 2027 e il 10 gennaio 2028?»: gemma
    chiama `conta_giorni` e nei log compare `execution=tool_error` con `anno 2028 non
    disponibile: ...`. Gemma risponde che il 2028 non è disponibile, senza numeri inventati.
- Errori controllati verificati anche con l'invocazione diretta, in locale: `23/12/2026`,
  data finale prima dell'iniziale, scadenza nel 2028.
- Non provati in questo task:
  - le domande dei due punti precedenti in Docker;
  - `giorni` fuori dai limiti con il modello (coperto solo dai test automatici);
  - le voci 1–8 della checklist in sessioni dell'app (`calcola` e `converti_unita`
    ricontrollati solo dalle prove reali automatiche).

### Lezione 5 — convertitore di unità (2026-11-10)

Eseguite il 2026-11-10 con `google/gemma-4-e2b` in LM Studio, in locale e con Docker Compose.

- Discovery: `['calcola', 'converti_unita']` in locale e nel container.
- Prove reali automatiche (`PROVE_REALI=1`, in locale): 4 superate su 4; per «Quanti miglia
  sono 10 km?» gemma chiama `converti_unita` con `{"a_unita": "mi", "da_unita": "km",
  "valore": 10}` → `10 km = 6.2137 mi`.
- In Docker (input da script, log letti sull'output): voce 9 superata; «Quanti pollici sono 30
  centimetri?» → `cm` → `in`, `30 cm = 11.811 in` (il simbolo `in` è passato correttamente);
  «Quanto fa 1234 per 5678?» → `calcola` con `1234 * 5678` (la calcolatrice continua a
  funzionare con due strumenti nel catalogo).
- «Quanti gradi Fahrenheit sono 100 gradi Celsius?»: in locale, come prima domanda della
  sessione, gemma chiama `converti_unita` con `C` → `F` (3 tentativi su 3); in Docker, nell'unico
  tentativo, a metà di una sessione più lunga, ha scelto invece `calcola` con
  `(100 * 9/5) + 32` → 212. La risposta è corretta in entrambi i casi.
- Voce 10 (`Converti 5 metri in chilogrammi`): gemma **non** chiama lo strumento e risponde
  da sola che lunghezza e massa non si convertono (1 volta in Docker, 3 in locale); nessun
  numero inventato, ma `execution=tool_error` non è stato osservato nella chat. L'errore
  controllato è stato verificato in locale con l'invocazione diretta
  (`unità incompatibili: m è lunghezza, kg è massa`), anche per `parsec` e `-300 C`.

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
- Con «Converti 5 metri in chilogrammi» gemma non chiama `converti_unita`: il rifiuto dello
  strumento è provato solo con l'invocazione diretta.
- Per una temperatura gemma ha scelto, in un caso su quattro, `calcola` con la formula invece di
  `converti_unita` (risultato corretto, strumento diverso).
- Meteo con la rete scollegata (voce 20 della checklist) non ancora provato in reale.
