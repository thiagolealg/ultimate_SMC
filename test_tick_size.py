"""Comparacao: sem tick_size vs tick_size=5 - Fevereiro 2026"""
import sys
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime
from smc_engine_v3 import SMCEngineV3

mt5.initialize()
symbol = "WIN$N"
mt5.symbol_select(symbol, True)

inicio = datetime(2026, 2, 1)
fim = datetime(2026, 2, 10)
rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, inicio, fim)
mt5.shutdown()

df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')
df = df[df['time'].dt.month == 2].reset_index(drop=True)

print(f"Simbolo: {symbol}")
print(f"Candles: {len(df):,} | Dias: {df['time'].dt.date.nunique()}")

def run_engine(tick_size):
    engine = SMCEngineV3(
        symbol=symbol, swing_length=5, risk_reward_ratio=3.0,
        min_volume_ratio=0.0, min_ob_size_atr=0.0, use_not_mitigated_filter=True,
        max_pending_candles=150, entry_delay_candles=1, tick_size=tick_size,
    )
    for i in range(len(df)):
        row = df.iloc[i]
        engine.add_candle({
            'open': float(row['open']), 'high': float(row['high']),
            'low': float(row['low']), 'close': float(row['close']),
            'volume': float(row.get('real_volume', row.get('tick_volume', 0)))
        })
    return engine.get_all_trades()

t1 = run_engine(0.0)
t2 = run_engine(5.0)

def stats(trades):
    w = sum(1 for t in trades if t['status'] == 'closed_tp')
    l = sum(1 for t in trades if t['status'] == 'closed_sl')
    pts = sum(t['profit_loss'] for t in trades)
    r = sum(t['profit_loss_r'] for t in trades)
    wp = sum(t['profit_loss'] for t in trades if t['status'] == 'closed_tp')
    lp = abs(sum(t['profit_loss'] for t in trades if t['status'] == 'closed_sl'))
    pf = wp / lp if lp > 0 else 0
    wr = w / (w + l) * 100 if (w + l) > 0 else 0
    return {'total': w + l, 'wins': w, 'losses': l, 'wr': wr, 'pf': pf, 'pts': pts, 'r': r}

s1 = stats(t1)
s2 = stats(t2)

print(f"\n{'='*80}")
print(f"COMPARACAO FEVEREIRO/2026")
print(f"{'='*80}")
print(f"{'':>25} {'SEM TICK':>15} {'TICK=5':>15} {'DIFERENCA':>15}")
print(f"  {'-'*70}")
print(f"{'Trades':>25} {s1['total']:>15} {s2['total']:>15} {s2['total']-s1['total']:>+15}")
print(f"{'Wins':>25} {s1['wins']:>15} {s2['wins']:>15} {s2['wins']-s1['wins']:>+15}")
print(f"{'Losses':>25} {s1['losses']:>15} {s2['losses']:>15} {s2['losses']-s1['losses']:>+15}")
print(f"{'Win Rate':>25} {s1['wr']:>14.1f}% {s2['wr']:>14.1f}% {s2['wr']-s1['wr']:>+14.1f}%")
print(f"{'Profit Factor':>25} {s1['pf']:>15.2f} {s2['pf']:>15.2f} {s2['pf']-s1['pf']:>+15.2f}")
print(f"{'Lucro (pts)':>25} {s1['pts']:>+15,.0f} {s2['pts']:>+15,.0f} {s2['pts']-s1['pts']:>+15,.0f}")
print(f"{'Lucro (R)':>25} {s1['r']:>+15,.1f} {s2['r']:>+15,.1f} {s2['r']-s1['r']:>+15,.1f}")

print(f"\n{'='*80}")
print("TRADES COM TICK=5 (precos arredondados)")
print(f"{'='*80}")
print(f"{'#':>3} {'Dir':>8} {'Entry':>10} {'SL':>10} {'TP':>10} {'Result':>7} {'P/L pts':>10}")
print("-" * 65)
for i, t in enumerate(t2):
    r = 'WIN' if t['status'] == 'closed_tp' else 'LOSS'
    print(f"{i+1:>3} {t['direction']:>8} {t['entry_price']:>10,.0f} {t['stop_loss']:>10,.0f} "
          f"{t['take_profit']:>10,.0f} {r:>7} {t['profit_loss']:>+10,.0f}")

# Verificar multiplos de 5
errors = 0
for t in t2:
    for p in [t['entry_price'], t['stop_loss'], t['take_profit']]:
        if p % 5 != 0:
            print(f"  ERRO: {p} nao e multiplo de 5!")
            errors += 1
if errors == 0:
    print(f"\nTodos os precos sao multiplos de 5: OK")
