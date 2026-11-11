"""Modello finto con risposte predefinite, al posto di LM Studio nei test."""

# COSA FA QUESTO FILE
# Non contiene test: contiene gli "attori finti" che gli altri test usano al posto del
# modello vero. Un modello finto risponde con frasi decise in anticipo, quindi i test sono
# veloci, si possono ripetere identici e non hanno bisogno di LM Studio acceso.

from collections.abc import Callable
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.tools import StructuredTool

from assistente.strumenti import crea_strumenti

# L'ora che lo strumento finto restituisce sempre (12:00 a Roma il 15 gennaio 2026).
ORA_FISSA = "2026-01-15T12:00:00+01:00 (Europe/Rome)"


# Un modello finto "a copione": gli si dà in anticipo la lista delle risposte e le
# restituisce una alla volta, nell'ordine. Se una voce è un errore, lo lancia al suo posto:
# serve per simulare "LM Studio spento" e simili.
class ModelloFinto:
    def __init__(self, risposte: list[AIMessage | BaseException]):
        # Copia della lista di risposte ancora da dare.
        self.risposte = list(risposte)
        # Ricorda tutto ciò che gli è stato inviato, così i test possono controllarlo.
        self.chiamate: list[list[BaseMessage]] = []

    # Stesso nome del metodo del modello vero: il grafo non nota la differenza.
    def invoke(self, messaggi: list[BaseMessage]) -> AIMessage:
        self.chiamate.append(list(messaggi))
        # Prende la prima risposta rimasta (e la toglie dalla lista).
        risposta = self.risposte.pop(0)
        if isinstance(risposta, BaseException):
            raise risposta
        return risposta


class ModelloInsistente:
    """Chiede sempre lo strumento: serve a provare il limite di passaggi."""

    def __init__(self):
        self.chiamate: list[list[BaseMessage]] = []

    def invoke(self, messaggi: list[BaseMessage]) -> AIMessage:
        self.chiamate.append(list(messaggi))
        # Non dà mai una risposta finale: chiede sempre di nuovo l'orologio, con un id
        # diverso ogni volta (call_1, call_2, ...). Il ciclo si ferma solo per il limite.
        return richiesta_ora(f"call_{len(self.chiamate)}")


# Costruisce un messaggio del modello che NON contiene testo ma una RICHIESTA DI STRUMENTO,
# cioè quello che farebbe il modello vero quando vuole sapere l'ora.
def richiesta_ora(id_chiamata: str = "call_1", nome: str = "ora_corrente") -> AIMessage:
    return AIMessage("", tool_calls=[{"name": nome, "args": {}, "id": id_chiamata}])


# Uno strumento finto con la stessa "etichetta" (metadata variante) di quelli MCP veri.
# `comportamento` riceve il dizionario degli argomenti e restituisce un testo oppure
# solleva un errore: così i test simulano successo, errore dello strumento e caduta del server.
def strumento_finto(nome: str, comportamento: Callable[[dict], str], variante: str = "mcp") -> StructuredTool:
    def funzione(**argomenti) -> str:
        return comportamento(argomenti)

    return StructuredTool.from_function(
        func=funzione,
        name=nome,
        description=f"Strumento finto {nome}",
        # Schema libero: accetta qualunque argomento (es. espressione).
        args_schema={"type": "object", "properties": {}, "additionalProperties": True},
        metadata={"variante": variante},
    )


# Messaggio del modello con una sola richiesta di strumento, con nome, argomenti e id a scelta.
def richiesta(nome: str, argomenti: dict, id_chiamata: str) -> AIMessage:
    return AIMessage("", tool_calls=[{"name": nome, "args": argomenti, "id": id_chiamata}])


def strumenti_fissi():
    """Orologio con istante fisso: restituisce sempre ORA_FISSA."""
    # Lo strumento vero, ma con un orologio finto: sono le 11:00 UTC del 15/1/2026,
    # che a Roma (+01:00) sono le 12:00. Il risultato è quindi sempre uguale.
    return crea_strumenti(ZoneInfo("Europe/Rome"), adesso=lambda: datetime(2026, 1, 15, 11, tzinfo=timezone.utc))
