# Ultimate SMC — Smart Money Concepts Trading Engine

Sistema completo de detecção de **Order Blocks** e execução de trades baseado em Smart Money Concepts (SMC), com API REST/WebSocket em tempo real, backtest engine, dashboard de métricas e integração com MetaTrader 5.

---

## Arquitetura do Projeto

```
ultimate_SMC/
├── smc_engine_v3.py              # Engine principal de backtest (versão mais recente, corrigida)
├── smc_engine_v2.py              # Engine V2 (legado)
├── smc_engine.py                 # Engine V1 (legado)
├── main.py                       # API FastAPI (raiz) — usa smc_engine.py
├── smc_trader_live.py            # Robô de execução live no MetaTrader 5
├── settings.py                   # Configurações via variáveis de ambiente
├── alerts.py                     # Alertas Telegram/Webhook
├── requirements.txt              # Dependências Python
├── Dockerfile                    # Container da API (raiz)
├── docker-compose.yml            # Orquestração Docker (raiz)
│
├── smc_realtime/                 # API Realtime (versão dedicada, corrigida)
│   ├── app/
│   │   ├── main.py               # FastAPI app com WebSocket
│   │   ├── smc_engine.py         # Engine realtime (com 6 correções aplicadas)
│   │   └── alerts.py             # Sistema de alertas
│   ├── config/settings.py        # Configurações
│   ├── mt5_connector/
│   │   └── SMC_DataSender.mq5    # Expert Advisor para MetaTrader 5
│   ├── Dockerfile                # Container da API realtime
│   ├── docker-compose.yml        # Orquestração Docker realtime (porta 8001)
│   ├── requirements.txt          # Dependências Python
│   └── client_example.py         # Exemplo de cliente WebSocket
│
├── dashboard/                    # Dashboard Web (React + TailwindCSS)
│   ├── client/
│   │   ├── index.html            # HTML entry point
│   │   └── src/
│   │       ├── App.tsx           # Roteamento principal
│   │       ├── index.css         # Tema Terminal Quant (dark, Bloomberg-inspired)
│   │       ├── pages/
│   │       │   └── Dashboard.tsx # Página principal do dashboard
│   │       ├── components/
│   │       │   ├── CandlestickChart.tsx   # Gráfico candlestick + OBs (lightweight-charts v5)
│   │       │   ├── KpiCard.tsx            # Cards de métricas
│   │       │   ├── TradeValidation.tsx    # Validação entrada/saída (10 checks)
│   │       │   ├── OrderBlocksTable.tsx   # Tabela de Order Blocks
│   │       │   ├── TradesTable.tsx        # Tabela de trades
│   │       │   ├── AccumulationChart.tsx  # Gráfico de acúmulo de memória
│   │       │   └── EngineConfig.tsx       # Config da engine
│   │       └── data/
│   │           └── backtest-data.json     # Dados exportados da engine V3
│   ├── server/index.ts           # Servidor Express (produção)
│   ├── package.json              # Dependências Node.js (React 19, Vite 7, etc.)
│   ├── tsconfig.json             # Config TypeScript
│   └── vite.config.ts            # Config Vite
│
├── SMC_DataSender.mq5            # Expert Advisor MetaTrader 5 (cópia raiz)
├── export_data.py                # Exporta dados da engine V3 para JSON (dashboard)
├── validate_entry_exit.py        # Validação de entrada/saída (10 checks por trade)
├── audit_obs.py                  # Auditoria de acúmulo de OBs
├── audit_performance.py          # Análise de performance estrutural
├── visualize_obs.py              # Gerador de visualizações matplotlib
├── test_fixes.py                 # Testes das 6 correções aplicadas
├── backtest_*.py                 # Scripts de backtest variados
├── validate_*.py                 # Scripts de validação variados
├── Relatorio_Auditoria_SMC.md    # Relatório completo da auditoria
└── ob_detection_audit.png        # Visualização do estado da detecção de OBs
```

---

## Pré-requisitos

