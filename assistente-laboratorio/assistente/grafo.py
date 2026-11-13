"""Grafo LangGraph del turno di conversazione.

START → router ─(conversazione, o risposta non valida)→ llm ─(richiesta di strumento e passi < limite)→ strumenti → llm
               │                                            ├(risposta finale)→ revisore ─(coerente: sì, o risposta non valida)→ END
               │                                            │                            ├(coerente: no, revisioni < limite)→ llm
               │                                            │                            └(coerente: no, limite raggiunto)→ END
               │                                            └(richiesta di strumento e passi al limite)→ END
               └(fuori ambito)→ rifiuto → END
"""

# COSA FA QUESTO FILE (è il cuore della lezione 4, esteso nella lezione 6)
# Descrive il "percorso" che compie ogni domanda, come una mappa della metropolitana:
#   - le STAZIONI sono i NODI:   "router" (decide se la domanda è nell'ambito),
#                                "rifiuto" (risponde con il testo fisso per le domande fuori ambito),
#                                "llm" (l'agente: chiama il modello), "strumenti" (esegue lo strumento)
#                                e "revisore" (controlla se la risposta è coerente con la domanda)
#   - i BINARI sono gli ARCHI:   le frecce che dicono quale nodo viene dopo
#   - gli SCAMBI sono gli INSTRADAMENTI: "dopo_router", "instrada" e "dopo_revisore" decidono dove andare
#   - il FOGLIO che passa di mano in mano è lo STATO: i messaggi, il contatore dei passi,
#     la categoria decisa dal router e il contatore delle revisioni

import json
import logging
from collections.abc import Sequence
from typing import Annotated, Literal, TypedDict

import openai
from langchain_core.messages import AIMessage, AnyMessage, SystemMessage, ToolMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from assistente.errori import ErroreCollegamentoMCP, ErroreStrumento
from assistente.revisore import domanda_e_risposta, e_indicazione, indicazione, leggi_valutazione, messaggi_per_revisore
from assistente.router import leggi_classificazione, messaggi_per_router, prompt_router, testo_rifiuto

log = logging.getLogger(__name__)

# Le istruzioni date al modello all'inizio di OGNI chiamata (il "prompt di sistema").
# Gli dicono chi è, come rispondere e, soprattutto, quando usare lo strumento orologio.
# Un modello piccolo segue queste istruzioni solo in parte: per questo conta come sono scritte.
PROMPT_SISTEMA = (
    "Sei l'assistente del laboratorio. Rispondi in italiano, in modo breve e chiaro. "
    "Hai a disposizione lo strumento ora_corrente, che restituisce data e ora attuali: "
    "chiamalo ogni volta che la domanda riguarda data, ora o giorno della settimana. "
    "Se ti sono disponibili altri strumenti (calcoli, conversioni di unità, giorni e scadenze, "
    "catalogo dei corsi, note, meteo), chiamali quando la domanda li riguarda invece di rispondere a memoria."
)


# LO STATO: il foglio che passa da un nodo all'altro. Contiene quattro cose:
class StatoTurno(TypedDict):
    # add_messages aggiunge i nuovi messaggi alla lista invece di sostituirla.
    # (La conversazione cresce: domanda, richiesta di strumento, risultato, risposta...)
    messages: Annotated[list[AnyMessage], add_messages]
    # Quante volte, in questo turno, abbiamo chiamato il modello. Serve per il limite.
    passi: int
    # La decisione del router per questo turno: "conversazione" o "fuori ambito".
    # (Il motivo non sta qui: va solo nel log.)
    categoria: str
    # Quante volte, in questo turno, il revisore ha rimandato la risposta all'agente.
    # È il "limite di revisioni nello stato" del PDF: non può superare MAX_REVISIONI.
    revisioni: int


