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
# Codici di uscita: 0 ok, 2 configurazione non valida, 3 Qdrant o LM Studio non raggiungibili,
# 4 errore sui dati (corpus non valido, cambio bloccato, errore di LM Studio o di Qdrant).

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


@dataclass(frozen=True)
class EsitoIngestion:
    ricette: int
    chunk: int
    punti_prima: int
    punti_dopo: int
    eliminati: int


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


def esegui_ingestion(config: ConfigurazioneRag, embedder, qdrant: ClientQdrant,
                     ricette_attese: int = RICETTE_ATTESE, lotto_embedding: int = LOTTO_EMBEDDING) -> EsitoIngestion:
    # 1-3. Caricare, pulire, dividere in ricette e controllare la numerazione.
    ricette = estrai_ricette(leggi_file(config.corpus_file))
    controlla_numerazione(ricette, ricette_attese)
    log.info("ricette lette: %d da %s", len(ricette), config.corpus_file)

    # 4-5. Chunk e payload.
    punti_senza_vettore: list[tuple[str, dict]] = []
    for ricetta in ricette:
        for posizione, testo in enumerate(dividi(ricetta.testo, config.strategia, config.dimensione, config.overlap)):
            payload = {
                "documento_id": ricetta.documento_id,
                "numero": ricetta.numero,
                "titolo": ricetta.titolo,
                "capitolo": ricetta.capitolo,
                "posizione": posizione,
                "testo": testo,
                "fonte": FONTE,
            }
            punti_senza_vettore.append((id_punto(ricetta.documento_id, posizione), payload))
    log.info("chunk prodotti: %d (strategia %s, dimensione %d, overlap %d)",
             len(punti_senza_vettore), config.strategia, config.dimensione, config.overlap)

    # Prima di calcolare gli embedding: la collezione esistente è compatibile con il modello?
    info = qdrant.info_collezione(config.collezione)
    if info is not None:
        controlla_compatibilita(info, embedder.modello, None)

    # 6. Embedding di TUTTI i chunk, prima di scrivere qualsiasi cosa.
    testi = [payload["testo"] for _, payload in punti_senza_vettore]
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
        qdrant.crea_indice(config.collezione, "capitolo")
        log.info("creata la collezione %s (coseno, dimensione %d, modello %s)",
                 config.collezione, dimensione, embedder.modello)

    # 7. Salvare: upsert per ID stabile, poi pulizia dei punti avanzati.
    punti_prima = qdrant.conta(config.collezione)
    punti = [Punto(pid, vettore, payload) for (pid, payload), vettore in zip(punti_senza_vettore, vettori)]
    for inizio in range(0, len(punti), LOTTO_UPSERT):
        qdrant.upsert(config.collezione, punti[inizio:inizio + LOTTO_UPSERT])
    avanzati = sorted(qdrant.ids_presenti(config.collezione) - {p.id for p in punti})
    qdrant.elimina(config.collezione, avanzati)
    punti_dopo = qdrant.conta(config.collezione)
    return EsitoIngestion(len(ricette), len(punti), punti_prima, punti_dopo, len(avanzati))


def crea_embedder(config: ConfigurazioneRag) -> EmbedderLMStudio:
    return EmbedderLMStudio(config.lm_base_url, config.embedding_modello)


def crea_qdrant(config: ConfigurazioneRag) -> ClientQdrant:
    return ClientQdrant(config.qdrant_url)


def main() -> int:
    try:
        config = carica_configurazione(leggi_ambiente(Path.cwd()), Path.cwd())
    except ErroreConfigurazioneRag as e:
        print(f"Configurazione non valida: {e}", file=sys.stderr)
        return 2
    configura_log(config.log_level)
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
        f"ricette lette: {esito.ricette}",
        f"chunk prodotti: {esito.chunk}",
        f"punti prima: {esito.punti_prima}",
        f"punti eliminati (avanzati): {esito.eliminati}",
        f"punti dopo: {esito.punti_dopo}",
    ]
    for riga in righe:
        log.info(riga)
        print(riga)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
