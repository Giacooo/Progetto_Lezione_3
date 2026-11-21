"""Ingestion: costruisce l'indice del libro in Qdrant (lezione 7).  python -m rag.ingestion"""

# COSA FA QUESTO FILE
# È lo SCRIPT SEPARATO di cui parla il PDF (pag. 11): si esegue quando il corpus cambia, non è
# uno strumento dell'agente. Fa tutta la pipeline:
#   caricare -> pulire -> dividere in ricette -> chunk -> payload -> embedding -> salvare.
#
# Ripetibile (pag. 18, strategia A): ogni chunk ha un ID STABILE, ricavato da ricetta e
# posizione (UUID versione 5): rieseguendo l'ingestion lo stesso chunk sostituisce il suo punto
# (upsert) invece di aggiungerne un altro. Poi si eliminano i punti "avanzati" (chunk che non
# esistono più, per esempio dopo aver cambiato la dimensione): la collezione resta coerente.
#
# Il modello di embedding è registrato nei metadati della collezione. Se la collezione esiste
# già con un altro modello (o un'altra dimensione dei vettori, o senza metadati), l'ingestion
# si ferma senza toccare niente ("cambio bloccato"): vettori di modelli diversi non si possono
# confrontare tra loro.
#
# Ordine scelto per non lasciare mai la collezione a metà: prima si controlla tutto e si
# calcolano TUTTI gli embedding; solo dopo si crea la collezione e si scrivono i punti.
#
# Modifica A: ogni punto ha il campo "contiene_dosi" (il chunk contiene almeno una riga intera di
# un elenco di ingredienti, vedi rag/corpus.py), con un indice bool per il filtro. Per dare il
# campo ai punti già presenti SENZA ricalcolare gli embedding:  python -m rag.ingestion --solo-payload
# rilegge il libro, ricalcola chunk e payload e scrive in Qdrant solo il campo ("set payload"):
# nessuna chiamata a LM Studio, nessun punto aggiunto o tolto. Si ferma se gli ID calcolati non
# sono esattamente quelli della collezione (chunking cambiato: serve l'ingestion completa).
#
# Modifica B: un chunk "di mezzo" di una ricetta lunga spesso non nomina il piatto. Per questo il
# testo passato all'EMBEDDER ha davanti titolo e capitolo (testo_da_indicizzare); il payload
# "testo" resta il chunk originale, quindi la ricerca e --solo-payload non cambiano. Gli ID
# dipendono da ricetta e posizione, non dal testo: l'ingestion completa sostituisce i vettori
# degli stessi punti (nessun punto in più, collezione non ricreata) e, con lo stesso modello,
# il "cambio bloccato" non scatta.
#
# Codici di uscita: 0 ok, 2 configurazione non valida, 3 Qdrant o LM Studio non raggiungibili,
# 4 errore sui dati (corpus non valido, cambio bloccato, errore di LM Studio o di Qdrant,
# --solo-payload non applicabile).

import argparse
import logging
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

from rag.chunking import dividi
from rag.configurazione import ConfigurazioneRag, ErroreConfigurazioneRag, carica_configurazione, configura_log, leggi_ambiente
from rag.corpus import ErroreCorpus, controlla_numerazione, estrai_ricette, leggi_file
from rag.embedding import EmbedderLMStudio, ErroreEmbedding, LMStudioNonRaggiungibile
from rag.qdrant import ClientQdrant, ErroreQdrant, InfoCollezione, Punto, QdrantNonRaggiungibile

log = logging.getLogger(__name__)

FONTE = "Artusi, La scienza in cucina e l'arte di mangiar bene (1891), Project Gutenberg n. 59047"
RICETTE_ATTESE = 790
LOTTO_EMBEDDING = 64  # testi passati all'embedder per volta (per mostrare l'avanzamento nel log)
LOTTO_UPSERT = 256  # punti inviati a Qdrant per richiesta
# "Spazio dei nomi" fisso degli ID: con lo stesso testo di partenza, uuid5 dà sempre lo stesso ID.
SPAZIO_ID = uuid.UUID("6f1d2c3e-7a7b-5c1e-9a57-a1e1a5c0c0a7")


