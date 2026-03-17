"""
Análise Completa do Engine V3:
- Lucro por mês
- Drawdown máximo
- Validações detalhadas
"""
import sys
sys.path.insert(0, '/home/ubuntu/smc_realtime/app')
import pandas as pd
import numpy as np
from smc_engine_v3 import SMCEngineV3, OrderStatus, SignalDirection

# ============================================================
# CARREGAR DADOS
# ============================================================
print("Carregando dados mtwin14400.csv...")
df = pd.read_csv('/home/ubuntu/upload/mtwin14400.csv')
df['time'] = pd.to_datetime(df['time'])
print(f"Total: {len(df)} candles")
print(f"Período: {df['time'].iloc[0]} até {df['time'].iloc[-1]}")

# ============================================================
# EXECUTAR ENGINE
# ============================================================
print("\nExecutando Engine V3 (RR 3:1, maxP=150, sem filtros vol/size)...")
engine = SMCEngineV3(
    symbol='WIN',
    swing_length=5,
    risk_reward_ratio=3.0,
    min_volume_ratio=0.0,
    min_ob_size_atr=0.0,
    use_not_mitigated_filter=True,
    max_pending_candles=150,
    entry_delay_candles=1,
)

for i, row in df.iterrows():
    engine.add_candle({
        'open': float(row['open']),
        'high': float(row['high']),
        'low': float(row['low']),
        'close': float(row['close']),
        'volume': float(row.get('real_volume', row.get('tick_volume', 0)))
    })
    if (i + 1) % 20000 == 0:
        print(f"  Processados {i+1} candles...")

print(f"  Processados {len(df)} candles (completo)")

# ============================================================
# COLETAR TRADES (usando chaves corretas do engine V3)
# ============================================================
raw_trades = engine.get_all_trades()
print(f"\nTotal de trades fechados: {len(raw_trades)}")

if len(raw_trades) == 0:
    print("NENHUM TRADE ENCONTRADO!")
    sys.exit(1)

# Construir DataFrame
trade_data = []
for t in raw_trades:
    fill_idx = t['filled_at']
    close_idx = t['closed_at']
    fill_time = df.iloc[fill_idx]['time'] if fill_idx < len(df) else None
    close_time = df.iloc[close_idx]['time'] if close_idx < len(df) else None
    
    direction = t['direction']
    entry = t['entry_price']
    tp = t['take_profit']
    sl = t['stop_loss']
    status = t['status']
    
    if direction == 'BULLISH':
        risk = entry - sl
    else:
        risk = sl - entry
    
    pnl_pts = t['profit_loss']
    pnl_r = t['profit_loss_r']
    result = 'WIN' if status == 'closed_tp' else 'LOSS'
    
    trade_data.append({
        'id': t['order_id'],
        'direction': direction,
        'fill_time': fill_time,
        'close_time': close_time,
        'fill_index': fill_idx,
        'close_index': close_idx,
        'created_at': t['created_at'],
        'entry': entry,
        'tp': tp,
        'sl': sl,
        'risk': risk,
        'status': status,
        'result': result,
        'pnl_pts': pnl_pts,
        'pnl_r': pnl_r,
        'ob_top': t['ob_top'],
        'ob_bottom': t['ob_bottom'],
        'ob_midline': t['ob_midline'],
        'confidence': t['confidence'],
        'patterns': str(t['patterns']),
        'wait_candles': t['wait_candles'],
        'duration_candles': t['duration_candles'],
    })

tdf = pd.DataFrame(trade_data)
tdf['fill_time'] = pd.to_datetime(tdf['fill_time'])
tdf['close_time'] = pd.to_datetime(tdf['close_time'])
tdf['month'] = tdf['fill_time'].dt.to_period('M')

wins = len(tdf[tdf['result']=='WIN'])
losses = len(tdf[tdf['result']=='LOSS'])
total = wins + losses
wr = wins / total * 100 if total > 0 else 0

# ============================================================
# RESULTADO GERAL
# ============================================================
print("\n" + "="*80)
print("RESULTADO GERAL")
print("="*80)
total_pts = tdf['pnl_pts'].sum()
total_r = tdf['pnl_r'].sum()
win_pts = tdf[tdf['result']=='WIN']['pnl_pts'].sum()
loss_pts = abs(tdf[tdf['result']=='LOSS']['pnl_pts'].sum())
pf = win_pts / loss_pts if loss_pts > 0 else float('inf')
exp_r = total_r / total if total > 0 else 0

