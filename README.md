# ultimate_SMC

Repositorio com engine de **Smart Money Concepts (SMC)** para analise, backtest, simulacao de execucao no MT5 e operacao em tempo real.

O projeto esta organizado em torno de um engine candle a candle, sem look-ahead bias, e inclui:

- API REST/WebSocket com FastAPI
- bot live conectado ao MetaTrader 5
- scripts de backtest e validacao
- alertas por Telegram e webhook
- empacotamento Docker para a API

## Visao Geral

Os fluxos principais do repositorio sao:

- `smc_engine_v3.py`: engine principal, com Order Blocks, BOS, CHoCH, FVG, liquidity sweeps, score de confianca e ordens limit
- `main.py`: API em tempo real para receber candles, listar sinais, ordens e estatisticas
- `smc_trader_live.py`: robo de execucao live no MetaTrader 5
- `backtest_*.py`: scripts de backtest, simulacao e comparacao
- `alerts.py`: envio de notificacoes para Telegram e webhook
- `smc_realtime/`: copia empacotada da API para uso isolado com Docker

## Estrategia

O engine trabalha com a seguinte logica:

1. detecta swings
2. confirma Order Blocks a partir de rompimentos
3. cruza o contexto com BOS, CHoCH, FVG e sweep
4. cria ordens pendentes por retracao no Order Block
5. gerencia fill, expiracao, cancelamento e fechamento
6. calcula confianca do sinal e estatisticas operacionais

## Requisitos

- Python 3.11 ou superior
- MetaTrader 5 Desktop instalado e conectado para fluxos live e backtests baseados em MT5
- Docker e Docker Compose apenas se voce quiser rodar a API em container

Instalacao base:

```bash
pip install -r requirements.txt
```

Para os scripts que usam MT5 e graficos, instale tambem:

```bash
pip install MetaTrader5 matplotlib
```

## Configuracao

O arquivo [`.env.example`](.env.example) traz as variaveis da API:

- `SERVER_HOST` e `SERVER_PORT`
- `SWING_LENGTH`
- `RISK_REWARD_RATIO`
- `MIN_VOLUME_RATIO`
- `MIN_OB_SIZE_ATR`
- `MAX_PENDING_ORDERS`
- `MAX_CANDLES_HISTORY`
- `USE_NOT_MITIGATED_FILTER`
- `SUPPORTED_SYMBOLS`
- `ALERT_TELEGRAM_BOT_TOKEN`
- `ALERT_TELEGRAM_CHAT_ID`
- `ALERT_WEBHOOK_URL`
- `LOG_LEVEL`

Crie seu `.env` a partir do exemplo antes de subir a API.

## Rodando a API

Execucao local:

```bash
python main.py
```

Ou com uvicorn:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

Health check:

```bash
curl http://localhost:8000/
```

Endpoints principais:

- `GET /`
- `POST /engine/create`
- `POST /candle`
- `POST /candles/batch`
- `GET /orders/pending`
- `GET /orders/filled`
- `GET /orders/closed`
- `DELETE /orders/{order_id}`
- `GET /stats`
- `GET /order_blocks`
- `WS /ws`

Exemplo de cliente:

```bash
python client_example.py
```

## Rodando com Docker

O repositorio raiz ja contem `Dockerfile` e `docker-compose.yml` para a API:

```bash
docker compose up --build
```

Tambem existe uma versao empacotada em [`smc_realtime/README.md`](smc_realtime/README.md) caso voce queira usar a estrutura separada.

## Trading Live no MT5

O script [`smc_trader_live.py`](smc_trader_live.py) conecta ao MetaTrader 5, detecta o simbolo `WIN*`, aquece o engine com historico M1 e envia ordens automaticamente.

Execucao:

```bash
python smc_trader_live.py
```

Observacoes importantes:

- o MT5 precisa estar aberto e autenticado
- o script usa a classe `Config` interna para tamanho de lote, RR, SL maximo, retracao e filtros
- alertas de Telegram sao opcionais e leem `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID`
- os logs sao gravados em `smc_trader.log`

## Backtests e Simulacoes

Alguns scripts centrais do repositorio:

- `backtest_2026_mt5.py`: puxa candles do MT5, roda o engine otimizado e grava saidas em `resultado_2026/`
- `backtest_mt5_sim.py`: simula comportamento realista de fill/SL/TP do MT5 e grava saidas em `resultado_mt5_sim/`
- `backtest_2025_mt5.py`, `backtest_week.py`, `backtest_mtf.py`, `backtest_timeframes.py`: variacoes de recorte e validacao
- `plot_mtf_trades.py` e `plot_obs.py`: geracao de imagens auxiliares

Exemplos:

```bash
python backtest_2026_mt5.py
python backtest_mt5_sim.py
```

As pastas de resultado sao geradas pelos scripts e ficam fora do versionamento por padrao.

## Estrutura do Repositorio

```text
ultimate_SMC/
|- main.py
|- smc_engine_v3.py
|- smc_trader_live.py
|- alerts.py
|- settings.py
|- client_example.py
|- backtest_*.py
|- validate_*.py
|- plot_*.py
|- smc_realtime/
|- resultado_2025/          # gerado
|- resultado_2026/          # gerado
|- resultado_mt5_sim/       # gerado
|- trades_hoje/             # gerado
|- trades_janeiro/          # gerado
`- trades_mes/              # gerado
```

## Notas

- O `requirements.txt` cobre a API e utilitarios principais. Fluxos com MT5 e graficos exigem dependencias adicionais.
- O repositorio contem scripts de pesquisa, validacao e comparacao, alem do fluxo principal de execucao.
- O projeto foi preparado para publicar apenas codigo e configuracoes; logs, imagens, zips e resultados ficam ignorados no Git.
