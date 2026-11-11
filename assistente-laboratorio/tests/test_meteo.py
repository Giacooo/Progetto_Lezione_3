"""Test del meteo: HTTP simulato con httpx.MockTransport, senza rete e senza modello."""

# COSA FA QUESTO FILE
# Un "gestore" finto risponde al posto di Open-Meteo: così si provano la risposta normale,
# la città ambigua, la città inesistente e ogni tipo di errore del servizio, sempre offline.

import httpx
import pytest

from assistente.strumenti_mcp.meteo import meteo_citta

PORDENONE = {
    "name": "Pordenone", "admin1": "Friuli-Venezia Giulia", "country": "Italia",
    "latitude": 45.95689, "longitude": 12.66051,
}
UDINE = {
    "name": "Udine", "admin1": "Friuli-Venezia Giulia", "country": "Italia",
    "latitude": 46.06093, "longitude": 13.24216,
}
UDINE_OMONIMA = {
    "name": "Udine", "admin1": "Lombardia", "country": "Italia",
    "latitude": 45.5, "longitude": 9.5,
}


def previsione(codice=3):
    return {
        "timezone": "Europe/Rome",
        "current_units": {"temperature_2m": "°C"},
        "current": {"time": "2026-11-10T12:00", "temperature_2m": 11.4, "weather_code": codice},
    }


def client_finto(geocoding, forecast=None):
    """Client httpx che risponde con i dati indicati (dict = JSON, Response = risposta pronta)."""

    def gestore(richiesta: httpx.Request) -> httpx.Response:
        dati = geocoding if richiesta.url.host == "geocoding-api.open-meteo.com" else forecast
        if isinstance(dati, httpx.Response):
            return dati
        return httpx.Response(200, json=dati)

    return httpx.Client(transport=httpx.MockTransport(gestore))


def client_che_solleva(eccezione):
    def gestore(richiesta: httpx.Request) -> httpx.Response:
        raise eccezione("simulato", request=richiesta)

    return httpx.Client(transport=httpx.MockTransport(gestore))


def test_citta_unica():
    testo = meteo_citta("Pordenone", client_finto({"results": [PORDENONE]}, previsione()))
    assert testo == (
        "Meteo a Pordenone, Friuli-Venezia Giulia, Italia (45.95689, 12.66051) "
        "alle 2026-11-10T12:00 (Europe/Rome): 11.4 °C, coperto."
    )
    assert "altre:" not in testo


def test_parametri_delle_richieste():
    richieste = []

    def gestore(richiesta: httpx.Request) -> httpx.Response:
        richieste.append(richiesta)
        if richiesta.url.host == "geocoding-api.open-meteo.com":
            return httpx.Response(200, json={"results": [PORDENONE]})
        return httpx.Response(200, json=previsione())

    meteo_citta("  Pordenone ", httpx.Client(transport=httpx.MockTransport(gestore)))
    geo, prev = richieste
    assert str(geo.url).startswith("https://geocoding-api.open-meteo.com/v1/search")
    assert dict(geo.url.params) == {"name": "Pordenone", "count": "5", "language": "it", "format": "json"}
    assert str(prev.url).startswith("https://api.open-meteo.com/v1/forecast")
    assert dict(prev.url.params) == {
        "latitude": "45.95689", "longitude": "12.66051",
        "current": "temperature_2m,weather_code", "timezone": "auto",
    }


def test_citta_ambigua_dichiara_le_altre():
    testo = meteo_citta("Udine", client_finto({"results": [UDINE, UDINE_OMONIMA]}, previsione(0)))
    assert testo.startswith("Meteo a Udine, Friuli-Venezia Giulia, Italia (46.06093, 13.24216)")
    assert "sereno." in testo
    assert testo.endswith("Scelta la prima corrispondenza; altre: Udine, Lombardia, Italia.")


def test_citta_non_trovata():
    with pytest.raises(ValueError, match="Città non trovata: Atlantide"):
        meteo_citta("Atlantide", client_finto({"generationtime_ms": 0.1}))


@pytest.mark.parametrize("citta", ["", "   "])
def test_citta_vuota(citta):
    with pytest.raises(ValueError, match="città non indicata"):
        meteo_citta(citta, client_che_solleva(httpx.ConnectError))


def test_rete_assente_non_e_citta_non_trovata():
    with pytest.raises(ValueError) as errore:
        meteo_citta("Pordenone", client_che_solleva(httpx.ConnectError))
    assert "Servizio meteo non raggiungibile" in str(errore.value)
    assert "non trovata" not in str(errore.value)


def test_attesa_scaduta():
    with pytest.raises(ValueError, match="Servizio meteo: attesa scaduta"):
        meteo_citta("Pordenone", client_che_solleva(httpx.ReadTimeout))


def test_errore_http():
    with pytest.raises(ValueError, match="Servizio meteo: errore HTTP 503"):
        meteo_citta("Pordenone", client_finto(httpx.Response(503)))


def test_errore_http_nelle_previsioni():
    with pytest.raises(ValueError, match="Servizio meteo: errore HTTP 500"):
        meteo_citta("Pordenone", client_finto({"results": [PORDENONE]}, httpx.Response(500)))


def test_corpo_non_json():
    with pytest.raises(ValueError, match="Servizio meteo: risposta non valida"):
        meteo_citta("Pordenone", client_finto(httpx.Response(200, text="<html>no</html>")))


def test_campi_mancanti():
    with pytest.raises(ValueError, match="Servizio meteo: risposta non valida"):
        meteo_citta("Pordenone", client_finto({"results": [PORDENONE]}, {"current": {}}))


@pytest.mark.parametrize("results", ["Pordenone", {"name": "Pordenone"}, [PORDENONE, "Udine"]])
def test_geocoding_con_risultati_strani(results):
    with pytest.raises(ValueError, match="Servizio meteo: risposta non valida"):
        meteo_citta("Pordenone", client_finto({"results": results}, previsione()))


def test_codice_wmo_sconosciuto():
    testo = meteo_citta("Pordenone", client_finto({"results": [PORDENONE]}, previsione(999)))
    assert "condizione non riconosciuta (codice 999)" in testo


@pytest.mark.parametrize(
    ("codice", "condizione"),
    [(1, "prevalentemente sereno"), (2, "parzialmente nuvoloso"), (48, "nebbia"),
     (53, "pioviggine"), (65, "pioggia"), (71, "neve"), (82, "rovesci"), (95, "temporale"),
     (99, "temporale con grandine")],
)
def test_condizioni_wmo(codice, condizione):
    testo = meteo_citta("Pordenone", client_finto({"results": [PORDENONE]}, previsione(codice)))
    assert testo.endswith(f"11.4 °C, {condizione}.")
