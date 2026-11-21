"""Dati e oggetti finti per i test del RAG (lezione 7, esercizio 1)."""

# COSA C'È IN QUESTO FILE
#   CORPUS_PROVA  un piccolo "libro" con le stesse particolarità del file vero di Gutenberg:
#                 BOM, intestazione, righe RICETTE/APPENDICE, introduzioni di capitolo, un titolo
#                 generale senza ricette (MINESTRE), titoli finti in maiuscolo, un rimando
#                 spezzato a capo ("N." + "137. ..."), ingredienti rientrati, corsivi _così_.
#                 Cinque ricette (1-5) in tre capitoli; la 3 è lunga (più di 1200 caratteri).

import json
import math
import zlib

import httpx

CORPUS_PROVA = "﻿" + """The Project Gutenberg eBook of La scienza in cucina e l'arte di mangiar bene

This eBook is for the use of anyone anywhere in the United States and
most other parts of the world at no cost and with almost no restrictions.

*** START OF THE PROJECT GUTENBERG EBOOK LA SCIENZA IN CUCINA ***


PREFAZIONE

La cucina è una bricconcella; spesso e volentieri fa disperare.




RICETTE


BRODI, GELATINA E SUGHI

Il brodo è la base di molte vivande e merita qualche parola prima
delle ricette.

1. Brodo

Lo sa il popolo e il comune che per ottenere il brodo buono bisogna
mettere la carne ad acqua diaccia e far bollire la pentola adagino.

2. Gelatina

La gelatina si fa con zampa di vitello e si chiarifica con la chiara
d'uovo sbattuta.

  Zampa di vitello, una.
  Acqua, litri 2.


MINESTRE

Una volta si diceva che la minestra era la biada dell'uomo; oggi i
medici consigliano di mangiarne poca.


MINESTRE IN BRODO

3. Cappelletti all'uso di Romagna

Sono detti così per la loro forma a cappello. Ecco il modo più semplice
di farli perché riescano più delicati e gentili al palato di ognuno.

  Ricotta, grammi 180.
  Petto di cappone, mezzo.
  Parmigiano grattato, grammi 30.
  Uova, uno intero e un rosso.

Cuocete il petto di cappone nel burro, conditelo con sale e pepe e
tritatelo fine colla lunetta. Aggiungete la ricotta, il parmigiano e
le uova, mescolate bene e fate un impasto sodo che si possa lavorare
colle mani senza che si attacchi.

Chiudete il ripieno nella sfoglia tagliata a dischi e piegate i
cappelletti come si usa in Romagna; poi lasciateli asciugare un poco
sopra un tovagliolo infarinato prima di cuocerli nel brodo di cappone,
che è quello che fa al caso loro meglio di ogni altro.

Se vi piace un sapore più grasso potete legare il ripieno con un poco
di _balsamella_ fatta come quella descritta al N.
137. Mettete il composto in un luogo fresco e lasciatelo riposare
almeno un'ora prima di adoperarlo, così prenderà consistenza.

PASTA FROLLA

La sfoglia per i cappelletti non è una pasta frolla, ma una pasta
all'uovo tirata sottile col matterello; badate che non si secchi
mentre lavorate, coprendola con un canovaccio umido.

  UN AMMIRATORE

Un mangiatore moderato si contenta di un centinaio di cappelletti, ma
ho conosciuto chi ne mangiava quattrocento senza batter ciglio e poi
chiedeva il lesso; e si sa che il Natale in Romagna senza i cappelletti
non si concepisce, tanto sono cari alla gente di quella regione.


FRITTI

Il fritto vuole padella ampia e olio abbondante, e la frittura si
giudica dal colore dorato.

4. Pollo fritto

Tagliate il pollo a pezzi, infarinatelo e friggetelo nell'olio bollente
finché non prende un bel colore dorato.

5. Fritto di cervello

Il cervello si lessa, si taglia a pezzetti e si frigge nell'olio
dopo averlo passato nell'uovo e nel pangrattato.


APPENDICE

CUCINA PER GLI STOMACHI DEBOLI

227. Scaloppine ... p. 228.

  RICETTE

*** END OF THE PROJECT GUTENBERG EBOOK LA SCIENZA IN CUCINA ***
"""

