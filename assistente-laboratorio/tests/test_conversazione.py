# COSA PROVA QUESTO FILE
# La "memoria" della chat (conversazione.py): che la cronologia cresca quando il turno
# riesce, che resti identica quando fallisce, e che gli errori finiscano nel log.
# Qui il modello è sempre finto (vedi finti.py): nessuna chiamata a LM Studio.

import logging

import httpx
import openai
import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from assistente.conversazione import Conversazione
from assistente.errori import ErroreTurno
from assistente.grafo import costruisci_grafo
# Importato con un altro nome: pytest raccoglierebbe "testo_rifiuto" come se fosse un test.
from assistente.router import testo_rifiuto as rifiuto
from finti import (
    PREFERENZE_PREDEFINITE,
    ModelloFinto,
    ModelloInsistente,
    RevisoreFinto,
    RouterFinto,
    classificazione,
    richiesta_ora,
    revisore_sempre_coerente,
    router_sempre_conversazione,
    strumenti_fissi,
    valutazione,
)

# Una richiesta HTTP "di facciata": serve solo per costruire gli errori di prova.
RICHIESTA = httpx.Request("POST", "http://localhost:1234/v1/chat/completions")


# L'ambito usato nei test (nell'applicazione viene da AMBITO_AGENTE).
AMBITO = "data e ora, meteo"


# Funzione di aiuto: crea una conversazione col modello finto a copione e il grafo vero.
# Il router finto risponde sempre "conversazione" e il revisore finto approva sempre,
# salvo che il test ne passi altri. Il riassuntore finto senza risposte non viene chiamato:
# con la soglia predefinita (20) le conversazioni dei test restano sotto la soglia.
def conversazione_con(
    risposte, router=None, revisore=None, max_passi=5, riassuntore=None, soglia_riassunto=20, messaggi_da_tenere=6
):
    modello = ModelloFinto(risposte)
    router = router or router_sempre_conversazione()
    revisore = revisore if revisore is not None else revisore_sempre_coerente()
    riassuntore = riassuntore if riassuntore is not None else ModelloFinto([])
    grafo = costruisci_grafo(
        modello,
        strumenti_fissi(),
        max_passi,
        router,
        AMBITO,
        revisore,
        2,
        riassuntore,
        soglia_riassunto,
        messaggi_da_tenere,
        PREFERENZE_PREDEFINITE,
    )
    return Conversazione(grafo), modello


# Due domande di seguito: la cronologia contiene tutti e quattro i messaggi nell'ordine
# giusto, e alla SECONDA chiamata il modello riceve anche la prima domanda e la prima risposta.
def test_cronologia_dopo_due_turni():
    conversazione, modello = conversazione_con([AIMessage("Ciao Luca"), AIMessage("Ti chiami Luca")])
    assert conversazione.chiedi("Mi chiamo Luca") == "Ciao Luca"
    assert conversazione.chiedi("Come mi chiamo?") == "Ti chiami Luca"
    cronologia = conversazione.cronologia
    assert [type(m) for m in cronologia] == [HumanMessage, AIMessage, HumanMessage, AIMessage]
    assert [m.content for m in cronologia] == ["Mi chiamo Luca", "Ciao Luca", "Come mi chiamo?", "Ti chiami Luca"]
    seconda = modello.chiamate[1]
    assert isinstance(seconda[0], SystemMessage)
    assert [m.content for m in seconda[1:]] == ["Mi chiamo Luca", "Ciao Luca", "Come mi chiamo?"]


# Provato 3 volte, con tre errori diversi (connessione, timeout, errore del server).
# Il turno fallito: dà il messaggio giusto, NON cambia la cronologia, e la domanda
# successiva funziona normalmente (la sessione non è rotta).
@pytest.mark.parametrize(
    "eccezione, messaggio",
    [
        (openai.APIConnectionError(request=RICHIESTA), "Connessione fallita: controllare LM Studio, URL e porta."),
        (openai.APITimeoutError(request=RICHIESTA), "Attesa scaduta: controllare server, carico e tempi."),
        (
            openai.APIStatusError("x", response=httpx.Response(400, request=RICHIESTA, text="bad"), body=None),
            "Errore dal server: 400 bad",
        ),
    ],
)
def test_errore_lascia_la_cronologia_invariata(eccezione, messaggio):
    conversazione, _ = conversazione_con([AIMessage("primo"), eccezione, AIMessage("terzo")])
    conversazione.chiedi("uno")
    prima = list(conversazione.cronologia)
    with pytest.raises(ErroreTurno) as errore:
        conversazione.chiedi("due")
    assert str(errore.value) == messaggio
    assert conversazione.cronologia == prima
    assert conversazione.chiedi("tre") == "terzo"
    assert [m.content for m in conversazione.cronologia] == ["uno", "primo", "tre", "terzo"]


