"""
Backtest MTF - Detecta OBs no HTF (M15/M30) e executa no M1
=============================================================
Compara: M1-only vs MTF-M15 vs MTF-M30 vs M15-only vs M30-only
"""
import sys
import os
os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.stdout.reconfigure(encoding='utf-8')

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime
from smc_engine_v3 import SMCEngineV3

# ============================================================
# 1. CONECTAR E PUXAR DADOS M1
# ============================================================
print("Conectando ao MetaTrader 5...")
if not mt5.initialize():
    print(f"ERRO: {mt5.last_error()}")
    sys.exit(1)

symbols_to_try = ["WIN$N", "WING26", "WINH26", "WINJ26", "WIN$"]
symbol = None
for s in symbols_to_try:
    if mt5.symbol_info(s) is not None:
        symbol = s
        mt5.symbol_select(s, True)
        break

print(f"Simbolo: {symbol}")

inicio = datetime(2025, 1, 1)
fim = datetime(2026, 2, 25)

# Dados M1
rates_m1 = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, inicio, fim)

# Dados M15 e M30 para comparacao standalone
rates_m15 = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M15, inicio, fim)
rates_m30 = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M30, inicio, fim)

mt5.shutdown()

df_m1 = pd.DataFrame(rates_m1)
df_m1['time_ts'] = df_m1['time']  # preservar unix timestamp original
df_m1['time'] = pd.to_datetime(df_m1['time'], unit='s')
df_m1 = df_m1[df_m1['time'].dt.year >= 2025].reset_index(drop=True)
df_m1 = df_m1.drop_duplicates(subset='time').sort_values('time').reset_index(drop=True)

df_m15 = pd.DataFrame(rates_m15)
df_m15['time'] = pd.to_datetime(df_m15['time'], unit='s')
df_m15 = df_m15[df_m15['time'].dt.year >= 2025].reset_index(drop=True)

df_m30 = pd.DataFrame(rates_m30)
df_m30['time'] = pd.to_datetime(df_m30['time'], unit='s')
df_m30 = df_m30[df_m30['time'].dt.year >= 2025].reset_index(drop=True)

print(f"M1:  {len(df_m1):>8,} candles | {df_m1['time'].iloc[0].date()} ate {df_m1['time'].iloc[-1].date()}")
print(f"M15: {len(df_m15):>8,} candles")
print(f"M30: {len(df_m30):>8,} candles")


def run_engine(name, df, htf_period=1, max_sl=50, max_pending=150):
    """Roda engine e retorna resultados."""
    engine = SMCEngineV3(
        symbol=symbol,
        swing_length=5,
        risk_reward_ratio=2.0,
        min_volume_ratio=0.0,
        min_ob_size_atr=0.3,
        use_not_mitigated_filter=True,
        max_pending_candles=max_pending,
        entry_delay_candles=1,
        tick_size=5.0,
        min_confidence=0.0,
        max_sl_points=float(max_sl),
        min_patterns=0,
        entry_retracement=0.7,
        htf_period=htf_period,
    )

    for i in range(len(df)):
        row = df.iloc[i]
        candle = {
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
            'volume': float(row.get('real_volume', row.get('tick_volume', 0))),
        }
        if htf_period > 1:
            candle['time'] = int(row['time_ts'])
        engine.add_candle(candle)

    stats = engine.get_stats()
    trades = engine.get_all_trades()
    dias = df['time'].dt.date.nunique()

    if stats['total_trades'] == 0:
        return {'name': name, 'trades': 0, 'wins': 0, 'losses': 0, 'wr': 0,
                'pf': 0, 'total_pts': 0, 'total_r': 0, 'exp_r': 0,
                'obs': stats['order_blocks_detected'], 'dias': dias,
                'avg_sl': 0, 'avg_dur': 0, 'max_dd': 0}

    wins = [t for t in trades if t['status'] == 'closed_tp']
    losses = [t for t in trades if t['status'] == 'closed_sl']
    win_pts = sum(t['profit_loss'] for t in wins)
    loss_pts = abs(sum(t['profit_loss'] for t in losses))
    avg_sl = np.mean([abs(t['entry_price'] - t['stop_loss']) for t in trades])
    avg_dur = np.mean([t['duration_candles'] for t in trades])
    cum = np.cumsum([t['profit_loss'] for t in trades])
    peak = np.maximum.accumulate(cum)
    max_dd = (cum - peak).min()

    return {
        'name': name,
        'trades': stats['total_trades'],
        'wins': len(wins),
        'losses': len(losses),
        'wr': stats['win_rate'],
        'pf': win_pts / loss_pts if loss_pts > 0 else float('inf'),
        'total_pts': stats['total_profit_points'],
        'total_r': stats['total_profit_r'],
        'exp_r': stats['avg_profit_r'],
        'obs': stats['order_blocks_detected'],
        'dias': dias,
        'avg_sl': avg_sl,
        'avg_dur': avg_dur,
        'max_dd': max_dd,
    }


