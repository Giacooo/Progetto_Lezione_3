"""Router: decide se la domanda rientra nell'ambito dell'agente (lezione 6, step 1)."""

# COSA FA QUESTO FILE
# Il router è il "portiere" che sta prima dell'agente: legge la domanda e decide soltanto
# se rientra nell'ambito dichiarato in AMBITO_AGENTE. Non risponde alla domanda e non sceglie
# strumenti: quello resta compito dell'agente. Usa lo stesso modello dell'agente, ma con un
# prompt di sistema diverso e con una risposta "strutturata" (un piccolo JSON con due campi).
#   prompt_router()          -> le istruzioni del router, con l'ambito della configurazione
#   SCHEMA_CLASSIFICAZIONE   -> la forma della risposta: categoria e motivo
#   messaggi_per_router()    -> quali messaggi della conversazione vede il router
#   leggi_classificazione()  -> controlla la risposta: valida -> (categoria, motivo), altrimenti None
#   testo_rifiuto()          -> la risposta fissa per le domande fuori ambito
#   crea_router()            -> collega il tutto al modello di LM Studio

from collections.abc import Sequence

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage
from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI

# Le due sole categorie ammesse, scritte esattamente così.
CATEGORIE: tuple[str, str] = ("conversazione", "fuori ambito")

# Lo schema JSON della risposta del router: un oggetto con due campi obbligatori.
# "enum" dice al server che la categoria può essere solo una delle due.
SCHEMA_CLASSIFICAZIONE: dict = {
    "title": "classificazione",
    "description": "Classificazione dell'ultima domanda dell'utente rispetto all'ambito dell'assistente.",
    "type": "object",
    "properties": {
        "categoria": {"type": "string", "enum": list(CATEGORIE)},
        "motivo": {"type": "string", "description": "Motivo breve della scelta, in italiano."},
    },
    "required": ["categoria", "motivo"],
}


def prompt_router(ambito: str) -> str:
    """Prompt di sistema del router, con l'ambito letto dalla configurazione."""
    # Gemma (modello piccolo) tendeva a giudicare se LUI sapesse rispondere e a rifiutare
    # domande dell'ambito: per questo il prompt insiste sull'argomento, dà la regola
    # "in caso di dubbio" e alcuni esempi (diversi dalle domande delle prove reali).
    # Gli esempi citano argomenti dell'ambito attuale: se cambia AMBITO_AGENTE, aggiornarli.
    return (
        "Sei un classificatore di domande. Non rispondi alla domanda: dici soltanto se l'ultima "
        "domanda dell'utente rientra negli argomenti dell'assistente.\n"
        f"Argomenti dell'assistente: {ambito}.\n"
        "Valuta solo l'argomento della domanda, non se tu sappia rispondere o abbia i dati: "
        "a rispondere ci penserà l'assistente.\n"
        "Rispondi con una di queste due categorie:\n"
        "- conversazione: la domanda riguarda, anche solo in parte, uno degli argomenti "
        "dell'assistente; oppure è un saluto, un ringraziamento, una presentazione (per esempio "
        "«Mi chiamo Luca» o «Come mi chiamo?»), una domanda sull'assistente stesso o il seguito "
        "di un argomento già presente nella conversazione;\n"
        "- fuori ambito: la domanda riguarda soltanto altri argomenti (per esempio storia, "
        "letteratura, cultura generale, scienze, città, luoghi, cibo), comprese le richieste di "
        "parlare o raccontare di un tema generale: non sono normale conversazione.\n"
        "In caso di dubbio scegli conversazione.\n"
        "Esempi:\n"
        "«Quanto fa 45 diviso 9?» → conversazione\n"
        "«Converti 3 litri in galloni» → conversazione\n"
        "«Che giorno della settimana è oggi?» → conversazione\n"
        "«Ci sono corsi di Excel a Trieste?» → conversazione\n"
        "«Pioverà domani a Trieste?» → conversazione\n"
        "«Chi ha scritto la Divina Commedia?» → fuori ambito\n"
        "«Spiegami come funziona un vulcano» → fuori ambito\n"
        "«Parlami di Venezia e della pizza» → fuori ambito\n"
        "Aggiungi un motivo breve, in italiano."
    )


def testo_rifiuto(ambito: str) -> str:
    """Risposta fissa alle domande fuori ambito (senza due punti di fila alla fine)."""
    return f"Questa domanda è fuori dal mio ambito. Posso aiutarti con: {ambito.rstrip('.')}."


def messaggi_per_router(messaggi: Sequence[AnyMessage]) -> list[AnyMessage]:
    """Solo domande dell'utente e risposte di testo dell'assistente.

    Le richieste di strumento e i loro risultati (ToolMessage) restano fuori: il router
    deve capire il contesto della conversazione, non valutare gli strumenti.
    """
    filtrati = []
    for messaggio in messaggi:
        if isinstance(messaggio, HumanMessage):
            filtrati.append(messaggio)
        elif isinstance(messaggio, AIMessage) and not messaggio.tool_calls and messaggio.text.strip():
            filtrati.append(messaggio)
    return filtrati


def leggi_classificazione(uscita: dict) -> tuple[str, str] | None:
    """(categoria, motivo) se la risposta del router è valida, altrimenti None."""
    letto = uscita.get("parsed")
    if not isinstance(letto, dict):
        return None
    categoria, motivo = letto.get("categoria"), letto.get("motivo")
    if categoria not in CATEGORIE or not isinstance(motivo, str) or not motivo.strip():
        return None
    return categoria, motivo.strip()


def crea_router(modello: ChatOpenAI) -> Runnable:
    """Il modello (SENZA strumenti) che risponde con lo schema della classificazione.

    Con include_raw=True una risposta illeggibile (JSON non valido) non solleva eccezioni:
    finisce in "parsing_error". Fanno eccezione la risposta troncata dal limite di token e
    quella bloccata dal filtro del server, che la libreria segnala con un errore: il nodo
    router del grafo le tratta come risposte non valide. Gli errori di collegamento
    (LM Studio spento) invece si propagano come per l'agente.
    """
    return modello.with_structured_output(SCHEMA_CLASSIFICAZIONE, method="json_schema", include_raw=True)
