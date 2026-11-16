"""Prove con LM Studio attivo: si eseguono solo con PROVE_REALI=1.

Verificano che il modello reale richieda lo strumento quando serve, cosa che un
modello simulato non può dimostrare.
"""

# COSA PROVA QUESTO FILE
# A differenza degli altri test, qui NON c'è nulla di finto: si usa il modello vero di
# LM Studio, che deve essere acceso. Per questo i test restano "saltati" (skipped) finché
# non si imposta la variabile PROVE_REALI=1.
# Il modello è non deterministico: una prova può riuscire o fallire in esecuzioni diverse.
# Le conversazioni leggono le preferenze vere (archivio/preferenze.json) come main(); le prove
# dello step 4 cambiano quel file e alla fine lo rimettono com'era.

import dataclasses
import logging
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import ToolMessage
from protezione_preferenze import preferenze_protette

from assistente.agente import costruisci_agente
from assistente.cliente import ClienteAgente
from assistente.collegamento_mcp import connessione_stdio, richiama_prompt_mcp
from assistente.configurazione import carica_configurazione, leggi_ambiente
from assistente.conversazione import Conversazione
from assistente.modello import crea_modello
from assistente.revisore import crea_revisore, leggi_valutazione, messaggi_per_revisore
from assistente.servizio import crea_app
# Importato con un altro nome: pytest raccoglierebbe "testo_rifiuto" come se fosse un test.
from assistente.router import testo_rifiuto as rifiuto
from backend.agente_remoto import AgenteRemoto
from backend.app import crea_app as crea_app_backend
from backend.archivio import ArchivioPostgres
from finti_backend import archivio_postgres_vuoto, salta_senza_postgres

# Due "etichette" applicate a tutti i test del file:
#  - "reale" li raggruppa (si lanciano con: pytest -m reale);
#  - skipif li salta se la variabile d'ambiente PROVE_REALI non vale "1".
pytestmark = [
    pytest.mark.reale,
    pytest.mark.skipif(os.environ.get("PROVE_REALI") != "1", reason="impostare PROVE_REALI=1 con LM Studio attivo"),
]


# Prepara una conversazione VERA a partire da una configurazione. Dallo step 6 il montaggio
# (discovery, preferenze, orologio nel fuso delle preferenze, modello, router, revisore,
# riassuntore, grafo) è quello di costruisci_agente(), lo stesso usato dal servizio HTTP;
# la Conversazione tiene in memoria cronologia e riassunto tra i turni.
def crea_conversazione(config):
    return Conversazione(costruisci_agente(config, Path.cwd()).grafo)


# Per ogni test, una conversazione vera con la configurazione del .env.
@pytest.fixture
def conversazione():
    return crea_conversazione(carica_configurazione(leggi_ambiente(Path.cwd())))


# Funzione di aiuto: elenca i nomi degli strumenti realmente eseguiti nella cronologia.
def strumenti_usati(conversazione):
    return [m.name for m in conversazione.cronologia if isinstance(m, ToolMessage)]


# Per una domanda sull'ora, il modello vero deve chiedere ESATTAMENTE lo strumento ora_corrente
# (e dare una risposta non vuota).
def test_domanda_sull_ora_usa_lo_strumento(conversazione):
    risposta = conversazione.chiedi("Che ore sono adesso?")
    assert strumenti_usati(conversazione) == ["ora_corrente"]
    assert risposta


# Per una domanda ordinaria, il modello vero NON deve chiedere nessuno strumento.
# (Dalla lezione 6 è un saluto: «Qual è la capitale della Francia?» ora è fuori ambito.)
def test_domanda_ordinaria_senza_strumento(conversazione):
    conversazione.chiedi("Ciao, come stai?")
    assert strumenti_usati(conversazione) == []


# Per una moltiplicazione il modello vero deve usare ESATTAMENTE lo strumento MCP calcola
# e riportare il risultato (7006652), anche se scritto con spazi o punti.
def test_calcolo_usa_calcola(conversazione):
    risposta = conversazione.chiedi("Quanto fa 1234 per 5678?")
    assert strumenti_usati(conversazione) == ["calcola"]
    assert "7006652" in risposta.replace(" ", "").replace(".", "")