INTRODUZIONE_FRITTI = "Il fritto vuole padella ampia e olio abbondante"


class EmbedderFinto:
    """Embedder deterministico al posto di LM Studio: un "sacco di parole" in pochi numeri.

    Ogni parola (in minuscolo, senza punteggiatura) accende una componente scelta con un hash
    stabile; il vettore è poi normalizzato. Testi con parole in comune risultano vicini, e la
    stessa frase dà sempre lo stesso vettore. `chiamate` registra i testi ricevuti.
    """

    def __init__(self, dimensione: int = 32, modello: str = "finto"):
        self.dimensione = dimensione
        self.modello = modello
        self.chiamate: list[list[str]] = []

    def vettore(self, testo: str) -> list[float]:
        valori = [0.0] * self.dimensione
        for parola in testo.lower().split():
            parola = parola.strip(".,;:!?'\"()«»")
            if parola:
                valori[zlib.crc32(parola.encode("utf-8")) % self.dimensione] += 1.0
        if not any(valori):
            valori[0] = 1.0
        norma = math.sqrt(sum(v * v for v in valori))
        return [v / norma for v in valori]

    def calcola(self, testi: list[str]) -> list[list[float]]:
        self.chiamate.append(list(testi))
        return [self.vettore(t) for t in testi]


