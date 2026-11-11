"""Strumenti che il modello può richiedere e che il programma esegue davvero."""

# COSA FA QUESTO FILE
# Contiene lo "strumento orologio". Il modello non sa che ora è: può solo CHIEDERE
# di usare lo strumento. Chi lo esegue davvero, e legge l'ora vera, è questo programma.

from collections.abc import Callable
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from langchain_core.tools import BaseTool, StructuredTool

# Questa descrizione viene mostrata al modello: è il "cartellino" che gli spiega
# a cosa serve lo strumento e quando usarlo. Se è scritta male, il modello lo usa male.
DESCRIZIONE_ORA = (
    "Restituisce data e ora correnti nel fuso orario configurato. Da usare ogni volta "
    "che servono data, ora o giorno della settimana attuali."
)


def formatta_ora(fuso: ZoneInfo, istante: datetime) -> str:
    """Data e ora ISO 8601 con offset, seguite dal nome del fuso."""
    # Passi, da dentro verso fuori:
    # 1) istante.astimezone(fuso)  converte l'istante nel fuso scelto (es. Roma);
    # 2) .isoformat(timespec='seconds')  lo scrive come 2026-11-02T11:06:05+01:00,
    #    cioè data, ora al secondo e differenza dall'ora di Greenwich (+01:00);
    # 3) (fuso.key)  aggiunge il nome del fuso, es. (Europe/Rome).
    return f"{istante.astimezone(fuso).isoformat(timespec='seconds')} ({fuso.key})"


def crea_strumenti(
    fuso: ZoneInfo,
    # "adesso" è la funzione che dice che ora è. Di solito legge l'orologio vero (in UTC),
    # ma nei test se ne passa una finta che restituisce sempre lo stesso istante:
    # così il risultato atteso è sempre uguale.
    adesso: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> list[BaseTool]:
    """Strumenti disponibili; `adesso` permette ai test di fissare l'istante."""

    # Questa è la funzione che il programma esegue quando il modello chiede
    # "ora_corrente". Non ha parametri: usa sempre il fuso ricevuto qui sopra
    # (quello del .env), per questo non si può chiedere l'ora di un'altra città.
    def ora_corrente() -> str:
        return formatta_ora(fuso, adesso())

    # Trasforma la funzione in uno "strumento" che il modello può conoscere:
    # nome, descrizione e (nessun) parametro. Restituisce una lista con un solo strumento.
    return [StructuredTool.from_function(ora_corrente, name="ora_corrente", description=DESCRIZIONE_ORA)]
