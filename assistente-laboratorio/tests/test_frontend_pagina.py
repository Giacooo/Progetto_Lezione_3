"""Controlli sui file della pagina di chat (lezione 6, step 8)."""

# COSA PROVA QUESTO FILE
# La pagina si prova davvero dal browser (prove manuali dell'utente). Qui si controllano, leggendo
# i file, le regole che non devono mai saltare:
#   - index.html carica app.js come modulo e stile.css, in italiano;
#   - il testo che arriva dal back-end (per esempio una risposta con "<script>") si mostra come
#     testo: nessun file usa innerHTML o simili, che lo interpreterebbero come HTML;
#   - i testi della pagina sono quelli della specifica;
#   - tutte le chiamate passano da api.js (le operazioni del contratto).

from pathlib import Path

import pytest

STATICO = Path(__file__).resolve().parent.parent / "frontend" / "statico"


def leggi(nome: str) -> str:
    return (STATICO / nome).read_text(encoding="utf-8")


def test_pagina_carica_il_modulo():
    html = leggi("index.html")
    for atteso in ('type="module"', 'src="app.js"', 'href="stile.css"', 'lang="it"', 'charset="utf-8"',
                   "Assistente del laboratorio", "Nuova chat", "Invia", "Elimina"):
        assert atteso in html, atteso


@pytest.mark.parametrize("nome", ["app.js", "api.js", "logica.js"])
def test_pagina_senza_innerhtml(nome):
    testo = leggi(nome)
    for vietato in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write"):
        assert vietato not in testo, f"{nome} usa {vietato}"


def test_testi_della_pagina():
    js = leggi("app.js")
    for atteso in ("L'assistente sta rispondendo…", 'Nessuna chat: premi "Nuova chat" per cominciare.',
                   "Riprova", 'Eliminare la chat "', "e tutti i suoi messaggi?", "dataElenco",
                   "descriviStrumenti"):
        assert atteso in js, atteso


def test_app_js_usa_api_js():
    js = leggi("app.js")
    assert "fetch(" not in js
    assert 'from "./api.js"' in js
