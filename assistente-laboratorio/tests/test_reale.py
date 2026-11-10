"""Prove con LM Studio attivo: si eseguono solo con PROVE_REALI=1.

Verificano che il modello reale richieda lo strumento quando serve, cosa che un
modello simulato non può dimostrare.
"""

# COSA PROVA QUESTO FILE
# A differenza degli altri test, qui NON c'è nulla di finto: si usa il modello vero di
# LM Studio, che deve essere acceso. Per questo i test restano "saltati" (skipped) finché
# non si imposta la variabile PROVE_REALI=1.
# Il modello è non deterministico: una prova può riuscire o fallire in esecuzioni diverse.

import os
from pathlib import Path

import pytest
from langchain_core.messages import ToolMessage

from assistente.collegamento_mcp import carica_strumenti_mcp, connessione_stdio
from assistente.configurazione import carica_configurazione, leggi_ambiente
from assistente.conversazione import Conversazione
from assistente.grafo import costruisci_grafo
from assistente.modello import crea_modello
from assistente.strumenti import crea_strumenti

# Due "etichette" applicate a tutti i test del file:
#  - "reale" li raggruppa (si lanciano con: pytest -m reale);
#  - skipif li salta se la variabile d'ambiente PROVE_REALI non vale "1".
pytestmark = [
    pytest.mark.reale,
    pytest.mark.skipif(os.environ.get("PROVE_REALI") != "1", reason="impostare PROVE_REALI=1 con LM Studio attivo"),
]


# Prepara, per ogni test, una conversazione VERA: legge il .env, crea lo strumento orologio,
# carica gli strumenti MCP dal server (discovery) e crea il modello di LM Studio, poi
# costruisce il grafo. Stesso montaggio di main() in terminale.py.
@pytest.fixture
def conversazione():
    config = carica_configurazione(leggi_ambiente(Path.cwd()))
    strumenti = crea_strumenti(config.fuso_orario) + carica_strumenti_mcp(connessione_stdio(Path.cwd()))
    modello = crea_modello(config).bind_tools(strumenti)
    return Conversazione(costruisci_grafo(modello, strumenti, config.max_passi))


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
def test_domanda_ordinaria_senza_strumento(conversazione):
    conversazione.chiedi("Qual è la capitale della Francia?")
    assert strumenti_usati(conversazione) == []


# Per una moltiplicazione il modello vero deve usare ESATTAMENTE lo strumento MCP calcola
# e riportare il risultato (7006652), anche se scritto con spazi o punti.
def test_calcolo_usa_calcola(conversazione):
    risposta = conversazione.chiedi("Quanto fa 1234 per 5678?")
    assert strumenti_usati(conversazione) == ["calcola"]
    assert "7006652" in risposta.replace(" ", "").replace(".", "")