# ============================================================
# 2. RODAR TODAS AS CONFIGURACOES
# ============================================================
configs = [
    # (nome, dataframe, htf_period, max_sl, max_pending)
    ("M1-only (atual)",       df_m1,  1,  50, 150),
    ("MTF M15 (sl=100)",      df_m1, 15, 100, 300),
    ("MTF M15 (sl=150)",      df_m1, 15, 150, 300),
    ("MTF M15 (sl=200)",      df_m1, 15, 200, 300),
    ("MTF M30 (sl=200)",      df_m1, 30, 200, 300),
    ("MTF M30 (sl=300)",      df_m1, 30, 300, 300),
    ("M15-only (standalone)", df_m15, 1, 200, 30),
    ("M30-only (standalone)", df_m30, 1, 300, 20),
]

results = []
for name, df, htf, sl, pending in configs:
    print(f"\nRodando: {name} (htf={htf}, sl={sl}, pending={pending})...")
    r = run_engine(name, df, htf_period=htf, max_sl=sl, max_pending=pending)
    results.append(r)
    print(f"  -> {r['trades']} trades | WR {r['wr']:.1f}% | PF {r['pf']:.2f} | {r['total_pts']:+,.0f} pts")

# ============================================================
# 3. TABELA COMPARATIVA
# ============================================================
print(f"\n\n{'='*130}")
print("COMPARACAO: M1-only vs MTF vs Standalone")
print(f"{'='*130}")
print(f"{'Config':<25} {'Trades':>7} {'Wins':>6} {'Loss':>6} {'WR%':>7} {'PF':>7} {'P/L(pts)':>12} {'P/L(R)':>10} "
      f"{'Exp(R)':>8} {'OBs':>7} {'AvgSL':>7} {'AvgDur':>7} {'MaxDD':>10}")
print(f"{'-'*130}")

for r in results:
    pf_str = f"{r['pf']:.2f}" if r['pf'] < 100 else "inf"
    print(f"{r['name']:<25} {r['trades']:>7} {r['wins']:>6} {r['losses']:>6} {r['wr']:>6.1f}% {pf_str:>7} "
          f"{r['total_pts']:>+12,.0f} {r['total_r']:>+10,.1f} {r['exp_r']:>+8.2f} {r['obs']:>7,} "
          f"{r['avg_sl']:>7.1f} {r['avg_dur']:>7.1f} {r['max_dd']:>+10,.0f}")

# Highlight
print(f"\n{'='*130}")
print("DESTAQUES:")
valid = [r for r in results if r['trades'] >= 10]
if valid:
    best_wr = max(valid, key=lambda x: x['wr'])
    best_pf = max(valid, key=lambda x: x['pf'])
    best_exp = max(valid, key=lambda x: x['exp_r'])
    best_pts = max(valid, key=lambda x: x['total_pts'])
    print(f"  Melhor WR:    {best_wr['name']} ({best_wr['wr']:.1f}% com {best_wr['trades']} trades)")
    print(f"  Melhor PF:    {best_pf['name']} ({best_pf['pf']:.2f})")
    print(f"  Melhor Exp:   {best_exp['name']} ({best_exp['exp_r']:.2f}R/trade)")
    print(f"  Mais lucro:   {best_pts['name']} ({best_pts['total_pts']:+,.0f} pts)")
