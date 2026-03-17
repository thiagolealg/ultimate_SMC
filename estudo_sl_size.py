"""
Estudo: Stop Loss pequeno (< 15 pts) tem mais chance de ser stopado?
================================================================
Roda a engine SMC nos dados de 2025 + janeiro/2026 e analisa
a relacao entre tamanho do SL e taxa de acerto.
"""
import sys
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime
from smc_engine_v3 import SMCEngineV3

# ============================================================
# 1. CONECTAR E PUXAR DADOS
# ============================================================
print("Conectando ao MetaTrader 5...")
if not mt5.initialize():
    print(f"ERRO: {mt5.last_error()}")
    sys.exit(1)

symbols_to_try = ["WIN$N", "WING26", "WINH26", "WINJ26"]
symbol = None
for s in symbols_to_try:
    if mt5.symbol_info(s) is not None:
        symbol = s
        mt5.symbol_select(s, True)
        break

print(f"Simbolo: {symbol}")

# Puxar 2025 inteiro + janeiro 2026
inicio = datetime(2025, 1, 1)
fim = datetime(2026, 2, 1)

print(f"Buscando candles M1 de {inicio.date()} ate {fim.date()}...")
rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, inicio, fim)
mt5.shutdown()

if rates is None or len(rates) == 0:
    print("ERRO: Nenhum candle encontrado.")
    sys.exit(1)

df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')
print(f"Total: {len(df):,} candles M1")
print(f"Periodo: {df['time'].iloc[0]} ate {df['time'].iloc[-1]}")

# ============================================================
# 2. RODAR ENGINE
# ============================================================
print("\nExecutando SMC Engine V3...")
engine = SMCEngineV3(
    symbol=symbol,
    swing_length=5,
    risk_reward_ratio=3.0,
    min_volume_ratio=0.0,
    min_ob_size_atr=0.0,
    use_not_mitigated_filter=True,
    max_pending_candles=150,
    entry_delay_candles=1,
    tick_size=5.0,
)

for i in range(len(df)):
    row = df.iloc[i]
    engine.add_candle({
        'open': float(row['open']),
        'high': float(row['high']),
        'low': float(row['low']),
        'close': float(row['close']),
        'volume': float(row.get('real_volume', row.get('tick_volume', 0)))
    })
    if (i + 1) % 50000 == 0:
        print(f"  {i+1:,} candles...")

print(f"  {len(df):,} candles processados")

# ============================================================
# 3. COLETAR TRADES E CALCULAR SL SIZE
# ============================================================
raw_trades = engine.get_all_trades()
print(f"\nTotal de trades: {len(raw_trades)}")

if len(raw_trades) == 0:
    print("Nenhum trade encontrado.")
    sys.exit(0)

trades = []
for t in raw_trades:
    sl_size = abs(t['entry_price'] - t['stop_loss'])
    tp_size = abs(t['take_profit'] - t['entry_price'])
    result = 'WIN' if t['status'] == 'closed_tp' else 'LOSS'
    trades.append({
        'direction': t['direction'],
        'entry': t['entry_price'],
        'sl': t['stop_loss'],
        'tp': t['take_profit'],
        'sl_size': sl_size,
        'tp_size': tp_size,
        'result': result,
        'pnl_pts': t['profit_loss'],
        'pnl_r': t['profit_loss_r'],
    })

tdf = pd.DataFrame(trades)

# ============================================================
# 4. ANALISE POR FAIXAS DE SL
# ============================================================
print(f"\n{'='*80}")
print("ESTUDO: TAMANHO DO STOP LOSS vs TAXA DE ACERTO")
print(f"{'='*80}")

# Estatisticas gerais
print(f"\n  SL medio: {tdf['sl_size'].mean():,.1f} pts")
print(f"  SL mediano: {tdf['sl_size'].median():,.1f} pts")
print(f"  SL min: {tdf['sl_size'].min():,.1f} pts")
print(f"  SL max: {tdf['sl_size'].max():,.1f} pts")
print(f"  SL std: {tdf['sl_size'].std():,.1f} pts")

# Faixas de SL
bins = [0, 5, 10, 15, 20, 30, 50, 100, 200, 500, float('inf')]
labels = ['0-5', '5-10', '10-15', '15-20', '20-30', '30-50', '50-100', '100-200', '200-500', '500+']
tdf['sl_faixa'] = pd.cut(tdf['sl_size'], bins=bins, labels=labels, right=False)

print(f"\n{'='*80}")
print("RESULTADO POR FAIXA DE SL")
print(f"{'='*80}")
print(f"{'Faixa SL':<12} {'Trades':>8} {'Wins':>6} {'Loss':>6} {'WR%':>8} {'Avg PnL(pts)':>14} {'Avg PnL(R)':>12} {'PF':>8}")
print("-" * 80)