# Per una conversione di unita' il modello vero deve usare ESATTAMENTE lo strumento MCP
# converti_unita (10 km = 6.2137 mi).
def test_conversione_usa_converti_unita(conversazione):
    conversazione.chiedi("Quanti miglia sono 10 km?")
    assert strumenti_usati(conversazione) == ["converti_unita"]


# Per un conteggio di giorni lavorativi il modello vero deve usare ESATTAMENTE lo strumento MCP
# conta_giorni (traducendo le date italiane nel formato AAAA-MM-GG).
def test_giorni_lavorativi_usa_conta_giorni(conversazione):
    conversazione.chiedi("Quanti giorni lavorativi ci sono tra il 23 e il 28 dicembre 2026?")
    assert "conta_giorni" in strumenti_usati(conversazione)


# Per una domanda che richiede ricerca e poi dettaglio, il modello vero deve usare in sequenza
# cerca_corsi e dettaglio_corso. Se ne usa uno solo, registrarlo come esito della prova.
def test_durata_corso_usa_cerca_e_dettaglio(conversazione):
    conversazione.chiedi("Quanto dura il corso di Python a Udine?")
    assert strumenti_usati(conversazione) == ["cerca_corsi", "dettaglio_corso"]


# Per «Ricordami di ...» il modello vero deve usare ESATTAMENTE aggiungi_nota. Scrive nell'archivio
# vero del progetto (archivio/note.sqlite): dopo la prova eliminare la nota o il file.
def test_ricordami_usa_aggiungi_nota(conversazione):
    conversazione.chiedi("Ricordami di consegnare il report venerdì")
    assert strumenti_usati(conversazione) == ["aggiungi_nota"]


# Richiede anche la rete (Open-Meteo): il modello vero deve usare ESATTAMENTE meteo_citta.
def test_che_tempo_fa_usa_meteo_citta(conversazione):
    conversazione.chiedi("Che tempo fa a Pordenone?")
    assert strumenti_usati(conversazione) == ["meteo_citta"]


# Lezione 6, step 1: una domanda fuori ambito riceve il rifiuto fisso e il nodo dell'agente
# non viene eseguito (nel log nessuna riga "Inizio chiamata al modello").
def test_domanda_fuori_ambito_rifiutata(conversazione, caplog):
    caplog.set_level(logging.INFO, logger="assistente")
    ambito = carica_configurazione(leggi_ambiente(Path.cwd())).ambito
    risposta = conversazione.chiedi("Raccontami la storia di Roma")
    assert risposta == rifiuto(ambito)
    righe = [r.getMessage() for r in caplog.records]
    assert any("router categoria=fuori ambito" in r and "next_node=rifiuto" in r for r in righe)
    assert not any("Inizio chiamata al modello" in r for r in righe)
    assert strumenti_usati(conversazione) == []


# ---------------- REVISORE (lezione 6, step 2) ----------------

# Le righe del log con la decisione del revisore («revisore coerente=...»).
def righe_revisore(caplog):
    return [r.getMessage() for r in caplog.records if r.getMessage().startswith("revisore coerente=")]


# Evidenza del PDF con il modello vero: domanda in due parti. Il turno deve finire con una
# risposta approvata (al primo passaggio o dopo una revisione) entro il limite. Il log dice
# quale dei due casi è successo: se c'è una riga «coerente=no» prima, c'è stata una correzione.
def test_domanda_in_due_parti(conversazione, caplog):
    caplog.set_level(logging.INFO, logger="assistente")
    risposta = conversazione.chiedi("Che ore sono e che tempo fa a Pordenone?")
    assert risposta
    righe = righe_revisore(caplog)
    assert righe
    assert "coerente=sì" in righe[-1]


# Evidenza del PDF con il modello vero: una risposta coerente è approvata al primo passaggio.
def test_risposta_coerente_approvata_al_primo_passaggio(conversazione, caplog):
    caplog.set_level(logging.INFO, logger="assistente")
    conversazione.chiedi("Ciao, come stai?")
    righe = righe_revisore(caplog)
    assert len(righe) == 1
    assert "coerente=sì" in righe[0]


