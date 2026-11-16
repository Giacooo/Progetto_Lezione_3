"""Client HTTP dell'agente: la CLI parla con il servizio dell'agente solo attraverso l'API."""

# COSA FA QUESTO FILE (lezione 6, step 6)
# Dallo step 6 la CLI non costruisce più grafo, modello e collegamento MCP: è un "client"
# dell'API dell'agente (servizio.py). Questo file fa le chiamate HTTP con httpx e, siccome
# l'agente non ha stato, tiene LUI la memoria della chat:
#   - cronologia: i messaggi in JSON così come li restituisce l'API;
#   - riassunto:  il riassunto dei messaggi più vecchi.
# A ogni turno li manda all'agente e li sostituisce con quelli aggiornati, SOLO se la chiamata
# riesce (la stessa "regola d'oro" della Conversazione). Ogni problema diventa un ErroreTurno
# con un messaggio chiaro: la CLI lo stampa e la chat continua.

import httpx
from mcp.types import Prompt, PromptArgument

from assistente.errori import ErroreComandoPrompt, ErroreTurno

# Secondi massimi di attesa di una risposta: un turno può chiamare il modello più volte
# (router, agente, strumenti, revisore), ognuna con un'attesa fino a 120 secondi.
ATTESA_MASSIMA = 600


class ClienteAgente:
    def __init__(self, url: str, client: httpx.Client | None = None):
        # Il "telefono" verso l'agente; i test ne passano uno con un servizio finto.
        self.client = client or httpx.Client(base_url=url.rstrip("/"), timeout=ATTESA_MASSIMA)
        self.cronologia: list[dict] = []
        self.riassunto: str = ""

    # Una chiamata all'API: restituisce il corpo JSON di una risposta 200, altrimenti ErroreTurno.
    # Un 400 sui prompt è un comando non valido: diventa ErroreComandoPrompt, come nello step 5.
    def _chiama(self, metodo: str, percorso: str, corpo: dict | None = None):
        try:
            risposta = self.client.request(metodo, percorso, json=corpo)
        except httpx.TimeoutException:
            raise ErroreTurno(f"Attesa scaduta: l'agente non ha risposto entro {ATTESA_MASSIMA} secondi.") from None
        except httpx.HTTPError:
            raise ErroreTurno("Agente non raggiungibile: controllare che il servizio sia avviato e AGENTE_URL.") from None
        if risposta.status_code == 200:
            return risposta.json()
        try:
            messaggio = risposta.json().get("errore")
        except (ValueError, AttributeError):
            messaggio = None
        if not isinstance(messaggio, str):
            raise ErroreTurno(f"Errore dall'agente: {risposta.status_code}")
        if risposta.status_code == 400 and percorso.startswith("/prompts/"):
            raise ErroreComandoPrompt(messaggio)
        raise ErroreTurno(messaggio)

    # Un turno: manda la memoria, riceve la risposta e la memoria aggiornata.
    def _turno(self, percorso: str, corpo: dict) -> str:
        esito = self._chiama("POST", percorso, {**corpo, "cronologia": self.cronologia, "riassunto": self.riassunto})
        self.cronologia = esito["cronologia"]
        self.riassunto = esito["riassunto"]
        return esito["risposta"]

    def chiedi(self, domanda: str) -> str:
        """Una domanda scritta dall'utente (POST /messaggio)."""
        return self._turno("/messaggio", {"messaggio": domanda})

    def elenca_prompt(self) -> list[Prompt]:
        """L'elenco dei prompt (GET /prompts), negli oggetti che usa testo_elenco_prompt."""
        return [
            Prompt(
                name=p["nome"],
                description=p.get("descrizione"),
                arguments=[
                    PromptArgument(name=a["nome"], description=a.get("descrizione"), required=a["obbligatorio"])
                    for a in p.get("argomenti", [])
                ],
            )
            for p in self._chiama("GET", "/prompts")
        ]

    def richiama_prompt(self, nome: str, argomenti: dict[str, str]) -> str:
        """Un prompt del server MCP (POST /prompts/{nome}): passa dal grafo come una domanda."""
        return self._turno(f"/prompts/{nome}", {"argomenti": argomenti})
