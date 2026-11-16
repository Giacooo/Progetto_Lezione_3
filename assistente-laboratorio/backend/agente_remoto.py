"""Client HTTP con cui il back-end chiama l'agente dello step 6 (POST /messaggio)."""

# COSA FA QUESTO FILE (lezione 6, step 7)
# Il back-end non conosce il grafo né il modello: manda all'agente la domanda con la memoria
# della chat (cronologia e riassunto) e riceve risposta, strumenti usati e memoria aggiornata.
# La cronologia è un dato "opaco": il back-end la salva e la rimanda senza interpretarla.
# Ogni guasto dell'agente diventa un ErroreAgente con il codice HTTP e il messaggio che il
# back-end restituirà (§9.1 della specifica): in quei casi la chat non viene toccata.

from dataclasses import dataclass

import httpx

# Secondi di attesa per la risposta dell'agente (come la CLI dello step 6).
ATTESA_MASSIMA = 600

NON_SALVATA = "La domanda non è stata salvata."
NON_RAGGIUNGIBILE = "Agente non raggiungibile: la domanda non è stata salvata, riprovare più tardi."
FUORI_TEMPO = "L'agente non ha risposto in tempo: la domanda non è stata salvata."
NON_VALIDA = f"Risposta non valida dall'agente: controllare AGENTE_URL. {NON_SALVATA}"


class ErroreAgente(Exception):
    """L'agente non ha dato una risposta utilizzabile; codice = codice HTTP per il front-end."""

    def __init__(self, codice: int, messaggio: str):
        super().__init__(messaggio)
        self.codice = codice


@dataclass(frozen=True)
class RispostaAgente:
    risposta: str
    strumenti_usati: list[dict]
    cronologia: list[dict]
    riassunto: str


def _lista_di_dizionari(valore) -> bool:
    return isinstance(valore, list) and all(isinstance(v, dict) for v in valore)


# Ogni strumento usato deve avere la forma dello step 6: nome (testo), argomenti (oggetto),
# risultato (testo). Controllato PRIMA di salvare: dopo sarebbe troppo tardi.
def _strumenti_validi(valore) -> bool:
    return _lista_di_dizionari(valore) and all(
        isinstance(s.get("nome"), str) and isinstance(s.get("argomenti"), dict) and isinstance(s.get("risultato"), str)
        for s in valore
    )


class AgenteRemoto:
    def __init__(self, url: str, client: httpx.Client | None = None):
        self.client = client or httpx.Client(base_url=url.rstrip("/"), timeout=ATTESA_MASSIMA)

    def invia(self, messaggio: str, cronologia: list[dict], riassunto: str) -> RispostaAgente:
        corpo = {"messaggio": messaggio, "cronologia": cronologia, "riassunto": riassunto}
        try:
            r = self.client.post("/messaggio", json=corpo)
        except httpx.TimeoutException:
            raise ErroreAgente(504, FUORI_TEMPO) from None
        except httpx.TransportError:  # connessione rifiutata, indirizzo sbagliato, connessione caduta
            raise ErroreAgente(503, NON_RAGGIUNGIBILE) from None

        try:
            dati = r.json()
        except ValueError:
            dati = None

        if r.status_code != 200:
            motivo = dati.get("errore") if isinstance(dati, dict) else None
            if not isinstance(motivo, str) or not motivo.strip():
                motivo = f"codice {r.status_code}"
            raise ErroreAgente(502, f"Errore dell'agente: {motivo.strip().rstrip('.')}. {NON_SALVATA}")

        if not (
            isinstance(dati, dict)
            and isinstance(dati.get("risposta"), str)
            and _strumenti_validi(dati.get("strumenti_usati"))
            and _lista_di_dizionari(dati.get("cronologia"))
            and isinstance(dati.get("riassunto"), str)
        ):
            raise ErroreAgente(502, NON_VALIDA)
        return RispostaAgente(dati["risposta"], dati["strumenti_usati"], dati["cronologia"], dati["riassunto"])
