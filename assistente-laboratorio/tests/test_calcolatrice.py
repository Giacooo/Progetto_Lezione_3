import pytest
from assistente.strumenti_mcp.calcolatrice import calcola

@pytest.mark.parametrize("espressione, atteso", [
    ("2+3*4", "14"), ("(1.5+2)/7", "0.5"), ("10/4", "2.5"), ("10/2", "5"),
    ("7//2", "3"), ("7%3", "1"), ("-3+ +2", "-1"), ("2**10", "1024"),
])
def test_espressioni_valide(espressione, atteso):
    assert calcola(espressione) == atteso

@pytest.mark.parametrize("espressione, frammento", [
    ("", "vuota"), ("   ", "vuota"),
    ("__import__('os')", "non ammess"), ("abs(-1)", "non ammess"), ("x+1", "non ammess"),
    ("'a'*3", "non ammess"), ("1<2", "non ammess"), ("2+", "sintassi"),
    ("10/0", "zero"), ("5//0", "zero"), ("5%0", "zero"),
    ("1+" * 100 + "1", "200"), ("2**10000", "esponente"), ("(10**100)**100", "troppo grande"),
    ("9**9**9", "esponente"),
])
def test_input_rifiutati(espressione, frammento):
    with pytest.raises(ValueError, match=frammento):
        calcola(espressione)

def test_nessun_eval():
    import inspect, assistente.strumenti_mcp.calcolatrice as m
    sorgente = inspect.getsource(m)
    assert "eval(" not in sorgente and "exec(" not in sorgente
