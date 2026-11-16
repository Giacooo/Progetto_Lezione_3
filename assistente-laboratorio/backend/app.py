"""API del back-end (lezione 6, step 7): le chat del front-end, salvate in PostgreSQL."""

# COSA FA QUESTO FILE
# È l'unica "porta d'ingresso" del futuro front-end (step 8). Gli endpoint:
#   POST   /chat                crea una chat (titolo facoltativo) → 201 con l'identificativo
#   GET    /chat                elenca le chat: titolo e data dell'ultimo messaggio
#   GET    /chat/{id}           legge una chat: i messaggi in ordine cronologico
#   DELETE /chat/{id}           elimina la chat e i suoi messaggi → 204
#   POST   /chat/{id}/messaggi  invia una domanda: chiama l'agente e salva domanda e risposta
#   /docs e /openapi.json       documentazione OpenAPI (il "contratto" per il front-end)
# Il front-end non conosce l'agente: lo chiama solo il back-end, via HTTP (agente_remoto.py).
# Se l'agente non risponde NON si salva niente: si restituisce l'errore e la chat resta com'era.
# Gli errori hanno sempre la stessa forma: {"errore": "messaggio in italiano"}, anche il 422.
# Gli endpoint sono funzioni normali (def): FastAPI le esegue in un thread a parte.

import logging
from datetime import datetime
from typing import Annotated, Literal

from fastapi import FastAPI, Path, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from backend.agente_remoto import ErroreAgente
from backend.archivio import ArchivioChat, ErroreDatabase, MessaggioSalvato

log = logging.getLogger("backend")

TITOLO_PREDEFINITO = "Nuova chat"
LUNGHEZZA_TITOLO = 50
CHAT_NON_TROVATA = "Chat non trovata."
DATABASE_GIU = "Database non disponibile."
ID_NON_VALIDO = "Richiesta non valida: l'identificativo della chat deve essere un numero intero positivo."

# Identificativo nel percorso: intero da 1 al massimo di una colonna BIGINT di PostgreSQL.
IdChat = Annotated[int, Path(ge=1, le=2**63 - 1, description="identificativo della chat")]


# Le risposte JSON dichiarano charset=utf-8: senza, Invoke-RestMethod di PowerShell 5.1 legge
# il testo come ISO-8859-1 e mostra «Ã¨» al posto di «è» (come nello step 6).
class RispostaJSON(JSONResponse):
    media_type = "application/json; charset=utf-8"


def titolo_da_domanda(testo: str) -> str:
    """Il titolo automatico: le prime 50 lettere della domanda, a capo e spazi doppi tolti."""
    titolo = " ".join(testo.split())
    if len(titolo) > LUNGHEZZA_TITOLO:
        titolo = titolo[:LUNGHEZZA_TITOLO] + "…"
    return titolo


# ---------------- La forma delle richieste e delle risposte (diventa lo schema OpenAPI) ----------------


class RispostaErrore(BaseModel):
    errore: str = Field(description="messaggio di errore in italiano")


class RichiestaChat(BaseModel):
    titolo: str | None = Field(default=None, description="facoltativo: senza, lo dà la prima domanda")


class RichiestaMessaggio(BaseModel):
    messaggio: str = Field(description="la domanda dell'utente")

    @field_validator("messaggio")
    @classmethod
    def _non_vuoto(cls, valore: str) -> str:
        if not valore.strip():
            raise ValueError("il messaggio non può essere vuoto")
        return valore


class StrumentoUsato(BaseModel):
    nome: str
    argomenti: dict
    risultato: str


class Messaggio(BaseModel):
    ruolo: Literal["utente", "assistente"]
    testo: str
    strumenti_usati: list[StrumentoUsato] = Field(description="solo per le risposte dell'assistente")
    data: datetime


class ChatCreata(BaseModel):
    id: int
    titolo: str = Field(description=f"«{TITOLO_PREDEFINITO}» finché non ce n'è uno")
    creata: datetime


class VoceChat(ChatCreata):
    ultimo_messaggio: datetime | None = Field(description="data del messaggio più recente, null se la chat è vuota")


class ChatCompleta(ChatCreata):
    messaggi: list[Messaggio] = Field(description="in ordine cronologico")


class Scambio(BaseModel):
    domanda: Messaggio
    risposta: Messaggio


def _errori(*codici: int) -> dict:
    return {codice: {"model": RispostaErrore} for codice in codici}


def _messaggio(m: MessaggioSalvato) -> Messaggio:
    return Messaggio(ruolo=m.ruolo, testo=m.testo, strumenti_usati=m.strumenti_usati, data=m.data)


# ---------------- Traduzione del 422 in italiano ----------------


def _operazione(request: Request) -> str:
    """Il nome dell'operazione nei log, dal metodo e dal percorso della richiesta."""
    if request.url.path.rstrip("/").endswith("/messaggi"):
        return "messaggio"
    if request.method == "POST":
        return "crea"
    if request.method == "DELETE":
        return "elimina"
    return "leggi" if request.path_params or request.url.path.rstrip("/") != "/chat" else "elenca"


def _motivo_422(errori: list[dict]) -> str:
    if any(e.get("loc", ("",))[0] == "path" for e in errori):
        return ID_NON_VALIDO
    e = errori[0]
    campo = e["loc"][-1] if len(e.get("loc", ())) > 1 else None
    if e["type"] == "json_invalid":
        motivo = "il JSON non è valido"
    elif e["type"] == "missing" and campo:
        motivo = f"manca il campo «{campo}»"
    elif e["type"] == "string_type" and campo:
        motivo = f"il campo «{campo}» deve essere un testo"
    elif e["type"] == "value_error":
        motivo = str(e["ctx"]["error"]) if "ctx" in e else e["msg"]
    elif e["type"] == "model_attributes_type":
        motivo = "il corpo deve essere un oggetto JSON"
    else:
        motivo = e["msg"]
    return f"Corpo non valido: {motivo}."


