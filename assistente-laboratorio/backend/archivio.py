"""Archivio delle chat del back-end: interfaccia comune e implementazione su PostgreSQL."""

# COSA FA QUESTO FILE (lezione 6, step 7)
# È il "magazzino" delle chat. Due tabelle:
#   chat      una riga per chat: titolo, data di creazione e la MEMORIA DELL'AGENTE
#             (cronologia completa e riassunto, come li restituisce l'agente dello step 6);
#   messaggi  quello che vede il front-end: per ogni turno la domanda e la risposta finale,
#             con gli strumenti usati. Eliminando una chat i suoi messaggi spariscono con lei
#             (ON DELETE CASCADE).
# L'operazione delicata è il TURNO (inviare un messaggio): con turno(chat_id) si apre una
# transazione e si "blocca" la chat; dentro si chiama l'agente e, solo se risponde, si salvano
# insieme domanda, risposta e memoria. Se l'agente non risponde (eccezione) o salva() non viene
# chiamato, la transazione viene annullata: nella chat non resta niente a metà.
# Il blocco (SELECT ... FOR UPDATE) fa sì che due messaggi contemporanei alla stessa chat siano
# serviti uno dopo l'altro: il secondo vede la memoria salvata dal primo.
# Ogni operazione apre e chiude la sua connessione (niente "pool": poche richieste, un utente).
# Il driver è pg8000, scritto solo in Python (Smart App Control di Windows blocca le DLL di
# psycopg). I valori JSON (cronologia, strumenti usati) si mandano come testo con "::jsonb" e
# tornano già trasformati in liste e dizionari Python.

import json
import socket
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

import pg8000.dbapi

from backend.configurazione import ParametriDatabase

# Secondi di attesa per aprire la connessione: oltre, il database è considerato giù.
ATTESA_CONNESSIONE = 5


class ErroreDatabase(Exception):
    """PostgreSQL non raggiungibile o connessione caduta."""


@dataclass(frozen=True)
class Chat:
    id: int
    titolo: str | None  # None finché non c'è (l'API mostra "Nuova chat")
    creata: datetime


@dataclass(frozen=True)
class VoceElenco:
    id: int
    titolo: str | None
    creata: datetime
    ultimo_messaggio: datetime | None  # None se la chat non ha messaggi


@dataclass(frozen=True)
class MessaggioSalvato:
    ruolo: str  # "utente" o "assistente"
    testo: str
    strumenti_usati: list[dict]  # solo per "assistente": [{"nome", "argomenti", "risultato"}]
    data: datetime


class TurnoAperto(Protocol):
    """Una chat bloccata durante un turno, con la memoria dell'agente da rimandargli."""

    chat: Chat
    cronologia: list[dict]
    riassunto: str
    ora_domanda: datetime  # presa DOPO il blocco: i turni non si intrecciano

    def salva(self, domanda: str, risposta: str, strumenti_usati: list[dict], cronologia: list[dict],
              riassunto: str, titolo: str | None) -> tuple[MessaggioSalvato, MessaggioSalvato]:
        """Domanda e risposta in messaggi, memoria aggiornata; il titolo solo se non è None."""


class ArchivioChat(Protocol):
    def crea(self, titolo: str | None) -> Chat: ...
    def elenca(self) -> list[VoceElenco]: ...
    def leggi(self, chat_id: int) -> tuple[Chat, list[MessaggioSalvato]] | None: ...
    def elimina(self, chat_id: int) -> bool: ...
    def turno(self, chat_id: int) -> AbstractContextManager[TurnoAperto | None]: ...


# Le tabelle, create all'avvio se non esistono (nessuno strumento di migrazione).
SCHEMA = """
CREATE TABLE IF NOT EXISTS chat (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    titolo      TEXT,
    creata      TIMESTAMPTZ NOT NULL DEFAULT now(),
    cronologia  JSONB NOT NULL DEFAULT '[]'::jsonb,
    riassunto   TEXT  NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS messaggi (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    chat_id         BIGINT NOT NULL REFERENCES chat(id) ON DELETE CASCADE,
    ruolo           TEXT NOT NULL CHECK (ruolo IN ('utente', 'assistente')),
    testo           TEXT NOT NULL,
    strumenti_usati JSONB NOT NULL DEFAULT '[]'::jsonb,
    data            TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS messaggi_chat_id ON messaggi (chat_id, id);
"""


