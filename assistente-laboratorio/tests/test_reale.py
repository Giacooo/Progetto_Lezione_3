"""Prove con LM Studio attivo: si eseguono solo con PROVE_REALI=1.

Verificano che il modello reale richieda lo strumento quando serve, cosa che un
modello simulato non può dimostrare.
"""

import os
from pathlib import Path

import pytest
from langchain_core.messages import ToolMessage

from assistente.configurazione import carica_configurazione, leggi_ambiente
from assistente.conversazione import Conversazione
from assistente.grafo import costruisci_grafo
from assistente.modello import crea_modello
from assistente.strumenti import crea_strumenti

pytestmark = [
    pytest.mark.reale,
    pytest.mark.skipif(os.environ.get("PROVE_REALI") != "1", reason="impostare PROVE_REALI=1 con LM Studio attivo"),
]


@pytest.fixture
def conversazione():
    config = carica_configurazione(leggi_ambiente(Path.cwd()))
    strumenti = crea_strumenti(config.fuso_orario)
    modello = crea_modello(config).bind_tools(strumenti)
    return Conversazione(costruisci_grafo(modello, strumenti, config.max_passi))


def strumenti_usati(conversazione):
    return [m.name for m in conversazione.cronologia if isinstance(m, ToolMessage)]


def test_domanda_sull_ora_usa_lo_strumento(conversazione):
    risposta = conversazione.chiedi("Che ore sono adesso?")
    assert strumenti_usati(conversazione) == ["ora_corrente"]
    assert risposta


def test_domanda_ordinaria_senza_strumento(conversazione):
    conversazione.chiedi("Qual è la capitale della Francia?")
    assert strumenti_usati(conversazione) == []
