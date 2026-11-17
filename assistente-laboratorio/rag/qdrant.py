"""Collegamento a Qdrant tramite la sua API REST (lezione 7, pipeline fase 7 e ricerca)."""

# COSA FA QUESTO FILE
# Qdrant è il database dei vettori: per ogni chunk conserva un "punto" (ID + vettore + payload,
# cioè testo e metadati) e sa trovare i punti più vicini a un vettore.
# Il client ufficiale (qdrant-client) su questo PC non si importa: richiede numpy e Smart App
# Control di Windows ne blocca una DLL. Per questo si parla con Qdrant direttamente con httpx,
# attraverso l'API REST (la stessa che usa il client ufficiale), esponendo SOLO le operazioni
# che servono:
#   info_collezione  GET  /collections/{c}                (dimensione e metadati, o None)
#   crea_collezione  PUT  /collections/{c}                (distanza coseno + metadati)
#   crea_indice      PUT  /collections/{c}/index          (indice su un campo: keyword o bool)
#   upsert           PUT  /collections/{c}/points         (inserisce o sostituisce per ID)
#   imposta_payload  POST /collections/{c}/points/payload (aggiunge campi al payload, vettori intatti)
#   cerca            POST /collections/{c}/points/query   (i più vicini, con filtro facoltativo)
#   ids_presenti     POST /collections/{c}/points/scroll  (tutti gli ID, a pagine)
#   testi_presenti   POST /collections/{c}/points/scroll  (ID e testo di tutti i punti, a pagine)
#   elimina          POST /collections/{c}/points/delete  (per ID)
#   conta            POST /collections/{c}/points/count   (conteggio esatto, filtro facoltativo)
#   capitoli         POST /collections/{c}/facet          (valori distinti di "capitolo")
# Errori di rete -> QdrantNonRaggiungibile; risposte di errore -> ErroreQdrant con il motivo.

from dataclasses import dataclass

import httpx

TIMEOUT = 10.0
PAGINA_SCROLL = 1000
LOTTO_PAYLOAD = 256  # ID per ogni richiesta di imposta_payload


class ErroreQdrant(Exception):
    """Qdrant ha risposto con un errore."""


class QdrantNonRaggiungibile(ErroreQdrant):
    """Qdrant non risponde (container spento o indirizzo sbagliato)."""


@dataclass(frozen=True)
class InfoCollezione:
    dimensione: int  # lunghezza dei vettori
    metadati: dict  # es. {"embedding_modello": ..., "embedding_dimensione": ...}; {} se assenti


@dataclass(frozen=True)
class Punto:
    id: str  # UUID in forma di testo
    vettore: list[float]
    payload: dict


@dataclass(frozen=True)
class Trovato:
    score: float  # similarità del coseno: più alto = più vicino
    payload: dict


