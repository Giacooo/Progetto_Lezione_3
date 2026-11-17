"""Esegue i test JavaScript della pagina con Node, se è installato (lezione 6, step 8)."""

# COSA PROVA QUESTO FILE
# Lancia "node --test tests/js/logica.test.mjs" (test runner integrato in Node, nessun pacchetto
# npm) con TZ=UTC. Senza Node il test viene saltato con il motivo: Node non è una dipendenza
# del progetto, serve solo per questi test facoltativi.

import os
import shutil
import subprocess
from pathlib import Path

import pytest

CARTELLA_PROGETTO = Path(__file__).resolve().parent.parent


def test_logica_js_con_node():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node non installato: test JavaScript saltati")
    esito = subprocess.run(
        [node, "--test", "tests/js/logica.test.mjs"],
        cwd=CARTELLA_PROGETTO, env={**os.environ, "TZ": "UTC"},
        capture_output=True, text=True, encoding="utf-8", timeout=60,
    )
    assert esito.returncode == 0, esito.stdout + esito.stderr
