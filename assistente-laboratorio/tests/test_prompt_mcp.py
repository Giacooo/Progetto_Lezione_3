# COSA PROVA QUESTO FILE
# Le funzioni pure dei comandi /prompt e /prompts (lezione 6, step 5): la lettura del comando
# scritto dall'utente, il controllo degli argomenti rispetto all'elenco del server (prompts/list)
# e il testo stampato da /prompts. Nessun server e nessun modello: l'elenco è costruito a mano,
# con gli stessi oggetti (Prompt, PromptArgument) che arrivano dal server.

import pytest
from mcp.types import Prompt, PromptArgument

from assistente.errori import ErroreComandoPrompt, ErroreTurno
from assistente.prompt_mcp import controlla_argomenti, leggi_comando_prompt
# Importato con un altro nome: pytest raccoglierebbe "testo_elenco_prompt" come se fosse un test.
from assistente.prompt_mcp import testo_elenco_prompt as elenco_in_testo

# Lo stesso elenco che pubblica il server MCP (vedi server_mcp.py).
ELENCO = [
    Prompt(
        name="spiega",
        description="Spiega un argomento al livello richiesto.",
        arguments=[
            PromptArgument(name="argomento", description="concetto da spiegare", required=True),
            PromptArgument(name="livello", description="base, intermedio o avanzato", required=False),
        ],
    ),
    Prompt(
        name="riassumi_conversazione",
        description="Riassume i turni della conversazione della sessione corrente.",
        arguments=[PromptArgument(name="stile", description="sintetico o dettagliato", required=False)],
    ),
]


# Il nuovo errore è un errore del turno: il ciclo del terminale lo stampa e la chat continua.
def test_errore_comando_prompt_e_un_errore_del_turno():
    assert issubclass(ErroreComandoPrompt, ErroreTurno)


# ---------------- Lettura del comando ----------------

# L'esempio del PDF: il valore con spazi tra virgolette diventa un valore unico, senza virgolette.
def test_lettura_con_virgolette():
    riga = '/prompt spiega argomento="Model Context Protocol" livello=base'
    assert leggi_comando_prompt(riga) == ("spiega", {"argomento": "Model Context Protocol", "livello": "base"})


def test_lettura_senza_argomenti():
    assert leggi_comando_prompt("/prompt riassumi_conversazione") == ("riassumi_conversazione", {})


# Chiave e valore si separano al PRIMO "=": il resto fa parte del valore.
def test_uguale_dentro_il_valore():
    assert leggi_comando_prompt('/prompt spiega argomento="a=b"') == ("spiega", {"argomento": "a=b"})


# Un apostrofo (frequente in italiano) va scritto dentro le virgolette doppie.
def test_apostrofo_tra_virgolette_doppie():
    assert leggi_comando_prompt("/prompt spiega argomento=\"l'agente\"") == ("spiega", {"argomento": "l'agente"})


# Una barra rovesciata (percorsi di Windows) resta com'è se il valore è tra apici singoli.
def test_barra_rovesciata_tra_apici_singoli():
    assert leggi_comando_prompt(r"/prompt spiega argomento='C:\dati'") == ("spiega", {"argomento": r"C:\dati"})


# Le chiavi restano come le ha scritte l'utente (maiuscole comprese): il controllo lo dirà.
def test_chiave_con_maiuscole_non_cambia():
    assert leggi_comando_prompt("/prompt spiega Livello=base") == ("spiega", {"Livello": "base"})


USO = "Uso: /prompt nome argomento=valore ..."
VIRGOLETTE = (
    "Comando non valido: virgolette non chiuse "
    "(un apostrofo va tra virgolette doppie, es. argomento=\"l'agente\")."
)
BARRA_FINALE = (
    "Comando non valido: barra rovesciata alla fine "
    "(un valore con \\ va tra apici singoli, es. argomento='C:\\dati')."
)


@pytest.mark.parametrize(
    ("riga", "messaggio"),
    [
        ("/prompt", USO),
        ("/prompt   ", USO),
        ('/prompt spiega argomento="Model', VIRGOLETTE),
        ("/prompt spiega argomento=l'agente", VIRGOLETTE),
        ("/prompt spiega argomento=C:\\", BARRA_FINALE),
        (
            "/prompt spiega argomento=Model Context",
            "Argomento non valido: 'Context' (scrivere argomento=valore; un valore con spazi va tra virgolette).",
        ),
        ("/prompt spiega =base", "Argomento non valido: '=base' (manca il nome dell'argomento)."),
        ("/prompt spiega livello=", "Argomento non valido: 'livello=' (manca il valore)."),
        ('/prompt spiega livello=""', "Argomento non valido: 'livello=' (manca il valore)."),
        ("/prompt spiega livello=base livello=avanzato", "Argomento ripetuto: 'livello'."),
    ],
)
def test_errori_di_lettura(riga, messaggio):
    with pytest.raises(ErroreComandoPrompt) as errore:
        leggi_comando_prompt(riga)
    assert str(errore.value) == messaggio


