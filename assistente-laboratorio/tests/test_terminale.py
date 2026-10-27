from assistente.terminale import ciclo


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


def esegui(righe, rispondi):
    scritte = []
    ciclo(rispondi, leggi=lettore(righe), scrivi=scritte.append)
    return scritte


def test_risponde_e_chiude_con_esci():
    domande = []

    def rispondi(domanda):
        domande.append(domanda)
        return "risposta"

    scritte = esegui(["ciao", "esci", "non letta"], rispondi)
    assert domande == ["ciao"]
    assert "risposta" in scritte


def test_ignora_righe_vuote():
    domande = []
    esegui(["", "   ", "esci"], domande.append)
    assert domande == []


def test_eof_chiude_senza_errori():
    esegui([], lambda d: "x")


def test_ctrl_c_al_prompt_chiude():
    esegui([KeyboardInterrupt()], lambda d: "x")


def test_ctrl_c_durante_la_risposta_chiude():
    def rispondi(domanda):
        raise KeyboardInterrupt

    esegui(["ciao", "altra"], rispondi)


def test_esci_ignora_maiuscole_e_spazi():
    domande = []
    esegui(["  ESCI ", "dopo"], domande.append)
    assert domande == []


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
