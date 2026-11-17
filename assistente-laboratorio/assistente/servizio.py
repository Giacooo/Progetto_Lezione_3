"""Servizio HTTP dell'agente (lezione 6, step 6): API FastAPI con documentazione OpenAPI."""

# COSA FA QUESTO FILE
# Mette l'agente "in rete": invece di leggere dalla tastiera, riceve richieste HTTP e risponde
# in JSON. Si avvia con:   python -m assistente.servizio
# Gli endpoint (le "porte d'ingresso" dell'API):
#   POST /messaggio       messaggio + cronologia + riassunto → risposta + strumenti usati +
#                         cronologia e riassunto aggiornati
#   GET  /stato           agente, server MCP e modello raggiungibili? (200 sì, 503 no)
#   GET  /prompts         elenco dei prompt del server MCP (step 5)
#   POST /prompts/{nome}  richiama un prompt: i messaggi ottenuti passano dal grafo come una domanda
#   /docs e /openapi.json documentazione OpenAPI, generata da FastAPI a partire dalle classi qui sotto
# L'agente è SENZA STATO: la conversazione la tiene chi chiama e la rimanda a ogni richiesta.
# Gli endpoint sono funzioni normali (def, non async def): FastAPI le esegue in un thread a
# parte, quindi il grafo resta sincrono come nel resto del programma.

import logging
import sys
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field, field_validator, model_validator

from assistente.agente import Agente, EsitoTurno, costruisci_agente
from assistente.configurazione import (
    carica_configurazione,
    carica_indirizzo_servizio,
    configura_log,
    leggi_ambiente,
)
from assistente.errori import ErroreCollegamentoMCP, ErroreComandoPrompt, ErroreConfigurazione, ErroreTurno
from assistente.formato import Messaggio, StrumentoUsato, controlla_cronologia, da_json, in_json

# Nome scritto per esteso, non __name__: avviato con "python -m assistente.servizio" il modulo
# si chiama "__main__" e le sue righe INFO non passerebbero (solo "assistente.*" è a INFO).
log = logging.getLogger("assistente.servizio")


# Le risposte JSON dichiarano charset=utf-8: senza, Invoke-RestMethod di PowerShell 5.1 legge
# il testo come ISO-8859-1 e mostra «Ã¨» al posto di «è».
class RispostaJSON(JSONResponse):
    media_type = "application/json; charset=utf-8"

# Dal tipo di errore del turno (vedi agente.py) al codice HTTP della risposta:
#   503 = un servizio necessario non risponde; 504 = attesa scaduta; 502 = LM Studio ha
#   risposto male; 500 = l'agente non è riuscito a concludere il turno.
CODICI = {
    "connessione": 503,
    "attesa": 504,
    "server": 502,
    "risposta_vuota": 502,
    "limite_passi": 500,
    "inatteso": 500,
}


# ---------------- La forma delle richieste e delle risposte (diventa lo schema OpenAPI) ----------------


class RispostaErrore(BaseModel):
    errore: str = Field(description="messaggio di errore in italiano")


# La cronologia ricevuta deve essere coerente: ogni risultato di strumento risponde a una
# richiesta precedente. Altrimenti 422, senza chiamare il modello.
class _ConCronologia(BaseModel):
    cronologia: list[Messaggio] = Field(default_factory=list, description="i messaggi dei turni precedenti")
    riassunto: str = Field(default="", description="il riassunto dei messaggi più vecchi già tolti")

    @model_validator(mode="after")
    def _cronologia_coerente(self):
        controlla_cronologia(self.cronologia)
        return self


class RichiestaMessaggio(_ConCronologia):
    messaggio: str = Field(description="la domanda dell'utente")

    @field_validator("messaggio")
    @classmethod
    def _non_vuoto(cls, valore: str) -> str:
        if not valore.strip():
            raise ValueError("il messaggio non può essere vuoto")
        return valore


class RichiestaPrompt(_ConCronologia):
    argomenti: dict[str, str] = Field(default_factory=dict, description="argomenti del prompt, es. {'argomento': 'MCP'}")


class RispostaTurno(BaseModel):
    risposta: str = Field(description="la risposta dell'agente")
    strumenti_usati: list[StrumentoUsato] = Field(description="gli strumenti eseguiti in questo turno")
    cronologia: list[Messaggio] = Field(description="la cronologia aggiornata, da rimandare al turno dopo")
    riassunto: str = Field(description="il riassunto aggiornato, da rimandare al turno dopo")


class RispostaStato(BaseModel):
    agente: str = Field(description="ok se il servizio risponde")
    server_mcp: str = Field(description="ok, oppure il motivo per cui il server MCP non risponde")
    modello: str = Field(description="ok, oppure il problema con LM Studio o con il modello")


class ArgomentoPrompt(BaseModel):
    nome: str
    descrizione: str | None = None
    obbligatorio: bool


class DescrizionePrompt(BaseModel):
    nome: str
    descrizione: str | None = None
    argomenti: list[ArgomentoPrompt]


# I codici di errore che un endpoint può restituire, con la forma del corpo: finiscono nella
# documentazione OpenAPI, così chi usa l'API li vede in /docs.
def _errori(*codici: int) -> dict:
    return {codice: {"model": RispostaErrore} for codice in codici}


