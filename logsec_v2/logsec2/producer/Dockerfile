# ============================================================
# Dockerfile — Producer
# ============================================================
# python:3.11-slim não tem curl por padrão — precisamos instalar
# para o healthcheck do docker-compose funcionar.
# ============================================================

FROM python:3.11-slim

# Instala curl (necessário para o healthcheck do docker-compose)
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "app.py"]
