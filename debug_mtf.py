"""
Debug MTF - Diagnosticar por que MTF M15 tem ~40% WR vs M15-standalone 66% WR
============================================================================
Compara passo a passo: OBs detectados, ordens criadas, fills, cancelamentos.
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

# Conectar
print("Conectando ao MT5...")
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

rates_m1 = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, inicio, fim)
rates_m15 = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M15, inicio, fim)
mt5.shutdown()

df_m1 = pd.DataFrame(rates_m1)
df_m1['time_ts'] = df_m1['time']
df_m1['time'] = pd.to_datetime(df_m1['time'], unit='s')
df_m1 = df_m1[df_m1['time'].dt.year >= 2025].reset_index(drop=True)
df_m1 = df_m1.drop_duplicates(subset='time').sort_values('time').reset_index(drop=True)

df_m15 = pd.DataFrame(rates_m15)
df_m15['time'] = pd.to_datetime(df_m15['time'], unit='s')
df_m15 = df_m15[df_m15['time'].dt.year >= 2025].reset_index(drop=True)

print(f"M1: {len(df_m1):,} candles")
print(f"M15: {len(df_m15):,} candles")

# ============================================================
# 1. RODAR M15-STANDALONE com tracking detalhado
# ============================================================
print(f"\n{'='*80}")
print("M15-STANDALONE")
print(f"{'='*80}")

engine_m15 = SMCEngineV3(
    symbol=symbol, swing_length=5, risk_reward_ratio=2.0,
    min_volume_ratio=0.0, min_ob_size_atr=0.3,
    use_not_mitigated_filter=True, max_pending_candles=30,
    entry_delay_candles=1, tick_size=5.0,
    min_confidence=0.0, max_sl_points=200.0,
    min_patterns=0, entry_retracement=0.7,
    htf_period=1,
)

m15_events_log = {'obs': 0, 'signals': 0, 'fills': 0, 'tp': 0, 'sl': 0,
                  'expired': 0, 'cancelled_mitigated': 0, 'cancelled_fill': 0,
                  'sl_sizes': [], 'ob_sizes': [], 'ob_sizes_atr': []}

for i in range(len(df_m15)):
    row = df_m15.iloc[i]
    events = engine_m15.add_candle({
        'open': float(row['open']),
        'high': float(row['high']),
        'low': float(row['low']),
        'close': float(row['close']),
        'volume': float(row.get('real_volume', row.get('tick_volume', 0))),
    })
    m15_events_log['obs'] += len(events['new_obs'])
    m15_events_log['signals'] += len(events['new_signals'])
    m15_events_log['fills'] += len(events['filled_orders'])
    for t in events['closed_trades']:
        if t['status'] == 'closed_tp':
            m15_events_log['tp'] += 1
        else:
            m15_events_log['sl'] += 1
    m15_events_log['expired'] += len(events['expired_orders'])
    for c in events['cancelled_orders']:
        if c.get('reason') == 'ob_mitigated_on_fill':
            m15_events_log['cancelled_fill'] += 1
        else:
            m15_events_log['cancelled_mitigated'] += 1

    for ob in events['new_obs']:
        m15_events_log['ob_sizes'].append(ob.ob_size)
        m15_events_log['ob_sizes_atr'].append(ob.ob_size_atr)

    for sig in events['new_signals']:
        sl_size = abs(sig['entry_price'] - sig['stop_loss'])
        m15_events_log['sl_sizes'].append(sl_size)

stats_m15 = engine_m15.get_stats()
trades_m15 = engine_m15.get_all_trades()

print(f"  OBs detectados:           {m15_events_log['obs']}")
print(f"  Sinais criados:           {m15_events_log['signals']}")
print(f"  Fills:                    {m15_events_log['fills']}")
print(f"  TP (wins):                {m15_events_log['tp']}")
print(f"  SL (losses):              {m15_events_log['sl']}")
print(f"  Expiradas:                {m15_events_log['expired']}")
print(f"  Canceladas (mitigacao):   {m15_events_log['cancelled_mitigated']}")
print(f"  Canceladas (fill):        {m15_events_log['cancelled_fill']}")
print(f"  Total trades:             {stats_m15['total_trades']}")
print(f"  WR:                       {stats_m15['win_rate']:.1f}%")
if m15_events_log['ob_sizes']:
    print(f"  OB size medio:            {np.mean(m15_events_log['ob_sizes']):.1f} pts")
    print(f"  OB size ATR medio:        {np.mean(m15_events_log['ob_sizes_atr']):.2f}")
if m15_events_log['sl_sizes']:
    print(f"  SL medio:                 {np.mean(m15_events_log['sl_sizes']):.1f} pts")

# ============================================================
# 2. RODAR MTF M15 com tracking detalhado
# ============================================================
print(f"\n{'='*80}")
print("MTF M15 (OBs do M15, execucao no M1)")
print(f"{'='*80}")

for max_sl in [100, 150, 200]:
    print(f"\n  --- max_sl={max_sl} ---")
    engine_mtf = SMCEngineV3(
        symbol=symbol, swing_length=5, risk_reward_ratio=2.0,
        min_volume_ratio=0.0, min_ob_size_atr=0.3,
        use_not_mitigated_filter=True, max_pending_candles=300,
        entry_delay_candles=1, tick_size=5.0,
        min_confidence=0.0, max_sl_points=float(max_sl),
        min_patterns=0, entry_retracement=0.7,
        htf_period=15,
    )

    mtf_log = {'obs': 0, 'signals': 0, 'fills': 0, 'tp': 0, 'sl': 0,
               'expired': 0, 'cancelled_mitigated': 0, 'cancelled_fill': 0,
               'sl_sizes': [], 'ob_sizes': [], 'ob_sizes_atr': [],
               'fill_details': [], 'signal_details': []}

    for i in range(len(df_m1)):
        row = df_m1.iloc[i]
        events = engine_mtf.add_candle({
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
            'volume': float(row.get('real_volume', row.get('tick_volume', 0))),
            'time': int(row['time_ts']),
        })
        mtf_log['obs'] += len(events['new_obs'])
        mtf_log['signals'] += len(events['new_signals'])
        mtf_log['fills'] += len(events['filled_orders'])
        for t in events['closed_trades']:
            if t['status'] == 'closed_tp':
                mtf_log['tp'] += 1
            else:
                mtf_log['sl'] += 1
        mtf_log['expired'] += len(events['expired_orders'])
        for c in events['cancelled_orders']:
            if c.get('reason') == 'ob_mitigated_on_fill':
                mtf_log['cancelled_fill'] += 1
            else:
                mtf_log['cancelled_mitigated'] += 1

        for ob in events['new_obs']:
            mtf_log['ob_sizes'].append(ob.ob_size)
            mtf_log['ob_sizes_atr'].append(ob.ob_size_atr)

        for sig in events['new_signals']:
            sl_size = abs(sig['entry_price'] - sig['stop_loss'])
            mtf_log['sl_sizes'].append(sl_size)
            mtf_log['signal_details'].append({
                'oid': sig['order_id'],
                'dir': sig['direction'],
                'entry': sig['entry_price'],
                'sl': sig['stop_loss'],
                'tp': sig['take_profit'],
                'ob_top': sig['ob_top'],
                'ob_bottom': sig['ob_bottom'],
                'conf': sig['confidence'],
                'patterns': sig['patterns'],
                'time': str(row['time']),
            })

    stats_mtf = engine_mtf.get_stats()
    trades_mtf = engine_mtf.get_all_trades()

    print(f"  OBs detectados:           {mtf_log['obs']}")
    print(f"  Sinais criados:           {mtf_log['signals']}")
    print(f"  Fills:                    {mtf_log['fills']}")
    print(f"  TP (wins):                {mtf_log['tp']}")
    print(f"  SL (losses):              {mtf_log['sl']}")
    print(f"  Expiradas:                {mtf_log['expired']}")
    print(f"  Canceladas (mitigacao):   {mtf_log['cancelled_mitigated']}")
    print(f"  Canceladas (fill):        {mtf_log['cancelled_fill']}")
    print(f"  Total trades:             {stats_mtf['total_trades']}")
    print(f"  WR:                       {stats_mtf['win_rate']:.1f}%")
    if mtf_log['ob_sizes']:
        print(f"  OB size medio:            {np.mean(mtf_log['ob_sizes']):.1f} pts")
        print(f"  OB size ATR medio:        {np.mean(mtf_log['ob_sizes_atr']):.2f}")
    if mtf_log['sl_sizes']:
        print(f"  SL medio:                 {np.mean(mtf_log['sl_sizes']):.1f} pts")

    # Pipeline conversion
    if mtf_log['obs'] > 0:
        print(f"\n  Pipeline de conversao:")
        print(f"    OBs -> Sinais:     {mtf_log['signals']}/{mtf_log['obs']} ({100*mtf_log['signals']/mtf_log['obs']:.1f}%)")
        total_orders = mtf_log['signals']
        if total_orders > 0:
            print(f"    Sinais -> Fills:   {mtf_log['fills']}/{total_orders} ({100*mtf_log['fills']/total_orders:.1f}%)")
            print(f"    Sinais -> Expired: {mtf_log['expired']}/{total_orders} ({100*mtf_log['expired']/total_orders:.1f}%)")
            print(f"    Sinais -> Cancel:  {mtf_log['cancelled_mitigated']+mtf_log['cancelled_fill']}/{total_orders} ({100*(mtf_log['cancelled_mitigated']+mtf_log['cancelled_fill'])/total_orders:.1f}%)")


# ============================================================
# 3. COMPARAR AGREGACAO: M15 do MT5 vs M15 agregado do M1
# ============================================================
print(f"\n\n{'='*80}")
print("VERIFICACAO: M15 do MT5 vs M15 agregado do M1")
print(f"{'='*80}")

# Agregar M1 para M15 manualmente
def aggregate_m1_to_m15(df_m1):
    """Agrega M1 para M15 usando boundaries de tempo."""
    df = df_m1.copy()
    df['boundary'] = (df['time_ts'] // (15*60)) * (15*60)
    grouped = df.groupby('boundary').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'time': 'first',
    }).reset_index()
    grouped = grouped.sort_values('boundary').reset_index(drop=True)
    return grouped

df_m15_agg = aggregate_m1_to_m15(df_m1)
print(f"M15 do MT5:     {len(df_m15)} barras")
print(f"M15 agregado:   {len(df_m15_agg)} barras")

# Comparar primeiros N bars
n_compare = min(20, len(df_m15), len(df_m15_agg))
mismatches = 0
total_compared = 0

for i in range(len(df_m15)):
    mt5_time = df_m15.iloc[i]['time']
    # Encontrar barra correspondente no agregado
    matches = df_m15_agg[df_m15_agg['time'].dt.floor('15min') == mt5_time.floor('15min')]
    if len(matches) == 0:
        continue
    total_compared += 1
    agg = matches.iloc[0]
    mt5_bar = df_m15.iloc[i]

    o_match = abs(mt5_bar['open'] - agg['open']) < 1
    h_match = abs(mt5_bar['high'] - agg['high']) < 1
    l_match = abs(mt5_bar['low'] - agg['low']) < 1
    c_match = abs(mt5_bar['close'] - agg['close']) < 1

    if not (o_match and h_match and l_match and c_match):
        mismatches += 1
        if mismatches <= 10:
            print(f"  MISMATCH em {mt5_time}:")
            print(f"    MT5:  O={mt5_bar['open']:.0f} H={mt5_bar['high']:.0f} L={mt5_bar['low']:.0f} C={mt5_bar['close']:.0f}")
            print(f"    AGG:  O={agg['open']:.0f} H={agg['high']:.0f} L={agg['low']:.0f} C={agg['close']:.0f}")

print(f"\nTotal comparadas: {total_compared}")
print(f"Mismatches: {mismatches} ({100*mismatches/total_compared:.1f}% se total_compared > 0)")


# ============================================================
# 4. DETALHE DOS TRADES MTF (sl=150)
# ============================================================
print(f"\n\n{'='*80}")
print("DETALHE TRADES MTF M15 (sl=150)")
print(f"{'='*80}")

engine_detail = SMCEngineV3(
    symbol=symbol, swing_length=5, risk_reward_ratio=2.0,
    min_volume_ratio=0.0, min_ob_size_atr=0.3,
    use_not_mitigated_filter=True, max_pending_candles=300,
    entry_delay_candles=1, tick_size=5.0,
    min_confidence=0.0, max_sl_points=150.0,
    min_patterns=0, entry_retracement=0.7,
    htf_period=15,
)

detail_trades = []
for i in range(len(df_m1)):
    row = df_m1.iloc[i]
    events = engine_detail.add_candle({
        'open': float(row['open']),
        'high': float(row['high']),
        'low': float(row['low']),
        'close': float(row['close']),
        'volume': float(row.get('real_volume', row.get('tick_volume', 0))),
        'time': int(row['time_ts']),
    })
    for t in events['closed_trades']:
        # Encontrar tempo do fill e close
        fill_time = df_m1.iloc[min(t['closed_at'], len(df_m1)-1)]['time'] if t['closed_at'] < len(df_m1) else 'N/A'
        detail_trades.append({
            'oid': t['order_id'],
            'dir': t['direction'],
            'status': t['status'],
            'entry': t['entry_price'],
            'exit': t['exit_price'],
            'sl': abs(t['entry_price'] - events['closed_trades'][0].get('stop_loss', 0)) if False else 0,
            'pnl': t['profit_loss'],
            'pnl_r': t['profit_loss_r'],
            'close_time': str(fill_time),
        })

all_trades = engine_detail.get_all_trades()
print(f"\n{'Dir':<8} {'Status':<10} {'Entry':>10} {'SL':>10} {'TP':>10} {'Exit':>10} {'P/L':>8} {'SL_sz':>6} {'Dur':>4}")
print("-" * 90)

wins = 0
losses = 0
for t in all_trades:
    sl_size = abs(t['entry_price'] - t['stop_loss'])
    status = 'WIN' if t['status'] == 'closed_tp' else 'LOSS'
    if status == 'WIN':
        wins += 1
    else:
        losses += 1
    dur = t['duration_candles']
    fill_idx = t.get('filled_at', 0)
    fill_time = df_m1.iloc[min(fill_idx, len(df_m1)-1)]['time'] if fill_idx < len(df_m1) else 'N/A'
    print(f"{t['direction']:<8} {status:<10} {t['entry_price']:>10.0f} {t['stop_loss']:>10.0f} {t['take_profit']:>10.0f} "
          f"{t['exit_price']:>10.0f} {t['profit_loss']:>+8.0f} {sl_size:>6.0f} {dur:>4}  {fill_time}")

print(f"\nTotal: {len(all_trades)} trades | W={wins} L={losses} | WR={100*wins/len(all_trades):.1f}%")

# Analisar SL sizes dos wins vs losses
win_sls = [abs(t['entry_price'] - t['stop_loss']) for t in all_trades if t['status'] == 'closed_tp']
loss_sls = [abs(t['entry_price'] - t['stop_loss']) for t in all_trades if t['status'] == 'closed_sl']

if win_sls and loss_sls:
    print(f"\nSL medio dos WINs:  {np.mean(win_sls):.1f} pts")
    print(f"SL medio dos LOSSes: {np.mean(loss_sls):.1f} pts")
    print(f"Duracao media WINs:  {np.mean([t['duration_candles'] for t in all_trades if t['status'] == 'closed_tp']):.1f}")
    print(f"Duracao media LOSSes: {np.mean([t['duration_candles'] for t in all_trades if t['status'] == 'closed_sl']):.1f}")

# Analisar wait_candles
wait_fills = [t['wait_candles'] for t in all_trades]
print(f"\nWait candles (antes do fill):")
print(f"  Media: {np.mean(wait_fills):.1f}")
print(f"  Mediana: {np.median(wait_fills):.1f}")
print(f"  Max: {max(wait_fills)}")
