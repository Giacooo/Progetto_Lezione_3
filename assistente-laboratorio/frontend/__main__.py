"""Avvio del front-end (lezione 6, step 8):  python -m frontend"""

# COSA FA QUESTO FILE
# Legge la configurazione (.env della cartella corrente + ambiente) e avvia il server del
# front-end con uvicorn (porta 8002 se non configurata). La pagina si apre nel browser su
# http://localhost:8002. Il back-end non deve essere già acceso: se manca, è la pagina a
# mostrare l'errore. Codice di uscita: 2 = configurazione non valida.

import sys
from pathlib import Path

import httpx
import uvicorn

from frontend.app import ATTESA_PROXY, crea_app
from frontend.configurazione import (
    ErroreConfigurazioneFrontend,
    carica_configurazione,
    configura_log,
    leggi_ambiente,
)


def main() -> int:
    try:
        config = carica_configurazione(leggi_ambiente(Path.cwd()))
    except ErroreConfigurazioneFrontend as e:
        print(f"Configurazione non valida: {e}", file=sys.stderr)
        return 2
    configura_log(config.log_level)
    client_backend = httpx.Client(base_url=config.backend_url, timeout=ATTESA_PROXY)
    uvicorn.run(crea_app(client_backend), host=config.host, port=config.porta)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
