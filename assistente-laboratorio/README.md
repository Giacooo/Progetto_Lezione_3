# Assistente del laboratorio

Applicazione da terminale in Python il cui turno di conversazione è un grafo LangGraph
esplicito, collegato a un modello locale servito da LM Studio.

Tutti i comandi si eseguono da PowerShell nella cartella `assistente-laboratorio`.

## Preparazione

Serve Python 3.13.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

`requirements.txt` contiene le dipendenze dell'applicazione; `requirements-dev.txt` aggiunge
`pytest` per i test.

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
con istante fisso.

```powershell
python -m pytest
```

Le due prove reali di `tests/test_reale.py` risultano *skipped*.

## Prove reali con LM Studio

Con LM Studio attivo e il `.env` configurato, verificano che il modello vero chieda
`ora_corrente` a una domanda sull'ora e non a una domanda ordinaria:

```powershell
$env:PROVE_REALI = "1"; python -m pytest -m reale -v; Remove-Item Env:PROVE_REALI
```

## Avvio locale

LM Studio deve essere avviato con il modello indicato in `LM_MODEL` caricato e il server attivo.

```powershell
python -m assistente
```

Al prompt `Tu> ` si scrive la domanda. La sessione si chiude con `esci`, con Ctrl+C o con
la fine dell'input; le righe vuote sono ignorate. La conversazione resta in memoria per tutta
la sessione e si perde alla chiusura.

Le righe di log (su stderr, nello stesso terminale) iniziano con livello e componente, per
esempio `INFO assistente.grafo: Inizio chiamata al modello (passo 1/5)`; il resto è la risposta.

Se il modello non è raggiungibile l'applicazione non inventa risposte: mostra uno di questi
messaggi e la sessione continua, senza registrare il turno fallito nella cronologia.

- `Connessione fallita: controllare LM Studio, URL e porta.`
- `Attesa scaduta: controllare server, carico e tempi.`
- `Errore dal server: <codice> <testo>` (per esempio un id del modello sbagliato)
- `Il modello ha restituito una risposta vuota.`

### Strumento orologio

Il modello può richiedere lo strumento `ora_corrente` (nessun parametro), che il programma
esegue davvero e che restituisce data e ora nel fuso `FUSO_ORARIO`, per esempio
`2026-10-27T12:43:44+01:00 (Europe/Rome)`. Il fuso non viene mai preso dal sistema.

Per una domanda sull'ora i log mostrano l'intero giro:

```
INFO assistente.grafo: Inizio chiamata al modello (passo 1/5)
INFO assistente.grafo: Fine chiamata al modello (passo 1/5): richieste di strumenti: 1
INFO assistente.grafo: Richiesta strumento ora_corrente con argomenti {}
INFO assistente.grafo: Risultato strumento ora_corrente: 2026-...+01:00 (Europe/Rome)
INFO assistente.grafo: Inizio chiamata al modello (passo 2/5)
INFO assistente.grafo: Fine chiamata al modello (passo 2/5): risposta finale
```

Una risposta sull'ora senza le righe `Richiesta strumento` non prova che lo strumento sia stato
usato. Se il modello continua a chiedere strumenti oltre `MAX_PASSI` chiamate, il turno si ferma
con `Limite di passaggi raggiunto: riprova con una domanda diversa.`

Lo strumento si può provare da solo, senza modello:

```powershell
python -c "from zoneinfo import ZoneInfo; from assistente.strumenti import crea_strumenti; print(crea_strumenti(ZoneInfo('Europe/Rome'))[0].invoke({}))"
```

### Verifica manuale della cronologia

1. Scrivere `Mi chiamo Luca`, poi `Come mi chiamo?`: la seconda risposta contiene «Luca».
2. Fermare il server in LM Studio e scrivere una domanda: compare `Connessione fallita: ...`.
3. Riavviare il server e chiedere di nuovo `Come mi chiamo?`: il nome è ancora ricordato.
4. Chiudere con `esci` (oppure Ctrl+C).

## Avvio con Docker Compose

L'applicazione gira nel container; LM Studio resta sull'host. Nel container `localhost` è il
container stesso, quindi `compose.yaml` sostituisce `LM_BASE_URL` con
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
```

## Checklist delle prove reali

Da eseguire in locale (`python -m assistente`) e con Docker Compose (secondo terminale con
`docker logs -f assistente-demo`):

1. Domanda ordinaria: risposta senza righe `Richiesta strumento` nei log.
2. `Che ore sono?`: nei log `Richiesta strumento ora_corrente`, `Risultato strumento ...` e una
   seconda chiamata al modello; la risposta riporta l'ora del risultato.
3. `Mi chiamo Luca`, poi `Come mi chiamo?`: la risposta contiene «Luca».
4. LM Studio fermo: `Connessione fallita: ...`; riacceso: la conversazione prosegue.
5. Le lettere accentate sono mostrate correttamente.
6. Chiusura con `esci` e con Ctrl+C, anche mentre si attende la risposta del modello.

## Diagnosi

| Sintomo | Cosa controllare |
|---|---|
| `Configurazione non valida: ...` all'avvio | il `.env` nella cartella da cui si avvia e le variabili indicate |
| `Connessione fallita: ...` | server di LM Studio avviato, `LM_BASE_URL` e porta; in Docker anche "Serve on Local Network" e firewall |
| `Attesa scaduta: ...` | modello caricato, carico della macchina (il primo caricamento è lento) |
| `Errore dal server: 404 ...` o simili | `LM_MODEL` uguale a un id restituito da `/v1/models` |
| `Errore dal server: 400 ... jinja template ...` | il template del modello in LM Studio non supporta gli strumenti: aggiornare LM Studio e il runtime llama.cpp |
| risposta sull'ora senza righe `Richiesta strumento` | il modello non ha usato lo strumento: la risposta non è affidabile |
| il container termina subito | avviarlo senza `--rm` e leggere `docker logs assistente-demo`; con `docker compose run` serve un terminale interattivo |

## Esiti delle prove reali

Eseguite il 2026-10-28 con `google/gemma-4-e2b` in LM Studio.

- Il 2026-10-27 ogni richiesta con strumenti falliva con
  `Errore dal server: 400 ... Error rendering prompt with jinja template ...`, anche con una
  richiesta HTTP diretta: dopo l'aggiornamento di LM Studio e del runtime l'errore non compare più.
- Con il prompt di sistema precedente gemma invitava l'utente a usare lo strumento invece di
  chiamarlo; con la formulazione attuale lo chiama.
- Prove reali automatiche (`PROVE_REALI=1`): 2 superate su 2, in tre esecuzioni.
- Checklist qui sopra: voci 1–6 superate in locale e con Docker Compose. In Docker la sessione
  è stata pilotata con input da script (`docker compose run -T`) e i log letti in parallelo
  con `docker logs -f assistente-demo`; LM Studio è stato fermato e riavviato con
  `lms server stop` / `lms server start`; il Ctrl+C nel container è stato inviato come SIGINT
  (`docker kill --signal=SIGINT assistente-demo`). Il Ctrl+C in locale durante l'attesa del
  modello è stato provato a mano: compare «Arrivederci.».

## Problemi aperti

Nessuno noto.
