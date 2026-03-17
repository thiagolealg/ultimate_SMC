"""
Teste final do Engine V3 com dados grandes (win.txt - 2M candles)
"""
import sys
sys.path.insert(0, 'app')
import pandas as pd
from smc_engine_v3 import SMCEngineV3

# Carregar dados
# Tentar detectar separador
with open('/home/ubuntu/upload/win.txt', 'r') as f:
    first_line = f.readline()
    
if '\t' in first_line:
    sep = '\t'
else:
    sep = ','

df = pd.read_csv('/home/ubuntu/upload/win.txt', sep=sep)
df.columns = [c.strip().lower() for c in df.columns]
print(f"Colunas: {list(df.columns)}")

# Normalizar colunas
col_map = {}
for c in df.columns:
    cl = c.lower().strip()
    if 'open' in cl: col_map[c] = 'open'
    elif 'high' in cl: col_map[c] = 'high'
    elif 'low' in cl: col_map[c] = 'low'
    elif 'close' in cl: col_map[c] = 'close'
    elif 'tick' in cl and 'vol' in cl: col_map[c] = 'tick_volume'
    elif 'vol' in cl: col_map[c] = 'volume'
    elif 'time' in cl or 'date' in cl: col_map[c] = 'time'
df = df.rename(columns=col_map)

vol_col = 'tick_volume' if 'tick_volume' in df.columns else 'volume'
print(f"Dados: {len(df)} candles")

# Engine V3
engine = SMCEngineV3(
    symbol='WIN', swing_length=5, risk_reward_ratio=3.0,
    min_volume_ratio=1.5, min_ob_size_atr=0.5,
    use_not_mitigated_filter=True, max_pending_candles=100,
    entry_delay_candles=1,
)

for i in range(len(df)):
    row = df.iloc[i]
    engine.add_candle({
        'open': float(row['open']),
        'high': float(row['high']),
        'low': float(row['low']),
        'close': float(row['close']),
        'volume': float(row[vol_col]) if vol_col in df.columns else 1.0
    })
    if (i + 1) % 500000 == 0:
        print(f"  Processados {i+1} candles...")

trades = engine.get_all_trades()
wins = [t for t in trades if t['status'] == 'closed_tp']
losses = [t for t in trades if t['status'] == 'closed_sl']
total = len(wins) + len(losses)

total_profit = sum(t['profit_loss'] for t in trades if t['status'] in ['closed_tp', 'closed_sl'])
total_win = sum(t['profit_loss'] for t in wins)
total_loss_pts = sum(abs(t['profit_loss']) for t in losses)
pf = total_win / total_loss_pts if total_loss_pts > 0 else float('inf')

win_r = len(wins) * 3
loss_r = len(losses)
lucro_r = win_r - loss_r

print(f"\n{'='*80}")
print(f"RESULTADO ENGINE V3 - RR 3:1 - SEM LOOK-AHEAD")
print(f"{'='*80}")
print(f"  Total Trades: {total}")
print(f"  Vencedores: {len(wins)}")
print(f"  Perdedores: {len(losses)}")
print(f"  Win Rate: {len(wins)/total*100:.1f}%")
print(f"  Profit Factor: {pf:.2f}")
print(f"  Lucro Total: {total_profit:+,.2f} pontos")
print(f"  Lucro em R: {lucro_r}R")
print(f"  Expectativa: {lucro_r/total:.2f}R/trade")

# Validação
invalid = sum(1 for t in trades if t['filled_at'] <= t['created_at'])
print(f"\n  Violações temporais: {invalid} {'✅' if invalid == 0 else '❌'}")
same_candle = sum(1 for t in trades if t['filled_at'] == t['created_at'])
print(f"  Fill no mesmo candle: {same_candle} {'✅' if same_candle == 0 else '❌'}")

mit_before = 0
for t in engine.closed_trades:
    if t.ob.mitigated and t.ob.mitigated_index < t.filled_at:
        mit_before += 1
print(f"  OBs mitigados antes do fill: {mit_before} {'✅' if mit_before == 0 else '❌'}")
