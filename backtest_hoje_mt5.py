"""
Backtest de Hoje - Dados do MetaTrader 5
=========================================
Puxa candles de 1 minuto do dia atual via MT5 e roda o SMCEngineV3.
"""
import sys
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from smc_engine_v3 import SMCEngineV3, OrderStatus, SignalDirection

# ============================================================
# CONECTAR AO MT5
# ============================================================
print("Conectando ao MetaTrader 5...")
if not mt5.initialize():
    print(f"ERRO: Falha ao inicializar MT5: {mt5.last_error()}")
    sys.exit(1)

info = mt5.terminal_info()
print(f"MT5 conectado: {info.name} (Build {info.build})")

# ============================================================
# DETECTAR SÍMBOLO WIN
# ============================================================
# Tenta encontrar o símbolo correto do mini índice
symbols_to_try = ["WIN$N", "WING26", "WINH26", "WINJ26", "WIN$", "WINM25"]
symbol = None

for s in symbols_to_try:
    sym_info = mt5.symbol_info(s)
    if sym_info is not None:
        symbol = s
        if not sym_info.visible:
            mt5.symbol_select(s, True)
        break

if symbol is None:
    # Busca qualquer símbolo que comece com WIN
    all_symbols = mt5.symbols_get()
    win_symbols = [s.name for s in all_symbols if s.name.startswith("WIN")]
    if win_symbols:
        symbol = win_symbols[0]
        mt5.symbol_select(symbol, True)
        print(f"Símbolos WIN encontrados: {win_symbols}")
    else:
        print("ERRO: Nenhum símbolo WIN encontrado no MT5!")
        mt5.shutdown()
        sys.exit(1)

print(f"Símbolo selecionado: {symbol}")

# ============================================================
# PUXAR DADOS DE HOJE (M1)
# ============================================================
# Tenta hoje, se não tiver dados busca o último pregão
agora = datetime.now() + timedelta(hours=1)
rates = None
dia_backtest = None

for dias_atras in range(0, 7):
    dia = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=dias_atras)
    fim = dia + timedelta(hours=23, minutes=59)
    r = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, dia, fim)
    if r is not None and len(r) > 10:
        rates = r
        dia_backtest = dia
        break

if rates is None or len(rates) == 0:
    print(f"ERRO: Nenhum candle encontrado nos últimos 7 dias.")
    print(f"Último erro MT5: {mt5.last_error()}")
    mt5.shutdown()
    sys.exit(1)

print(f"\nÚltimo pregão encontrado: {dia_backtest.strftime('%d/%m/%Y')}")

df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')

print(f"Total: {len(df)} candles de 1 minuto")
print(f"Período: {df['time'].iloc[0]} até {df['time'].iloc[-1]}")
print(f"Abertura: {df['open'].iloc[0]:,.0f} | Último: {df['close'].iloc[-1]:,.0f}")

# ============================================================
# EXECUTAR ENGINE V3
# ============================================================
print("\nExecutando SMC Engine V3...")
print("  Config: RR 3:1 | max_pending=150 | sem filtros vol/size")

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

all_events = []
for i, row in df.iterrows():
    events = engine.add_candle({
        'open': float(row['open']),
        'high': float(row['high']),
        'low': float(row['low']),
        'close': float(row['close']),
        'volume': float(row.get('real_volume', row.get('tick_volume', 0)))
    })
    if events.get('new_signals'):
        for sig in events['new_signals']:
            candle_time = df.iloc[i if isinstance(i, int) else df.index.get_loc(i)]['time']
            print(f"  [{candle_time}] SINAL {sig['direction']} @ {sig['entry_price']:,.0f} "
                  f"SL={sig['stop_loss']:,.0f} TP={sig['take_profit']:,.0f}")
    if events.get('filled_orders'):
        for fill in events['filled_orders']:
            idx = engine.candle_count - 1
            candle_time = df['time'].iloc[min(idx, len(df)-1)]
            print(f"  [{candle_time}] FILL {fill['direction']} @ {fill['entry_price']:,.0f}")
    if events.get('closed_trades'):
        for trade in events['closed_trades']:
            idx = engine.candle_count - 1
            candle_time = df['time'].iloc[min(idx, len(df)-1)]
            status_emoji = "+" if trade['status'] == 'closed_tp' else "-"
            print(f"  [{candle_time}] CLOSE {status_emoji} {trade['direction']} "
                  f"P/L={trade['profit_loss']:+,.0f} pts ({trade['profit_loss_r']:+.1f}R)")