class CambioBloccato(Exception):
    """La collezione esiste con un altro modello di embedding (o un'altra dimensione)."""


class PayloadNonAggiornabile(Exception):
    """--solo-payload non si può applicare: collezione assente o chunk diversi da quelli salvati."""


@dataclass(frozen=True)
class EsitoIngestion:
    ricette: int
    chunk: int
    punti_prima: int
    punti_dopo: int
    eliminati: int


@dataclass(frozen=True)
class EsitoPayload:
    punti: int  # punti aggiornati
    con_dosi: int
    senza_dosi: int
    punti_prima: int
    punti_dopo: int


def contiene_dosi(testo_chunk: str, righe_dosi: tuple[str, ...]) -> bool:
    """Vero se almeno una riga INTERA del chunk è una riga di un elenco di ingredienti.

    Un pezzo di riga portato dall'overlap all'inizio del chunk successivo non conta.
    """
    dosi = set(righe_dosi)
    return any(riga in dosi for riga in testo_chunk.split("\n"))


def crea_indici(qdrant: ClientQdrant, collezione: str) -> None:
    """Indici sul payload, chiesti a ogni esecuzione: su un indice già esistente è innocuo."""
    qdrant.crea_indice(collezione, "capitolo")
    qdrant.crea_indice(collezione, "contiene_dosi", "bool")


def testo_da_indicizzare(titolo: str, capitolo: str, testo: str) -> str:
    """Il testo che va all'embedder: titolo e capitolo della ricetta, poi il chunk originale."""
    return f"Ricetta: {titolo}\nCapitolo: {capitolo}\n\n{testo}"


def id_punto(documento_id: str, posizione: int) -> str:
    """ID stabile del chunk: stesso documento e stessa posizione -> sempre lo stesso ID."""
    return str(uuid.uuid5(SPAZIO_ID, f"{documento_id}#{posizione}"))


def controlla_compatibilita(info: InfoCollezione, modello: str, dimensione: int | None) -> None:
    """Ferma tutto se la collezione è stata creata con un altro modello o un'altra dimensione."""
    registrato = info.metadati.get("embedding_modello")
    if registrato is None:
        raise CambioBloccato(
            "la collezione esiste ma non indica con quale modello di embedding è stata creata: "
            "cambio bloccato. Usare un'altra QDRANT_COLLEZIONE.")
    if registrato != modello:
        raise CambioBloccato(
            f"la collezione è stata creata con il modello {registrato!r}, ma EMBEDDING_MODELLO è {modello!r}: "
            "cambio bloccato. Rimettere il modello registrato oppure usare un'altra QDRANT_COLLEZIONE.")
    if dimensione is not None and dimensione != info.dimensione:
        raise CambioBloccato(
            f"il modello {modello!r} produce vettori di dimensione {dimensione}, la collezione ha dimensione "
            f"{info.dimensione}: cambio bloccato. Usare un'altra QDRANT_COLLEZIONE.")


def prepara_punti(config: ConfigurazioneRag, ricette_attese: int) -> tuple[int, list[tuple[str, dict]]]:
    """Passi 1-5: dal libro alle coppie (ID stabile, payload). Restituisce anche il numero di ricette."""
    # 1-3. Caricare, pulire, dividere in ricette e controllare la numerazione.
    ricette = estrai_ricette(leggi_file(config.corpus_file))
    controlla_numerazione(ricette, ricette_attese)
    log.info("ricette lette: %d da %s", len(ricette), config.corpus_file)

    # 4-5. Chunk e payload.
    punti_senza_vettore: list[tuple[str, dict]] = []
    for ricetta in ricette:
        chunk = dividi(ricetta.testo, config.strategia, config.dimensione, config.overlap)
        if not chunk:
            log.warning("ricetta %d (%s): nessun chunk (testo vuoto), non sarà cercabile", ricetta.numero, ricetta.titolo)
        for posizione, testo in enumerate(chunk):
            payload = {
                "documento_id": ricetta.documento_id,
                "numero": ricetta.numero,
                "titolo": ricetta.titolo,
                "capitolo": ricetta.capitolo,
                "posizione": posizione,
                "testo": testo,
                "fonte": FONTE,
                "contiene_dosi": contiene_dosi(testo, ricetta.righe_dosi),
            }
            punti_senza_vettore.append((id_punto(ricetta.documento_id, posizione), payload))
    log.info("chunk prodotti: %d (strategia %s, dimensione %d, overlap %d)",
             len(punti_senza_vettore), config.strategia, config.dimensione, config.overlap)
    return len(ricette), punti_senza_vettore