# Se il modello risponde con un testo vuoto, è un errore e la cronologia resta vuota.
def test_risposta_vuota_e_un_errore():
    conversazione, _ = conversazione_con([AIMessage("")])
    with pytest.raises(ErroreTurno, match="^Il modello ha restituito una risposta vuota.$"):
        conversazione.chiedi("ciao")
    assert conversazione.cronologia == []


# Nel log compaiono le righe "Inizio/Fine chiamata al modello (passo 1...)".
# (caplog è lo strumento di pytest per raccogliere i messaggi di log durante il test.)
def test_log_chiamata_al_modello(caplog):
    conversazione, _ = conversazione_con([AIMessage("ok")])
    with caplog.at_level(logging.INFO, logger="assistente"):
        conversazione.chiedi("ciao")
    righe = [r.getMessage() for r in caplog.records if r.name.startswith("assistente")]
    assert any("Inizio chiamata al modello" in r and "passo 1" in r for r in righe)
    assert any("Fine chiamata al modello" in r and "passo 1" in r for r in righe)


# Un modello che chiede lo strumento all'infinito viene fermato dal limite (3 passi),
# con il messaggio giusto, e la cronologia resta vuota.
def test_limite_passi_lascia_la_cronologia_invariata():
    conversazione = Conversazione(
        costruisci_grafo(
            ModelloInsistente(), strumenti_fissi(), 3, router_sempre_conversazione(), AMBITO,
            revisore_sempre_coerente(), 2, ModelloFinto([]), 20, 6, PREFERENZE_PREDEFINITE,
        )
    )
    with pytest.raises(ErroreTurno) as errore:
        conversazione.chiedi("Che ore sono?")
    assert str(errore.value) == "Limite di passaggi raggiunto: riprova con una domanda diversa."
    assert conversazione.cronologia == []


# Quando c'è un giro con lo strumento, nella cronologia restano tutti i messaggi:
# domanda, richiesta dello strumento, risultato, risposta; poi la domanda successiva e la sua risposta.
def test_cronologia_conserva_il_giro_dello_strumento():
    conversazione, _ = conversazione_con(
        [richiesta_ora(), AIMessage("Sono le 12:00."), AIMessage("Prego.")]
    )
    conversazione.chiedi("Che ore sono?")
    conversazione.chiedi("Grazie")
    assert [type(m) for m in conversazione.cronologia] == [
        HumanMessage, AIMessage, ToolMessage, AIMessage, HumanMessage, AIMessage
    ]


# Un errore del server viene scritto nel log come riga ERROR con il messaggio chiaro.
def test_errore_del_server_finisce_nel_log(caplog):
    conversazione, _ = conversazione_con([openai.APIConnectionError(request=RICHIESTA)])
    with caplog.at_level(logging.INFO, logger="assistente"), pytest.raises(ErroreTurno):
        conversazione.chiedi("ciao")
    errori = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert errori == ["Turno fallito: Connessione fallita: controllare LM Studio, URL e porta."]


# Una risposta vuota viene scritta nel log come avviso (WARNING).
def test_risposta_vuota_finisce_nel_log(caplog):
    conversazione, _ = conversazione_con([AIMessage("")])
    with caplog.at_level(logging.INFO, logger="assistente"), pytest.raises(ErroreTurno):
        conversazione.chiedi("ciao")
    avvisi = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert avvisi == ["Turno fallito: Il modello ha restituito una risposta vuota."]


