# COSA PROVA QUESTO FILE
# Il grafo (grafo.py): che il percorso modello -> strumento -> modello funzioni, che
# lo strumento sconosciuto non mandi in crash, che il limite di passaggi fermi il ciclo
# e che le righe di log giuste vengano scritte. Il modello è finto (vedi finti.py).

import logging
from types import SimpleNamespace

import openai
import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from assistente.errori import ErroreCollegamentoMCP, ErroreStrumento
from assistente.grafo import PROMPT_SISTEMA, costruisci_grafo
from assistente.router import prompt_router
# Importato con un altro nome: pytest raccoglierebbe "testo_rifiuto" come se fosse un test.
from assistente.router import testo_rifiuto as rifiuto
from finti import (
    ORA_FISSA,
    ModelloFinto,
    ModelloInsistente,
    RouterFinto,
    classificazione,
    richiesta,
    richiesta_ora,
    router_sempre_conversazione,
    strumenti_fissi,
    strumento_finto,
)

# L'ambito usato nei test (nell'applicazione viene da AMBITO_AGENTE).
AMBITO = "data e ora, meteo"


# Funzione di aiuto: costruisce il grafo col modello dato e lo esegue su una domanda.
# Se il test non passa un router, quello finto risponde sempre "conversazione":
# così si arriva sempre all'agente, come prima dello step 1.
def esegui(modello, domanda="domanda", max_passi=5, extra=(), router=None, cronologia=()):
    router = router or router_sempre_conversazione()
    grafo = costruisci_grafo(modello, [*strumenti_fissi(), *extra], max_passi, router, AMBITO)
    return grafo.invoke({"messages": [*cronologia, HumanMessage(domanda)], "passi": 0})


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


# Strumento locale: il log ha le tre righe chiave=valore (variante, esito, correlazione):
# sono la "prova" che lo strumento è stato eseguito davvero.
def test_log_strumento_locale(caplog):
    modello = ModelloFinto([richiesta_ora("call_1"), AIMessage("Sono le 12:00.")])
    with caplog.at_level(logging.INFO, logger="assistente.grafo"):
        esegui(modello)
    righe = [r.getMessage() for r in caplog.records]
    assert "variant=local tool=ora_corrente call_id=call_1 arguments={}" in righe
    assert f"variant=local tool=ora_corrente call_id=call_1 execution=ok result={ORA_FISSA}" in righe
    assert "tool_message.call_id=call_1 next_node=llm" in righe


# Strumento MCP che funziona: il risultato arriva nel ToolMessage e nel log.
def test_strumento_mcp_ok(caplog):
    calcola = strumento_finto("calcola", lambda argomenti: "14")
    modello = ModelloFinto([richiesta("calcola", {"espressione": "2+3*4"}, "c1"), AIMessage("14")])
    with caplog.at_level(logging.INFO, logger="assistente.grafo"):
        risultato = esegui(modello, extra=[calcola])
    messaggio = risultato["messages"][2]
    assert isinstance(messaggio, ToolMessage)
    assert (messaggio.content, messaggio.tool_call_id, messaggio.name) == ("14", "c1", "calcola")
    righe = [r.getMessage() for r in caplog.records]
    assert 'variant=mcp tool=calcola call_id=c1 arguments={"espressione": "2+3*4"}' in righe
    assert "variant=mcp tool=calcola call_id=c1 execution=ok result=14" in righe


# Errore dello strumento: diventa un ToolMessage correlato e il grafo torna al modello.
def test_errore_dello_strumento_correlato(caplog):
    def rifiuta(argomenti):
        raise ErroreStrumento("costrutto non ammesso: Call")

    calcola = strumento_finto("calcola", rifiuta)
    modello = ModelloFinto([richiesta("calcola", {"espressione": "f()"}, "c1"), AIMessage("Non posso.")])
    with caplog.at_level(logging.INFO, logger="assistente.grafo"):
        risultato = esegui(modello, extra=[calcola])
    messaggio = risultato["messages"][2]
    assert isinstance(messaggio, ToolMessage)
    assert messaggio.content == "Errore dello strumento: costrutto non ammesso: Call"
    assert messaggio.tool_call_id == "c1"
    assert len(modello.chiamate) == 2
    assert risultato["messages"][-1].content == "Non posso."
    atteso = "variant=mcp tool=calcola call_id=c1 execution=tool_error result=Errore dello strumento: costrutto non ammesso: Call"
    assert atteso in [r.getMessage() for r in caplog.records]