def esegui_ingestion(config: ConfigurazioneRag, embedder, qdrant: ClientQdrant,
                     ricette_attese: int = RICETTE_ATTESE, lotto_embedding: int = LOTTO_EMBEDDING) -> EsitoIngestion:
    ricette, punti_senza_vettore = prepara_punti(config, ricette_attese)

    # Prima di calcolare gli embedding: la collezione esistente è compatibile con il modello?
    info = qdrant.info_collezione(config.collezione)
    if info is not None:
        controlla_compatibilita(info, embedder.modello, None)

    # 6. Embedding di TUTTI i chunk, prima di scrivere qualsiasi cosa. Modifica B: all'embedder va
    # il chunk con davanti titolo e capitolo (il nome è cercato nel modulo a ogni chiamata, così i
    # test possono sostituirlo per simulare una collezione costruita prima della modifica).
    testi = [testo_da_indicizzare(p["titolo"], p["capitolo"], p["testo"]) for _, p in punti_senza_vettore]
    vettori: list[list[float]] = []
    for inizio in range(0, len(testi), lotto_embedding):
        vettori.extend(embedder.calcola(testi[inizio:inizio + lotto_embedding]))
        log.info("embedding: %d/%d", len(vettori), len(testi))
    dimensione = len(vettori[0])
    if info is not None:
        controlla_compatibilita(info, embedder.modello, dimensione)
    else:
        metadati = {"embedding_modello": embedder.modello, "embedding_dimensione": dimensione}
        qdrant.crea_collezione(config.collezione, dimensione, metadati)
        log.info("creata la collezione %s (coseno, dimensione %d, modello %s)",
                 config.collezione, dimensione, embedder.modello)
    # Indici su capitolo e contiene_dosi (filtri ed elenco dei capitoli), chiesti a ogni ingestion:
    # se una volta la loro creazione fosse fallita, questa li ricrea.
    crea_indici(qdrant, config.collezione)

    # 7. Salvare: upsert per ID stabile, poi pulizia dei punti avanzati.
    punti_prima = qdrant.conta(config.collezione)
    punti = [Punto(pid, vettore, payload) for (pid, payload), vettore in zip(punti_senza_vettore, vettori)]
    for inizio in range(0, len(punti), LOTTO_UPSERT):
        qdrant.upsert(config.collezione, punti[inizio:inizio + LOTTO_UPSERT])
    avanzati = sorted(qdrant.ids_presenti(config.collezione) - {p.id for p in punti})
    qdrant.elimina(config.collezione, avanzati)
    punti_dopo = qdrant.conta(config.collezione)
    return EsitoIngestion(ricette, len(punti), punti_prima, punti_dopo, len(avanzati))


def aggiorna_payload(config: ConfigurazioneRag, qdrant: ClientQdrant,
                     ricette_attese: int = RICETTE_ATTESE) -> EsitoPayload:
    """--solo-payload: scrive contiene_dosi sui punti esistenti, senza embedding né nuovi punti."""
    _, punti_senza_vettore = prepara_punti(config, ricette_attese)
    info = qdrant.info_collezione(config.collezione)
    if info is None:
        raise PayloadNonAggiornabile(
            f"la collezione {config.collezione!r} non esiste: eseguire prima l'ingestion completa "
            "(python -m rag.ingestion).")
    controlla_compatibilita(info, config.embedding_modello, None)
    # Stessi chunk = stessi ID E stesso testo (l'ID dipende solo da ricetta e posizione: con un
    # overlap appena diverso gli ID restano uguali ma i testi no).
    calcolati = {pid: payload["testo"] for pid, payload in punti_senza_vettore}
    presenti = qdrant.testi_presenti(config.collezione)
    if calcolati != presenti:
        diversi = sum(1 for pid in calcolati.keys() & presenti.keys() if calcolati[pid] != presenti[pid])
        raise PayloadNonAggiornabile(
            f"i chunk calcolati ({len(calcolati)}) non sono quelli della collezione ({len(presenti)} punti: "
            f"{len(presenti.keys() - calcolati.keys())} non più prodotti, {len(calcolati.keys() - presenti.keys())} "
            f"nuovi, {diversi} con testo diverso): il chunking è cambiato, eseguire l'ingestion completa "
            "(python -m rag.ingestion).")
    punti_prima = len(presenti)
    crea_indici(qdrant, config.collezione)
    con = [pid for pid, payload in punti_senza_vettore if payload["contiene_dosi"]]
    senza = [pid for pid, payload in punti_senza_vettore if not payload["contiene_dosi"]]
    qdrant.imposta_payload(config.collezione, {"contiene_dosi": True}, con)
    qdrant.imposta_payload(config.collezione, {"contiene_dosi": False}, senza)
    log.info("contiene_dosi aggiornato su %d punti (%d con dosi)", len(punti_senza_vettore), len(con))
    return EsitoPayload(len(punti_senza_vettore), len(con), len(senza), punti_prima, qdrant.conta(config.collezione))


