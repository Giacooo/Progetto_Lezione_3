"""Test dell'archivio delle chat del back-end (lezione 6, step 7)."""

# COSA PROVA QUESTO FILE
# L'archivio è il "magazzino" delle chat. Ce ne sono due con la stessa interfaccia:
#   - ArchivioMemoria (tests/finti_backend.py): dati in memoria, per i test dell'API;
#   - ArchivioPostgres (backend/archivio.py): quello vero, su PostgreSQL.
# Gli stessi test girano su entrambi (fixture "archivio" parametrizzata). I casi "postgres"
# girano solo con PROVE_POSTGRES=1 e il container db acceso, e usano il database separato
# <POSTGRES_DB>_prove: le chat vere dell'utente non vengono mai toccate.

import socket
import threading
import time

import pytest
from finti_backend import archivio  # noqa: F401  (è una fixture)

from backend.archivio import ArchivioPostgres, ErroreDatabase
from backend.configurazione import ParametriDatabase

CRONOLOGIA_1 = [
    {"ruolo": "utente", "testo": "Quanto fa 45 diviso 9?"},
    {"ruolo": "assistente", "testo": "", "richieste_strumenti": [{"id": "c1", "nome": "calcola", "argomenti": {"espressione": "45 / 9"}}]},
    {"ruolo": "strumento", "testo": "5", "nome": "calcola", "id_chiamata": "c1"},
    {"ruolo": "assistente", "testo": "Fa 5."},
]
STRUMENTI_1 = [{"nome": "calcola", "argomenti": {"espressione": "45 / 9"}, "risultato": "5"}]


# Un turno completo salvato, come lo farà l'API.
def salva_turno(archivio, chat_id, domanda="Quanto fa 45 diviso 9?", risposta="Fa 5.", cronologia=CRONOLOGIA_1,
                riassunto="", titolo=None, strumenti=STRUMENTI_1):
    with archivio.turno(chat_id) as turno:
        return turno.salva(domanda, risposta, strumenti, cronologia, riassunto, titolo)


def test_crea_e_leggi_chat_vuota(archivio):
    chat = archivio.crea("Prima chat")
    letta, messaggi = archivio.leggi(chat.id)
    assert letta == chat
    assert chat.titolo == "Prima chat"
    assert messaggi == []


def test_crea_senza_titolo(archivio):
    chat = archivio.crea(None)
    assert chat.titolo is None


def test_leggi_inesistente_none(archivio):
    assert archivio.leggi(999) is None


def test_elenco_con_ultimo_messaggio_e_ordine(archivio):
    prima = archivio.crea("prima")
    seconda = archivio.crea("seconda")
    elenco = archivio.elenca()
    # Nessun messaggio: ultimo_messaggio è None e in cima c'è la chat creata per ultima.
    assert [v.id for v in elenco] == [seconda.id, prima.id]
    assert all(v.ultimo_messaggio is None for v in elenco)
    domanda, risposta = salva_turno(archivio, prima.id)
    elenco = archivio.elenca()
    # Ora la prima ha l'attività più recente: sale in cima, con la data della risposta.
    assert [v.id for v in elenco] == [prima.id, seconda.id]
    assert elenco[0].ultimo_messaggio == risposta.data
    assert elenco[0].titolo == "prima"


def test_turno_salva_domanda_e_risposta_in_ordine(archivio):
    chat = archivio.crea(None)
    with archivio.turno(chat.id) as turno:
        assert turno.chat.id == chat.id
        assert (turno.cronologia, turno.riassunto) == ([], "")
        domanda, risposta = turno.salva("Quanto fa 45 diviso 9?", "Fa 5.", STRUMENTI_1, CRONOLOGIA_1, "", None)
    assert (domanda.ruolo, domanda.testo, domanda.strumenti_usati) == ("utente", "Quanto fa 45 diviso 9?", [])
    assert (risposta.ruolo, risposta.testo, risposta.strumenti_usati) == ("assistente", "Fa 5.", STRUMENTI_1)
    assert domanda.data == turno.ora_domanda
    assert domanda.data <= risposta.data
    _, messaggi = archivio.leggi(chat.id)
    assert messaggi == [domanda, risposta]
    # La memoria dell'agente salvata è quella che il turno dopo rimanderà all'agente.
    with archivio.turno(chat.id) as turno:
        assert turno.cronologia == CRONOLOGIA_1
        assert turno.riassunto == ""


def test_riassunto_conservato(archivio):
    chat = archivio.crea(None)
    salva_turno(archivio, chat.id, riassunto="L'utente si chiama Carlo.")
    with archivio.turno(chat.id) as turno:
        assert turno.riassunto == "L'utente si chiama Carlo."


def test_turno_senza_salva_non_lascia_nulla(archivio):
    chat = archivio.crea(None)
    with archivio.turno(chat.id):
        pass
    _, messaggi = archivio.leggi(chat.id)
    assert messaggi == []


def test_eccezione_nel_turno_non_lascia_nulla(archivio):
    chat = archivio.crea(None)
    salva_turno(archivio, chat.id)
    with pytest.raises(RuntimeError):
        with archivio.turno(chat.id) as turno:
            turno.salva("altra", "risposta", [], [{"ruolo": "utente", "testo": "altra"}], "nuovo", "titolo nuovo")
            raise RuntimeError("l'agente non ha risposto")
    letta, messaggi = archivio.leggi(chat.id)
    assert [m.testo for m in messaggi] == ["Quanto fa 45 diviso 9?", "Fa 5."]
    assert letta.titolo is None
    with archivio.turno(chat.id) as turno:
        assert (turno.cronologia, turno.riassunto) == (CRONOLOGIA_1, "")


