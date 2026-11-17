# RICETTA PER COSTRUIRE L'IMMAGINE DOCKER DELL'AGENTE (e della CLI)
# Un'immagine è come una "scatola sigillata" con dentro Python, le librerie e il nostro
# codice: gira uguale su qualsiasi computer. LM Studio resta FUORI, sul PC.
# Dallo step 9 della lezione 6 ogni componente ha il suo Dockerfile: questo (nella cartella del
# progetto) è dell'agente; back-end e front-end hanno backend/Dockerfile e frontend/Dockerfile.
# Si costruisce con: docker compose build agente

# Punto di partenza: un Python 3.13 in versione leggera ("slim").
FROM python:3.13-slim

# PYTHONUNBUFFERED=1: i messaggi compaiono subito a schermo (e nei log di Docker).
# PYTHONDONTWRITEBYTECODE=1: Python non crea file temporanei .pyc dentro l'immagine.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Cartella di lavoro dentro il container: da qui in poi i comandi partono da /app.
WORKDIR /app

# Prima si copiano e si installano SOLO le librerie, poi (più sotto) il codice.
# Così, se si cambia solo il codice, Docker riusa questo passo già fatto e il build è veloce.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Si copia solo la cartella del programma: niente test, documenti, .env o .venv
# (il file .dockerignore esclude il resto).
COPY assistente ./assistente

# Comando eseguito quando il container parte: avvia la CLI (dallo step 6 è il client dell'agente).
# Il servizio "agente" di compose.yaml lo sostituisce con: python -m assistente.servizio
CMD ["python", "-m", "assistente"]
