"""Comandi /prompt e /prompts: lettura del comando, controllo degli argomenti, elenco."""

# COSA FA QUESTO FILE
# I prompt MCP (step 5) li sceglie l'UTENTE, con un comando della CLI:
#   /prompts                              -> elenco dei prompt del server
#   /prompt nome argomento=valore ...     -> richiama un prompt
# Qui ci sono solo funzioni "pure" (niente server, niente modello, niente log):
#   leggi_comando_prompt() -> divide la riga in nome del prompt e argomenti
#   controlla_argomenti()  -> confronta gli argomenti con l'elenco del server (prompts/list)
#   testo_elenco_prompt()  -> prepara il testo che /prompts stampa
# Ogni problema diventa un ErroreComandoPrompt con un messaggio chiaro: la richiesta si blocca
# PRIMA di chiedere il prompt al server e senza chiamare il modello.

import shlex

from mcp.types import Prompt

from assistente.errori import ErroreComandoPrompt

USO_PROMPT = "Uso: /prompt nome argomento=valore ..."
VIRGOLETTE_NON_CHIUSE = (
    "Comando non valido: virgolette non chiuse "
    "(un apostrofo va tra virgolette doppie, es. argomento=\"l'agente\")."
)
BARRA_FINALE = (
    "Comando non valido: barra rovesciata alla fine "
    "(un valore con \\ va tra apici singoli, es. argomento='C:\\dati')."
)


def leggi_comando_prompt(riga: str) -> tuple[str, dict[str, str]]:
    """Divide la riga "/prompt nome chiave=valore ..." in nome del prompt e argomenti."""
    # Le parole si separano come in una shell: argomento="Model Context Protocol" è UNA parola
    # e le virgolette spariscono. Un apostrofo da solo conta come virgoletta aperta, una barra
    # rovesciata come carattere speciale: per questo i due messaggi suggeriscono come scriverli.
    try:
        parole = shlex.split(riga, posix=True)
    except ValueError as errore:
        messaggio = VIRGOLETTE_NON_CHIUSE if "quotation" in str(errore) else BARRA_FINALE
        raise ErroreComandoPrompt(messaggio) from errore
    # La prima parola è "/prompt": serve solo al terminale per riconoscere il comando.
    parole = parole[1:]
    if not parole:
        raise ErroreComandoPrompt(USO_PROMPT)
    nome, *coppie = parole
    argomenti: dict[str, str] = {}
    for parola in coppie:
        # Chiave e valore si separano al PRIMO "=": argomento="a=b" dà il valore "a=b".
        chiave, uguale, valore = parola.partition("=")
        if not uguale:
            raise ErroreComandoPrompt(
                f"Argomento non valido: '{parola}' "
                "(scrivere argomento=valore; un valore con spazi va tra virgolette)."
            )
        if not chiave:
            raise ErroreComandoPrompt(f"Argomento non valido: '{parola}' (manca il nome dell'argomento).")
        if not valore:
            raise ErroreComandoPrompt(f"Argomento non valido: '{parola}' (manca il valore).")
        if chiave in argomenti:
            raise ErroreComandoPrompt(f"Argomento ripetuto: '{chiave}'.")
        argomenti[chiave] = valore
    return nome, argomenti


# Nomi separati da virgola, oppure "nessuno" se la lista è vuota.
def _nomi(nomi: list[str]) -> str:
    return ", ".join(nomi) or "nessuno"


def controlla_argomenti(elenco: list[Prompt], nome: str, argomenti: dict[str, str]) -> None:
    """Controlla nome e argomenti rispetto all'elenco del server; se qualcosa non va, solleva."""
    # Solo i controlli chiesti dal PDF: prompt esistente, nessun argomento sconosciuto, nessun
    # obbligatorio mancante. I VALORI non si controllano (livello=pippo passa).
    per_nome = {prompt.name: prompt for prompt in elenco}
    if nome not in per_nome:
        raise ErroreComandoPrompt(f"Prompt sconosciuto: '{nome}'. Prompt disponibili: {_nomi(list(per_nome))}.")
    previsti = per_nome[nome].arguments or []
    ammessi = [argomento.name for argomento in previsti]
    # Prima gli sconosciuti (nell'ordine scritto dall'utente), poi i mancanti (nell'ordine del server).
    sconosciuti = [chiave for chiave in argomenti if chiave not in ammessi]
    if sconosciuti:
        raise ErroreComandoPrompt(
            f"Argomenti sconosciuti per '{nome}': {_nomi(sconosciuti)}. Argomenti ammessi: {_nomi(ammessi)}."
        )
    mancanti = [a.name for a in previsti if a.required and a.name not in argomenti]
    if mancanti:
        raise ErroreComandoPrompt(f"Argomenti obbligatori mancanti per '{nome}': {_nomi(mancanti)}.")


def testo_elenco_prompt(elenco: list[Prompt]) -> str:
    """Il testo di /prompts: nome e descrizione di ogni prompt, poi i suoi argomenti."""
    if not elenco:
        return "Il server non offre prompt."
    righe = []
    for prompt in elenco:
        righe.append(f"{prompt.name}: {prompt.description}" if prompt.description else prompt.name)
        for argomento in prompt.arguments or []:
            tipo = "obbligatorio" if argomento.required else "facoltativo"
            riga = f"  {argomento.name} ({tipo})"
            righe.append(f"{riga}: {argomento.description}" if argomento.description else riga)
    return "\n".join(righe)
