# COSA PROVA QUESTO FILE
# Il dialogo da terminale (la funzione ciclo() in terminale.py): uscita con "esci",
# righe vuote, Ctrl+C, fine dell'input, errori mostrati senza chiudere la chat e il
# carattere invisibile BOM di PowerShell. Tastiera e schermo sono simulati con liste.

from assistente.terminale import ciclo


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
