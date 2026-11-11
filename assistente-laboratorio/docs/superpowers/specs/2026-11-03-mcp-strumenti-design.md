# Specifica — Lezione 5: sei strumenti MCP nell'assistente del laboratorio

Data: 2026-11-03. Stato: **bozza da approvare**.
Fonte dei requisiti: `lezione_3\LLM_Lez_5.pdf` (31 pagine), `assistente-laboratorio/CLAUDE.md`
(versione approvata il 2026-11-03), decisioni dell'utente registrate in
`docs/superpowers/HANDOFF-lezione-5.md`.

Le voci marcate **[scelta mia]** non sono state decise dall'utente: sono decisioni di chi ha
scritto la specifica, da controllare in lettura.

---

## 1. Intento

Il progetto della lezione 4 è un assistente da terminale con grafo LangGraph
`llm → strumenti → llm`, modello `google/gemma-4-e2b` in LM Studio, uno strumento locale
`ora_corrente`, cronologia di sessione e Docker Compose. La lezione 5 chiede di cambiare **il
confine di esecuzione** degli strumenti: le nuove capacità stanno in un **server MCP**, il
programma ne legge il **catalogo** (discovery) e le invoca tramite un client MCP, mentre il
ciclo del grafo resta riconoscibile.

Il PDF chiede **una** integrazione MCP; l'utente ha scelto di realizzare **tutti e sei** gli
strumenti proposti nel blocco 5. Il completamento si dimostra con **evidenze** (percorso dei
dati nei log), non con la plausibilità delle risposte.

## 2. Obiettivi

1. Un server FastMCP che espone i sei strumenti del blocco 5.
2. Il programma avvia il server, ne legge il catalogo con `tools/list` e converte le voci in
   strumenti LangChain con un adattatore; nessun nome o schema riscritto a mano nel client.
3. Il grafo esistente esegue gli strumenti MCP come esegue `ora_corrente`: richiesta conservata,
   un `ToolMessage` con il `tool_call_id` della richiesta **per ogni richiesta**, anche quando
   fallisce, ritorno a `llm`, limite `MAX_PASSI`.
4. Tre tipi di problema distinti nei messaggi e nei log: **errore dello strumento** (argomenti
   non validi, dato inesistente), **errore di collegamento** (server MCP non raggiungibile o
   caduto; rete assente per il meteo), **interpretazione del modello** (visibile confrontando
   log e risposta).
5. Log che seguono tutta la richiesta, nel formato del §6.
6. Le sei evidenze di p. 31 per ogni strumento (§9).
7. Tutto il resto della lezione 4 continua a funzionare (cronologia, errori, Docker, test).

## 3. Non obiettivi e anti-obiettivi

**Fuori perimetro** (CLAUDE.md, «Confini»): RAG e recupero da documenti (lezione 6), workflow,
altri strumenti, interfacce grafiche, Streamable HTTP, più server MCP, prompt MCP, resource MCP
(anche quella facoltativa del catalogo), varianti FastAPI dell'orologio. `ora_corrente` resta
**invariato** (locale, senza parametri).

**Sarebbe un fallimento anche se «funziona»:**
- una risposta corretta senza la riga di invocazione nei log (falso successo);
- un catalogo copiato a mano nel client invece che letto dal server;
- un errore che produce un risultato inventato (un'ora, un calcolo, un elemento di catalogo,
  una città scelta in silenzio);
- un'eliminazione di nota ambigua o non registrata nel log;
- `eval`/`exec` nella calcolatrice;
- un test automatico che richiede LM Studio o la rete.

## 4. Vincoli

- Python 3.13, codice sincrono; l'unica parte asincrona è il collegamento MCP, isolata in un
  modulo e dichiarata (§5.3).
