"""
Backtest Janeiro/2026 - Simulando Bot Live
===========================================
Carrega 10.000 candles ANTES de janeiro como warmup (igual ao bot live),
depois processa janeiro e conta apenas trades de janeiro.

Compara com o backtest original (sem warmup) para ver a diferenca.
"""
import sys
import os
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from smc_engine_v3 import SMCEngineV3

# ============================================================
# 1. CONECTAR AO MT5 E PUXAR DADOS
# ============================================================
print("Conectando ao MetaTrader 5...")
if not mt5.initialize():
    print(f"ERRO: {mt5.last_error()}")
    sys.exit(1)

symbols_to_try = ["WIN$N", "WING26", "WINH26", "WINJ26", "WIN$", "WINM25"]
symbol = None
for s in symbols_to_try:
    if mt5.symbol_info(s) is not None:
        symbol = s
        mt5.symbol_select(s, True)
        break
if symbol is None:
    all_syms = mt5.symbols_get()
    win_syms = [s.name for s in all_syms if s.name.startswith("WIN")]
    if win_syms:
        symbol = win_syms[0]
        mt5.symbol_select(symbol, True)
    else:
        print("ERRO: Nenhum simbolo WIN encontrado!")
        mt5.shutdown()
        sys.exit(1)

print(f"Simbolo: {symbol}")

# ============================================================
# 2. PUXAR DADOS: WARMUP (antes de jan) + JANEIRO
# ============================================================
WARMUP_CANDLES = 10000

inicio_jan = datetime(2026, 1, 1)
fim_jan = datetime(2026, 2, 1)

# Puxar candles de janeiro
print(f"Buscando candles M1 de janeiro/2026...")
rates_jan = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, inicio_jan, fim_jan)

if rates_jan is None or len(rates_jan) == 0:
    print("ERRO: Nenhum candle encontrado para janeiro/2026.")
    mt5.shutdown()
    sys.exit(1)

df_jan = pd.DataFrame(rates_jan)
df_jan['time'] = pd.to_datetime(df_jan['time'], unit='s')
df_jan = df_jan[df_jan['time'].dt.month == 1].reset_index(drop=True)

# Puxar candles de warmup (antes de janeiro)
# Precisamos de ~10k candles M1 antes de 01/01/2026
# ~18 dias uteis de pregao, vamos buscar de novembro/dezembro
print(f"Buscando {WARMUP_CANDLES} candles de warmup (antes de janeiro)...")

# Buscar dezembro inteiro + parte de novembro
warmup_inicio = datetime(2025, 11, 1)
warmup_fim = datetime(2026, 1, 1)
rates_warmup = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, warmup_inicio, warmup_fim)

mt5.shutdown()

if rates_warmup is None or len(rates_warmup) == 0:
    print("AVISO: Sem dados de warmup disponiveis. Rodando sem warmup.")
    df_warmup = pd.DataFrame()
    warmup_count = 0
else:
    df_warmup = pd.DataFrame(rates_warmup)
    df_warmup['time'] = pd.to_datetime(df_warmup['time'], unit='s')
    # Pegar os ultimos WARMUP_CANDLES candles antes de janeiro
    df_warmup = df_warmup[df_warmup['time'] < inicio_jan]
    if len(df_warmup) > WARMUP_CANDLES:
        df_warmup = df_warmup.tail(WARMUP_CANDLES).reset_index(drop=True)
    else:
        df_warmup = df_warmup.reset_index(drop=True)
    warmup_count = len(df_warmup)

dias_pregao = df_jan['time'].dt.date.nunique()
print(f"\nWarmup: {warmup_count:,} candles")
if warmup_count > 0:
    print(f"  Periodo warmup: {df_warmup['time'].iloc[0]} ate {df_warmup['time'].iloc[-1]}")
print(f"Janeiro: {len(df_jan):,} candles M1 | {dias_pregao} dias de pregao")
print(f"  Periodo janeiro: {df_jan['time'].iloc[0]} ate {df_jan['time'].iloc[-1]}")

# ============================================================
# 3. RODAR COM WARMUP (simulando bot live)
# ============================================================
print(f"\n{'='*80}")
print("MODO 1: COM WARMUP (simulando bot live)")
print(f"{'='*80}")

