"""Strumenti che il modello può richiedere e che il programma esegue davvero."""

from collections.abc import Callable
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from langchain_core.tools import BaseTool, StructuredTool

DESCRIZIONE_ORA = (
    "Restituisce data e ora correnti nel fuso orario configurato. Da usare ogni volta "
    "che servono data, ora o giorno della settimana attuali."
)


def formatta_ora(fuso: ZoneInfo, istante: datetime) -> str:
    """Data e ora ISO 8601 con offset, seguite dal nome del fuso."""
    return f"{istante.astimezone(fuso).isoformat(timespec='seconds')} ({fuso.key})"


def crea_strumenti(
    fuso: ZoneInfo,
    adesso: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> list[BaseTool]:
    """Strumenti disponibili; `adesso` permette ai test di fissare l'istante."""

    def ora_corrente() -> str:
        return formatta_ora(fuso, adesso())

    return [StructuredTool.from_function(ora_corrente, name="ora_corrente", description=DESCRIZIONE_ORA)]
