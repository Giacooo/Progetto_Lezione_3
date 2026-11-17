"""Oggetti finti e fixture per i test del back-end (lezione 6, step 7)."""

# COSA C'È IN QUESTO FILE
#   ArchivioMemoria  archivio delle chat tenuto in memoria, con la STESSA interfaccia di
#                    ArchivioPostgres: i test dell'API girano senza database;
#   ArchivioGiu      archivio che fallisce sempre, come un PostgreSQL spento;
#   parametri_prove  i parametri del database di prova <POSTGRES_DB>_prove (creato se manca):
#                    i test non toccano mai il database vero dell'utente;
#   archivio         fixture parametrizzata: "memoria" sempre, "postgres" solo con
#                    PROVE_POSTGRES=1 e il container db acceso.

import copy
import os
import threading
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pg8000.native import identifier

from backend.archivio import ArchivioPostgres, Chat, ErroreDatabase, MessaggioSalvato, VoceElenco, connetti
from backend.configurazione import ParametriDatabase, carica_configurazione, leggi_ambiente


class _TurnoMemoria:
    def __init__(self, voce: dict):
        self.chat = voce["chat"]
        self.cronologia = copy.deepcopy(voce["cronologia"])
        self.riassunto = voce["riassunto"]
        self.ora_domanda = datetime.now(UTC)
        self.da_salvare = None  # scritto nell'archivio solo se il blocco "with" finisce bene

    def salva(self, domanda, risposta, strumenti_usati, cronologia, riassunto, titolo):
        d = MessaggioSalvato("utente", domanda, [], self.ora_domanda)
        r = MessaggioSalvato("assistente", risposta, copy.deepcopy(strumenti_usati), datetime.now(UTC))
        self.da_salvare = (d, r, copy.deepcopy(cronologia), riassunto, titolo)
        return d, r


class ArchivioMemoria:
    def __init__(self):
        self._voci: dict[int, dict] = {}  # id -> {"chat", "cronologia", "riassunto", "messaggi", "blocco"}
        self._prossimo = 1
        self._dati = threading.Lock()

    def crea(self, titolo):
        with self._dati:
            chat = Chat(id=self._prossimo, titolo=titolo, creata=datetime.now(UTC))
            self._prossimo += 1
            self._voci[chat.id] = {"chat": chat, "cronologia": [], "riassunto": "", "messaggi": [],
                                   "blocco": threading.Lock()}
        return chat

    def elenca(self):
        with self._dati:
            voci = [
                VoceElenco(v["chat"].id, v["chat"].titolo, v["chat"].creata,
                           v["messaggi"][-1].data if v["messaggi"] else None)
                for v in self._voci.values()
            ]
        return sorted(voci, key=lambda v: (v.ultimo_messaggio or v.creata, v.id), reverse=True)

    def leggi(self, chat_id):
        with self._dati:
            voce = self._voci.get(chat_id)
            return None if voce is None else (voce["chat"], list(voce["messaggi"]))

    def elimina(self, chat_id):
        with self._dati:
            return self._voci.pop(chat_id, None) is not None

    @contextmanager
    def turno(self, chat_id):
        with self._dati:
            voce = self._voci.get(chat_id)
        if voce is None:
            yield None
            return
        with voce["blocco"]:
            turno = _TurnoMemoria(voce)
            yield turno
            if turno.da_salvare is not None:
                d, r, cronologia, riassunto, titolo = turno.da_salvare
                with self._dati:
                    voce["messaggi"] += [d, r]
                    voce["cronologia"] = cronologia
                    voce["riassunto"] = riassunto
                    if titolo is not None:
                        voce["chat"] = Chat(voce["chat"].id, titolo, voce["chat"].creata)


class ArchivioGiu:
    """Ogni operazione fallisce come con PostgreSQL spento."""

    def _giu(self, *argomenti):
        raise ErroreDatabase("connessione rifiutata")

    crea = elenca = leggi = elimina = _giu

    @contextmanager
    def turno(self, chat_id):
        self._giu()
        yield None


def parametri_prove() -> ParametriDatabase:
    """Parametri del database di prova <POSTGRES_DB>_prove, creato se manca."""
    vero = carica_configurazione(leggi_ambiente(Path.cwd())).database
    prove = vero.con_database(f"{vero.database}_prove")
    conn = connetti(prove, database="postgres")
    try:
        conn.autocommit = True  # CREATE DATABASE non può stare dentro una transazione
        c = conn.cursor()
        c.execute("SELECT 1 FROM pg_database WHERE datname = %s", (prove.database,))
        if c.fetchone() is None:
            c.execute(f"CREATE DATABASE {identifier(prove.database)}")  # nome tra virgolette
    finally:
        conn.close()
    return prove


def archivio_postgres_vuoto() -> ArchivioPostgres:
    """Un ArchivioPostgres sul database di prova, con le tabelle svuotate."""
    archivio = ArchivioPostgres(parametri_prove())
    archivio.prepara()
    conn = connetti(archivio.parametri)
    try:
        conn.cursor().execute("TRUNCATE chat, messaggi RESTART IDENTITY CASCADE")
        conn.commit()
    finally:
        conn.close()
    return archivio


def salta_senza_postgres():
    if os.environ.get("PROVE_POSTGRES") != "1":
        pytest.skip("impostare PROVE_POSTGRES=1 con il container db acceso")


@pytest.fixture(params=["memoria", pytest.param("postgres", marks=pytest.mark.postgres)])
def archivio(request):
    if request.param == "memoria":
        return ArchivioMemoria()
    salta_senza_postgres()
    return archivio_postgres_vuoto()
