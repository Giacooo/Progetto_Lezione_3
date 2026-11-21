# RICETTA PER COSTRUIRE L'IMMAGINE DOCKER DEL RAG (lezione 7)
# Contiene gli script del pacchetto rag: ingestion (predefinito), ricerca e valutazione.
# Si costruisce da compose.yaml (servizio "ingestion") con: docker compose build ingestion
# e si usa con: docker compose run --rm ingestion
# La "cartella di partenza" del build è quella del progetto (context: . in compose.yaml):
# per questo i percorsi qui sotto (requirements.txt, rag) sono scritti da lì.
# Il libro (dati/artusi.txt) NON entra nell'immagine: compose.yaml monta la cartella dati/ del
# PC in sola lettura.

# Punto di partenza: lo stesso Python 3.13 leggero degli altri componenti.
FROM python:3.13-slim

# PYTHONUNBUFFERED=1: i messaggi compaiono subito nei log di Docker.
# PYTHONDONTWRITEBYTECODE=1: Python non crea file temporanei .pyc dentro l'immagine.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Cartella di lavoro dentro il container (dati/artusi.txt si cerca da qui).
WORKDIR /app

# Prima le librerie (stesso elenco di tutto il progetto), poi il codice: se cambia solo il
# codice, Docker riusa il passo delle librerie e il build è veloce.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Solo il pacchetto del RAG (con il file delle domande di valutazione).
COPY rag ./rag

# Comando predefinito: l'ingestion. Per ricerca e valutazione si scrive il comando dopo il nome
# del servizio, es.: docker compose run --rm ingestion python -m rag.valutazione
CMD ["python", "-m", "rag.ingestion"]