def connetti(parametri: ParametriDatabase, database: str | None = None) -> pg8000.dbapi.Connection:
    """Apre una connessione (al database dei parametri, o a quello indicato).

    Collegamento e presentazione al server (utente, password) hanno un limite di
    ATTESA_CONNESSIONE secondi; a connessione riuscita il limite si toglie: durante un turno la
    connessione resta ferma finché l'agente risponde, e un secondo turno sulla stessa chat aspetta
    il blocco anche a lungo (fino a 600 s). Niente SSL: il database è locale (container sul PC o,
    allo step 9, nella rete di Docker). Ogni problema di connessione diventa ErroreDatabase, anche
    quando sulla porta risponde un programma che non è PostgreSQL.
    """
    try:
        presa = socket.create_connection((parametri.host, parametri.porta), timeout=ATTESA_CONNESSIONE)
        presa.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    except OSError as e:
        raise ErroreDatabase(f"connessione a {parametri.host}:{parametri.porta} non riuscita ({e})") from None
    try:
        conn = pg8000.dbapi.connect(user=parametri.utente, password=parametri.password,
                                    database=database or parametri.database, sock=presa, ssl_context=False)
    except Exception as e:  # anche errori interni del driver davanti a un servizio che non è PostgreSQL
        presa.close()
        raise ErroreDatabase(_testo_errore(e)) from None
    presa.settimeout(None)
    return conn


def _testo_errore(e: Exception) -> str:
    # Gli errori del server arrivano come dizionario ({"M": messaggio, ...}): si tiene il messaggio.
    if e.args and isinstance(e.args[0], dict):
        return str(e.args[0].get("M", e.args[0]))
    return str(e).strip() or type(e).__name__


# Classi di errore del server che significano "database non disponibile": connessione (08),
# risorse esaurite (53), intervento dell'amministratore, per esempio spegnimento (57).
CLASSI_DI_CONNESSIONE = ("08", "53", "57")


def _di_connessione(e: Exception) -> bool:
    if isinstance(e, (pg8000.dbapi.InterfaceError, OSError)):
        return True
    dati = e.args[0] if e.args and isinstance(e.args[0], dict) else {}
    return str(dati.get("C", "")).startswith(CLASSI_DI_CONNESSIONE)


def _righe(cursore) -> list[dict]:
    """Le righe del risultato come dizionari {nome colonna: valore}."""
    nomi = [colonna[0] for colonna in cursore.description]
    return [dict(zip(nomi, riga)) for riga in cursore.fetchall()]


def _una(cursore) -> dict | None:
    righe = _righe(cursore)
    return righe[0] if righe else None


def _messaggio(riga: dict) -> MessaggioSalvato:
    return MessaggioSalvato(ruolo=riga["ruolo"], testo=riga["testo"], strumenti_usati=riga["strumenti_usati"],
                            data=riga["data"])


class _TurnoPostgres:
    def __init__(self, cursore, riga: dict, ora_domanda: datetime):
        self._cursore = cursore
        self.chat = Chat(id=riga["id"], titolo=riga["titolo"], creata=riga["creata"])
        self.cronologia = riga["cronologia"]
        self.riassunto = riga["riassunto"]
        self.ora_domanda = ora_domanda

    def salva(self, domanda, risposta, strumenti_usati, cronologia, riassunto, titolo):
        inserisci = (
            "INSERT INTO messaggi (chat_id, ruolo, testo, strumenti_usati, data) "
            "VALUES (%s, %s, %s, %s::jsonb, {}) RETURNING ruolo, testo, strumenti_usati, data"
        )
        c = self._cursore
        # La domanda porta l'ora presa dopo il blocco; la risposta l'ora del salvataggio
        # (clock_timestamp() = l'ora vera, now() sarebbe l'inizio della transazione).
        c.execute(inserisci.format("%s"), (self.chat.id, "utente", domanda, "[]", self.ora_domanda))
        d = _una(c)
        c.execute(inserisci.format("clock_timestamp()"),
                  (self.chat.id, "assistente", risposta, json.dumps(strumenti_usati, ensure_ascii=False)))
        r = _una(c)
        c.execute(
            "UPDATE chat SET cronologia = %s::jsonb, riassunto = %s, titolo = COALESCE(%s, titolo) WHERE id = %s",
            (json.dumps(cronologia, ensure_ascii=False), riassunto, titolo, self.chat.id),
        )
        return _messaggio(d), _messaggio(r)