print(f"  Total de trades: {total}")
print(f"  Wins: {wins} | Losses: {losses}")
print(f"  Win Rate: {wr:.1f}%")
print(f"  Profit Factor: {pf:.2f}")
print(f"  Lucro total: {total_pts:+,.2f} pontos")
print(f"  Lucro total: {total_r:+,.2f} R")
print(f"  Expectativa: {exp_r:.2f}R/trade")
print(f"  Média espera (candles): {tdf['wait_candles'].mean():.1f}")
print(f"  Média duração (candles): {tdf['duration_candles'].mean():.1f}")

# ============================================================
# LUCRO POR MÊS
# ============================================================
print("\n" + "="*80)
print("LUCRO POR MÊS")
print("="*80)
monthly = tdf.groupby('month').agg(
    trades=('result', 'count'),
    wins=('result', lambda x: (x=='WIN').sum()),
    losses=('result', lambda x: (x=='LOSS').sum()),
    pnl_pts=('pnl_pts', 'sum'),
    pnl_r=('pnl_r', 'sum'),
).reset_index()

monthly['wr'] = monthly['wins'] / monthly['trades'] * 100

print(f"{'Mês':<12} {'Trades':>7} {'Wins':>6} {'Loss':>6} {'WR%':>7} {'Lucro(pts)':>14} {'Lucro(R)':>10}")
print("-" * 70)
for _, row in monthly.iterrows():
    print(f"{str(row['month']):<12} {row['trades']:>7} {row['wins']:>6} {row['losses']:>6} {row['wr']:>6.1f}% {row['pnl_pts']:>+14,.2f} {row['pnl_r']:>+10,.2f}")

print("-" * 70)
print(f"{'TOTAL':<12} {total:>7} {wins:>6} {losses:>6} {wr:>6.1f}% {total_pts:>+14,.2f} {total_r:>+10,.2f}")

# Último mês
last_month = monthly.iloc[-1]
print(f"\n>>> ÚLTIMO MÊS ({last_month['month']}):")
print(f"    Trades: {int(last_month['trades'])}")
print(f"    Wins: {int(last_month['wins'])} | Losses: {int(last_month['losses'])}")
print(f"    Win Rate: {last_month['wr']:.1f}%")
print(f"    Lucro: {last_month['pnl_pts']:+,.2f} pontos")
print(f"    Lucro: {last_month['pnl_r']:+,.2f} R")

# ============================================================
# DRAWDOWN
# ============================================================
print("\n" + "="*80)
print("DRAWDOWN ANALYSIS")
print("="*80)

tdf_sorted = tdf.sort_values('fill_time').reset_index(drop=True)
tdf_sorted['cumulative_pts'] = tdf_sorted['pnl_pts'].cumsum()
tdf_sorted['cumulative_r'] = tdf_sorted['pnl_r'].cumsum()

# Drawdown em pontos
tdf_sorted['peak_pts'] = tdf_sorted['cumulative_pts'].cummax()
tdf_sorted['drawdown_pts'] = tdf_sorted['cumulative_pts'] - tdf_sorted['peak_pts']
max_dd_pts = tdf_sorted['drawdown_pts'].min()
max_dd_pts_idx = tdf_sorted['drawdown_pts'].idxmin()

# Drawdown em R
tdf_sorted['peak_r'] = tdf_sorted['cumulative_r'].cummax()
tdf_sorted['drawdown_r'] = tdf_sorted['cumulative_r'] - tdf_sorted['peak_r']
max_dd_r = tdf_sorted['drawdown_r'].min()

# Período do drawdown
dd_end_idx = max_dd_pts_idx
dd_start_candidates = tdf_sorted.loc[:dd_end_idx]
dd_start_idx = dd_start_candidates['cumulative_pts'].idxmax()

dd_start_time = tdf_sorted.loc[dd_start_idx, 'fill_time']
dd_end_time = tdf_sorted.loc[dd_end_idx, 'fill_time']
dd_peak = tdf_sorted.loc[dd_start_idx, 'cumulative_pts']
dd_valley = tdf_sorted.loc[dd_end_idx, 'cumulative_pts']
dd_trades = dd_end_idx - dd_start_idx

# Recuperação
recovery_candidates = tdf_sorted.loc[dd_end_idx:]
recovery_mask = recovery_candidates['cumulative_pts'] >= dd_peak
if recovery_mask.any():
    recovery_idx = recovery_mask.idxmax()
    recovery_time = tdf_sorted.loc[recovery_idx, 'fill_time']
    recovery_trades = recovery_idx - dd_end_idx
