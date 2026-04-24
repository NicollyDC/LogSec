
# Recebe alertas do Processor e os registra/exibe.


import json
import logging
from datetime import datetime
from flask import Flask, request, jsonify


# Logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [ALERT] %(levelname)s — %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)

app = Flask(__name__)

ARQUIVO_ALERTAS = "/tmp/alertas.jsonl"

# Memória em tempo de execução
alertas_recebidos  = []
alertas_ids_vistos = set()    # IDEMPOTÊNCIA

VISUAL_NIVEL = {
    "NORMAL":       "🟢 NORMAL",
    "BAIXO":        "🔵 BAIXO",
    "MEDIO":        "🟡 MÉDIO",
    "ALTO":         "🟠 ALTO",
    "CRITICO":      "🔴 CRÍTICO",
    "DESCONHECIDO": "⚪ ?",
}


def salvar_em_disco(alerta):
    
    with open(ARQUIVO_ALERTAS, "a") as f:
        f.write(json.dumps(alerta, ensure_ascii=False) + "\n")


def exibir_alerta(alerta):
    
    nivel_visual = VISUAL_NIVEL.get(alerta["nivel"], "⚪ ?")
    sep = "═" * 55
    log.warning(f"\n{sep}")
    log.warning(f"  {nivel_visual} — ALERTA #{alerta['numero']}")
    log.warning(sep)
    log.warning(f"  Tipo:    {alerta['tipo']}")
    log.warning(f"  Detalhe: {alerta['descricao']}")
    log.warning(f"  IP:      {alerta['ip']}  ({alerta.get('ocorrencias_ip','?')}x)")
    log.warning(f"  Risco:   {alerta['risco']}/10")
    log.warning(f"  Servidor:{alerta['servidor']}")
    log.warning(f"{sep}\n")



# ROTAS


@app.route("/health", methods=["GET"])
def health():
   
    return jsonify({
        "status":         "ok",
        "servico":        "alert",
        "total_alertas":  len(alertas_recebidos),
    })


@app.route("/alerta", methods=["POST"])
def receber_alerta():
    
    alerta = request.get_json(silent=True)

    # 1. Validação
    if not alerta or "evento_id" not in alerta:
        return jsonify({"erro": "Campo 'evento_id' obrigatório"}), 400

    evento_id = alerta["evento_id"]

    # 2. IDEMPOTÊNCIA
    if evento_id in alertas_ids_vistos:
        log.info(f"🔁 Alerta {evento_id[:8]}... duplicado — ignorado")
        return jsonify({"status": "ignorado"}), 200

    alertas_ids_vistos.add(evento_id)

    # 3. Metadados e exibição
    alerta["recebido_em"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    alerta["numero"]      = len(alertas_recebidos) + 1

    exibir_alerta(alerta)

    # 4. Persistência
    alertas_recebidos.append(alerta)
    salvar_em_disco(alerta)

    return jsonify({
        "status":        "registrado",
        "numero_alerta": alerta["numero"],
    }), 200


@app.route("/historico", methods=["GET"])
def historico():
    
    nivel = request.args.get("nivel", "").upper()
    resultado = (
        [a for a in alertas_recebidos if a.get("nivel") == nivel]
        if nivel else alertas_recebidos
    )
    return jsonify({"total": len(resultado), "alertas": resultado})


@app.route("/resumo", methods=["GET"])
def resumo():
    por_nivel = {}
    por_tipo  = {}
    por_ip    = {}

    for a in alertas_recebidos:
        por_nivel[a.get("nivel", "?")] = por_nivel.get(a.get("nivel", "?"), 0) + 1
        por_tipo[a.get("tipo",  "?")] = por_tipo.get(a.get("tipo",  "?"), 0) + 1
        por_ip[a.get("ip",    "?")] = por_ip.get(a.get("ip",    "?"), 0) + 1

    return jsonify({
        "total_alertas": len(alertas_recebidos),
        "por_nivel":     por_nivel,
        "por_tipo":      por_tipo,
        "ips_atacantes": dict(sorted(por_ip.items(), key=lambda x: x[1], reverse=True)),
        "ultimo_alerta": alertas_recebidos[-1] if alertas_recebidos else None,
    })


# ============================================================
# Sem app.run() — gunicorn cuida disso via Dockerfile
# ============================================================
if __name__ == "__main__":
    log.info("⚠️  Modo desenvolvimento — use Docker para produção!")
    app.run(host="0.0.0.0", port=5001, debug=True)
