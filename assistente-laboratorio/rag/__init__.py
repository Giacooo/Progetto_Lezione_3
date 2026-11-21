"""RAG, prima metà (lezione 7): ingestion del libro di Artusi in Qdrant, ricerca e valutazione."""

# COSA C'È IN QUESTO PACCHETTO
# Una fase della pipeline per modulo, così ognuna si può provare e ispezionare da sola:
#   configurazione  variabili d'ambiente (.env) del RAG
#   corpus          pulizia del libro e divisione in ricette (numero, titolo, capitolo, testo)
#   chunking        divisione di ogni ricetta in pezzi (chunk) con sovrapposizione
#   embedding       vettori calcolati da LM Studio (stesso modello per documenti e domande)
#   qdrant          le poche operazioni dell'API REST di Qdrant che servono
#   ingestion       lo script che costruisce l'indice:   python -m rag.ingestion
#   ricerca         i passaggi più vicini a una domanda: python -m rag.ricerca "domanda"
#   valutazione     domande con fonte attesa:            python -m rag.valutazione
# Il pacchetto non importa nulla di assistente, backend e frontend.