# ---------------- Controllo rispetto a prompts/list ----------------

@pytest.mark.parametrize(
    ("nome", "argomenti"),
    [
        ("spiega", {"argomento": "MCP", "livello": "base"}),
        ("spiega", {"argomento": "MCP"}),  # facoltativo omesso
        ("spiega", {"argomento": "MCP", "livello": "pippo"}),  # i valori non si controllano
        ("riassumi_conversazione", {}),
        ("riassumi_conversazione", {"stile": "dettagliato"}),
    ],
)
def test_controllo_superato(nome, argomenti):
    controlla_argomenti(ELENCO, nome, argomenti)  # nessuna eccezione


def errore_del_controllo(elenco, nome, argomenti) -> str:
    with pytest.raises(ErroreComandoPrompt) as errore:
        controlla_argomenti(elenco, nome, argomenti)
    return str(errore.value)


def test_prompt_sconosciuto():
    assert errore_del_controllo(ELENCO, "x", {}) == (
        "Prompt sconosciuto: 'x'. Prompt disponibili: spiega, riassumi_conversazione."
    )


def test_prompt_sconosciuto_con_elenco_vuoto():
    assert errore_del_controllo([], "x", {}) == "Prompt sconosciuto: 'x'. Prompt disponibili: nessuno."


# Gli sconosciuti si controllano PRIMA dei mancanti, e il messaggio li elenca tutti.
def test_argomenti_sconosciuti_prima_dei_mancanti():
    assert errore_del_controllo(ELENCO, "spiega", {"colore": "rosso", "tono": "allegro"}) == (
        "Argomenti sconosciuti per 'spiega': colore, tono. Argomenti ammessi: argomento, livello."
    )


def test_chiave_con_maiuscole_e_sconosciuta():
    assert errore_del_controllo(ELENCO, "spiega", {"argomento": "MCP", "Livello": "base"}).startswith(
        "Argomenti sconosciuti per 'spiega': Livello."
    )


def test_obbligatorio_mancante():
    assert errore_del_controllo(ELENCO, "spiega", {"livello": "base"}) == (
        "Argomenti obbligatori mancanti per 'spiega': argomento."
    )


def test_tutti_gli_obbligatori_mancanti_nell_ordine_del_server():
    doppio = Prompt(
        name="doppio",
        arguments=[PromptArgument(name="a", required=True), PromptArgument(name="b", required=True)],
    )
    assert errore_del_controllo([doppio], "doppio", {}) == "Argomenti obbligatori mancanti per 'doppio': a, b."


# Un prompt senza argomenti (arguments=None): nessun argomento è ammesso.
def test_prompt_senza_argomenti():
    vuoto = Prompt(name="vuoto", arguments=None)
    controlla_argomenti([vuoto], "vuoto", {})
    assert errore_del_controllo([vuoto], "vuoto", {"x": "1"}) == (
        "Argomenti sconosciuti per 'vuoto': x. Argomenti ammessi: nessuno."
    )


# ---------------- Testo di /prompts ----------------

def test_testo_elenco_prompt():
    assert elenco_in_testo(ELENCO) == (
        "spiega: Spiega un argomento al livello richiesto.\n"
        "  argomento (obbligatorio): concetto da spiegare\n"
        "  livello (facoltativo): base, intermedio o avanzato\n"
        "riassumi_conversazione: Riassume i turni della conversazione della sessione corrente.\n"
        "  stile (facoltativo): sintetico o dettagliato"
    )


# Descrizioni mancanti e "required" non indicato (None, cioè facoltativo).
def test_testo_elenco_prompt_senza_descrizioni():
    prompt = Prompt(name="nudo", arguments=[PromptArgument(name="x")])
    assert elenco_in_testo([prompt]) == "nudo\n  x (facoltativo)"


def test_testo_elenco_vuoto():
    assert elenco_in_testo([]) == "Il server non offre prompt."
