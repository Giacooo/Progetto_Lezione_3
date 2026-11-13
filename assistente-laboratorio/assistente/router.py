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
    return (
        "Sei il router dell'assistente del laboratorio. Non rispondi alla domanda: decidi soltanto "
        "se l'ultima domanda dell'utente rientra nell'ambito dell'assistente.\n"
        f"Ambito dell'assistente: {ambito}.\n"
        "Sono sempre «conversazione»: saluti, ringraziamenti, presentazioni (per esempio "
        "«Mi chiamo Luca» o «Come mi chiamo?»), domande sull'assistente stesso e seguiti di un "
        "tema dell'ambito già presente nella conversazione. Se una domanda contiene anche solo "
        "una parte che rientra nell'ambito, è «conversazione».\n"
        "Rispondi con una di queste due categorie:\n"
        "- conversazione: la domanda rientra nell'ambito o è normale conversazione;\n"
        "- fuori ambito: la domanda riguarda altri argomenti.\n"
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

    Con include_raw=True una risposta illeggibile non solleva eccezioni: finisce in
    "parsing_error". Gli errori di collegamento (LM Studio spento) invece si propagano
    come per l'agente.
    """
    return modello.with_structured_output(SCHEMA_CLASSIFICAZIONE, method="json_schema", include_raw=True)
