# Smart Money Concepts Enhanced - VERSÃO FINAL

Biblioteca Python para análise de mercado baseada em Smart Money Concepts (SMC), com estratégia de Order Block 3:1 e medição de confiança.

## IMPORTANTE: Versões Disponíveis

Este pacote contém **duas versões**:

### 1. `smc_enhanced.py` - Versão Original (COM Look-Ahead Bias)
- **NÃO USE PARA TRADING REAL**
- Usa dados futuros para identificar swings (look-ahead bias)
- Win Rate artificialmente inflado (~97%)
- Útil apenas para estudo do código original

### 2. `smc_final.py` - Versão Corrigida (SEM Look-Ahead Bias) ⭐
- **USE ESTA VERSÃO PARA TRADING REAL**
- Não usa dados futuros
- Win Rate realista (~43% com RR 3:1)
- Profit Factor ~2.0 (realista e lucrativo)
- Validada com testes rigorosos

## Evidência do Look-Ahead Bias

| Métrica | Versão Original | Versão Corrigida |
|---------|-----------------|------------------|
| Win Rate | 97.9% (irreal) | 43.1% (realista) |
| Profit Factor | 72.81 | 2.05 |
| Sinais | 48 | 1.681 |

A diferença de **54.8% no Win Rate** era causada pelo uso de dados futuros.

## Instalação

```bash
pip install pandas numpy
```

## Uso da Versão Corrigida

```python
import pandas as pd
from smc_final import OrderBlockStrategyFinal, SignalDirection

# Carregar dados
df = pd.read_csv('seus_dados.csv')
df['time'] = pd.to_datetime(df['time'])
df.set_index('time', inplace=True)

# Criar estratégia
strategy = OrderBlockStrategyFinal(
    df,
    swing_length=5,           # Candles para confirmar swing
    risk_reward_ratio=3.0,    # 3:1 Risk:Reward
    min_confidence=30.0,      # Confiança mínima
    entry_delay_candles=1,    # Entrada após o sinal
)

# Gerar sinais
signals = strategy.generate_signals()

# Backtest
results, stats = strategy.backtest(signals)

print(f"Win Rate: {stats['win_rate']:.1f}%")
print(f"Profit Factor: {stats['profit_factor']:.2f}")
```

## Como Funciona (Sem Look-Ahead)

### 1. Detecção de Swings
```
Swing High no índice i é CONFIRMADO no índice i + swing_length
quando todos os candles de i+1 até i+swing_length têm máximas menores.
```

### 2. Detecção de Order Blocks
```
1. Esperar swing ser confirmado
2. Esperar preço romper o swing
3. Marcar OB no candle de ROMPIMENTO (não na formação)
```

### 3. Geração de Sinais
```
1. OB é confirmado no índice i
2. Esperar entry_delay_candles (mínimo 1)
3. Procurar entrada quando preço retorna ao OB
4. Entrada sempre em j > i
```

## Estrutura do Sinal

```python
@dataclass
class TradeSignal:
    index: int                    # Índice de ENTRADA
    direction: SignalDirection    # BULLISH ou BEARISH
    entry_price: float            # Preço de entrada
    stop_loss: float              # Stop Loss
    take_profit: float            # Take Profit (3x o risco)
    confidence: float             # Confiança (0-100%)
    ob_top: float                 # Topo do Order Block
    ob_bottom: float              # Fundo do Order Block
    signal_candle_index: int      # Índice onde OB foi CONFIRMADO
    ob_candle_index: int          # Índice do candle que FORMA o OB
```

**Garantia temporal:**
- `ob_candle_index` < `signal_candle_index` < `index`
- Entrada NUNCA ocorre no mesmo candle do sinal

## Cálculo de Confiança

| Fator | Pontuação |
|-------|-----------|
| Volume/Percentage do OB | 0-25 |
| FVG na mesma direção (ANTES do OB) | 0-25 |
| BOS na mesma direção (ANTES do OB) | 0-15 |
| CHoCH na mesma direção (ANTES do OB) | 0-10 |
| Tamanho adequado do OB | 0-15 |
| Volume acima da média | 0-10 |
| **Total Máximo** | **100** |

**IMPORTANTE:** A confiança usa apenas dados ANTERIORES ao OB.

## Resultados Esperados

Com a configuração padrão (RR 3:1, confiança 30%):

| Métrica | Valor Esperado |
|---------|----------------|
| Win Rate | 40-45% |
| Profit Factor | 1.8-2.2 |
| Expectativa | Positiva |

**Nota:** Um Win Rate de 43% com RR 3:1 significa:
- 43 trades ganham 3R cada = 129R
- 57 trades perdem 1R cada = 57R
- **Lucro líquido = 72R por 100 trades**

## Arquivos do Projeto

| Arquivo | Descrição |
|---------|-----------|
| `smc_final.py` | **USE ESTE** - Versão corrigida sem look-ahead |
| `smc_enhanced.py` | Versão original (apenas para referência) |
| `validate_no_lookahead.py` | Testes de validação |
| `example_usage.py` | Exemplos de uso |
| `data.csv` | Dados de exemplo |

## Validação

Execute os testes para verificar a integridade:

```bash
python3 validate_no_lookahead.py
```

Testes incluídos:
1. **Timing dos Sinais** - Entrada sempre após o sinal
2. **Confirmação de OBs** - OBs marcados após confirmação
3. **Simulação Tempo Real** - Processamento candle a candle
4. **Integridade Backtest** - Saída sempre após entrada

## Licença

MIT License

## Créditos

Baseado em [joshyattridge/smart-money-concepts](https://github.com/joshyattridge/smart-money-concepts)
