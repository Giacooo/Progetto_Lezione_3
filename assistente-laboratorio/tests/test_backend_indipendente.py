"""Il back-end non conosce l'agente: nessun modulo di backend/ importa assistente (step 7)."""

# COSA PROVA QUESTO FILE
# Il back-end parla con l'agente solo via HTTP. Lo si verifica leggendo il codice di ogni file
# .py di backend/ con il modulo ast (l'albero della sintassi di Python), senza eseguirlo.

import ast
from pathlib import Path

CARTELLA_BACKEND = Path(__file__).resolve().parent.parent / "backend"


def moduli_importati(file: Path) -> list[str]:
    albero = ast.parse(file.read_text(encoding="utf-8"))
    nomi = []
    for nodo in ast.walk(albero):
        if isinstance(nodo, ast.Import):
            nomi += [alias.name for alias in nodo.names]
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            nomi.append(nodo.module)
    return nomi


def test_backend_non_importa_assistente():
    file = sorted(CARTELLA_BACKEND.glob("*.py"))
    assert {f.name for f in file} >= {"__init__.py", "configurazione.py", "archivio.py", "agente_remoto.py", "app.py"}
    for f in file:
        vietati = [m for m in moduli_importati(f) if m == "assistente" or m.startswith("assistente.")]
        assert vietati == [], f"{f.name} importa {vietati}"
