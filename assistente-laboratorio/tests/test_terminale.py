# COSA PROVA QUESTO FILE
# Il dialogo da terminale (la funzione ciclo() in terminale.py): uscita con "esci",
# righe vuote, Ctrl+C, fine dell'input, errori mostrati senza chiudere la chat e il
# carattere invisibile BOM di PowerShell. Tastiera e schermo sono simulati con liste.
# Prova anche main(): server MCP giù (codice 3) e, dallo step 4, le preferenze lette dopo la
# discovery e il loro fuso usato dall'orologio (modello, router, revisore e grafo finti).

from zoneinfo import ZoneInfo

from assistente.errori import ErroreCollegamentoMCP
from assistente.preferenze import Preferenze, predefinite
from assistente.terminale import ciclo, main


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
    from assistente.errori import ErroreTurno

    risposte = [ErroreTurno("Connessione fallita: controllare LM Studio, URL e porta."), "seconda"]

    def rispondi(domanda):
        risposta = risposte.pop(0)
        if isinstance(risposta, Exception):
            raise risposta
        return risposta

    scritte = esegui(["prima domanda", "seconda domanda"], rispondi)
    assert "Connessione fallita: controllare LM Studio, URL e porta." in scritte
    assert "seconda" in scritte


# PowerShell 5.1 aggiunge a volte un carattere invisibile (BOM, "\ufeff") all'inizio del
# testo passato con una pipe. Qui si prova che venga ignorato: "\ufeffciao" vale "ciao" e
# "\ufeffesci" chiude comunque la chat.
def test_ignora_il_bom_aggiunto_dalla_pipe_di_powershell():
    domande = []

    def rispondi(domanda):
        domande.append(domanda)
        return "ok"

    esegui(["\ufeffciao", "\ufeffesci", "dopo"], rispondi)
    assert domande == ["ciao"]


