"""
Otimizacao de parametros SMC Engine V3 para ~60% WR
===================================================
Estrategia de 2 fases:
  Fase 1: Roda engine com combinacoes de (max_pend, min_size, retrace) = 27 runs
  Fase 2: Pos-filtra trades por (min_conf, max_sl, min_patt) = 72 combos
Total: 27 engine runs x 72 filtros = 1944 resultados em ~4 minutos
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

# Pre-processar dados como lista de dicts para performance
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


# ============================================================
# 2. FUNCOES AUXILIARES
# ============================================================
def calc_stats(trades):
    """Calcula estatisticas de uma lista de trades."""
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

    # Drawdown maximo
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
        'trades': total,
        'wins': wins,
        'losses': losses,
        'wr': wr,
        'pf': pf,
        'total_pnl': total_pnl,
        'total_r': total_r,
        'exp_r': exp_r,
        'max_dd': max_dd,
    }


# ============================================================
# 3. FASE 1: RODAR ENGINE COM PARAMETROS ESTRUTURAIS
# ============================================================
print("\n" + "=" * 80)
print("FASE 1: RODAR ENGINE COM PARAMETROS ESTRUTURAIS")
print("=" * 80)

# Parametros que MUDAM a geracao de sinais (precisam rodar engine)
engine_params = {
    'max_pend': [50, 80, 150],
    'min_size': [0.0, 0.3, 0.5],
    'retrace': [0.5, 0.6, 0.7],
}

engine_combos = list(product(
    engine_params['max_pend'],
    engine_params['min_size'],
    engine_params['retrace'],
))
print(f"Engine runs necessarios: {len(engine_combos)}")

# Parametros que so FILTRAM trades (pos-filtro rapido)
filter_params = {
    'min_conf': [0, 30, 35, 40, 45, 50],
    'max_sl': [0, 50, 75, 100],
    'min_patt': [0, 1, 2],
}

filter_combos = list(product(
    filter_params['min_conf'],
    filter_params['max_sl'],
    filter_params['min_patt'],
))
print(f"Filtros pos-engine: {len(filter_combos)}")
print(f"Total de resultados: {len(engine_combos) * len(filter_combos):,}")

# Armazenar trades de cada engine run
engine_results = {}  # key = (max_pend, min_size, retrace) -> list of trades
start_time = time.time()

for i, (max_pend, min_size, retrace) in enumerate(engine_combos):
    t0 = time.time()
    engine = SMCEngineV3(
        symbol='WIN', swing_length=5, risk_reward_ratio=3.0,
        min_volume_ratio=0.0, min_ob_size_atr=min_size,
        use_not_mitigated_filter=True, max_pending_candles=max_pend,
        entry_delay_candles=1, tick_size=5.0,
        min_confidence=0,       # sem filtro - vamos pos-filtrar
        max_sl_points=0,        # sem filtro - vamos pos-filtrar
        min_patterns=0,         # sem filtro - vamos pos-filtrar
        entry_retracement=retrace,
    )

    for c in candle_data:
        engine.add_candle(c)

    trades = engine.get_all_trades()
    key = (max_pend, min_size, retrace)
    engine_results[key] = trades if trades else []

    elapsed_run = time.time() - t0
    n_trades = len(engine_results[key])
    print(f"  [{i+1}/{len(engine_combos)}] pend={max_pend} size={min_size} retrace={retrace} "
          f"-> {n_trades} trades ({elapsed_run:.1f}s)")

elapsed_phase1 = time.time() - start_time
print(f"\nFase 1 completa: {len(engine_combos)} engine runs em {elapsed_phase1:.0f}s")


# ============================================================
# 4. FASE 2: POS-FILTRAR TRADES
# ============================================================
print(f"\n{'='*80}")
print("FASE 2: POS-FILTRAR TRADES")
print(f"{'='*80}")

results = []

for key, trades in engine_results.items():
    max_pend, min_size, retrace = key

    if not trades:
        continue

    for min_conf, max_sl, min_patt in filter_combos:
        # Filtrar trades
        filtered_trades = trades
        if min_conf > 0:
            filtered_trades = [t for t in filtered_trades if t.get('confidence', 0) >= min_conf]
        if max_sl > 0:
            filtered_trades = [t for t in filtered_trades
                               if abs(t['entry_price'] - t['stop_loss']) <= max_sl]
        if min_patt > 0:
            filtered_trades = [t for t in filtered_trades
                               if len(t.get('patterns', [])) - 1 >= min_patt]

        stats = calc_stats(filtered_trades)
        if stats is not None:
            stats.update({
                'min_conf': min_conf,
                'max_sl': max_sl,
                'min_patt': min_patt,
                'max_pend': max_pend,
                'min_size': min_size,
                'retrace': retrace,
            })
            results.append(stats)

elapsed_total = time.time() - start_time
print(f"Fase 2 completa: {len(results)} resultados validos")


# ============================================================
# 5. RANKING E RESULTADOS
# ============================================================
rdf = pd.DataFrame(results)

# Baseline (sem filtros)
baseline = rdf[(rdf['min_conf'] == 0) & (rdf['max_sl'] == 0) &
               (rdf['min_patt'] == 0) & (rdf['max_pend'] == 150) &
               (rdf['min_size'] == 0.0) & (rdf['retrace'] == 0.5)]

print(f"\n{'='*80}")
print("BASELINE (sem filtros)")
print(f"{'='*80}")
if len(baseline) > 0:
    b = baseline.iloc[0]
    print(f"  Trades: {b['trades']:.0f} | WR: {b['wr']:.1f}% | PF: {b['pf']:.2f} | "
          f"P/L: {b['total_pnl']:+,.0f} pts | Exp: {b['exp_r']:.2f}R | MaxDD: {b['max_dd']:,.0f}")

# Filtrar: WR >= 55% e trades >= 300
filtered = rdf[(rdf['wr'] >= 55) & (rdf['trades'] >= 300)].copy()
filtered = filtered.sort_values('exp_r', ascending=False)

print(f"\n{'='*80}")
print(f"TOP 20 CONFIGS (WR >= 55%, trades >= 300, ordenado por expectancia)")
print(f"{'='*80}")
print(f"{'#':<4} {'Trades':>7} {'WR%':>6} {'PF':>6} {'Exp(R)':>7} {'P/L pts':>10} {'MaxDD':>8} | "
      f"{'Conf':>4} {'MaxSL':>5} {'Patt':>4} {'Pend':>4} {'Size':>5} {'Retr':>5}")
print("-" * 100)

for i, (_, row) in enumerate(filtered.head(20).iterrows()):
    print(f"{i+1:<4} {row['trades']:>7.0f} {row['wr']:>5.1f}% {row['pf']:>6.2f} "
          f"{row['exp_r']:>+7.2f} {row['total_pnl']:>+10,.0f} {row['max_dd']:>8,.0f} | "
          f"{row['min_conf']:>4.0f} {row['max_sl']:>5.0f} {row['min_patt']:>4.0f} "
          f"{row['max_pend']:>4.0f} {row['min_size']:>5.1f} {row['retrace']:>5.1f}")

# Segundo ranking: top por profit factor (mais conservador)
filtered_pf = rdf[(rdf['wr'] >= 52) & (rdf['trades'] >= 400)].copy()
filtered_pf = filtered_pf.sort_values('pf', ascending=False)

print(f"\n{'='*80}")
print(f"TOP 10 CONFIGS POR PROFIT FACTOR (WR >= 52%, trades >= 400)")
print(f"{'='*80}")
print(f"{'#':<4} {'Trades':>7} {'WR%':>6} {'PF':>6} {'Exp(R)':>7} {'P/L pts':>10} {'MaxDD':>8} | "
      f"{'Conf':>4} {'MaxSL':>5} {'Patt':>4} {'Pend':>4} {'Size':>5} {'Retr':>5}")
print("-" * 100)

for i, (_, row) in enumerate(filtered_pf.head(10).iterrows()):
    print(f"{i+1:<4} {row['trades']:>7.0f} {row['wr']:>5.1f}% {row['pf']:>6.2f} "
          f"{row['exp_r']:>+7.2f} {row['total_pnl']:>+10,.0f} {row['max_dd']:>8,.0f} | "
          f"{row['min_conf']:>4.0f} {row['max_sl']:>5.0f} {row['min_patt']:>4.0f} "
          f"{row['max_pend']:>4.0f} {row['min_size']:>5.1f} {row['retrace']:>5.1f}")

# Terceiro ranking: melhor P/L absoluto com WR decente
filtered_pl = rdf[(rdf['wr'] >= 50) & (rdf['trades'] >= 500)].copy()
filtered_pl = filtered_pl.sort_values('total_pnl', ascending=False)

print(f"\n{'='*80}")
print(f"TOP 10 CONFIGS POR P/L TOTAL (WR >= 50%, trades >= 500)")
print(f"{'='*80}")
print(f"{'#':<4} {'Trades':>7} {'WR%':>6} {'PF':>6} {'Exp(R)':>7} {'P/L pts':>10} {'MaxDD':>8} | "
      f"{'Conf':>4} {'MaxSL':>5} {'Patt':>4} {'Pend':>4} {'Size':>5} {'Retr':>5}")
print("-" * 100)

for i, (_, row) in enumerate(filtered_pl.head(10).iterrows()):
    print(f"{i+1:<4} {row['trades']:>7.0f} {row['wr']:>5.1f}% {row['pf']:>6.2f} "
          f"{row['exp_r']:>+7.2f} {row['total_pnl']:>+10,.0f} {row['max_dd']:>8,.0f} | "
          f"{row['min_conf']:>4.0f} {row['max_sl']:>5.0f} {row['min_patt']:>4.0f} "
          f"{row['max_pend']:>4.0f} {row['min_size']:>5.1f} {row['retrace']:>5.1f}")

# Resumo geral
total_combos = len(engine_combos) * len(filter_combos)
print(f"\n{'='*80}")
print("RESUMO GERAL")
print(f"{'='*80}")
print(f"  Total configs testadas: {total_combos:,}")
print(f"  Configs com trades: {len(rdf)}")
print(f"  Configs com WR >= 55% e trades >= 300: {len(rdf[(rdf['wr'] >= 55) & (rdf['trades'] >= 300)])}")
print(f"  Configs com WR >= 60% e trades >= 300: {len(rdf[(rdf['wr'] >= 60) & (rdf['trades'] >= 300)])}")
print(f"  Configs com WR >= 60% (qualquer qtd): {len(rdf[rdf['wr'] >= 60])}")
print(f"  Tempo total: {elapsed_total:.0f}s ({elapsed_total/60:.1f}min)")
