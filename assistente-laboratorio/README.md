# Assistente del laboratorio

Applicazione da terminale in Python il cui turno di conversazione è un grafo LangGraph
esplicito, collegato a un modello locale servito da LM Studio. Oltre all'orologio interno,
l'assistente usa gli strumenti pubblicati da un server MCP del progetto, che scopre all'avvio.
Prima dell'agente un router decide se la domanda rientra nell'ambito dichiarato in
configurazione; le domande fuori ambito ricevono un rifiuto senza raggiungere l'agente.
Dopo l'agente un revisore controlla se la risposta è coerente con la domanda; se non lo è,
il motivo torna all'agente come indicazione, fino a un limite di revisioni.
All'inizio di ogni turno, se la conversazione supera una soglia di messaggi, i messaggi più
vecchi vengono sostituiti da un riassunto e restano intatti solo gli ultimi.
A inizio sessione l'applicazione legge dal server MCP le preferenze dell'utente (lingua, fuso
orario, stile delle risposte) e le mette in cima al prompt di sistema dell'agente: per cambiare
il comportamento basta modificare un file, senza toccare il codice.
Il server MCP pubblica anche due prompt, `spiega` e `riassumi_conversazione`, che l'utente
richiama con i comandi `/prompts` e `/prompt`: l'applicazione controlla gli argomenti senza
chiamare il modello e manda i messaggi ottenuti al grafo, come una domanda.

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
| `FUSO_ORARIO` | sì | fuso IANA di ripiego dell'orologio, es. `Europe/Rome`: si usa se le preferenze dell'utente non sono disponibili (vedi «Preferenze dell'utente (resource MCP)»); altrimenti vale il fuso delle preferenze |
| `AMBITO_AGENTE` | sì | argomenti dell'agente, separati da virgola, es. `data e ora, calcoli, conversioni di unità, giorni lavorativi e scadenze, corsi del catalogo, note, meteo, concetti del corso (LLM, agenti, MCP)`; le domande fuori da questo ambito sono rifiutate dal router (saluti e conversazione sono sempre ammessi) |
| `MAX_PASSI` | no | chiamate massime al modello per ogni tentativo di risposta dell'agente (default `5`; dopo un rifiuto del revisore il conteggio riparte) |
| `MAX_REVISIONI` | no | volte massime in cui il revisore può rimandare la risposta all'agente in una domanda (default `2`, intero maggiore di zero) |
| `SOGLIA_RIASSUNTO` | no | numero di messaggi della conversazione oltre il quale i più vecchi vengono riassunti (default `20`, intero maggiore di zero) |
| `MESSAGGI_DA_TENERE` | no | quanti messaggi recenti restano intatti dopo il riassunto (default `6`, intero maggiore di zero e minore di `SOGLIA_RIASSUNTO`) |
| `LOG_LEVEL` | no | `DEBUG`, `INFO` (default), `WARNING`, `ERROR`, `CRITICAL` |

Si legge solo il `.env` della cartella da cui si avvia l'applicazione; le variabili già
impostate nell'ambiente hanno la precedenza. Se la configurazione manca o non è valida,
l'applicazione termina subito con `Configurazione non valida: ...`.

`AMBITO_AGENTE` è obbligatoria dalla lezione 6: un `.env` creato prima va completato a mano
con la riga di `.env.example`, altrimenti l'avvio si ferma con
`Configurazione non valida: variabili mancanti: AMBITO_AGENTE`. Il testo del rifiuto riusa lo
stesso valore: `Questa domanda è fuori dal mio ambito. Posso aiutarti con: <AMBITO_AGENTE>.`
Il prompt del router contiene alcuni esempi legati all'ambito attuale
(`assistente/router.py`): se l'ambito cambia, vanno aggiornati.

Dalla lezione 6, step 5, l'ambito dell'esempio comprende anche `concetti del corso (LLM,
agenti, MCP)`: serve perché il router lasci passare il prompt `spiega` (vedi «Prompt MCP e
comandi della CLI»). Chi ha già un `.env` deve aggiungere a mano questa parte alla riga
`AMBITO_AGENTE`: il `.env` non si aggiorna da solo. Con l'ambito allungato sono cambiati
anche gli esempi del router (`«Spiegami cos'è un agente»` e `«Che ore sono e piove a Udine?»`,
entrambi `conversazione`). Nelle prove reali, senza questi esempi, `gemma-4-e2b` respingeva
sempre la domanda composta «Che ore sono e che tempo fa a Pordenone?» (0 volte su 10); togliendo
dall'ambito i concetti del corso, respingeva invece il prompt `spiega` (0 volte su 3). Con gli
esempi la domanda composta passa solo a volte (3 volte su 5): è un limite noto, vedi «Esiti
delle prove reali».

## Test automatici

Non richiedono LM Studio né la rete: usano un modello simulato con risposte predefinite, un
orologio con istante fisso e risposte HTTP simulate per il meteo. I test del server e del
collegamento MCP avviano il server vero del progetto come processo locale.

```powershell
python -m pytest
```

Le diciassette prove reali di `tests/test_reale.py` risultano *skipped*.

`tests/test_router.py` controlla prompt, schema, filtro dei messaggi e lettura della risposta
del router; `tests/test_grafo.py` e `tests/test_conversazione.py` provano i due percorsi con un
router simulato (`conversazione` → agente; `fuori ambito` → rifiuto senza alcuna chiamata al
modello dell'agente), la risposta non valida del router e l'errore di collegamento durante il
router (cronologia invariata).

`tests/test_revisore.py` controlla prompt, schema, scelta di domanda e risposta, lettura della
valutazione e testo dell'indicazione del revisore. Con un revisore simulato, `tests/test_grafo.py`
e `tests/test_conversazione.py` provano le tre evidenze del PDF (risposta coerente approvata al
primo passaggio; risposta parziale rifiutata con un motivo e corretta; limite di revisioni
rispettato con un revisore che rifiuta sempre), la risposta non valida del revisore, i passi
azzerati dopo una revisione, il caso peggiore senza errore di ricorsione di LangGraph,
l'errore di collegamento durante il revisore e la cronologia dopo una revisione.

`tests/test_riassunto.py` controlla il prompt del riassunto (chiede di conservare il nome e le
informazioni sull'utente, non nomina gli strumenti), il punto di taglio (anche quando cade su una
richiesta di strumento, su un risultato, su un'indicazione del revisore o sulla bozza rifiutata:
torna sempre alla domanda che apre il turno), la trascrizione e il paragrafo nel messaggio di
sistema. Con un riassuntore simulato, `tests/test_grafo.py` e `tests/test_conversazione.py`
provano le evidenze del PDF (sotto la soglia nessuna chiamata al modello; sopra la soglia log
`prima`/`dopo`; nome usato dopo la compressione), il riassunto aggiornato e non accumulato, il
taglio che non separa richiesta e risultato di uno strumento, il turno unico più lungo della
soglia, il riassunto vuoto, l'errore di collegamento durante il riassunto (cronologia e
riassunto invariati) e il riassunto conservato tra i turni. `tests/test_configurazione.py`
controlla i default e i valori non validi di `SOGLIA_RIASSUNTO` e `MESSAGGI_DA_TENERE`.

`tests/test_preferenze.py` controlla la validazione del file delle preferenze (file valido, chiavi
in più ignorate, e ogni difetto con il suo motivo: JSON non valido o vuoto, radice che non è un
oggetto, chiave mancante, valori del tipo sbagliato, lingua vuota o su più righe, fuso
inesistente o strano, stile sconosciuto), i predefiniti e il paragrafo in cima al prompt
dell'agente. `tests/test_server_mcp.py` verifica che la resource `utente://preferenze` sia in
`resources/list` (tipo `application/json`) e non in `tools/list`, che restituisca il testo del
file (anche con il BOM) e che fallisca se il file manca. `tests/test_collegamento_mcp.py` legge la
resource dal server vero con un file temporaneo, mai quello dell'utente, e controlla le righe
`preferenze lette ...` e `preferenze non disponibili (...)` e i predefiniti con il fuso di
ripiego. `tests/test_grafo.py` controlla che il messaggio di sistema dell'agente inizi con le
preferenze (e finisca con il riassunto, se c'è) e che router, revisore e riassuntore non le
ricevano. `tests/test_terminale.py` verifica che `main()` legga le preferenze dopo la discovery
(server giù: codice 3 senza leggerle) e che l'orologio usi il fuso delle preferenze, oppure
quello di `FUSO_ORARIO` con i predefiniti.

Prompt MCP (step 5): `tests/test_server_mcp.py` verifica che `spiega` e `riassumi_conversazione`
siano in `prompts/list` con descrizioni e argomenti, che restituiscano un messaggio `user` (anche
con i valori predefiniti e con un valore non previsto come `livello=pippo`) e che non siano in
`tools/list`. `tests/test_prompt_mcp.py` controlla la lettura del comando `/prompt` (virgolette,
apostrofo, barra rovesciata e ogni errore con il suo messaggio), il controllo degli argomenti
rispetto all'elenco del server e il testo di `/prompts`. `tests/test_collegamento_mcp.py`
elenca e richiama i prompt dal server vero e verifica che, con un controllo fallito, la
richiesta `prompts/get` non parta. `tests/test_conversazione.py` prova il turno aperto dai
messaggi di un prompt (dopo la cronologia, attraverso router e revisore, cronologia invariata
se il turno fallisce). `tests/test_terminale.py` prova i comandi `/prompts` e `/prompt` con un
collegamento MCP simulato: comandi non validi senza chiamare il modello, maiuscole e parole in
più, server MCP giù durante un comando.

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
`ora_corrente` a una domanda sull'ora, nessuno strumento a «Ciao, come stai?», `calcola`
a «Quanto fa 1234 per 5678?» (con `7006652` nella risposta), `converti_unita` a «Quanti
miglia sono 10 km?», `conta_giorni` a «Quanti giorni lavorativi ci sono tra il 23 e il 28
dicembre 2026?», nello stesso turno `cerca_corsi` poi `dettaglio_corso` a «Quanto dura il
corso di Python a Udine?», una sola `aggiungi_nota` a «Ricordami di consegnare il report
venerdì» e `meteo_citta` a «Che tempo fa a Pordenone?» (questa prova usa anche la rete).
La nona prova verifica il router: «Raccontami la storia di Roma» riceve il rifiuto fisso, nel
log c'è `router categoria=fuori ambito ... next_node=rifiuto` e nessuna riga
`Inizio chiamata al modello`. Le altre otto passano dal router, che deve classificarle
`conversazione`, e dal revisore.

Tre prove riguardano il revisore: «Che ore sono e che tempo fa a Pordenone?» deve finire con
una riga `revisore coerente=sì` (al primo passaggio o dopo una revisione; il log mostra quale
dei due casi); «Ciao, come stai?» deve avere una sola riga del revisore, con `coerente=sì`; il
revisore chiamato da solo, davanti a una risposta parziale preparata dal test («Sono le 10:30.»
alla domanda su ora e meteo), deve rispondere `coerente=no` con un motivo.

Una prova riguarda il riassunto (evidenza minima del PDF): con una conversazione costruita dal
test con `SOGLIA_RIASSUNTO=4` e `MESSAGGI_DA_TENERE=2` (senza toccare il `.env`) si chiede «Mi
chiamo Luca», «Che ore sono?», «Quanto fa 12 per 3?» e infine «Come mi chiamo?»: nel log deve
comparire almeno una riga `riassunto messaggi prima=... dopo=...`, il primo turno non deve più
essere nella cronologia e la risposta deve contenere «Luca». Questa prova da sola dura 3–4
minuti; le tredici prove fino allo step 3 durano circa 13 minuti.

Due prove riguardano le preferenze (step 4) e cambiano per qualche istante il file
`archivio\preferenze.json`: prima ne fanno una copia su disco, `archivio\preferenze.json.bak`, e
alla fine lo rimettono com'era e tolgono la copia (oppure cancellano il file, se prima non
esisteva). Se la serie viene interrotta a metà (finestra chiusa, Ctrl+C), la copia resta su
disco e le prove successive si fermano con `RuntimeError: trovato ...preferenze.json.bak ...`
senza toccare nulla: per rimettere il file com'era,
`Move-Item -Force archivio\preferenze.json.bak archivio\preferenze.json`. Se invece prima il file
non c'era e non c'è nessuna copia, basta `Remove-Item archivio\preferenze.json`. Con
`America/New_York` nel file, «Che ore sono?»
deve usare solo `ora_corrente`, il risultato deve finire con `(America/New_York)` e nel log deve
esserci una sola riga `preferenze lette uri=utente://preferenze ...`. Senza file, nel log deve
comparire `preferenze non disponibili (...)` e l'orologio deve usare il fuso di `FUSO_ORARIO`.
Tutte le altre prove leggono le preferenze vere dell'utente, come l'applicazione.

Due prove riguardano i prompt MCP (step 5) e seguono lo stesso percorso del comando `/prompt`,
senza tastiera: `spiega` con `argomento="Model Context Protocol"` e `livello=base` deve passare
dal router come `conversazione` (serve l'ambito allargato nel `.env`, vedi «Configurazione») e
dal revisore, con una risposta che non è il rifiuto; `riassumi_conversazione` con
`stile=sintetico`, dopo «Mi chiamo Luca» e «Quanto fa 45 diviso 9?», deve dare una risposta che
contiene «Luca» e il risultato 5. L'adeguatezza al livello si giudica a mano (checklist).

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

All'avvio l'applicazione lancia il server MCP e ne legge il catalogo (vedi «Strumenti MCP»),
poi legge le preferenze dell'utente (vedi «Preferenze dell'utente (resource MCP)»). Al prompt `Tu> ` si scrive la domanda (oppure un comando `/prompts` o `/prompt`, vedi «Prompt MCP e comandi della CLI»). La sessione si chiude con `esci`, con Ctrl+C o con
la fine dell'input; le righe vuote sono ignorate. La conversazione resta in memoria per tutta
la sessione e si perde alla chiusura.

Le righe di log (su stderr, nello stesso terminale) iniziano con livello e componente, per
esempio `INFO assistente.grafo: Inizio chiamata al modello (passo 1/5)`; il resto è la risposta.
All'avvio compaiono anche alcune righe del server MCP (`Starting MCP server 'Strumenti del
laboratorio' with transport 'stdio'`, `Processing request of type ListToolsRequest`,
`Processing request of type ReadResourceRequest`).

