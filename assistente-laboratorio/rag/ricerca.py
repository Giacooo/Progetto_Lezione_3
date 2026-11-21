"""Ricerca: i passaggi del libro più vicini a una domanda (lezione 7).

Uso:  python -m rag.ricerca "domanda" [--capitolo NOME] [--solo-dosi] [--k N]
"""

# COSA FA QUESTO FILE
# Trasforma la domanda in un vettore con LO STESSO modello usato nell'ingestion e chiede a
# Qdrant i k punti più vicini (top-k). Solo recupero: nessuna risposta generata (lezione 8).
#   - k: predefinito 5; il massimo (20) è imposto dal codice, non lasciato a chi chiama;
#   - --capitolo: filtro applicato DURANTE la ricerca (Qdrant cerca solo tra i punti di quel
#     capitolo); il nome va scritto come nel payload, es. "Fritti"; se non esiste, si elencano
#     i capitoli disponibili;
#   - --solo-dosi (modifica A): cerca solo tra i chunk con un elenco di ingredienti
#     (contiene_dosi vero), anche insieme a --capitolo; al massimo k risultati, tutti con il
#     campo vero. Se nessun punto ha il campo (collezione non aggiornata) lo dice, invece di
#     restituire una lista vuota;
#   - nessuna soglia sullo score: si mostrano i k risultati con il loro score.
# Per ogni risultato: posizione in classifica, score, ricetta (numero e titolo), capitolo,
# posizione del chunk nella ricetta, se contiene dosi e testo.
# Codici di uscita: 0 ok, 2 configurazione non valida, 3 Qdrant o LM Studio non raggiungibili,
# 4 richiesta o dati non validi (k, domanda vuota, capitolo, collezione, cambio bloccato).

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

from rag.configurazione import ErroreConfigurazioneRag, carica_configurazione, configura_log, leggi_ambiente
from rag.embedding import ErroreEmbedding, LMStudioNonRaggiungibile
from rag.ingestion import CambioBloccato, controlla_compatibilita, crea_embedder, crea_qdrant
from rag.qdrant import ClientQdrant, ErroreQdrant, QdrantNonRaggiungibile

log = logging.getLogger(__name__)

K_PREDEFINITO = 5
K_MASSIMO = 20


class ErroreRicerca(Exception):
    """Richiesta non valida o indice non pronto."""


@dataclass(frozen=True)
class Risultato:
    classifica: int  # 1 = il più vicino
    score: float
    numero: int
    titolo: str
    capitolo: str
    posizione: int  # posizione del chunk nella ricetta (0, 1, 2...)
    testo: str
    contiene_dosi: bool | None = None  # None: punto senza il campo (collezione non aggiornata)


FILTRO_DOSI = {"must": [{"key": "contiene_dosi", "match": {"value": True}}]}


def cerca(domanda: str, embedder, qdrant: ClientQdrant, collezione: str,
          k: int = K_PREDEFINITO, capitolo: str | None = None, solo_dosi: bool = False) -> list[Risultato]:
    # Controlli che non costano nulla, prima di qualsiasi chiamata.
    if not domanda.strip():
        raise ErroreRicerca("la domanda è vuota")
    if not 1 <= k <= K_MASSIMO:
        raise ErroreRicerca(f"k deve essere tra 1 e {K_MASSIMO}, non {k}")
    info = qdrant.info_collezione(collezione)
    if info is None:
        raise ErroreRicerca(f"la collezione {collezione!r} non esiste: eseguire prima python -m rag.ingestion")
    controlla_compatibilita(info, embedder.modello, None)
    if capitolo is not None:
        disponibili = qdrant.capitoli(collezione)
        if capitolo not in disponibili:
            raise ErroreRicerca(
                f"nessun punto ha il capitolo {capitolo!r}. Capitoli disponibili (scriverli così): "
                + "; ".join(disponibili))
    if solo_dosi and qdrant.conta(collezione, FILTRO_DOSI) == 0:
        raise ErroreRicerca(
            "nessun punto ha contiene_dosi vero: la collezione non è aggiornata. Eseguire "
            "python -m rag.ingestion --solo-payload")

    [vettore] = embedder.calcola([domanda])
    controlla_compatibilita(info, embedder.modello, len(vettore))
    trovati = qdrant.cerca(collezione, vettore, k, capitolo, solo_dosi)
    log.info("ricerca: k=%d capitolo=%s solo_dosi=%s risultati=%d", k, capitolo or "-", solo_dosi, len(trovati))
    return [
        Risultato(classifica=n, score=t.score, numero=t.payload["numero"], titolo=t.payload["titolo"],
                  capitolo=t.payload["capitolo"], posizione=t.payload["posizione"], testo=t.payload["testo"],
                  contiene_dosi=t.payload.get("contiene_dosi"))
        for n, t in enumerate(trovati, start=1)
    ]


def _dosi(valore: bool | None) -> str:
    return "" if valore is None else f" | dosi: {'sì' if valore else 'no'}"


def formatta(risultati: list[Risultato]) -> str:
    if not risultati:
        return "Nessun risultato."
    blocchi = []
    for r in risultati:
        blocchi.append(
            f"{r.classifica}. score {r.score:.4f} | N. {r.numero} {r.titolo} | {r.capitolo} | chunk {r.posizione}"
            f"{_dosi(r.contiene_dosi)}\n"
            f"{r.testo}"
        )
    return "\n\n".join(blocchi)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m rag.ricerca", description="Cerca nel libro di Artusi.")
    parser.add_argument("domanda", help="la domanda, tra virgolette")
    parser.add_argument("--capitolo", help='filtra per capitolo, scritto come nel libro, es. "Fritti"')
    parser.add_argument("--solo-dosi", action="store_true",
                        help="solo i passaggi con un elenco di ingredienti (contiene_dosi)")
    parser.add_argument("--k", type=int, default=K_PREDEFINITO, help=f"quanti risultati (1-{K_MASSIMO})")
    argomenti = parser.parse_args(argv)
    try:
        config = carica_configurazione(leggi_ambiente(Path.cwd()), Path.cwd())
    except ErroreConfigurazioneRag as e:
        print(f"Configurazione non valida: {e}", file=sys.stderr)
        return 2
    configura_log(config.log_level)
    try:
        risultati = cerca(argomenti.domanda, crea_embedder(config), crea_qdrant(config), config.collezione,
                          argomenti.k, argomenti.capitolo, argomenti.solo_dosi)
    except (QdrantNonRaggiungibile, LMStudioNonRaggiungibile) as e:
        print(str(e), file=sys.stderr)
        return 3
    except (ErroreRicerca, CambioBloccato, ErroreEmbedding, ErroreQdrant) as e:
        print(f"Ricerca non eseguita: {e}", file=sys.stderr)
        return 4
    print(formatta(risultati))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
