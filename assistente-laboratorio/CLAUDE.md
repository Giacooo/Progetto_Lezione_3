# Assistente del laboratorio

Progetto del corso «Deep Learning e LLM: costruire chatbot e agenti». La cartella del progetto è `assistente-laboratorio/`.

## Obiettivo

Un'applicazione da terminale in Python che conversa con un modello locale e:

- organizza il flusso in un grafo LangGraph esplicito (stato, nodi, instradamento riconoscibili);
- usa un modello servito da LM Studio, che resta sul computer host;
- conserva la cronologia della conversazione per la durata della sessione (la conversazione non viene salvata);
- offre lo strumento locale `ora_corrente` (fuso da `FUSO_ORARIO`), invariato rispetto alla lezione 4;
- (lezione 5) offre, tramite MCP, i sei strumenti del blocco 5 del PDF: calcolatrice sicura, convertitore di unità, giorni e scadenze, catalogo locale, note persistenti, meteo; il programma ne scopre il catalogo dal server (discovery) e li esegue davvero;
- si avvia anche con Docker Compose.

## Confini

- Implementare solo quanto già presente nel progetto e quanto richiesto dal PDF della lezione 5 (MCP e i sei strumenti), con ciò che serve a realizzarlo (dipendenze, dati locali, test, documentazione, Docker). Niente altro.
- Fuori perimetro: RAG e recupero da documenti (lezione 6), workflow, altri strumenti non elencati, interfacce grafiche, e le parti facoltative del PDF (Streamable HTTP, più server MCP, prompt e resource MCP, varianti FastAPI dell'orologio).
- Unico servizio esterno ammesso: l'API pubblica Open-Meteo per lo strumento meteo. Nessun altro servizio cloud.
- Lavorare solo dentro `assistente-laboratorio/`. La repository contiene altre lezioni: non leggerle per copiarne il codice e non modificarle.

## Scelte tecniche

- Python, moduli piccoli, separazione semplice tra grafo, collegamento al modello, strumenti, server MCP, collegamento MCP e interfaccia da terminale.
- Codice sincrono; l'unica parte asincrona è il collegamento MCP, isolata e dichiarata.
- LM Studio sull'host, raggiunto tramite la sua API compatibile con OpenAI.
- Un solo server MCP con FastMCP, trasporto stdio (avviato dal programma come sottoprocesso; log del server su stderr); il catalogo arriva dal server (`tools/list`), mai riscritto a mano nel client.
- Indirizzo del server e identificativo del modello solo da variabili d'ambiente. L'identificativo è quello restituito dal server (`GET /v1/models`), mai inventato.
- Le note sono l'unico dato persistente: file SQLite nella cartella del progetto, escluso da Git (in Docker su volume).
- Un file di configurazione di esempio senza credenziali; il file reale resta fuori da Git.
- Docker Compose per l'applicazione; LM Studio non va containerizzato.
- Dipendenze motivate, concordate e con versioni fissate.
- Comandi documentati anche per PowerShell (Windows).

## Metodo: Superpowers

- Usare le skill di Superpowers per brainstorming, specifica, piano, implementazione e verifica.
- Non scrivere codice prima che io abbia approvato la specifica e poi il piano.
- Salvare specifica e piano in `assistente-laboratorio/docs/superpowers/`.
- Prima di ogni task, avvisarmi (che cosa, su quale branch, quali file); segnare ogni task completato nella checklist del piano.
- Procedere per incrementi piccoli, ciascuno verificato prima del commit.

## Test e verifiche

- Test automatici ripetibili che non richiedono un modello attivo né la rete: grafo, cronologia, instradamento, orologio con istante controllato, server MCP (discovery e invocazione diretta), strumenti con dati locali, SQLite temporaneo, HTTP simulato per il meteo.
- Prove reali con LM Studio, con Docker e con la rete tenute separate e attivate esplicitamente.
- Una risposta simulata non dimostra che il modello locale sappia usare lo strumento.
- Nel resoconto indicare che cosa è stato eseguito, con quale esito, e che cosa resta da provare. Se una prova reale fallisce, registrare il punto esatto senza dichiarare completato il percorso.

## Git

- Un branch `feat/<nome>` per ogni strumento, creato da `dev`; quando è finito e testato, merge in `dev`. Solo quando tutti e sei sono testati e funzionanti, merge di `dev` in `main`. `dev` nasce da `main`. La base MCP comune nasce nel branch del primo strumento (`feat/calcolatrice`).
- Conventional Commits in italiano, per esempio `feat(grafo): ...`, `test(strumenti): ...`, `docs: ...`.
- Prima di ogni commit: `git status`, controllo del diff, staging selettivo dei soli file pertinenti.
- Mai versionare credenziali, `.env`, ambienti virtuali, cache, database delle note o pesi dei modelli.
- Push soltanto su mia richiesta.

## Documentazione

- Tenere aggiornato il README con configurazione, avvio, test e diagnosi, riportando solo comandi verificati.
- Aggiornare questo file quando cambiano convenzioni stabili (struttura, comandi di test, regole di lavoro), non per annotare l'avanzamento.