| Componente | Versão Mínima | Uso |
|---|---|---|
| Python | 3.11+ | Engine, API, backtest, scripts |
| Node.js | 18+ | Dashboard web |
| pnpm | 8+ | Gerenciador de pacotes do dashboard |
| Docker | 20+ | Deploy containerizado (opcional) |
| Docker Compose | 2.0+ | Orquestração de serviços (opcional) |
| MetaTrader 5 | Build 3000+ | Envio de dados de mercado (opcional, só para live) |

---

## Deploy Completo — Passo a Passo para Agentes de IA

Este guia cobre o deploy de todos os componentes do sistema. Siga na ordem.

### Passo 1: Clonar o Repositório

```bash
git clone https://github.com/thiagolealg/ultimate_SMC.git
cd ultimate_SMC
```

### Passo 2: Instalar Dependências Python

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Para scripts que usam MetaTrader 5 e gráficos, instale também:

```bash
pip install MetaTrader5 matplotlib
```

### Passo 3: Configurar Variáveis de Ambiente

Crie um arquivo `.env` na raiz com as seguintes variáveis (ajuste conforme necessário):

```bash
# Servidor
SERVER_HOST=0.0.0.0
SERVER_PORT=8000

# Engine SMC
SWING_LENGTH=5
RISK_REWARD_RATIO=3.0
MIN_VOLUME_RATIO=1.5
MIN_OB_SIZE_ATR=0.5
MAX_PENDING_ORDERS=10
MAX_CANDLES_HISTORY=5000
USE_NOT_MITIGATED_FILTER=true

# Símbolos suportados
SUPPORTED_SYMBOLS=WINM24,WDOM24,PETR4,VALE3

# Alertas (opcional)
ALERT_TELEGRAM_BOT_TOKEN=
ALERT_TELEGRAM_CHAT_ID=
ALERT_WEBHOOK_URL=

# Logging
LOG_LEVEL=INFO
```

### Passo 4: Subir a API (Opção A — Docker)

```bash
# Na raiz do repositório
docker-compose up -d --build

# Verificar se está rodando
curl http://localhost:8000/
# Resposta esperada: {"status": "ok", "engine": "SMC Realtime API", ...}

# Ver logs
docker-compose logs -f
```

### Passo 4: Subir a API (Opção B — Sem Docker)

```bash
# Na raiz do repositório, com virtualenv ativado
python -m uvicorn main:app --host 0.0.0.0 --port 8000

# OU para a versão realtime dedicada (porta 8001):
cd smc_realtime/app
python -m uvicorn main:app --host 0.0.0.0 --port 8001
```

### Passo 5: Subir o Dashboard Web

```bash
# Entrar no diretório do dashboard
cd dashboard

# Instalar dependências Node.js
pnpm install

# Modo desenvolvimento (hot reload, porta 5173)
pnpm dev --host

# OU build para produção (porta 3000)
pnpm build
pnpm start
```

O dashboard estará disponível em `http://localhost:5173` (dev) ou `http://localhost:3000` (prod).

### Passo 6: Atualizar Dados do Dashboard

Para regenerar os dados do dashboard com novos dados de mercado:

```bash
# Na raiz do repositório, com virtualenv ativado
# Coloque seu CSV de candles M1 como mtwin14400.csv (ou altere o nome no export_data.py)
python3 export_data.py

# O JSON será salvo em dashboard/client/src/data/backtest-data.json
# Depois faça rebuild do dashboard:
cd dashboard && pnpm build
```

### Passo 7: Verificar Tudo

```bash
# API respondendo
curl http://localhost:8000/

# Dashboard acessível
curl -s http://localhost:3000/ | head -5

# Testes das correções
cd /caminho/para/ultimate_SMC
source venv/bin/activate
python3 test_fixes.py
# Esperado: 9/9 testes passando

# Validação de entrada/saída
python3 validate_entry_exit.py
# Esperado: 10/10 checks passando
```

---

## Endpoints da API