# Un errore non previsto (qui un ValueError) non chiude la sessione: viene mostrato come
# "Errore inatteso", il traceback completo va nel log, la cronologia resta com'era e
# la domanda successiva funziona.
def test_errore_inatteso_non_chiude_la_sessione(caplog):
    conversazione, _ = conversazione_con([AIMessage("primo"), ValueError("risposta malformata"), AIMessage("terzo")])
    conversazione.chiedi("uno")
    prima = list(conversazione.cronologia)
    with caplog.at_level(logging.INFO, logger="assistente"), pytest.raises(ErroreTurno) as errore:
        conversazione.chiedi("due")
    assert str(errore.value) == "Errore inatteso: risposta malformata (dettagli nel log)"
    assert conversazione.cronologia == prima
    registrati = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert registrati and registrati[0].exc_info is not None  # traceback completo nel log
    assert conversazione.chiedi("tre") == "terzo"


# ---------------- ROUTER (lezione 6, step 1) ----------------

# Il rifiuto è una risposta normale: entra nella cronologia insieme alla domanda.
def test_rifiuto_entra_nella_cronologia():
    router = RouterFinto([classificazione("fuori ambito", "storia")])
    conversazione, modello = conversazione_con([], router=router)
    assert conversazione.chiedi("Raccontami la storia di Roma") == rifiuto(AMBITO)
    assert [type(m) for m in conversazione.cronologia] == [HumanMessage, AIMessage]
    assert [m.content for m in conversazione.cronologia] == ["Raccontami la storia di Roma", rifiuto(AMBITO)]
    assert modello.chiamate == []


# Un errore di collegamento durante il router fa fallire il turno come per l'agente:
# stesso messaggio, cronologia invariata, agente non chiamato in quel turno.
def test_errore_del_router_lascia_la_cronologia_invariata():
    router = RouterFinto([classificazione("conversazione"), openai.APIConnectionError(request=RICHIESTA)])
    conversazione, modello = conversazione_con([AIMessage("primo")], router=router)
    conversazione.chiedi("uno")
    prima = list(conversazione.cronologia)
    with pytest.raises(ErroreTurno) as errore:
        conversazione.chiedi("due")
    assert str(errore.value) == "Connessione fallita: controllare LM Studio, URL e porta."
    assert conversazione.cronologia == prima
    assert len(modello.chiamate) == 1


# ---------------- REVISORE (lezione 6, step 2) ----------------

# Dopo una revisione nella cronologia resta tutto (decisione dell'utente): domanda, bozza
# rifiutata, indicazione del revisore e risposta nuova.
def test_cronologia_dopo_una_revisione():
    revisore = RevisoreFinto([valutazione("no", "manca il meteo"), valutazione("sì", "ok")])
    conversazione, _ = conversazione_con(
        [AIMessage("Sono le 12."), AIMessage("Sono le 12 e piove.")], revisore=revisore
    )
    assert conversazione.chiedi("Che ore sono e che tempo fa?") == "Sono le 12 e piove."
    cronologia = conversazione.cronologia
    assert [type(m) for m in cronologia] == [HumanMessage, AIMessage, HumanMessage, AIMessage]
    assert cronologia[1].content == "Sono le 12."
    assert cronologia[2].name == "revisore" and "manca il meteo" in cronologia[2].text
    assert cronologia[3].content == "Sono le 12 e piove."


# Un errore di collegamento durante il revisore (LM Studio spento dopo la risposta
# dell'agente) fa fallire il turno come per l'agente: stesso messaggio, cronologia invariata.
def test_errore_del_revisore_lascia_la_cronologia_invariata():
    revisore = RevisoreFinto([valutazione("sì"), openai.APIConnectionError(request=RICHIESTA)])
    conversazione, _ = conversazione_con([AIMessage("primo"), AIMessage("secondo")], revisore=revisore)
    conversazione.chiedi("uno")
    prima = list(conversazione.cronologia)
    with pytest.raises(ErroreTurno) as errore:
        conversazione.chiedi("due")
    assert str(errore.value) == "Connessione fallita: controllare LM Studio, URL e porta."
    assert conversazione.cronologia == prima


# Se il nuovo tentativo dopo una revisione si ferma al limite di passaggi con una richiesta di
# strumento aperta, il turno fallisce come oggi e la cronologia resta invariata.
def test_limite_passi_in_un_nuovo_tentativo():
    revisore = RevisoreFinto([valutazione("no", "x")])
    conversazione, _ = conversazione_con(
        [AIMessage("r1"), richiesta_ora("c1"), richiesta_ora("c2")], revisore=revisore, max_passi=2
    )
    with pytest.raises(ErroreTurno) as errore:
        conversazione.chiedi("Che ore sono?")
    assert str(errore.value) == "Limite di passaggi raggiunto: riprova con una domanda diversa."
    assert conversazione.cronologia == []