# Se il server MCP non parte o la discovery fallisce, main() si ferma con il codice 3 e un
# messaggio chiaro su stderr. Il collegamento MCP è simulato con un errore; la configurazione
# è valida (.env temporaneo). Gli strumenti MCP si caricano PRIMA di creare il modello, quindi
# il test non tocca né il modello né la rete.
def test_main_server_mcp_non_disponibile(tmp_path, monkeypatch, capsys):
    contenuto_env = "LM_BASE_URL=http://localhost:1234/v1\nLM_MODEL=modello-di-prova\nFUSO_ORARIO=Europe/Rome\n"
    contenuto_env += "AMBITO_AGENTE=data e ora, meteo\n"
    (tmp_path / ".env").write_text(contenuto_env, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    def carica_che_fallisce(connessione):
        raise ErroreCollegamentoMCP("prova")

    monkeypatch.setattr("assistente.terminale.carica_strumenti_mcp", carica_che_fallisce)
    assert main() == 3
    assert "Server MCP non disponibile: prova" in capsys.readouterr().err


# ---------------- PREFERENZE (lezione 6, step 4) ----------------

# Un modello finto per main(): main() chiede solo bind_tools; il resto (router, revisore, grafo)
# è sostituito nei test, quindi nessuno lo usa davvero e LM Studio non viene contattato.
class ModelloFinto:
    def bind_tools(self, strumenti):
        return self


# Prepara main() senza LM Studio né server: .env valido con FUSO_ORARIO=Europe/Rome in tmp_path,
# discovery finta (nessuno strumento MCP), carica_preferenze finta che restituisce "preferenze"
# e ricorda le chiamate, costruisci_grafo "spia" che ricorda gli argomenti ricevuti, ciclo che
# non legge la tastiera. Restituisce le due liste: chiamate a carica_preferenze e al grafo.
def prepara_main(tmp_path, monkeypatch, preferenze):
    contenuto_env = "LM_BASE_URL=http://localhost:1234/v1\nLM_MODEL=modello-di-prova\nFUSO_ORARIO=Europe/Rome\n"
    contenuto_env += "AMBITO_AGENTE=data e ora, meteo\n"
    (tmp_path / ".env").write_text(contenuto_env, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    chiamate_preferenze = []
    chiamate_grafo = []

    def carica_preferenze_finta(connessione, fuso_ripiego):
        chiamate_preferenze.append(fuso_ripiego)
        return preferenze

    def costruisci_grafo_spia(*argomenti):
        chiamate_grafo.append(argomenti)
        return "grafo finto"

    monkeypatch.setattr("assistente.terminale.carica_strumenti_mcp", lambda connessione: [])
    monkeypatch.setattr("assistente.terminale.carica_preferenze", carica_preferenze_finta)
    monkeypatch.setattr("assistente.terminale.crea_modello", lambda config: ModelloFinto())
    monkeypatch.setattr("assistente.terminale.crea_router", lambda modello: modello)
    monkeypatch.setattr("assistente.terminale.crea_revisore", lambda modello: modello)
    monkeypatch.setattr("assistente.terminale.costruisci_grafo", costruisci_grafo_spia)
    monkeypatch.setattr("assistente.terminale.ciclo", lambda rispondi: None)
    return chiamate_preferenze, chiamate_grafo


# Esegue lo strumento ora_corrente passato al grafo (secondo argomento di costruisci_grafo) e
# restituisce il suo risultato, es. "2026-11-15T05:00:00-05:00 (America/New_York)".
def ora_dal_grafo(argomenti_grafo):
    strumenti = argomenti_grafo[1]
    orologio = next(s for s in strumenti if s.name == "ora_corrente")
    return orologio.invoke({})


# Evidenza del PDF: con le preferenze America/New_York (e FUSO_ORARIO=Europe/Rome nel .env)
# l'orologio costruito da main() risponde nel fuso delle PREFERENZE, e il grafo riceve proprio
# quelle preferenze (ultimo argomento). carica_preferenze riceve il fuso del .env come ripiego.
def test_main_usa_il_fuso_delle_preferenze(tmp_path, monkeypatch):
    preferenze = Preferenze("inglese", ZoneInfo("America/New_York"), "dettagliato")
    chiamate_preferenze, chiamate_grafo = prepara_main(tmp_path, monkeypatch, preferenze)
    assert main() == 0
    assert chiamate_preferenze == [ZoneInfo("Europe/Rome")]
    assert len(chiamate_grafo) == 1
    assert chiamate_grafo[0][-1] == preferenze
    assert ora_dal_grafo(chiamate_grafo[0]).endswith("(America/New_York)")


# Resource non disponibile: carica_preferenze restituisce i predefiniti con il fuso di ripiego
# (Europe/Rome, da FUSO_ORARIO) e l'orologio risponde in quel fuso.
def test_main_con_preferenze_non_disponibili_usa_il_fuso_di_ripiego(tmp_path, monkeypatch):
    preferenze = predefinite(ZoneInfo("Europe/Rome"))
    chiamate_preferenze, chiamate_grafo = prepara_main(tmp_path, monkeypatch, preferenze)
    assert main() == 0
    assert chiamate_grafo[0][-1] == preferenze
    assert ora_dal_grafo(chiamate_grafo[0]).endswith("(Europe/Rome)")


# Server giù: main() si ferma con il codice 3 durante la discovery, PRIMA di leggere le
# preferenze (la lettura fallirebbe comunque e i predefiniti nasconderebbero il guasto).
def test_main_server_giu_non_legge_le_preferenze(tmp_path, monkeypatch, capsys):
    chiamate_preferenze, chiamate_grafo = prepara_main(tmp_path, monkeypatch, predefinite(ZoneInfo("Europe/Rome")))

    def carica_che_fallisce(connessione):
        raise ErroreCollegamentoMCP("prova")

    monkeypatch.setattr("assistente.terminale.carica_strumenti_mcp", carica_che_fallisce)
    assert main() == 3
    assert "Server MCP non disponibile: prova" in capsys.readouterr().err
    assert chiamate_preferenze == []
    assert chiamate_grafo == []
