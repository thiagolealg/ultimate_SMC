"""
Otimizacao V2: Foco em WR 60%
==============================
Insights da V1:
- retrace=0.7 foi o maior impacto (+5% WR)
- max_sl=50 ajuda
- Nenhuma config passou de 53% com RR=3.0

Novas dimensoes:
- RR: [2.0, 2.5, 3.0] (TP mais perto = mais WR)
- Retracement: [0.5, 0.6, 0.7, 0.8] (mais fundo = SL menor)
- max_pending: [50, 80, 150]
"""
import sys
import time
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime
from itertools import product
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

candle_data = []
for i in range(len(df)):
    row = df.iloc[i]
    candle_data.append({
        'open': float(row['open']),
        'high': float(row['high']),
        'low': float(row['low']),
        'close': float(row['close']),
        'volume': float(row['real_volume']) if row['real_volume'] > 0 else float(row['tick_volume']),
    })

print(f"Dados preparados: {len(candle_data):,} candles")


def calc_stats(trades):
    if not trades:
        return None
    wins = sum(1 for t in trades if t['status'] == 'closed_tp')
    losses = sum(1 for t in trades if t['status'] == 'closed_sl')
    total = wins + losses
    if total == 0:
        return None

    wr = wins / total * 100
    total_pnl = sum(t['profit_loss'] for t in trades)
    total_r = sum(t['profit_loss_r'] for t in trades)
    win_pts = sum(t['profit_loss'] for t in trades if t['status'] == 'closed_tp')
    loss_pts = abs(sum(t['profit_loss'] for t in trades if t['status'] == 'closed_sl'))
    pf = win_pts / loss_pts if loss_pts > 0 else float('inf')
    exp_r = total_r / total

    cumulative = 0
    peak = 0
    max_dd = 0
    for t in trades:
        cumulative += t['profit_loss']
        if cumulative > peak:
            peak = cumulative
        dd = peak - cumulative
        if dd > max_dd:
            max_dd = dd

    return {
        'trades': total, 'wins': wins, 'losses': losses,
        'wr': wr, 'pf': pf, 'total_pnl': total_pnl,
        'total_r': total_r, 'exp_r': exp_r, 'max_dd': max_dd,
    }


# ============================================================
# 2. RODAR ENGINE COM PARAMETROS ESTRUTURAIS
# ============================================================
print("\n" + "=" * 80)
print("OTIMIZACAO V2: RR + RETRACEMENT + FILTROS")
print("=" * 80)

# Parametros estruturais (precisam engine run)
engine_grid = list(product(
    [2.0, 2.5, 3.0],           # RR
    [50, 80, 150],              # max_pending
    [0.0, 0.3],                 # min_ob_size_atr
    [0.5, 0.6, 0.7, 0.8],      # entry_retracement
))
print(f"Engine runs: {len(engine_grid)}")

# Filtros pos-engine
filter_grid = list(product(
    [0, 35, 45],      # min_conf
    [0, 50],           # max_sl
    [0, 1, 2],         # min_patt
))
print(f"Filtros pos-engine: {len(filter_grid)}")
print(f"Total combinacoes: {len(engine_grid) * len(filter_grid):,}")

engine_cache = {}
start_time = time.time()

for i, (rr, max_pend, min_size, retrace) in enumerate(engine_grid):
    t0 = time.time()
    engine = SMCEngineV3(
        symbol='WIN', swing_length=5, risk_reward_ratio=rr,
        min_volume_ratio=0.0, min_ob_size_atr=min_size,
        use_not_mitigated_filter=True, max_pending_candles=max_pend,
        entry_delay_candles=1, tick_size=5.0,
        min_confidence=0, max_sl_points=0,
        min_patterns=0, entry_retracement=retrace,
    )

    for c in candle_data:
        engine.add_candle(c)

    trades = engine.get_all_trades() or []
    key = (rr, max_pend, min_size, retrace)
    engine_cache[key] = trades

    elapsed_run = time.time() - t0
    n = len(trades)
    wr = 0
    if n > 0:
        w = sum(1 for t in trades if t['status'] == 'closed_tp')
        l = sum(1 for t in trades if t['status'] == 'closed_sl')
        wr = w / (w + l) * 100 if (w + l) > 0 else 0
    print(f"  [{i+1}/{len(engine_grid)}] RR={rr} pend={max_pend} size={min_size} "
          f"ret={retrace} -> {n} trades WR={wr:.1f}% ({elapsed_run:.1f}s)")

