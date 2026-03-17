"""
Parameter sweep MTF M15 com M1 fills
====================================
Encontrar melhor combinacao: entry_retracement, max_sl, min_ob_size, min_patterns, RR
"""
import sys, os
os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.stdout.reconfigure(encoding='utf-8')

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime
from smc_engine_v3 import SMCEngineV3

mt5.initialize()
symbol = None
for s in ['WIN$N', 'WING26', 'WINH26']:
    if mt5.symbol_info(s) is not None:
        symbol = s
        mt5.symbol_select(s, True)
        break
print(f"Simbolo: {symbol}")

rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, datetime(2025, 1, 1), datetime(2026, 3, 1))
mt5.shutdown()

df = pd.DataFrame(rates)
df['time_ts'] = df['time']
df['time'] = pd.to_datetime(df['time'], unit='s')
df = df.drop_duplicates(subset='time').sort_values('time').reset_index(drop=True)
print(f"M1: {len(df):,} candles | {df['time'].iloc[0]} ate {df['time'].iloc[-1]}")


def run_config(retrace, max_sl, min_size, min_pat, rr, max_pend):
    engine = SMCEngineV3(
        symbol=symbol, swing_length=5, risk_reward_ratio=rr,
        min_volume_ratio=0.0, min_ob_size_atr=min_size,
        use_not_mitigated_filter=True, max_pending_candles=max_pend,
        entry_delay_candles=1, tick_size=5.0,
        min_confidence=0.0, max_sl_points=float(max_sl),
        min_patterns=min_pat, entry_retracement=retrace,
        htf_period=15)

    for i in range(len(df)):
        row = df.iloc[i]
        engine.add_candle({
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
            'volume': float(row.get('real_volume', row.get('tick_volume', 0))),
            'time': int(row['time_ts']),
        })

    stats = engine.get_stats()
    trades = engine.get_all_trades()

    total = stats['total_trades']
    if total == 0:
        return None

    wins = stats['winning_trades']
    wr = stats['win_rate']
    pf = stats['profit_factor']
    pts = stats['total_profit_points']

    # Max drawdown
    cum = 0
    peak = 0
    max_dd = 0
    for t in trades:
        cum += t['profit_loss']
        peak = max(peak, cum)
        max_dd = min(max_dd, cum - peak)

    avg_sl = np.mean([abs(t['entry_price'] - t['stop_loss']) for t in trades]) if trades else 0
    avg_tp = np.mean([abs(t['take_profit'] - t['entry_price']) for t in trades]) if trades else 0

    return {
        'trades': total, 'wins': wins, 'losses': total - wins,
        'wr': wr, 'pf': pf, 'pts': pts, 'max_dd': max_dd,
        'avg_sl': avg_sl, 'avg_tp': avg_tp,
    }


# Parameter grid
configs = []
for retrace in [0.5, 0.6, 0.7]:
    for max_sl in [80, 100, 150, 200]:
        for min_size in [0.3, 0.5, 0.7]:
            for rr in [2.0, 3.0]:
                for min_pat in [0, 1]:
                    for max_pend in [150, 300]:
                        configs.append({
                            'retrace': retrace, 'max_sl': max_sl,
                            'min_size': min_size, 'rr': rr,
                            'min_pat': min_pat, 'max_pend': max_pend,
                        })

print(f"\n{len(configs)} configuracoes para testar...\n")

results = []
for i, cfg in enumerate(configs):
    r = run_config(cfg['retrace'], cfg['max_sl'], cfg['min_size'],
                   cfg['min_pat'], cfg['rr'], cfg['max_pend'])
    if r and r['trades'] >= 10:
        results.append({**cfg, **r})
    if (i + 1) % 50 == 0:
        print(f"  {i+1}/{len(configs)}...")

print(f"\n{len(results)} configuracoes com >= 10 trades")

# Sort by profit factor
results.sort(key=lambda x: x['pf'], reverse=True)

print(f"\n{'='*130}")
print(f"TOP 20 POR PROFIT FACTOR (>= 10 trades)")
print(f"{'='*130}")
print(f"{'Ret':>4} {'SL':>4} {'Size':>5} {'RR':>4} {'Pat':>4} {'Pend':>5} | "
      f"{'Trd':>4} {'W':>3} {'L':>3} {'WR%':>6} {'PF':>6} {'Pts':>8} {'DD':>7} {'AvgSL':>6} {'AvgTP':>6}")
print("-" * 130)
for r in results[:20]:
    print(f"{r['retrace']:>4.1f} {r['max_sl']:>4} {r['min_size']:>5.1f} {r['rr']:>4.1f} {r['min_pat']:>4} {r['max_pend']:>5} | "
          f"{r['trades']:>4} {r['wins']:>3} {r['losses']:>3} {r['wr']:>5.1f}% {r['pf']:>6.2f} "
          f"{r['pts']:>+8.0f} {r['max_dd']:>7.0f} {r['avg_sl']:>6.1f} {r['avg_tp']:>6.1f}")

# Sort by total points
results.sort(key=lambda x: x['pts'], reverse=True)
print(f"\n{'='*130}")
print(f"TOP 20 POR LUCRO TOTAL (>= 10 trades)")
print(f"{'='*130}")
print(f"{'Ret':>4} {'SL':>4} {'Size':>5} {'RR':>4} {'Pat':>4} {'Pend':>5} | "
      f"{'Trd':>4} {'W':>3} {'L':>3} {'WR%':>6} {'PF':>6} {'Pts':>8} {'DD':>7} {'AvgSL':>6} {'AvgTP':>6}")
print("-" * 130)
for r in results[:20]:
    print(f"{r['retrace']:>4.1f} {r['max_sl']:>4} {r['min_size']:>5.1f} {r['rr']:>4.1f} {r['min_pat']:>4} {r['max_pend']:>5} | "
          f"{r['trades']:>4} {r['wins']:>3} {r['losses']:>3} {r['wr']:>5.1f}% {r['pf']:>6.2f} "
          f"{r['pts']:>+8.0f} {r['max_dd']:>7.0f} {r['avg_sl']:>6.1f} {r['avg_tp']:>6.1f}")

# Best balanced (PF > 2 AND most trades)
balanced = [r for r in results if r['pf'] >= 2.0]
balanced.sort(key=lambda x: x['pts'], reverse=True)
print(f"\n{'='*130}")
print(f"MELHOR EQUILIBRIO (PF >= 2.0, ordenado por lucro)")
print(f"{'='*130}")
print(f"{'Ret':>4} {'SL':>4} {'Size':>5} {'RR':>4} {'Pat':>4} {'Pend':>5} | "
      f"{'Trd':>4} {'W':>3} {'L':>3} {'WR%':>6} {'PF':>6} {'Pts':>8} {'DD':>7} {'AvgSL':>6} {'AvgTP':>6}")
print("-" * 130)
for r in balanced[:20]:
    print(f"{r['retrace']:>4.1f} {r['max_sl']:>4} {r['min_size']:>5.1f} {r['rr']:>4.1f} {r['min_pat']:>4} {r['max_pend']:>5} | "
          f"{r['trades']:>4} {r['wins']:>3} {r['losses']:>3} {r['wr']:>5.1f}% {r['pf']:>6.2f} "
          f"{r['pts']:>+8.0f} {r['max_dd']:>7.0f} {r['avg_sl']:>6.1f} {r['avg_tp']:>6.1f}")
