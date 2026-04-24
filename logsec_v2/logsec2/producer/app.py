
# Gera eventos falsos de segurança e envia ao Processor via HTTP.

import os
import time
import uuid
import random
import logging
import requests


# Configuração de Logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [PRODUCER] %(levelname)s — %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)


# Configurações via variáveis de ambiente

PROCESSOR_URL = os.getenv("PROCESSOR_URL", "http://localhost:5000")
INTERVAL      = int(os.getenv("INTERVAL", "3"))


# Tipos de eventos simulados

IPS_SUSPEITOS = ["192.168.1.99", "10.0.0.200", "172.16.0.55"]
IPS_NORMAIS   = ["192.168.1.1",  "10.0.0.1",   "192.168.0.105"]

EVENTOS = [
    {"tipo": "LOGIN_OK",      "descricao": "Login bem-sucedido",            "peso": 50},
    {"tipo": "LOGIN_FALHOU",  "descricao": "Tentativa de login com falha",  "peso": 25},
    {"tipo": "ACESSO_NEGADO", "descricao": "Acesso a recurso negado",       "peso": 15},
    {"tipo": "BRUTE_FORCE",   "descricao": "Múltiplas falhas de login",     "peso": 7},
    {"tipo": "SQL_INJECTION", "descricao": "Tentativa de SQL Injection",    "peso": 2},
    {"tipo": "PORT_SCAN",     "descricao": "Varredura de portas detectada", "peso": 1},
]


def gerar_evento():
    
    tipos_suspeitos = {"BRUTE_FORCE", "SQL_INJECTION", "PORT_SCAN"}

    evento_sorteado = random.choices(
        EVENTOS,
        weights=[e["peso"] for e in EVENTOS],
        k=1
    )[0]

    ip = random.choice(
        IPS_SUSPEITOS if evento_sorteado["tipo"] in tipos_suspeitos
        else IPS_NORMAIS
    )

    return {
        "id":        str(uuid.uuid4()),                    # UUID único —  idempotência
        "tipo":      evento_sorteado["tipo"],
        "descricao": evento_sorteado["descricao"],
        "ip":        ip,
        "servidor":  f"srv-{random.randint(1, 5):02d}",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


def enviar_com_retry(evento, max_tentativas=3, timeout_seg=2):
    
    for tentativa in range(1, max_tentativas + 1):
        try:
            log.info(f"Enviando {evento['tipo']} [tentativa {tentativa}/{max_tentativas}]...")

            resposta = requests.post(
                f"{PROCESSOR_URL}/log",
                json=evento,
                timeout=timeout_seg          # ← TIMEOUT aqui
            )

            if resposta.status_code == 200:
                dados = resposta.json()
                log.info(f" Enviado! Status: {dados.get('status')} | Nível: {dados.get('nivel', 'N/A')}")
                return True
            else:
                log.warning(f"  Processor retornou HTTP {resposta.status_code}")

        except requests.exceptions.Timeout:
            log.warning(f"⏱️  Timeout na tentativa {tentativa} (limite: {timeout_seg}s)")

        except requests.exceptions.ConnectionError:
            log.warning(f" Sem conexão com Processor na tentativa {tentativa}")

        # Backoff exponencial antes da próxima tentativa
        if tentativa < max_tentativas:
            espera = 2 ** (tentativa - 1)   # 1s, 2s, 4s
            log.info(f"Aguardando {espera}s (backoff exponencial)...")
            time.sleep(espera)

    return False   # Todas as tentativas falharam


def fallback_local(evento):
   
    import json
    caminho = "/tmp/logs_fallback.jsonl"
    with open(caminho, "a") as f:
        f.write(json.dumps(evento, ensure_ascii=False) + "\n")
    log.error(f"FALLBACK ativado! Evento salvo em {caminho}")



# Loop principal

if __name__ == "__main__":
    log.info("Producer iniciado!")
    log.info(f" Processor: {PROCESSOR_URL} | Intervalo: {INTERVAL}s")

    # O depends_on com healthcheck no docker-compose já garante
    # que o Processor está pronto antes deste container iniciar.
    # Adicionamos uma pequena espera extra por segurança.
    log.info(" Aguardando 2s para garantir que o Processor está estável...")
    time.sleep(2)

    contador = 0
    while True:
        contador += 1
        log.info(f"\n{'─'*50}")
        log.info(f"Gerando evento #{contador}")

        evento = gerar_evento()
        log.info(f"   {evento['tipo']} | IP: {evento['ip']} | {evento['servidor']}")

        sucesso = enviar_com_retry(evento)

        if not sucesso:
            fallback_local(evento)

        time.sleep(INTERVAL)