else:
    recovery_time = "Não recuperou"
    recovery_trades = "N/A"

print(f"  Max Drawdown (pontos): {max_dd_pts:,.2f} pts")
print(f"  Max Drawdown (R): {max_dd_r:,.2f} R")
print(f"  Período DD: {dd_start_time} → {dd_end_time}")
print(f"  Peak: {dd_peak:,.2f} pts → Valley: {dd_valley:,.2f} pts")
print(f"  Trades no drawdown: {dd_trades}")
print(f"  Recuperação: {recovery_time} ({recovery_trades} trades)")

ratio = total_pts / abs(max_dd_pts) if max_dd_pts != 0 else float('inf')
print(f"  Ratio Lucro/DD: {ratio:.2f}x")

# Losses consecutivas
consecutive_losses = 0
max_consecutive_losses = 0
consecutive_loss_pts = 0
max_consecutive_loss_pts = 0
for _, row in tdf_sorted.iterrows():
    if row['result'] == 'LOSS':
        consecutive_losses += 1
        consecutive_loss_pts += row['pnl_pts']
        max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
        max_consecutive_loss_pts = min(max_consecutive_loss_pts, consecutive_loss_pts)
    else:
        consecutive_losses = 0
        consecutive_loss_pts = 0

print(f"  Max losses consecutivas: {max_consecutive_losses}")
print(f"  Max perda consecutiva: {max_consecutive_loss_pts:,.2f} pts")

# Drawdown mensal
print("\n  DRAWDOWN POR MÊS:")
monthly_dd = tdf_sorted.groupby(tdf_sorted['fill_time'].dt.to_period('M')).apply(
    lambda g: g['pnl_pts'].cumsum().min() if (g['pnl_pts'].cumsum() < 0).any() else 0
).reset_index()
monthly_dd.columns = ['month', 'max_dd']
for _, row in monthly_dd.iterrows():
    if row['max_dd'] < 0:
        print(f"    {row['month']}: {row['max_dd']:,.2f} pts")

# ============================================================
# VALIDAÇÕES DETALHADAS
# ============================================================
print("\n" + "="*80)
print("VALIDAÇÕES DETALHADAS")
print("="*80)

# 1. Toque real na linha do meio
print("\n1. TOQUE REAL NA LINHA DO MEIO")
touch_violations = 0
for _, t in tdf.iterrows():
    fi = int(t['fill_index'])
    if fi >= len(df):
        continue
    candle = df.iloc[fi]
    midline = t['ob_midline']
    
    if t['direction'] == 'BULLISH':
        if candle['low'] > midline + 0.01:
            touch_violations += 1
    else:
        if candle['high'] < midline - 0.01:
            touch_violations += 1

print(f"   Violações: {touch_violations}/{len(tdf)}")
print(f"   {'✅ PASSOU' if touch_violations == 0 else '❌ FALHOU'}")

# 2. Fill não no mesmo candle do sinal
print("\n2. FILL NÃO NO MESMO CANDLE DO SINAL")
same_candle = 0
for _, t in tdf.iterrows():
    if t['fill_index'] <= t['created_at']:
        same_candle += 1

print(f"   Violações: {same_candle}/{len(tdf)}")
print(f"   {'✅ PASSOU' if same_candle == 0 else '❌ FALHOU'}")

# 3. Sequência temporal
print("\n3. SEQUÊNCIA TEMPORAL (Criação → Fill → Close)")
temporal_violations = 0
for _, t in tdf.iterrows():
    if not (t['created_at'] < t['fill_index'] <= t['close_index']):
        temporal_violations += 1

print(f"   Violações: {temporal_violations}/{len(tdf)}")
print(f"   {'✅ PASSOU' if temporal_violations == 0 else '❌ FALHOU'}")

# 4. TP/SL calculado corretamente (RR 3:1)
print("\n4. TP/SL CALCULADO CORRETAMENTE (RR 3:1)")
tp_sl_errors = 0
for _, t in tdf.iterrows():
    entry = t['entry']
    tp = t['tp']
    sl = t['sl']
    
    if t['direction'] == 'BULLISH':
        risk = entry - sl
        expected_tp = entry + risk * 3.0
    else:
        risk = sl - entry
        expected_tp = entry - risk * 3.0
    
    if abs(tp - expected_tp) > 1.0:
        tp_sl_errors += 1

