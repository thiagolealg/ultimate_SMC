# Smart Money Concepts Enhanced

Biblioteca Python para análise de mercado baseada em Smart Money Concepts (SMC), com estratégia de Order Block 3:1 e medição de confiança.

## Características Principais

- **Fair Value Gap (FVG)**: Detecta gaps de valor justo bullish e bearish
- **Swing Highs/Lows**: Identifica pontos de reversão do mercado
- **Break of Structure (BOS)**: Detecta quebras de estrutura de mercado
- **Change of Character (CHoCH)**: Identifica mudanças de caráter do mercado
- **Order Blocks (OB)**: Detecta zonas de acumulação institucional com medição de confiança
- **Liquidity**: Identifica zonas de liquidez
- **Retracements**: Calcula retrações de preço

## Estratégia Order Block 3:1

A estratégia implementada inclui:

1. **Risk:Reward 3:1**: Take Profit é 3x o risco (Stop Loss)
2. **Medição de Confiança**: Cada Order Block recebe uma pontuação de 0-100% baseada em:
   - Volume do Order Block
   - Presença de FVG próximo
   - Presença de BOS/CHoCH
   - Tamanho do OB em relação ao movimento médio
3. **Entrada Atrasada**: As entradas **NÃO** ocorrem no mesmo candle do sinal, garantindo que o trader tenha tempo para avaliar o setup

## Instalação

```bash
# Clonar ou copiar os arquivos para seu projeto
cp smc_enhanced.py /seu/projeto/

# Dependências
pip install pandas numpy
```

## Uso Básico

### Indicadores SMC

```python
import pandas as pd
from smc_enhanced import SMCEnhanced

# Carregar dados OHLCV
df = pd.read_csv('seus_dados.csv')
df['time'] = pd.to_datetime(df['time'])
df.set_index('time', inplace=True)

# Calcular Swing Highs/Lows
swing_hl = SMCEnhanced.swing_highs_lows(df, swing_length=5)

# Calcular FVG
fvg = SMCEnhanced.fvg(df)

# Calcular Order Blocks
ob = SMCEnhanced.ob(df, swing_hl)

# Calcular BOS/CHoCH
bos_choch = SMCEnhanced.bos_choch(df, swing_hl)

# Calcular Liquidity
liq = SMCEnhanced.liquidity(df, swing_hl)

# Calcular Retracements
ret = SMCEnhanced.retracements(df, swing_hl)
```

### Estratégia Order Block 3:1

```python
from smc_enhanced import OrderBlockStrategy, SignalDirection

# Criar estratégia
strategy = OrderBlockStrategy(
    df,
    swing_length=5,           # Comprimento do swing
    risk_reward_ratio=3.0,    # 3:1 Risk:Reward
    min_confidence=50.0,      # Confiança mínima de 50%
    entry_delay_candles=1,    # Entrada 1 candle após o sinal
)

# Gerar sinais
signals = strategy.generate_signals()

# Verificar sinais
for signal in signals:
    direction = "LONG" if signal.direction == SignalDirection.BULLISH else "SHORT"
    print(f"{direction} | Entry: {signal.entry_price:.2f} | SL: {signal.stop_loss:.2f} | TP: {signal.take_profit:.2f} | Conf: {signal.confidence:.1f}%")

# Executar backtest
results, stats = strategy.backtest(signals)

print(f"Win Rate: {stats['win_rate']:.1f}%")
print(f"Profit Factor: {stats['profit_factor']:.2f}")
print(f"Total P/L: {stats['total_profit_loss']:.2f}")
```

### Análise Completa

```python
# Obter DataFrame com todos os indicadores
analysis_df = strategy.get_analysis_dataframe()

# Colunas disponíveis:
# - open, high, low, close, volume
# - SwingHighLow, SwingLevel
# - OB, OB_Top, OB_Bottom, OB_Volume, OB_Percentage, OB_Confidence
# - FVG, FVG_Top, FVG_Bottom
# - BOS, CHOCH, BOS_CHOCH_Level

# Filtrar Order Blocks com alta confiança
high_conf = analysis_df[analysis_df['OB_Confidence'] >= 60]
```

