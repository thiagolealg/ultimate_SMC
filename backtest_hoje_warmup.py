"""Backtest de hoje COM warmup (igual ao bot live) - conta sinais, ordens, cancelamentos"""
import sys
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime
from smc_engine_v3 import SMCEngineV3

print("Conectando ao MetaTrader 5...")
if not mt5.initialize():
    print(f"ERRO: {mt5.last_error()}")
    sys.exit(1)

symbols_to_try = ["WIN$N", "WING26", "WINH26"]
symbol = None
for s in symbols_to_try:
    if mt5.symbol_info(s) is not None:
        symbol = s
        mt5.symbol_select(s, True)
        break
print(f"Simbolo: {symbol}")

# Puxar dados de hoje
hoje = datetime.now().date()
inicio = datetime(hoje.year, hoje.month, hoje.day, 0, 0)
fim = datetime(hoje.year, hoje.month, hoje.day, 23, 59)
rates_hoje = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, inicio, fim)

# Puxar warmup (10000 candles antes de hoje)
WARMUP = 10000
rates_warmup = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 1, WARMUP + 600)
mt5.shutdown()

if rates_hoje is None or len(rates_hoje) == 0:
    print("ERRO: sem dados de hoje"); sys.exit(1)

df_hoje = pd.DataFrame(rates_hoje)
df_hoje['time'] = pd.to_datetime(df_hoje['time'], unit='s')
df_hoje = df_hoje[df_hoje['time'].dt.date == hoje].reset_index(drop=True)

df_warmup = pd.DataFrame(rates_warmup)
df_warmup['time'] = pd.to_datetime(df_warmup['time'], unit='s')
df_warmup = df_warmup[df_warmup['time'].dt.date < hoje]
if len(df_warmup) > WARMUP:
    df_warmup = df_warmup.tail(WARMUP).reset_index(drop=True)

print(f"Warmup: {len(df_warmup):,} candles")
print(f"Hoje: {len(df_hoje):,} candles ({df_hoje['time'].iloc[0]} ate {df_hoje['time'].iloc[-1]})")

# Engine com warmup
engine = SMCEngineV3(
    symbol=symbol, swing_length=5, risk_reward_ratio=3.0,
    min_volume_ratio=0.0, min_ob_size_atr=0.0,
    use_not_mitigated_filter=True, max_pending_candles=150,
    entry_delay_candles=1, tick_size=5.0,
)

# Warmup
for i in range(len(df_warmup)):
    row = df_warmup.iloc[i]
    engine.add_candle({
        'open': float(row['open']), 'high': float(row['high']),
        'low': float(row['low']), 'close': float(row['close']),
        'volume': float(row.get('real_volume', row.get('tick_volume', 0)))
    })

warmup_idx = engine.candle_count
print(f"Warmup completo: {warmup_idx} candles processados")

# Processar hoje e contar eventos
sinais = 0
fills = 0
expires = 0
cancels = 0
closes = 0
all_signals = []
all_trades = []

for i in range(len(df_hoje)):
    row = df_hoje.iloc[i]
    events = engine.add_candle({
        'open': float(row['open']), 'high': float(row['high']),
        'low': float(row['low']), 'close': float(row['close']),
        'volume': float(row.get('real_volume', row.get('tick_volume', 0)))
    })

    t = row['time'].strftime('%H:%M')

    for s in events.get('new_signals', []):
        sinais += 1
        d = s['direction']
        e = s['entry_price']
        sl = s['stop_loss']
        tp = s['take_profit']
        sl_size = abs(e - sl)
        conf = s['confidence']
        all_signals.append({'time': t, 'dir': d, 'entry': e, 'sl': sl, 'tp': tp,
                           'sl_size': sl_size, 'conf': conf, 'order_id': s['order_id']})
        print(f"  [{t}] SINAL #{s['order_id']}: {d} @ {e:,.0f} SL={sl:,.0f} TP={tp:,.0f} Conf={conf:.0f}%")

    for f in events.get('filled_orders', []):
        fills += 1
        print(f"  [{t}] FILL: {f['order_id']} {f['direction']} @ {f['entry_price']:,.0f}")

    for e_evt in events.get('expired_orders', []):
        expires += 1
        print(f"  [{t}] EXPIRADA: {e_evt['order_id']}")

    for c in events.get('cancelled_orders', []):
        cancels += 1
        print(f"  [{t}] CANCELADA: {c['order_id']} ({c.get('reason', '?')})")

    for cl in events.get('closed_trades', []):
        closes += 1
        status = 'WIN' if cl['status'] == 'closed_tp' else 'LOSS'
        pnl = cl['profit_loss']
        pnl_r = cl['profit_loss_r']
        all_trades.append({'time': t, 'dir': cl['direction'], 'entry': cl['entry_price'],
                          'status': status, 'pnl': pnl, 'pnl_r': pnl_r})
        print(f"  [{t}] CLOSE {status}: {cl['direction']} @ {cl['entry_price']:,.0f} P/L={pnl:+,.0f} ({pnl_r:+.1f}R)")

# Resultado
total_pnl = sum(t['pnl'] for t in all_trades)
total_r = sum(t['pnl_r'] for t in all_trades)
wins = sum(1 for t in all_trades if t['status'] == 'WIN')
losses = sum(1 for t in all_trades if t['status'] == 'LOSS')
wr = wins / len(all_trades) * 100 if all_trades else 0

print(f"\n{'='*70}")
print(f"RESULTADO BACKTEST HOJE COM WARMUP ({hoje})")
print(f"{'='*70}")
print(f"  Sinais gerados: {sinais}")
print(f"  Fills: {fills}")
print(f"  Expiracoes: {expires}")
print(f"  Cancelamentos: {cancels}")
print(f"  Trades fechados: {closes}")
print(f"  Wins: {wins} | Losses: {losses} | WR: {wr:.1f}%")
print(f"  P/L: {total_pnl:+,.0f} pts ({total_r:+,.1f}R)")

if all_trades:
    print(f"\n  {'#':<4} {'Dir':<8} {'Entry':>8} {'Result':<6} {'P/L pts':>10} {'P/L R':>8}")
    print(f"  {'-'*50}")
    for i, t in enumerate(all_trades, 1):
        print(f"  {i:<4} {t['dir']:<8} {t['entry']:>8,.0f} {t['status']:<6} {t['pnl']:>+10,.0f} {t['pnl_r']:>+8.1f}")
    print(f"  {'-'*50}")
    print(f"  {'TOTAL':<22} {'':<6} {total_pnl:>+10,.0f} {total_r:>+8.1f}")
