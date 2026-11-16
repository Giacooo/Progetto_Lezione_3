"""Formato JSON dei messaggi scambiati con l'API dell'agente (lezione 6, step 6)."""

# COSA FA QUESTO FILE
# Dallo step 6 l'agente è un servizio HTTP SENZA STATO: la cronologia non la tiene lui, gliela
# manda ogni volta chi chiama (la CLI, più avanti il back-end) e lui la restituisce aggiornata.
# Sulla rete i messaggi non possono viaggiare come oggetti Python di LangChain: qui c'è
#   - la "forma" JSON di un messaggio (classi pydantic, da cui FastAPI ricava lo schema OpenAPI);
#   - in_json():  messaggi LangChain → JSON (dal grafo verso chi chiama);
#   - da_json():  JSON → messaggi LangChain (da chi chiama verso il grafo);
#   - controlla_cronologia(): rifiuta una cronologia incoerente prima di chiamare il modello.
# La cronologia viaggia COMPLETA, con le richieste di strumento e i loro risultati: servono al
# riassunto (step 3), che non separa mai una richiesta dal suo risultato.

from collections.abc import Sequence
from typing import Any, Literal

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from pydantic import BaseModel, Field, model_validator


# Una richiesta di strumento scritta dal modello: quale strumento, con quali argomenti e con
# quale id (il risultato dello strumento porta lo stesso id).
class RichiestaStrumento(BaseModel):
    id: str = Field(description="identificativo della richiesta")
    nome: str = Field(description="nome dello strumento")
    argomenti: dict[str, Any] = Field(default_factory=dict, description="argomenti scelti dal modello")


# Un messaggio della cronologia.
#   utente     = HumanMessage (la domanda, o l'indicazione del revisore con nome="revisore")
#   assistente = AIMessage (risposta del modello, eventualmente con richieste di strumento)
#   strumento  = ToolMessage (il risultato di uno strumento, collegato alla richiesta da id_chiamata)
class Messaggio(BaseModel):
    ruolo: Literal["utente", "assistente", "strumento"] = Field(description="chi ha scritto il messaggio")
    testo: str = Field(default="", description="contenuto del messaggio")
    nome: str | None = Field(
        default=None, description="nome del mittente (es. revisore) o dello strumento"
    )
    richieste_strumenti: list[RichiestaStrumento] = Field(
        default_factory=list, description="solo per assistente: le richieste di strumento"
    )
    id_chiamata: str | None = Field(
        default=None, description="solo per strumento: id della richiesta a cui risponde"
    )

    # Un risultato di strumento senza id non si può collegare a nessuna richiesta.
    @model_validator(mode="after")
    def _strumento_con_id(self):
        if self.ruolo == "strumento" and not self.id_chiamata:
            raise ValueError("un messaggio con ruolo 'strumento' richiede id_chiamata")
        # Solo il modello (assistente) chiede strumenti: una richiesta in un altro messaggio
        # andrebbe persa nella conversione e il suo risultato arriverebbe al modello orfano.
        if self.ruolo != "assistente" and self.richieste_strumenti:
            raise ValueError("solo un messaggio con ruolo 'assistente' può avere richieste_strumenti")
        return self


# Uno strumento usato durante un turno, come lo restituisce l'API: nome, argomenti e risultato.
class StrumentoUsato(BaseModel):
    nome: str = Field(description="nome dello strumento")
    argomenti: dict[str, Any] = Field(description="argomenti con cui è stato chiamato")
    risultato: str = Field(description="testo restituito dallo strumento")


# Ogni risultato di strumento deve rispondere a una richiesta comparsa PRIMA nella cronologia;
# altrimenti il modello riceverebbe una conversazione impossibile.
def controlla_cronologia(cronologia: Sequence[Messaggio]) -> None:
    richieste: set[str] = set()
    for messaggio in cronologia:
        richieste.update(r.id for r in messaggio.richieste_strumenti)
        if messaggio.ruolo == "strumento" and messaggio.id_chiamata not in richieste:
            raise ValueError(
                f"il risultato di strumento con id_chiamata {messaggio.id_chiamata!r} "
                "non risponde a nessuna richiesta precedente"
            )


def in_json(messaggi: Sequence[BaseMessage]) -> list[Messaggio]:
    """Messaggi LangChain → messaggi JSON; altri tipi (es. di sistema) → ValueError."""
    risultato = []
    for m in messaggi:
        if isinstance(m, HumanMessage):
            risultato.append(Messaggio(ruolo="utente", testo=m.text, nome=m.name))
        elif isinstance(m, AIMessage):
            richieste = [
                RichiestaStrumento(id=r["id"], nome=r["name"], argomenti=r["args"]) for r in m.tool_calls
            ]
            risultato.append(Messaggio(ruolo="assistente", testo=m.text, nome=m.name, richieste_strumenti=richieste))
        elif isinstance(m, ToolMessage):
            risultato.append(Messaggio(ruolo="strumento", testo=m.text, nome=m.name, id_chiamata=m.tool_call_id))
        else:
            raise ValueError(f"tipo di messaggio non ammesso nella cronologia: {m.type}")
    return risultato


def da_json(messaggi: Sequence[Messaggio]) -> list[BaseMessage]:
    """Messaggi JSON → messaggi LangChain (l'inverso di in_json)."""
    risultato: list[BaseMessage] = []
    for m in messaggi:
        if m.ruolo == "utente":
            risultato.append(HumanMessage(m.testo, name=m.nome))
        elif m.ruolo == "assistente":
            richieste = [{"name": r.nome, "args": r.argomenti, "id": r.id} for r in m.richieste_strumenti]
            risultato.append(AIMessage(m.testo, name=m.nome, tool_calls=richieste))
        else:
            risultato.append(ToolMessage(m.testo, tool_call_id=m.id_chiamata, name=m.nome))
    return risultato