# ============================================================
# COLETAR TRADES
# ============================================================
raw_trades = engine.get_all_trades()
print(f"\n{'='*70}")
print(f"RESULTADO DO BACKTEST - {dia_backtest.strftime('%d/%m/%Y')} ({symbol})")
print(f"{'='*70}")
print(f"  Candles processados: {len(df)}")

if len(raw_trades) == 0:
    # Verificar ordens pendentes
    pending = len(engine.pending_orders) if hasattr(engine, 'pending_orders') else 0
    filled = len(engine.filled_orders) if hasattr(engine, 'filled_orders') else 0
    obs = len(engine.order_blocks) if hasattr(engine, 'order_blocks') else 0
    print(f"  Order Blocks detectados: {obs}")
    print(f"  Ordens pendentes: {pending}")
    print(f"  Ordens em aberto (filled): {filled}")
    print(f"  Trades fechados: 0")
    print(f"\n  Nenhum trade fechado ainda hoje.")
    if pending > 0 or filled > 0:
        print(f"  Existem ordens aguardando execução/fechamento.")
else:
    # Construir DataFrame de trades
    trade_data = []
    for t in raw_trades:
        fill_idx = t['filled_at']
        close_idx = t['closed_at']
        fill_time = df['time'].iloc[fill_idx] if fill_idx < len(df) else None
        close_time = df['time'].iloc[close_idx] if close_idx < len(df) else None

        trade_data.append({
            'direction': t['direction'],
            'fill_time': fill_time,
            'close_time': close_time,
            'entry': t['entry_price'],
            'tp': t['take_profit'],
            'sl': t['stop_loss'],
            'result': 'WIN' if t['status'] == 'closed_tp' else 'LOSS',
            'pnl_pts': t['profit_loss'],
            'pnl_r': t['profit_loss_r'],
            'confidence': t['confidence'],
            'patterns': str(t['patterns']),
            'wait_candles': t['wait_candles'],
            'duration_candles': t['duration_candles'],
        })

    tdf = pd.DataFrame(trade_data)
    wins = len(tdf[tdf['result'] == 'WIN'])
    losses = len(tdf[tdf['result'] == 'LOSS'])
    total = wins + losses
    wr = wins / total * 100 if total > 0 else 0
    total_pts = tdf['pnl_pts'].sum()
    total_r = tdf['pnl_r'].sum()
    win_pts = tdf[tdf['result'] == 'WIN']['pnl_pts'].sum()
    loss_pts = abs(tdf[tdf['result'] == 'LOSS']['pnl_pts'].sum())
    pf = win_pts / loss_pts if loss_pts > 0 else float('inf')

    print(f"  Total de trades: {total}")
    print(f"  Wins: {wins} | Losses: {losses}")
    print(f"  Win Rate: {wr:.1f}%")
    print(f"  Profit Factor: {pf:.2f}")
    print(f"  Lucro total: {total_pts:+,.2f} pontos")
    print(f"  Lucro total: {total_r:+,.2f} R")

    # Detalhe de cada trade
    print(f"\n{'='*70}")
    print("DETALHE DOS TRADES")
    print(f"{'='*70}")
    print(f"{'#':>3} {'Dir':>7} {'Fill':>20} {'Entry':>10} {'SL':>10} {'TP':>10} {'Result':>6} {'P/L pts':>10} {'P/L R':>7}")
    print("-" * 95)
    for idx, t in tdf.iterrows():
        fill_str = t['fill_time'].strftime('%H:%M') if t['fill_time'] is not None else '?'
        print(f"{idx+1:>3} {t['direction']:>7} {fill_str:>20} {t['entry']:>10,.0f} {t['sl']:>10,.0f} "
              f"{t['tp']:>10,.0f} {t['result']:>6} {t['pnl_pts']:>+10,.0f} {t['pnl_r']:>+7.1f}")

# Estado atual
print(f"\n{'='*70}")
print("ESTADO ATUAL DO ENGINE")
print(f"{'='*70}")
stats = engine.get_stats() if hasattr(engine, 'get_stats') else {}
if stats:
    for k, v in stats.items():
        print(f"  {k}: {v}")
else:
    print(f"  Candles processados: {engine.candle_count}")
    if hasattr(engine, 'order_blocks'):
        print(f"  Order Blocks: {len(engine.order_blocks)}")
    if hasattr(engine, 'pending_orders'):
        print(f"  Ordens pendentes: {len(engine.pending_orders)}")
    if hasattr(engine, 'filled_orders'):
        print(f"  Ordens em aberto: {len(engine.filled_orders)}")

mt5.shutdown()
print("\nMT5 desconectado. Backtest concluído.")