def crea_embedder(config: ConfigurazioneRag) -> EmbedderLMStudio:
    return EmbedderLMStudio(config.lm_base_url, config.embedding_modello)


def crea_qdrant(config: ConfigurazioneRag) -> ClientQdrant:
    return ClientQdrant(config.qdrant_url)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m rag.ingestion",
                                     description="Costruisce l'indice del libro di Artusi in Qdrant.")
    parser.add_argument("--solo-payload", action="store_true",
                        help="aggiorna solo il campo contiene_dosi dei punti esistenti (niente embedding)")
    argomenti = parser.parse_args([] if argv is None else argv)
    try:
        config = carica_configurazione(leggi_ambiente(Path.cwd()), Path.cwd())
    except ErroreConfigurazioneRag as e:
        print(f"Configurazione non valida: {e}", file=sys.stderr)
        return 2
    configura_log(config.log_level)
    if argomenti.solo_payload:
        return _main_solo_payload(config)
    try:
        esito = esegui_ingestion(config, crea_embedder(config), crea_qdrant(config), RICETTE_ATTESE)
    except (QdrantNonRaggiungibile, LMStudioNonRaggiungibile) as e:
        print(str(e), file=sys.stderr)
        return 3
    except (ErroreCorpus, CambioBloccato, ErroreEmbedding, ErroreQdrant) as e:
        print(f"Ingestion fermata: {e}", file=sys.stderr)
        return 4
    righe = [
        f"modello di embedding: {config.embedding_modello}",
        f"collezione: {config.collezione}",
        f"chunking: {config.strategia}, dimensione {config.dimensione}, overlap {config.overlap}",
        "testo indicizzato: titolo e capitolo + chunk (payload con il testo originale)",
        f"ricette lette: {esito.ricette}",
        f"chunk prodotti: {esito.chunk}",
        f"punti prima: {esito.punti_prima}",
        f"punti eliminati (avanzati): {esito.eliminati}",
        f"punti dopo: {esito.punti_dopo}",
    ]
    _stampa(righe)
    return 0


def _main_solo_payload(config: ConfigurazioneRag) -> int:
    try:
        esito = aggiorna_payload(config, crea_qdrant(config), RICETTE_ATTESE)
    except QdrantNonRaggiungibile as e:
        print(str(e), file=sys.stderr)
        return 3
    except (ErroreCorpus, CambioBloccato, PayloadNonAggiornabile, ErroreQdrant) as e:
        print(f"Aggiornamento del payload fermato: {e}", file=sys.stderr)
        return 4
    _stampa([
        f"modello di embedding: {config.embedding_modello} (nessun embedding ricalcolato)",
        f"collezione: {config.collezione}",
        f"punti aggiornati: {esito.punti}",
        f"con dosi: {esito.con_dosi}",
        f"senza dosi: {esito.senza_dosi}",
        f"punti prima: {esito.punti_prima}",
        f"punti dopo: {esito.punti_dopo}",
    ])
    return 0


def _stampa(righe: list[str]) -> None:
    for riga in righe:
        log.info(riga)
        print(riga)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