# Errore di collegamento col server MCP: il turno non si interrompe.
def test_errore_di_collegamento_correlato(caplog):
    def cade(argomenti):
        raise ErroreCollegamentoMCP("processo terminato")

    calcola = strumento_finto("calcola", cade)
    modello = ModelloFinto([richiesta("calcola", {"espressione": "1+1"}, "c2"), AIMessage("Server non disponibile.")])
    with caplog.at_level(logging.INFO, logger="assistente.grafo"):
        risultato = esegui(modello, extra=[calcola])
    messaggio = risultato["messages"][2]
    assert messaggio.content == "Errore di collegamento con il server MCP: processo terminato"
    assert messaggio.tool_call_id == "c2"
    assert risultato["messages"][-1].content == "Server non disponibile."
    assert any("execution=connection_error" in r.getMessage() for r in caplog.records)


# Strumento sconosciuto: variante ed esecuzione "unknown", contenuto invariato.
def test_log_strumento_sconosciuto(caplog):
    modello = ModelloFinto([richiesta_ora("x1", nome="meteo"), AIMessage("Non posso.")])
    with caplog.at_level(logging.INFO, logger="assistente.grafo"):
        esegui(modello)
    atteso = "variant=unknown tool=meteo call_id=x1 execution=unknown_tool result=Strumento sconosciuto: meteo"
    assert atteso in [r.getMessage() for r in caplog.records]


# Il risultato nel log è troncato a 200 caratteri; il ToolMessage resta intero.
def test_risultato_log_troncato(caplog):
    lungo = strumento_finto("lungo", lambda argomenti: "x" * 500)
    modello = ModelloFinto([richiesta("lungo", {}, "c1"), AIMessage("ok")])
    with caplog.at_level(logging.INFO, logger="assistente.grafo"):
        risultato = esegui(modello, extra=[lungo])
    assert risultato["messages"][2].content == "x" * 500
    assert "variant=mcp tool=lungo call_id=c1 execution=ok result=" + "x" * 200 in [r.getMessage() for r in caplog.records]


# Il limite di passi vale anche per gli strumenti MCP.
def test_limite_passi_con_strumento_mcp():
    class Insiste:
        def __init__(self):
            self.chiamate = []

        def invoke(self, messaggi):
            self.chiamate.append(list(messaggi))
            return richiesta("calcola", {"espressione": "1+1"}, f"c{len(self.chiamate)}")

    modello = Insiste()
    esegui(modello, max_passi=3, extra=[strumento_finto("calcola", lambda argomenti: "2")])
    assert len(modello.chiamate) == 3


# Quando si raggiunge il limite, nel log compare l'avviso "Limite di passaggi raggiunto".
def test_log_limite(caplog):
    with caplog.at_level(logging.INFO, logger="assistente"):
        esegui(ModelloInsistente(), max_passi=2)
    avvisi = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any("Limite di passaggi raggiunto" in a for a in avvisi)


# ---------------- ROUTER (lezione 6, step 1) ----------------

# Domanda in ambito: il router dice "conversazione", l'agente viene chiamato e il log
# mostra categoria, motivo e passaggio all'agente.
def test_router_conversazione_passa_all_agente(caplog):
    router = RouterFinto([classificazione("conversazione", "saluto")])
    modello = ModelloFinto([AIMessage("Ciao!")])
    with caplog.at_level(logging.INFO, logger="assistente.grafo"):
        risultato = esegui(modello, "Ciao", router=router)
    assert len(modello.chiamate) == 1
    assert risultato["messages"][-1].content == "Ciao!"
    righe = [r.getMessage() for r in caplog.records]
    assert "router categoria=conversazione motivo=saluto next_node=llm (agente)" in righe
    assert "Inizio chiamata al modello (passo 1/5)" in righe


