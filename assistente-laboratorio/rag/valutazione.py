"""Valutazione della ricerca con domande e fonte attesa (lezione 7).  python -m rag.valutazione"""

# COSA FA QUESTO FILE
# Misura la ricerca invece di giudicarla "a occhio" (PDF, pag. 21-22): per ogni domanda di
# rag/domande.json si sa quale ricetta (o quali) contiene la risposta; si esegue la ricerca con
# k = 5 e si guarda IN CHE POSIZIONE compare il primo chunk di una ricetta attesa e con quale
# score. Le domande senza risposta nel libro (lista vuota) mostrano solo lo score migliore:
# serve a vedere che la ricerca restituisce comunque qualcosa, anche quando non dovrebbe.
# Il risultato è una tabella Markdown, da copiare in docs/retrieval.md; stessi indice e domande
# danno la stessa tabella. In fondo: "Fonte attesa trovata in X casi su Y".
# Codici di uscita come la ricerca: 0, 2 (configurazione), 3 (servizi), 4 (dati).

import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from rag.configurazione import ConfigurazioneRag, ErroreConfigurazioneRag, carica_configurazione, configura_log, leggi_ambiente
from rag.embedding import ErroreEmbedding, LMStudioNonRaggiungibile
from rag.ingestion import CambioBloccato, crea_embedder, crea_qdrant
from rag.qdrant import ErroreQdrant, QdrantNonRaggiungibile
from rag.ricerca import ErroreRicerca, Risultato, cerca

K_VALUTAZIONE = 5
FILE_DOMANDE = Path(__file__).resolve().parent / "domande.json"
TRATTINO = "—"


@dataclass(frozen=True)
class Domanda:
    testo: str
    attese: list[int]  # numeri delle ricette che contengono la risposta; [] = nessuna


@dataclass(frozen=True)
class Riga:
    domanda: Domanda
    posizione: int | None  # classifica del primo chunk di una ricetta attesa; None = assente
    score_fonte: float | None
    score_migliore: float | None  # None solo se la ricerca non ha restituito nulla


def carica_domande(percorso: Path = FILE_DOMANDE) -> list[Domanda]:
    dati = json.loads(percorso.read_text(encoding="utf-8"))
    return [Domanda(d["domanda"], list(d["attese"])) for d in dati]


def valuta(domande: list[Domanda], cerca_fn: Callable[[str], list[Risultato]]) -> list[Riga]:
    righe = []
    for domanda in domande:
        risultati = cerca_fn(domanda.testo)
        fonte = next((r for r in risultati if r.numero in domanda.attese), None)
        righe.append(Riga(
            domanda=domanda,
            posizione=fonte.classifica if fonte else None,
            score_fonte=fonte.score if fonte else None,
            score_migliore=risultati[0].score if risultati else None,
        ))
    return righe


def _score(valore: float | None) -> str:
    return TRATTINO if valore is None else f"{valore:.4f}"


def tabella_markdown(righe: list[Riga]) -> str:
    linee = [
        "| # | Domanda | Fonte attesa | Posizione | Score fonte | Score migliore |",
        "|---|---|---|---|---|---|",
    ]
    for n, riga in enumerate(righe, start=1):
        attese = riga.domanda.attese
        if attese:
            fonte = "N. " + ", ".join(map(str, attese))
            posizione = str(riga.posizione) if riga.posizione is not None else "assente"
        else:
            fonte, posizione = "nessuna", TRATTINO
        linee.append(f"| {n} | {riga.domanda.testo} | {fonte} | {posizione} | {_score(riga.score_fonte)} "
                     f"| {_score(riga.score_migliore)} |")
    con_fonte = [r for r in righe if r.domanda.attese]
    trovate = sum(1 for r in con_fonte if r.posizione is not None)
    linee += ["", f"Fonte attesa trovata in {trovate} casi su {len(con_fonte)}."]
    return "\n".join(linee)


def cerca_con(config: ConfigurazioneRag) -> Callable[[str], list[Risultato]]:
    """La ricerca con k = 5 sulla collezione configurata (stesso embedder per tutte le domande)."""
    embedder, qdrant = crea_embedder(config), crea_qdrant(config)
    return lambda testo: cerca(testo, embedder, qdrant, config.collezione, k=K_VALUTAZIONE)


def main() -> int:
    try:
        config = carica_configurazione(leggi_ambiente(Path.cwd()), Path.cwd())
    except ErroreConfigurazioneRag as e:
        print(f"Configurazione non valida: {e}", file=sys.stderr)
        return 2
    configura_log(config.log_level)
    try:
        righe = valuta(carica_domande(), cerca_con(config))
    except (QdrantNonRaggiungibile, LMStudioNonRaggiungibile) as e:
        print(str(e), file=sys.stderr)
        return 3
    except (ErroreRicerca, CambioBloccato, ErroreEmbedding, ErroreQdrant) as e:
        print(f"Valutazione non eseguita: {e}", file=sys.stderr)
        return 4
    print(f"Modello {config.embedding_modello}, collezione {config.collezione}, "
          f"chunking {config.strategia} {config.dimensione}/{config.overlap}, k = {K_VALUTAZIONE}\n")
    print(tabella_markdown(righe))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
