import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from assistente.grafo import PROMPT_SISTEMA, costruisci_grafo
from finti import ORA_FISSA, ModelloFinto, ModelloInsistente, richiesta_ora, strumenti_fissi


def esegui(modello, domanda="domanda", max_passi=5):
    grafo = costruisci_grafo(modello, strumenti_fissi(), max_passi)
    return grafo.invoke({"messages": [HumanMessage(domanda)], "passi": 0})


def test_domanda_ordinaria_una_chiamata():
    modello = ModelloFinto([AIMessage("Parigi")])
    risultato = esegui(modello, "Capitale della Francia?")
    assert len(modello.chiamate) == 1
    inviati = modello.chiamate[0]
    assert isinstance(inviati[0], SystemMessage) and inviati[0].content == PROMPT_SISTEMA
    assert inviati[1].content == "Capitale della Francia?"
    assert risultato["messages"][-1].content == "Parigi"
    assert risultato["passi"] == 1
    assert not any(isinstance(m, ToolMessage) for m in risultato["messages"])


def test_domanda_sull_ora_giro_completo():
    modello = ModelloFinto([richiesta_ora("call_1"), AIMessage("Sono le 12:00.")])
    risultato = esegui(modello, "Che ore sono?")
    messaggi = risultato["messages"]
    assert [type(m) for m in messaggi] == [HumanMessage, AIMessage, ToolMessage, AIMessage]
    strumento = messaggi[2]
    assert strumento.tool_call_id == "call_1"
    assert strumento.content == ORA_FISSA
    assert len(modello.chiamate) == 2
    assert modello.chiamate[1][-1] == strumento
    assert messaggi[-1].content == "Sono le 12:00."
    assert risultato["passi"] == 2


def test_due_richieste_nello_stesso_messaggio():
    doppia = AIMessage(
        "",
        tool_calls=[
            {"name": "ora_corrente", "args": {}, "id": "a"},
            {"name": "ora_corrente", "args": {}, "id": "b"},
        ],
    )
    risultato = esegui(ModelloFinto([doppia, AIMessage("fatto")]))
    risultati = [m for m in risultato["messages"] if isinstance(m, ToolMessage)]
    assert [m.tool_call_id for m in risultati] == ["a", "b"]


def test_strumento_sconosciuto(caplog):
    modello = ModelloFinto([richiesta_ora("x1", nome="meteo"), AIMessage("Non posso.")])
    with caplog.at_level(logging.WARNING, logger="assistente"):
        risultato = esegui(modello)
    strumento = risultato["messages"][2]
    assert isinstance(strumento, ToolMessage)
    assert strumento.tool_call_id == "x1"
    assert strumento.content == "Strumento sconosciuto: meteo"
    assert risultato["messages"][-1].content == "Non posso."
    assert any("meteo" in r.getMessage() for r in caplog.records if r.levelno == logging.WARNING)


def test_limite_passi():
    modello = ModelloInsistente()
    risultato = esegui(modello, max_passi=3)
    assert len(modello.chiamate) == 3
    assert sum(isinstance(m, ToolMessage) for m in risultato["messages"]) == 2
    assert risultato["messages"][-1].tool_calls


def test_log_strumento(caplog):
    modello = ModelloFinto([richiesta_ora(), AIMessage("Sono le 12:00.")])
    with caplog.at_level(logging.INFO, logger="assistente"):
        esegui(modello)
    righe = [r.getMessage() for r in caplog.records]
    assert "Richiesta strumento ora_corrente con argomenti {}" in righe
    assert f"Risultato strumento ora_corrente: {ORA_FISSA}" in righe


def test_log_limite(caplog):
    with caplog.at_level(logging.INFO, logger="assistente"):
        esegui(ModelloInsistente(), max_passi=2)
    avvisi = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any("Limite di passaggi raggiunto" in a for a in avvisi)
