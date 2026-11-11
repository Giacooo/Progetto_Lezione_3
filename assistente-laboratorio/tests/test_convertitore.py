import pytest
from assistente.strumenti_mcp.convertitore import converti_unita


@pytest.mark.parametrize("valore, da, a, atteso", [
    (10, "km", "mi", "10 km = 6.2137 mi"),
    (100, "C", "F", "100 C = 212 F"),
    (0, "K", "C", "0 K = -273.15 C"),
    (1, "lb", "g", "1 lb = 453.5924 g"),
])
def test_conversioni_valide(valore, da, a, atteso):
    assert converti_unita(valore, da, a) == atteso


@pytest.mark.parametrize("valore, da, a, frammento", [
    (1, "parsec", "m", "ammesse"),
    (1, "m", "parsec", "ammesse"),
    (1, "m", "kg", "incompatibil"),
    (-300, "C", "K", "zero assoluto"),
    (-1, "K", "C", "zero assoluto"),
])
def test_input_rifiutati(valore, da, a, frammento):
    with pytest.raises(ValueError, match=frammento):
        converti_unita(valore, da, a)


def test_messaggio_unita_sconosciuta_elenca_le_unita():
    with pytest.raises(ValueError) as errore:
        converti_unita(1, "parsec", "m")
    for simbolo in ("mm", "km", "mi", "lb", "oz", "C", "F", "K"):
        assert simbolo in str(errore.value)
