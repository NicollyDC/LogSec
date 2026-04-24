# ============================================================
# Dockerfile — Alert Service
# ============================================================

FROM python:3.11-slim

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# gunicorn com 1 worker apenas — o Alert é sequencial por design
# (exibe um alerta de cada vez no terminal)
CMD ["gunicorn", "-w", "1", "-b", "0.0.0.0:5001", "app:app"]
