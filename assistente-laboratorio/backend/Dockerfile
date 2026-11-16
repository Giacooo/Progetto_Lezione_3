# RICETTA PER COSTRUIRE L'IMMAGINE DOCKER DEL BACK-END (lezione 6, step 9)
# Dallo step 9 ogni componente ha il suo container: questa è l'immagine del back-end, l'API
# che salva chat e messaggi in PostgreSQL e chiama l'agente via HTTP.
# Si costruisce da compose.yaml (servizio "backend") con: docker compose build backend
# La "cartella di partenza" del build è quella del progetto (context: . in compose.yaml):
# per questo i percorsi qui sotto (requirements.txt, backend) sono scritti da lì.

# Punto di partenza: lo stesso Python 3.13 leggero dell'agente.
FROM python:3.13-slim

# PYTHONUNBUFFERED=1: i messaggi compaiono subito nei log di Docker.
# PYTHONDONTWRITEBYTECODE=1: Python non crea file temporanei .pyc dentro l'immagine.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Cartella di lavoro dentro il container.
WORKDIR /app

# Prima le librerie (stesso elenco di tutto il progetto), poi il codice: se cambia solo il
# codice, Docker riusa il passo delle librerie e il build è veloce.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Solo il pacchetto del back-end: l'immagine non contiene né l'agente né il front-end.
COPY backend ./backend

# Avvia il back-end (porta 8001). Indirizzi del database e dell'agente arrivano da compose.yaml.
CMD ["python", "-m", "backend"]