elapsed_phase1 = time.time() - start_time
print(f"\nFase 1 completa: {len(engine_grid)} engine runs em {elapsed_phase1:.0f}s ({elapsed_phase1/60:.1f}min)")

# ============================================================
# 3. POS-FILTRAR
# ============================================================
results = []

for key, trades in engine_cache.items():
    rr, max_pend, min_size, retrace = key
    if not trades:
        continue

    for min_conf, max_sl, min_patt in filter_grid:
        ft = trades
        if min_conf > 0:
            ft = [t for t in ft if t.get('confidence', 0) >= min_conf]
        if max_sl > 0:
            ft = [t for t in ft if abs(t['entry_price'] - t['stop_loss']) <= max_sl]
        if min_patt > 0:
            ft = [t for t in ft if len(t.get('patterns', [])) - 1 >= min_patt]

        stats = calc_stats(ft)
        if stats is not None:
            stats.update({
                'rr': rr, 'min_conf': min_conf, 'max_sl': max_sl,
                'min_patt': min_patt, 'max_pend': max_pend,
                'min_size': min_size, 'retrace': retrace,
            })
            results.append(stats)

elapsed_total = time.time() - start_time
rdf = pd.DataFrame(results)

# ============================================================
# 4. RESULTADOS
# ============================================================

# Baseline
baseline = rdf[(rdf['rr'] == 3.0) & (rdf['min_conf'] == 0) & (rdf['max_sl'] == 0) &
               (rdf['min_patt'] == 0) & (rdf['max_pend'] == 150) &
               (rdf['min_size'] == 0.0) & (rdf['retrace'] == 0.5)]

print(f"\n{'='*80}")
print("BASELINE (RR=3.0, sem filtros, retrace=0.5)")
print(f"{'='*80}")
if len(baseline) > 0:
    b = baseline.iloc[0]
    print(f"  Trades: {b['trades']:.0f} | WR: {b['wr']:.1f}% | PF: {b['pf']:.2f} | "
          f"P/L: {b['total_pnl']:+,.0f} pts | Exp: {b['exp_r']:.2f}R | MaxDD: {b['max_dd']:,.0f}")

# TOP POR EXPECTANCIA (configs que maximizam R/trade)
hdr = (f"{'#':<4} {'RR':>4} {'Trades':>7} {'WR%':>6} {'PF':>6} {'Exp(R)':>7} "
       f"{'P/L pts':>10} {'MaxDD':>8} | {'Conf':>4} {'MaxSL':>5} {'Patt':>4} "
       f"{'Pend':>4} {'Size':>5} {'Retr':>5}")
sep = "-" * 110

# ----- WR >= 60% -----
f60 = rdf[(rdf['wr'] >= 60) & (rdf['trades'] >= 200)].sort_values('exp_r', ascending=False)
print(f"\n{'='*80}")
print(f"TOP 20 CONFIGS COM WR >= 60% (trades >= 200)")
print(f"{'='*80}")
print(hdr)
print(sep)
for i, (_, r) in enumerate(f60.head(20).iterrows()):
    print(f"{i+1:<4} {r['rr']:>4.1f} {r['trades']:>7.0f} {r['wr']:>5.1f}% {r['pf']:>6.2f} "
          f"{r['exp_r']:>+7.2f} {r['total_pnl']:>+10,.0f} {r['max_dd']:>8,.0f} | "
          f"{r['min_conf']:>4.0f} {r['max_sl']:>5.0f} {r['min_patt']:>4.0f} "
          f"{r['max_pend']:>4.0f} {r['min_size']:>5.1f} {r['retrace']:>5.1f}")