- Moduli piccoli; lavoro solo in `assistente-laboratorio/`; lezioni precedenti intoccate.
- Configurazione solo da variabili d'ambiente / `.env`; `.env.example` aggiornato, senza segreti.
- Unico servizio esterno: Open-Meteo (geocoding + previsioni), senza chiave.
- Le note sono l'unico dato persistente, in SQLite, fuori da Git.
- Dipendenze nuove motivate e con versione fissata (§10), da approvare con questa specifica.
- Comandi documentati per PowerShell.
- Git: `dev` da `main`; un branch `feat/<nome>` da `dev` per strumento; merge in `dev` quando lo
  strumento è finito e testato; merge `dev → main` solo quando tutti e sei sono testati e
  funzionanti; push solo su richiesta dell'utente. Avviso all'utente prima di ogni task.

## 5. Architettura

### 5.1 Componenti

| Componente | Ruolo MCP (p. 9) | Contenuto |
|---|---|---|
| Programma `python -m assistente` | **host** | grafo, cronologia, modello, scelta degli strumenti, log |
| Modulo di collegamento MCP | **client** + adattatore | avvio del server, discovery, conversione, invocazione |
| `python -m assistente.server_mcp` | **server** | i sei strumenti, validazione degli argomenti |
| Logica di dominio | — | funzioni pure per ciascuno strumento, senza dipendenze MCP |

Separazione richiesta: **logica di dominio** (testabile da sola) ≠ **registrazione nel server**
(`@mcp.tool`) ≠ **collegamento** lato host. Nomi dei file e struttura interna dei moduli:
lasciati al builder, rispettando questa separazione **[scelta mia]**: un modulo di dominio per
strumento (es. `assistente/strumenti_mcp/calcolatrice.py`), un modulo server, un modulo di
collegamento.

### 5.2 Trasporto e ciclo di vita

- Un solo server FastMCP (nome es. «Strumenti del laboratorio»), trasporto **stdio**, avviato dal
  client come sottoprocesso con lo **stesso interprete** del programma (`sys.executable -m
  assistente.server_mcp`) e la stessa cartella di lavoro.
- Il server scrive log **solo su stderr**; stdout è riservato al protocollo.
- **All'avvio** del programma: una connessione, `tools/list`, conversione in strumenti
  LangChain, chiusura della connessione. Nel log: `INFO … discovery server=… tools=[…]`.
- Se l'avvio del server o la discovery falliscono, il programma **termina** con un messaggio su
  stderr `Server MCP non disponibile: <motivo>` e codice di uscita 3, come fa già per la
  configurazione non valida **[scelta mia]**: senza catalogo l'applicazione della lezione 5 non
  è quella richiesta, e proseguire con il solo orologio nasconderebbe il problema.

### 5.3 Asincronia (requisito esplicito di p. 22)

Gli strumenti prodotti da `langchain-mcp-adapters` sono solo asincroni. Decisione **[scelta
mia]**: il modulo di collegamento offre al resto del programma strumenti **sincroni**; ogni
invocazione esegue `asyncio.run(...)`, apre **una sessione stdio nuova** (nuovo processo del
server), chiama `tools/call` e chiude. Nome, descrizione e schema dello strumento sincrono sono
**presi dall'oggetto prodotto dalla discovery**, non riscritti.
Conseguenze dichiarate: ogni chiamata costa l'avvio di un processo (stima 1–3 s); nessuno stato
in memoria nel server tra due chiamate (le note sono su file, quindi non ne risentono). Il
grafo, la conversazione e il terminale restano sincroni.

### 5.4 Grafo

