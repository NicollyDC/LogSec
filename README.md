
Sistema de Monitoramento de Segurança com Análise de Logs (Protótipo)
# 🔐 LogSec — Sistema Distribuído de Monitoramento de Segurança

> Sistema distribuído com 3 containers Docker que simula detecção de ameaças em tempo real, desenvolvido como trabalho prático da disciplina de Sistemas Distribuídos.
> Projeto adaptado do TCC em desenvolvimento sobre monitoramento de segurança em ambientes corporativos.

---

## 📋 Índice

- [Sobre o Projeto](#-sobre-o-projeto)
- [Arquitetura](#-arquitetura)
- [Conceitos de Resiliência](#-conceitos-de-resiliência)
- [Estrutura de Arquivos](#-estrutura-de-arquivos)
- [Como Rodar](#-como-rodar)
- [Endpoints da API](#-endpoints-da-api)
- [Como Testar](#-como-testar)
- [Demonstração do Fallback](#-demonstração-do-fallback)
- [Tecnologias](#-tecnologias)

---

## 💡 Sobre o Projeto

O **LogSec** simula o que acontece num ambiente corporativo real: servidores gerando eventos de segurança que são analisados automaticamente e geram alertas quando ameaças são detectadas.

O sistema é dividido em **3 serviços independentes** que se comunicam via HTTP, cada um rodando em seu próprio container Docker:

| Serviço | Responsabilidade | Porta |
|---------|-----------------|-------|
| `producer` | Gera eventos de segurança simulados a cada 3 segundos | — |
| `processor` | Analisa eventos e detecta ameaças | 5000 |
| `alert` | Recebe alertas e mantém histórico do SOC | 5001 |

---

## 🏗️ Arquitetura

```
                        ┌─────────────────────────────────────────┐
                        │         logsec-net (Docker bridge)       │
                        │                                          │
  ┌──────────┐          │  ┌───────────┐       ┌───────────────┐  │
  │ Usuário  │──────────┼─▶│ Processor │──────▶│ Alert Service │  │
  │ (curl /  │          │  │ porta 5000│       │  porta 5001   │  │
  │ browser) │          │  └─────▲─────┘       └───────────────┘  │
  └──────────┘          │        │                                 │
                        │  ┌─────┴─────┐                          │
                        │  │  Producer │                           │
                        │  │ (sem porta│                           │
                        │  │  exposta) │                           │
                        │  └───────────┘                           │
                        └─────────────────────────────────────────┘

  POST /log                           POST /alerta
  retry 3x + timeout 2s               retry 3x + timeout 2s
  fallback: logs_fallback.jsonl       fallback: alertas_fallback.jsonl
```

### Ordem de inicialização

```
Alert (healthy) → Processor (healthy) → Producer (inicia)
```

O `docker-compose.yml` garante essa ordem via `depends_on` com `condition: service_healthy`.

---

## 🛡️ Conceitos de Resiliência

### ✅ Retry — Tentativas Automáticas
Se uma requisição falhar, o sistema tenta novamente com **backoff exponencial** (1s → 2s → 4s), até 3 tentativas.

```python
for tentativa in range(1, max_tentativas + 1):
    resposta = requests.post(url, json=dados, timeout=2)
    if resposta.status_code == 200:
        return True
    espera = 2 ** (tentativa - 1)  # 1s, 2s, 4s
    time.sleep(espera)
```

**Onde:** `producer/app.py` → `enviar_com_retry()` | `processor/app.py` → `enviar_alerta_com_retry()`

---

### ✅ Timeout — Limite de Espera
Cada requisição tem limite de **2 segundos**. Se o serviço de destino não responder a tempo, a tentativa é abandonada e o retry assume.

```python
requests.post(url, json=dados, timeout=2)  # desiste após 2s
```

**Onde:** Todas as chamadas HTTP do Producer e do Processor.

---

### ✅ Fallback — Plano B Automático
Se todas as tentativas de retry falharem, o dado é **salvo localmente em arquivo JSONL** para não ser perdido.

```python
sucesso = enviar_com_retry(evento)
if not sucesso:
    fallback_local(evento)  # salva em /tmp/logs_fallback.jsonl
```

| Serviço | Arquivo de Fallback |
|---------|-------------------|
| Producer | `/tmp/logs_fallback.jsonl` |
| Processor | `/tmp/alertas_fallback.jsonl` |

**Onde:** `producer/app.py` → `fallback_local()` | `processor/app.py` → `fallback_alerta()`

---

### ✅ Idempotência — Sem Duplicatas
Cada evento recebe um **UUID único** no Producer. O Processor e o Alert mantêm um `set` de IDs já processados — eventos duplicados (causados pelo retry) são silenciosamente ignorados.

```python
# Producer — gera UUID único
"id": str(uuid.uuid4())

# Processor — verifica duplicata
if evento_id in eventos_processados:
    return jsonify({"status": "ignorado"}), 200
eventos_processados.add(evento_id)
```

**Onde:** `producer/app.py` → `gerar_evento()` | `processor/app.py` e `alert/app.py` → verificação no início de cada rota POST.

---

## 📁 Estrutura de Arquivos

```
logsec/
├── docker-compose.yml        # Orquestra os 3 containers
├── README.md
│
├── producer/                 # Container 1 — Gerador de eventos
│   ├── Dockerfile
│   ├── requirements.txt      # requests
│   └── app.py                # Loop infinito: gera → envia → retry → fallback
│
├── processor/                # Container 2 — Analisador de ameaças
│   ├── Dockerfile            # Usa gunicorn (2 workers)
│   ├── requirements.txt      # flask, requests, gunicorn
│   └── app.py                # API Flask: /health /log /stats
│
└── alert/                    # Container 3 — Painel SOC
    ├── Dockerfile            # Usa gunicorn
    ├── requirements.txt      # flask, gunicorn
    └── app.py                # API Flask: /health /alerta /historico /resumo
```

---

## 🚀 Como Rodar

### Pré-requisitos
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) instalado e rodando

### Subir o sistema
```bash
# Clone o repositório
git clone https://github.com/seu-usuario/logsec.git
cd logsec

# Sobe os 3 containers
docker compose up --build
```

O sistema está pronto quando aparecer no terminal:
```
Container logsec-alert     Healthy
Container logsec-processor Healthy
logsec-producer | Producer iniciado!
```

### Parar o sistema
```bash
docker compose down
```

### Ver status dos containers
```bash
docker compose ps
```

---

## 🌐 Endpoints da API

### Processor — `localhost:5000`

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/health` | Status do serviço e total de eventos processados |
| POST | `/log` | Recebe eventos do Producer |
| GET | `/stats` | Estatísticas e IPs mais ativos |

### Alert Service — `localhost:5001`

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/health` | Status do serviço e total de alertas |
| POST | `/alerta` | Recebe alertas do Processor |
| GET | `/historico` | Lista todos os alertas (aceita `?nivel=CRITICO`) |
| GET | `/resumo` | Resumo estatístico completo do SOC |

> **Nota:** O Producer não expõe porta — ele só produz e consome, nunca é consultado externamente.

---

## 🧪 Como Testar

### Verificar saúde dos serviços
```bash
curl http://localhost:5000/health
curl http://localhost:5001/health
```

### Ver estatísticas em tempo real
```bash
# Eventos processados e IPs monitorados
curl http://localhost:5000/stats

# Resumo de alertas do SOC
curl http://localhost:5001/resumo

# Histórico completo de alertas
curl http://localhost:5001/historico

# Filtrar só alertas críticos
curl http://localhost:5001/historico?nivel=CRITICO
```

### Testar idempotência manualmente
```bash
# Envia o mesmo evento duas vezes com o mesmo ID
curl -X POST http://localhost:5000/log \
  -H "Content-Type: application/json" \
  -d '{"id":"teste-123","tipo":"BRUTE_FORCE","ip":"10.0.0.1","servidor":"srv-01","descricao":"Teste","timestamp":"2024-01-01T00:00:00"}'

# Segunda vez com o mesmo ID — deve retornar "ignorado"
curl -X POST http://localhost:5000/log \
  -H "Content-Type: application/json" \
  -d '{"id":"teste-123","tipo":"BRUTE_FORCE","ip":"10.0.0.1","servidor":"srv-01","descricao":"Teste","timestamp":"2024-01-01T00:00:00"}'
```

Resposta esperada na segunda chamada:
```json
{"status": "ignorado", "motivo": "já processado"}
```

---

## 🔥 Demonstração do Fallback

Para demonstrar o fallback ao vivo, abra **dois terminais**:

**Terminal 1** — logs do Processor em tempo real:
```bash
docker compose logs -f processor
```

**Terminal 2** — comandos de controle:

```bash
# 1. Derruba o Alert Service
docker stop logsec-alert

# Observe no Terminal 1 o Processor tentando 3x e ativando o fallback:
# PROCESSOR WARNING — Timeout ao contatar Alert Service (tentativa 1)
# PROCESSOR INFO    — Aguardando 1s...
# PROCESSOR WARNING — Timeout ao contatar Alert Service (tentativa 2)
# PROCESSOR INFO    — Aguardando 2s...
# PROCESSOR WARNING — Timeout ao contatar Alert Service (tentativa 3)
# PROCESSOR ERROR   — FALLBACK: alerta salvo em /tmp/alertas_fallback.jsonl

# 2. Confirma que o arquivo de fallback foi criado
docker exec logsec-processor cat /tmp/alertas_fallback.jsonl

# 3. Sobe o Alert de volta
docker start logsec-alert

# O sistema volta ao normal automaticamente
```

---

## 🛠️ Tecnologias

| Tecnologia | Uso |
|-----------|-----|
| Python 3.11 | Linguagem principal |
| Flask 3.0 | Framework web para as APIs |
| Gunicorn 21.2 | Servidor WSGI de produção (2 workers) |
| Requests 2.31 | Chamadas HTTP entre serviços |
| Docker | Containerização dos serviços |
| Docker Compose | Orquestração e rede entre containers |

---

## 👩‍💻 Autora

**Nicolly Dias**
Trabalho prático — Disciplina de Sistemas Distribuídos
Adaptado do TCC em desenvolvimento sobre monitoramento de segurança corporativa.
