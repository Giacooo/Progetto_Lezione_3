"""Modello finto con risposte predefinite, al posto di LM Studio nei test."""

from langchain_core.messages import AIMessage, BaseMessage


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
