# RICETTA PER COSTRUIRE L'IMMAGINE DOCKER DEL FRONT-END (lezione 6, step 9)
# Dallo step 9 ogni componente ha il suo container: questa è l'immagine del front-end, che
# serve la pagina di chat al browser e inoltra le chiamate /api/... al back-end.
# Si costruisce da compose.yaml (servizio "frontend") con: docker compose build frontend
# La "cartella di partenza" del build è quella del progetto (context: . in compose.yaml):
# per questo i percorsi qui sotto (requirements.txt, frontend) sono scritti da lì.

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

# Solo il pacchetto del front-end, con la pagina (statico/) e il contratto OpenAPI (contratto/):
# l'immagine non contiene né l'agente né il back-end.
COPY frontend ./frontend

# Avvia il front-end (porta 8002). L'indirizzo del back-end arriva da compose.yaml.
CMD ["python", "-m", "frontend"]
