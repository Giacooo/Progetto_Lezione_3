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
from langchain_core.messages import ToolMessage

from assistente.collegamento_mcp import carica_preferenze, carica_strumenti_mcp, connessione_stdio
from assistente.configurazione import carica_configurazione, leggi_ambiente
from assistente.conversazione import Conversazione
from assistente.grafo import costruisci_grafo
from assistente.modello import crea_modello
from assistente.revisore import crea_revisore, leggi_valutazione, messaggi_per_revisore
from assistente.router import crea_router
# Importato con un altro nome: pytest raccoglierebbe "testo_rifiuto" come se fosse un test.
from assistente.router import testo_rifiuto as rifiuto
from assistente.strumenti import crea_strumenti

# Due "etichette" applicate a tutti i test del file:
#  - "reale" li raggruppa (si lanciano con: pytest -m reale);
#  - skipif li salta se la variabile d'ambiente PROVE_REALI non vale "1".
pytestmark = [
    pytest.mark.reale,
    pytest.mark.skipif(os.environ.get("PROVE_REALI") != "1", reason="impostare PROVE_REALI=1 con LM Studio attivo"),
]


# Prepara una conversazione VERA a partire da una configurazione: carica gli strumenti MCP dal
# server (discovery), legge le preferenze (resource utente://preferenze, con ripiego sui
# predefiniti), crea lo strumento orologio nel fuso delle preferenze, il modello di LM Studio,
# il router, il revisore e il riassuntore (stesso modello, senza strumenti), poi costruisce il
# grafo. Stesso montaggio, e stesso ordine, di main() in terminale.py.
def crea_conversazione(config):
    connessione = connessione_stdio(Path.cwd())
    strumenti_mcp = carica_strumenti_mcp(connessione)
    preferenze = carica_preferenze(connessione, config.fuso_orario)
    strumenti = crea_strumenti(preferenze.fuso) + strumenti_mcp
    modello = crea_modello(config).bind_tools(strumenti)
    router = crea_router(crea_modello(config))
    revisore = crea_revisore(crea_modello(config))
    riassuntore = crea_modello(config)
    return Conversazione(
        costruisci_grafo(
            modello,
            strumenti,
            config.max_passi,
            router,
            config.ambito,
            revisore,
            config.max_revisioni,
            riassuntore,
            config.soglia_riassunto,
            config.messaggi_da_tenere,
            preferenze,
        )
    )


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
# dell'utente: prima se ne copia il contenuto in memoria; alla fine (anche se la prova fallisce)
# lo si rimette com'era, oppure lo si cancella se prima non esisteva.
@pytest.fixture
def file_preferenze():
    percorso = Path.cwd() / PERCORSO_PREFERENZE
    originale = percorso.read_bytes() if percorso.exists() else None
    percorso.parent.mkdir(exist_ok=True)
    yield percorso
    if originale is None:
        percorso.unlink(missing_ok=True)
    else:
        percorso.write_bytes(originale)


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
