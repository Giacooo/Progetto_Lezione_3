"""Avvio del back-end (lezione 6, step 7):  python -m backend"""

# COSA FA QUESTO FILE
# Legge la configurazione (.env della cartella corrente + ambiente), crea le tabelle in
# PostgreSQL se mancano e avvia il servizio HTTP con uvicorn (porta 8001 se non configurata).
# Codici di uscita: 2 = configurazione non valida, 3 = database non disponibile (come l'agente).

import sys
from pathlib import Path

import uvicorn

from backend.agente_remoto import AgenteRemoto
from backend.app import crea_app
from backend.archivio import ArchivioPostgres, ErroreDatabase
from backend.configurazione import (
    ErroreConfigurazioneBackend,
    carica_configurazione,
    configura_log,
    leggi_ambiente,
)


def main() -> int:
    try:
        config = carica_configurazione(leggi_ambiente(Path.cwd()))
    except ErroreConfigurazioneBackend as e:
        print(f"Configurazione non valida: {e}", file=sys.stderr)
        return 2
    configura_log(config.log_level)
    archivio = ArchivioPostgres(config.database)
    try:
        archivio.prepara()
    except ErroreDatabase as e:
        print(f"Database non disponibile: {e}", file=sys.stderr)
        return 3
    uvicorn.run(crea_app(archivio, AgenteRemoto(config.agente_url)), host=config.host, port=config.porta)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
