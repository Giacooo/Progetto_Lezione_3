"""Preferenze dell'utente: validazione, predefiniti e paragrafo del prompt di sistema."""

# COSA FA QUESTO FILE
# Il server MCP pubblica il file delle preferenze (lingua, fuso orario, stile) come "resource":
# la legge il programma (l'host), non il modello. Qui ci sono solo funzioni semplici, senza
# server e senza LM Studio:
#   - leggi_preferenze_da_testo: controlla il contenuto del file e lo trasforma in Preferenze;
#   - predefinite: i valori da usare quando il file non c'è o non è valido (tutti o niente);
#   - prompt_agente: il prompt di sistema dell'agente, con le preferenze IN CIMA.

import json
from dataclasses import dataclass
from zoneinfo import ZoneInfo, available_timezones

from assistente.errori import ErrorePreferenze

# Gli unici stili ammessi, con la frase che li descrive al modello.
STILI = {
    "sintetico": "risposte brevi e chiare, in poche frasi",
    "dettagliato": "risposte complete, con spiegazioni e passaggi",
}


@dataclass(frozen=True)
class Preferenze:
    lingua: str
    fuso: ZoneInfo
    stile: str


# Valori usati quando la resource non è disponibile o non è valida: lingua italiana, stile
# sintetico e il fuso di ripiego (quello di FUSO_ORARIO).
def predefinite(fuso: ZoneInfo) -> Preferenze:
    return Preferenze("italiano", fuso, "sintetico")


# Controlla il testo del file. Ogni difetto diventa un ErrorePreferenze con il motivo,
# mai un errore generico: chi chiama può ripiegare sui predefiniti.
def leggi_preferenze_da_testo(testo: str) -> Preferenze:
    try:
        dati = json.loads(testo)
    except (ValueError, RecursionError) as errore:  # RecursionError: JSON annidato troppo in profondità
        raise ErrorePreferenze(f"JSON non valido ({errore})") from errore
    if not isinstance(dati, dict):
        raise ErrorePreferenze("il file deve contenere un oggetto JSON")
    for chiave in ("lingua", "fuso_orario", "stile"):
        if chiave not in dati:
            raise ErrorePreferenze(f"manca la chiave '{chiave}'")

    lingua = dati["lingua"]
    # isprintable() rifiuta ogni "a capo" (anche quelli Unicode) e i caratteri spezzati,
    # che finirebbero nel prompt di sistema o farebbero fallire la richiesta al modello.
    if not isinstance(lingua, str) or not lingua.strip() or not lingua.strip().isprintable():
        raise ErrorePreferenze(f"lingua non valida: {lingua!r} (testo non vuoto, su una riga)")
    lingua = lingua.strip()

    nome_fuso = dati["fuso_orario"]
    if not isinstance(nome_fuso, str):
        raise ErrorePreferenze(f"fuso_orario non valido: {nome_fuso!r} (deve essere un testo)")
    # Solo i nomi dell'elenco IANA: su Windows ZoneInfo accetterebbe anche "Europe/Rome "
    # o "Europe\Rome", che in Docker (Linux) verrebbero invece rifiutati.
    if nome_fuso not in available_timezones():
        raise ErrorePreferenze(f"fuso_orario non valido: {nome_fuso!r}")
    try:
        fuso = ZoneInfo(nome_fuso)
    except Exception as errore:  # nome sconosciuto, cartella, percorso strano...
        raise ErrorePreferenze(f"fuso_orario non valido: {nome_fuso!r}") from errore

    stile = dati["stile"]
    if not isinstance(stile, str) or stile not in STILI:  # (il controllo del tipo evita il TypeError con una lista)
        raise ErrorePreferenze(f"stile deve essere 'sintetico' o 'dettagliato', non {stile!r}")

    return Preferenze(lingua, fuso, stile)


# Il prompt di sistema dell'agente: paragrafo delle preferenze in cima (meglio in cima, dice
# il PDF), riga vuota, poi il prompt di base. Il prompt di base arriva come parametro perché
# vive in grafo.py, che importa questo file.
def prompt_agente(preferenze: Preferenze, prompt_base: str) -> str:
    return (
        f"Preferenze dell'utente: rispondi in {preferenze.lingua}. "
        f"Stile: {STILI[preferenze.stile]}. "
        f"Il fuso orario predefinito è {preferenze.fuso.key}: "
        "lo strumento ora_corrente lo usa già, non chiederlo all'utente."
        f"\n\n{prompt_base}"
    )
