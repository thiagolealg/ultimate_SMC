"""
Backtest Multi-Timeframe - Compara assertividade da engine em M1, M5, M15, M30, H1
==================================================================================
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
# 1. CONECTAR AO MT5
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

# ============================================================
# 2. PUXAR DADOS EM CADA TIMEFRAME
# ============================================================
inicio = datetime(2025, 1, 1)
fim = datetime(2026, 2, 24)

timeframes = {
    'M1':  mt5.TIMEFRAME_M1,
    'M5':  mt5.TIMEFRAME_M5,
    'M15': mt5.TIMEFRAME_M15,
    'M30': mt5.TIMEFRAME_M30,
    'H1':  mt5.TIMEFRAME_H1,
}

data = {}
for tf_name, tf_code in timeframes.items():
    rates = mt5.copy_rates_range(symbol, tf_code, inicio, fim)
    if rates is not None and len(rates) > 0:
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df = df[df['time'].dt.year >= 2025].reset_index(drop=True)
        df = df.drop_duplicates(subset='time').sort_values('time').reset_index(drop=True)
        data[tf_name] = df
        print(f"  {tf_name}: {len(df):>8,} candles | {df['time'].iloc[0].date()} ate {df['time'].iloc[-1].date()}")
    else:
        print(f"  {tf_name}: SEM DADOS")

mt5.shutdown()

# ============================================================
# 3. RODAR ENGINE EM CADA TIMEFRAME
# ============================================================
# Configs: usar mesmos filtros proporcionais
# Para timeframes maiores, ajustar max_sl_points proporcionalmente
tf_configs = {
    'M1':  {'max_sl': 50,  'max_pending': 150, 'swing': 5, 'tick': 5.0},
    'M5':  {'max_sl': 100, 'max_pending': 50,  'swing': 5, 'tick': 5.0},
    'M15': {'max_sl': 200, 'max_pending': 30,  'swing': 5, 'tick': 5.0},
    'M30': {'max_sl': 300, 'max_pending': 20,  'swing': 5, 'tick': 5.0},
    'H1':  {'max_sl': 500, 'max_pending': 15,  'swing': 5, 'tick': 5.0},
}

results = {}

for tf_name, df in data.items():
    cfg = tf_configs[tf_name]
    print(f"\n{'='*80}")
    print(f"RODANDO {tf_name} ({len(df):,} candles) - SL max: {cfg['max_sl']} pts")
    print(f"{'='*80}")

    # Separar 2025 (backtest) e 2026
    df_2025 = df[df['time'].dt.year == 2025].reset_index(drop=True)
    df_2026 = df[df['time'].dt.year == 2026].reset_index(drop=True)

    for period_name, period_df in [('2025', df_2025), ('2026', df_2026), ('TOTAL', df)]:
        if len(period_df) == 0:
            continue

        # Rodar com filtros otimizados
        engine = SMCEngineV3(
            symbol=symbol,
            swing_length=cfg['swing'],
            risk_reward_ratio=2.0,
            min_volume_ratio=0.0,
            min_ob_size_atr=0.3,
            use_not_mitigated_filter=True,
            max_pending_candles=cfg['max_pending'],
            entry_delay_candles=1,
            tick_size=cfg['tick'],
            min_confidence=0.0,
            max_sl_points=float(cfg['max_sl']),
            min_patterns=0,
            entry_retracement=0.7,
        )

        for i in range(len(period_df)):
            row = period_df.iloc[i]
            engine.add_candle({
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'volume': float(row.get('real_volume', row.get('tick_volume', 0)))
            })

        stats = engine.get_stats()
        trades = engine.get_all_trades()

        if stats['total_trades'] > 0:
            dias = period_df['time'].dt.date.nunique()

            # Calcular metricas adicionais
            wins = [t for t in trades if t['status'] == 'closed_tp']
            losses = [t for t in trades if t['status'] == 'closed_sl']
            win_pts = sum(t['profit_loss'] for t in wins)
            loss_pts = abs(sum(t['profit_loss'] for t in losses))

            # Duracao media dos trades
            avg_duration = np.mean([t['duration_candles'] for t in trades]) if trades else 0
            avg_wait = np.mean([t['wait_candles'] for t in trades]) if trades else 0

            # SL medio
            avg_sl = np.mean([abs(t['entry_price'] - t['stop_loss']) for t in trades])

            # Drawdown
            cum = np.cumsum([t['profit_loss'] for t in trades])
            peak = np.maximum.accumulate(cum)
            dd = cum - peak
            max_dd = dd.min() if len(dd) > 0 else 0

            results[(tf_name, period_name)] = {
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
                'trades_dia': stats['total_trades'] / dias if dias > 0 else 0,
                'avg_duration': avg_duration,
                'avg_wait': avg_wait,
                'avg_sl': avg_sl,
                'max_dd': max_dd,
            }

# ============================================================
# 4. TABELA COMPARATIVA
# ============================================================
print(f"\n\n{'='*120}")
print("COMPARACAO DE TIMEFRAMES - PARAMETROS OTIMIZADOS (RR=2.0, ret=0.7, min_size=0.3*ATR)")
print(f"{'='*120}")

# 4a. RESUMO POR TIMEFRAME (TOTAL 2025+2026)
print(f"\n{'-'*120}")
print(f"{'TF':<6} {'Trades':>7} {'Wins':>6} {'Loss':>6} {'WR%':>7} {'PF':>7} {'P/L(pts)':>12} {'P/L(R)':>10} "
      f"{'Exp(R)':>8} {'OBs':>7} {'Tr/dia':>7} {'AvgSL':>7} {'AvgDur':>7} {'MaxDD':>10}")
print(f"{'-'*120}")

for tf_name in ['M1', 'M5', 'M15', 'M30', 'H1']:
    key = (tf_name, 'TOTAL')
    if key in results:
        r = results[key]
        print(f"{tf_name:<6} {r['trades']:>7} {r['wins']:>6} {r['losses']:>6} {r['wr']:>6.1f}% {r['pf']:>7.2f} "
              f"{r['total_pts']:>+12,.0f} {r['total_r']:>+10,.1f} {r['exp_r']:>+8.2f} {r['obs']:>7,} "
              f"{r['trades_dia']:>7.1f} {r['avg_sl']:>7.1f} {r['avg_duration']:>7.1f} {r['max_dd']:>+10,.0f}")

# 4b. POR ANO
for period in ['2025', '2026']:
    print(f"\n{'-'*120}")
    print(f"PERIODO: {period}")
    print(f"{'-'*120}")
    print(f"{'TF':<6} {'Trades':>7} {'Wins':>6} {'Loss':>6} {'WR%':>7} {'PF':>7} {'P/L(pts)':>12} {'P/L(R)':>10} "
          f"{'Exp(R)':>8} {'OBs':>7} {'Tr/dia':>7} {'AvgSL':>7} {'AvgDur':>7} {'MaxDD':>10}")
    print(f"{'-'*120}")
    for tf_name in ['M1', 'M5', 'M15', 'M30', 'H1']:
        key = (tf_name, period)
        if key in results:
            r = results[key]
            print(f"{tf_name:<6} {r['trades']:>7} {r['wins']:>6} {r['losses']:>6} {r['wr']:>6.1f}% {r['pf']:>7.2f} "
                  f"{r['total_pts']:>+12,.0f} {r['total_r']:>+10,.1f} {r['exp_r']:>+8.2f} {r['obs']:>7,} "
                  f"{r['trades_dia']:>7.1f} {r['avg_sl']:>7.1f} {r['avg_duration']:>7.1f} {r['max_dd']:>+10,.0f}")

# 4c. ANALISE
print(f"\n\n{'='*120}")
print("ANALISE")
print(f"{'='*120}")

best_wr = None
best_pf = None
best_exp = None
best_pts = None

for tf_name in ['M1', 'M5', 'M15', 'M30', 'H1']:
    key = (tf_name, 'TOTAL')
    if key in results:
        r = results[key]
        if r['trades'] >= 20:  # Minimo de trades para ser significativo
            if best_wr is None or r['wr'] > results[best_wr]['wr']:
                best_wr = key
            if best_pf is None or r['pf'] > results[best_pf]['pf']:
                best_pf = key
            if best_exp is None or r['exp_r'] > results[best_exp]['exp_r']:
                best_exp = key
            if best_pts is None or r['total_pts'] > results[best_pts]['total_pts']:
                best_pts = key

if best_wr:
    print(f"  Melhor WR:         {best_wr[0]} ({results[best_wr]['wr']:.1f}%)")
if best_pf:
    print(f"  Melhor PF:         {best_pf[0]} ({results[best_pf]['pf']:.2f})")
if best_exp:
    print(f"  Melhor Expectancia: {best_exp[0]} ({results[best_exp]['exp_r']:.2f}R)")
if best_pts:
    print(f"  Mais lucrativo:    {best_pts[0]} ({results[best_pts]['total_pts']:+,.0f} pts)")

# Análise de OBs
print(f"\n  OBs detectados por timeframe:")
for tf_name in ['M1', 'M5', 'M15', 'M30', 'H1']:
    key = (tf_name, 'TOTAL')
    if key in results:
        r = results[key]
        obs_per_trade = r['obs'] / r['trades'] if r['trades'] > 0 else 0
        print(f"    {tf_name}: {r['obs']:>6,} OBs -> {r['trades']:>5} trades (1 trade a cada {obs_per_trade:.0f} OBs)")
