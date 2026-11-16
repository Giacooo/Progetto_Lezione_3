"""Test del formato JSON dei messaggi usato dall'API dell'agente (lezione 6, step 6)."""

# La cronologia viaggia tra chi chiama e l'agente come JSON: questi test controllano che la
# conversione da messaggi LangChain a JSON e ritorno non perda nulla (richieste di strumento,
# risultati, nomi, accenti) e che i messaggi incoerenti vengano rifiutati.

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from pydantic import ValidationError

from assistente.formato import Messaggio, RichiestaStrumento, controlla_cronologia, da_json, in_json


def giro_con_strumento():
    return [
        HumanMessage("Quanto fa 45/9?"),
        AIMessage("", tool_calls=[{"name": "calcola", "args": {"espressione": "45/9"}, "id": "c1"}]),
        ToolMessage("5", tool_call_id="c1", name="calcola"),
        AIMessage("Fa 5."),
    ]


# Andata (LangChain → JSON) e ritorno (JSON → LangChain): tipi, testi, richieste e risultati uguali.
def test_andata_e_ritorno_di_un_giro_con_strumento():
    originali = giro_con_strumento()
    json_ = in_json(originali)
    assert [m.ruolo for m in json_] == ["utente", "assistente", "strumento", "assistente"]
    assert json_[1].richieste_strumenti == [RichiestaStrumento(id="c1", nome="calcola", argomenti={"espressione": "45/9"})]
    assert json_[2].id_chiamata == "c1" and json_[2].nome == "calcola"
    ritorno = da_json(json_)
    assert [type(m) for m in ritorno] == [HumanMessage, AIMessage, ToolMessage, AIMessage]
    assert [m.text for m in ritorno] == [m.text for m in originali]
    assert ritorno[1].tool_calls[0]["name"] == "calcola"
    assert ritorno[1].tool_calls[0]["args"] == {"espressione": "45/9"}
    assert ritorno[1].tool_calls[0]["id"] == "c1"
    assert ritorno[2].tool_call_id == "c1" and ritorno[2].name == "calcola"


# L'indicazione del revisore (step 2) è un HumanMessage con name="revisore": il nome non si perde.
def test_indicazione_del_revisore_conserva_il_nome():
    json_ = in_json([HumanMessage("manca il meteo", name="revisore")])
    assert json_[0].ruolo == "utente" and json_[0].nome == "revisore"
    assert da_json(json_)[0].name == "revisore"


# Accenti e virgolette basse passano intatti anche attraverso il testo JSON.
def test_accenti_e_virgolette_restano_uguali():
    testo = "«Perché» la città è così?"
    json_ = in_json([HumanMessage(testo)])
    testo_json = json_[0].model_dump_json()
    ritorno = da_json([Messaggio.model_validate_json(testo_json)])
    assert ritorno[0].text == testo


# Il prompt di sistema lo aggiunge il grafo a ogni chiamata: nella cronologia non deve esserci.
def test_messaggio_di_sistema_non_ammesso():
    with pytest.raises(ValueError):
        in_json([SystemMessage("x")])


def test_strumento_senza_id_chiamata_e_rifiutato():
    with pytest.raises(ValidationError):
        Messaggio(ruolo="strumento", testo="5")


def test_ruolo_sconosciuto_e_rifiutato():
    with pytest.raises(ValidationError):
        Messaggio(ruolo="sistema")


# Un risultato di strumento deve rispondere a una richiesta comparsa PRIMA nella cronologia.
# Review Focus 1: solo un messaggio dell'assistente può chiedere strumenti; altrimenti una richiesta
# messa in un messaggio dell'utente "coprirebbe" un risultato che al modello arriverebbe orfano.
def test_richieste_solo_nei_messaggi_dell_assistente():
    for ruolo, extra in (("utente", {}), ("strumento", {"id_chiamata": "c1"})):
        with pytest.raises(ValidationError):
            Messaggio(ruolo=ruolo, testo="x", richieste_strumenti=[RichiestaStrumento(id="c1", nome="calcola")], **extra)


def test_strumento_senza_richiesta_e_rifiutato():
    with pytest.raises(ValueError, match="zzz"):
        controlla_cronologia([Messaggio(ruolo="strumento", testo="5", id_chiamata="zzz")])
    controlla_cronologia(
        [
            Messaggio(ruolo="assistente", richieste_strumenti=[RichiestaStrumento(id="zzz", nome="calcola")]),
            Messaggio(ruolo="strumento", testo="5", id_chiamata="zzz"),
        ]
    )