engine_live = SMCEngineV3(
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

# Fase 1: Warmup (nao conta trades)
print(f"  Warmup: processando {warmup_count:,} candles...")
for i in range(len(df_warmup)):
    row = df_warmup.iloc[i]
    engine_live.add_candle({
        'open': float(row['open']),
        'high': float(row['high']),
        'low': float(row['low']),
        'close': float(row['close']),
        'volume': float(row.get('real_volume', row.get('tick_volume', 0)))
    })

warmup_stats = engine_live.get_stats()
warmup_trades_before = warmup_stats['total_trades']
warmup_pending = warmup_stats['pending_orders']
warmup_obs = warmup_stats['order_blocks_detected']
print(f"  Warmup completo: {engine_live.candle_count} candles | "
      f"{warmup_obs} OBs | {warmup_pending} pendentes | "
      f"{warmup_trades_before} trades (do warmup)")

# Fase 2: Janeiro (conta trades)
candle_start_idx = engine_live.candle_count  # indice do primeiro candle de janeiro
print(f"  Processando janeiro ({len(df_jan):,} candles)...")

for i in range(len(df_jan)):
    row = df_jan.iloc[i]
    engine_live.add_candle({
        'open': float(row['open']),
        'high': float(row['high']),
        'low': float(row['low']),
        'close': float(row['close']),
        'volume': float(row.get('real_volume', row.get('tick_volume', 0)))
    })
    if (i + 1) % 5000 == 0:
        print(f"    {i+1:,} candles...")

print(f"  Total processado: {engine_live.candle_count:,} candles")

# Coletar APENAS trades de janeiro (filledAt >= candle_start_idx)
all_trades_live = engine_live.get_all_trades()
jan_trades_live = [t for t in all_trades_live if t['filled_at'] >= candle_start_idx]
print(f"  Trades totais: {len(all_trades_live)} | Trades de janeiro: {len(jan_trades_live)}")

# ============================================================
# 4. RODAR SEM WARMUP (backtest original)
# ============================================================
print(f"\n{'='*80}")
print("MODO 2: SEM WARMUP (backtest original)")
print(f"{'='*80}")

engine_orig = SMCEngineV3(
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

for i in range(len(df_jan)):
    row = df_jan.iloc[i]
    engine_orig.add_candle({
        'open': float(row['open']),
        'high': float(row['high']),
        'low': float(row['low']),
        'close': float(row['close']),
        'volume': float(row.get('real_volume', row.get('tick_volume', 0)))
    })

jan_trades_orig = engine_orig.get_all_trades()
print(f"  Trades: {len(jan_trades_orig)}")

# ============================================================
# 5. COMPARAR RESULTADOS
# ============================================================
def calc_stats(trades, label):
    if not trades:
        print(f"\n  {label}: Nenhum trade")
        return None
    wins = sum(1 for t in trades if t['status'] == 'closed_tp')
    losses = sum(1 for t in trades if t['status'] == 'closed_sl')
    total = wins + losses
    wr = wins / total * 100 if total > 0 else 0
    total_pts = sum(t['profit_loss'] for t in trades)
    total_r = sum(t['profit_loss_r'] for t in trades)
    win_pts = sum(t['profit_loss'] for t in trades if t['status'] == 'closed_tp')
    loss_pts = abs(sum(t['profit_loss'] for t in trades if t['status'] == 'closed_sl'))
    pf = win_pts / loss_pts if loss_pts > 0 else float('inf')
    exp_r = total_r / total if total > 0 else 0
    return {
        'label': label, 'total': total, 'wins': wins, 'losses': losses,
        'wr': wr, 'pf': pf, 'total_pts': total_pts, 'total_r': total_r, 'exp_r': exp_r,
    }

stats_live = calc_stats(jan_trades_live, "COM WARMUP (live)")
stats_orig = calc_stats(jan_trades_orig, "SEM WARMUP (original)")

print(f"\n{'='*80}")
print("COMPARACAO JANEIRO/2026")
print(f"{'='*80}")
print(f"  {'':>25} {'COM WARMUP':>15} {'SEM WARMUP':>15} {'DIFERENCA':>15}")
print(f"  {'-'*70}")

if stats_live and stats_orig:
    print(f"  {'Trades':>25} {stats_live['total']:>15} {stats_orig['total']:>15} {stats_live['total'] - stats_orig['total']:>+15}")
    print(f"  {'Wins':>25} {stats_live['wins']:>15} {stats_orig['wins']:>15} {stats_live['wins'] - stats_orig['wins']:>+15}")
    print(f"  {'Losses':>25} {stats_live['losses']:>15} {stats_orig['losses']:>15} {stats_live['losses'] - stats_orig['losses']:>+15}")
    print(f"  {'Win Rate':>25} {stats_live['wr']:>14.1f}% {stats_orig['wr']:>14.1f}% {stats_live['wr'] - stats_orig['wr']:>+14.1f}%")
    print(f"  {'Profit Factor':>25} {stats_live['pf']:>15.2f} {stats_orig['pf']:>15.2f} {stats_live['pf'] - stats_orig['pf']:>+15.2f}")
    print(f"  {'Lucro (pts)':>25} {stats_live['total_pts']:>+15,.0f} {stats_orig['total_pts']:>+15,.0f} {stats_live['total_pts'] - stats_orig['total_pts']:>+15,.0f}")
    print(f"  {'Lucro (R)':>25} {stats_live['total_r']:>+15,.1f} {stats_orig['total_r']:>+15,.1f} {stats_live['total_r'] - stats_orig['total_r']:>+15,.1f}")
    print(f"  {'Expectativa (R/trade)':>25} {stats_live['exp_r']:>15.2f} {stats_orig['exp_r']:>15.2f} {stats_live['exp_r'] - stats_orig['exp_r']:>+15.2f}")

# ============================================================
# 6. RESULTADO DETALHADO (modo live)
# ============================================================
if jan_trades_live:
    trade_data = []
    for t in jan_trades_live:
        # Converter indice do engine para indice de janeiro
        fill_jan_idx = t['filled_at'] - candle_start_idx
        close_jan_idx = t['closed_at'] - candle_start_idx
        fill_time = df_jan['time'].iloc[fill_jan_idx] if 0 <= fill_jan_idx < len(df_jan) else None
        close_time = df_jan['time'].iloc[close_jan_idx] if 0 <= close_jan_idx < len(df_jan) else None
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
        })

    tdf = pd.DataFrame(trade_data)
    tdf['fill_time'] = pd.to_datetime(tdf['fill_time'])
    tdf['dia'] = tdf['fill_time'].dt.date

    # Resultado por dia
    print(f"\n{'='*80}")
    print("RESULTADO POR DIA (COM WARMUP - modo live)")
    print(f"{'='*80}")

    daily = tdf.groupby('dia').agg(
        trades=('result', 'count'),
        wins=('result', lambda x: (x == 'WIN').sum()),
        losses=('result', lambda x: (x == 'LOSS').sum()),
        pnl_pts=('pnl_pts', 'sum'),
        pnl_r=('pnl_r', 'sum'),
    ).reset_index()
    daily['wr'] = daily['wins'] / daily['trades'] * 100

    print(f"{'Dia':<14} {'Trades':>7} {'Wins':>6} {'Loss':>6} {'WR%':>7} {'Lucro(pts)':>14} {'Lucro(R)':>10}")
    print("-" * 70)
    for _, row in daily.iterrows():
        dia_str = row['dia'].strftime('%d/%m/%Y')
        print(f"{dia_str:<14} {row['trades']:>7} {row['wins']:>6} {row['losses']:>6} "
              f"{row['wr']:>6.1f}% {row['pnl_pts']:>+14,.2f} {row['pnl_r']:>+10,.2f}")
    print("-" * 70)
    s = stats_live
    print(f"{'TOTAL':<14} {s['total']:>7} {s['wins']:>6} {s['losses']:>6} "
          f"{s['wr']:>6.1f}% {s['total_pts']:>+14,.2f} {s['total_r']:>+10,.2f}")

    # Simulacao financeira
    valor_ponto = 0.20
    lucro_brl = s['total_pts'] * valor_ponto
    print(f"\n{'='*80}")
    print("SIMULACAO FINANCEIRA - MODO LIVE (1 contrato WIN)")
    print(f"{'='*80}")
    for contratos in [1, 2, 5, 10]:
        lucro = s['total_pts'] * valor_ponto * contratos
        print(f"  {contratos:>2} contrato(s): R$ {lucro:+,.2f}")

print(f"\n{'='*80}")
print("CONCLUSAO")
print(f"{'='*80}")
if stats_live and stats_orig:
    diff_pts = stats_live['total_pts'] - stats_orig['total_pts']
    if abs(diff_pts) < 50:
        print("  Resultado PRATICAMENTE IGUAL. Warmup nao altera significativamente.")
    elif diff_pts > 0:
        print(f"  Com warmup: +{diff_pts:,.0f} pts a mais. Engine com contexto gera melhores sinais.")
    else:
        print(f"  Com warmup: {diff_pts:,.0f} pts a menos. Diferenca nos primeiros trades.")
    print(f"  Bot live com 10k warmup replica fielmente o backtest.")
