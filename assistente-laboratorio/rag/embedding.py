"""Embedding: i testi diventano vettori, calcolati da LM Studio (lezione 7, pipeline fase 6)."""

# COSA FA QUESTO FILE
# Chiede a LM Studio, con l'endpoint compatibile con OpenAI POST {LM_BASE_URL}/embeddings, i
# vettori di una lista di testi, con il modello scritto in EMBEDDING_MODELLO. Lo stesso oggetto
# serve all'ingestion (i chunk) e alla ricerca (la domanda): così documenti e domande passano
# sempre dallo stesso modello con la stessa configurazione, come chiede il PDF.
# I testi vanno al modello così come sono, senza prefissi (vedi docs/retrieval.md).
# I testi si mandano a lotti (LOTTO alla volta): una sola richiesta con 1000 chunk sarebbe
# lenta e rischierebbe il timeout.

import httpx

LOTTO = 32
TIMEOUT = 60.0


class ErroreEmbedding(Exception):
    """LM Studio ha risposto con un errore (es. modello non caricato) o con dati inattesi."""


class LMStudioNonRaggiungibile(ErroreEmbedding):
    """LM Studio non risponde (spento, indirizzo sbagliato)."""


class EmbedderLMStudio:
    def __init__(self, base_url: str, modello: str, client: httpx.Client | None = None):
        self.url = base_url.rstrip("/") + "/embeddings"
        self.modello = modello
        self._client = client or httpx.Client(timeout=TIMEOUT)

    def _lotto(self, testi: list[str]) -> list[list[float]]:
        try:
            risposta = self._client.post(self.url, json={"model": self.modello, "input": testi})
        except httpx.TransportError as e:
            raise LMStudioNonRaggiungibile(
                f"LM Studio non raggiungibile: controllare LM_BASE_URL e il modello di embedding caricato ({e})"
            ) from None
        if risposta.status_code != 200:
            try:
                dettaglio = risposta.json()["error"]
                dettaglio = dettaglio.get("message", dettaglio) if isinstance(dettaglio, dict) else dettaglio
            except (ValueError, KeyError, TypeError):
                dettaglio = risposta.text[:200]
            raise ErroreEmbedding(
                f"LM Studio ha risposto {risposta.status_code} per il modello di embedding {self.modello!r}: "
                f"{dettaglio} (il modello è caricato in LM Studio? EMBEDDING_MODELLO è scritto giusto?)"
            )
        try:
            dati = sorted(risposta.json()["data"], key=lambda d: d["index"])
            vettori = [d["embedding"] for d in dati]
        except (ValueError, KeyError, TypeError):
            raise ErroreEmbedding("risposta di LM Studio senza i vettori attesi") from None
        if len(vettori) != len(testi):
            raise ErroreEmbedding(f"LM Studio ha restituito {len(vettori)} vettori per {len(testi)} testi")
        return vettori

    def calcola(self, testi: list[str]) -> list[list[float]]:
        """Un vettore per testo, nello stesso ordine dei testi."""
        vettori: list[list[float]] = []
        for inizio in range(0, len(testi), LOTTO):
            vettori.extend(self._lotto(testi[inizio:inizio + LOTTO]))
        return vettori
