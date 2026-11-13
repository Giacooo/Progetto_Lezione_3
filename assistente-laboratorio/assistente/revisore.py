"""Revisore: controlla se la risposta dell'agente è coerente con la domanda (lezione 6, step 2)."""

# COSA FA QUESTO FILE
# Il revisore è il "correttore di bozze" che sta dopo l'agente: legge la domanda dell'utente e
# la risposta proposta e dice soltanto se la risposta è coerente, cioè se risponde a tutte le
# parti della domanda e resta in tema. Non controlla se i dati sono veri e non riscrive la
# risposta. Usa lo stesso modello dell'agente, con un prompt di sistema diverso e una risposta
# "strutturata" (un piccolo JSON con due campi), come il router.
#   prompt_revisore()       -> le istruzioni del revisore
#   SCHEMA_VALUTAZIONE      -> la forma della risposta: coerente (sì/no) e motivo
#   domanda_e_risposta()    -> quale domanda e quale risposta giudicare
#   messaggi_per_revisore() -> i messaggi che il revisore riceve
#   leggi_valutazione()     -> controlla la risposta: valida -> (coerente, motivo), altrimenti None
#   indicazione()           -> il messaggio per l'agente quando la risposta non è coerente
#   e_indicazione()         -> riconosce quel messaggio nella cronologia
#   crea_revisore()         -> collega il tutto al modello di LM Studio

from collections.abc import Sequence

from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI

# Le due sole risposte ammesse per "coerente", scritte esattamente così (come nel PDF).
VALORI_COERENTE: tuple[str, str] = ("sì", "no")

# Il nome che distingue l'indicazione del revisore dalle domande vere dell'utente: entrambe
# sono messaggi "utente", ma l'indicazione porta questo nome.
NOME_INDICAZIONE = "revisore"

# Lo schema JSON della risposta del revisore: un oggetto con due campi obbligatori.
SCHEMA_VALUTAZIONE: dict = {
    "title": "valutazione",
    "description": "Valutazione della risposta proposta rispetto alla domanda dell'utente.",
    "type": "object",
    "properties": {
        "coerente": {"type": "string", "enum": list(VALORI_COERENTE)},
        "motivo": {"type": "string", "description": "Motivo breve della valutazione, in italiano."},
    },
    "required": ["coerente", "motivo"],
}


def prompt_revisore() -> str:
    """Prompt di sistema del revisore."""
    # Il revisore non vede la conversazione precedente: per questo il prompt gli dice di non
    # bocciare le domande brevi che la proseguono ("E domani?") per mancanza di contesto.
    return (
        "Sei un revisore di risposte. Ricevi la domanda di un utente e la risposta proposta da "
        "un assistente. Non rispondi alla domanda e non riscrivi la risposta: dici soltanto se "
        "la risposta è coerente con la domanda.\n"
        "Una risposta è coerente se risponde a tutte le parti della domanda e resta in tema. "
        "Non giudicare se i dati della risposta sono veri o aggiornati: non puoi controllarli.\n"
        "Una domanda breve può proseguire una conversazione precedente che tu non vedi (per "
        "esempio «E domani?» o «Come mi chiamo?»): in quel caso giudica solo se la risposta "
        "prova a rispondere a ciò che viene chiesto, senza bocciarla per mancanza di contesto.\n"
        "Rispondi con coerente uguale a una di queste due parole:\n"
        "- sì: la risposta risponde a tutte le parti della domanda e resta in tema;\n"
        "- no: la risposta tralascia una parte della domanda oppure parla d'altro.\n"
        "Aggiungi un motivo breve, in italiano; se la risposta non è coerente, di' che cosa manca "
        "o che cosa è fuori tema."
    )


def e_indicazione(messaggio: AnyMessage) -> bool:
    """True se il messaggio è un'indicazione del revisore (non una domanda dell'utente)."""
    return isinstance(messaggio, HumanMessage) and messaggio.name == NOME_INDICAZIONE


def domanda_e_risposta(messaggi: Sequence[AnyMessage]) -> tuple[str, str]:
    """La domanda del turno (ultimo messaggio dell'utente che non è un'indicazione) e la risposta
    proposta (l'ultimo messaggio, cioè la risposta finale dell'agente)."""
    domanda = next(m.text for m in reversed(messaggi) if isinstance(m, HumanMessage) and not e_indicazione(m))
    return domanda, messaggi[-1].text


def messaggi_per_revisore(domanda: str, risposta: str) -> list[AnyMessage]:
    """Il prompt del revisore e un solo messaggio con domanda e risposta da giudicare."""
    return [
        SystemMessage(prompt_revisore()),
        HumanMessage(f"Domanda dell'utente:\n{domanda}\n\nRisposta proposta:\n{risposta}"),
    ]


def leggi_valutazione(uscita: dict) -> tuple[str, str] | None:
    """(coerente, motivo) se la risposta del revisore è valida, altrimenti None."""
    letto = uscita.get("parsed")
    if not isinstance(letto, dict):
        return None
    coerente, motivo = letto.get("coerente"), letto.get("motivo")
    if coerente not in VALORI_COERENTE or not isinstance(motivo, str) or not motivo.strip():
        return None
    return coerente, motivo.strip()


def indicazione(motivo: str) -> HumanMessage:
    """Il messaggio per l'agente quando la risposta non è coerente: contiene il motivo."""
    testo = (
        "Indicazione del revisore: la risposta precedente non è coerente con la domanda. "
        f"Motivo: {motivo.rstrip('.')}. Rispondi di nuovo alla domanda, completa e in tema."
    )
    return HumanMessage(testo, name=NOME_INDICAZIONE)


def crea_revisore(modello: ChatOpenAI) -> Runnable:
    """Il modello (SENZA strumenti) che risponde con lo schema della valutazione.

    Come per il router: con include_raw=True una risposta illeggibile finisce in
    "parsing_error" senza eccezioni; la risposta troncata o filtrata solleva un errore che il
    nodo del grafo tratta come risposta non valida; gli errori di collegamento si propagano.
    """
    return modello.with_structured_output(SCHEMA_VALUTAZIONE, method="json_schema", include_raw=True)
