"""Server MCP con gli strumenti del laboratorio."""

# COSA FA QUESTO FILE
# Pubblica gli strumenti tramite il protocollo MCP. Il programma principale lo avvia come
# sottoprocesso (trasporto stdio) e ne scopre il catalogo (discovery) invece di riscriverlo.
# ATTENZIONE: su stdout passa solo il protocollo, quindi niente print; i log vanno su stderr.
# Convenzione: la funzione registrata ha lo stesso nome dello strumento, la docstring in
# italiano e' la descrizione che vede il modello, e ogni ValueError diventa un ToolError.

import logging
import sys
from pathlib import Path
from typing import Annotated

import httpx
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from assistente.strumenti_mcp import calcolatrice, convertitore
from assistente.strumenti_mcp import catalogo as dominio_catalogo
from assistente.strumenti_mcp import giorni as dominio_giorni
from assistente.strumenti_mcp import meteo as dominio_meteo
from assistente.strumenti_mcp import note as dominio_note

logger = logging.getLogger(__name__)

mcp = FastMCP("Strumenti del laboratorio")

# Le festività si caricano una sola volta, all'avvio del server.
FESTIVITA = dominio_giorni.carica_festivita(Path(__file__).parent / "dati" / "festivita.json")
# Il catalogo dei corsi si carica una sola volta, all'avvio del server.
CORSI = dominio_catalogo.carica_catalogo(Path(__file__).parent / "dati" / "catalogo.json")
# Archivio delle note, relativo alla cartella di lavoro (le funzioni lo leggono a ogni chiamata).
PERCORSO_NOTE = Path("archivio/note.sqlite")


@mcp.tool
def calcola(espressione: str) -> str:
    """Valuta un'espressione aritmetica con numeri, + - * / // % ** e parentesi.

    Usala per ogni calcolo, anche semplice, invece di calcolare a mente.
    Traduci le parole italiane negli operatori: "per", "moltiplicato", "x" -> *;
    "diviso" -> /; "più" -> +; "meno" -> -. Esempio: "1234 per 5678" -> "1234 * 5678".
    """
    try:
        risultato = calcolatrice.calcola(espressione)
    except ValueError as errore:
        logger.info("calcola rifiutata: %s", errore)
        raise ToolError(str(errore)) from errore
    return risultato


@mcp.tool
def converti_unita(valore: float, da_unita: str, a_unita: str) -> str:
    """Converte un valore da un'unità a un'altra della stessa categoria.

    Passa i SIMBOLI tra virgolette qui sotto (maiuscole comprese), non i nomi in italiano.
    Lunghezza: "mm" = millimetri, "cm" = centimetri, "m" = metri, "km" = chilometri,
    "in" = pollici, "ft" = piedi, "mi" = miglia.
    Massa: "g" = grammi, "kg" = chilogrammi, "lb" = libbre, "oz" = once.
    Temperatura: "C" = gradi Celsius, "F" = gradi Fahrenheit, "K" = kelvin.
    Esempio: "quante miglia sono 10 chilometri" -> valore=10, da_unita="km", a_unita="mi".
    Non si convertono unità di categorie diverse (es. m in kg).
    """
    try:
        risultato = convertitore.converti_unita(valore, da_unita, a_unita)
    except ValueError as errore:
        logger.info("converti_unita rifiutata: %s", errore)
        raise ToolError(str(errore)) from errore
    return risultato


@mcp.tool
def conta_giorni(data_inizio: str, data_fine: str) -> str:
    """Conta i giorni di calendario e lavorativi tra due date, con le festività incluse.

    Le date vanno passate SOLO come "AAAA-MM-GG": traduci la data italiana,
    "23 dicembre 2026" -> "2026-12-23". L'inizio è escluso, la fine è inclusa.
    Esempio: "quanti giorni lavorativi tra il 23 e il 28 dicembre 2026" ->
    data_inizio="2026-12-23", data_fine="2026-12-28". Valida per gli anni 2026 e 2027.
    """
    try:
        risultato = dominio_giorni.conta_giorni(data_inizio, data_fine, FESTIVITA)
    except ValueError as errore:
        logger.info("conta_giorni rifiutata: %s", errore)
        raise ToolError(str(errore)) from errore
    return risultato


@mcp.tool
def aggiungi_giorni_lavorativi(data_inizio: str, giorni: int) -> str:
    """Calcola la data di scadenza dopo un numero di giorni lavorativi (da 1 a 365).

    La data va passata SOLO come "AAAA-MM-GG": traduci "20 dicembre 2026" -> "2026-12-20".
    Il giorno di partenza non conta. Esempio: "10 giorni lavorativi dopo il 2026-12-20" ->
    data_inizio="2026-12-20", giorni=10. Valida per gli anni 2026 e 2027.
    """
    try:
        risultato = dominio_giorni.aggiungi_giorni_lavorativi(data_inizio, giorni, FESTIVITA)
    except ValueError as errore:
        logger.info("aggiungi_giorni_lavorativi rifiutata: %s", errore)
        raise ToolError(str(errore)) from errore
    return risultato


