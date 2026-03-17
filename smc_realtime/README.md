# SMC Realtime API

API para estratégias **Smart Money Concepts** em tempo real com Docker.

## Características

- **Processamento em tempo real** - Recebe dados minuto a minuto
- **Todas as estratégias SMC** - Order Blocks, BOS, CHoCH, FVG, Sweep, Wyckoff
- **Ordens pendentes (Limit)** - Entrada na linha do meio do OB
- **Filtros de qualidade** - OB não mitigado, Volume, Tamanho ATR
- **Índice de confiança** - Para alavancagem de contratos
- **Alertas** - Telegram e Webhook
- **WebSocket** - Comunicação bidirecional em tempo real

## Resultados do Backtest

| R:R | Trades | Win Rate | Lucro Total |
|-----|--------|----------|-------------|
| 3:1 | 4.720 | 45.3% | **98.816 pontos** |
| 1:1 | 4.720 | 70.0% | 59.735 pontos |

*Testado com 2.099.880 candles (16 anos de dados)*

## Instalação

### Pré-requisitos

- Docker
- Docker Compose

### Iniciar

```bash
# Clonar ou copiar os arquivos
cd smc_realtime

# Configurar variáveis de ambiente (opcional)
cp .env.example .env
nano .env

# Iniciar
docker-compose up -d

# Verificar logs
docker-compose logs -f
```

### Verificar se está rodando

```bash
curl http://localhost:8000/
```

Resposta esperada:
```json
{
  "status": "online",
  "service": "SMC Realtime API",
  "version": "1.0.0"
}
```

## Uso

### 1. Enviar Candle (REST API)

```bash
curl -X POST http://localhost:8000/candle \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "WINM24",
    "time": "2024-01-01 09:00:00",
    "open": 100000,
    "high": 100100,
    "low": 99900,
    "close": 100050,
    "volume": 1000
  }'
```

### 2. Enviar Múltiplos Candles

```bash
curl -X POST http://localhost:8000/candles/batch \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "WINM24",
    "candles": [
      {"time": "2024-01-01 09:00:00", "open": 100000, "high": 100100, "low": 99900, "close": 100050, "volume": 1000},
      {"time": "2024-01-01 09:01:00", "open": 100050, "high": 100150, "low": 99950, "close": 100100, "volume": 1200}
    ]
  }'
```

### 3. Obter Estatísticas

```bash
curl http://localhost:8000/stats?symbol=WINM24
```

### 4. Obter Ordens Pendentes

```bash
curl http://localhost:8000/orders/pending?symbol=WINM24
```

### 5. Obter Order Blocks

```bash
curl http://localhost:8000/order_blocks?symbol=WINM24&limit=10
```

## WebSocket

Conecte via WebSocket para comunicação em tempo real:

```javascript
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onopen = () => {
  console.log('Conectado');
  
  // Enviar candle
  ws.send(JSON.stringify({
    action: 'candle',
    data: {
      symbol: 'WINM24',
      time: '2024-01-01 09:00:00',
      open: 100000,
      high: 100100,
      low: 99900,
      close: 100050,
      volume: 1000
    }
  }));
};

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  
  if (msg.type === 'signal') {
    console.log('Novo sinal:', msg.data);
  }
};
```

## Integração com MT5

1. Copie o arquivo `mt5_connector/SMC_DataSender.mq5` para a pasta `MQL5/Experts/`
2. No MT5, vá em **Ferramentas > Opções > Expert Advisors**
3. Marque "Permitir WebRequest para URLs listadas"
4. Adicione: `http://localhost:8000`
5. Compile e anexe o EA ao gráfico

## Configuração

### Variáveis de Ambiente

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `SWING_LENGTH` | 5 | Tamanho do swing para detecção |
| `RISK_REWARD_RATIO` | 3.0 | Relação risco/recompensa |
| `MIN_VOLUME_RATIO` | 1.5 | Volume mínimo vs média |
| `MIN_OB_SIZE_ATR` | 0.5 | Tamanho mínimo do OB vs ATR |
| `USE_NOT_MITIGATED_FILTER` | true | Usar apenas OBs não mitigados |

### Alertas Telegram

1. Crie um bot no [@BotFather](https://t.me/BotFather)
2. Obtenha o token do bot
3. Obtenha seu chat_id (envie mensagem para [@userinfobot](https://t.me/userinfobot))
4. Configure no `.env`:

```env
ALERT_TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
ALERT_TELEGRAM_CHAT_ID=987654321
```

## Endpoints da API

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/` | Health check |
| POST | `/candle` | Enviar um candle |
| POST | `/candles/batch` | Enviar múltiplos candles |
| GET | `/stats` | Estatísticas do engine |
| GET | `/orders/pending` | Ordens pendentes |
| GET | `/orders/filled` | Ordens preenchidas |
| GET | `/orders/closed` | Histórico de ordens |
| DELETE | `/orders/{id}` | Cancelar ordem |
| GET | `/order_blocks` | Order Blocks detectados |
| WS | `/ws` | WebSocket |

## Estrutura de Arquivos

```
smc_realtime/
├── app/
│   ├── main.py           # API FastAPI
│   ├── smc_engine.py     # Engine de estratégias
│   └── alerts.py         # Serviço de alertas
├── config/
│   └── settings.py       # Configurações
├── mt5_connector/
│   └── SMC_DataSender.mq5  # EA para MT5
├── data/                 # Dados persistentes
├── logs/                 # Logs da aplicação
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── client_example.py     # Cliente Python de exemplo
└── README.md
```

## Licença

MIT License