Se il modello non è raggiungibile l'applicazione non inventa risposte: mostra uno di questi
messaggi e la sessione continua, senza registrare il turno fallito nella cronologia.

- `Connessione fallita: controllare LM Studio, URL e porta.`
- `Attesa scaduta: controllare server, carico e tempi.`
- `Errore dal server: <codice> <testo>` (per esempio un id del modello sbagliato)
- `Il modello ha restituito una risposta vuota.`

Codici di uscita: `0` chiusura normale, `2` configurazione non valida, `3` server MCP non
disponibile.

Il percorso di ogni domanda nel grafo:

```
START → riassunto → router ─(conversazione, o risposta non valida)→ llm ⇄ strumenti
                           │                                          └─(risposta finale)→ revisore
                           │                                                 ├─(coerente: sì, o risposta non valida)→ END
                           │                                                 ├─(coerente: no, revisioni < MAX_REVISIONI)→ llm
                           │                                                 └─(coerente: no, limite raggiunto)→ END
                           └─(fuori ambito)→ rifiuto → END
```

Il nodo riassunto è il primo di ogni turno. Conta i messaggi della conversazione, compresa la
domanda nuova: se non superano `SOGLIA_RIASSUNTO` non fa nulla e non chiama il modello. Se la
superano, sceglie il punto di taglio: parte dagli ultimi `MESSAGGI_DA_TENERE` messaggi e, se lì
non c'è una domanda dell'utente, torna indietro fino alla domanda che apre quel turno. Così una
richiesta di strumento non viene mai separata dal suo risultato, un'indicazione del revisore non
resta senza la sua bozza e a volte si tengono più messaggi di `MESSAGGI_DA_TENERE`; se l'unica
domanda è all'inizio (un solo turno molto lungo) non c'è niente da togliere. I messaggi prima
del taglio vanno al riassuntore (stesso modello, prompt proprio in `assistente/riassunto.py`,
nessuno strumento, testo libero) insieme al riassunto precedente, e il riassunto nuovo e
completo **sostituisce** il campo `riassunto` dello stato: non si accumula e non diventa un
messaggio. I messaggi riassunti escono dalla cronologia. Il riassunto entra in coda al
messaggio di sistema dell'agente e del router, con l'intestazione `Cosa sai già della
conversazione con l'utente (usalo per rispondere):`; il revisore non lo vede. La conversazione
conserva il riassunto tra un turno e l'altro; se il turno fallisce, cronologia e riassunto
restano com'erano. Il riassuntore non conta nelle chiamate di `MAX_PASSI`.

Il router usa lo stesso modello dell'agente, ma senza strumenti, con un proprio prompt di
sistema (che contiene `AMBITO_AGENTE`) e una risposta strutturata con `categoria`
(`conversazione` o `fuori ambito`) e `motivo`. Vede solo le domande e le risposte di testo
della conversazione, non i giri degli strumenti, e non conta nelle chiamate di `MAX_PASSI`.
Il motivo compare solo nel log. Il rifiuto entra nella cronologia come una risposta normale.

### Formato dei log del router

```
INFO assistente.grafo: Inizio chiamata al router
INFO assistente.grafo: router categoria=conversazione motivo=<motivo> next_node=llm (agente)
INFO assistente.grafo: Inizio chiamata al modello (passo 1/5)
```

```
INFO assistente.grafo: Inizio chiamata al router
INFO assistente.grafo: router categoria=fuori ambito motivo=<motivo> next_node=rifiuto
INFO assistente.grafo: rifiuto inviato, nodo agente non eseguito
```

`llm` è il nome interno del nodo dell'agente. Nel percorso fuori ambito non compare alcuna
riga `Inizio chiamata al modello`: è la prova che l'agente non è stato eseguito. Se la risposta
del router non si può leggere (JSON non valido, risposta troncata dal limite di token o bloccata
dal filtro del server), ha una categoria diversa dalle due ammesse oppure un motivo mancante o
vuoto, la domanda passa comunque all'agente con l'avviso
`WARNING assistente.grafo: router risposta non valida (<dettaglio>): passaggio all'agente next_node=llm (agente)`.
Se LM Studio non risponde durante il router, il turno fallisce con gli stessi messaggi
dell'agente (`Connessione fallita: ...`) e la cronologia non cambia.

Il revisore usa anch'esso lo stesso modello, senza strumenti, con un proprio prompt di sistema
(`assistente/revisore.py`) e una risposta strutturata con `coerente` (`sì` o `no`) e `motivo`.
Vede solo la domanda del turno e la risposta finale dell'agente (non la conversazione
precedente né i giri degli strumenti): giudica se la risposta copre tutte le parti della domanda
e resta in tema, non se i dati sono veri. Una domanda breve che prosegue la conversazione
(«E domani?») non viene bocciata per mancanza di contesto. Se la risposta non è coerente,
nella conversazione entra un'indicazione per l'agente
(`Indicazione del revisore: la risposta precedente non è coerente con la domanda. Motivo: ...`)
e l'agente risponde di nuovo, con il conteggio di `MAX_PASSI` che riparte. Dopo
`MAX_REVISIONI` rifiuti l'utente riceve l'ultima risposta e il limite compare solo nel log.
Nella cronologia della sessione restano domanda, bozza rifiutata, indicazione e risposta nuova;
il router salta indicazioni e bozze rifiutate. Il rifiuto del router non passa dal revisore.