# ---------------- L'app ----------------


def crea_app(archivio: ArchivioChat, agente) -> FastAPI:
    """L'applicazione FastAPI del back-end; agente = oggetto con invia(...) come AgenteRemoto."""
    app = FastAPI(
        title="Back-end del laboratorio",
        description=(
            "API per il front-end: crea, elenca, legge ed elimina le chat e invia i messaggi. "
            "Le chat sono salvate in PostgreSQL; le domande vanno all'agente, che il front-end non "
            "conosce. Se l'agente non risponde la domanda non viene salvata e la chat resta com'era."
        ),
        version="1.0.0",
        default_response_class=RispostaJSON,
    )

    # Risposta di errore uniforme, con una riga WARNING nei log.
    def errore(operazione: str, codice: int, messaggio: str) -> JSONResponse:
        log.warning("errore operazione=%s codice=%d messaggio=%s", operazione, codice, messaggio)
        return RispostaJSON(status_code=codice, content={"errore": messaggio})

    @app.exception_handler(RequestValidationError)
    def corpo_non_valido(request: Request, e: RequestValidationError):
        return errore(_operazione(request), 422, _motivo_422(list(e.errors())))

    # Database giù in qualunque operazione → 503, senza traceback.
    @app.exception_handler(ErroreDatabase)
    def database_giu(request: Request, e: ErroreDatabase):
        log.warning("database non disponibile: %s", e)
        return errore(_operazione(request), 503, DATABASE_GIU)

    def nome(titolo: str | None) -> str:
        return titolo if titolo is not None else TITOLO_PREDEFINITO

    @app.post("/chat", status_code=201, response_model=ChatCreata, responses=_errori(422, 503),
              summary="Crea una chat", description="Restituisce l'identificativo della nuova chat.")
    def crea(richiesta: RichiestaChat | None = None):
        log.info("richiesta operazione=crea chat=-")
        titolo = (richiesta.titolo or "").strip() if richiesta else ""
        chat = archivio.crea(titolo or None)
        return ChatCreata(id=chat.id, titolo=nome(chat.titolo), creata=chat.creata)

    @app.get("/chat", response_model=list[VoceChat], responses=_errori(503),
             summary="Elenca le chat", description="Titolo e data dell'ultimo messaggio; prima le più recenti.")
    def elenca():
        log.info("richiesta operazione=elenca chat=-")
        return [VoceChat(id=v.id, titolo=nome(v.titolo), creata=v.creata, ultimo_messaggio=v.ultimo_messaggio)
                for v in archivio.elenca()]

    @app.get("/chat/{chat_id}", response_model=ChatCompleta, responses=_errori(404, 422, 503),
             summary="Legge una chat", description="I messaggi in ordine cronologico.")
    def leggi(chat_id: IdChat):
        log.info("richiesta operazione=leggi chat=%d", chat_id)
        trovata = archivio.leggi(chat_id)
        if trovata is None:
            return errore("leggi", 404, CHAT_NON_TROVATA)
        chat, messaggi = trovata
        return ChatCompleta(id=chat.id, titolo=nome(chat.titolo), creata=chat.creata,
                            messaggi=[_messaggio(m) for m in messaggi])

    @app.delete("/chat/{chat_id}", status_code=204, response_class=Response,
                responses=_errori(404, 422, 503),
                summary="Elimina una chat", description="Rimuove la chat e i suoi messaggi.")
    def elimina(chat_id: IdChat):
        log.info("richiesta operazione=elimina chat=%d", chat_id)
        if not archivio.elimina(chat_id):
            return errore("elimina", 404, CHAT_NON_TROVATA)
        return Response(status_code=204)

    @app.post(
        "/chat/{chat_id}/messaggi",
        response_model=Scambio,
        responses=_errori(404, 422, 502, 503, 504),
        summary="Invia un messaggio",
        description=(
            "Salva la domanda, chiama l'agente, salva e restituisce la risposta. Se l'agente non è "
            "raggiungibile (503), non risponde in tempo (504) o risponde con un errore (502), non viene "
            "salvato niente: la chat resta com'era e la domanda va rimandata."
        ),
    )
    def messaggio(chat_id: IdChat, richiesta: RichiestaMessaggio):
        log.info("richiesta operazione=messaggio chat=%d", chat_id)
        try:
            # La chat resta bloccata per tutto il turno; uscendo dal "with" con un'eccezione
            # (agente che non risponde) la transazione viene annullata: nulla resta salvato.
            with archivio.turno(chat_id) as turno:
                if turno is None:
                    return errore("messaggio", 404, CHAT_NON_TROVATA)
                esito = agente.invia(richiesta.messaggio, turno.cronologia, turno.riassunto)
                log.info("agente chat=%d strumenti=%s", chat_id, [s.get("nome") for s in esito.strumenti_usati])
                titolo = None if turno.chat.titolo is not None else titolo_da_domanda(richiesta.messaggio)
                domanda, risposta = turno.salva(richiesta.messaggio, esito.risposta, esito.strumenti_usati,
                                                esito.cronologia, esito.riassunto, titolo)
        except ErroreAgente as e:
            return errore("messaggio", e.codice, str(e))
        return Scambio(domanda=_messaggio(domanda), risposta=_messaggio(risposta))

    return app
