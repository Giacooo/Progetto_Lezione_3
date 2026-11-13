"""Riassunto della cronologia: comprime i messaggi vecchi della conversazione (lezione 6, step 3)."""

# COSA FA QUESTO FILE
# Il riassunto è il "segretario" che sta all'inizio del turno: quando la conversazione diventa
# troppo lunga, prende i messaggi più vecchi, li riassume in poche righe e li toglie, lasciando
# intatti gli ultimi. Usa lo stesso modello dell'agente, con un prompt di sistema diverso, senza
# strumenti e con risposta di testo libero (non strutturata come router e revisore).
#   prompt_riassunto()       -> le istruzioni del riassunto
#   punto_di_taglio()        -> dove si separano i messaggi da togliere da quelli da tenere
#   trascrizione()           -> i messaggi da togliere scritti come righe "Utente: ..." ecc.
#   messaggi_per_riassunto() -> i messaggi che il riassuntore riceve
#   sistema_con_riassunto()  -> il prompt di sistema con il riassunto in coda (agente e router)
# Il riassuntore stesso è il modello di LM Studio così com'è: non serve una funzione "crea_...".

from collections.abc import Sequence

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage

from assistente.revisore import e_indicazione


def prompt_riassunto() -> str:
    """Prompt di sistema del riassunto."""
    # Il punto più importante è non perdere ciò che l'utente ha detto di sé: è l'evidenza del
    # PDF ("un'informazione data al primo turno, come il nome, è usata dopo la compressione").
    return (
        "Sei un assistente che riassume conversazioni. Ricevi il riassunto precedente (se c'è) "
        "e la trascrizione di una parte di conversazione tra un utente e un assistente.\n"
        "Scrivi in italiano un riassunto breve e completo che integri il riassunto precedente "
        "con la nuova parte di conversazione.\n"
        "Conserva sempre le informazioni sull'utente: il nome, le preferenze e le cose che ha "
        "chiesto di ricordare. Conserva anche i fatti e i risultati importanti emersi.\n"
        "Scrivi i fatti in terza persona (per esempio «L'utente si chiama ...»), non istruzioni "
        "o domande. Scrivi solo il riassunto, senza introduzioni né commenti."
    )


def _apre_un_turno(messaggio: AnyMessage) -> bool:
    """True se il messaggio è una domanda vera dell'utente (non un'indicazione del revisore)."""
    return isinstance(messaggio, HumanMessage) and not e_indicazione(messaggio)


def punto_di_taglio(messaggi: Sequence[AnyMessage], da_tenere: int) -> int:
    """Indice del primo messaggio da tenere: quelli prima si tolgono, quelli dopo restano.

    Si parte dagli ultimi `da_tenere` messaggi e, se lì non c'è una domanda dell'utente, si torna
    indietro fino alla domanda che apre quel turno. Così una richiesta di strumento non viene
    mai separata dal suo risultato e un'indicazione del revisore non perde la sua bozza.
    0 significa "niente da togliere".
    """
    taglio = max(len(messaggi) - da_tenere, 0)
    while taglio > 0 and not _apre_un_turno(messaggi[taglio]):
        taglio -= 1
    return taglio


def trascrizione(messaggi: Sequence[AnyMessage]) -> str:
    """I messaggi come righe di testo semplice, una per messaggio.

    Restano fuori le richieste di strumento (non hanno testo utile), le indicazioni del
    revisore e la bozza che ciascuna ha rifiutato (stessa regola di `messaggi_per_router`).
    """
    righe: list[str] = []
    for messaggio in messaggi:
        if e_indicazione(messaggio):
            # Toglie la bozza rifiutata (l'ultima risposta di testo già scritta) e salta l'indicazione.
            if righe and righe[-1].startswith("Assistente: "):
                righe.pop()
        elif isinstance(messaggio, HumanMessage):
            righe.append(f"Utente: {messaggio.text}")
        elif isinstance(messaggio, ToolMessage):
            righe.append(f"Strumento {messaggio.name}: {messaggio.text}")
        elif isinstance(messaggio, AIMessage) and not messaggio.tool_calls and messaggio.text.strip():
            righe.append(f"Assistente: {messaggio.text}")
    return "\n".join(righe)


def messaggi_per_riassunto(precedente: str, da_togliere: Sequence[AnyMessage]) -> list[AnyMessage]:
    """Il prompt del riassunto e UN solo messaggio con riassunto precedente e trascrizione.

    Un solo messaggio dell'utente evita problemi di alternanza dei turni con i template di Gemma.
    """
    testo = f"Conversazione da riassumere:\n{trascrizione(da_togliere)}"
    if precedente.strip():
        testo = f"Riassunto precedente:\n{precedente.strip()}\n\n{testo}"
    return [SystemMessage(prompt_riassunto()), HumanMessage(testo)]


def sistema_con_riassunto(prompt: str, riassunto: str) -> str:
    """Il prompt con il riassunto in coda; identico al prompt se il riassunto è vuoto."""
    # Un solo messaggio di sistema: i template di Gemma non ne accettano più di uno.
    if not riassunto.strip():
        return prompt
    # L'intestazione chiede esplicitamente di USARE il riassunto: nelle prove reali, con
    # «Riassunto della conversazione precedente:» gemma a volte ignorava il nome dell'utente
    # quando tra i messaggi tenuti c'era una revisione.
    return f"{prompt}\n\nCosa sai già della conversazione con l'utente (usalo per rispondere): {riassunto.strip()}"