# Evidenza minima del PDF con il modello vero: davanti a una risposta parziale preparata dal
# test (risponde solo all'ora, non al meteo) il revisore deve dire «no» con un motivo.
# Chiama direttamente il revisore: serve anche se nel grafo intero gemma risponde bene subito.
def test_revisore_boccia_una_risposta_parziale():
    config = carica_configurazione(leggi_ambiente(Path.cwd()))
    revisore = crea_revisore(crea_modello(config))
    letto = leggi_valutazione(
        revisore.invoke(messaggi_per_revisore("Che ore sono e che tempo fa a Pordenone?", "Sono le 10:30."))
    )
    assert letto is not None
    assert letto[0] == "no"
    assert letto[1]


# ---------------- RIASSUNTO (lezione 6, step 3) ----------------

# Evidenza minima del PDF con il modello vero: un'informazione data al primo turno (il nome) è
# ancora usata dopo la compressione. Soglia bassa impostata dal test (non dal .env): 4 messaggi,
# ne restano 2. Al terzo turno la cronologia supera la soglia e il primo turno viene riassunto.
def test_nome_usato_dopo_la_compressione(caplog):
    config = dataclasses.replace(
        carica_configurazione(leggi_ambiente(Path.cwd())), soglia_riassunto=4, messaggi_da_tenere=2
    )
    conv = crea_conversazione(config)
    caplog.set_level(logging.INFO, logger="assistente")
    conv.chiedi("Mi chiamo Luca")
    conv.chiedi("Che ore sono?")
    conv.chiedi("Quanto fa 12 per 3?")
    risposta = conv.chiedi("Come mi chiamo?")
    assert any(r.getMessage().startswith("riassunto messaggi prima=") for r in caplog.records)
    assert all(m.text != "Mi chiamo Luca" for m in conv.cronologia)
    assert "luca" in risposta.lower()


# ---------------- PREFERENZE (lezione 6, step 4) ----------------

# Il file delle preferenze VERO dell'utente (lo stesso che legge il server MCP).
PERCORSO_PREFERENZE = Path("archivio/preferenze.json")


# Queste prove cambiano o tolgono il file delle preferenze. Per NON distruggere quello
# dell'utente: prima se ne fa una copia su disco (archivio/preferenze.json.bak); alla fine
# (anche se la prova fallisce) lo si rimette com'era, oppure lo si cancella se prima non
# esisteva. Se la serie viene interrotta, la copia resta su disco (vedi README).
@pytest.fixture
def file_preferenze():
    with preferenze_protette(Path.cwd() / PERCORSO_PREFERENZE) as percorso:
        yield percorso


# I risultati dello strumento ora_corrente nella cronologia (es. "...-05:00 (America/New_York)").
def risultati_orologio(conversazione):
    return [m.text for m in conversazione.cronologia if isinstance(m, ToolMessage) and m.name == "ora_corrente"]


# Evidenza del PDF: con un fuso non ovvio nelle preferenze (America/New_York), «Che ore sono?»
# usa quel fuso senza chiederlo: il modello chiama solo ora_corrente e il risultato termina con
# (America/New_York). La lettura compare una volta nei log, come riga separata dai tool.
def test_ora_nel_fuso_delle_preferenze(file_preferenze, caplog):
    testo = '{"lingua": "italiano", "fuso_orario": "America/New_York", "stile": "sintetico"}'
    file_preferenze.write_text(testo, encoding="utf-8")
    caplog.set_level(logging.INFO, logger="assistente")
    conv = crea_conversazione(carica_configurazione(leggi_ambiente(Path.cwd())))
    risposta = conv.chiedi("Che ore sono?")
    assert risposta
    assert strumenti_usati(conv) == ["ora_corrente"]
    assert all(r.endswith("(America/New_York)") for r in risultati_orologio(conv))
    letture = [r.getMessage() for r in caplog.records if r.getMessage().startswith("preferenze lette ")]
    assert letture == ["preferenze lette uri=utente://preferenze lingua=italiano fuso=America/New_York stile=sintetico"]