class ClientQdrant:
    def __init__(self, url: str, client: httpx.Client | None = None):
        self.url = url.rstrip("/")
        self._client = client or httpx.Client(timeout=TIMEOUT)

    def _chiama(self, metodo: str, percorso: str, corpo: dict | None = None, ammessi=()) -> httpx.Response:
        try:
            risposta = self._client.request(metodo, self.url + percorso, json=corpo)
        except httpx.TransportError as e:
            raise QdrantNonRaggiungibile(
                f"Qdrant non raggiungibile su {self.url}: controllare docker compose ps e QDRANT_URL ({e})"
            ) from None
        if risposta.status_code not in ammessi and not risposta.is_success:
            try:
                motivo = risposta.json()["status"]["error"]
            except (ValueError, KeyError, TypeError):
                motivo = risposta.text[:200]
            raise ErroreQdrant(f"Qdrant ha risposto {risposta.status_code} a {metodo} {percorso}: {motivo}")
        return risposta

    def _risultato(self, metodo: str, percorso: str, corpo: dict | None = None):
        return self._chiama(metodo, percorso, corpo).json()["result"]

    def info_collezione(self, nome: str) -> InfoCollezione | None:
        risposta = self._chiama("GET", f"/collections/{nome}", ammessi=(404,))
        if risposta.status_code == 404:
            return None
        risultato = risposta.json()["result"]
        config = risultato["config"]
        metadati = config.get("metadata") or risultato.get("metadata") or {}
        return InfoCollezione(dimensione=config["params"]["vectors"]["size"], metadati=dict(metadati))

    def crea_collezione(self, nome: str, dimensione: int, metadati: dict) -> None:
        corpo = {"vectors": {"size": dimensione, "distance": "Cosine"}, "metadata": metadati}
        self._chiama("PUT", f"/collections/{nome}", corpo)

    def crea_indice(self, nome: str, campo: str, schema: str = "keyword") -> None:
        self._chiama("PUT", f"/collections/{nome}/index?wait=true", {"field_name": campo, "field_schema": schema})

    def upsert(self, nome: str, punti: list[Punto]) -> None:
        corpo = {"points": [{"id": p.id, "vector": p.vettore, "payload": p.payload} for p in punti]}
        self._chiama("PUT", f"/collections/{nome}/points?wait=true", corpo)

    def imposta_payload(self, nome: str, payload: dict, ids: list[str]) -> None:
        """Aggiunge (o sostituisce) i campi di `payload` sui punti indicati, senza toccare i vettori."""
        for inizio in range(0, len(ids), LOTTO_PAYLOAD):
            corpo = {"payload": payload, "points": ids[inizio:inizio + LOTTO_PAYLOAD]}
            self._chiama("POST", f"/collections/{nome}/points/payload?wait=true", corpo)

    def cerca(self, nome: str, vettore: list[float], limite: int, capitolo: str | None = None,
              solo_dosi: bool = False) -> list[Trovato]:
        corpo: dict = {"query": vettore, "limit": limite, "with_payload": True}
        # Filtri applicati DURANTE la ricerca (non dopo): Qdrant cerca solo tra i punti che li
        # rispettano tutti ("must"), e restituisce comunque fino a `limite` risultati.
        condizioni = []
        if capitolo is not None:
            condizioni.append({"key": "capitolo", "match": {"value": capitolo}})
        if solo_dosi:
            condizioni.append({"key": "contiene_dosi", "match": {"value": True}})
        if condizioni:
            corpo["filter"] = {"must": condizioni}
        punti = self._risultato("POST", f"/collections/{nome}/points/query", corpo)["points"]
        return [Trovato(score=p["score"], payload=p.get("payload") or {}) for p in punti]

    def ids_presenti(self, nome: str) -> set[str]:
        ids: set[str] = set()
        corpo: dict = {"limit": PAGINA_SCROLL, "with_payload": False, "with_vector": False}
        while True:
            risultato = self._risultato("POST", f"/collections/{nome}/points/scroll", corpo)
            ids.update(str(p["id"]) for p in risultato["points"])
            if risultato.get("next_page_offset") is None:
                return ids
            corpo = {**corpo, "offset": risultato["next_page_offset"]}

    def testi_presenti(self, nome: str) -> dict[str, str]:
        """ID e testo di tutti i punti (scroll a pagine, senza vettori)."""
        testi: dict[str, str] = {}
        corpo: dict = {"limit": PAGINA_SCROLL, "with_payload": ["testo"], "with_vector": False}
        while True:
            risultato = self._risultato("POST", f"/collections/{nome}/points/scroll", corpo)
            for p in risultato["points"]:
                testi[str(p["id"])] = (p.get("payload") or {}).get("testo")
            if risultato.get("next_page_offset") is None:
                return testi
            corpo = {**corpo, "offset": risultato["next_page_offset"]}

    def elimina(self, nome: str, ids: list[str]) -> None:
        if ids:
            self._chiama("POST", f"/collections/{nome}/points/delete?wait=true", {"points": ids})

    def conta(self, nome: str, filtro: dict | None = None) -> int:
        corpo: dict = {"exact": True}
        if filtro is not None:
            corpo["filter"] = filtro
        return self._risultato("POST", f"/collections/{nome}/points/count", corpo)["count"]

    def capitoli(self, nome: str) -> list[str]:
        corpo = {"key": "capitolo", "limit": 100, "exact": True}
        hits = self._risultato("POST", f"/collections/{nome}/facet", corpo)["hits"]
        return sorted(h["value"] for h in hits)