## Estrutura do Sinal (TradeSignal)

```python
@dataclass
class TradeSignal:
    index: int                    # Índice do candle de entrada
    direction: SignalDirection    # BULLISH ou BEARISH
    entry_price: float            # Preço de entrada
    stop_loss: float              # Stop Loss
    take_profit: float            # Take Profit
    confidence: float             # Confiança (0-100%)
    ob_top: float                 # Topo do Order Block
    ob_bottom: float              # Fundo do Order Block
    risk_reward_ratio: float      # Ratio R:R
    signal_candle_index: int      # Índice do candle que gerou o sinal
```

## Estrutura do Resultado de Backtest (BacktestResult)

```python
@dataclass
class BacktestResult:
    signal: TradeSignal           # Sinal original
    entry_index: int              # Índice de entrada
    exit_index: int               # Índice de saída
    exit_price: float             # Preço de saída
    profit_loss: float            # Lucro/Prejuízo
    profit_loss_percent: float    # L/P em percentual
    hit_tp: bool                  # Atingiu Take Profit
    hit_sl: bool                  # Atingiu Stop Loss
    duration_candles: int         # Duração em candles
```

## Estatísticas do Backtest

```python
stats = {
    'total_trades': int,          # Total de trades
    'winning_trades': int,        # Trades vencedores
    'losing_trades': int,         # Trades perdedores
    'win_rate': float,            # Taxa de acerto (%)
    'total_profit_loss': float,   # P/L total
    'avg_profit_loss': float,     # P/L médio
    'avg_win': float,             # Média de ganhos
    'avg_loss': float,            # Média de perdas
    'profit_factor': float,       # Fator de lucro
    'avg_confidence': float,      # Confiança média
    'avg_duration': float,        # Duração média
    'hit_tp_count': int,          # Quantidade que atingiu TP
    'hit_sl_count': int,          # Quantidade que atingiu SL
}
```

## Cálculo de Confiança

A confiança de cada Order Block é calculada com base em:

| Fator | Pontuação Máxima |
|-------|------------------|
| Volume/Percentage do OB | 25 pontos |
| Presença de FVG na mesma direção | 25 pontos |
| Presença de BOS na mesma direção | 15 pontos |
| Presença de CHoCH na mesma direção | 10 pontos |
| Tamanho do OB adequado | 15 pontos |
| Volume do OB acima da média | 10 pontos |
| **Total Máximo** | **100 pontos** |

## Garantia de Entrada Atrasada

O parâmetro `entry_delay_candles` garante que a entrada **nunca** ocorra no mesmo candle do sinal:

```python
strategy = OrderBlockStrategy(
    df,
    entry_delay_candles=1,  # Mínimo 1 candle de atraso
)

# Verificação
for signal in signals:
    assert signal.index > signal.signal_candle_index
    # signal.index = candle de entrada
    # signal.signal_candle_index = candle que gerou o sinal
```

## Arquivos do Projeto

- `smc_enhanced.py` - Módulo principal com todos os indicadores e estratégia
- `test_real_data.py` - Testes com dados reais
- `example_usage.py` - Exemplos de uso
- `data.csv` - Dados de exemplo
- `analysis_report.csv` - Relatório de análise gerado

## Requisitos

- Python 3.8+
- pandas
- numpy

## Baseado em

Este projeto é baseado no repositório [joshyattridge/smart-money-concepts](https://github.com/joshyattridge/smart-money-concepts) com as seguintes melhorias:

1. Correção de erros e robustez
2. Estratégia 3:1 com medição de confiança
3. Garantia de entrada atrasada
4. Backtesting integrado
5. Documentação completa

## Licença

MIT License