# Resource non disponibile (nessun file): la sessione parte lo stesso, i log riportano il
# WARNING con i valori predefiniti e l'orologio usa il fuso di ripiego, quello di FUSO_ORARIO.
def test_preferenze_assenti_usano_il_fuso_del_env(file_preferenze, caplog):
    file_preferenze.unlink(missing_ok=True)
    config = carica_configurazione(leggi_ambiente(Path.cwd()))
    caplog.set_level(logging.INFO, logger="assistente")
    conv = crea_conversazione(config)
    conv.chiedi("Che ore sono?")
    assert any(r.getMessage().startswith("preferenze non disponibili (") for r in caplog.records)
    risultati = risultati_orologio(conv)
    assert risultati
    assert all(r.endswith(f"({config.fuso_orario.key})") for r in risultati)


# ---------------- PROMPT MCP (lezione 6, step 5) ----------------
# Stesso percorso del comando /prompt, senza tastiera: richiamo del prompt dal server vero
# (prompts/list, controllo, prompts/get) e turno nel grafo con i messaggi ottenuti.

# Evidenza del PDF: /prompt spiega argomento="Model Context Protocol" livello=base. Il prompt
# passa dal router (classificato "conversazione", grazie all'ambito allargato nel .env) e dal
# revisore; la risposta non è il rifiuto. L'adeguatezza al livello si osserva a mano.
def test_prompt_spiega(conversazione, caplog):
    caplog.set_level(logging.INFO, logger="assistente")
    ambito = carica_configurazione(leggi_ambiente(Path.cwd())).ambito
    messaggi = richiama_prompt_mcp(
        connessione_stdio(Path.cwd()), "spiega", {"argomento": "Model Context Protocol", "livello": "base"}
    )
    risposta = conversazione.chiedi_messaggi(messaggi)
    assert risposta and risposta != rifiuto(ambito)
    righe = [r.getMessage() for r in caplog.records]
    assert any(r.startswith("router categoria=conversazione") for r in righe)
    assert any(r.startswith("revisore coerente=") for r in righe)


# Evidenza del PDF: riassumi_conversazione riassume i turni della sessione corrente (il nome
# dato al primo turno e il risultato del calcolo del secondo).
def test_prompt_riassumi_conversazione(conversazione):
    conversazione.chiedi("Mi chiamo Luca")
    conversazione.chiedi("Quanto fa 45 diviso 9?")
    messaggi = richiama_prompt_mcp(connessione_stdio(Path.cwd()), "riassumi_conversazione", {"stile": "sintetico"})
    risposta = conversazione.chiedi_messaggi(messaggi)
    assert "luca" in risposta.lower()
    assert "5" in risposta


# ---------------- AGENTE COME SERVIZIO HTTP (lezione 6, step 6) ----------------
# Il servizio FastAPI con l'agente VERO (costruisci_agente: server MCP, modello, grafo), chiamato
# con il TestClient di FastAPI: le richieste HTTP non passano dalla rete, ma attraversano
# esattamente gli stessi endpoint, gli stessi controlli e lo stesso grafo del servizio avviato
# con "python -m assistente.servizio".

DOMANDA_CALCOLO = "Quanto fa 45 diviso 9?"


# Per ogni test, il servizio con l'agente vero e la configurazione del .env.
@pytest.fixture
def servizio():
    agente = costruisci_agente(carica_configurazione(leggi_ambiente(Path.cwd())), Path.cwd())
    return TestClient(crea_app(agente))


# Evidenza del PDF: messaggio -> risposta + strumenti usati. Il modello vero usa calcola e la
# risposta contiene il risultato.
def test_api_domanda_con_strumento(servizio):
    risposta = servizio.post("/messaggio", json={"messaggio": DOMANDA_CALCOLO})
    assert risposta.status_code == 200
    corpo = risposta.json()
    assert "calcola" in [s["nome"] for s in corpo["strumenti_usati"]]
    assert "5" in corpo["risposta"]


