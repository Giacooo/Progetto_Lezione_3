"""Meteo attuale di una città dal servizio pubblico Open-Meteo.

# COSA FA QUESTO FILE
Due richieste HTTP: il geocoding trasforma il nome della città in coordinate, poi le
previsioni danno temperatura e codice meteo WMO attuali. Il client httpx arriva da fuori
(il server ne crea uno vero, i test uno simulato), così i test non usano la rete.
Ogni errore è un ValueError con un messaggio in italiano che distingue la città non
trovata dai problemi del servizio (rete assente, attesa scaduta, errore HTTP, risposta strana).
"""

import httpx

URL_GEOCODING = "https://geocoding-api.open-meteo.com/v1/search"
URL_PREVISIONI = "https://api.open-meteo.com/v1/forecast"

# Codici meteo WMO usati da Open-Meteo, tradotti in italiano.
CONDIZIONI = {
    0: "sereno",
    1: "prevalentemente sereno",
    2: "parzialmente nuvoloso",
    3: "coperto",
    45: "nebbia", 48: "nebbia",
    51: "pioviggine", 53: "pioviggine", 55: "pioviggine",
    61: "pioggia", 63: "pioggia", 65: "pioggia",
    71: "neve", 73: "neve", 75: "neve",
    80: "rovesci", 81: "rovesci", 82: "rovesci",
    95: "temporale",
    96: "temporale con grandine", 99: "temporale con grandine",
}


def _chiedi_json(client: httpx.Client, url: str, parametri: dict) -> dict:
    """Esegue una GET e restituisce il JSON; traduce ogni problema in un ValueError distinto."""
    try:
        risposta = client.get(url, params=parametri)
    except httpx.TimeoutException as errore:  # va prima: è anche un TransportError
        raise ValueError("Servizio meteo: attesa scaduta.") from errore
    except httpx.TransportError as errore:
        raise ValueError("Servizio meteo non raggiungibile: controlla la connessione.") from errore
    if risposta.status_code >= 400:
        raise ValueError(f"Servizio meteo: errore HTTP {risposta.status_code}.")
    try:
        dati = risposta.json()
    except ValueError as errore:
        raise ValueError("Servizio meteo: risposta non valida.") from errore
    if not isinstance(dati, dict):
        raise ValueError("Servizio meteo: risposta non valida.")
    return dati


def _luogo(risultato: dict) -> str:
    """«nome, regione, paese», saltando le parti che il geocoding non fornisce."""
    parti = (risultato.get("name"), risultato.get("admin1"), risultato.get("country"))
    return ", ".join(parte for parte in parti if parte)


def meteo_citta(citta: str, client: httpx.Client) -> str:
    """Meteo attuale della città; se il nome è ambiguo usa la prima corrispondenza e lo dice."""
    citta = citta.strip()
    if not citta:
        raise ValueError("città non indicata: scrivi il nome di una città.")

    geocoding = _chiedi_json(
        client, URL_GEOCODING, {"name": citta, "count": 5, "language": "it", "format": "json"}
    )
    risultati = geocoding.get("results")
    if not risultati:
        raise ValueError(f"Città non trovata: {citta}")

    # Campi che ci aspettiamo dal servizio: se mancano o hanno un tipo strano, la risposta non è valida.
    campi_strani = (KeyError, IndexError, TypeError, AttributeError)
    try:
        if not isinstance(risultati, list):
            raise TypeError("results non è un elenco")
        scelta = risultati[0]
        latitudine, longitudine = scelta["latitude"], scelta["longitude"]
        altre = [_luogo(risultato) for risultato in risultati[1:]]
    except campi_strani as errore:
        raise ValueError("Servizio meteo: risposta non valida.") from errore

    previsioni = _chiedi_json(
        client,
        URL_PREVISIONI,
        {
            "latitude": latitudine,
            "longitude": longitudine,
            "current": "temperature_2m,weather_code",
            "timezone": "auto",
        },
    )
    try:
        attuale = previsioni["current"]
        temperatura = attuale["temperature_2m"]
        unita = previsioni["current_units"]["temperature_2m"]
        codice = attuale["weather_code"]
        ora = attuale["time"]
        fuso = previsioni["timezone"]
    except campi_strani as errore:
        raise ValueError("Servizio meteo: risposta non valida.") from errore

    condizione = CONDIZIONI.get(codice, f"condizione non riconosciuta (codice {codice})")
    testo = (
        f"Meteo a {_luogo(scelta)} ({latitudine}, {longitudine}) alle {ora} ({fuso}): "
        f"{temperatura} {unita}, {condizione}."
    )
    if altre:
        testo += f" Scelta la prima corrispondenza; altre: {'; '.join(altre)}."
    return testo
