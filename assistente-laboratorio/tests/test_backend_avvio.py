"""Test dell'avvio del back-end: python -m backend (lezione 6, step 7)."""

# COSA PROVA QUESTO FILE
# main() legge il .env della cartella corrente, prepara le tabelle e avvia uvicorn. Qui uvicorn
# è sostituito da una funzione che registra con che cosa è stato chiamato: nessuna porta aperta.
# Codici di uscita: 2 = configurazione non valida, 3 = database non disponibile.

import logging

from backend import __main__ as avvio
from backend.agente_remoto import AgenteRemoto

VARIABILI = ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB", "POSTGRES_HOST", "POSTGRES_PORTA",
             "BACKEND_HOST", "BACKEND_PORTA", "AGENTE_URL", "LOG_LEVEL")
ENV_VALIDO = "POSTGRES_USER=utente\nPOSTGRES_PASSWORD=segreta\nPOSTGRES_DB=chat\n"


def prepara_main(tmp_path, monkeypatch, env, prepara=None):
    (tmp_path / ".env").write_text(env, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    for nome in VARIABILI:
        monkeypatch.delenv(nome, raising=False)
    avvii = []
    monkeypatch.setattr("backend.__main__.uvicorn.run", lambda app, host, port: avvii.append((app, host, port)))
    if prepara is not None:
        monkeypatch.setattr("backend.__main__.ArchivioPostgres.prepara", prepara)
    return avvii


def test_main_configurazione_non_valida(tmp_path, monkeypatch, capsys):
    avvii = prepara_main(tmp_path, monkeypatch, "POSTGRES_USER=utente\n")
    assert avvio.main() == 2
    errore = capsys.readouterr().err
    assert "Configurazione non valida:" in errore
    assert "POSTGRES_PASSWORD" in errore
    assert avvii == []


# Sulla porta 1 non risponde nessuno: è come un PostgreSQL spento.
def test_main_database_non_disponibile(tmp_path, monkeypatch, capsys):
    avvii = prepara_main(tmp_path, monkeypatch, ENV_VALIDO + "POSTGRES_HOST=127.0.0.1\nPOSTGRES_PORTA=1\n")
    assert avvio.main() == 3
    assert "Database non disponibile:" in capsys.readouterr().err
    assert avvii == []


def test_main_avvia_uvicorn(tmp_path, monkeypatch):
    preparati = []
    avvii = prepara_main(
        tmp_path, monkeypatch,
        ENV_VALIDO + "BACKEND_HOST=0.0.0.0\nBACKEND_PORTA=8101\nAGENTE_URL=http://agente:8000\nPOSTGRES_HOST=db\n",
        prepara=lambda archivio: preparati.append(archivio.parametri),
    )
    assert avvio.main() == 0
    ((app, host, porta),) = avvii
    assert (host, porta) == ("0.0.0.0", 8101)
    assert app.title == "Back-end del laboratorio"
    (parametri,) = preparati
    assert (parametri.host, parametri.database, parametri.utente) == ("db", "chat", "utente")


def test_main_agente_dall_indirizzo_configurato(tmp_path, monkeypatch):
    creati = []
    prepara_main(tmp_path, monkeypatch, ENV_VALIDO + "AGENTE_URL=http://agente:8000\n", prepara=lambda a: None)
    monkeypatch.setattr("backend.__main__.AgenteRemoto", lambda url: creati.append(url) or AgenteRemoto(url))
    assert avvio.main() == 0
    assert creati == ["http://agente:8000"]


def test_log_attivo(tmp_path, monkeypatch):
    prepara_main(tmp_path, monkeypatch, ENV_VALIDO, prepara=lambda a: None)
    assert avvio.main() == 0
    assert logging.getLogger("backend").getEffectiveLevel() == logging.INFO