print(f"   Erros: {tp_sl_errors}/{len(tdf)}")
print(f"   {'✅ PASSOU' if tp_sl_errors == 0 else '❌ FALHOU'}")

# 5. Resultado verificado candle a candle
print("\n5. RESULTADO VERIFICADO CANDLE A CANDLE")
result_errors = 0
checked = 0
for _, t in tdf.iterrows():
    fi = int(t['fill_index'])
    ci = int(t['close_index'])
    if ci >= len(df):
        continue
    
    entry = t['entry']
    tp = t['tp']
    sl = t['sl']
    
    actual_result = None
    for k in range(fi + 1, min(ci + 1, len(df))):
        c = df.iloc[k]
        if t['direction'] == 'BULLISH':
            if c['low'] <= sl:
                actual_result = 'LOSS'
                break
            if c['high'] >= tp:
                actual_result = 'WIN'
                break
        else:
            if c['high'] >= sl:
                actual_result = 'LOSS'
                break
            if c['low'] <= tp:
                actual_result = 'WIN'
                break
    
    if actual_result and actual_result != t['result']:
        result_errors += 1
    checked += 1

print(f"   Verificados: {checked}/{len(tdf)}")
print(f"   Erros: {result_errors}")
print(f"   {'✅ PASSOU' if result_errors == 0 else '❌ FALHOU'}")

# 6. OB não mitigado (primeiro toque)
print("\n6. OB NÃO MITIGADO (primeiro toque)")
mitigated_violations = 0
for _, t in tdf.iterrows():
    created = int(t['created_at'])
    fill_idx = int(t['fill_index'])
    midline = t['ob_midline']
    direction = t['direction']
    
    already_touched = False
    for k in range(created + 2, fill_idx):
        if k >= len(df):
            break
        c = df.iloc[k]
        if direction == 'BULLISH' and c['low'] <= midline:
            already_touched = True
            break
        elif direction == 'BEARISH' and c['high'] >= midline:
            already_touched = True
            break
    
    if already_touched:
        mitigated_violations += 1

print(f"   Violações: {mitigated_violations}/{len(tdf)}")
print(f"   {'✅ PASSOU' if mitigated_violations == 0 else '⚠️ ATENÇÃO'}")

# 7. Tempo máximo de espera
print("\n7. TEMPO MÁXIMO DE ESPERA DA ORDEM")
max_wait = tdf['wait_candles'].max()
avg_wait = tdf['wait_candles'].mean()
over_150 = len(tdf[tdf['wait_candles'] > 150])
print(f"   Max espera: {max_wait} candles")
print(f"   Média espera: {avg_wait:.1f} candles")
print(f"   Ordens > 150 candles: {over_150}")
print(f"   {'✅ PASSOU' if over_150 == 0 else '❌ FALHOU'}")

# ============================================================
# RESUMO FINAL
# ============================================================
tests = [
    touch_violations == 0,
    same_candle == 0,
    temporal_violations == 0,
    tp_sl_errors == 0,
    result_errors == 0,
    mitigated_violations == 0,
    over_150 == 0,
]
tests_passed = sum(tests)

print("\n" + "="*80)
print("RESUMO FINAL")
print("="*80)
print(f"  Testes passados: {tests_passed}/7")
print(f"  Total trades: {total}")
print(f"  Win Rate: {wr:.1f}%")
print(f"  Profit Factor: {pf:.2f}")
print(f"  Lucro total: {total_pts:+,.2f} pontos | {total_r:+,.2f} R")
print(f"  Expectativa: {exp_r:.2f}R/trade")
print(f"  Max Drawdown: {max_dd_pts:,.2f} pts | {max_dd_r:,.2f} R")
print(f"  Ratio Lucro/DD: {ratio:.2f}x")
print(f"  Max losses consecutivas: {max_consecutive_losses}")
print(f"  Max perda consecutiva: {max_consecutive_loss_pts:,.2f} pts")
print(f"  Último mês ({last_month['month']}): {last_month['pnl_pts']:+,.2f} pts ({int(last_month['trades'])} trades, {last_month['wr']:.1f}% WR)")
print(f"  OB olha para trás: máximo {engine.max_pending_candles} candles (ordem expira)")

# Salvar tabela
tdf.to_csv('/home/ubuntu/smc_realtime/trades_full_analysis.csv', index=False)
print(f"\nTabela salva em: trades_full_analysis.csv")
