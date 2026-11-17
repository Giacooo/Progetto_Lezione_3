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

from assistente.preferenze import predefinite
from assistente.strumenti import crea_strumenti

# L'ora che lo strumento finto restituisce sempre (12:00 a Roma il 15 gennaio 2026).
ORA_FISSA = "2026-01-15T12:00:00+01:00 (Europe/Rome)"
# Le preferenze usate dai test quando non ne servono di particolari (i predefiniti, fuso di Roma).
PREFERENZE_PREDEFINITE = predefinite(ZoneInfo("Europe/Rome"))


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


# Il router finto: come il modello finto, ma restituisce l'output strutturato del router,
# cioè un dizionario {"raw", "parsed", "parsing_error"}. Se una voce è un errore, lo lancia.
class RouterFinto:
    def __init__(self, uscite: list[dict | BaseException]):
        self.uscite = list(uscite)
        # Ricorda i messaggi ricevuti a ogni chiamata, così i test possono controllarli.
        self.chiamate: list[list[BaseMessage]] = []

    def invoke(self, messaggi: list[BaseMessage]) -> dict:
        self.chiamate.append(list(messaggi))
        uscita = self.uscite.pop(0)
        if isinstance(uscita, BaseException):
            raise uscita
        return uscita


# L'uscita del router quando la risposta del modello è stata letta correttamente.
def classificazione(categoria: str, motivo: str = "motivo di prova") -> dict:
    return {"raw": None, "parsed": {"categoria": categoria, "motivo": motivo}, "parsing_error": None}


class RouterSempreConversazione(RouterFinto):
    """Risponde sempre «conversazione» e non si esaurisce mai: serve ai test esistenti."""

    def __init__(self):
        super().__init__([])

    def invoke(self, messaggi: list[BaseMessage]) -> dict:
        self.chiamate.append(list(messaggi))
        return classificazione("conversazione")


def router_sempre_conversazione() -> RouterFinto:
    return RouterSempreConversazione()


# Il revisore finto (lezione 6, step 2): stessa logica "a copione" del router finto, ma le
# uscite sono valutazioni {"raw", "parsed", "parsing_error"} con "coerente" e "motivo".
class RevisoreFinto(RouterFinto):
    pass


# L'uscita del revisore quando la risposta del modello è stata letta correttamente.
def valutazione(coerente: str, motivo: str = "motivo di prova") -> dict:
    return {"raw": None, "parsed": {"coerente": coerente, "motivo": motivo}, "parsing_error": None}


class RevisoreSempreUguale(RevisoreFinto):
    """Dà sempre la stessa valutazione e non si esaurisce mai."""

    def __init__(self, coerente: str, motivo: str):
        super().__init__([])
        self.uscita = valutazione(coerente, motivo)

    def invoke(self, messaggi: list[BaseMessage]) -> dict:
        self.chiamate.append(list(messaggi))
        return self.uscita


def revisore_sempre_coerente() -> RevisoreFinto:
    """Approva sempre: serve ai test esistenti, che non riguardano il revisore."""
    return RevisoreSempreUguale("sì", "motivo di prova")


def revisore_sempre_contrario() -> RevisoreFinto:
    """Rifiuta sempre: serve a provare il limite di revisioni (evidenza del PDF)."""
    return RevisoreSempreUguale("no", "manca una parte")


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
