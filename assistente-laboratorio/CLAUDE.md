# Assistente del laboratorio

Progetto del corso «Deep Learning e LLM: costruire chatbot e agenti». La cartella del progetto è `assistente-laboratorio/`.

## Obiettivo

Un'applicazione in Python che conversa con un modello locale e:

- organizza il flusso in un grafo LangGraph esplicito (stato, nodi, instradamento riconoscibili);
- (lezione 6, step 1) fa passare ogni domanda da un nodo router (stesso modello, senza strumenti, output strutturato `categoria`/`motivo`) prima dell'agente: `START → router → llm ⇄ strumenti → END`, con `fuori ambito` → nodo `rifiuto` → END; l'ambito sta nella variabile obbligatoria `AMBITO_AGENTE`, il prompt del router in `assistente/router.py`;
- (lezione 6, step 2) fa passare la risposta finale dell'agente da un nodo revisore (stesso modello, senza strumenti, output strutturato `coerente` `sì`/`no` e `motivo`, vede solo domanda del turno e risposta): `llm → revisore → END`, oppure, se non coerente, indicazione (`HumanMessage` con `name="revisore"`) nella cronologia e ritorno a `llm` con i passi azzerati, fino al limite nella variabile facoltativa `MAX_REVISIONI` (default 2; campo di stato `revisioni`), al limite l'ultima risposta con avviso nel log; il prompt del revisore in `assistente/revisore.py`;
- (lezione 6, step 3) apre ogni turno con un nodo riassunto (stesso modello, senza strumenti, testo libero): `START → riassunto → router`; oltre `SOGLIA_RIASSUNTO` messaggi (facoltativa, default 20) comprime i vecchi e tiene gli ultimi `MESSAGGI_DA_TENERE` (facoltativa, default 6, minore della soglia), con il taglio spostato indietro alla domanda dell'utente che apre il turno; il riassunto è il campo di stato `riassunto`, sostituito e non accumulato, conservato da `Conversazione` tra i turni e messo in coda al messaggio di sistema di agente e router (non del revisore); sotto la soglia nessuna chiamata al modello; prompt e taglio in `assistente/riassunto.py`;
- (lezione 6, step 4) il server MCP pubblica la resource `utente://preferenze` (testo di `archivio/preferenze.json`: `lingua`, `fuso_orario`, `stile` `sintetico`/`dettagliato`); l'host la legge una volta a inizio sessione, dopo la discovery (server giù → codice 3), la valida in `assistente/preferenze.py` e la mette in cima al messaggio di sistema dell'agente (non di router, revisore e riassuntore); se non è disponibile o non è valida, tutti i valori predefiniti (italiano, `FUSO_ORARIO`, sintetico) con un WARNING nei log; la resource non passa da `bind_tools`;
- (lezione 6, step 5) il server MCP pubblica i prompt `spiega(argomento, livello)` e `riassumi_conversazione(stile)`; la CLI offre `/prompts` (elenco da `prompts/list`) e `/prompt nome argomento=valore` (lettura in `assistente/prompt_mcp.py`, smistamento in `assistente/terminale.py`); l'host controlla gli argomenti rispetto a `prompts/list` (sconosciuti, obbligatori mancanti) senza chiamare il modello, poi `prompts/get` nella stessa sessione (`assistente/collegamento_mcp.py`); i messaggi ottenuti vanno al grafo come una domanda (`Conversazione.chiedi_messaggi`); i prompt non passano da `bind_tools`;
- (lezione 6, step 6) l'agente è un servizio HTTP senza stato: il montaggio (`costruisci_agente`) e il turno (`esegui_turno`, con `strumenti_usati`) stanno in `assistente/agente.py`, l'API FastAPI in `assistente/servizio.py` (`POST /messaggio`, `GET /stato`, `GET /prompts`, `POST /prompts/{nome}`, `/docs`; avvio `python -m assistente.servizio`, `AGENTE_HOST`/`AGENTE_PORTA`), il formato JSON dei messaggi in `assistente/formato.py`; la CLI (`python -m assistente`) è solo client dell'API (`assistente/cliente.py`, `AGENTE_URL`) e tiene lei cronologia e riassunto; `Conversazione` resta come client in memoria (prove reali);
- usa un modello servito da LM Studio, che resta sul computer host;
- conserva la cronologia della conversazione per la durata della sessione (dallo step 6 nel client, perché l'agente è senza stato; la conversazione non viene salvata, finché lo step 7 della lezione 6 non introduce il salvataggio delle chat);
- offre lo strumento locale `ora_corrente` (fuso dalle preferenze, o da `FUSO_ORARIO` se non disponibili; deciso dall'host a inizio sessione, lo strumento resta senza parametri come nella lezione 4);
- (lezione 5, completata) offre, tramite MCP, i sei strumenti del blocco 5 del PDF: calcolatrice sicura, convertitore di unità, giorni e scadenze, catalogo locale, note persistenti, meteo; il programma ne scopre il catalogo dal server (discovery) e li esegue davvero;
- si avvia anche con Docker Compose (dallo step 6 due servizi dalla stessa immagine: `agente`, con la porta 8000 pubblicata, e `cli`; `docker compose up -d --build agente`, poi `docker compose run --rm cli`).

### Lezione 6 — evolvere l'agente (PDF `LLM_Lez_6.pdf`)

Il PDF si trova in `C:\Users\CarloGiacomini\Desktop\AI 2\LLM - Paolo\assistente_laboratorio\LLM_Lez_6.pdf` (fuori da questa repository; quella cartella contiene solo materiale di partenza della lezione 4: non lavorarci). Si parte dall'agente delle lezioni 4 e 5 e lo si fa evolvere in nove step, ciascuno con le proprie «evidenze richieste» (vedi il PDF):

1. Router (Base): nodo LLM prima dell'agente; ambito dichiarato in configurazione; output strutturato categoria (conversazione / fuori ambito) e motivo; fuori ambito → nodo di rifiuto senza passare dall'agente; il router non valuta gli strumenti.
2. Revisore (Intermedio): nodo LLM dopo l'agente; output strutturato coerente (sì/no) e motivo; se non coerente il motivo entra nella cronologia per l'agente; limite di revisioni nello stato, al limite si restituisce l'ultima risposta e lo si segnala nei log.
3. Riassunto della cronologia (Avanzato): soglia configurabile (messaggi o stima dei token); nodo all'inizio del turno che comprime i messaggi vecchi e conserva gli ultimi N; il riassunto è un campo dello stato aggiornato, non accumulato; il taglio non separa mai una richiesta di tool dal suo ToolMessage; sotto la soglia nessuna chiamata al modello.
4. Resource MCP `utente://preferenze` (lingua, fuso orario predefinito, stile): letta dall'host a inizio sessione e messa in cima al prompt di sistema; non compare tra i tool di `bind_tools`; se non disponibile, valori predefiniti segnalati nei log.
5. Prompt MCP `spiega(argomento, livello)` e `riassumi_conversazione(stile)`; comandi CLI `/prompts` e `/prompt nome argomento=valore`; argomenti validati nell'host rispetto a `prompts/list` senza chiamare il modello; i messaggi ottenuti passano dal grafo come una domanda.
6. Agente come servizio HTTP: modulo dell'agente separato dall'interfaccia (la CLI diventa client dell'API); endpoint messaggio + cronologia → risposta + strumenti usati; endpoint di stato (agente, server MCP, modello); agente senza stato; documentazione OpenAPI.
7. Back-end: API per il front-end (creare, elencare, leggere, eliminare chat; inviare un messaggio), chat e messaggi in PostgreSQL; il front-end non conosce l'agente.
8. Front-end: interfaccia di chat (tecnologia libera) che parla solo con il back-end; elenco/creazione/eliminazione chat, invio domanda, stato di attesa, errori comprensibili; indirizzo del back-end da configurazione; il documento OpenAPI del back-end è il contratto.
9. Docker Compose: quattro servizi (front-end, back-end, agente con il proprio Dockerfile; PostgreSQL con l'immagine ufficiale); agente non esposto; volume per PostgreSQL; credenziali in `.env` escluso da Git; back-end avviato a database pronto; l'agente raggiunge LM Studio con `host.docker.internal` e i server MCP stdio partono nel suo container.

Facoltativo nel PDF («Se manca»): streaming della risposta lungo tutta la catena; con il revisore attivo va scelto e documentato se mostrare la bozza o solo la risposta approvata. Si affronta solo se l'utente lo decide.

## Confini

- Implementare solo quanto già presente nel progetto e quanto richiesto dal PDF della lezione 6, step per step, con ciò che serve a realizzarlo (dipendenze, test, documentazione, Docker). Niente altro.
- Uno step alla volta: ogni step parte da quello precedente funzionante; estendere il progetto senza riscriverlo e non anticipare gli step successivi.
- Fuori perimetro: RAG e recupero da documenti, workflow, strumenti non elencati, Streamable HTTP, servizi cloud, e qualunque cosa non richiesta dal PDF. Il modello resta `google/gemma-4-e2b`.
- Unico servizio esterno ammesso: l'API pubblica Open-Meteo per lo strumento meteo. PostgreSQL gira in locale (container), non come servizio cloud.
- Lavorare solo dentro `assistente-laboratorio/`. La repository contiene altre lezioni: non leggerle per copiarne il codice e non modificarle.

## Scelte tecniche

- Python, moduli piccoli, separazione semplice tra grafo, collegamento al modello, strumenti, server MCP, collegamento MCP e interfaccia (dallo step 6: agente come servizio, back-end, front-end).
- Codice sincrono dove possibile; le parti asincrone (collegamento MCP e, se servono, servizi HTTP) sono isolate e dichiarate.
- LM Studio sull'host, raggiunto tramite la sua API compatibile con OpenAI.
- Dallo step 6: servizio dell'agente con FastAPI e uvicorn, endpoint sincroni (`def`); la CLI parla con l'agente solo via HTTP (httpx). In locale due finestre: `python -m assistente.servizio` e `python -m assistente`.
- Un solo server MCP con FastMCP, trasporto stdio (avviato dal programma come sottoprocesso; log del server su stderr); tool, resource e prompt arrivano dal server (`tools/list`, `resources/read`, `prompts/list`, `prompts/get`), mai riscritti a mano nel client. Tool: li attiva il modello; resource: l'host; prompt: l'utente.
- Indirizzo del server e identificativo del modello solo da variabili d'ambiente. L'identificativo è quello restituito dal server (`GET /v1/models`), mai inventato. Ambito dell'agente e soglie in configurazione, non nel codice.
- Dati persistenti: le note (SQLite nella cartella del progetto, escluso da Git, in Docker su volume) e, dallo step 7, chat e messaggi in PostgreSQL su volume.
- Un file di configurazione di esempio senza credenziali; il file reale resta fuori da Git.
- Docker Compose per l'applicazione (dallo step 9: un container per componente); LM Studio non va containerizzato.
- Dipendenze motivate, concordate e con versioni fissate (i framework per API, database e front-end si scelgono nella specifica dello step che li richiede).
- Comandi documentati anche per PowerShell (Windows).

## Metodo: Superpowers

- Usare le skill di Superpowers per brainstorming, specifica, piano, implementazione e verifica.
- Per ogni step della lezione 6: brainstorming, specifica e piano approvati prima del codice. Non scrivere codice prima che io abbia approvato la specifica e poi il piano.
- Chiarire le decisioni mancanti e proporre una soluzione semplice.
- Salvare specifica e piano in `assistente-laboratorio/docs/superpowers/`.
- Prima di ogni task, avvisarmi (che cosa, su quale branch, quali file) e aspettare il via libera; segnare ogni task completato nella checklist del piano.
- Procedere per incrementi piccoli, ciascuno verificato prima del commit.

## Test e verifiche

- Test automatici ripetibili che non richiedono un modello attivo né la rete: grafo, cronologia, instradamento, orologio con istante controllato, server MCP (discovery e invocazione diretta), strumenti con dati locali, SQLite temporaneo, HTTP simulato per il meteo; dalla lezione 6 anche router, revisore e riassunto con risposte simulate, API con grafo o agente simulato.
- Prove reali con LM Studio, con Docker, con la rete e (dallo step 8) dal browser tenute separate e attivate esplicitamente.
- Una risposta simulata non dimostra che il modello locale sappia usare lo strumento.
- Le evidenze richieste dal PDF per ogni step devono essere verificabili nei log o nei test.
- Per ogni step: test automatici, prova reale con LM Studio, README aggiornato e commit.
- Nel resoconto indicare che cosa è stato eseguito, con quale esito, e che cosa resta da provare. Se una prova reale fallisce, registrare il punto esatto senza dichiarare completato il percorso.

## Git

- Lezione 5 (completata): un branch `feat/<nome>` per strumento da `dev`, merge in `dev`, poi `dev` in `main`.
- Lezione 6: un branch `feat/<step>` per ogni step, creato da `dev`; quando è finito e verificato, merge in `dev`; merge di `dev` in `main` solo con la mia conferma.
- Conventional Commits in italiano, per esempio `feat(grafo): ...`, `test(strumenti): ...`, `docs: ...`; un commit per ogni incremento verificato.
- Prima di ogni commit: `git status`, controllo del diff, staging selettivo dei soli file pertinenti.
- Mai versionare credenziali, `.env`, ambienti virtuali, cache, database delle note, dati di PostgreSQL o pesi dei modelli.
- Push soltanto su mia richiesta.

## Documentazione

- Tenere aggiornato il README con configurazione, avvio, test e diagnosi, riportando solo comandi verificati.
- Aggiornare questo file quando cambiano convenzioni stabili (struttura, architettura, comandi di test, regole di lavoro), non per annotare l'avanzamento.
