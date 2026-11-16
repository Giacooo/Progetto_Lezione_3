"""Cronologia della sessione ed esecuzione di un turno attraverso il grafo."""

# COSA FA QUESTO FILE
# Tiene la "memoria" della chat e gestisce UN turno (una domanda e la sua risposta).
# Il modello non ricorda nulla da solo: ad ogni domanda gli rimandiamo tutta la
# conversazione precedente, che è conservata qui nella lista "cronologia".
# Dalla lezione 6 (step 3) conserva anche il "riassunto" dei messaggi più vecchi già tolti.
# Dallo step 5 un turno può aprirsi anche con i messaggi già pronti di un prompt MCP
# (comando /prompt): passano dal grafo esattamente come una domanda scritta a mano.
# Dallo step 6 è un "client in memoria" dell'agente senza stato (agente.py): la usano i test e
# le prove reali; tiene lei cronologia e riassunto e per ogni turno chiama esegui_turno.
# (La CLI, invece, dallo step 6 parla con l'agente via HTTP: vedi cliente.py.)
# Regola d'oro: cronologia e riassunto cambiano SOLO se il turno finisce bene.

from langchain_core.messages import BaseMessage, HumanMessage

from assistente.agente import esegui_turno


class Conversazione:
    def __init__(self, grafo):
        # Il grafo che sa come elaborare un turno (vedi grafo.py).
        self.grafo = grafo
        # Tutti i messaggi della sessione, dall'inizio. Parte vuota.
        self.cronologia: list[BaseMessage] = []
        # Il riassunto della parte di conversazione già tolta dalla cronologia. Parte vuoto.
        self.riassunto: str = ""

    def chiedi(self, domanda: str) -> str:
        """Esegue un turno a partire da una domanda scritta dall'utente."""
        # Forma breve: la domanda diventa un HumanMessage e il turno è quello di chiedi_messaggi.
        return self.chiedi_messaggi([HumanMessage(domanda)])

    def chiedi_messaggi(self, messaggi: list[BaseMessage]) -> str:
        """Esegue un turno con messaggi già pronti; memoria aggiornata solo se il turno riesce."""
        # Il turno vero e proprio lo esegue l'agente senza stato: riceve cronologia e riassunto e
        # li restituisce aggiornati. Se il turno fallisce, esegui_turno lancia un ErroreTurno
        # (con il messaggio chiaro già scritto nel log) e qui non si tocca nulla.
        esito = esegui_turno(self.grafo, self.cronologia, messaggi, self.riassunto)
        # Tutto bene, quindi (e solo ora) aggiorniamo la memoria: tutti i messaggi del turno
        # (domanda, richieste di strumento, risultati, risposta) e il riassunto, se il nodo
        # riassunto ha compresso la conversazione.
        self.cronologia = esito.cronologia
        self.riassunto = esito.riassunto
        return esito.risposta