class QdrantFinto:
    """Un Qdrant finto in memoria, che risponde agli stessi percorsi dell'API REST.

    Non è il "Qdrant in memoria" della libreria ufficiale (qdrant-client non si può usare su
    questo PC): è scritto qui, con lo stato in un dizionario. Si monta su httpx.MockTransport,
    quindi il client vero (rag/qdrant.py) gli parla come al server, senza rete. Registra le
    richieste ricevute in `richieste` (metodo, percorso, corpo JSON), così i test possono
    verificare che l'indice sul capitolo e il filtro durante la ricerca vengano davvero inviati.
    Le risposte hanno la stessa forma di quelle di Qdrant: {"result": ..., "status": "ok"}.
    """

    def __init__(self):
        self.collezioni: dict[str, dict] = {}
        self.richieste: list[tuple[str, str, dict | None]] = []

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._gestisci)

    @staticmethod
    def _ok(risultato) -> httpx.Response:
        return httpx.Response(200, json={"result": risultato, "status": "ok", "time": 0.0})

    @staticmethod
    def _errore(codice: int, messaggio: str) -> httpx.Response:
        return httpx.Response(codice, json={"status": {"error": messaggio}, "time": 0.0})

    @staticmethod
    def _rispetta(payload: dict, filtro: dict | None) -> bool:
        if not filtro:
            return True
        return all(payload.get(c["key"]) == c["match"]["value"] for c in filtro.get("must", []))

    def _gestisci(self, request: httpx.Request) -> httpx.Response:
        corpo = json.loads(request.content) if request.content else None
        percorso = request.url.path
        self.richieste.append((request.method, percorso, corpo))
        parti = percorso.strip("/").split("/")
        if len(parti) < 2 or parti[0] != "collections":
            return self._errore(404, "percorso sconosciuto")
        nome, resto = parti[1], "/".join(parti[2:])
        collezione = self.collezioni.get(nome)
        if request.method == "PUT" and resto == "":
            if collezione is not None:
                return self._errore(409, f"Wrong input: Collection `{nome}` already exists!")
            vettori = corpo["vectors"]
            assert vettori["distance"] == "Cosine"
            self.collezioni[nome] = {"dimensione": vettori["size"], "metadati": corpo.get("metadata") or {},
                                     "indici": {}, "punti": {}}
            return self._ok(True)
        if collezione is None:
            return self._errore(404, f"Not found: Collection `{nome}` doesn't exist!")
        punti = collezione["punti"]
        if request.method == "GET" and resto == "":
            config = {"params": {"vectors": {"size": collezione["dimensione"], "distance": "Cosine"}}}
            if collezione["metadati"]:
                config["metadata"] = collezione["metadati"]
            return self._ok({"status": "green", "points_count": len(punti), "config": config})
        if request.method == "PUT" and resto == "index":
            collezione["indici"][corpo["field_name"]] = corpo["field_schema"]
            return self._ok({"status": "completed"})
        if request.method == "PUT" and resto == "points":
            for p in corpo["points"]:
                if len(p["vector"]) != collezione["dimensione"]:
                    return self._errore(400, f"Wrong input: Vector dimension error: expected dim: "
                                             f"{collezione['dimensione']}, got {len(p['vector'])}")
            for p in corpo["points"]:
                punti[p["id"]] = (p["vector"], p["payload"])
            return self._ok({"status": "completed"})
        if request.method == "POST" and resto == "points/query":
            vettore = corpo["query"]
            if len(vettore) != collezione["dimensione"]:
                return self._errore(400, "Wrong input: Vector dimension error")
            trovati = [
                {"id": i, "version": 0, "score": _coseno(vettore, v), "payload": dict(pl)}
                for i, (v, pl) in punti.items() if self._rispetta(pl, corpo.get("filter"))
            ]
            trovati.sort(key=lambda t: t["score"], reverse=True)
            return self._ok({"points": trovati[:corpo["limit"]]})
        if request.method == "POST" and resto == "points/scroll":
            ids = sorted(punti)
            inizio = ids.index(corpo["offset"]) if corpo.get("offset") is not None else 0
            pagina = ids[inizio:inizio + corpo["limit"]]
            prossimo = ids[inizio + corpo["limit"]] if inizio + corpo["limit"] < len(ids) else None
            campi = corpo.get("with_payload")
            if isinstance(campi, list):
                elenco = [{"id": i, "payload": {k: v for k, v in punti[i][1].items() if k in campi}}
                          for i in pagina]
            else:
                elenco = [{"id": i} for i in pagina]
            return self._ok({"points": elenco, "next_page_offset": prossimo})
        if request.method == "POST" and resto == "points/delete":
            for i in corpo["points"]:
                punti.pop(i, None)
            return self._ok({"status": "completed"})
        if request.method == "POST" and resto == "points/count":
            return self._ok({"count": sum(1 for _, pl in punti.values() if self._rispetta(pl, corpo.get("filter")))})
        if request.method == "POST" and resto == "points/payload":
            assenti = [i for i in corpo["points"] if i not in punti]
            if assenti:
                return self._errore(404, f"Not found: No point with id {assenti[0]} found")
            for i in corpo["points"]:
                vettore, payload = punti[i]
                punti[i] = (vettore, {**payload, **corpo["payload"]})
            return self._ok({"status": "completed"})
        if request.method == "POST" and resto == "facet":
            if corpo["key"] not in collezione["indici"]:
                return self._errore(400, f"Bad request: Index required but not found for \"{corpo['key']}\" "
                                         "of one of the following types: [keyword]")
            conteggi: dict[str, int] = {}
            for _, payload in punti.values():
                if corpo["key"] in payload:
                    conteggi[payload[corpo["key"]]] = conteggi.get(payload[corpo["key"]], 0) + 1
            hits = [{"value": v, "count": n} for v, n in sorted(conteggi.items(), key=lambda x: -x[1])]
            return self._ok({"hits": hits[:corpo.get("limit", 10)]})
        return self._errore(404, f"percorso sconosciuto: {request.method} {percorso}")


def _coseno(a: list[float], b: list[float]) -> float:
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return sum(x * y for x, y in zip(a, b)) / (na * nb) if na and nb else 0.0


def client_finto(qdrant: QdrantFinto):
    """Il client vero di rag/qdrant.py collegato al Qdrant finto."""
    from rag.qdrant import ClientQdrant

    return ClientQdrant("http://qdrant-finto:6333", client=httpx.Client(transport=qdrant.transport()))