@mcp.tool
def cerca_corsi(
    testo: Annotated[
        str,
        'UNA sola parola: la materia (es. "Python") OPPURE la sede (es. "Udine"), '
        "mai entrambe insieme.",
    ],
    max_risultati: int = 5,
) -> str:
    """Cerca corsi con UNA parola chiave (titolo, codice o sede) e restituisce un elenco breve.

    Cerca una sola parola alla volta, per esempio "Python" oppure "Udine". L'elenco riporta
    codice, titolo e sede, ma NON la durata: per i dettagli usa dettaglio_corso.
    max_risultati (da 1 a 20, predefinito 5) limita il numero di corsi elencati.
    Esempio: "Quanto dura il corso di Python a Udine?" -> cerca_corsi(testo="Python"),
    poi dettaglio_corso(codice=<codice del corso con sede Udine>).
    """
    try:
        risultato = dominio_catalogo.cerca_corsi(testo, max_risultati, CORSI)
    except ValueError as errore:
        logger.info("cerca_corsi rifiutata: %s", errore)
        raise ToolError(str(errore)) from errore
    return risultato


@mcp.tool
def dettaglio_corso(codice: str) -> str:
    """Dà tutti i dettagli di UN corso (titolo, sede, durata in ore) dato il suo codice esatto.

    Richiede il codice esatto, nel formato "ITS-XXX-NN", preso dal risultato di cerca_corsi:
    se non lo conosci, trovalo prima con cerca_corsi. Usala dopo cerca_corsi per sapere la durata o i dettagli di un corso.
    """
    try:
        risultato = dominio_catalogo.dettaglio_corso(codice, CORSI)
    except ValueError as errore:
        logger.info("dettaglio_corso rifiutata: %s", errore)
        raise ToolError(str(errore)) from errore
    return risultato


@mcp.tool
def aggiungi_nota(
    testo: Annotated[
        str, 'Il contenuto della nota, senza le parole "ricordami di" (es. "consegnare il report venerdì").'
    ],
) -> str:
    """Crea una nota: salva in modo permanente un testo (massimo 500 caratteri) e ne restituisce l'ID.

    Usala quando l'utente chiede di ricordare o annotare qualcosa.
    Esempio: "Ricordami di consegnare il report venerdì" -> testo="consegnare il report venerdì".
    """
    try:
        risultato = dominio_note.aggiungi_nota(testo, PERCORSO_NOTE)
    except ValueError as errore:
        logger.info("aggiungi_nota rifiutata: %s", errore)
        raise ToolError(str(errore)) from errore
    return risultato


@mcp.tool
def elenca_note(
    limite: Annotated[int, "Quante note mostrare, da 1 a 50 (predefinito 10)."] = 10,
) -> str:
    """Elenca le note salvate, ciascuna con ID, data e testo, in ordine di ID crescente.

    Usala per mostrare le note e per conoscere gli ID prima di eliminarne una.
    Il limite è facoltativo: non chiederlo all'utente se non lo indica.
    Esempio: "Quali note ho?" -> elenca_note() senza argomenti.
    """
    try:
        risultato = dominio_note.elenca_note(limite, PERCORSO_NOTE)
    except ValueError as errore:
        logger.info("elenca_note rifiutata: %s", errore)
        raise ToolError(str(errore)) from errore
    return risultato


@mcp.tool
def elimina_nota(
    id_nota: Annotated[int, "L'ID numerico della nota da eliminare (es. 99)."],
) -> str:
    """Cancella una nota: elimina definitivamente la sola nota con questo ID.

    Esempio: "Elimina la nota 99" -> id_nota=99. Per vedere gli ID usa elenca_note.
    """
    try:
        risultato = dominio_note.elimina_nota(id_nota, PERCORSO_NOTE)
    except ValueError as errore:
        logger.info("elimina_nota rifiutata: %s", errore)
        raise ToolError(str(errore)) from errore
    return risultato


@mcp.tool
def meteo_citta(
    citta: Annotated[str, 'Il solo nome della città, in italiano (es. "Pordenone").'],
) -> str:
    """Dà il meteo attuale di una città (temperatura e condizioni) dal servizio Open-Meteo.

    Usala per ogni domanda sul tempo che fa adesso in una città.
    Esempio: "Che tempo fa a Pordenone?" -> citta="Pordenone".
    Se il nome è ambiguo usa la prima città trovata e lo dichiara, elencando le altre.
    """
    try:
        # Un client nuovo a ogni chiamata, chiuso alla fine; attesa massima 10 secondi.
        with httpx.Client(timeout=10.0) as client:
            risultato = dominio_meteo.meteo_citta(citta, client)
    except ValueError as errore:
        logger.info("meteo_citta rifiutata: %s", errore)
        raise ToolError(str(errore)) from errore
    return risultato


if __name__ == "__main__":
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    mcp.run(show_banner=False)
