"""Il modulo dell'agente, separato dall'interfaccia: un turno senza stato attraverso il grafo."""

# COSA FA QUESTO FILE (lezione 6, step 6)
# Contiene l'agente "puro", senza tastiera, schermo o HTTP: lo usano sia il servizio HTTP
# (servizio.py) sia, per i test e le prove reali, la Conversazione in memoria.
# L'agente è SENZA STATO: non ricorda nulla tra un turno e l'altro. A ogni turno riceve da chi
# chiama la cronologia e il riassunto, fa girare il grafo e restituisce:
#   - la risposta,
#   - gli strumenti usati in questo turno (nome, argomenti, risultato),
#   - la cronologia e il riassunto aggiornati, che chi chiama dovrà rimandare al turno dopo.
# Gli errori del turno portano un "tipo" (connessione, attesa, ...): il servizio ne ricava il
# codice HTTP, la CLI ne mostra solo il messaggio.

import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass

import openai
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage

from assistente.errori import ErroreTurno
from assistente.formato import StrumentoUsato
from assistente.modello import traduci_errore

log = logging.getLogger(__name__)


# Un errore del turno con il suo tipo. È un ErroreTurno, quindi chi già gestisce quelli
# (la CLI, la Conversazione) continua a funzionare uguale.
class ErroreTurnoAgente(ErroreTurno):
    """Il turno non si è concluso; `tipo` dice perché (connessione, attesa, server, ...)."""

    def __init__(self, messaggio: str, tipo: str):
        super().__init__(messaggio)
        self.tipo = tipo


# Il risultato di un turno riuscito.
@dataclass(frozen=True)
class EsitoTurno:
    risposta: str
    strumenti_usati: list[StrumentoUsato]
    cronologia: list[BaseMessage]
    riassunto: str


# Il tipo di un errore del modello: l'attesa scaduta va controllata PRIMA della connessione
# fallita, perché APITimeoutError è un caso particolare di APIConnectionError.
def _tipo_errore(exc: Exception) -> str:
    if isinstance(exc, openai.APITimeoutError):
        return "attesa"
    if isinstance(exc, openai.APIConnectionError):
        return "connessione"
    if isinstance(exc, openai.APIStatusError):
        return "server"
    return "inatteso"


# Gli strumenti usati nel turno: ogni richiesta di strumento dei messaggi del turno, abbinata
# al suo risultato (stesso id). Una richiesta senza risultato non è stata eseguita: non conta.
def _strumenti_usati(messaggi_del_turno: Sequence[BaseMessage]) -> list[StrumentoUsato]:
    risultati = {m.tool_call_id: m.text for m in messaggi_del_turno if isinstance(m, ToolMessage)}
    usati = []
    for m in messaggi_del_turno:
        if isinstance(m, AIMessage):
            for richiesta in m.tool_calls:
                if richiesta["id"] in risultati:
                    usati.append(
                        StrumentoUsato(nome=richiesta["name"], argomenti=richiesta["args"], risultato=risultati[richiesta["id"]])
                    )
    return usati


def esegui_turno(grafo, cronologia: Sequence[BaseMessage], nuovi: Sequence[BaseMessage], riassunto: str) -> EsitoTurno:
    """Un turno senza stato: restituisce l'esito, oppure lancia ErroreTurnoAgente."""
    # Ogni messaggio nuovo riceve un identificativo: dopo il grafo serve a ritrovare dove
    # comincia questo turno (il riassunto può aver tolto messaggi vecchi, quindi le posizioni
    # non bastano). Si lavora su copie: i messaggi ricevuti non vengono modificati.
    nuovi = [m if m.id else m.model_copy(update={"id": str(uuid.uuid4())}) for m in nuovi]

    # --- Passo 1: far girare il grafo, con passi e revisioni da zero ---
    try:
        risultato = grafo.invoke(
            {"messages": [*cronologia, *nuovi], "passi": 0, "revisioni": 0, "riassunto": riassunto}
        )
    except Exception as exc:
        errore = traduci_errore(exc)
        tipo = _tipo_errore(exc)
        if errore is None:
            # Errore non previsto: traceback completo nel log.
            log.exception("Turno fallito per un errore inatteso")
            messaggio = f"Errore inatteso: {exc} (dettagli nel log)"
        else:
            messaggio = str(errore)
            log.error("Turno fallito: %s", messaggio)
        raise ErroreTurnoAgente(messaggio, tipo) from exc

    # --- Passo 2: controllare il risultato ---
    messaggi = risultato["messages"]
    finale = messaggi[-1]
    if finale.tool_calls:
        # Fermato al limite con una richiesta di strumento ancora aperta (avviso già nel log).
        raise ErroreTurnoAgente("Limite di passaggi raggiunto: riprova con una domanda diversa.", "limite_passi")
    testo = finale.text.strip()
    if not testo:
        messaggio = "Il modello ha restituito una risposta vuota."
        log.warning("Turno fallito: %s", messaggio)
        raise ErroreTurnoAgente(messaggio, "risposta_vuota")

    # --- Passo 3: l'esito, con i soli strumenti di questo turno ---
    inizio = next(i for i, m in enumerate(messaggi) if m.id == nuovi[0].id)
    return EsitoTurno(
        risposta=testo,
        strumenti_usati=_strumenti_usati(messaggi[inizio:]),
        cronologia=list(messaggi),
        riassunto=risultato["riassunto"],
    )