# ----- WR >= 55% -----
f55 = rdf[(rdf['wr'] >= 55) & (rdf['trades'] >= 300)].sort_values('exp_r', ascending=False)
print(f"\n{'='*80}")
print(f"TOP 20 CONFIGS COM WR >= 55% (trades >= 300)")
print(f"{'='*80}")
print(hdr)
print(sep)
for i, (_, r) in enumerate(f55.head(20).iterrows()):
    print(f"{i+1:<4} {r['rr']:>4.1f} {r['trades']:>7.0f} {r['wr']:>5.1f}% {r['pf']:>6.2f} "
          f"{r['exp_r']:>+7.2f} {r['total_pnl']:>+10,.0f} {r['max_dd']:>8,.0f} | "
          f"{r['min_conf']:>4.0f} {r['max_sl']:>5.0f} {r['min_patt']:>4.0f} "
          f"{r['max_pend']:>4.0f} {r['min_size']:>5.1f} {r['retrace']:>5.1f}")

# ----- MELHOR EXPECTANCIA COM WR >= 50% -----
f50 = rdf[(rdf['wr'] >= 50) & (rdf['trades'] >= 400)].sort_values('exp_r', ascending=False)
print(f"\n{'='*80}")
print(f"TOP 20 CONFIGS POR EXPECTANCIA (WR >= 50%, trades >= 400)")
print(f"{'='*80}")
print(hdr)
print(sep)
for i, (_, r) in enumerate(f50.head(20).iterrows()):
    print(f"{i+1:<4} {r['rr']:>4.1f} {r['trades']:>7.0f} {r['wr']:>5.1f}% {r['pf']:>6.2f} "
          f"{r['exp_r']:>+7.2f} {r['total_pnl']:>+10,.0f} {r['max_dd']:>8,.0f} | "
          f"{r['min_conf']:>4.0f} {r['max_sl']:>5.0f} {r['min_patt']:>4.0f} "
          f"{r['max_pend']:>4.0f} {r['min_size']:>5.1f} {r['retrace']:>5.1f}")

# ----- MELHOR P/L ABSOLUTO -----
fpl = rdf[(rdf['wr'] >= 48) & (rdf['trades'] >= 500)].sort_values('total_pnl', ascending=False)
print(f"\n{'='*80}")
print(f"TOP 10 CONFIGS POR P/L ABSOLUTO (WR >= 48%, trades >= 500)")
print(f"{'='*80}")
print(hdr)
print(sep)
for i, (_, r) in enumerate(fpl.head(10).iterrows()):
    print(f"{i+1:<4} {r['rr']:>4.1f} {r['trades']:>7.0f} {r['wr']:>5.1f}% {r['pf']:>6.2f} "
          f"{r['exp_r']:>+7.2f} {r['total_pnl']:>+10,.0f} {r['max_dd']:>8,.0f} | "
          f"{r['min_conf']:>4.0f} {r['max_sl']:>5.0f} {r['min_patt']:>4.0f} "
          f"{r['max_pend']:>4.0f} {r['min_size']:>5.1f} {r['retrace']:>5.1f}")

# Resumo
print(f"\n{'='*80}")
print("RESUMO GERAL")
print(f"{'='*80}")
total_combos = len(engine_grid) * len(filter_grid)
print(f"  Total configs testadas: {total_combos:,}")
print(f"  Configs com trades: {len(rdf)}")
print(f"  WR >= 55% e trades >= 300: {len(rdf[(rdf['wr'] >= 55) & (rdf['trades'] >= 300)])}")
print(f"  WR >= 60% e trades >= 200: {len(rdf[(rdf['wr'] >= 60) & (rdf['trades'] >= 200)])}")
print(f"  WR >= 60% e trades >= 300: {len(rdf[(rdf['wr'] >= 60) & (rdf['trades'] >= 300)])}")
print(f"  WR >= 65% (qualquer qtd): {len(rdf[rdf['wr'] >= 65])}")
print(f"  Melhor WR geral: {rdf['wr'].max():.1f}% ({rdf.loc[rdf['wr'].idxmax(), 'trades']:.0f} trades)")
print(f"  Melhor Exp geral: {rdf['exp_r'].max():.2f}R ({rdf.loc[rdf['exp_r'].idxmax(), 'trades']:.0f} trades)")
print(f"  Tempo total: {elapsed_total:.0f}s ({elapsed_total/60:.1f}min)")
