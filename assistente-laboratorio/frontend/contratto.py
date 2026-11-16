"""Il contratto OpenAPI del back-end: operazioni ammesse e download (python -m frontend.contratto)."""

# COSA FA QUESTO FILE (lezione 6, step 8)
# Il PDF chiede che il documento OpenAPI del back-end sia il "contratto" del front-end: le
# chiamate si ricavano da lì, senza indovinare gli endpoint. Il front-end ne tiene una copia in
# frontend/contratto/openapi-backend.json (salvata in Git) e la usa in due modi:
#   - operazioni(): l'elenco "metodo + percorso" che il proxy (app.py) lascia passare;
#   - main(): riscarica il documento dal back-end acceso (GET /openapi.json all'indirizzo
#     BACKEND_URL) e riscrive la copia. Il front-end riceve il contratto dal back-end come un
#     qualunque cliente HTTP: non importa il pacchetto backend.
# Uscita di main(): 0 = file aggiornato, 1 = back-end non raggiungibile o risposta non valida
# (file non toccato), 2 = configurazione non valida.

import json
import re
import sys
from pathlib import Path

import httpx

from frontend.configurazione import ErroreConfigurazioneFrontend, carica_configurazione, leggi_ambiente

FILE_CONTRATTO = Path(__file__).resolve().parent / "contratto" / "openapi-backend.json"
METODI = ("get", "post", "put", "patch", "delete")
# Un parametro del percorso ({chat_id}): un pezzo senza "/", "?", "#", spazi o a capo, che
# altrimenti cambierebbero la richiesta che arriva al back-end.
PARAMETRO = r"[^/?#\s]+"


class ErroreContratto(Exception):
    """Il documento OpenAPI non si è potuto scaricare dal back-end."""


def carica_contratto(percorso: Path | None = None) -> dict:
    """Il documento OpenAPI salvato (per i test, si può indicare un altro file)."""
    return json.loads((percorso or FILE_CONTRATTO).read_text(encoding="utf-8"))


def operazioni(documento: dict) -> list[tuple[str, re.Pattern[str]]]:
    """Coppie (metodo, regex del percorso): "/chat/{chat_id}" diventa /chat/PARAMETRO."""
    elenco = []
    for percorso, voci in documento.get("paths", {}).items():
        regex = re.sub(r"\\\{[^}]*\\\}", lambda _: PARAMETRO, re.escape(percorso))
        for metodo in voci:
            if metodo in METODI:
                elenco.append((metodo.upper(), re.compile(regex)))
    return elenco


def ammessa(operazioni_ammesse: list[tuple[str, re.Pattern[str]]], metodo: str, percorso: str) -> bool:
    """True se metodo e percorso corrispondono a un'operazione del contratto."""
    metodo = metodo.upper()
    # "." e ".." verrebbero risolti dal client HTTP (/chat/.. → /): il percorso che arriva al
    # back-end non sarebbe più quello controllato qui.
    if any(pezzo in (".", "..") for pezzo in percorso.split("/")):
        return False
    # fullmatch: tutto il percorso deve corrispondere, anche senza un "a capo" finale.
    return any(m == metodo and regex.fullmatch(percorso) for m, regex in operazioni_ammesse)


def scarica_contratto(client: httpx.Client, destinazione: Path) -> None:
    """Scarica /openapi.json dal back-end e lo scrive (UTF-8 senza BOM, JSON indentato)."""
    try:
        risposta = client.get("/openapi.json")
    except httpx.TransportError as e:
        raise ErroreContratto(f"Back-end non raggiungibile: {e}") from None
    if risposta.status_code != 200:
        raise ErroreContratto(f"il back-end ha risposto con il codice {risposta.status_code}")
    try:
        documento = risposta.json()
    except ValueError:
        raise ErroreContratto("la risposta del back-end non è un documento JSON") from None
    if not isinstance(documento, dict):
        raise ErroreContratto("la risposta del back-end non è un documento OpenAPI")
    testo = json.dumps(documento, ensure_ascii=False, indent=2) + "\n"
    destinazione.write_text(testo, encoding="utf-8", newline="\n")


def main() -> int:
    try:
        config = carica_configurazione(leggi_ambiente(Path.cwd()))
    except ErroreConfigurazioneFrontend as e:
        print(f"Configurazione non valida: {e}", file=sys.stderr)
        return 2
    with httpx.Client(base_url=config.backend_url, timeout=10) as client:
        try:
            scarica_contratto(client, FILE_CONTRATTO)
        except ErroreContratto as e:
            print(str(e) if str(e).startswith("Back-end") else f"Contratto non aggiornato: {e}", file=sys.stderr)
            return 1
    print(f"Contratto aggiornato: {FILE_CONTRATTO}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