| Método | Endpoint | Descrição | Exemplo de Body |
|---|---|---|---|
| `GET` | `/` | Health check | — |
| `POST` | `/engine/create` | Cria engine para um símbolo | `{"symbol": "WINM24", "swing_length": 5}` |
| `POST` | `/candle` | Envia um candle | `{"symbol": "WINM24", "time": "2024-06-10 09:01:00", "open": 127000, "high": 127050, "low": 126980, "close": 127030, "volume": 1500}` |
| `POST` | `/candles/batch` | Envia múltiplos candles | `{"symbol": "WINM24", "candles": [...]}` |
| `GET` | `/orders/pending` | Ordens pendentes | — |
| `GET` | `/orders/filled` | Ordens preenchidas | — |
| `GET` | `/orders/closed` | Ordens fechadas | — |
| `DELETE` | `/orders/{order_id}` | Cancela uma ordem | — |
| `GET` | `/stats` | Estatísticas da engine | — |
| `GET` | `/order_blocks` | Lista Order Blocks | — |
| `WS` | `/ws` | WebSocket tempo real | — |

---

## Exemplo de Uso da API (Python)

```python
import requests

API_URL = "http://localhost:8000"

# Enviar um candle
candle = {
    "symbol": "WINM24",
    "time": "2024-06-10 09:01:00",
    "open": 127000.0,
    "high": 127050.0,
    "low": 126980.0,
    "close": 127030.0,
    "volume": 1500.0
}
response = requests.post(f"{API_URL}/candle", json=candle)
result = response.json()

if result.get("new_signals"):
    print("Novos sinais:", result["new_signals"])

if result.get("new_orders"):
    print("Novas ordens:", result["new_orders"])

# Consultar estatísticas
stats = requests.get(f"{API_URL}/stats").json()
print(f"Win Rate: {stats['win_rate']}%")
print(f"Total P&L: {stats['total_profit_points']} pts")
```

---

## Exemplo de Uso via WebSocket

```python
import asyncio
import websockets
import json

async def connect():
    async with websockets.connect("ws://localhost:8000/ws") as ws:
        while True:
            message = json.loads(await ws.recv())
            if message["type"] == "signal":
                print(f"SINAL: {message['data']['direction']} @ {message['data']['entry_price']}")
            elif message["type"] == "order_filled":
                print(f"FILL: {message['data']['order_id']}")
            elif message["type"] == "order_closed":
                print(f"CLOSE: {message['data']['pnl']} pts")

asyncio.run(connect())
```

---

## Rodar Backtest com Engine V3

```bash
cd ultimate_SMC
source venv/bin/activate

python3 -c "
from smc_engine_v3 import SMCEngineV3
import csv

engine = SMCEngineV3(
    swing_length=5,
    risk_reward_ratio=3.0,
    min_volume_ratio=0.0,
    min_ob_size_atr=0.0,
    use_not_mitigated_filter=True,
    max_pending_candles=150,
    entry_delay_candles=1,
)

with open('SEU_ARQUIVO.csv') as f:
    reader = csv.DictReader(f)
    for row in reader:
        engine.add_candle({
            'time': row['time'],
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
            'volume': float(row.get('volume', 1)),
        })

stats = engine.get_stats()
print(f'Trades: {stats[\"total_trades\"]}')
print(f'Win Rate: {stats[\"win_rate\"]}%')
print(f'P&L: {stats[\"total_profit_points\"]} pts')
print(f'Profit Factor: {stats[\"profit_factor\"]}')
"
```

---

## Trading Live no MetaTrader 5

O script `smc_trader_live.py` conecta ao MetaTrader 5, detecta o símbolo `WIN*`, aquece a engine com histórico M1 e envia ordens automaticamente.

```bash
# MT5 precisa estar aberto e autenticado
python smc_trader_live.py
```

O Expert Advisor `SMC_DataSender.mq5` (em `smc_realtime/mt5_connector/`) envia candles M1 do MT5 para a API. Para configurar:

1. Abra o MetaEditor no MetaTrader 5.
2. Crie um novo Expert Advisor e cole o conteúdo de `SMC_DataSender.mq5`.
3. Compile com F7.
4. Arraste o EA para o gráfico M1 do ativo desejado.
5. Configure o parâmetro `API_URL` para apontar para sua API (`http://localhost:8000` ou `http://SEU_SERVIDOR:8000`).
6. Ative "Allow WebRequest" nas opções do MT5 e adicione a URL da API.

---

## Rodar Testes e Validações

```bash
cd ultimate_SMC
source venv/bin/activate

# Testar as 6 correções da engine (GC, dedup, swings, sinais, bounds, expiração)
python3 test_fixes.py
# Esperado: 9/9 testes passando

# Validar entrada/saída dos trades (10 checks por trade, sem lookahead)
python3 validate_entry_exit.py
# Esperado: 10/10 checks passando, gera validation_entry_exit.png

# Auditoria de acúmulo de OBs na memória
python3 audit_obs.py

# Análise de performance estrutural
python3 audit_performance.py
```

---

## Correções Aplicadas na Engine (Auditoria 2024)

As seguintes correções foram aplicadas nas engines V3 (`smc_engine_v3.py`) e Realtime (`smc_realtime/app/smc_engine.py`):

| ID | Severidade | Problema Original | Correção Aplicada |
|---|---|---|---|
| FIX-1 | Crítico | `active_obs` nunca era limpo — OBs mitigados ficavam na memória para sempre, causando memory leak | Garbage Collector automático a cada 10 candles remove OBs mitigados sem ordens ativas |
| FIX-2 | Crítico | Engine Realtime gerava sinais repetidos para o mesmo OB a cada novo candle | Flag `ob.used` impede sinal duplicado; verifica pending, filled e closed antes de criar |
| FIX-3 | Alto | `swing_highs` e `swing_lows` cresciam infinitamente sem limite | Limitados a 200 entradas mais recentes (configurável via `MAX_SWING_HISTORY`) |
| FIX-4 | Alto | Divergência entre V3 e Realtime no cálculo dos limites do OB (sombra vs corpo) | Ambas engines agora usam corpo do candle (`open`/`close`) para calcular `top` e `bottom` |
| FIX-5 | Médio | Sem filtro de OBs duplicados ou sobrepostos na mesma região de preço | Calcula sobreposição entre OBs; rejeita novo OB se overlap > 50% com existente |
| FIX-6 | Médio | Ordens pendentes no Realtime ficavam abertas para sempre sem expiração | Expiração automática após 100 candles (configurável via `max_pending_candles`) |

---

## Formato do CSV de Entrada

```csv
time,open,high,low,close,volume
2024-06-10 09:00:00,127000.0,127050.0,126980.0,127030.0,1500.0
2024-06-10 09:01:00,127030.0,127060.0,127010.0,127045.0,1200.0
```

Os campos `time`, `open`, `high`, `low`, `close` e `volume` são obrigatórios. O timeframe padrão é M1 (1 minuto).

---

## Stack Tecnológico

| Camada | Tecnologia | Versão |
|---|---|---|
| Engine | Python (dataclasses, enum) | 3.11+ |
| API | FastAPI + Uvicorn | 0.104+ |
| WebSocket | FastAPI WebSocket | nativo |
| Dashboard Frontend | React 19 + TypeScript | 19.2+ |
| Estilização | TailwindCSS 4 + shadcn/ui | 4.1+ |
| Gráfico Candlestick | lightweight-charts (TradingView) | 5.0+ |
| Charts/Métricas | Recharts | 2.15+ |
| Build Tool | Vite 7 | 7.1+ |
| Container | Docker + Docker Compose | 20+ |
| Broker | MetaTrader 5 (MQL5) | Build 3000+ |

---

## Notas Importantes

O `requirements.txt` da raiz cobre a API e utilitários principais. Fluxos com MT5 e gráficos exigem dependências adicionais (`MetaTrader5`, `matplotlib`). O repositório contém scripts de pesquisa, validação e comparação além do fluxo principal de execução. Logs, imagens geradas, zips e resultados de backtest ficam ignorados no Git por padrão.

---

## Licença

Projeto privado. Todos os direitos reservados.
