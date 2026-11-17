"""Test dell'avvio del front-end: python -m frontend (lezione 6, step 8)."""

# COSA PROVA QUESTO FILE
# main() legge il .env della cartella corrente e avvia uvicorn. Qui uvicorn è sostituito da una
# funzione che registra con che cosa è stato chiamato: nessuna porta aperta.
# Codice di uscita 2 = configurazione non valida. Il back-end spento NON impedisce l'avvio: sarà
# la pagina a mostrare l'errore.

from frontend import __main__ as avvio

VARIABILI = ("BACKEND_URL", "FRONTEND_HOST", "FRONTEND_PORTA", "LOG_LEVEL")


def prepara_main(tmp_path, monkeypatch, env):
    (tmp_path / ".env").write_text(env, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    for nome in VARIABILI:
        monkeypatch.delenv(nome, raising=False)
    avvii = []
    monkeypatch.setattr("frontend.__main__.uvicorn.run", lambda app, host, port: avvii.append((app, host, port)))
    return avvii


def test_main_configurazione_non_valida(tmp_path, monkeypatch, capsys):
    avvii = prepara_main(tmp_path, monkeypatch, "FRONTEND_PORTA=abc\n")
    assert avvio.main() == 2
    errore = capsys.readouterr().err
    assert "Configurazione non valida:" in errore
    assert "FRONTEND_PORTA" in errore
    assert avvii == []


def test_main_avvia_uvicorn(tmp_path, monkeypatch):
    avvii = prepara_main(tmp_path, monkeypatch,
                         "FRONTEND_HOST=0.0.0.0\nFRONTEND_PORTA=8102\nBACKEND_URL=http://backend:8001\n")
    assert avvio.main() == 0
    ((app, host, porta),) = avvii
    assert (host, porta) == ("0.0.0.0", 8102)
    assert app.title == "Front-end del laboratorio"