# Lezione 6, step 3: dopo una compressione la Conversazione conserva insieme cronologia e
# riassunto, e al turno successivo passa al grafo il riassunto salvato.
def test_riassunto_conservato_tra_i_turni():
    riassuntore = ModelloFinto(
        [AIMessage("L'utente si chiama Luca."), AIMessage("L'utente si chiama Luca. Ha chiesto l'ora.")]
    )
    conversazione, _ = conversazione_con(
        [AIMessage("Piacere, Luca"), AIMessage("Sono le 12."), AIMessage("Ti chiami Luca."), AIMessage("Prego.")],
        riassuntore=riassuntore,
        soglia_riassunto=4,
        messaggi_da_tenere=2,
    )
    conversazione.chiedi("Mi chiamo Luca")
    conversazione.chiedi("Che ore sono?")
    assert conversazione.chiedi("Come mi chiamo?") == "Ti chiami Luca."
    assert conversazione.riassunto == "L'utente si chiama Luca."
    assert not any(m.text == "Mi chiamo Luca" for m in conversazione.cronologia)
    assert isinstance(conversazione.cronologia[0], HumanMessage)
    assert conversazione.cronologia[0].text == "Che ore sono?"

    conversazione.chiedi("Grazie")
    seconda_trascrizione = riassuntore.chiamate[1][1].content
    assert "L'utente si chiama Luca." in seconda_trascrizione
    # La seconda compressione toglie solo il turno appena uscito, non ripete il primo.
    assert "Utente: Che ore sono?" in seconda_trascrizione
    assert "Mi chiamo Luca" not in seconda_trascrizione
    assert conversazione.riassunto == "L'utente si chiama Luca. Ha chiesto l'ora."
    # Il riassunto è un campo a parte: nessun messaggio della cronologia lo contiene.
    assert not any("L'utente si chiama Luca" in m.text for m in conversazione.cronologia)


# LM Studio spento proprio durante il riassunto: il turno fallisce con il messaggio di sempre
# e cronologia e riassunto restano com'erano.
def test_errore_durante_il_riassunto_lascia_tutto_invariato():
    conversazione, _ = conversazione_con(
        [AIMessage("Piacere, Luca"), AIMessage("Sono le 12.")],
        riassuntore=ModelloFinto([openai.APIConnectionError(request=RICHIESTA)]),
        soglia_riassunto=4,
        messaggi_da_tenere=2,
    )
    conversazione.chiedi("Mi chiamo Luca")
    conversazione.chiedi("Che ore sono?")
    prima = list(conversazione.cronologia)
    with pytest.raises(ErroreTurno) as errore:
        conversazione.chiedi("Come mi chiamo?")
    assert str(errore.value) == "Connessione fallita: controllare LM Studio, URL e porta."
    assert conversazione.cronologia == prima
    assert conversazione.riassunto == ""


# Come sopra, ma con un riassunto già salvato: se la SECONDA compressione fallisce, il
# riassunto resta quello di prima (invariato, non azzerato).
def test_errore_nella_seconda_compressione_conserva_il_riassunto():
    conversazione, _ = conversazione_con(
        [AIMessage("Piacere, Luca"), AIMessage("Sono le 12."), AIMessage("Ti chiami Luca.")],
        riassuntore=ModelloFinto([AIMessage("L'utente si chiama Luca."), openai.APIConnectionError(request=RICHIESTA)]),
        soglia_riassunto=4,
        messaggi_da_tenere=2,
    )
    conversazione.chiedi("Mi chiamo Luca")
    conversazione.chiedi("Che ore sono?")
    conversazione.chiedi("Come mi chiamo?")
    assert conversazione.riassunto == "L'utente si chiama Luca."
    prima = list(conversazione.cronologia)
    with pytest.raises(ErroreTurno) as errore:
        conversazione.chiedi("Grazie")
    assert str(errore.value) == "Connessione fallita: controllare LM Studio, URL e porta."
    assert conversazione.cronologia == prima
    assert conversazione.riassunto == "L'utente si chiama Luca."
