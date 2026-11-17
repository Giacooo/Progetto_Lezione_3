# COSA PROVA QUESTO FILE
# Il dialogo da terminale (la funzione ciclo() in terminale.py): uscita con "esci",
# righe vuote, Ctrl+C, fine dell'input, errori mostrati senza chiudere la chat e il
# carattere invisibile BOM di PowerShell. Tastiera e schermo sono simulati con liste.
# Dallo step 5 prova lo smistamento dei comandi /prompts e /prompt.
# Dallo step 6 la CLI è un client dell'API dell'agente: lo smistamento usa un client finto
# (nessun servizio, nessun server MCP) e main() legge solo la configurazione del client.
# (Il montaggio dell'agente, con server MCP giù e preferenze, si prova in test_agente.py.)

import logging

from mcp.types import Prompt, PromptArgument

from assistente.errori import ErroreComandoPrompt, ErroreTurno
# Importata con un altro nome: pytest raccoglierebbe "testo_elenco_prompt" come se fosse un test.
from assistente.prompt_mcp import testo_elenco_prompt as elenco_in_testo
from assistente.terminale import ciclo, crea_smistamento, main


# Simula la TASTIERA: dà le righe una alla volta; quando finiscono simula la fine dell'input
# (EOFError). Se una "riga" è in realtà un errore (es. KeyboardInterrupt), lo lancia:
# serve per simulare Ctrl+C.
def lettore(righe):
    """Restituisce le righe una alla volta, poi simula la fine dell'input."""
    rimaste = list(righe)

    def leggi(prompt):
        if not rimaste:
            raise EOFError
        riga = rimaste.pop(0)
        if isinstance(riga, BaseException):
            raise riga
        return riga

    return leggi


# Funzione di aiuto: esegue il ciclo con la tastiera simulata e uno "schermo" che è una
# semplice lista (scritte.append). Restituisce tutto ciò che il programma ha "stampato".
def esegui(righe, rispondi):
    scritte = []
    ciclo(rispondi, leggi=lettore(righe), scrivi=scritte.append)
    return scritte


# Dopo "esci" il ciclo si ferma e la riga successiva ("non letta") non viene nemmeno letta.
def test_risponde_e_chiude_con_esci():
    domande = []

    def rispondi(domanda):
        domande.append(domanda)
        return "risposta"

    scritte = esegui(["ciao", "esci", "non letta"], rispondi)
    assert domande == ["ciao"]
    assert "risposta" in scritte


# Le righe vuote o di soli spazi vengono ignorate: nessuna domanda arriva a chi risponde.
def test_ignora_righe_vuote():
    domande = []
    esegui(["", "   ", "esci"], domande.append)
    assert domande == []


# Se l'input finisce all'improvviso, il ciclo chiude senza errori.
def test_eof_chiude_senza_errori():
    esegui([], lambda d: "x")


# Ctrl+C premuto al prompt: chiusura pulita.
def test_ctrl_c_al_prompt_chiude():
    esegui([KeyboardInterrupt()], lambda d: "x")


# Ctrl+C premuto mentre si aspetta la risposta: chiusura pulita anche in questo caso.
def test_ctrl_c_durante_la_risposta_chiude():
    def rispondi(domanda):
        raise KeyboardInterrupt

    esegui(["ciao", "altra"], rispondi)


# "  ESCI " (maiuscole e spazi) chiude lo stesso: la riga dopo non viene letta.
def test_esci_ignora_maiuscole_e_spazi():
    domande = []
    esegui(["  ESCI ", "dopo"], domande.append)
    assert domande == []


# Un turno fallito (ErroreTurno) viene mostrato come messaggio e la chat CONTINUA:
# la domanda dopo riceve la sua risposta ("seconda").
def test_errore_turno_viene_mostrato_e_la_sessione_continua():
    risposte = [ErroreTurno("Connessione fallita: controllare LM Studio, URL e porta."), "seconda"]

    def rispondi(domanda):
        risposta = risposte.pop(0)
        if isinstance(risposta, Exception):
            raise risposta
        return risposta

    scritte = esegui(["prima domanda", "seconda domanda"], rispondi)
    assert "Connessione fallita: controllare LM Studio, URL e porta." in scritte
    assert "seconda" in scritte


# PowerShell 5.1 aggiunge a volte un carattere invisibile (BOM, "﻿") all'inizio del
# testo passato con una pipe. Qui si prova che venga ignorato: "﻿ciao" vale "ciao" e
# "﻿esci" chiude comunque la chat.
def test_ignora_il_bom_aggiunto_dalla_pipe_di_powershell():
    domande = []

    def rispondi(domanda):
        domande.append(domanda)
        return "ok"

    esegui(["﻿ciao", "﻿esci", "dopo"], rispondi)
    assert domande == ["ciao"]


# ---------------- COMANDI /prompts E /prompt (step 5), CON LA CLI CLIENT (step 6) ----------------

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


# Un client dell'agente finto: ricorda le chiamate. "elenca" e "richiama", se dati, sono
# funzioni che possono lanciare un errore (come farebbe il client vero).
class ClienteFinto:
    def __init__(self, elenca=None, richiama=None):
        self.domande, self.elenchi, self.richiami = [], 0, []
        self._elenca, self._richiama = elenca, richiama

    def chiedi(self, domanda):
        self.domande.append(domanda)
        return f"risposta a {domanda}"

    def elenca_prompt(self):
        self.elenchi += 1
        return self._elenca() if self._elenca else ELENCO

    def richiama_prompt(self, nome, argomenti):
        self.richiami.append((nome, argomenti))
        return self._richiama(nome, argomenti) if self._richiama else "risposta al prompt"