### Formato dei log del revisore

```
INFO assistente.grafo: Inizio chiamata al revisore
INFO assistente.grafo: revisore coerente=sì motivo=<motivo> next_node=END
```

```
INFO assistente.grafo: Inizio chiamata al revisore
INFO assistente.grafo: revisore coerente=no motivo=<motivo> next_node=llm (agente) revisione=1/2
INFO assistente.grafo: Inizio chiamata al modello (passo 1/5)
```

```
INFO assistente.grafo: revisore coerente=no motivo=<motivo> next_node=END revisione=2/2
WARNING assistente.grafo: limite di revisioni raggiunto (2): restituita l'ultima risposta
```

`revisione=n/m` indica le revisioni fatte nel turno e `MAX_REVISIONI`. Se la risposta del
revisore non si può leggere (JSON non valido, risposta troncata o filtrata), ha un valore di
`coerente` diverso da `sì`/`no` (anche `si` senza accento) oppure un motivo vuoto, la risposta
dell'agente è approvata con l'avviso
`WARNING assistente.grafo: revisore risposta non valida (<dettaglio>): risposta approvata next_node=END`.
Se LM Studio non risponde durante il revisore, il turno fallisce con i soliti messaggi e la
cronologia non cambia. Motivo e dettaglio sono troncati a 200 caratteri.

### Formato dei log del riassunto

Sotto la soglia (o uguale), nessuna chiamata al modello:

```
INFO assistente.grafo: riassunto non necessario messaggi=8 soglia=20
```

Sopra la soglia, con messaggi da togliere (`prima` e `dopo` sono i messaggi della conversazione
prima e dopo il taglio, `caratteri` la lunghezza del riassunto):

```
INFO assistente.grafo: Inizio chiamata al riassunto (messaggi=22 soglia=20 da_togliere=15)
INFO assistente.grafo: riassunto messaggi prima=22 dopo=7 caratteri=<lunghezza del riassunto>
```

Sopra la soglia, ma senza niente da togliere (un solo turno più lungo della soglia):

```
INFO assistente.grafo: riassunto non necessario messaggi=23 soglia=20 da_togliere=0
```

Il testo del riassunto compare solo con `LOG_LEVEL=DEBUG`
(`DEBUG assistente.grafo: riassunto testo=...`, troncato a 500 caratteri). Se il modello
restituisce un riassunto vuoto, i messaggi non vengono compressi, il turno continua e compare
`WARNING assistente.grafo: riassunto vuoto: messaggi non compressi (messaggi=<m>)`. Se LM Studio
non risponde durante il riassunto, il turno fallisce con i soliti messaggi e cronologia e
riassunto non cambiano.

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
esegue davvero e che restituisce data e ora nel fuso delle preferenze dell'utente, oppure in
`FUSO_ORARIO` se le preferenze non sono disponibili, per esempio
`2026-11-10T09:31:54+01:00 (Europe/Rome)`. Il fuso lo sceglie l'applicazione a inizio sessione,
non il modello, e non viene mai preso dal sistema.
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

## Preferenze dell'utente (resource MCP)

Oltre agli strumenti, il server MCP pubblica una **resource**: le preferenze dell'utente,
all'indirizzo `utente://preferenze` (tipo `application/json`). Il server restituisce il testo del
file `archivio\preferenze.json` (relativo alla cartella da cui si avvia l'applicazione) senza
controllarlo. La resource non è uno strumento: il modello non la vede e non la può chiamare (non
passa da `bind_tools` e non compare nella riga `discovery ... tools=[...]`). La legge
l'applicazione, una sola volta a inizio sessione, prima della prima domanda; per vedere una
modifica del file bisogna chiudere e riavviare l'applicazione.

Contenuto del file:

```json
{"lingua": "italiano", "fuso_orario": "America/New_York", "stile": "sintetico"}
```

- `lingua`: la lingua delle risposte dell'agente, testo libero non vuoto su una riga (es.
  `italiano`, `inglese`, `francese`);
- `fuso_orario`: nome IANA valido (es. `Europe/Rome`, `America/New_York`), usato dallo strumento
  `ora_corrente`;
- `stile`: esattamente `sintetico` (risposte brevi e chiare, in poche frasi) oppure `dettagliato`
  (risposte complete, con spiegazioni e passaggi).

Le tre chiavi sono obbligatorie; altre chiavi sono ignorate. Il file non è in Git (la cartella
`archivio` è esclusa): su una copia nuova del progetto va creato a mano, per esempio così:

```powershell
New-Item -ItemType Directory -Force archivio | Out-Null
Set-Content -Path archivio\preferenze.json -Encoding utf8 -Value '{"lingua": "italiano", "fuso_orario": "America/New_York", "stile": "sintetico"}'
```

In Windows PowerShell 5.1 `-Encoding utf8` aggiunge all'inizio il carattere invisibile BOM: il
server lo tollera. Il file deve essere in UTF-8: non crearlo con `echo ... >` o `Out-File`, che in
Windows PowerShell 5.1 salvano in UTF-16, né con `Set-Content` senza `-Encoding` se contiene
lettere accentate (vedi «Diagnosi»). Si può anche scrivere il file con un editor di testo che
salvi in UTF-8. Per tornare ai valori
predefiniti basta togliere il file:

```powershell
Remove-Item archivio\preferenze.json
```

**Valori predefiniti.** Se la resource non è disponibile (file assente, server che non riesce a
leggerla) o il contenuto non è valido (JSON rotto, chiave mancante, fuso sconosciuto, stile
diverso da `sintetico`/`dettagliato`, lingua vuota o su più righe), l'applicazione parte comunque
con **tutti** i valori predefiniti, mai con un miscuglio: lingua `italiano`, stile `sintetico` e il
fuso di `FUSO_ORARIO`. Sono gli stessi comportamenti di prima dello step 4. Il motivo compare nel
log.

**Dove finiscono.** Le preferenze diventano il primo paragrafo del messaggio di sistema
dell'agente, prima delle istruzioni sugli strumenti (e prima del riassunto, che resta in coda):

```
Preferenze dell'utente: rispondi in italiano. Stile: risposte brevi e chiare, in poche frasi. Il fuso orario predefinito è America/New_York: lo strumento ora_corrente lo usa già, non chiederlo all'utente.
```

Il fuso lo applica l'applicazione: lo strumento `ora_corrente` viene creato a inizio sessione con
il fuso delle preferenze, quindi a «Che ore sono?» risponde in quel fuso senza chiederlo. Router,
revisore e riassuntore non ricevono le preferenze: i loro testi interni (motivi, riassunto)
restano in italiano, come il testo fisso del rifiuto.

### Formato dei log delle preferenze

La lettura compare una volta, prima di `Tu> `, con il logger `assistente.collegamento_mcp`,
separata dalle righe degli strumenti (`assistente.grafo`, `variant=...`). Dal server arriva anche
la riga `Processing request of type ReadResourceRequest`.

```
INFO assistente.collegamento_mcp: preferenze lette uri=utente://preferenze lingua=italiano fuso=America/New_York stile=sintetico
```

```
WARNING assistente.collegamento_mcp: preferenze non disponibili (stile deve essere 'sintetico' o 'dettagliato', non 'lungo'): valori predefiniti lingua=italiano fuso=Europe/Rome stile=sintetico
```

Con il file assente il motivo è
`Error reading resource 'utente://preferenze': [Errno 2] No such file or directory: 'archivio\\preferenze.json'`;
in questo caso, prima del WARNING, il server stampa anche `Error reading resource
'utente://preferenze'` con un lungo riquadro di traceback che termina con `FileNotFoundError`: è il
server che segnala il file mancante, l'applicazione prosegue con i predefiniti.

### Tool, resource e prompt

| Primitiva MCP | Chi la usa | Quando | Nei log |
|---|---|---|---|
| tool (es. `calcola`) | il modello, che decide se chiamarlo | durante il turno, quando serve | `variant=mcp tool=...` (`assistente.grafo`) |
| resource (`utente://preferenze`) | l'applicazione (l'host) | una volta, a inizio sessione | `preferenze lette ...` o `preferenze non disponibili (...)` (`assistente.collegamento_mcp`) |
| prompt (`spiega`, `riassumi_conversazione`) | l'utente, con `/prompts` e `/prompt` | quando l'utente scrive il comando | `prompts/list ...`, `prompt richiamato ...`, `prompt messaggi ottenuti ...` (`assistente.collegamento_mcp`) |

Lettura delle preferenze senza modello (stampa i valori usati; con il file assente o non valido
stampa i predefiniti con il fuso indicato nel comando):

```powershell
python -c "from pathlib import Path; from zoneinfo import ZoneInfo; from assistente.configurazione import configura_log; from assistente.collegamento_mcp import carica_preferenze, connessione_stdio; configura_log('INFO'); print(carica_preferenze(connessione_stdio(Path.cwd()), ZoneInfo('Europe/Rome')))"
```

Atteso, con il file dell'esempio: la riga `INFO assistente.collegamento_mcp: preferenze lette
uri=utente://preferenze lingua=italiano fuso=America/New_York stile=sintetico` e poi
`Preferenze(lingua='italiano', fuso=zoneinfo.ZoneInfo(key='America/New_York'), stile='sintetico')`.

**Docker.** La cartella `archivio` è già montata nel container (vedi «Avvio con Docker
Compose»): il file modificato sul PC vale anche in Docker. Basta avviare un nuovo container, senza
ricostruire l'immagine.

## Prompt MCP e comandi della CLI

La terza primitiva MCP è il **prompt**: un modello di istruzioni con argomenti, salvato sul
server, che sceglie e richiama **l'utente** con un comando. Non è uno strumento: il modello non
lo vede e non lo può chiamare (non passa da `bind_tools`). MCP non prevede un comando standard: i
comandi `/prompts` e `/prompt` li definisce l'applicazione.

Il server pubblica due prompt (`assistente/server_mcp.py`), ognuno con un solo messaggio di
ruolo `user`:

- `spiega(argomento, livello)`: `argomento` obbligatorio (il concetto da spiegare), `livello`
  facoltativo (`base`, `intermedio` o `avanzato`; predefinito `base`). Il testo comincia con
  `Spiegami «<argomento>» a livello <livello>.` e aggiunge una frase che descrive **solo** il
  livello richiesto (`base`: parole semplici, senza gergo tecnico, con un esempio concreto;
  `intermedio`: termini tecnici spiegati; `avanzato`: dettagli tecnici); un livello fuori elenco
  (per esempio `pippo`) non viene bloccato e resta senza descrizione. Quando il testo descriveva
  tutti e tre i livelli, `gemma-4-e2b` spiegava l'argomento a tutti e tre;
- `riassumi_conversazione(stile)`: `stile` facoltativo (`sintetico` o `dettagliato`; predefinito
  `sintetico`). Il testo è `Riassumi in stile <stile> i turni di questa conversazione (domande e
  risposte), senza aggiungere informazioni nuove.` Il server non vede la conversazione: la vede
  l'agente, che ha la cronologia (e, dopo una compressione, il riassunto).

I valori degli argomenti non sono controllati: `livello=pippo` passa e finisce così com'è nel
testo.

### `/prompts`

Elenca i prompt del server, letti ogni volta con `prompts/list` (nessuna copia in memoria). Non
chiama il modello e non entra nella cronologia. Con parole in più risponde
`Uso: /prompts (senza argomenti)`.

```
Tu> /prompts
spiega: Spiega un argomento al livello richiesto.
  argomento (obbligatorio): concetto da spiegare
  livello (facoltativo): base, intermedio o avanzato
riassumi_conversazione: Riassume i turni della conversazione della sessione corrente.
  stile (facoltativo): sintetico o dettagliato
```

### `/prompt nome argomento=valore ...`

```
Tu> /prompt spiega argomento="Model Context Protocol" livello=base
Tu> /prompt riassumi_conversazione stile=dettagliato
```