def test_turno_chat_inesistente_none(archivio):
    with archivio.turno(999) as turno:
        assert turno is None


def test_elimina_a_cascata(archivio):
    chat = archivio.crea(None)
    salva_turno(archivio, chat.id)
    assert archivio.elimina(chat.id) is True
    assert archivio.leggi(chat.id) is None
    assert archivio.elenca() == []


def test_elimina_inesistente_false(archivio):
    assert archivio.elimina(999) is False


def test_titolo_scritto_solo_se_dato(archivio):
    chat = archivio.crea(None)
    salva_turno(archivio, chat.id, titolo="Quanto fa 45 diviso 9?")
    salva_turno(archivio, chat.id, titolo=None)
    letta, _ = archivio.leggi(chat.id)
    assert letta.titolo == "Quanto fa 45 diviso 9?"


def test_accenti_conservati(archivio):
    testo = "È già l'ora? «Sì» 😀"
    chat = archivio.crea(testo)
    cronologia = [{"ruolo": "utente", "testo": testo}, {"ruolo": "assistente", "testo": testo}]
    salva_turno(archivio, chat.id, domanda=testo, risposta=testo, cronologia=cronologia, riassunto=testo,
                strumenti=[{"nome": "calcola", "argomenti": {"espressione": testo}, "risultato": testo}])
    letta, messaggi = archivio.leggi(chat.id)
    assert letta.titolo == testo
    assert [m.testo for m in messaggi] == [testo, testo]
    assert messaggi[1].strumenti_usati[0]["argomenti"]["espressione"] == testo
    with archivio.turno(chat.id) as turno:
        assert (turno.cronologia, turno.riassunto) == (cronologia, testo)


def test_turni_contemporanei_in_fila(archivio):
    chat = archivio.crea(None)
    a_dentro = threading.Event()
    via_a = threading.Event()
    ordine = []
    vista_da_b = {}

    def primo():
        with archivio.turno(chat.id) as turno:
            a_dentro.set()
            via_a.wait(10)
            ordine.append("A salva")
            turno.salva("U1", "A1", [], [{"ruolo": "utente", "testo": "U1"}], "", None)

    def secondo():
        a_dentro.wait(10)
        with archivio.turno(chat.id) as turno:
            ordine.append("B entra")
            vista_da_b["cronologia"] = turno.cronologia
            turno.salva("U2", "A2", [], turno.cronologia + [{"ruolo": "utente", "testo": "U2"}], "", None)

    thread = [threading.Thread(target=primo), threading.Thread(target=secondo)]
    for t in thread:
        t.start()
    a_dentro.wait(10)
    time.sleep(0.5)  # tempo a B per provare a entrare: se non fosse bloccato, entrerebbe prima di "A salva"
    via_a.set()
    for t in thread:
        t.join(15)
    assert ordine == ["A salva", "B entra"]
    assert vista_da_b["cronologia"] == [{"ruolo": "utente", "testo": "U1"}]
    _, messaggi = archivio.leggi(chat.id)
    assert [m.testo for m in messaggi] == ["U1", "A1", "U2", "A2"]


# ---------------- Solo PostgreSQL ----------------


def test_persistenza_nuovo_archivio(archivio):
    if not isinstance(archivio, ArchivioPostgres):
        pytest.skip("solo PostgreSQL")
    chat = archivio.crea("resta")
    salva_turno(archivio, chat.id)
    # Un archivio NUOVO sugli stessi parametri: è quello che succede al riavvio del back-end.
    nuovo = ArchivioPostgres(archivio.parametri)
    nuovo.prepara()
    assert [v.id for v in nuovo.elenca()] == [chat.id]
    _, messaggi = nuovo.leggi(chat.id)
    assert [m.testo for m in messaggi] == ["Quanto fa 45 diviso 9?", "Fa 5."]


def test_prepara_due_volte(archivio):
    if not isinstance(archivio, ArchivioPostgres):
        pytest.skip("solo PostgreSQL")
    archivio.prepara()
    archivio.prepara()


# Non serve un server: sulla porta 1 non risponde nessuno.
def test_database_irraggiungibile():
    archivio = ArchivioPostgres(ParametriDatabase("utente", "segreta", "chat", "127.0.0.1", 1))
    with pytest.raises(ErroreDatabase):
        archivio.prepara()
    with pytest.raises(ErroreDatabase):
        archivio.elenca()


# Un servizio in ascolto che NON è PostgreSQL (porta sbagliata in POSTGRES_PORTA): ErroreDatabase,
# né un errore interno del driver né un'attesa infinita.
def servizio_finto(risposta: bytes | None):
    server = socket.create_server(("127.0.0.1", 0))

    def servi():
        conn, _ = server.accept()
        conn.recv(1024)
        if risposta is not None:
            conn.sendall(risposta)
        else:
            time.sleep(3)  # accetta la connessione e non risponde
        conn.close()

    threading.Thread(target=servi, daemon=True).start()
    return server, server.getsockname()[1]


@pytest.mark.parametrize("risposta", [b"HTTP/1.1 400 Bad Request\r\n\r\n", None], ids=["HTTP", "muto"])
def test_porta_di_un_altro_servizio(risposta, monkeypatch):
    monkeypatch.setattr("backend.archivio.ATTESA_CONNESSIONE", 0.5)
    server, porta = servizio_finto(risposta)
    try:
        archivio = ArchivioPostgres(ParametriDatabase("utente", "segreta", "chat", "127.0.0.1", porta))
        inizio = time.monotonic()
        with pytest.raises(ErroreDatabase):
            archivio.prepara()
        assert time.monotonic() - inizio < 2.5
    finally:
        server.close()