# Gli strumenti usati in un turno, ricavati dalla cronologia JSON restituita dall'API: per ogni
# richiesta dell'assistente, nome, argomenti e il risultato del messaggio "strumento" abbinato.
def strumenti_dalla_cronologia(cronologia):
    risultati = {m["id_chiamata"]: m["testo"] for m in cronologia if m["ruolo"] == "strumento"}
    return [
        {"nome": r["nome"], "argomenti": r["argomenti"], "risultato": risultati[r["id"]]}
        for m in cronologia
        if m["ruolo"] == "assistente"
        for r in m.get("richieste_strumenti", [])
        if r["id"] in risultati
    ]


# Evidenza del PDF: lo stesso grafo risponde alla CLI e alle chiamate HTTP. La stessa domanda
# deterministica va all'agente due volte: con ClienteAgente (il client che usa la CLI) e con un
# POST /messaggio diretto. Stesso strumento con gli stessi argomenti, stesso risultato (5), e
# tutte e due le risposte contengono 5. (Il testo esatto può cambiare: il modello non è
# deterministico.)
def test_stessa_risposta_da_cli_e_api(servizio):
    cliente = ClienteAgente("http://testserver", client=servizio)
    risposta_cli = cliente.chiedi(DOMANDA_CALCOLO)
    dalla_cli = strumenti_dalla_cronologia(cliente.cronologia)

    corpo = servizio.post("/messaggio", json={"messaggio": DOMANDA_CALCOLO}).json()
    dall_api = corpo["strumenti_usati"]

    assert [s["nome"] for s in dalla_cli] == ["calcola"]
    assert dalla_cli == dall_api
    assert dall_api[0]["risultato"] == "5"
    assert "5" in risposta_cli
    assert "5" in corpo["risposta"]


# Evidenza del PDF: endpoint di stato. Con LM Studio acceso e il modello caricato, le tre voci
# (agente, server MCP, modello) sono "ok" e il codice è 200.
def test_api_stato_ok(servizio):
    risposta = servizio.get("/stato")
    assert risposta.status_code == 200
    assert risposta.json() == {"agente": "ok", "server_mcp": "ok", "modello": "ok"}


# ---------------- Lezione 6, step 7: il back-end ----------------

# Back-end vero + agente vero + LM Studio + PostgreSQL (database di prova <POSTGRES_DB>_prove):
# serve anche PROVE_POSTGRES=1 con il container db acceso. L'agente è quello dello step 6
# (costruisci_agente) raggiunto con il TestClient al posto della rete: il back-end lo chiama
# comunque solo attraverso la sua API HTTP (AgenteRemoto).
# Evidenze: la domanda con uno strumento viene salvata con gli strumenti usati; al secondo turno
# la memoria dell'agente arriva dal database; dopo il "riavvio" (app e archivio nuovi sullo
# stesso database) la chat c'è ancora.
def test_backend_chat_con_strumento():
    salta_senza_postgres()
    agente = costruisci_agente(carica_configurazione(leggi_ambiente(Path.cwd())), Path.cwd())
    remoto = AgenteRemoto("http://agente", client=TestClient(crea_app(agente)))
    archivio = archivio_postgres_vuoto()
    backend = TestClient(crea_app_backend(archivio, remoto))

    chat = backend.post("/chat").json()
    primo = backend.post(f"/chat/{chat['id']}/messaggi", json={"messaggio": "Quanto fa 45 diviso 9?"})
    assert primo.status_code == 200, primo.text
    assert "calcola" in [s["nome"] for s in primo.json()["risposta"]["strumenti_usati"]]
    assert "5" in primo.json()["risposta"]["testo"]

    secondo = backend.post(f"/chat/{chat['id']}/messaggi", json={"messaggio": "E se aggiungo 10?"})
    assert secondo.status_code == 200, secondo.text
    assert "15" in secondo.json()["risposta"]["testo"]

    # "Riavvio": un back-end nuovo con un archivio nuovo sullo stesso database.
    riavviato = TestClient(crea_app_backend(ArchivioPostgres(archivio.parametri), remoto))
    letta = riavviato.get(f"/chat/{chat['id']}").json()
    assert [m["ruolo"] for m in letta["messaggi"]] == ["utente", "assistente", "utente", "assistente"]
    assert letta["titolo"] == "Quanto fa 45 diviso 9?"
