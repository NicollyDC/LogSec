
# Recebe eventos do Producer, analisa ameaças e envia alertas.


import os
import time
import logging
import requests
from flask import Flask, request, jsonify


# Logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [PROCESSOR] %(levelname)s — %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)


# App Flask

# IMPORTANTE: a variável precisa chamar "app" para o gunicorn
# encontrar com o comando: gunicorn app:app
app = Flask(__name__)

ALERT_URL = os.getenv("ALERT_URL", "http://localhost:5001")

# IDEMPOTÊNCIA — memória de eventos já processados

eventos_processados = set()

# Contador de eventos por IP 
contagem_por_ip = {}

# Regras de classificação de ameaças

REGRAS = {
    "LOGIN_OK":       {"nivel": "NORMAL",  "risco": 0,  "alerta": False},
    "LOGIN_FALHOU":   {"nivel": "BAIXO",   "risco": 2,  "alerta": False},
    "ACESSO_NEGADO":  {"nivel": "MEDIO",   "risco": 4,  "alerta": False},
    "BRUTE_FORCE":    {"nivel": "ALTO",    "risco": 7,  "alerta": True},
    "SQL_INJECTION":  {"nivel": "CRITICO", "risco": 10, "alerta": True},
    "PORT_SCAN":      {"nivel": "ALTO",    "risco": 8,  "alerta": True},
}


def analisar_evento(evento):
    
    tipo = evento.get("tipo", "DESCONHECIDO")
    ip   = evento.get("ip", "0.0.0.0")

    regra = REGRAS.get(tipo, {"nivel": "DESCONHECIDO", "risco": 5, "alerta": True})

    # Atualiza contagem por IP
    contagem_por_ip[ip] = contagem_por_ip.get(ip, 0) + 1

    gerar_alerta = regra["alerta"]
    nivel        = regra["nivel"]
    risco        = regra["risco"]

    # Regra comportamental: muitos LOGIN_FALHOU do mesmo IP = brute force
    if contagem_por_ip[ip] > 5 and tipo == "LOGIN_FALHOU":
        gerar_alerta = True
        nivel        = "ALTO"
        risco        = max(risco, 7)
        log.warning(f" Padrão suspeito: IP {ip} com {contagem_por_ip[ip]} eventos!")

    return {
        "evento_id":      evento["id"],
        "tipo":           tipo,
        "descricao":      evento.get("descricao", ""),
        "ip":             ip,
        "servidor":       evento.get("servidor", "?"),
        "nivel":          nivel,
        "risco":          risco,
        "gerar_alerta":   gerar_alerta,
        "timestamp":      evento.get("timestamp"),
        "ocorrencias_ip": contagem_por_ip[ip],
    }


def enviar_alerta_com_retry(analise, max_tentativas=3, timeout_seg=2):
   
    for tentativa in range(1, max_tentativas + 1):
        try:
            r = requests.post(
                f"{ALERT_URL}/alerta",
                json=analise,
                timeout=timeout_seg          # ← TIMEOUT
            )
            if r.status_code == 200:
                log.info(" Alerta entregue ao Alert Service!")
                return True
            log.warning(f" Alert Service retornou HTTP {r.status_code}")

        except requests.exceptions.Timeout:
            log.warning(f"  Timeout ao contatar Alert Service (tentativa {tentativa})")

        except requests.exceptions.ConnectionError:
            log.warning(f" Alert Service inacessível (tentativa {tentativa})")

        if tentativa < max_tentativas:
            espera = 2 ** (tentativa - 1)
            log.info(f" Aguardando {espera}s antes de tentar novamente...")
            time.sleep(espera)

    return False


def fallback_alerta(analise):
    
    import json
    caminho = "/tmp/alertas_fallback.jsonl"
    with open(caminho, "a") as f:
        f.write(json.dumps(analise, ensure_ascii=False) + "\n")
    log.error(f"💾 FALLBACK: alerta salvo em {caminho}")


# ROTAS DA API


@app.route("/health", methods=["GET"])
def health():
   
    return jsonify({
        "status":               "ok",
        "servico":              "processor",
        "eventos_processados":  len(eventos_processados),
        "ips_monitorados":      len(contagem_por_ip),
    })


@app.route("/log", methods=["POST"])
def receber_log():
   
    evento = request.get_json(silent=True)  # silent=True evita exceção se JSON inválido

    # 1. Validação
    if not evento or "id" not in evento or "tipo" not in evento:
        return jsonify({"erro": "Campos obrigatórios: id, tipo"}), 400

    evento_id = evento["id"]

    # 2. IDEMPOTÊNCIA
    if evento_id in eventos_processados:
        log.info(f"Evento {evento_id[:8]}... duplicado — ignorado")
        return jsonify({"status": "ignorado", "motivo": "já processado"}), 200

    eventos_processados.add(evento_id)

    log.info(f" {evento['tipo']} de {evento.get('ip')} ({evento.get('servidor')})")

    # 3. Análise
    analise = analisar_evento(evento)
    log.info(f" Nível: {analise['nivel']} | Risco: {analise['risco']}/10")

    # 4. Alerta se suspeito
    if analise["gerar_alerta"]:
        log.warning(f" AMEAÇA: {analise['tipo']} — {analise['nivel']}")
        if not enviar_alerta_com_retry(analise):
            fallback_alerta(analise)

    # 5. Resposta
    return jsonify({
        "status":         "processado",
        "evento_id":      evento_id,
        "nivel":          analise["nivel"],
        "risco":          analise["risco"],
        "alerta_enviado": analise["gerar_alerta"],
    }), 200


@app.route("/stats", methods=["GET"])
def stats():
    """Estatísticas do Processor para monitoramento."""
    return jsonify({
        "total_processados": len(eventos_processados),
        "ips_monitorados":   dict(sorted(
            contagem_por_ip.items(), key=lambda x: x[1], reverse=True
        )),
    })


# ============================================================
# ATENÇÃO: não há app.run() aqui!
# O gunicorn (no Dockerfile) inicia o servidor Flask diretamente.
# app.run() é apenas para desenvolvimento local — não para Docker.
# ============================================================
if __name__ == "__main__":
    # Só executa se rodar "python app.py" diretamente (fora do Docker)
    log.info("⚠️  Modo desenvolvimento — use Docker para produção!")
    app.run(host="0.0.0.0", port=5000, debug=True)