def costruisci_grafo(
    modello: Runnable,
    strumenti: Sequence[BaseTool],
    max_passi: int,
    router: Runnable,
    ambito: str,
    revisore: Runnable,
    max_revisioni: int,
):
    """Grafo del turno.

    `modello` deve già conoscere gli strumenti (per LM Studio: `bind_tools`);
    `max_passi` è il numero massimo di chiamate al modello per ogni tentativo dell'agente;
    `router` è il modello SENZA strumenti con risposta strutturata (vedi router.py);
    `ambito` è l'elenco degli argomenti dell'agente, letto da AMBITO_AGENTE;
    `revisore` è il modello SENZA strumenti con risposta strutturata (vedi revisore.py);
    `max_revisioni` è quante volte il revisore può rimandare la risposta all'agente (MAX_REVISIONI).
    """
    # Un "elenco telefonico" degli strumenti: dato il nome (es. "ora_corrente")
    # si trova subito lo strumento corrispondente.
    per_nome = {strumento.name: strumento for strumento in strumenti}

    # ---------------- NODO 0: "router" ----------------
    # Decide se la domanda rientra nell'ambito. Non risponde e non sceglie strumenti.
    # Non conta nei "passi": il limite MAX_PASSI resta quello dell'agente.
    # Gli errori di collegamento NON si catturano: se LM Studio è spento l'errore sale come
    # per l'agente. Si catturano solo la risposta troncata (limite di token) e quella bloccata
    # dal filtro del server: sono risposte illeggibili, quindi si passa all'agente.
    def nodo_router(stato: StatoTurno) -> dict:
        log.info("Inizio chiamata al router")
        try:
            uscita = router.invoke([SystemMessage(prompt_router(ambito)), *messaggi_per_router(stato["messages"])])
        except (openai.LengthFinishReasonError, openai.ContentFilterFinishReasonError) as errore:
            uscita = {"raw": None, "parsed": None, "parsing_error": errore}
        letto = leggi_classificazione(uscita)
        if letto is None:
            # Risposta non valida (JSON illeggibile, categoria sconosciuta, motivo mancante):
            # decisione dell'utente, la domanda passa comunque all'agente, con un avviso.
            dettaglio = uscita.get("parsing_error") or uscita.get("parsed")
            log.warning(
                "router risposta non valida (%s): passaggio all'agente next_node=llm (agente)",
                str(dettaglio)[:200],
            )
            return {"categoria": "conversazione"}
        categoria, motivo = letto
        prossimo = "llm (agente)" if categoria == "conversazione" else "rifiuto"
        log.info("router categoria=%s motivo=%s next_node=%s", categoria, motivo[:200], prossimo)
        return {"categoria": categoria}

    # ---------------- NODO: "rifiuto" ----------------
    # Risposta fissa per le domande fuori ambito. Non chiama nessun modello.
    def rifiuto(stato: StatoTurno) -> dict:
        log.info("rifiuto inviato, nodo agente non eseguito")
        return {"messages": [AIMessage(testo_rifiuto(ambito))]}

    # ---------------- LO SCAMBIO DOPO IL ROUTER ----------------
    def dopo_router(stato: StatoTurno) -> Literal["llm", "rifiuto"]:
        return "rifiuto" if stato["categoria"] == "fuori ambito" else "llm"

    # ---------------- NODO 1: "llm" ----------------
    # Chiama il modello e restituisce la sua risposta (che può essere testo oppure
    # una richiesta di strumento).
    def llm(stato: StatoTurno) -> dict:
        # Questo è il passo numero (passi già fatti + 1).
        passo = stato["passi"] + 1
        log.info("Inizio chiamata al modello (passo %d/%d)", passo, max_passi)
        # Invia al modello: prima le istruzioni di sistema, poi tutta la conversazione.
        risposta = modello.invoke([SystemMessage(PROMPT_SISTEMA), *stato["messages"]])
        # Per il log: il modello ha chiesto strumenti o ha dato la risposta finale?
        esito = f"richieste di strumenti: {len(risposta.tool_calls)}" if risposta.tool_calls else "risposta finale"
        log.info("Fine chiamata al modello (passo %d/%d): %s", passo, max_passi, esito)
        # Restituisce le novità da aggiungere allo stato: la risposta e il nuovo contatore.
        return {"messages": [risposta], "passi": passo}

    # ---------------- NODO 2: "strumenti" ----------------
    # Esegue DAVVERO gli strumenti che il modello ha chiesto. Il modello non esegue nulla:
    # scrive solo la richiesta; qui il programma fa il lavoro vero.
    def esegui_strumenti(stato: StatoTurno) -> dict:
        risultati = []
        # L'ultimo messaggio è la risposta del modello: contiene le richieste (tool_calls).
        for richiesta in stato["messages"][-1].tool_calls:
            # Ogni richiesta ha un nome (quale strumento) e degli argomenti.
            nome, argomenti = richiesta["name"], richiesta["args"]
            id_chiamata = richiesta["id"]
            strumento = per_nome.get(nome)
            # La "variante" dice da dove viene lo strumento: locale (come ora_corrente),
            # MCP (scoperto dal server) oppure sconosciuto (il modello l'ha inventato).
            if strumento is None:
                variante = "unknown"
            else:
                variante = (strumento.metadata or {}).get("variante", "local")
            log.info(
                "variant=%s tool=%s call_id=%s arguments=%s",
                variante, nome, id_chiamata, json.dumps(argomenti, ensure_ascii=False),
            )
            if strumento is None:
                # Il modello ha chiesto uno strumento che non esiste: non andiamo in crash,
                # rispondiamo "sconosciuto" e lasciamo un avviso nel log.
                risultato = f"Strumento sconosciuto: {nome}"
                esecuzione = "unknown_tool"
                log.warning(risultato)
            else:
                # Esegue lo strumento e ne trasforma il risultato in testo. Gli errori previsti
                # (input rifiutato, server MCP non raggiungibile) non interrompono il turno:
                # diventano un messaggio di strumento, così il modello può reagire.
                try:
                    risultato = str(strumento.invoke(argomenti))
                    esecuzione = "ok"
                except ErroreStrumento as errore:
                    risultato = f"Errore dello strumento: {errore}"
                    esecuzione = "tool_error"
                except ErroreCollegamentoMCP as errore:
                    risultato = f"Errore di collegamento con il server MCP: {errore}"
                    esecuzione = "connection_error"
            log.info(
                "variant=%s tool=%s call_id=%s execution=%s result=%s",
                variante, nome, id_chiamata, esecuzione, risultato[:200],
            )
            # Impacchetta il risultato come "messaggio di strumento". Il tool_call_id lo collega
            # alla richiesta, così il modello sa a quale domanda sta rispondendo il risultato.
            risultati.append(ToolMessage(content=risultato, tool_call_id=id_chiamata, name=nome))
            log.info("tool_message.call_id=%s next_node=llm", id_chiamata)
        return {"messages": risultati}

    # ---------------- NODO 3: "revisore" (lezione 6, step 2) ----------------
    # Legge la domanda del turno e la risposta finale dell'agente e dice se la risposta è
    # coerente. Se non lo è, aggiunge alla conversazione l'indicazione con il motivo e
    # l'agente riprova, finché non è coerente o si raggiunge MAX_REVISIONI.
    # Non conta nei "passi". Come per il router, gli errori di collegamento NON si catturano;
    # la risposta troncata o filtrata è una risposta illeggibile, quindi si approva.
    def nodo_revisore(stato: StatoTurno) -> dict:
        log.info("Inizio chiamata al revisore")
        try:
            uscita = revisore.invoke(messaggi_per_revisore(*domanda_e_risposta(stato["messages"])))
        except (openai.LengthFinishReasonError, openai.ContentFilterFinishReasonError) as errore:
            uscita = {"raw": None, "parsed": None, "parsing_error": errore}
        letto = leggi_valutazione(uscita)
        if letto is None:
            # Risposta non valida: decisione dell'utente, la risposta dell'agente è approvata.
            dettaglio = uscita.get("parsing_error") or uscita.get("parsed")
            log.warning("revisore risposta non valida (%s): risposta approvata next_node=END", str(dettaglio)[:200])
            return {}
        coerente, motivo = letto
        if coerente == "sì":
            log.info("revisore coerente=sì motivo=%s next_node=END", motivo[:200])
            return {}
        revisioni = stato["revisioni"]
        if revisioni >= max_revisioni:
            # Limite raggiunto: si restituisce l'ultima risposta e lo si segnala nel log (PDF).
            log.info(
                "revisore coerente=no motivo=%s next_node=END revisione=%d/%d", motivo[:200], revisioni, max_revisioni
            )
            log.warning("limite di revisioni raggiunto (%d): restituita l'ultima risposta", max_revisioni)
            return {}
        # Non coerente: l'indicazione entra nella conversazione e l'agente riparte con i passi a 0.
        log.info(
            "revisore coerente=no motivo=%s next_node=llm (agente) revisione=%d/%d",
            motivo[:200], revisioni + 1, max_revisioni,
        )
        return {"messages": [indicazione(motivo)], "revisioni": revisioni + 1, "passi": 0}

    # ---------------- LO SCAMBIO DOPO IL REVISORE ----------------
    # Se il revisore ha appena aggiunto un'indicazione si torna all'agente, altrimenti è finita.
    def dopo_revisore(stato: StatoTurno) -> Literal["llm", "__end__"]:
        return "llm" if e_indicazione(stato["messages"][-1]) else END

    # ---------------- LO SCAMBIO: "instrada" ----------------
    # Dopo il nodo "llm" decide dove andare: "strumenti", "revisore" oppure END (fine).
    def instrada(stato: StatoTurno) -> Literal["strumenti", "revisore", "__end__"]:
        # Il modello non ha chiesto strumenti: ha dato la risposta, che passa al revisore.
        if not stato["messages"][-1].tool_calls:
            return "revisore"
        # Ha chiesto uno strumento, ma abbiamo già usato tutti i passi consentiti: ci fermiamo.
        # Questo è il freno di sicurezza: impedisce che il ciclo giri all'infinito.
        if stato["passi"] >= max_passi:
            log.warning("Limite di passaggi raggiunto (%d): richiesta di strumento non eseguita", max_passi)
            return END
        # Altrimenti si va ad eseguire lo strumento.
        return "strumenti"

    # ---------------- COSTRUZIONE DELLA MAPPA ----------------
    # Crea un grafo vuoto che lavora sul tipo di stato definito sopra.
    grafo = StateGraph(StatoTurno)
    # Aggiunge le stazioni, ognuna con il suo nome e la funzione da eseguire.
    grafo.add_node("router", nodo_router)
    grafo.add_node("rifiuto", rifiuto)
    grafo.add_node("llm", llm)
    grafo.add_node("strumenti", esegui_strumenti)
    grafo.add_node("revisore", nodo_revisore)
    # Si parte sempre dal router.
    grafo.add_edge(START, "router")
    # Dopo il router: "conversazione" -> agente ("llm"); "fuori ambito" -> "rifiuto".
    grafo.add_conditional_edges("router", dopo_router)
    # Dopo il rifiuto il turno è finito.
    grafo.add_edge("rifiuto", END)
    # Dopo "llm" non c'è una freccia sola: decide la funzione "instrada".
    grafo.add_conditional_edges("llm", instrada)
    # Dopo "strumenti" si torna SEMPRE a "llm", perché il modello deve leggere il risultato.
    grafo.add_edge("strumenti", "llm")
    # Dopo il revisore: indicazione -> di nuovo "llm"; altrimenti fine.
    grafo.add_conditional_edges("revisore", dopo_revisore)
    # LangGraph si ferma con un errore oltre 25 nodi eseguiti in un turno (limite di ricorsione).
    # Con il revisore un turno può superarli: il caso peggiore è 1 router più, per ognuno dei
    # (max_revisioni + 1) tentativi, max_passi chiamate all'agente, max_passi - 1 strumenti e
    # 1 revisore. Il limite si calcola da qui, con un piccolo margine.
    limite_ricorsione = 1 + (max_revisioni + 1) * (2 * max_passi + 1) + 5
    # "Compila" la mappa: la rende un oggetto pronto da usare con .invoke(...).
    return grafo.compile().with_config(recursion_limit=limite_ricorsione)
