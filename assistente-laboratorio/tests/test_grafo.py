from assistente.grafo import costruisci_grafo_fisso


def test_grafo_fisso_restituisce_la_risposta_prevista():
    chiamate = []
    grafo = costruisci_grafo_fisso(osservatore=chiamate.append)
    risultato = grafo.invoke({"user_text": "ciao"})
    assert risultato["answer"] == "Il grafo è in esecuzione."
    assert risultato["user_text"] == "ciao"
    assert chiamate == ["ciao"]  # nodo eseguito una sola volta, ha letto l'input
