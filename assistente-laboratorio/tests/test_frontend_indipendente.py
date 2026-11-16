"""Il front-end parla solo con il back-end, e non scrive indirizzi nel codice della pagina (step 8)."""

# COSA PROVA QUESTO FILE
# - Nessun modulo Python di frontend/ importa assistente (l'agente) o backend: il front-end
#   parla con il back-end solo via HTTP (letto con il modulo ast, senza eseguire il codice).
# - Nessun file della pagina (frontend/statico/) contiene porte o indirizzi di agente e
#   back-end: la pagina chiama solo /api/... e l'indirizzo vero sta nella configurazione.

import ast
from pathlib import Path

CARTELLA_FRONTEND = Path(__file__).resolve().parent.parent / "frontend"
VIETATI_NELLA_PAGINA = ("8000", "8001", "localhost", "127.0.0.1", "AGENTE")


def moduli_importati(file: Path) -> list[str]:
    albero = ast.parse(file.read_text(encoding="utf-8"))
    nomi = []
    for nodo in ast.walk(albero):
        if isinstance(nodo, ast.Import):
            nomi += [alias.name for alias in nodo.names]
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            nomi.append(nodo.module)
    return nomi


def test_frontend_non_importa_agente_ne_backend():
    file = sorted(CARTELLA_FRONTEND.glob("*.py"))
    assert {f.name for f in file} >= {"__init__.py", "configurazione.py", "contratto.py", "app.py"}
    for f in file:
        vietati = [m for m in moduli_importati(f)
                   if m.split(".")[0] in ("assistente", "backend")]
        assert vietati == [], f"{f.name} importa {vietati}"


def test_pagina_senza_indirizzi():
    file = sorted((CARTELLA_FRONTEND / "statico").iterdir())
    assert file, "frontend/statico/ è vuota"
    for f in file:
        testo = f.read_text(encoding="utf-8")
        trovati = [v for v in VIETATI_NELLA_PAGINA if v in testo]
        assert trovati == [], f"{f.name} contiene {trovati}"
