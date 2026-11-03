# COSA PROVA QUESTO FILE
# Il grafo (grafo.py): che il percorso modello -> strumento -> modello funzioni, che
# lo strumento sconosciuto non mandi in crash, che il limite di passaggi fermi il ciclo
# e che le righe di log giuste vengano scritte. Il modello è finto (vedi finti.py).

import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from assistente.grafo import PROMPT_SISTEMA, costruisci_grafo
from finti import ORA_FISSA, ModelloFinto, ModelloInsistente, richiesta_ora, strumenti_fissi


# Funzione di aiuto: costruisce il grafo col modello dato e lo esegue su una domanda.
def esegui(modello, domanda="domanda", max_passi=5):
    grafo = costruisci_grafo(modello, strumenti_fissi(), max_passi)
    return grafo.invoke({"messages": [HumanMessage(domanda)], "passi": 0})


# Domanda ordinaria: il modello risponde subito, quindi UNA sola chiamata al modello,
# nessun messaggio di strumento, e il modello riceve prima il prompt di sistema e poi la domanda.
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


# Domanda sull'ora: il giro completo. Il modello chiede lo strumento, il programma lo
# esegue e restituisce ORA_FISSA, il modello risponde. Due chiamate al modello in tutto.
def test_domanda_sull_ora_giro_completo():
    modello = ModelloFinto([richiesta_ora("call_1"), AIMessage("Sono le 12:00.")])
    risultato = esegui(modello, "Che ore sono?")
    messaggi = risultato["messages"]
    assert [type(m) for m in messaggi] == [HumanMessage, AIMessage, ToolMessage, AIMessage]
    strumento = messaggi[2]
    assert strumento.tool_call_id == "call_1"
    assert strumento.content == ORA_FISSA
    assert len(modello.chiamate) == 2
    # Alla seconda chiamata il modello vede, per ultimo, il risultato dello strumento.
    assert modello.chiamate[1][-1] == strumento
    assert messaggi[-1].content == "Sono le 12:00."
    assert risultato["passi"] == 2


# Se il modello chiede lo strumento due volte nello stesso messaggio, vengono eseguite
# entrambe e ogni risultato è collegato alla sua richiesta (id "a" e "b").
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


# Se il modello chiede uno strumento che non esiste ("meteo"), il programma non va in crash:
# risponde "Strumento sconosciuto", lascia un avviso nel log e il turno si conclude.
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


# Il freno di sicurezza: un modello che chiede sempre lo strumento viene fermato dopo
# 3 chiamate (il limite). Gli strumenti eseguiti sono 2 e l'ultimo messaggio è ancora una richiesta aperta.
def test_limite_passi():
    modello = ModelloInsistente()
    risultato = esegui(modello, max_passi=3)
    assert len(modello.chiamate) == 3
    assert sum(isinstance(m, ToolMessage) for m in risultato["messages"]) == 2
    assert risultato["messages"][-1].tool_calls


# Nel log compaiono le righe che mostrano la richiesta dello strumento e il suo risultato:
# sono la "prova" che lo strumento è stato eseguito davvero.
def test_log_strumento(caplog):
    modello = ModelloFinto([richiesta_ora(), AIMessage("Sono le 12:00.")])
    with caplog.at_level(logging.INFO, logger="assistente"):
        esegui(modello)
    righe = [r.getMessage() for r in caplog.records]
    assert "Richiesta strumento ora_corrente con argomenti {}" in righe
    assert f"Risultato strumento ora_corrente: {ORA_FISSA}" in righe


# Quando si raggiunge il limite, nel log compare l'avviso "Limite di passaggi raggiunto".
def test_log_limite(caplog):
    with caplog.at_level(logging.INFO, logger="assistente"):
        esegui(ModelloInsistente(), max_passi=2)
    avvisi = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any("Limite di passaggi raggiunto" in a for a in avvisi)