for faixa in labels:
    subset = tdf[tdf['sl_faixa'] == faixa]
    if len(subset) == 0:
        continue
    wins = (subset['result'] == 'WIN').sum()
    losses = (subset['result'] == 'LOSS').sum()
    total = wins + losses
    wr = wins / total * 100 if total > 0 else 0
    avg_pnl = subset['pnl_pts'].mean()
    avg_r = subset['pnl_r'].mean()
    win_pts = subset[subset['result'] == 'WIN']['pnl_pts'].sum()
    loss_pts = abs(subset[subset['result'] == 'LOSS']['pnl_pts'].sum())
    pf = win_pts / loss_pts if loss_pts > 0 else float('inf')
    print(f"{faixa:<12} {total:>8} {wins:>6} {losses:>6} {wr:>7.1f}% {avg_pnl:>+14,.1f} {avg_r:>+12,.2f} {pf:>8.2f}")

print("-" * 80)
total_all = len(tdf)
wins_all = (tdf['result'] == 'WIN').sum()
losses_all = (tdf['result'] == 'LOSS').sum()
wr_all = wins_all / total_all * 100
print(f"{'TOTAL':<12} {total_all:>8} {wins_all:>6} {losses_all:>6} {wr_all:>7.1f}%")

# ============================================================
# 5. FOCO: SL < 15 vs SL >= 15
# ============================================================
print(f"\n{'='*80}")
print("COMPARACAO DIRETA: SL < 15 pts vs SL >= 15 pts")
print(f"{'='*80}")

for label, mask in [("SL < 15 pts", tdf['sl_size'] < 15), ("SL >= 15 pts", tdf['sl_size'] >= 15)]:
    subset = tdf[mask]
    if len(subset) == 0:
        print(f"\n  {label}: Nenhum trade")
        continue
    wins = (subset['result'] == 'WIN').sum()
    losses = (subset['result'] == 'LOSS').sum()
    total = wins + losses
    wr = wins / total * 100 if total > 0 else 0
    total_pts = subset['pnl_pts'].sum()
    total_r = subset['pnl_r'].sum()
    avg_sl = subset['sl_size'].mean()
    win_pts = subset[subset['result'] == 'WIN']['pnl_pts'].sum()
    loss_pts = abs(subset[subset['result'] == 'LOSS']['pnl_pts'].sum())
    pf = win_pts / loss_pts if loss_pts > 0 else float('inf')
    exp_r = total_r / total if total > 0 else 0

    print(f"\n  {label}:")
    print(f"    Trades: {total} ({total/len(tdf)*100:.1f}% do total)")
    print(f"    SL medio: {avg_sl:,.1f} pts")
    print(f"    Wins: {wins} | Losses: {losses}")
    print(f"    Win Rate: {wr:.1f}%")
    print(f"    Profit Factor: {pf:.2f}")
    print(f"    Lucro total: {total_pts:+,.0f} pts | {total_r:+,.1f}R")
    print(f"    Expectativa: {exp_r:.2f}R/trade")

# ============================================================
# 6. ANALISE POR DIRECAO
# ============================================================
print(f"\n{'='*80}")
print("POR DIRECAO + TAMANHO DO SL")
print(f"{'='*80}")

for direction in ['BULLISH', 'BEARISH']:
    print(f"\n  --- {direction} ---")
    for label, mask in [("SL < 15", tdf['sl_size'] < 15), ("SL >= 15", tdf['sl_size'] >= 15)]:
        subset = tdf[(tdf['direction'] == direction) & mask]
        if len(subset) == 0:
            print(f"    {label}: Nenhum trade")
            continue
        wins = (subset['result'] == 'WIN').sum()
        losses = (subset['result'] == 'LOSS').sum()
        total = wins + losses
        wr = wins / total * 100 if total > 0 else 0
        total_pts = subset['pnl_pts'].sum()
        win_pts = subset[subset['result'] == 'WIN']['pnl_pts'].sum()
        loss_pts = abs(subset[subset['result'] == 'LOSS']['pnl_pts'].sum())
        pf = win_pts / loss_pts if loss_pts > 0 else float('inf')
        print(f"    {label}: {total:>5} trades | WR={wr:>5.1f}% | PF={pf:>5.2f} | PnL={total_pts:>+10,.0f} pts")

# ============================================================
# 7. DISTRIBUICAO DE SL SIZE
# ============================================================
print(f"\n{'='*80}")
print("DISTRIBUICAO DO TAMANHO DO STOP LOSS")
print(f"{'='*80}")

percentiles = [5, 10, 25, 50, 75, 90, 95]
for p in percentiles:
    val = np.percentile(tdf['sl_size'], p)
    print(f"  P{p:>2}: {val:>8,.1f} pts")

# Trades com SL <= 10 (muito apertado)
tiny_sl = tdf[tdf['sl_size'] <= 10]
if len(tiny_sl) > 0:
    wr_tiny = (tiny_sl['result'] == 'WIN').sum() / len(tiny_sl) * 100
    print(f"\n  Trades com SL <= 10 pts: {len(tiny_sl)} ({len(tiny_sl)/len(tdf)*100:.1f}%) | WR={wr_tiny:.1f}%")

small_sl = tdf[tdf['sl_size'] <= 15]
if len(small_sl) > 0:
    wr_small = (small_sl['result'] == 'WIN').sum() / len(small_sl) * 100
    print(f"  Trades com SL <= 15 pts: {len(small_sl)} ({len(small_sl)/len(tdf)*100:.1f}%) | WR={wr_small:.1f}%")

print(f"\n{'='*80}")
print("CONCLUSAO")
print(f"{'='*80}")