# ---------------- L'app ----------------


def crea_app(agente: Agente) -> FastAPI:
    """L'applicazione FastAPI che espone l'agente ricevuto."""
    app = FastAPI(
        title="Agente del laboratorio",
        description=(
            "Agente LangGraph con strumenti MCP, esposto come servizio HTTP senza stato: "
            "chi chiama manda cronologia e riassunto e li riceve aggiornati."
        ),
        version="1.0.0",
        default_response_class=RispostaJSON,
    )

    # Risposta di errore uniforme, con una riga WARNING nei log.
    def errore(endpoint: str, codice: int, messaggio: str) -> JSONResponse:
        log.warning("errore endpoint=%s codice=%d messaggio=%s", endpoint, codice, messaggio)
        return RispostaJSON(status_code=codice, content={"errore": messaggio})

    # Un turno (domanda o prompt) con i log di inizio e fine e la traduzione degli errori.
    def esegui(endpoint: str, richiesta: _ConCronologia, fai_turno) -> RispostaTurno | JSONResponse:
        log.info(
            "richiesta endpoint=%s messaggi_cronologia=%d riassunto=%s",
            endpoint, len(richiesta.cronologia), "sì" if richiesta.riassunto else "no",
        )
        try:
            esito: EsitoTurno = fai_turno(da_json(richiesta.cronologia), richiesta.riassunto)
        except ErroreComandoPrompt as e:
            return errore(endpoint, 400, str(e))
        except ErroreCollegamentoMCP as e:
            return errore(endpoint, 503, f"Server MCP non disponibile: {e}")
        except ErroreTurno as e:
            return errore(endpoint, CODICI.get(getattr(e, "tipo", ""), 500), str(e))
        log.info(
            "risposta endpoint=%s strumenti=%s messaggi_cronologia=%d",
            endpoint, [s.nome for s in esito.strumenti_usati], len(esito.cronologia),
        )
        return RispostaTurno(
            risposta=esito.risposta,
            strumenti_usati=esito.strumenti_usati,
            cronologia=in_json(esito.cronologia),
            riassunto=esito.riassunto,
        )

    @app.post(
        "/messaggio",
        response_model=RispostaTurno,
        responses=_errori(500, 502, 503, 504),
        summary="Invia un messaggio all'agente",
        description="Esegue un turno del grafo (router, agente, strumenti, revisore) con la cronologia ricevuta.",
    )
    def messaggio(richiesta: RichiestaMessaggio):
        return esegui(
            "/messaggio",
            richiesta,
            lambda cronologia, riassunto: agente.turno(cronologia, [HumanMessage(richiesta.messaggio)], riassunto),
        )

    @app.get(
        "/stato",
        response_model=RispostaStato,
        responses={503: {"model": RispostaStato, "description": "qualcosa non è raggiungibile"}},
        summary="Stato dell'agente, del server MCP e del modello",
    )
    def stato(response: Response):
        voci = agente.stato()
        if any(valore != "ok" for valore in voci.values()):
            response.status_code = 503
        return RispostaStato(**voci)

    @app.get(
        "/prompts",
        response_model=list[DescrizionePrompt],
        responses=_errori(503),
        summary="Elenco dei prompt del server MCP",
    )
    def prompts():
        try:
            elenco = agente.elenca_prompt()
        except ErroreCollegamentoMCP as e:
            return errore("/prompts", 503, f"Server MCP non disponibile: {e}")
        return [
            DescrizionePrompt(
                nome=p.name,
                descrizione=p.description,
                argomenti=[
                    ArgomentoPrompt(nome=a.name, descrizione=a.description, obbligatorio=bool(a.required))
                    for a in (p.arguments or [])
                ],
            )
            for p in elenco
        ]

    @app.post(
        "/prompts/{nome}",
        response_model=RispostaTurno,
        responses=_errori(400, 500, 502, 503, 504),
        summary="Richiama un prompt del server MCP",
        description=(
            "Controlla gli argomenti rispetto all'elenco dei prompt (400 se non validi, senza chiamare il "
            "modello), poi fa passare i messaggi ottenuti dal grafo come una domanda."
        ),
    )
    def richiama_prompt(nome: str, richiesta: RichiestaPrompt):
        return esegui(
            f"/prompts/{nome}",
            richiesta,
            lambda cronologia, riassunto: agente.richiama_prompt(nome, richiesta.argomenti, cronologia, riassunto),
        )

    return app


# ---------------- Avvio ----------------


# Restituisce 0 a servizio fermato, 2 se la configurazione non è valida, 3 se il server MCP
# non è disponibile (gli stessi codici della CLI fino allo step 5).
def main() -> int:
    ambiente = leggi_ambiente(Path.cwd())
    try:
        config = carica_configurazione(ambiente)
        indirizzo = carica_indirizzo_servizio(ambiente)
    except ErroreConfigurazione as e:
        print(f"Configurazione non valida: {e}", file=sys.stderr)
        return 2
    configura_log(config.log_level)
    try:
        agente = costruisci_agente(config, Path.cwd())
    except ErroreCollegamentoMCP as e:
        print(f"Server MCP non disponibile: {e}", file=sys.stderr)
        return 3
    uvicorn.run(crea_app(agente), host=indirizzo.host, port=indirizzo.porta)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
