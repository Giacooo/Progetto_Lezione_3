"""Server del front-end (lezione 6, step 8): la pagina di chat e il proxy /api verso il back-end."""

# COSA FA QUESTO FILE
# Il browser parla solo con questo server, sulla sua porta (8002):
#   GET /              la pagina (frontend/statico/: index.html, stile.css, app.js, ...)
#   /api/{percorso}    "passacarte" verso il back-end: /api/chat/3 → BACKEND_URL/chat/3
# Perché un proxy e non il back-end chiamato direttamente dal browser: la pagina e le chiamate
# hanno la stessa origine (niente CORS da aggiungere al back-end dello step 7) e l'indirizzo del
# back-end resta nella configurazione del server, non nel codice della pagina.
# Il proxy lascia passare solo le operazioni del contratto (frontend/contratto.py); le altre
# ricevono 404 senza arrivare al back-end. Le risposte del back-end tornano così come sono; se il
# back-end è spento o troppo lento risponde il proxy, nella stessa forma {"errore": "..."}.
#
# Parte asincrona (dichiarata): l'endpoint del proxy è "async def" perché il corpo della
# richiesta si legge solo in modo asincrono; la chiamata al back-end usa però il client httpx
# sincrono, eseguito in un thread a parte con run_in_threadpool (come gli endpoint "def").

import logging
import mimetypes
from pathlib import Path

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from frontend.contratto import ammessa, carica_contratto, operazioni

log = logging.getLogger("frontend")

CARTELLA_STATICA = Path(__file__).resolve().parent / "statico"

# Secondi di attesa per il back-end: più dei 600 che il back-end concede all'agente, così un
# "L'agente non ha risposto in tempo" del back-end arriva al browser; 5 s per collegarsi.
ATTESA_PROXY = httpx.Timeout(630, connect=5)

BACKEND_GIU = "Back-end non raggiungibile: controllare che sia avviato e l'indirizzo BACKEND_URL."
BACKEND_FUORI_TEMPO = "Il back-end non ha risposto in tempo."
NON_DISPONIBILE = "Operazione non disponibile."

# Su Windows il tipo dei file si legge anche dal registro, che a volte dice text/plain per .js:
# il browser rifiuterebbe allora i moduli JavaScript e la pagina resterebbe vuota.
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/css", ".css")


def _errore(codice: int, messaggio: str) -> JSONResponse:
    return JSONResponse(status_code=codice, content={"errore": messaggio},
                        media_type="application/json; charset=utf-8")


def crea_app(client_backend: httpx.Client, contratto: dict | None = None) -> FastAPI:
    """Il server del front-end; client_backend ha già il base_url del back-end (BACKEND_URL)."""
    ammesse = operazioni(contratto if contratto is not None else carica_contratto())
    app = FastAPI(title="Front-end del laboratorio", docs_url=None, redoc_url=None, openapi_url=None)

    @app.api_route("/api/{percorso:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    async def proxy(percorso: str, request: Request):
        metodo = request.method
        # Il percorso completo e già decodificato, tolto "/api" (il parametro "percorso" di
        # Starlette perde un eventuale "a capo" finale: si controlla quello che c'è davvero).
        destinazione = request.scope["path"].removeprefix("/api")
        if not ammessa(ammesse, metodo, destinazione):
            log.warning("operazione fuori contratto metodo=%s percorso=%s", metodo, destinazione)
            return _errore(404, NON_DISPONIBILE)

        corpo = await request.body()
        intestazioni = {}
        if "content-type" in request.headers:
            intestazioni["content-type"] = request.headers["content-type"]
        try:
            r = await run_in_threadpool(
                client_backend.request, metodo, destinazione,
                params=request.url.query or None, content=corpo or None, headers=intestazioni,
            )
        except httpx.TimeoutException:
            log.warning("back-end fuori tempo metodo=%s percorso=%s", metodo, destinazione)
            return _errore(504, BACKEND_FUORI_TEMPO)
        except httpx.TransportError:  # spento, indirizzo sbagliato, connessione caduta
            log.warning("back-end non raggiungibile metodo=%s percorso=%s", metodo, destinazione)
            return _errore(503, BACKEND_GIU)

        log.info("inoltro metodo=%s percorso=%s codice=%d", metodo, destinazione, r.status_code)
        if r.status_code == 204:
            return Response(status_code=204)
        return Response(content=r.content, status_code=r.status_code, media_type=r.headers.get("content-type"))

    # La pagina: montata per ultima, così /api/... ha la precedenza. html=True: "/" → index.html.
    app.mount("/", StaticFiles(directory=CARTELLA_STATICA, html=True), name="pagina")
    return app