def test_prompts_stampa_l_elenco():
    cliente = ClienteFinto()
    scritte = esegui(["/prompts"], crea_smistamento(cliente))
    assert elenco_in_testo(ELENCO) in scritte
    assert cliente.elenchi == 1 and cliente.domande == []


def test_prompts_con_parole_in_piu():
    cliente = ClienteFinto()
    scritte = esegui(["/prompts spiega"], crea_smistamento(cliente))
    assert "Uso: /prompts (senza argomenti)" in scritte
    assert cliente.elenchi == 0 and cliente.domande == []


def test_prompt_valido_va_all_agente():
    cliente = ClienteFinto()
    scritte = esegui(['/prompt spiega argomento="Model Context Protocol" livello=base'], crea_smistamento(cliente))
    assert cliente.richiami == [("spiega", {"argomento": "Model Context Protocol", "livello": "base"})]
    assert "risposta al prompt" in scritte
    assert cliente.domande == []


# Il controllo rispetto a prompts/list lo fa l'agente: il suo rifiuto viene stampato e la chat continua.
def test_prompt_non_valido_viene_mostrato():
    def rifiuta(nome, argomenti):
        raise ErroreComandoPrompt("Argomenti obbligatori mancanti per 'spiega': argomento.")

    cliente = ClienteFinto(richiama=rifiuta)
    scritte = esegui(["/prompt spiega livello=base", "ciao"], crea_smistamento(cliente))
    assert "Argomenti obbligatori mancanti per 'spiega': argomento." in scritte
    assert cliente.domande == ["ciao"]
    assert "risposta a ciao" in scritte


# Errore di lettura del comando: l'agente non viene contattato e il rifiuto finisce nel log.
def test_prompt_scritto_male_non_contatta_l_agente(caplog):
    caplog.set_level(logging.INFO, logger="assistente")
    cliente = ClienteFinto()
    scritte = esegui(['/prompt spiega argomento="Model'], crea_smistamento(cliente))
    assert any(s.startswith("Comando non valido: virgolette non chiuse") for s in scritte)
    assert cliente.richiami == []
    avvisi = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(avvisi) == 1
    assert avvisi[0].name == "assistente.terminale"
    assert avvisi[0].getMessage().startswith("prompt rifiutato nome=- motivo=Comando non valido: virgolette non chiuse")


# Solo "/prompts" e "/prompt" esatti (minuscole) sono comandi; tutto il resto, anche se
# comincia con "/", è una domanda normale e arriva così com'è.
def test_altre_righe_sono_domande():
    cliente = ClienteFinto()
    righe = ["/Prompts", "/PROMPT spiega", "/promptspiega", "/help"]
    esegui(righe, crea_smistamento(cliente))
    assert cliente.domande == righe
    assert cliente.elenchi == 0 and cliente.richiami == []


# Agente o server MCP giù durante un comando: il messaggio del client viene stampato e la chat continua.
def test_errore_durante_un_comando():
    def giu(*argomenti):
        raise ErroreTurno("Server MCP non disponibile: prova")

    cliente = ClienteFinto(elenca=giu, richiama=giu)
    scritte = esegui(["/prompts", "/prompt spiega argomento=MCP", "ciao"], crea_smistamento(cliente))
    assert scritte.count("Server MCP non disponibile: prova") == 2
    assert "risposta a ciao" in scritte


# ---------------- main() della CLI client (step 6) ----------------


def prepara_main(tmp_path, monkeypatch, env):
    (tmp_path / ".env").write_text(env, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AGENTE_URL", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)


def test_main_configurazione_non_valida(tmp_path, monkeypatch, capsys):
    prepara_main(tmp_path, monkeypatch, "AGENTE_URL=localhost:8000\n")
    assert main() == 2
    assert "Configurazione non valida: AGENTE_URL" in capsys.readouterr().err


# main() passa a ciclo() lo smistamento collegato a un ClienteAgente con AGENTE_URL; la CLI non
# richiede le variabili del modello e non avvia nessun server MCP.
def test_main_passa_lo_smistamento(tmp_path, monkeypatch):
    prepara_main(tmp_path, monkeypatch, "AGENTE_URL=http://agente-di-prova:9000\n")
    indirizzi = []
    cliente = ClienteFinto()
    monkeypatch.setattr("assistente.terminale.ClienteAgente", lambda url: indirizzi.append(url) or cliente)
    salvato = {}
    monkeypatch.setattr("assistente.terminale.ciclo", lambda rispondi: salvato.setdefault("rispondi", rispondi))
    assert main() == 0
    assert indirizzi == ["http://agente-di-prova:9000"]
    assert salvato["rispondi"]("/prompts") == elenco_in_testo(ELENCO)
    assert salvato["rispondi"]("ciao") == "risposta a ciao"


# Il modulo della CLI non importa più grafo, modello o collegamento MCP (anti-obiettivo della specifica).
def test_la_cli_non_conosce_l_agente():
    import assistente.terminale as terminale

    for nome in ("costruisci_grafo", "crea_modello", "connessione_stdio", "carica_strumenti_mcp", "Conversazione"):
        assert not hasattr(terminale, nome)
