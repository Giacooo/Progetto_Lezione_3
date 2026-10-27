from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from assistente.grafo import PROMPT_SISTEMA, costruisci_grafo
from finti import ModelloFinto


def test_domanda_ordinaria_una_chiamata():
    modello = ModelloFinto([AIMessage("Parigi")])
    grafo = costruisci_grafo(modello)
    risultato = grafo.invoke({"messages": [HumanMessage("Capitale della Francia?")], "passi": 0})
    assert len(modello.chiamate) == 1
    inviati = modello.chiamate[0]
    assert isinstance(inviati[0], SystemMessage) and inviati[0].content == PROMPT_SISTEMA
    assert inviati[1].content == "Capitale della Francia?"
    assert risultato["messages"][-1].content == "Parigi"
    assert risultato["passi"] == 1
