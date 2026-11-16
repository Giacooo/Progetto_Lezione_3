"""Il modulo dell'agente, separato dall'interfaccia: un turno senza stato attraverso il grafo."""

# COSA FA QUESTO FILE (lezione 6, step 6)
# Contiene l'agente "puro", senza tastiera, schermo o HTTP: lo usano sia il servizio HTTP
# (servizio.py) sia, per i test e le prove reali, la Conversazione in memoria.
# L'agente è SENZA STATO: non ricorda nulla tra un turno e l'altro. A ogni turno riceve da chi
# chiama la cronologia e il riassunto, fa girare il grafo e restituisce:
#   - la risposta,
#   - gli strumenti usati in questo turno (nome, argomenti, risultato),
#   - la cronologia e il riassunto aggiornati, che chi chiama dovrà rimandare al turno dopo.
# Gli errori del turno portano un "tipo" (connessione, attesa, ...): il servizio ne ricava il
# codice HTTP, la CLI ne mostra solo il messaggio.

import logging
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import httpx
import openai
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from mcp.types import Prompt

from assistente.collegamento_mcp import (
    carica_preferenze,
    carica_strumenti_mcp,
    connessione_stdio,
    elenca_prompt_mcp,
    richiama_prompt_mcp,
)
from assistente.configurazione import Configurazione
from assistente.errori import ErroreCollegamentoMCP, ErroreTurno
from assistente.formato import StrumentoUsato
from assistente.grafo import costruisci_grafo
from assistente.modello import crea_modello, traduci_errore
from assistente.revisore import crea_revisore
from assistente.router import crea_router
from assistente.strumenti import crea_strumenti

log = logging.getLogger(__name__)


# Un errore del turno con il suo tipo. È un ErroreTurno, quindi chi già gestisce quelli
# (la CLI, la Conversazione) continua a funzionare uguale.
class ErroreTurnoAgente(ErroreTurno):
    """Il turno non si è concluso; `tipo` dice perché (connessione, attesa, server, ...)."""

    def __init__(self, messaggio: str, tipo: str):
        super().__init__(messaggio)
        self.tipo = tipo


# Il risultato di un turno riuscito.
@dataclass(frozen=True)
class EsitoTurno:
    risposta: str
    strumenti_usati: list[StrumentoUsato]
    cronologia: list[BaseMessage]
    riassunto: str


# Il tipo di un errore del modello: l'attesa scaduta va controllata PRIMA della connessione
# fallita, perché APITimeoutError è un caso particolare di APIConnectionError.
def _tipo_errore(exc: Exception) -> str:
    if isinstance(exc, openai.APITimeoutError):
        return "attesa"
    if isinstance(exc, openai.APIConnectionError):
        return "connessione"
    if isinstance(exc, openai.APIStatusError):
        return "server"
    return "inatteso"


# Gli strumenti usati nel turno: ogni richiesta di strumento dei messaggi del turno, abbinata
# al suo risultato (stesso id). Una richiesta senza risultato non è stata eseguita: non conta.
def _strumenti_usati(messaggi_del_turno: Sequence[BaseMessage]) -> list[StrumentoUsato]:
    risultati = {m.tool_call_id: m.text for m in messaggi_del_turno if isinstance(m, ToolMessage)}
    usati = []
    for m in messaggi_del_turno:
        if isinstance(m, AIMessage):
            for richiesta in m.tool_calls:
                if richiesta["id"] in risultati:
                    usati.append(
                        StrumentoUsato(nome=richiesta["name"], argomenti=richiesta["args"], risultato=risultati[richiesta["id"]])
                    )
    return usati


def esegui_turno(grafo, cronologia: Sequence[BaseMessage], nuovi: Sequence[BaseMessage], riassunto: str) -> EsitoTurno:
    """Un turno senza stato: restituisce l'esito, oppure lancia ErroreTurnoAgente."""
    # Ogni messaggio nuovo riceve un identificativo: dopo il grafo serve a ritrovare dove
    # comincia questo turno (il riassunto può aver tolto messaggi vecchi, quindi le posizioni
    # non bastano). Si lavora su copie: i messaggi ricevuti non vengono modificati.
    nuovi = [m if m.id else m.model_copy(update={"id": str(uuid.uuid4())}) for m in nuovi]

    # --- Passo 1: far girare il grafo, con passi e revisioni da zero ---
    try:
        risultato = grafo.invoke(
            {"messages": [*cronologia, *nuovi], "passi": 0, "revisioni": 0, "riassunto": riassunto}
        )
    except Exception as exc:
        errore = traduci_errore(exc)
        tipo = _tipo_errore(exc)
        if errore is None:
            # Errore non previsto: traceback completo nel log.
            log.exception("Turno fallito per un errore inatteso")
            messaggio = f"Errore inatteso: {exc} (dettagli nel log)"
        else:
            messaggio = str(errore)
            log.error("Turno fallito: %s", messaggio)
        raise ErroreTurnoAgente(messaggio, tipo) from exc

    # --- Passo 2: controllare il risultato ---
    messaggi = risultato["messages"]
    finale = messaggi[-1]
    if finale.tool_calls:
        # Fermato al limite con una richiesta di strumento ancora aperta (avviso già nel log).
        raise ErroreTurnoAgente("Limite di passaggi raggiunto: riprova con una domanda diversa.", "limite_passi")
    testo = finale.text.strip()
    if not testo:
        messaggio = "Il modello ha restituito una risposta vuota."
        log.warning("Turno fallito: %s", messaggio)
        raise ErroreTurnoAgente(messaggio, "risposta_vuota")

    # --- Passo 3: l'esito, con i soli strumenti di questo turno ---
    inizio = next(i for i, m in enumerate(messaggi) if m.id == nuovi[0].id)
    return EsitoTurno(
        risposta=testo,
        strumenti_usati=_strumenti_usati(messaggi[inizio:]),
        cronologia=list(messaggi),
        riassunto=risultato["riassunto"],
    )


