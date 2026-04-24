# ============================================================
# Dockerfile — Processor
# ============================================================
# Usa gunicorn como servidor WSGI de produção no lugar do
# servidor de desenvolvimento do Flask (app.run).
# O gunicorn aguenta múltiplas requisições simultâneas.
# ============================================================

FROM python:3.11-slim

# curl necessário para o healthcheck
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# gunicorn: servidor WSGI robusto para produção
# -w 2         → 2 workers (processos paralelos)
# -b 0.0.0.0:5000 → escuta em todas as interfaces na porta 5000
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5000", "app:app"]
