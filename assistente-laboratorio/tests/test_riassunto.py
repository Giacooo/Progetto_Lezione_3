# COSA PROVA QUESTO FILE
# I pezzi del riassunto (riassunto.py, lezione 6, step 3), senza modello e senza grafo: il prompt
# del riassunto, il punto di taglio (dove si separano i messaggi da togliere da quelli da tenere),
# la trascrizione dei messaggi tolti, i messaggi per il riassuntore e il messaggio di sistema con
# il riassunto in coda.

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from assistente.revisore import e_indicazione, indicazione
from assistente.riassunto import (
    messaggi_per_riassunto,
    prompt_riassunto,
    punto_di_taglio,
    sistema_con_riassunto,
    trascrizione,
)
from finti import ORA_FISSA, richiesta_ora

H = HumanMessage
AI = AIMessage

# L'esempio della specifica (§6.2): un giro di strumento in mezzo alla conversazione.
ESEMPIO = [
    H("Mi chiamo Luca"),
    AI("Piacere, Luca"),
    H("Che ore sono?"),
    richiesta_ora("c1"),
    ToolMessage(ORA_FISSA, tool_call_id="c1"),
    AI("Sono le 12."),
    H("Come mi chiamo?"),
]


# Il prompt chiede di conservare le informazioni sull'utente (come il nome) e non parla di
# strumenti: il riassunto racconta la conversazione, non come l'agente ha ottenuto i dati.
def test_prompt_riassunto_conserva_l_utente_e_non_nomina_gli_strumenti():
    p = prompt_riassunto().lower()
    assert "nome" in p
    for parola in ("strument", "ora_corrente", "calcola", "meteo_citta"):
        assert parola not in p


# Gli ultimi 3 messaggi iniziano già con una domanda dell'utente: il taglio resta lì.
def test_taglio_su_una_domanda():
    assert punto_di_taglio([H("a"), AI("b"), H("c"), AI("d"), H("e")], 3) == 2


# L'indice di partenza (7 - 3 = 4) è un risultato di strumento: il taglio torna alla domanda
# che apre quel turno, così la richiesta e il suo risultato restano insieme.
def test_taglio_su_un_tool_message_torna_alla_domanda():
    assert punto_di_taglio(ESEMPIO, 3) == 2


# L'indice di partenza (7 - 4 = 3) è una richiesta di strumento: stessa regola.
def test_taglio_su_una_richiesta_di_strumento_torna_alla_domanda():
    assert punto_di_taglio(ESEMPIO, 4) == 2


# Un'indicazione del revisore è un messaggio "utente" ma non apre un turno: il taglio non si
# ferma lì e non si ferma nemmeno sulla bozza che l'indicazione ha rifiutato.
@pytest.mark.parametrize("da_tenere", [3, 4])
def test_taglio_su_indicazione_o_bozza_torna_alla_domanda(da_tenere):
    messaggi = [
        H("a"),
        AI("b"),
        H("Che ore e che tempo?"),
        AI("Sono le 12."),
        indicazione("manca il meteo"),
        AI("Sono le 12 e piove."),
        H("Grazie"),
    ]
    assert punto_di_taglio(messaggi, da_tenere) == 2


# Un unico turno lunghissimo: prima non c'è nessuna domanda a cui tornare, niente da togliere.
def test_turno_unico_lungo_niente_da_togliere():
    messaggi = [
        H("x"),
        richiesta_ora("c1"),
        ToolMessage(ORA_FISSA, tool_call_id="c1"),
        richiesta_ora("c2"),
        ToolMessage(ORA_FISSA, tool_call_id="c2"),
        AI("fine"),
    ]
    assert punto_di_taglio(messaggi, 2) == 0


# Con un solo messaggio da tenere resta soltanto la domanda nuova.
def test_tenere_un_messaggio():
    assert punto_di_taglio([H("a"), AI("b"), H("c")], 1) == 2


# Per ogni numero di messaggi da tenere, il taglio cade su una domanda vera dell'utente (o è 0,
# niente da togliere) e nessun risultato di strumento tenuto perde la sua richiesta.
def test_taglio_non_separa_mai_strumento_e_risultato():
    for da_tenere in range(1, len(ESEMPIO) + 1):
        taglio = punto_di_taglio(ESEMPIO, da_tenere)
        assert taglio == 0 or (isinstance(ESEMPIO[taglio], HumanMessage) and not e_indicazione(ESEMPIO[taglio]))
        id_richieste_tolte = {c["id"] for m in ESEMPIO[:taglio] if isinstance(m, AIMessage) for c in m.tool_calls}
        for m in ESEMPIO[taglio:]:
            if isinstance(m, ToolMessage):
                assert m.tool_call_id not in id_richieste_tolte


# La trascrizione tiene domande, risposte di testo e risultati degli strumenti (con il nome);
# salta la richiesta di strumento, l'indicazione del revisore e la bozza rifiutata.
def test_trascrizione():
    messaggi = [
        H("Mi chiamo Luca"),
        AI("Piacere"),
        H("Che ore e che tempo?"),
        richiesta_ora("c1"),
        ToolMessage(ORA_FISSA, tool_call_id="c1", name="ora_corrente"),
        AI("Sono le 12."),
        indicazione("manca il meteo"),
        AI("Sono le 12 e piove."),
    ]
    assert trascrizione(messaggi) == (
        "Utente: Mi chiamo Luca\n"
        "Assistente: Piacere\n"
        "Utente: Che ore e che tempo?\n"
        "Strumento ora_corrente: " + ORA_FISSA + "\n"
        "Assistente: Sono le 12 e piove."
    )


# Il riassuntore riceve il suo prompt e UN solo messaggio con il riassunto precedente (se c'è)
# e la trascrizione dei messaggi da togliere.
def test_messaggi_per_riassunto():
    m = messaggi_per_riassunto("L'utente si chiama Luca.", [H("Che ore sono?"), AI("Sono le 12.")])
    assert len(m) == 2
    assert isinstance(m[0], SystemMessage)
    assert m[0].content == prompt_riassunto()
    assert isinstance(m[1], HumanMessage)
    assert "L'utente si chiama Luca." in m[1].content
    assert "Utente: Che ore sono?" in m[1].content
    assert "Assistente: Sono le 12." in m[1].content

    senza_precedente = messaggi_per_riassunto("", [H("Che ore sono?"), AI("Sono le 12.")])
    assert "riassunto precedente" not in senza_precedente[1].content.lower()


# Il riassunto va in coda al prompt di sistema; se è vuoto il prompt resta identico.
def test_sistema_con_riassunto():
    assert sistema_con_riassunto("P", "") == "P"
    assert sistema_con_riassunto("P", "  ") == "P"
    assert sistema_con_riassunto("P", " R ") == "P\n\nRiassunto della conversazione precedente: R"