# ---------------- Stato: LM Studio e il modello ----------------

# Controlla che LM Studio risponda e che il modello della configurazione sia caricato
# (GET /v1/models, attesa massima 5 secondi). "leggi" è httpx.get; i test ne passano uno finto.
def controlla_modello(config: Configurazione, leggi: Callable = httpx.get) -> str:
    indirizzo = config.lm_base_url.rstrip("/") + "/models"
    try:
        risposta = leggi(indirizzo, timeout=5)
    except httpx.HTTPError:
        return "LM Studio non raggiungibile: controllare URL e porta"
    if risposta.status_code != 200:
        return f"risposta non valida da LM Studio: {risposta.status_code}"
    caricati = [modello.get("id") for modello in risposta.json().get("data", [])]
    if config.lm_model not in caricati:
        return f"modello {config.lm_model} non caricato in LM Studio"
    return "ok"


# ---------------- L'agente ----------------

# L'agente pronto all'uso: il grafo (con modello, strumenti, router, revisore e riassunto), la
# connessione al server MCP (per prompt e stato) e la configurazione. NESSUNA conversazione:
# cronologia e riassunto arrivano a ogni chiamata da chi usa l'agente.
@dataclass
class Agente:
    grafo: object
    connessione: dict
    config: Configurazione

    def turno(self, cronologia: Sequence[BaseMessage], nuovi: Sequence[BaseMessage], riassunto: str) -> EsitoTurno:
        return esegui_turno(self.grafo, cronologia, nuovi, riassunto)

    # Elenco dei prompt del server (prompts/list), letto a ogni richiesta come nello step 5.
    def elenca_prompt(self) -> list[Prompt]:
        return elenca_prompt_mcp(self.connessione)

    # Richiamo di un prompt (step 5): controllo degli argomenti e prompts/get; se il controllo
    # fallisce l'errore sale PRIMA di chiamare il modello. I messaggi ottenuti passano dal grafo
    # come una domanda.
    def richiama_prompt(
        self, nome: str, argomenti: dict[str, str], cronologia: Sequence[BaseMessage], riassunto: str
    ) -> EsitoTurno:
        messaggi = richiama_prompt_mcp(self.connessione, nome, argomenti)
        return self.turno(cronologia, messaggi, riassunto)

    # Lo stato per l'endpoint /stato: l'agente (se risponde, è ok), il server MCP (una tools/list
    # fresca) e il modello (LM Studio e id del modello). Una riga di log per ogni controllo.
    def stato(self) -> dict[str, str]:
        try:
            carica_strumenti_mcp(self.connessione)
            server_mcp = "ok"
        except ErroreCollegamentoMCP as errore:
            server_mcp = f"non raggiungibile: {errore}"
        stato = {"agente": "ok", "server_mcp": server_mcp, "modello": controlla_modello(self.config, leggi=httpx.get)}
        for voce, valore in stato.items():
            log.info("stato %s=%s", voce, valore)
        return stato


# Costruisce l'agente: è il montaggio che fino allo step 5 stava in terminale.main(), con lo
# stesso ordine. Se il server MCP non parte, ErroreCollegamentoMCP sale subito (chi chiama
# esce con il codice 3), PRIMA di leggere le preferenze e senza contattare LM Studio.
def costruisci_agente(config: Configurazione, cartella: Path) -> Agente:
    # Come avviare il server MCP (stesso interprete, stessa cartella).
    connessione = connessione_stdio(cartella)
    # Discovery degli strumenti del server MCP.
    strumenti_mcp = carica_strumenti_mcp(connessione)
    # Le preferenze (resource utente://preferenze): lette una volta sola, all'avvio dell'agente.
    # Dallo step 6 la "sessione" dello step 4 è la vita del servizio: dopo una modifica del file
    # basta riavviarlo. Se non sono disponibili: valori predefiniti e WARNING nei log.
    preferenze = carica_preferenze(connessione, config.fuso_orario)
    # L'orologio nel fuso delle preferenze, più gli strumenti MCP. La resource non è uno strumento.
    strumenti = crea_strumenti(preferenze.fuso) + strumenti_mcp
    # Il modello con gli strumenti; router, revisore e riassuntore: stesso modello, senza strumenti.
    modello = crea_modello(config).bind_tools(strumenti)
    router = crea_router(crea_modello(config))
    revisore = crea_revisore(crea_modello(config))
    riassuntore = crea_modello(config)
    grafo = costruisci_grafo(
        modello,
        strumenti,
        config.max_passi,
        router,
        config.ambito,
        revisore,
        config.max_revisioni,
        riassuntore,
        config.soglia_riassunto,
        config.messaggi_da_tenere,
        preferenze,
    )
    return Agente(grafo, connessione, config)