Le parole si separano come in una shell:
- un valore con spazi va tra virgolette doppie: `argomento="Model Context Protocol"`;
- un apostrofo va dentro le virgolette doppie: `argomento="l'agente"` (senza virgolette
  l'apostrofo apre una citazione che non si chiude);
- una barra rovesciata va tra apici singoli: `argomento='C:\dati'` (senza apici la barra viene
  tolta);
- chiave e valore si separano al primo `=`; le chiavi vanno scritte esattamente come nell'elenco
  (minuscole).

Solo `/prompts` e `/prompt` scritti così, in minuscolo e come prima parola, sono comandi: ogni
altra riga (anche `/Prompts` o `/help`) è una domanda normale.

Prima di chiedere il prompt al server, l'applicazione legge di nuovo `prompts/list` e controlla
gli argomenti, senza chiamare il modello: prima gli argomenti sconosciuti, poi gli obbligatori
mancanti. Se il controllo passa, chiede il prompt (`prompts/get`, nella stessa sessione) e manda
i messaggi ottenuti al grafo, dopo la cronologia: passano da riassunto, router, agente,
strumenti e revisore come una domanda scritta a mano, e restano nella cronologia. Se il
controllo fallisce compare il messaggio, la richiesta non arriva al server né al modello e la
chat continua. Messaggi:

| Caso | Messaggio |
|---|---|
| `/prompt` da solo | `Uso: /prompt nome argomento=valore ...` |
| virgolette non chiuse | `Comando non valido: virgolette non chiuse (un apostrofo va tra virgolette doppie, es. argomento="l'agente").` |
| barra rovesciata alla fine | `Comando non valido: barra rovesciata alla fine (un valore con \ va tra apici singoli, es. argomento='C:\dati').` |
| parola senza `=` | `Argomento non valido: 'Context' (scrivere argomento=valore; un valore con spazi va tra virgolette).` |
| nome dell'argomento mancante | `Argomento non valido: '=base' (manca il nome dell'argomento).` |
| valore mancante (anche `livello=""`) | `Argomento non valido: 'livello=' (manca il valore).` |
| argomento ripetuto | `Argomento ripetuto: 'livello'.` |
| prompt inesistente | `Prompt sconosciuto: 'x'. Prompt disponibili: spiega, riassumi_conversazione.` |
| argomento sconosciuto | `Argomenti sconosciuti per 'spiega': colore. Argomenti ammessi: argomento, livello.` |
| argomento obbligatorio mancante | `Argomenti obbligatori mancanti per 'spiega': argomento.` |
| server MCP giù durante un comando | `Server MCP non disponibile: <motivo>` |

### Formato dei log dei prompt

Logger `assistente.collegamento_mcp`, separato dalle righe degli strumenti (`assistente.grafo`,
`variant=...`). Il server stampa anche `Processing request of type ListPromptsRequest` e
`Processing request of type GetPromptRequest`.

```
INFO assistente.collegamento_mcp: prompts/list prompts=['spiega', 'riassumi_conversazione']
INFO assistente.collegamento_mcp: prompt richiamato nome=spiega argomenti={"argomento": "Model Context Protocol", "livello": "base"}
INFO assistente.collegamento_mcp: prompt messaggi ottenuti numero=1 [user] Spiegami «Model Context Protocol» a livello base. Usa parole semplici, senza gergo tecnico, con un esempio concreto.
```

Il testo di ogni messaggio ottenuto è tagliato a 500 caratteri. Seguono le righe del turno già
note (`router categoria=...`, `variant=...`, `revisore coerente=...`): mostrano che il prompt
passa dal grafo. Un comando bloccato dal controllo lascia un WARNING e nessuna riga del grafo:

```
WARNING assistente.collegamento_mcp: prompt rifiutato nome=spiega motivo=Argomenti obbligatori mancanti per 'spiega': argomento.
```

Un comando scritto male (per esempio con le virgolette non chiuse) non contatta nemmeno il
server; il WARNING lo scrive `assistente.terminale`, con `nome=-` perché il nome non è ancora
stato letto:

```
WARNING assistente.terminale: prompt rifiutato nome=- motivo=Comando non valido: virgolette non chiuse (...)
```

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
`./archivio:/app/archivio`), quindi locale e Docker usano lo stesso `archivio\note.sqlite` e lo
stesso `archivio\preferenze.json` (una modifica delle preferenze non richiede `docker compose
build`: basta un nuovo `docker compose run`).
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

Router (lezione 6, step 1), in locale:

21. `Che ore sono?`: nei log `router categoria=conversazione motivo=... next_node=llm (agente)`,
    poi il giro di `ora_corrente` come nella voce 2.
22. `Raccontami la storia di Roma`: risposta `Questa domanda è fuori dal mio ambito. Posso
    aiutarti con: ...`; nei log `router categoria=fuori ambito motivo=... next_node=rifiuto` e
    `rifiuto inviato, nodo agente non eseguito`, nessuna riga `Inizio chiamata al modello`.
23. `Mi chiamo Luca`, poi `Come mi chiamo?`: entrambe `categoria=conversazione`; la risposta
    contiene «Luca».
24. `Cosa sai fare?`: `categoria=conversazione` e risposta dell'agente.
25. LM Studio fermo: `Connessione fallita: ...` già alla chiamata del router; la sessione
    continua e, riacceso il server, la domanda successiva riceve risposta.

Per lo step 1 in Docker si verifica solo che l'applicazione non si rompa: `docker compose
build` e avvio del container fino a `Tu> ` (con `AMBITO_AGENTE` nel `.env`).

Revisore (lezione 6, step 2), in locale:

26. `Che ore sono?`: router, giro di `ora_corrente`, poi `Inizio chiamata al revisore` e
    `revisore coerente=sì motivo=... next_node=END`.
27. `Che ore sono e che tempo fa a Pordenone?`: righe del revisore; se c'è
    `coerente=no ... next_node=llm (agente) revisione=1/2`, segue una nuova risposta
    dell'agente (`passo 1/5`) e un'altra riga del revisore.
28. `Mi chiamo Luca`, poi `Come mi chiamo?`: la risposta finale contiene ancora «Luca».
29. `Che tempo fa a Pordenone?`, poi `E domani?`: il revisore non boccia la seconda domanda per
    mancanza di contesto.
30. `Raccontami la storia di Roma`: rifiuto del router e nessuna riga `revisore`.
31. LM Studio fermo: `Connessione fallita: ...`, la sessione continua; riacceso il server, la
    domanda successiva riceve risposta e passa dal revisore.

Per lo step 2 in Docker si verifica ancora solo che l'applicazione non si rompa: `docker
compose build` e avvio del container fino a `Tu> `.

Riassunto (lezione 6, step 3), in locale, in una sola sessione con `SOGLIA_RIASSUNTO=4` e
`MESSAGGI_DA_TENERE=2` nel `.env` (alla fine togliere le due righe o rimettere `20` e `6`):

32. `Mi chiamo Luca`: nel log `riassunto non necessario messaggi=1 soglia=4` e nessuna chiamata
    in più al modello.
33. `Che ore sono?`: di nuovo `riassunto non necessario ...` (anche con `da_togliere=0`, se il
    primo turno ha avuto una revisione), poi l'ora.
34. `Quanto fa 12 per 3?`: `Inizio chiamata al riassunto (...)` e
    `riassunto messaggi prima=... dopo=...`, poi il giro di `calcola`.
35. `Come mi chiamo?`: la risposta contiene «Luca» anche se il primo turno è stato riassunto.
36. `Che tempo fa a Pordenone?`: `meteo_citta` con `execution=ok` dopo la compressione (il taglio
    non ha rotto i giri degli strumenti).
37. LM Studio fermo, poi una domanda: `Connessione fallita: ...`, la sessione continua; riacceso
    il server, la domanda successiva riceve risposta.
38. `esci` → `Arrivederci.`

Per lo step 3 in Docker si verifica ancora solo che l'applicazione non si rompa: `docker
compose build` e avvio del container fino a `Tu> `.

Preferenze (lezione 6, step 4), in locale; dopo ogni modifica del file chiudere con `esci` e
riavviare `python -m assistente`. Se all'inizio esiste già un `archivio\preferenze.json`, copiarne
prima il contenuto e rimetterlo alla fine.

39. Senza `archivio\preferenze.json`: prima di `Tu> ` la riga `WARNING
    assistente.collegamento_mcp: preferenze non disponibili (...): valori predefiniti
    lingua=italiano fuso=<FUSO_ORARIO> stile=sintetico`; la sessione parte. `Che ore sono?`: nei
    log `variant=local tool=ora_corrente` con il risultato nel fuso di `FUSO_ORARIO`.
40. Creare il file con `America/New_York` (comandi della sezione «Preferenze dell'utente»):
    prima di `Tu> ` una sola riga `preferenze lette uri=utente://preferenze lingua=italiano
    fuso=America/New_York stile=sintetico`. `Che ore sono?`: il modello non chiede il fuso, nei
    log `variant=local tool=ora_corrente ... result=...(America/New_York)` e la risposta riporta
    l'ora di New York.
41. Nei log la riga `preferenze lette ...` compare una volta sola, prima della prima domanda,
    distinta dalle righe `variant=...` degli strumenti; la riga `discovery ... tools=[...]` non
    contiene le preferenze.
42. Nel file `lingua` `inglese` e `stile` `dettagliato`: dopo il riavvio la riga `preferenze
    lette ...` riporta i nuovi valori; `Cosa sai fare?` riceve una risposta in inglese, più
    lunga e articolata di quella con `sintetico`. Il codice non è stato modificato.
43. Nel file uno stile non ammesso (per esempio `lungo`): `WARNING ... preferenze non disponibili
    (stile deve essere 'sintetico' o 'dettagliato', non 'lungo') ...`, la sessione parte con i
    predefiniti.
44. `esci` → `Arrivederci.`; alla fine rimettere il file com'era (o eliminarlo con
    `Remove-Item archivio\preferenze.json`).

Per lo step 4 in Docker: `docker compose build` e avvio del container fino a `Tu> `, con la riga
`preferenze lette ...` (o `preferenze non disponibili (...)`, senza file) nei log del container.

Prompt MCP (lezione 6, step 5), in locale, con l'ambito allargato nel `.env` (vedi
«Configurazione»):

45. `/prompts`: l'elenco dei due prompt con argomenti e descrizioni (sezione «Prompt MCP e
    comandi della CLI»); nei log `prompts/list prompts=['spiega', 'riassumi_conversazione']` e
    nessuna riga `router` o `Inizio chiamata al modello`.
46. `/prompt spiega livello=base`: `Argomenti obbligatori mancanti per 'spiega': argomento.`;
    nei log `WARNING ... prompt rifiutato nome=spiega ...` e nessuna riga `prompt richiamato`,
    `router` o `variant=`.
47. `/prompt spiega argomento=MCP colore=blu`: `Argomenti sconosciuti per 'spiega': colore.
    Argomenti ammessi: argomento, livello.`; come sopra, nessuna riga del grafo.
48. `/prompt inesistente`: `Prompt sconosciuto: 'inesistente'. Prompt disponibili: spiega,
    riassumi_conversazione.`; nessuna riga del grafo.
49. `/prompt spiega argomento="Model Context Protocol" livello=base`: nei log `prompt richiamato
    ...`, `prompt messaggi ottenuti numero=1 [user] Spiegami «Model Context Protocol» ...`,
    `router categoria=conversazione` e `revisore coerente=...`; la risposta è adatta al livello
    base (parole semplici, un esempio concreto).
50. `Mi chiamo Luca`, `Quanto fa 45 diviso 9?`, poi `/prompt riassumi_conversazione`: il
    riassunto cita Luca e il risultato 5 e non aggiunge informazioni nuove.
51. `/prompt riassumi_conversazione stile=dettagliato` con lo stile `sintetico` nelle preferenze:
    annotare quale dei due prevale.
52. `esci` → `Arrivederci.`

Per lo step 5 in Docker: `docker compose build`, avvio del container fino a `Tu> `, poi
`/prompts` e `/prompt spiega argomento="Model Context Protocol" livello=base` nel container.

## Diagnosi

Problemi dell'applicazione e del modello:

| Sintomo | Cosa controllare |
|---|---|
| `Configurazione non valida: ...` all'avvio | il `.env` nella cartella da cui si avvia e le variabili indicate |
| `Configurazione non valida: variabili mancanti: AMBITO_AGENTE` | un `.env` creato prima della lezione 6: aggiungere la riga `AMBITO_AGENTE=...` di `.env.example` |
| domanda dell'ambito rifiutata (`router categoria=fuori ambito`) o domanda estranea passata all'agente | il motivo nella riga `router ...` del log; correggere il prompt del router in `assistente/router.py` (non il modello) e ripetere le prove reali |
| `Configurazione non valida: MAX_REVISIONI deve essere un intero maggiore di zero, non '...'` | il valore di `MAX_REVISIONI` nel `.env` (oppure togliere la riga per usare il default `2`) |
| risposte buone rimandate all'agente (`revisore coerente=no` con un motivo sbagliato) o risposte incomplete approvate | il motivo nella riga `revisore ...` del log; se fa fallire le prove, correggere il prompt del revisore in `assistente/revisore.py` (non il modello) e ripetere le prove reali; il limite `MAX_REVISIONI` impedisce comunque giri infiniti |
| `Configurazione non valida: SOGLIA_RIASSUNTO deve essere un intero maggiore di zero, non '...'` (o lo stesso per `MESSAGGI_DA_TENERE`) | il valore nel `.env` (oppure togliere la riga per usare il default `20` o `6`) |
| `Configurazione non valida: MESSAGGI_DA_TENERE (<n>) deve essere minore di SOGLIA_RIASSUNTO (<s>)` | i due valori nel `.env`: i messaggi da tenere devono essere meno della soglia |
| dopo un riassunto l'assistente non ricorda il nome o un'informazione data all'inizio | con `LOG_LEVEL=DEBUG` la riga `riassunto testo=...`: se l'informazione manca, correggere il prompt in `prompt_riassunto` (`assistente/riassunto.py`), non il modello; se c'è ma l'agente non la usa, l'intestazione del paragrafo in `sistema_con_riassunto` (vedi esiti dello step 3); poi ripetere le prove reali |
| `WARNING ... preferenze non disponibili (Error reading resource ... No such file or directory ...)` | il file `archivio\preferenze.json` non esiste nella cartella da cui si avvia l'applicazione: crearlo (sezione «Preferenze dell'utente») oppure accettare i predefiniti |
| `WARNING ... preferenze non disponibili (Error reading resource ... 'utf-8' codec can't decode byte ...)` | il file non è in UTF-8: `0xff in position 0` se è stato scritto con `echo ... >` o `Out-File` (in Windows PowerShell 5.1 salvano in UTF-16), un altro byte (es. `0xe7`) se è stato scritto con `Set-Content` senza `-Encoding` e contiene lettere accentate; riscriverlo con il comando `Set-Content ... -Encoding utf8` della sezione «Preferenze dell'utente» |
| `WARNING ... preferenze non disponibili (JSON non valido (...))` | virgolette, virgole e parentesi del file; le chiavi e i testi vanno tra virgolette doppie |
| `WARNING ... preferenze non disponibili (manca la chiave '...')` / `(fuso_orario non valido: '...')` / `(stile deve essere ...)` / `(lingua non valida: ...)` | la chiave o il valore indicati nel file (fuso con nome IANA, es. `Europe/Rome`; stile `sintetico` o `dettagliato`) |
| le preferenze modificate non hanno effetto | si leggono solo all'avvio: chiudere con `esci` e riavviare; controllare i valori nella riga `preferenze lette ...` |
| un comando `/prompt` riceve un messaggio come `Argomenti obbligatori mancanti ...`, `Argomenti sconosciuti ...` o `Prompt sconosciuto ...` | il comando è stato bloccato dall'applicazione prima del modello (nei log `WARNING ... prompt rifiutato ...`): correggere nome e argomenti confrontandoli con `/prompts` |
| `Comando non valido: virgolette non chiuse ...` o `Argomento non valido: ...` | la scrittura del comando: valori con spazi o apostrofi tra virgolette doppie, barre rovesciate tra apici singoli (sezione «Prompt MCP e comandi della CLI») |
| `Server MCP non disponibile: ...` dopo `/prompts` o `/prompt`, a sessione avviata | il server MCP non è partito per quel comando: la chat continua; provare la discovery senza modello e ripetere il comando |
| `/prompt spiega ...` riceve il rifiuto `Questa domanda è fuori dal mio ambito ...` | `AMBITO_AGENTE` nel `.env` senza `concetti del corso (LLM, agenti, MCP)` (vedi «Configurazione»); il motivo nella riga `router ...` del log |
| l'agente risponde in una lingua o con uno stile diversi da quelli del file, con la riga `preferenze lette ...` corretta | limite del modello: il paragrafo delle preferenze è in cima al prompt (`prompt_agente` in `assistente/preferenze.py`); vedi gli esiti delle prove reali |
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

### Lezione 6 — step 5, prompt (2026-11-15 e 2026-11-16)

Eseguite sul branch `feat/prompt` con `google/gemma-4-e2b` in LM Studio, senza
`archivio\preferenze.json` (valori predefiniti, stile `sintetico`).

- Test automatici: 423 superati, 17 saltati (le prove reali, 2 nuove in questo step).
- Prima serie reale completa (testo di `spiega` sui tre livelli, ambito allungato con i concetti
  del corso, router senza esempi nuovi): **16 superate, 1 fallita**. Passano le due prove nuove
  (`test_prompt_spiega`, `test_prompt_riassumi_conversazione`); fallisce
  `test_domanda_in_due_parti` (step 2): il router respinge «Che ore sono e che tempo fa a
  Pordenone?» come fuori ambito.
- Diagnosi dell'ambito (variabile solo nel processo delle prove, `.env` non toccato): senza i
  concetti del corso la domanda composta passa (6 su 6) ma il router respinge `spiega` (0 su 3);
  con i concetti del corso, in tre formulazioni diverse, passa `spiega` e non la domanda composta
  (0 su 10). Con la sola configurazione non passavano mai entrambe.
- Strada C (decisa dall'utente, scostamento 3 del piano): due esempi in più nel prompt del router
  (`«Che ore sono e piove a Udine?»` e `«Spiegami cos'è un agente»` → `conversazione`). Serie
  completa con gli esempi: **15 superate, 2 fallite** (domanda composta; `test_durata_corso_usa_cerca_e_dettaglio`,
  che ripetuta 3 volte con i log passa 3 su 3).
- Testo di `spiega` (scostamento 4 del piano): con la frase sui tre livelli il revisore diceva,
  10 volte su 10, che la risposta spiegava l'argomento a tutti e tre i livelli. Ora il testo
  descrive solo il livello richiesto; prova mirata 3 su 3, risposte lette: livello base, parole
  semplici, un esempio concreto.
- Revisione indipendente del branch: «con correzioni», nessun problema critico, nessun difetto
  nuovo negli step 1–4; l'unico punto importante era la chiusura dello step (queste prove). Minori
  non corrette (decide l'utente):
  - un valore di soli spazi (`argomento=" "`) passa e arriva al modello;
  - `livello=Base` o `BASE` perde la frase del livello (il confronto distingue le maiuscole);
  - `ErroreComandoPrompt` è riconosciuto solo se è la prima eccezione dell'`ExceptionGroup`;
  - l'esempio del router «Che ore sono e piove a Udine?» ha la stessa forma della prova reale della
    domanda composta, che quindi dimostra meno;
  - `argomento=C:\dati` senza apici diventa `C:dati`: documentato, ma senza un test;
  - (dalla prova manuale 50) `test_prompt_riassumi_conversazione` cerca `5` nella risposta, ma lo
    trova anche nel «45» della domanda: non dimostra che il riassunto riporti il risultato.
- Serie reale completa finale (testo nuovo di `spiega` ed esempi del router): **16 superate,
  1 fallita**. Passano le due prove dello step 5, la domanda composta (con gli esempi in tutto
  3 volte su 5) e la prova del corso. Fallisce `test_nome_usato_dopo_la_compressione` (step 3, già
  instabile): «Come mi chiamo?» → «Mi chiamo assistente del laboratorio.»; nella stessa prova il
  router respinge un calcolo (limite noto dello step 1).
- Prove manuali in locale (voci 45–52), 2026-11-16:
  - 45: `/prompts` stampa la riga `prompts/list prompts=['spiega', 'riassumi_conversazione']` e
    l'elenco di cinque righe; nessuna riga del router né del modello;
  - 46–48: i tre errori con i messaggi della sezione «Prompt MCP e comandi della CLI», ciascuno con
    `WARNING ... prompt rifiutato nome=... motivo=...`; nessuna riga `prompt richiamato`, `router`
    o `variant=`;
  - 49: `prompt richiamato nome=spiega argomenti={"argomento": "Model Context Protocol",
    "livello": "base"}`, `prompt messaggi ottenuti numero=1 [user] Spiegami «Model Context
    Protocol» a livello base. Usa parole semplici, ...`, poi `router categoria=conversazione` e
    `revisore coerente=sì` al primo giro; risposta di livello base con un esempio concreto;
  - 50: dopo «Mi chiamo Luca» e «quanto fa 45 diviso 9?» (`tool=calcola`, `result=5`), il riassunto
    sintetico elenca i tre turni e cita Luca, ma riporta solo le domande: il risultato 5 non c'è;
  - 51: con `stile=dettagliato` e lo stile `sintetico` delle preferenze **prevale `dettagliato`**:
    sei punti con domande e risposte, compreso il 5;
  - 52: `esci` → `Arrivederci.`.
- Docker, 2026-11-16: `docker compose run --rm --name assistente-demo assistente` elenca i dieci
  strumenti, stampa il WARNING delle preferenze (con il traceback del server, vedi «Preferenze
  dell'utente») e arriva a `Tu> `; `/prompts` stampa lo stesso elenco (sul server
  `ListPromptsRequest`); `/prompt spiega argomento="Model Context Protocol" livello=base`, due
  volte, ha le stesse righe di log della voce 49 (sul server `GetPromptRequest`) e risposte di
  livello base; `esci` → `Arrivederci.`. L'output di `docker compose build` non è stato
  registrato; l'immagine usata contiene il testo nuovo di `spiega`.
- Limiti osservati e non corretti in questo step:
  - **Router (step 1) e domanda composta.** Anche con gli esempi, «Che ore sono e che tempo fa a
    Pordenone?» passa solo 3 volte su 5.
  - **Corso.** `test_durata_corso_usa_cerca_e_dettaglio` è fallita 1 volta su 5 con gli esempi del router (nessuno
    strumento eseguito; log non catturati in quell'esecuzione).
  - **Riassunto (step 3).** `test_nome_usato_dopo_la_compressione` resta instabile.
  - **MCP descritto in modo inesatto.** `gemma-4-e2b` rispetta il livello, ma descrive MCP come
    «il contesto dato al modello», non come un protocollo per collegare il modello a strumenti e
    dati.
  - **Riassunto sintetico.** Con `riassumi_conversazione` in stile sintetico il modello può
    elencare solo le domande, senza le risposte.

### Lezione 6 — step 4, preferenze (2026-11-15)

Eseguite il 2026-11-15 sul branch `feat/preferenze` con `google/gemma-4-e2b` in LM Studio.
Durante le prove automatiche non c'era un `archivio\preferenze.json`: le prove diverse da quelle
delle preferenze sono partite con i valori predefiniti.

- Test automatici: 362 superati, 15 saltati (le prove reali). Erano 348 prima delle correzioni
  della revisione indipendente (vedi sotto).
- Prove reali automatiche, serie completa prima della revisione
  (`$env:PROVE_REALI = "1"; python -m pytest -m reale -v; Remove-Item Env:PROVE_REALI`):
  **14 superate, 1 fallita** in circa 16 minuti. Passano le due prove nuove
  (`test_ora_nel_fuso_delle_preferenze` e `test_preferenze_assenti_usano_il_fuso_del_env`).
  Fallisce `test_nome_usato_dopo_la_compressione` (step 3): al terzo turno («Quanto fa 12 per
  3?»), dopo il riassunto (`riassunto messaggi prima=9 dopo=5 caratteri=24`), la chiamata al
  router va in timeout (`Attesa scaduta`). Il router non riceve le preferenze. La stessa prova
  ripetuta da sola passa (circa 5 minuti): è quindi **instabile**, e non è corretta in questo step.
- Revisione indipendente del branch: esito «con correzioni», nessun problema critico o
  importante, otto minori:
  - M1: la lingua accettava caratteri non stampabili (` `, `\x0b`, `\x85`, surrogati);
  - M2: su Windows `ZoneInfo` accettava fusi come `"Europe/Rome "` o `"Europe/Rome."`; ora il fuso
    deve essere nell'elenco IANA;
  - M3: un JSON annidato troppo in profondità fermava l'avvio (`RecursionError`);
  - M4: mancava in «Diagnosi» il caso del file non in UTF-8;
  - M5: nessun test su che cosa `main()` passa a `bind_tools`;
  - M6: la fixture delle prove reali teneva il file originale solo in memoria (ora copia
    `archivio\preferenze.json.bak` su disco);
  - M7: commenti non aggiornati;
  - M8: la prova reale non verifica che il modello non chieda il fuso.

  M1–M7 corretti con TDD; M8 verificato nella prova manuale 40.
- Dopo le correzioni, le due prove delle preferenze
  (`python -m pytest -m reale -v -k preferenze`, con `PROVE_REALI=1`): **2 superate su 2**. La
  serie completa non è stata ripetuta.
- Prove manuali in locale (voci 39–44):
  - 39: senza file, `WARNING ... preferenze non disponibili (...)` prima di `Tu> `; `ora_corrente`
    con risultato `...+01:00 (Europe/Rome)`;
  - 40–41: con `America/New_York` una sola riga `preferenze lette ... fuso=America/New_York ...`
    prima di `Tu> `, la riga `discovery ...` senza preferenze; `ora_corrente` con
    `result=2026-11-15T12:00:04-05:00 (America/New_York)`, il modello non chiede il fuso,
    risposta «L'ora attuale è 12:00:04 nel fuso orario America/New_York.»;
  - 42: con `lingua` `inglese` e `stile` `dettagliato`, «Cosa sai fare?» riceve una risposta in
    inglese, lunga, con gli strumenti divisi per gruppi; il codice non è stato modificato;
  - 43: con lo stile `lungo`, `WARNING ... preferenze non disponibili (stile deve essere
    'sintetico' o 'dettagliato', non 'lungo'): valori predefiniti lingua=italiano
    fuso=Europe/Rome stile=sintetico`, nessun traceback, la sessione parte;
  - 44: `esci` → `Arrivederci.`; file tolto.
- Docker: `docker compose build` riuscito; con il file (`America/New_York`) montato,
  `docker compose run --rm --name assistente-demo assistente` elenca i dieci strumenti, stampa
  una sola riga `preferenze lette uri=utente://preferenze lingua=italiano fuso=America/New_York
  stile=sintetico` prima di `Tu> ` (la stessa in `docker logs assistente-demo`) ed `esci` stampa
  `Arrivederci.`. Nel container non sono state fatte domande al modello.
- Limiti osservati e non corretti in questo step:
  - **Riassunto (step 3).** `test_nome_usato_dopo_la_compressione` è instabile: timeout del
    router dopo il riassunto, una volta su due.
  - **Revisore (step 2) e preferenze.** Il revisore non riceve le preferenze (scelta della
    specifica): nella prova 40 ha bocciato due volte la risposta con l'ora di New York
    («fornisce un orario specifico in un fuso orario», poi «spiega come si ottiene») e l'ha
    approvata la terza.
  - **`FUSO_ORARIO` (lezione 4).** Secondo la revisione ha su Windows la stessa debolezza
    corretta in M2 per le preferenze (`ZoneInfo` accetta valori come `"Europe/Rome "`); non
    verificato né corretto in questo step.
- Coperti solo dai test automatici: i file non validi diversi dallo stile (JSON non valido o
  troppo annidato, chiave mancante, fuso o lingua non validi) e la copia `.bak` lasciata da una
  serie di prove reali interrotta.

### Lezione 6 — step 3, riassunto (2026-11-13 e 2026-11-15)

Eseguite il 2026-11-13 e il 2026-11-15 sul branch `feat/riassunto` con `google/gemma-4-e2b` in
LM Studio (`MAX_PASSI=5`, `MAX_REVISIONI=2`; la prova del riassunto imposta da sé
`SOGLIA_RIASSUNTO=4` e `MESSAGGI_DA_TENERE=2`).

- Test automatici: 300 superati, 13 saltati (le prove reali). Erano 297 prima della revisione
  indipendente e della correzione del prompt del 2026-11-15 (vedi in fondo a questa sezione).
- Prove reali automatiche, prima serie
  (`$env:PROVE_REALI = "1"; .\.venv\Scripts\python.exe -m pytest -m reale -v -o log_cli=true --log-cli-level=INFO; Remove-Item Env:PROVE_REALI`):
  **12 superate, 1 fallita**. Le dodici prove precedenti passano con il nodo riassunto (con la
  soglia predefinita non riassumono mai). Fallisce la prova del nome: compressioni avvenute
  (`riassunto messaggi prima=9 dopo=5 caratteri=24`, poi `prima=11 dopo=7 caratteri=134`), primo
  turno tolto dalla cronologia, ma risposta «Non mi hai detto come ti chiami.». La stessa prova
  ripetuta da sola fallisce allo stesso modo.
- Diagnosi (script temporanei, non nel progetto, che stampano il riassunto dopo ogni turno e
  chiamano l'agente direttamente):
  - il riassunto **contiene** il nome («L'utente si chiama Luca.», poi «L'utente si chiama
    Luca. L'utente ha chiesto l'ora, ...»): il prompt del riassunto non è la causa;
  - in tutte le esecuzioni fallite il turno «Quanto fa 12 per 3?», rimasto tra i messaggi
    tenuti, conteneva una revisione sbagliata del revisore («12 diviso 3 fa 4», il caso già
    visto nello step 2) seguita da «Mi scuso per l'errore.»;
  - chiamando l'agente con il riassunto nel messaggio di sistema e «Come mi chiamo?»: con
    l'intestazione iniziale `Riassunto della conversazione precedente:` il nome è usato 3 volte
    su 3 dopo un turno pulito e 2 su 3 dopo il turno con la revisione sbagliata; con
    l'intestazione `Cosa sai già della conversazione con l'utente (usalo per rispondere):` 3 su 3
    in entrambi i casi.
- Correzione (decisa dall'utente): nuova intestazione del paragrafo del riassunto in
  `sistema_con_riassunto`; il prompt del riassunto e il modello non cambiano.
- Prove reali automatiche, seconda serie completa dopo la correzione (stesso comando):
  **13 superate su 13**. Nella prova del nome il revisore ha di nuovo bocciato per errore il
  calcolo, ma la risposta finale contiene «Luca»; righe osservate:
  `riassunto non necessario messaggi=1 soglia=4`,
  `riassunto non necessario messaggi=7 soglia=4 da_togliere=0` (primo turno con due revisioni:
  niente da togliere), `riassunto messaggi prima=11 dopo=5 caratteri=24`,
  `riassunto messaggi prima=11 dopo=7 caratteri=134`.
  In entrambe le serie il router, alla domanda «Quanto fa 12 per 3?» dopo la compressione, ha
  esaurito i token (`router risposta non valida (... length limit was reached ...)`) e la domanda
  è passata all'agente come previsto dallo step 1.
- Docker: `docker compose build` riuscito.
- Revisione indipendente del branch (2026-11-15): nessun problema Critical, un solo Important
  (il merge richiedeva ancora le prove manuali e l'avvio Docker), tre Minor sui test (errore alla
  seconda compressione, controlli sulle due compressioni di seguito, invariante del taglio con
  indicazioni), corretti con TDD.
- Prove manuali (2026-11-15, `SOGLIA_RIASSUNTO=4`, `MESSAGGI_DA_TENERE=2`, voci 32–38):
  - 32–34: `riassunto non necessario messaggi=1 soglia=4`; `riassunto non necessario messaggi=5
    soglia=4 da_togliere=0` (primo turno con una revisione, niente da togliere); poi
    `Inizio chiamata al riassunto (messaggi=9 soglia=4 da_togliere=4)` e
    `riassunto messaggi prima=9 dopo=5 caratteri=24`, con `calcola` `execution=ok result=36`;
  - 35: nella prima prova il riassunto conteneva il nome, ma la risposta è stata «Non posso dirti
    come ti chiami...» (compressione `prima=11 dopo=7 caratteri=130`); nella seconda, con il log
    `DEBUG`, il riassunto conteneva «L'utente si chiama Luca.» e la risposta è stata «Mi chiamo
    Luca.», cioè il nome è usato ma riferito all'assistente; nella terza «Ti chiami Luca.»;
  - 36: `meteo_citta` con `execution=ok` dopo la compressione;
  - 37: con LM Studio fermo `Connessione fallita: controllare LM Studio, URL e porta.` e la sessione
    continua; la stessa domanda dopo la riaccensione riparte con gli stessi numeri
    (`messaggi=9 soglia=4 da_togliere=2`), quindi nulla è cambiato; 38: `Arrivederci.`.
- Difetti osservati e non corretti in questo step (decisione dell'utente):
  - **Ora vecchia ripetuta.** Il riassunto riportava «ora sono le 13:27:37» e, alla domanda
    successiva sull'ora, l'agente ha risposto 13:27 senza chiamare `ora_corrente`. Correzione:
    `prompt_riassunto` ora chiede di non riportare i valori che cambiano nel tempo (ora, data,
    meteo) e di scrivere solo che l'utente li ha chiesti (commit `fix(riassunto)`, un test sul
    testo del prompt). Il modello **non rispetta sempre l'istruzione**: nella verifica manuale
    successiva il riassunto conteneva ancora «14:50:44» (`DEBUG riassunto testo=...`), anche se
    in quella prova l'agente ha richiamato `ora_corrente` e ha dato l'ora giusta (14:57:23). È
    quindi un limite noto di `gemma-4-e2b`, non risolto: nel caso peggiore l'agente ripete un'ora
    o un meteo vecchi.
  - **Revisore (step 2, M4).** «12 per 3» e «1234 per 5678» a volte sono letti come divisioni: il
    revisore boccia un risultato corretto e l'agente lo «corregge» in modo sbagliato (visto anche
    nel riassunto: «12 diviso 3 è 4»).
  - **Router (step 1).** In una prova manuale «Quanto fa 12 per 3?» è stato respinto come fuori
    ambito, in un'altra il router ha esaurito i token e la domanda è passata all'agente.
- Serie reali dopo la correzione del prompt del 2026-11-15 (stesso comando, `.env` con i valori
  predefiniti): prima serie **12 superate, 1 fallita** (`test_calcolo_usa_calcola`: risposta
  «divisione, circa 0.2164», difetto M4 del revisore su una conversazione di un solo turno,
  sotto la soglia: il riassunto non c'entra); seconda serie, senza altre modifiche, **13
  superate su 13**. La prova di calcolo è quindi instabile per colpa del revisore.
- Docker (2026-11-15): `docker compose run --rm --name assistente-demo assistente` avvia il
  container, la discovery elenca i dieci strumenti (`discovery server=assistente.server_mcp
  tools=[...]`), compare `Tu> `, `esci` stampa `Arrivederci.`. Nel container non sono state fatte
  domande al modello.
- Coperti solo dai test automatici: il riassunto vuoto. Non provata la correzione dell'ora oltre
  alle due prove manuali sopra.

### Lezione 6 — step 2, revisore (2026-11-13)

Eseguite il 2026-11-13 sul branch `feat/revisore` con `google/gemma-4-e2b` in LM Studio
(`MAX_PASSI=5`, `MAX_REVISIONI=2`).

- Test automatici: 266 superati, 12 saltati (le prove reali).
- Prove reali automatiche, una sola serie con il prompt iniziale del revisore: **12 superate su
  12**. Righe del revisore osservate:
  - «Che ore sono e che tempo fa a Pordenone?»: `ora_corrente` e `meteo_citta`, poi
    `revisore coerente=sì` al primo passaggio (nel grafo intero gemma ha risposto
    completamente subito, nessuna correzione);
  - il revisore chiamato da solo davanti alla risposta parziale «Sono le 10:30.»: `coerente=no`
    con un motivo (evidenza minima del PDF con il modello vero);
  - «Quanto fa 1234 per 5678?»: `calcola` → `7006652`, poi due rifiuti del revisore (il primo
    con un motivo sbagliato, «la domanda chiede una divisione»), `revisione=2/2` e terzo
    tentativo approvato; la prova passa (`calcola` usato una volta, `7006652` nella risposta);
  - «Ricordami di consegnare il report venerdì»: un rifiuto («non fornisce il promemoria
    richiesto, ma conferma un'azione di salvataggio»), poi approvata;
  - tutte le altre: `coerente=sì` al primo passaggio; nessuno strumento ripetuto.
  Le revisioni superflue con gemma non fanno fallire le prove: per decisione dell'utente il
  prompt del revisore resta invariato e il caso è registrato qui.
- Prove manuali (voci 26–31), in una sola sessione con `.\.venv\Scripts\python.exe -m assistente`,
  tutte superate:
  - «Che ore sono?»: `ora_corrente`, `revisore coerente=sì` (voce 26);
  - «Che ore sono e che tempo fa a Pordenone?»: due strumenti nello stesso passo,
    `revisore coerente=sì motivo=La risposta risponde a entrambe le parti della domanda.` (voce 27);
  - «Mi chiamo Luca» / «Come mi chiamo?»: la prima bozza è rifiutata
    (`coerente=no motivo=La risposta non fornisce il nome dell'utente. next_node=llm (agente)
    revisione=1/2`), l'agente riparte da `passo 1/5` e la risposta approvata contiene «Sei
    Luca.» (voce 28). È una correzione dopo la revisione entro il limite; la risposta finale è
    però goffa («Mi chiamo assistente del laboratorio. ... Sei Luca.») e il testo della bozza
    rifiutata non compare né a schermo né nel log;
  - «Che tempo fa a Pordenone?» / «E domani?»: la seconda è approvata
    (`motivo=La risposta risponde al contesto della domanda, anche se non fornisce
    l'informazione richiesta.`); l'agente non ha chiamato lo strumento e ha risposto «Non ho
    informazioni sul meteo per domani» (voce 29);
  - «Raccontami la storia di Roma»: rifiuto del router, nessuna riga `revisore` (voce 30);
  - server di LM Studio fermo: `Connessione fallita: ...` già alla chiamata del router, poi di
    nuovo `Tu> `; dopo il riavvio «Che ore sono?» risponde con `revisore coerente=sì` (voce 31);
    `esci` → `Arrivederci.`
- Docker: `docker compose build` riuscito; `docker compose run --rm --name assistente-demo
  assistente` → discovery dei 10 strumenti, `Tu> `, `esci` → `Arrivederci.`
- Non provate con il modello vero: la caduta di LM Studio proprio durante la chiamata al
  revisore e l'avviso `limite di revisioni raggiunto` (nessuna risposta è stata rifiutata tre
  volte: entrambi coperti solo dai test automatici); le altre voci della checklist dentro Docker.

### Lezione 6 — step 1, router (2026-11-13)

Eseguite il 2026-11-13 sul branch `feat/router` con `google/gemma-4-e2b` in LM Studio.

- Test automatici: 233 superati, 9 saltati (le prove reali); dopo la correzione della revisione finale (risposta del router troncata o filtrata → agente) 235 superati, 9 saltati.
- Prove reali automatiche, prima serie (prompt iniziale del router): **5 superate, 4 fallite**.
  Calcolo, conversione, corso e meteo non hanno usato strumenti perché il router li ha
  classificati `fuori ambito`, con motivi come «Non ho accesso a informazioni meteo in tempo
  reale» e «richiede una conversione di unità… che non rientra nell'ambito»: gemma giudicava se
  sapeva rispondere invece dell'argomento. Ora, giorni lavorativi, nota, «Ciao, come stai?» e
  la domanda fuori ambito superate.
- Correzione del solo prompt del router (il modello resta gemma): valutare solo l'argomento,
  «in caso di dubbio conversazione», esempi diversi dalle domande delle prove. Verifica del
  solo router su 20 domande (tabella 4.1 della specifica e domande delle prove): 19/20, con
  «Parlami di Forlì e del caffè» classificata `conversazione`; dopo una seconda correzione
  (città, luoghi, cibo e richieste di parlare di un tema generale sono fuori ambito) 20/20.
- Prove reali automatiche, seconda serie completa dopo l'ultima correzione: **9 superate su 9**.
- Prove reali automatiche, terza serie dopo la correzione della revisione finale (risposta
  troncata o filtrata → agente): **9 superate su 9**.
- Prove manuali (voci 21–25), in una sola sessione con `.\.venv\Scripts\python.exe -m assistente`,
  tutte superate:
  - «Che ore sono?»: `router categoria=conversazione ... next_node=llm (agente)`, poi
    `ora_corrente` con `variant=local` e l'ora (voce 21);
  - «Raccontami la storia di Roma»: `router categoria=fuori ambito ... next_node=rifiuto`,
    `rifiuto inviato, nodo agente non eseguito`, il rifiuto fisso e nessuna riga
    `Inizio chiamata al modello` (voce 22);
  - «Mi chiamo Luca» / «Come mi chiamo?»: entrambe `conversazione`, risposta «Ti sei
    presentato come Luca.» (voce 23);
  - «Cosa sai fare?»: `conversazione` e risposta dell'agente (voce 24);
  - server di LM Studio fermo: `Connessione fallita: controllare LM Studio, URL e porta.` già
    alla chiamata del router, poi di nuovo `Tu> `; dopo il riavvio «Che ore sono?» risponde
    (voce 25); `esci` → `Arrivederci.`
- Docker: `docker compose build` riuscito; `docker compose run --rm --name assistente-demo
  assistente` → discovery dei 10 strumenti, `Tu> `, `esci` → `Arrivederci.`
- Non provate: le altre voci della checklist dentro Docker (per lo step 1 il PDF chiede solo la
  prova reale con LM Studio).

### Lezione 5 — verifica complessiva (2026-11-11)

Eseguita il 2026-11-11 sul branch `dev` con `google/gemma-4-e2b` in LM Studio.

- Test automatici: 211 superati, 8 saltati (le prove reali).
- `docker compose build` e discovery nel container: i 10 strumenti, da `calcola` a
  `meteo_citta`.
- Checklist in **una sola sessione** con Docker Compose (voci 1–16, 18, 19 e Ctrl+C).
  - La sessione è stata pilotata da uno script: le domande arrivano da stdin una alla volta,
    dopo il prompt `Tu> `, e i log sono letti sull'output del comando.
  - LM Studio è stato fermato e riavviato con `lms server stop` / `lms server start`.
  - Il Ctrl+C è stato inviato come SIGINT (`docker kill --signal=SIGINT assistente-demo`)
    mentre si attendeva la risposta del modello.
  - Superate:
    - domanda ordinaria senza strumenti (voce 1);
    - orologio con `variant=local` (voce 2);
    - `calcola` con `1234 * 5678` → 7.006.652 (voce 3);
    - «Mi chiamo Luca» / «Come mi chiamo?» (voce 5);
    - LM Studio fermo, con `Connessione fallita: ...`, e dopo il riavvio «Ti chiami Luca.»,
      quindi la cronologia è conservata (voce 6);
    - accenti (voce 7);
    - Ctrl+C con «Arrivederci.» (voce 8);
    - `converti_unita` (voce 9);
    - `aggiungi_giorni_lavorativi` → `2027-01-05` (voce 12);
    - `cerca_corsi` con «astronautica» (voce 14);
    - una sola `aggiungi_nota` (voce 15);
    - `meteo_citta` per Pordenone (voce 18).
  - Come già osservato, con `abs(3)` (voce 4) e «Converti 5 metri in chilogrammi» (voce 10)
    gemma non chiama lo strumento e non inventa risultati.
  - **Fallite** nella sessione unica, verso la fine di una cronologia di 15–19 turni:
    - voce 11: `conta_giorni` chiamato correttamente, con `execution=ok` e 2 giorni lavorativi,
      ma gemma ignora il risultato, risponde che il calcolo «è complesso» e chiede le date;
    - voce 13: nessuno strumento chiamato, gemma chiede se deve cercare i corsi;
    - voce 16: nessuno strumento chiamato, gemma chiede conferma prima di eliminare la nota 99.
      Nessuna nota è stata eliminata;
    - voce 19: nessuno strumento chiamato per «Valbruniforte», risposta «Non ho informazioni
      sul meteo», senza dati inventati.
- Voce 17, in un nuovo container: `elenca_note` con `arguments={}` mostra la nota salvata nella
  sessione precedente. La chiusura con `esci` dà «Arrivederci.».
- Diagnosi dei fallimenti, con una sola ipotesi: la cronologia lunga. Le quattro domande
  fallite, poste come prima domanda di una sessione nuova in locale, riescono 3 volte su 3
  ciascuna (12 su 12), con gli strumenti e le risposte attesi. Gli strumenti e il collegamento
  MCP funzionano: con una cronologia lunga gemma-4-e2b smette di usare gli strumenti o di
  leggerne il risultato. Nessuna correzione applicata.
- Dopo le prove `archivio\note.sqlite` è stato eliminato.
- Voce 20 (meteo con la rete scollegata): non inclusa nella sessione unica, eseguita a parte
  lo stesso giorno e superata (vedi «Lezione 5 — meteo»).
- Non eseguiti:
  - la sessione unica in locale, che è stata fatta solo in Docker;
  - il Ctrl+C in locale (provato a mano il 2026-10-28).

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
- Voce 20, rete scollegata (Wi-Fi spento, LM Studio acceso), eseguita più tardi lo stesso
  giorno. Le domande sono state passate da uno script che aspetta la caduta della rete e dà un
  tempo massimo a ogni prova:
  - in locale e in Docker gemma chiama `meteo_citta` con `{"citta": "Pordenone"}`;
  - nei log compare `execution=tool_error` con `Servizio meteo non raggiungibile: controlla la
    connessione.`, distinto da «Città non trovata»;
  - gemma risponde «Mi dispiace, non sono riuscito a recuperare le informazioni sul tempo per
    Pordenone. C'è stato un errore con il servizio meteo.», senza dati inventati;
  - l'invocazione diretta dà lo stesso errore.
- Non provati in questo task:
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
- In una sessione lunga (15–19 turni) gemma-4-e2b a volte non chiama lo strumento giusto o
  ignora il risultato ricevuto (voci 11, 13, 16 e 19 nella verifica complessiva). Le stesse
  domande riescono in sessioni brevi. Le note salvate restano intatte, ma la risposta non è
  affidabile se nei log manca la riga `variant=...` o se `result=` non coincide con la risposta.
