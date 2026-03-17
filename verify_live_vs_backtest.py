"""Verifica que bot live e backtest geram os mesmos trades com tick_size=5"""
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta
from smc_engine_v3 import SMCEngineV3

mt5.initialize()
symbol = "WIN$N"
mt5.symbol_select(symbol, True)

# ======= MODO BACKTEST: so candles de hoje =======
dia = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
for d in range(7):
    test_dia = dia - timedelta(days=d)
    r = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, test_dia, test_dia + timedelta(hours=23, minutes=59))
    if r is not None and len(r) > 10:
        rates_dia = r
        dia_bt = test_dia
        break

df_dia = pd.DataFrame(rates_dia)
df_dia['time'] = pd.to_datetime(df_dia['time'], unit='s')

# ======= MODO LIVE: 10k warmup + candles de hoje =======
rates_hist = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 1, 10000)
mt5.shutdown()

df_hist = pd.DataFrame(rates_hist)
df_hist['time'] = pd.to_datetime(df_hist['time'], unit='s')

# Separar warmup (antes do dia) e candles do dia
warmup = df_hist[df_hist['time'] < dia_bt].reset_index(drop=True)
dia_candles = df_hist[df_hist['time'] >= dia_bt].reset_index(drop=True)

print(f"Simbolo: {symbol}")
print(f"Dia: {dia_bt.strftime('%d/%m/%Y')}")
print(f"Candles do dia: {len(df_dia)}")
print(f"Warmup: {len(warmup)} candles")
print(f"Candles do dia (via hist): {len(dia_candles)}")

# ======= ENGINE 1: Backtest puro (so dia, tick_size=5) =======
engine_bt = SMCEngineV3(
    symbol=symbol, swing_length=5, risk_reward_ratio=3.0,
    min_volume_ratio=0.0, min_ob_size_atr=0.0, use_not_mitigated_filter=True,
    max_pending_candles=150, entry_delay_candles=1, tick_size=5.0,
)
for i in range(len(df_dia)):
    row = df_dia.iloc[i]
    engine_bt.add_candle({
        'open': float(row['open']), 'high': float(row['high']),
        'low': float(row['low']), 'close': float(row['close']),
        'volume': float(row.get('real_volume', row.get('tick_volume', 0)))
    })

trades_bt = engine_bt.get_all_trades()

# ======= ENGINE 2: Modo live (warmup + dia, tick_size=5) =======
engine_live = SMCEngineV3(
    symbol=symbol, swing_length=5, risk_reward_ratio=3.0,
    min_volume_ratio=0.0, min_ob_size_atr=0.0, use_not_mitigated_filter=True,
    max_pending_candles=150, entry_delay_candles=1, tick_size=5.0,
)

# Warmup
for i in range(len(warmup)):
    row = warmup.iloc[i]
    engine_live.add_candle({
        'open': float(row['open']), 'high': float(row['high']),
        'low': float(row['low']), 'close': float(row['close']),
        'volume': float(row.get('real_volume', row.get('tick_volume', 0)))
    })

candle_start = engine_live.candle_count

# Dia
for i in range(len(dia_candles)):
    row = dia_candles.iloc[i]
    engine_live.add_candle({
        'open': float(row['open']), 'high': float(row['high']),
        'low': float(row['low']), 'close': float(row['close']),
        'volume': float(row.get('real_volume', row.get('tick_volume', 0)))
    })

all_trades_live = engine_live.get_all_trades()
trades_live = [t for t in all_trades_live if t['filled_at'] >= candle_start]

# ======= COMPARAR =======
print(f"\n{'='*80}")
print("COMPARACAO: BACKTEST vs LIVE (tick_size=5)")
print(f"{'='*80}")

def show_trades(trades, label):
    w = sum(1 for t in trades if t['status'] == 'closed_tp')
    l = sum(1 for t in trades if t['status'] == 'closed_sl')
    pts = sum(t['profit_loss'] for t in trades)
    r = sum(t['profit_loss_r'] for t in trades)
    print(f"\n  {label}:")
    print(f"    Trades: {len(trades)} | Wins: {w} | Losses: {l}")
    print(f"    Lucro: {pts:+,.0f} pts | {r:+,.1f}R")
    return trades

print("\n--- BACKTEST (so candles do dia) ---")
show_trades(trades_bt, "Backtest")
print(f"\n  {'#':>3} {'Dir':>8} {'Entry':>10} {'SL':>10} {'TP':>10} {'Result':>7} {'P/L':>8}")
print(f"  {'-'*60}")
for i, t in enumerate(trades_bt):
    r = 'WIN' if t['status'] == 'closed_tp' else 'LOSS'
    print(f"  {i+1:>3} {t['direction']:>8} {t['entry_price']:>10,.0f} {t['stop_loss']:>10,.0f} "
          f"{t['take_profit']:>10,.0f} {r:>7} {t['profit_loss']:>+8,.0f}")

print("\n--- LIVE (10k warmup + dia) ---")
show_trades(trades_live, "Live")
print(f"\n  {'#':>3} {'Dir':>8} {'Entry':>10} {'SL':>10} {'TP':>10} {'Result':>7} {'P/L':>8}")
print(f"  {'-'*60}")
for i, t in enumerate(trades_live):
    r = 'WIN' if t['status'] == 'closed_tp' else 'LOSS'
    print(f"  {i+1:>3} {t['direction']:>8} {t['entry_price']:>10,.0f} {t['stop_loss']:>10,.0f} "
          f"{t['take_profit']:>10,.0f} {r:>7} {t['profit_loss']:>+8,.0f}")

# Verificar match
print(f"\n{'='*80}")
if len(trades_bt) == len(trades_live):
    match = True
    for i in range(len(trades_bt)):
        bt = trades_bt[i]
        lv = trades_live[i]
        if (bt['entry_price'] != lv['entry_price'] or
            bt['stop_loss'] != lv['stop_loss'] or
            bt['take_profit'] != lv['take_profit'] or
            bt['status'] != lv['status']):
            match = False
            print(f"  DIFERENCA no trade #{i+1}:")
            print(f"    BT: {bt['entry_price']:,.0f} SL={bt['stop_loss']:,.0f} TP={bt['take_profit']:,.0f} {bt['status']}")
            print(f"    LV: {lv['entry_price']:,.0f} SL={lv['stop_loss']:,.0f} TP={lv['take_profit']:,.0f} {lv['status']}")
    if match:
        print("RESULTADO: IDENTICO - Backtest e Live geram os mesmos trades!")
    else:
        print("RESULTADO: Trades diferentes entre Backtest e Live")
else:
    print(f"RESULTADO: Quantidade diferente - BT={len(trades_bt)} vs Live={len(trades_live)}")
    pts_bt = sum(t['profit_loss'] for t in trades_bt)
    pts_lv = sum(t['profit_loss'] for t in trades_live)
    print(f"  Lucro BT: {pts_bt:+,.0f} pts | Lucro Live: {pts_lv:+,.0f} pts | Diff: {pts_lv-pts_bt:+,.0f}")
print(f"{'='*80}")