Struttura invariata (`START → llm → instrada → strumenti → llm`, `MAX_PASSI`). Modifiche:
- `bind_tools` riceve `ora_corrente` + gli strumenti MCP scoperti.
- Il nodo strumenti **cattura** gli errori di collegamento di una singola chiamata e produce
  comunque il `ToolMessage` correlato, con testo `Errore di collegamento con il server MCP:
  <motivo>` (oggi un'eccezione nello strumento interromperebbe il turno). Gli errori dello
  strumento arrivano già come risultato d'errore dall'adattatore e diventano un `ToolMessage`
  con il testo dell'errore.
- Ogni `ToolMessage` ha lo **stesso** `tool_call_id` della richiesta, anche negli errori e per
  «Strumento sconosciuto».
- Prompt di sistema: aggiornato per dire che sono disponibili strumenti per calcoli,
  conversioni, date, catalogo dei corsi, note e meteo, e che vanno usati quando la domanda li
  riguarda invece di rispondere a memoria; il dettaglio di ciascuno resta nelle descrizioni del
  catalogo **[scelta mia]**. La formulazione definitiva si sistema con le prove reali.

### 5.5 Errori: classificazione

| Tipo | Dove nasce | Come arriva al modello | Esempio |
|---|---|---|---|
| Errore dello strumento | il server rifiuta l'input o il dato non esiste (`ToolError` → `isError`) | `ToolMessage` con messaggio chiaro, nessun valore inventato | `Mars/Olympus`-equivalenti: «unità non ammessa: parsec» |
| Errore del servizio esterno (meteo) | il server non raggiunge Open-Meteo | `ToolMessage` d'errore che dice **«servizio meteo non raggiungibile»/«attesa scaduta»/«risposta non valida»**, distinto da «città non trovata» | rete assente |
| Errore di collegamento MCP | il processo server non parte o cade durante la chiamata | `ToolMessage` «Errore di collegamento con il server MCP: …» | interprete o modulo mancante |
| Interpretazione del modello | il modello usa male un risultato corretto | non rilevabile dal codice: si vede confrontando log e risposta | — |

## 6. Log

Formato di riga (logger `assistente.grafo`, livello INFO), una riga per evento, `chiave=valore`
**[scelta mia, ricalcato sulla traccia di p. 23]**:

```
INFO assistente.grafo: variant=mcp tool=calcola call_id=call_01 arguments={"espressione": "2+3*4"}
INFO assistente.grafo: variant=mcp tool=calcola call_id=call_01 execution=ok result=14
INFO assistente.grafo: tool_message.call_id=call_01 next_node=llm
```

- `variant=local` per `ora_corrente`, `variant=mcp` per gli strumenti del server.
- `execution=ok | tool_error | connection_error | unknown_tool`.
- Il risultato nel log è troncato a una lunghezza ragionevole (scelta del builder).
- Restano le righe esistenti `Inizio/Fine chiamata al modello (passo n/N)` e l'avviso del limite.
- Il server registra su stderr **ogni modifica** delle note (`nota creata id=…`, `nota eliminata
  id=…`, `eliminazione rifiutata id=… inesistente`).
- La discovery all'avvio produce una riga con i nomi degli strumenti ricevuti.
Le righe di log dell'host precedenti (lezione 4) che descrivono strumento e risultato vengono
sostituite da questo formato; il README va aggiornato di conseguenza.

## 7. I sei strumenti

Nomi di strumenti e argomenti, descrizioni e messaggi **in italiano**, come il resto del
progetto (`ora_corrente`): **decisione dell'utente** (2026-11-03, «tieni lo stesso pattern»).
I nomi inglesi del PDF corrispondono così: `search_catalog` → `cerca_corsi`, `get_item` →
`dettaglio_corso`, `add_note` → `aggiungi_nota`, `list_notes` → `elenca_note`, `delete_note` →
`elimina_nota`, `get_weather` → `meteo_citta`. I nomi precisi sono **[scelta mia]**. Ogni risultato è testo leggibile dal modello e, dove utile, strutturato (scelta del
builder purché i test lo verifichino). Ogni errore è un `ToolError` con messaggio in italiano.

### 7.1 Calcolatrice sicura — branch `feat/calcolatrice` (contiene anche la base MCP)

- `calcola(espressione: str)` → risultato numerico dell'espressione.
- Ammessi: numeri interi e decimali (punto decimale), `+ - * /`, `//`, `%`, `**`, `-` e `+`
  unari, parentesi **[scelta mia]**. Nessun nome, funzione, attributo, stringa, confronto.
- Valutazione tramite analisi dell'albero sintattico (`ast`) con elenco chiuso di nodi; **mai**
  `eval`/`exec`/`compile` in modalità eseguibile.
- Errori: espressione vuota; carattere o costrutto non ammesso (il messaggio dice quale);
  sintassi non valida; divisione per zero; lunghezza oltre 200 caratteri; esponente oltre 100
  in valore assoluto o risultato non finito **[soglie scelta mia]**.
- Casi: `2+3*4` → 14; `(1.5+2)/7` → 0.5; `__import__('os')` → rifiuto; `10/0` → errore;
  `2**10000` → rifiuto.

### 7.2 Convertitore di unità — `feat/convertitore`

- `converti_unita(valore: float, da_unita: str, a_unita: str)`.
- Elenco chiuso **[scelta mia]**: lunghezza `mm, cm, m, km, in, ft, mi`; massa
  `g, kg, lb, oz`; temperatura `C, F, K`. Simboli esatti; l'elenco compare nella descrizione.
- Risultato: valore convertito con le due unità esplicite (es. `10 km = 6.2137 mi`).
- Errori: unità non ammessa (il messaggio elenca quelle ammesse); categorie incompatibili
  (`m` → `kg`); temperatura sotto lo zero assoluto.

### 7.3 Giorni e scadenze — `feat/giorni-scadenze`

- `conta_giorni(data_inizio: str, data_fine: str)` → giorni di calendario e giorni lavorativi
  (esclusi sabato, domenica e festività) tra le due date, con l'elenco delle festività incluse.
- `aggiungi_giorni_lavorativi(data_inizio: str, giorni: int)` → data di scadenza dopo N giorni lavorativi.
- Date **solo ISO** `YYYY-MM-DD`.
- Regole di conteggio **[scelta mia]**:
  - `conta_giorni`: giorni di calendario = `data_fine − data_inizio` (stessa data → 0); giorni lavorativi =
    giorni lavorativi nell'intervallo **escluso l'inizio, incluso la fine**;
  - `aggiungi_giorni_lavorativi`: la data di partenza **non conta**, anche se lavorativa; si contano i
    successivi N giorni lavorativi e la scadenza è l'N-esimo. Se la partenza cade di sabato,
    domenica o festivo il conteggio parte comunque dal giorno dopo.
  - giorno lavorativo = lunedì–venerdì e non festivo.
- Festività: file locale versionato con le **festività nazionali italiane 2026 e 2027**
  (date e nomi) **[scelta mia]**: 1 gen, 6 gen, Pasqua, Lunedì dell'Angelo, 25 apr, 1 mag,
  2 giu, 15 ago, **4 ott (San Francesco, di nuovo festa nazionale dal 2026)**, 1 nov, 8 dic,
  25 dic, 26 dic. Niente patroni locali. Le date di Pasqua vanno verificate su fonte affidabile
  quando si scrive il file.
- Ogni risultato riporta la nota «calcolo indicativo, non normativo».
- Errori: data non ISO o inesistente (`2026-02-30`); fine prima dell'inizio; intervallo o
  scadenza che esce dagli anni presenti nel file (errore esplicito, non calcolo senza
  festività); `giorni` minore di 1 o oltre 365 **[soglia scelta mia]**.

### 7.4 Catalogo locale — `feat/catalogo`

- Dati: file JSON versionato con circa 10 corsi **inventati** (codice, titolo, sede, durata in
  ore) **[scelta mia]**.
- `cerca_corsi(testo: str, max_risultati: int = 5)` → elenco (codice, titolo, sede) dei corsi il
  cui titolo, codice o sede contiene `testo`, senza distinzione di maiuscole.
  `max_risultati` ammesso da 1 a 20 **[scelta mia]**.
- `dettaglio_corso(codice: str)` → tutti i campi del corso.
- Nessun risultato → elenco vuoto **dichiarato** («nessun corso trovato per …»), non un errore.
- Errori: `testo` vuoto; `max_risultati` fuori intervallo; codice inesistente.
- Descrizioni dei due strumenti chiaramente distinte (ricerca vs dettaglio per codice).
- Caso da provare: domanda che richiede ricerca e poi dettaglio (due chiamate in sequenza nello
  stesso turno, entro `MAX_PASSI=5`).

### 7.5 Note persistenti — `feat/note`

- `aggiungi_nota(testo: str)` → ID e data/ora di creazione.
- `elenca_note(limite: int = 10)` → note ordinate per ID crescente (= ordine di creazione),
  con ID, data e testo; `limite` da 1 a 50 **[scelta mia]**; elenco vuoto dichiarato.
- `elimina_nota(id_nota: int)` → conferma con ID e testo della nota eliminata.
- Archivio: file SQLite in `archivio/note.sqlite` nella cartella del progetto, creato al primo
  uso, **escluso da Git**. Percorso fisso, nessuna variabile d'ambiente: la logica di dominio
  riceve il percorso come parametro (i test usano una cartella temporanea), il server usa quello
  fisso.
- Errori: testo vuoto o oltre 500 caratteri **[soglia scelta mia]**; ID inesistente → nessuna
  eliminazione; archivio non accessibile.
- Descrizioni precise sugli effetti («salva in modo permanente», «elimina definitivamente la
  sola nota con questo ID»). Un log per ogni modifica (§6).
- Casi: «Ricordami di consegnare il report venerdì» → una sola `aggiungi_nota`; «Elimina la nota 99»
  → errore, nessuna eliminazione; dopo il riavvio dell'applicazione le note ci sono ancora.

### 7.6 Meteo — `feat/meteo`

- `meteo_citta(citta: str)` → città scelta (nome, regione, paese, coordinate), temperatura
  attuale con unità, condizioni in italiano (dal codice meteo WMO), ora di riferimento con fuso.
- Servizio: Open-Meteo, geocoding (`geocoding-api.open-meteo.com/v1/search`) poi previsioni
  correnti (`api.open-meteo.com/v1/forecast`), via `httpx` con timeout di 10 s **[scelta mia]**.
- Città ambigua: si usa il primo risultato del geocoding e il risultato lo **dichiara**,
  elencando le altre corrispondenze.
- Errori distinti: città vuota; città non trovata; attesa scaduta; servizio non raggiungibile;
  risposta HTTP d'errore; risposta non valida.
- Test con trasporto HTTP simulato (nessuna rete). Prova reale con rete attivata esplicitamente.
- Docker: verificare che il container raggiunga Open-Meteo.

## 8. Configurazione e Docker

- **Nessuna variabile d'ambiente nuova**: `.env.example` invariato.
- `.gitignore` del progetto: `archivio/` (o il solo file del database).
- Dockerfile: copia anche i file di dati (festività, catalogo); il server MCP gira **dentro lo
  stesso container** dell'applicazione, avviato come sottoprocesso.
- `compose.yaml`: un volume per `archivio/` così le note sopravvivono a `docker compose run
  --rm`; nessuna porta pubblicata; LM Studio resta sull'host come oggi.

## 9. Test e verifiche

Automatici (`python -m pytest`, senza LM Studio né rete):
- logica di dominio di ciascuno strumento, compresi tutti i casi d'errore del §7;
- **server**: discovery (nomi, descrizioni, schemi) e invocazione diretta con input noti,
  tramite il client in memoria di FastMCP (evidenze «Discovery» e «Invocazione diretta»);
- **collegamento**: avvio reale del server via stdio e discovery (processo locale, nessuna rete);
  conversione in strumenti sincroni con nome/schema uguali a quelli del server; errore di
  collegamento quando il server non può partire;
- **grafo**: con modello simulato, `ToolMessage` correlato per successo, errore dello strumento,
  errore di collegamento e strumento sconosciuto; limite `MAX_PASSI`; righe di log del §6;
- note con database in cartella temporanea; meteo con HTTP simulato;
- tutti i test della lezione 4 restano verdi (a parte quello che fallisce per il blocco di
  Windows su `jiter`, noto e non considerato un problema dall'utente).

Prove reali (attivate esplicitamente, separate):
- `PROVE_REALI=1`: con LM Studio, per ogni strumento una domanda che deve attivarlo e la verifica
  nei log di richiesta, argomenti, esecuzione e `ToolMessage` correlato; per il meteo serve
  anche la rete;
- checklist manuale del README estesa ai casi del §7 (incluso il riavvio per le note) in locale
  e con Docker Compose.
- Ambiente delle prove reali **[scelta mia]**: in locale finché Windows App Control blocca
  `jiter` (l'app oggi non parte in locale) le prove reali si eseguono **con Docker Compose**,
  che non ne risente; per questo il supporto Docker è parte della base in `feat/calcolatrice`,
  prima della prima prova reale. Se il blocco viene rimosso, si fanno anche in locale.
- Se una prova reale fallisce (per esempio `gemma-4-e2b` sceglie lo strumento sbagliato), si
  registra il punto esatto nel README senza dichiarare completato il percorso.

Ogni strumento si considera **finito** (e può andare in `dev`) quando ha: test automatici verdi,
discovery e invocazione diretta verificate, prova reale con LM Studio eseguita e registrata,
README aggiornato. **Decisione dell'utente (2026-11-03):** se la prova reale fallisce, lo
strumento va **comunque** in `dev`, purché i test automatici siano verdi e il fallimento sia
registrato nel README con il punto esatto (senza dichiarare completato il percorso). Il merge
`dev → main` resta subordinato alla conferma dell'utente, che vedrà l'elenco degli esiti.

## 10. Dipendenze nuove (da approvare)

| Pacchetto | Versione | Motivo |
|---|---|---|
| `fastmcp` | 3.4.11 | server MCP (come negli esempi del PDF) e client in memoria per i test; ultima versione compatibile con `mcp` 1.x |
| `langchain-mcp-adapters` | 0.3.2 | adattatore che converte il catalogo MCP in strumenti LangChain (p. 20–21) |
| `mcp` | 1.30.0 | SDK del protocollo; fissato perché `fastmcp` 4.x e l'adattatore richiedono versioni incompatibili (`>=2` contro `<2`) |
| `httpx` | 0.28.1 | chiamate HTTP del meteo e trasporto simulato nei test; oggi presente solo come dipendenza indiretta |

Rischio noto: le nuove dipendenze contengono estensioni native; su questo PC Windows App
Control ha già bloccato `jiter`. Va verificato subito dopo l'installazione.

## 11. Ordine di lavoro

0. Creazione di `dev` da `main`, poi su `dev`, prima di ogni funzionalità:
   - commit `docs:` con i **soli commenti esplicativi** già presenti nei file di
     `assistente-laboratorio/` (decisione dell'utente, 2026-11-03);
   - commit del nuovo CLAUDE.md, della specifica e del piano.
   I 4 file della Lezione 3 nella radice (`client.py`, `requirements.txt`, `.env.example`,
   `.gitignore`) restano **non committati e non toccati**; non vanno mai inclusi nello staging.
1. `feat/calcolatrice`: base MCP (server, collegamento, discovery, adattatore sincrono, log,
   gestione errori nel grafo, Docker) + calcolatrice. È l'integrazione «obbligatoria» del PDF:
   gli strumenti successivi partono solo dopo che questa è dimostrata con evidenze nei log.
2. `feat/convertitore` 3. `feat/giorni-scadenze` 4. `feat/catalogo` 5. `feat/note`
6. `feat/meteo` — ciascuno da `dev` aggiornato, merge in `dev` quando finito.
7. Verifica complessiva su `dev` (test, prove reali, Docker), poi merge `dev → main` su
   conferma dell'utente; push solo su sua richiesta.

## 12. Lasciato al builder

Nomi dei file e struttura interna dei moduli (nel rispetto del §5.1); forma esatta dei
risultati (purché leggibile e testata); testo esatto dei messaggi; lunghezza del troncamento nei
log; dettaglio del prompt di sistema (da validare con le prove reali); suddivisione in task e
commit nel piano.