class ArchivioPostgres:
    def __init__(self, parametri: ParametriDatabase):
        self.parametri = parametri

    # Una connessione = una transazione: alla fine conferma (commit), con un'eccezione annulla
    # (rollback); in ogni caso la chiude. I problemi di connessione diventano ErroreDatabase;
    # le altre eccezioni (per esempio l'agente che non risponde durante un turno) passano oltre.
    @contextmanager
    def _cursore(self) -> Iterator:
        conn = connetti(self.parametri)
        try:
            try:
                yield conn.cursor()
                conn.commit()
            except BaseException:
                try:
                    conn.rollback()
                except (pg8000.dbapi.InterfaceError, OSError):
                    pass  # connessione già caduta: il server annulla da solo la transazione
                raise
        except (pg8000.dbapi.Error, OSError) as e:
            if not _di_connessione(e):
                raise  # un errore SQL vero è un difetto del programma: non va nascosto
            raise ErroreDatabase(_testo_errore(e)) from None
        finally:
            try:
                conn.close()
            except (pg8000.dbapi.InterfaceError, OSError):
                pass

    def prepara(self) -> None:
        """Crea tabelle e indice se mancano (all'avvio del back-end)."""
        with self._cursore() as c:
            c.execute(SCHEMA)

    def crea(self, titolo):
        with self._cursore() as c:
            c.execute("INSERT INTO chat (titolo) VALUES (%s) RETURNING id, titolo, creata", (titolo,))
            riga = _una(c)
        return Chat(**riga)

    def elenca(self):
        with self._cursore() as c:
            c.execute(
                "SELECT c.id, c.titolo, c.creata, max(m.data) AS ultimo_messaggio "
                "FROM chat c LEFT JOIN messaggi m ON m.chat_id = c.id "
                "GROUP BY c.id "
                "ORDER BY COALESCE(max(m.data), c.creata) DESC, c.id DESC"
            )
            righe = _righe(c)
        return [VoceElenco(**riga) for riga in righe]

    def leggi(self, chat_id):
        with self._cursore() as c:
            c.execute("SELECT id, titolo, creata FROM chat WHERE id = %s", (chat_id,))
            riga = _una(c)
            if riga is None:
                return None
            c.execute(
                "SELECT ruolo, testo, strumenti_usati, data FROM messaggi WHERE chat_id = %s ORDER BY data, id",
                (chat_id,),
            )
            righe = _righe(c)
        return Chat(**riga), [_messaggio(r) for r in righe]

    def elimina(self, chat_id):
        with self._cursore() as c:
            c.execute("DELETE FROM chat WHERE id = %s RETURNING id", (chat_id,))
            riga = _una(c)
        return riga is not None

    @contextmanager
    def turno(self, chat_id):
        with self._cursore() as c:
            c.execute("SELECT id, titolo, creata, cronologia, riassunto FROM chat WHERE id = %s FOR UPDATE",
                      (chat_id,))
            riga = _una(c)
            if riga is None:
                yield None
                return
            # L'ora si chiede DOPO aver ottenuto il blocco, con una richiesta a parte.
            c.execute("SELECT clock_timestamp() AS ora")
            ora = _una(c)["ora"]
            yield _TurnoPostgres(c, riga, ora)
