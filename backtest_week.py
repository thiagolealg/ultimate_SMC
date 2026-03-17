"""Backtest da semana atual - M1-only e MTF M15"""
import sys, os, collections
os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.stdout.reconfigure(encoding='utf-8')
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime
from smc_engine_v3 import SMCEngineV3

mt5.initialize()
symbol = None
for s in ['WIN$N', 'WING26', 'WINH26', 'WINJ26']:
    if mt5.symbol_info(s) is not None:
        symbol = s
        mt5.symbol_select(s, True)
        break
print(f"Simbolo: {symbol}")

rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, datetime(2025, 1, 1), datetime(2026, 3, 7))
mt5.shutdown()

df = pd.DataFrame(rates)
df['time_ts'] = df['time']
df['time'] = pd.to_datetime(df['time'], unit='s')
df = df.drop_duplicates(subset='time').sort_values('time').reset_index(drop=True)
print(f"Total: {len(df):,} candles")
print(f"Periodo: {df['time'].iloc[0]} ate {df['time'].iloc[-1]}")

WEEK_START = datetime(2026, 3, 2)
WEEK_END = datetime(2026, 3, 7)


def run_and_report(name, engine, df, need_time=False):
    for i in range(len(df)):
        row = df.iloc[i]
        candle = {
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
            'volume': float(row.get('real_volume', row.get('tick_volume', 0))),
        }
        if need_time:
            candle['time'] = int(row['time_ts'])
        engine.add_candle(candle)

    trades = engine.get_all_trades()

    week_trades = []
    trades_2026 = []
    for t in trades:
        fill_idx = t['filled_at']
        if fill_idx < len(df):
            ft = df['time'].iloc[fill_idx]
            ct = df['time'].iloc[min(t['closed_at'], len(df) - 1)]
            t_ext = {**t, 'fill_time': ft, 'close_time': ct}
            if ft.year == 2026:
                trades_2026.append(t_ext)
            if WEEK_START <= ft < WEEK_END:
                week_trades.append(t_ext)

    print(f"\n{'=' * 70}")
    print(f"{name}")
    print(f"{'=' * 70}")

    if week_trades:
        wins = sum(1 for t in week_trades if t['status'] == 'closed_tp')
        losses = sum(1 for t in week_trades if t['status'] == 'closed_sl')
        total = wins + losses
        pnl = sum(t['profit_loss'] for t in week_trades)
        wr = wins / total * 100 if total > 0 else 0
        print(f"  Semana (Mar 2-6): {total} trades | {wins}W/{losses}L | WR {wr:.0f}% | {pnl:+.0f} pts")
        print()
        print(f"  {'Dir':<8} {'Status':<6} {'Entry':>8} {'SL':>8} {'TP':>8} {'Exit':>8} {'P/L':>7}  Fill Time")
        print(f"  {'-' * 75}")
        for t in week_trades:
            st = 'WIN' if t['status'] == 'closed_tp' else 'LOSS'
            print(f"  {t['direction']:<8} {st:<6} {t['entry_price']:>8.0f} "
                  f"{t['stop_loss']:>8.0f} {t['take_profit']:>8.0f} "
                  f"{t['exit_price']:>8.0f} {t['profit_loss']:>+7.0f}  {t['fill_time']}")
    else:
        print("  Semana (Mar 2-6): NENHUM trade")

    # 2026 resumo
    w26 = sum(1 for t in trades_2026 if t['status'] == 'closed_tp')
    l26 = sum(1 for t in trades_2026 if t['status'] == 'closed_sl')
    t26 = w26 + l26
    p26 = sum(t['profit_loss'] for t in trades_2026)
    wr26 = w26 / t26 * 100 if t26 > 0 else 0
    week_pnl = collections.defaultdict(float)
    for t in trades_2026:
        w = t['fill_time'].isocalendar()[1]
        week_pnl[w] += t['profit_loss']
    weeks_pos = sum(1 for v in week_pnl.values() if v > 0)
    weeks_total = len(week_pnl)
    print(f"\n  2026 total: {t26} trades | {w26}W/{l26}L | WR {wr26:.1f}% | "
          f"{p26:+.0f} pts | {weeks_pos}/{weeks_total} semanas +")


# M1-only
engine_m1 = SMCEngineV3(
    symbol=symbol, swing_length=5, risk_reward_ratio=2.0,
    min_volume_ratio=0.0, min_ob_size_atr=0.3,
    use_not_mitigated_filter=True, max_pending_candles=150,
    entry_delay_candles=1, tick_size=5.0,
    min_confidence=0.0, max_sl_points=50.0,
    min_patterns=0, entry_retracement=0.7, htf_period=1)

run_and_report("M1-ONLY (config producao: RR=2, ret=0.7, sl<=50)", engine_m1, df)

# MTF M15
engine_mtf = SMCEngineV3(
    symbol=symbol, swing_length=5, risk_reward_ratio=2.0,
    min_volume_ratio=0.0, min_ob_size_atr=0.3,
    use_not_mitigated_filter=True, max_pending_candles=300,
    entry_delay_candles=1, tick_size=5.0,
    min_confidence=0.0, max_sl_points=150.0,
    min_patterns=0, entry_retracement=0.7, htf_period=15)

run_and_report("MTF M15 (RR=2, ret=0.7, sl<=150, htf=15)", engine_mtf, df, need_time=True)
