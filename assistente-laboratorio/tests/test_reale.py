"""Prove con LM Studio attivo: si eseguono solo con PROVE_REALI=1.

Verificano che il modello reale richieda lo strumento quando serve, cosa che un
modello simulato non può dimostrare.
"""

# COSA PROVA QUESTO FILE
# A differenza degli altri test, qui NON c'è nulla di finto: si usa il modello vero di
# LM Studio, che deve essere acceso. Per questo i test restano "saltati" (skipped) finché
# non si imposta la variabile PROVE_REALI=1.
# Il modello è non deterministico: una prova può riuscire o fallire in esecuzioni diverse.

import logging
import os
from pathlib import Path

import pytest
from langchain_core.messages import ToolMessage

from assistente.collegamento_mcp import carica_strumenti_mcp, connessione_stdio
from assistente.configurazione import carica_configurazione, leggi_ambiente
from assistente.conversazione import Conversazione
from assistente.grafo import costruisci_grafo
from assistente.modello import crea_modello
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


# Prepara, per ogni test, una conversazione VERA: legge il .env, crea lo strumento orologio,
# carica gli strumenti MCP dal server (discovery), crea il modello di LM Studio e il router
# (stesso modello, senza strumenti), poi costruisce il grafo. Stesso montaggio di main() in terminale.py.
@pytest.fixture
def conversazione():
    config = carica_configurazione(leggi_ambiente(Path.cwd()))
    strumenti = crea_strumenti(config.fuso_orario) + carica_strumenti_mcp(connessione_stdio(Path.cwd()))
    modello = crea_modello(config).bind_tools(strumenti)
    router = crea_router(crea_modello(config))
    return Conversazione(costruisci_grafo(modello, strumenti, config.max_passi, router, config.ambito))


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
