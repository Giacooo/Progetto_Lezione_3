"""Modello finto con risposte predefinite, al posto di LM Studio nei test."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from langchain_core.messages import AIMessage, BaseMessage

from assistente.strumenti import crea_strumenti

ORA_FISSA = "2026-01-15T12:00:00+01:00 (Europe/Rome)"


class ModelloFinto:
    def __init__(self, risposte: list[AIMessage | BaseException]):
        self.risposte = list(risposte)
        self.chiamate: list[list[BaseMessage]] = []

    def invoke(self, messaggi: list[BaseMessage]) -> AIMessage:
        self.chiamate.append(list(messaggi))
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
        return richiesta_ora(f"call_{len(self.chiamate)}")


def richiesta_ora(id_chiamata: str = "call_1", nome: str = "ora_corrente") -> AIMessage:
    return AIMessage("", tool_calls=[{"name": nome, "args": {}, "id": id_chiamata}])


def strumenti_fissi():
    """Orologio con istante fisso: restituisce sempre ORA_FISSA."""
    return crea_strumenti(ZoneInfo("Europe/Rome"), adesso=lambda: datetime(2026, 1, 15, 11, tzinfo=timezone.utc))