# Domanda fuori ambito: rifiuto fisso e il nodo dell'agente non viene mai eseguito.
def test_router_fuori_ambito_non_esegue_l_agente(caplog):
    router = RouterFinto([classificazione("fuori ambito", "storia")])
    modello = ModelloFinto([])
    with caplog.at_level(logging.INFO, logger="assistente.grafo"):
        risultato = esegui(modello, "Raccontami la storia di Roma", router=router)
    assert modello.chiamate == []
    ultimo = risultato["messages"][-1]
    assert isinstance(ultimo, AIMessage) and ultimo.content == rifiuto(AMBITO)
    assert risultato["passi"] == 0
    righe = [r.getMessage() for r in caplog.records]
    assert "router categoria=fuori ambito motivo=storia next_node=rifiuto" in righe
    assert "rifiuto inviato, nodo agente non eseguito" in righe
    assert not any("Inizio chiamata al modello" in r for r in righe)


# Risposta del router non valida (categoria sconosciuta): si passa all'agente con un avviso.
def test_router_risposta_non_valida_passa_all_agente(caplog):
    router = RouterFinto([{"raw": None, "parsed": {"categoria": "altro", "motivo": "x"}, "parsing_error": None}])
    modello = ModelloFinto([AIMessage("Risposta")])
    with caplog.at_level(logging.INFO, logger="assistente.grafo"):
        esegui(modello, router=router)
    assert len(modello.chiamate) == 1
    avvisi = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any("router risposta non valida" in a and "next_node=llm (agente)" in a for a in avvisi)


# Il router riceve il suo prompt con l'ambito e solo i messaggi di testo: niente giri di strumento.
def test_router_riceve_prompt_con_ambito_e_messaggi_di_testo():
    cronologia = [
        HumanMessage("Che ore sono?"),
        richiesta_ora("call_1"),
        ToolMessage(ORA_FISSA, tool_call_id="call_1"),
        AIMessage("Sono le 12:00."),
    ]
    router = RouterFinto([classificazione("conversazione")])
    esegui(ModelloFinto([AIMessage("Prego.")]), "Grazie", router=router, cronologia=cronologia)
    ricevuti = router.chiamate[0]
    assert isinstance(ricevuti[0], SystemMessage) and ricevuti[0].content == prompt_router(AMBITO)
    assert not any(isinstance(m, ToolMessage) for m in ricevuti)
    assert not any(isinstance(m, AIMessage) and m.tool_calls for m in ricevuti)
    assert [m.content for m in ricevuti[1:]] == ["Che ore sono?", "Sono le 12:00.", "Grazie"]


# Dopo il router l'agente usa gli strumenti come prima: router -> llm -> strumenti -> llm.
def test_strumento_dopo_il_router():
    router = RouterFinto([classificazione("conversazione", "ora")])
    modello = ModelloFinto([richiesta_ora("call_1"), AIMessage("Sono le 12:00.")])
    risultato = esegui(modello, "Che ore sono?", router=router)
    strumenti = [m for m in risultato["messages"] if isinstance(m, ToolMessage)]
    assert len(strumenti) == 1 and strumenti[0].content == ORA_FISSA
    assert risultato["passi"] == 2
    assert len(router.chiamate) == 1


# Risposta del router troncata (limite di token) o bloccata dal filtro del server: la libreria
# OpenAI solleva un errore invece di restituire "parsing_error". È comunque una risposta non
# valida, non un errore di collegamento: si passa all'agente con l'avviso.
@pytest.mark.parametrize(
    "errore",
    [
        openai.LengthFinishReasonError(completion=SimpleNamespace(usage=None)),
        openai.ContentFilterFinishReasonError(),
    ],
)
def test_router_risposta_troncata_o_filtrata_passa_all_agente(errore, caplog):
    router = RouterFinto([errore])
    modello = ModelloFinto([AIMessage("Risposta")])
    with caplog.at_level(logging.INFO, logger="assistente.grafo"):
        risultato = esegui(modello, router=router)
    assert len(modello.chiamate) == 1
    assert risultato["messages"][-1].content == "Risposta"
    avvisi = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any("router risposta non valida" in a and "next_node=llm (agente)" in a for a in avvisi)
