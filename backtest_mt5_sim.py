"""
Backtest com Simulador MT5 Realista (Bar a Bar)
================================================
Simula o comportamento real do MT5:
- Fill on touch (sem tolerancia de 1 tick)
- Quando engine cancela ordem ja preenchida pelo MT5 -> posicao e fechada a mercado
- SL/TP on touch (igual a engine)
- Ordens rejeitadas por margem nao sao simuladas (simplificacao)

Isso replica fielmente o que acontece na live com smc_trader_live.py
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
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from smc_engine_v3 import SMCEngineV3

# ============================================================
# SIMULADOR MT5
# ============================================================

@dataclass
class MT5Order:
    """Ordem pendente no simulador MT5"""
    order_id: str
    direction: str  # 'BULLISH' ou 'BEARISH'
    entry_price: float
    stop_loss: float
    take_profit: float
    created_at: int  # indice do candle

@dataclass
class MT5Position:
    """Posicao aberta no simulador MT5"""
    order_id: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    filled_at: int  # indice do candle de fill

@dataclass
class MT5Trade:
    """Trade fechado no simulador MT5"""
    order_id: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    exit_price: float
    filled_at: int
    closed_at: int
    result: str      # 'WIN', 'LOSS', 'FORCE_CLOSE'
    pnl_pts: float
    close_reason: str  # 'tp', 'sl', 'force_close_cancel', 'force_close_mitigated'


class MT5Simulator:
    """
    Simula o comportamento REAL do MT5 para ordens limit:
    - Fill on touch (preco encosta no nivel = preenchido)
    - SL/TP verificado INCLUSIVE no candle de fill (MT5 real bate SL em 2-3 seg)
    - Engine cancela -> posicao JA tem SL/TP, deixa proteger (nao force close)
    - SL verificado primeiro (pior caso), TP depois

    Fluxo real observado na live:
    1. MT5 preenche ordem on touch -> posicao aberta com SL/TP
    2. Se OB sendo mitigado, preco continua -> SL bate em 2-3 segundos
    3. Engine processa candle -> cancela ordem -> bot detecta 'filled' ou 'not_found'
    4. Posicao ja foi fechada pelo SL antes do bot tentar force close
    """

    def __init__(self, tick_size: float = 5.0):
        self.tick_size = tick_size
        self.pending_orders: Dict[str, MT5Order] = {}
        self.positions: Dict[str, MT5Position] = {}
        self.trades: List[MT5Trade] = []
        self.engine_also_filled: set = set()  # IDs que engine tambem preencheu

    def add_order(self, signal: dict):
        """Engine criou uma ordem pendente -> adicionar ao MT5 sim"""
        oid = signal['order_id']
        self.pending_orders[oid] = MT5Order(
            order_id=oid,
            direction=signal['direction'],
            entry_price=signal['entry_price'],
            stop_loss=signal['stop_loss'],
            take_profit=signal['take_profit'],
            created_at=signal.get('created_at', 0),
        )

    def remove_order(self, order_id: str):
        """
        Engine cancelou/expirou uma ordem -> remover se ainda pendente.
        Se ja foi preenchida pelo MT5, NAO force close - SL/TP protege.
        """
        if order_id in self.pending_orders:
            del self.pending_orders[order_id]
            return 'cancelled'
        elif order_id in self.positions:
            # MT5 ja preencheu, mas SL/TP vai proteger - nao fazemos nada
            return 'filled_but_protected'
        return 'not_found'  # ja fechou por SL/TP

    def process_candle(self, idx: int, h: float, l: float, c: float) -> dict:
        """
        Processa um candle: verificar fills e TP/SL.

        IMPORTANTE: SL/TP e verificado INCLUSIVE no candle de fill!
        No MT5 real, SL bate em 2-3 segundos apos o fill.
        Como nao temos dados de tick, verificamos no mesmo candle.
        """
        events = {
            'mt5_fills': [],
            'mt5_closes': [],
        }

        # 1. Verificar fills de ordens pendentes (on touch, sem tolerancia)
        filled_ids = []
        for oid, order in self.pending_orders.items():
            touched = False
            if order.direction == 'BULLISH':
                # Buy limit: preco cai ate entry (low <= entry)
                touched = l <= order.entry_price
            else:
                # Sell limit: preco sobe ate entry (high >= entry)
                touched = h >= order.entry_price

            if touched:
                # MT5 preencheu!
                self.positions[oid] = MT5Position(
                    order_id=oid,
                    direction=order.direction,
                    entry_price=order.entry_price,
                    stop_loss=order.stop_loss,
                    take_profit=order.take_profit,
                    filled_at=idx,
                )
                filled_ids.append(oid)
                events['mt5_fills'].append(oid)

        for oid in filled_ids:
            del self.pending_orders[oid]

        # 2. Verificar TP/SL de TODAS as posicoes abertas (incluindo fills deste candle!)
        # No MT5 real, SL/TP e ativado instantaneamente apos fill.
        # Se o candle que preenche tambem atinge SL -> SL bate em 2-3 seg.
        closed_ids = []
        for oid, pos in self.positions.items():
            hit_tp = False
            hit_sl = False

            if pos.direction == 'BULLISH':
                if l <= pos.stop_loss:
                    hit_sl = True
                elif h >= pos.take_profit:
                    hit_tp = True
            else:  # BEARISH
                if h >= pos.stop_loss:
                    hit_sl = True
                elif l <= pos.take_profit:
                    hit_tp = True

            if hit_tp or hit_sl:
                exit_price = pos.take_profit if hit_tp else pos.stop_loss
                if pos.direction == 'BULLISH':
                    pnl = exit_price - pos.entry_price
                else:
                    pnl = pos.entry_price - exit_price

                result = 'WIN' if hit_tp else 'LOSS'
                reason = 'tp' if hit_tp else 'sl'
                if idx == pos.filled_at:
                    reason += '_same_candle'  # SL/TP bateu no mesmo candle do fill

                trade = MT5Trade(
                    order_id=oid,
                    direction=pos.direction,
                    entry_price=pos.entry_price,
                    stop_loss=pos.stop_loss,
                    take_profit=pos.take_profit,
                    exit_price=exit_price,
                    filled_at=pos.filled_at,
                    closed_at=idx,
                    result=result,
                    pnl_pts=pnl,
                    close_reason=reason,
                )
                self.trades.append(trade)
                closed_ids.append(oid)
                events['mt5_closes'].append({
                    'order_id': oid,
                    'result': result,
                    'pnl': pnl,
                })

        for oid in closed_ids:
            del self.positions[oid]

        return events


# ============================================================
# 1. CONECTAR AO MT5 E PUXAR DADOS
# ============================================================
print("=" * 80)
print("BACKTEST COM SIMULADOR MT5 REALISTA (BAR A BAR)")
print("=" * 80)
print()
print("Conectando ao MetaTrader 5...")
if not mt5.initialize():
    print(f"ERRO: {mt5.last_error()}")
    sys.exit(1)

symbols_to_try = ["WIN$N", "WINJ26", "WINH26", "WING26", "WIN$"]
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
# CONFIGURACAO DO PERIODO
# ============================================================
# Argumentos: python backtest_mt5_sim.py [ano] [mes_inicio] [mes_fim]
# Padrao: 2026 completo

import argparse
parser = argparse.ArgumentParser()
parser.add_argument('--start', type=str, default='2026-01-01', help='Data inicio (YYYY-MM-DD)')
parser.add_argument('--end', type=str, default='2026-12-31', help='Data fim (YYYY-MM-DD)')
parser.add_argument('--week', type=str, default=None, help='Semana especifica (YYYY-MM-DD da segunda)')
args = parser.parse_args()

if args.week:
    week_start = datetime.strptime(args.week, '%Y-%m-%d')
    inicio = datetime(2026, 1, 1)  # warmup desde jan
    fim = week_start + timedelta(days=6)
    filter_start = week_start
    filter_end = fim
    label = f"Semana de {week_start.date()}"
else:
    inicio = datetime.strptime(args.start, '%Y-%m-%d')
    fim_str = args.end
    fim = datetime.strptime(fim_str, '%Y-%m-%d') + timedelta(days=1)
    # Para warmup, sempre comecar de janeiro se inicio for em 2026
    warmup_start = datetime(inicio.year, 1, 1) if inicio.month > 1 else inicio
    filter_start = inicio
    filter_end = fim
    inicio = warmup_start
    label = f"{filter_start.date()} a {filter_end.date()}"

print(f"Buscando candles M1 de {inicio.date()} ate {fim.date()}...")
rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, inicio, fim)
mt5.shutdown()

if rates is None or len(rates) == 0:
    print("ERRO: Nenhum dado encontrado.")
    sys.exit(1)

df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')
df = df.drop_duplicates(subset='time').sort_values('time').reset_index(drop=True)

print(f"Total: {len(df):,} candles M1")
print(f"Periodo dados: {df['time'].iloc[0]} ate {df['time'].iloc[-1]}")

# ============================================================
# 2. RODAR ENGINE + SIMULADOR MT5 BAR A BAR
# ============================================================
print(f"\nRodando engine + simulador MT5 bar a bar...")
print(f"  Engine: fill = entry +/- 1 tick (5 pts)")
print(f"  MT5 Sim: fill = on touch (sem tolerancia)")
print()

engine = SMCEngineV3(
    symbol=symbol,
    swing_length=5,
    risk_reward_ratio=2.0,
    min_volume_ratio=0.0,
    min_ob_size_atr=0.3,
    use_not_mitigated_filter=True,
    max_pending_candles=150,
    entry_delay_candles=1,
    tick_size=5.0,
    min_confidence=0.0,
    max_sl_points=50.0,
    min_patterns=0,
    entry_retracement=0.7,
)

mt5_sim = MT5Simulator(tick_size=5.0)

# Contadores
stats = {
    'sinais': 0,
    'engine_fills': 0,
    'engine_cancels': 0,
    'engine_expires': 0,
    'engine_trades': 0,
    'mt5_fills': 0,
    'mt5_extra_fills': 0,  # fills que engine NAO fez
    'mt5_extra_fills_from_cancel': 0,  # engine cancelou mas MT5 preencheu
    'mt5_trades': 0,
    'divergences': [],
}

for i in range(len(df)):
    row = df.iloc[i]
    h = float(row['high'])
    l = float(row['low'])
    c = float(row['close'])

    # 1. Engine processa o candle
    events = engine.add_candle({
        'open': float(row['open']),
        'high': h,
        'low': l,
        'close': c,
        'volume': float(row.get('real_volume', row.get('tick_volume', 0)))
    })

    # 2. Novos sinais -> adicionar ao MT5 sim
    for sig in events['new_signals']:
        sig['created_at'] = i
        mt5_sim.add_order(sig)
        stats['sinais'] += 1

    # 3. MT5 sim processa o candle (fills on touch + TP/SL)
    mt5_events = mt5_sim.process_candle(i, h, l, c)

    # 4. Engine preencheu ordens
    for fill in events['filled_orders']:
        stats['engine_fills'] += 1
        mt5_sim.engine_also_filled.add(fill['order_id'])

    # 5. Engine fechou trades
    for trade in events['closed_trades']:
        stats['engine_trades'] += 1

    # 6. Engine cancelou ordens -> verificar se MT5 ja preencheu
    for cancel in events['cancelled_orders']:
        oid = cancel['order_id']
        reason = cancel.get('reason', 'unknown')
        stats['engine_cancels'] += 1

        status = mt5_sim.remove_order(oid)
        if status == 'filled_but_protected':
            # MT5 ja preencheu, mas SL/TP protege a posicao
            # NAO force close - deixar SL/TP resolver naturalmente
            # (no MT5 real, SL bate em 2-3 seg quando OB e mitigado)
            stats['mt5_extra_fills_from_cancel'] += 1
            candle_time = df['time'].iloc[i]
            stats['divergences'].append({
                'time': candle_time,
                'order_id': oid,
                'reason': reason,
                'type': 'engine_cancel_mt5_filled',
            })

    # 7. Engine expirou ordens -> remover do MT5 sim
    for exp in events['expired_orders']:
        oid = exp['order_id']
        stats['engine_expires'] += 1
        mt5_sim.remove_order(oid)

    # Progresso
    if (i + 1) % 10000 == 0:
        print(f"  {i+1:,} candles... (MT5: {len(mt5_sim.trades)} trades)")

print(f"  {len(df):,} candles processados")

# ============================================================
# 3. COLETAR RESULTADOS
# ============================================================

# Engine trades (para comparacao)
engine_trades = engine.get_all_trades() or []
engine_closed = [t for t in engine_trades if t['status'] in ('closed_tp', 'closed_sl')]

# MT5 sim trades
mt5_trades = mt5_sim.trades

# Filtrar por periodo se necessario
if args.week or args.start != '2026-01-01':
    filter_start_ts = pd.Timestamp(filter_start)
    filter_end_ts = pd.Timestamp(filter_end)

    # Filtrar engine trades
    engine_filtered = []
    for t in engine_closed:
        fill_idx = t['filled_at']
        if fill_idx < len(df):
            fill_time = df['time'].iloc[fill_idx]
            if filter_start_ts <= fill_time <= filter_end_ts:
                engine_filtered.append(t)
    engine_closed = engine_filtered

    # Filtrar MT5 trades
    mt5_filtered = []
    for t in mt5_trades:
        if t.filled_at < len(df):
            fill_time = df['time'].iloc[t.filled_at]
            if filter_start_ts <= fill_time <= filter_end_ts:
                mt5_filtered.append(t)
    mt5_trades = mt5_filtered

# Contar MT5 fills extras
mt5_fill_ids = set(t.order_id for t in mt5_sim.trades)
engine_fill_ids = mt5_sim.engine_also_filled
stats['mt5_extra_fills'] = len(mt5_fill_ids - engine_fill_ids)
stats['mt5_fills'] = len(mt5_fill_ids)
stats['mt5_trades'] = len(mt5_trades)

# ============================================================
# 4. RESULTADOS
# ============================================================

# --- Engine stats ---
e_wins = sum(1 for t in engine_closed if t['status'] == 'closed_tp')
e_losses = sum(1 for t in engine_closed if t['status'] == 'closed_sl')
e_total = e_wins + e_losses
e_wr = e_wins / e_total * 100 if e_total > 0 else 0
e_pnl = sum(t['profit_loss'] for t in engine_closed)
e_win_pts = sum(t['profit_loss'] for t in engine_closed if t['status'] == 'closed_tp')
e_loss_pts = abs(sum(t['profit_loss'] for t in engine_closed if t['status'] == 'closed_sl'))
e_pf = e_win_pts / e_loss_pts if e_loss_pts > 0 else float('inf')

# --- MT5 sim stats ---
m_wins = sum(1 for t in mt5_trades if t.result == 'WIN')
m_losses = sum(1 for t in mt5_trades if t.result == 'LOSS')
m_total = m_wins + m_losses
m_wr = m_wins / m_total * 100 if m_total > 0 else 0
m_pnl = sum(t.pnl_pts for t in mt5_trades)
m_win_pts = sum(t.pnl_pts for t in mt5_trades if t.pnl_pts > 0)
m_loss_pts = abs(sum(t.pnl_pts for t in mt5_trades if t.pnl_pts <= 0))
m_pf = m_win_pts / m_loss_pts if m_loss_pts > 0 else float('inf')

# Trades extras (MT5 preencheu mas engine nao)
extra_trades = [t for t in mt5_trades if t.order_id not in engine_fill_ids]
extra_pnl = sum(t.pnl_pts for t in extra_trades)

# Trades same-candle SL (fill + SL no mesmo candle)
same_candle_trades = [t for t in mt5_trades if 'same_candle' in t.close_reason]
same_candle_pnl = sum(t.pnl_pts for t in same_candle_trades)

print(f"\n{'='*80}")
print(f"RESULTADO: ENGINE vs SIMULADOR MT5 ({label})")
print(f"{'='*80}")
print(f"  Config: RR=2.0 | retrace=0.7 | max_sl=50 | min_size=0.3*ATR")
print()

print(f"  {'Metrica':<30} {'Engine':>15} {'MT5 Sim':>15} {'Delta':>12}")
print(f"  {'-'*72}")
print(f"  {'Trades':<30} {e_total:>15} {m_total:>15} {m_total-e_total:>+12}")
print(f"  {'Wins':<30} {e_wins:>15} {m_wins:>15} {m_wins-e_wins:>+12}")
print(f"  {'Losses':<30} {e_losses:>15} {m_losses:>15} {m_losses-e_losses:>+12}")
print(f"  {'Win Rate':<30} {e_wr:>14.1f}% {m_wr:>14.1f}% {m_wr-e_wr:>+11.1f}%")
print(f"  {'Profit Factor':<30} {e_pf:>15.2f} {m_pf:>15.2f} {m_pf-e_pf:>+12.2f}")
print(f"  {'P/L (pts)':<30} {e_pnl:>+15,.0f} {m_pnl:>+15,.0f} {m_pnl-e_pnl:>+12,.0f}")
if e_total > 0 and m_total > 0:
    e_exp = e_pnl / e_total
    m_exp = m_pnl / m_total
    print(f"  {'Expectancia (pts/trade)':<30} {e_exp:>+15.1f} {m_exp:>+15.1f} {m_exp-e_exp:>+12.1f}")

print(f"\n  --- Divergencias MT5 ---")
print(f"  Trades extras (MT5 fill, engine nao): {len(extra_trades)} | P/L: {extra_pnl:+,.0f} pts")
print(f"  SL no mesmo candle do fill: {len(same_candle_trades)} | P/L: {same_candle_pnl:+,.0f} pts")
print(f"  Engine cancelou + MT5 ja preencheu: {stats['mt5_extra_fills_from_cancel']}")
if extra_trades:
    print(f"\n  Top 10 maiores perdas extras:")
    sorted_extras = sorted(extra_trades, key=lambda t: t.pnl_pts)
    for t in sorted_extras[:10]:
        fill_time = df['time'].iloc[t.filled_at] if t.filled_at < len(df) else '?'
        print(f"    {t.order_id}: {t.direction} @ {t.entry_price:,.0f} -> "
              f"{t.exit_price:,.0f} = {t.pnl_pts:+,.0f} pts ({t.close_reason}) [{fill_time}]")

# ============================================================
# 5. TODOS OS TRADES MT5 SIM
# ============================================================
print(f"\n{'='*80}")
print(f"TRADES MT5 SIMULADOR (todos)")
print(f"{'='*80}")

# Criar DataFrame para analise
trade_data = []
for t in mt5_trades:
    fill_time = df['time'].iloc[t.filled_at] if t.filled_at < len(df) else None
    close_time = df['time'].iloc[t.closed_at] if t.closed_at < len(df) else None
    is_extra = t.order_id not in engine_fill_ids

    trade_data.append({
        'order_id': t.order_id,
        'direction': t.direction,
        'fill_time': fill_time,
        'close_time': close_time,
        'entry': t.entry_price,
        'exit': t.exit_price,
        'sl': t.stop_loss,
        'tp': t.take_profit,
        'result': t.result,
        'pnl_pts': t.pnl_pts,
        'reason': t.close_reason,
        'extra': is_extra,  # True = MT5 preencheu mas engine nao
    })

if trade_data:
    tdf = pd.DataFrame(trade_data)
    tdf['fill_time'] = pd.to_datetime(tdf['fill_time'])
    tdf['dia'] = tdf['fill_time'].dt.date

    # Imprimir cada trade
    print(f"{'#':<5} {'ID':<10} {'Dir':<8} {'Fill Time':<18} {'Entry':>10} {'Exit':>10} "
          f"{'P/L':>8} {'Result':<6} {'Reason':<20} {'Extra':<6}")
    print("-" * 110)
    for i, (_, row) in enumerate(tdf.iterrows()):
        fill_str = row['fill_time'].strftime('%m/%d %H:%M') if pd.notna(row['fill_time']) else '?'
        extra_str = "<<< MT5" if row['extra'] else ""
        print(f"{i+1:<5} {row['order_id']:<10} {row['direction']:<8} {fill_str:<18} "
              f"{row['entry']:>10,.0f} {row['exit']:>10,.0f} {row['pnl_pts']:>+8,.0f} "
              f"{row['result']:<6} {row['reason']:<20} {extra_str}")

    # ============================================================
    # 6. RESULTADO POR DIA
    # ============================================================
    print(f"\n{'='*80}")
    print("RESULTADO POR DIA (MT5 Simulador)")
    print(f"{'='*80}")

    daily = tdf.groupby('dia').agg(
        trades=('result', 'count'),
        wins=('result', lambda x: (x == 'WIN').sum()),
        losses=('result', lambda x: (x == 'LOSS').sum()),
        pnl_pts=('pnl_pts', 'sum'),
        extras=('extra', 'sum'),
    ).reset_index()
    daily['wr'] = daily['wins'] / daily['trades'] * 100

    print(f"{'Dia':<14} {'Trades':>7} {'Wins':>6} {'Loss':>6} {'WR%':>7} {'P/L(pts)':>12} {'Extras':>7}")
    print("-" * 65)
    for _, row in daily.iterrows():
        dow = pd.Timestamp(row['dia']).day_name()[:3]
        print(f"{row['dia']} {dow}  {row['trades']:>7} {row['wins']:>6} {row['losses']:>6} "
              f"{row['wr']:>6.1f}% {row['pnl_pts']:>+12,.0f} {int(row['extras']):>7}")
    print("-" * 65)
    print(f"{'TOTAL':<17} {m_total:>7} {m_wins:>6} {m_losses:>6} "
          f"{m_wr:>6.1f}% {m_pnl:>+12,.0f} {int(tdf['extra'].sum()):>7}")

    # ============================================================
    # 7. RESULTADO POR SEMANA
    # ============================================================
    tdf['semana'] = tdf['fill_time'].dt.isocalendar().week

    print(f"\n{'='*80}")
    print("RESULTADO POR SEMANA (MT5 Simulador)")
    print(f"{'='*80}")

    weekly = tdf.groupby('semana').agg(
        trades=('result', 'count'),
        wins=('result', lambda x: (x == 'WIN').sum()),
        losses=('result', lambda x: (x == 'LOSS').sum()),
        pnl_pts=('pnl_pts', 'sum'),
        extras=('extra', 'sum'),
        first_day=('dia', 'min'),
        last_day=('dia', 'max'),
    ).reset_index()
    weekly['wr'] = weekly['wins'] / weekly['trades'] * 100

    print(f"{'Sem':<6} {'Periodo':<25} {'Trd':>5} {'W':>4} {'L':>4} {'WR%':>7} {'P/L(pts)':>12} {'Ext':>5}")
    print("-" * 75)
    for _, row in weekly.iterrows():
        periodo = f"{row['first_day']} a {row['last_day']}"
        print(f"W{int(row['semana']):<5} {periodo:<25} {row['trades']:>5} {row['wins']:>4} {row['losses']:>4} "
              f"{row['wr']:>6.1f}% {row['pnl_pts']:>+12,.0f} {int(row['extras']):>5}")
    print("-" * 75)
    print(f"{'TOTAL':<6} {'':<25} {m_total:>5} {m_wins:>4} {m_losses:>4} "
          f"{m_wr:>6.1f}% {m_pnl:>+12,.0f} {int(tdf['extra'].sum()):>5}")

    # ============================================================
    # 8. DRAWDOWN
    # ============================================================
    tdf_sorted = tdf.sort_values('fill_time').reset_index(drop=True)
    tdf_sorted['cum_pnl'] = tdf_sorted['pnl_pts'].cumsum()
    tdf_sorted['peak'] = tdf_sorted['cum_pnl'].cummax()
    tdf_sorted['dd'] = tdf_sorted['cum_pnl'] - tdf_sorted['peak']
    max_dd = tdf_sorted['dd'].min()
    ratio = m_pnl / abs(max_dd) if max_dd != 0 else float('inf')

    # Max consecutivas losses
    consec = 0
    max_consec = 0
    for _, row in tdf_sorted.iterrows():
        if row['result'] == 'LOSS':
            consec += 1
            max_consec = max(max_consec, consec)
        else:
            consec = 0

    dias_pos = len(daily[daily['pnl_pts'] > 0])
    dias_neg = len(daily[daily['pnl_pts'] < 0])
    semanas_pos = len(weekly[weekly['pnl_pts'] > 0])
    semanas_neg = len(weekly[weekly['pnl_pts'] <= 0])

    print(f"\n{'='*80}")
    print("DRAWDOWN & ESTATISTICAS (MT5 Simulador)")
    print(f"{'='*80}")
    print(f"  Max Drawdown: {max_dd:,.0f} pts")
    print(f"  Ratio Lucro/DD: {ratio:.2f}x")
    print(f"  Max losses consecutivas: {max_consec}")
    print(f"  Dias positivos: {dias_pos} | Negativos: {dias_neg}")
    print(f"  Semanas positivas: {semanas_pos} | Negativas: {semanas_neg}")

    # ============================================================
    # 9. COMPARACAO ENGINE vs MT5 SIM (lado a lado)
    # ============================================================
    print(f"\n{'='*80}")
    print("COMPARACAO FINAL: ENGINE (backtest) vs MT5 SIM (realista)")
    print(f"{'='*80}")

    # Engine por dia
    e_trade_data = []
    for t in engine_closed:
        fill_idx = t['filled_at']
        fill_time = df['time'].iloc[fill_idx] if fill_idx < len(df) else None
        e_trade_data.append({
            'fill_time': fill_time,
            'result': 'WIN' if t['status'] == 'closed_tp' else 'LOSS',
            'pnl_pts': t['profit_loss'],
        })

    if e_trade_data:
        edf = pd.DataFrame(e_trade_data)
        edf['fill_time'] = pd.to_datetime(edf['fill_time'])
        edf['dia'] = edf['fill_time'].dt.date

        e_daily = edf.groupby('dia').agg(
            e_trades=('result', 'count'),
            e_pnl=('pnl_pts', 'sum'),
        ).reset_index()

        m_daily = tdf.groupby('dia').agg(
            m_trades=('result', 'count'),
            m_pnl=('pnl_pts', 'sum'),
        ).reset_index()

        compare = pd.merge(e_daily, m_daily, on='dia', how='outer').fillna(0)
        compare['delta_trades'] = compare['m_trades'] - compare['e_trades']
        compare['delta_pnl'] = compare['m_pnl'] - compare['e_pnl']

        print(f"{'Dia':<14} {'Eng Trd':>8} {'Eng P/L':>10} {'MT5 Trd':>8} {'MT5 P/L':>10} "
              f"{'dTrd':>6} {'dP/L':>10}")
        print("-" * 75)
        for _, row in compare.iterrows():
            dow = pd.Timestamp(row['dia']).day_name()[:3]
            print(f"{row['dia']} {dow}  {int(row['e_trades']):>8} {row['e_pnl']:>+10,.0f} "
                  f"{int(row['m_trades']):>8} {row['m_pnl']:>+10,.0f} "
                  f"{int(row['delta_trades']):>+6} {row['delta_pnl']:>+10,.0f}")
        print("-" * 75)
        print(f"{'TOTAL':<17} {e_total:>8} {e_pnl:>+10,.0f} {m_total:>8} {m_pnl:>+10,.0f} "
              f"{m_total-e_total:>+6} {m_pnl-e_pnl:>+10,.0f}")

    # ============================================================
    # 10. SIMULACAO FINANCEIRA
    # ============================================================
    valor_ponto = 0.20
    dias_pregao = len(daily)
    meses = max(1, dias_pregao / 21)

    print(f"\n{'='*80}")
    print("SIMULACAO FINANCEIRA MT5 SIM (WIN mini)")
    print(f"{'='*80}")
    print(f"  Valor do ponto: R$ {valor_ponto:.2f}")
    print(f"  Periodo: ~{meses:.1f} meses ({dias_pregao} dias)")
    for contratos in [1, 2, 5, 10]:
        lucro = m_pnl * valor_ponto * contratos
        lucro_mensal = lucro / meses
        print(f"  {contratos:>2} contrato(s): R$ {lucro:>+12,.2f} total  |  R$ {lucro_mensal:>+10,.2f}/mes")

    # ============================================================
    # 11. EQUITY CURVE
    # ============================================================
    output_dir = os.path.join(os.path.dirname(__file__), 'resultado_mt5_sim')
    os.makedirs(output_dir, exist_ok=True)

    fig, axes = plt.subplots(2, 1, figsize=(18, 12), gridspec_kw={'height_ratios': [3, 1.5]})
    fig.patch.set_facecolor('#1e1e2f')

    # --- Equity curves lado a lado ---
    ax1 = axes[0]
    ax1.set_facecolor('#1e1e2f')

    # MT5 sim equity
    cum_mt5 = tdf_sorted['cum_pnl'].values
    x_mt5 = range(len(tdf_sorted))
    ax1.plot(x_mt5, cum_mt5, color='#FF6B35', linewidth=2, label=f'MT5 Sim ({m_total} trades, {m_pnl:+,.0f} pts)')
    ax1.fill_between(x_mt5, 0, cum_mt5, alpha=0.1, color='#FF6B35')

    # Engine equity
    if e_trade_data:
        edf_sorted = edf.sort_values('fill_time').reset_index(drop=True)
        edf_sorted['cum_pnl'] = edf_sorted['pnl_pts'].cumsum()
        x_eng = range(len(edf_sorted))
        ax1.plot(x_eng, edf_sorted['cum_pnl'].values, color='#42A5F5', linewidth=2,
                 label=f'Engine ({e_total} trades, {e_pnl:+,.0f} pts)', linestyle='--')

    ax1.axhline(y=0, color='#555555', linewidth=0.8, linestyle='--')

    # Marcar force closes
    for i_t, t in enumerate(tdf_sorted.itertuples()):
        if t.extra:
            ax1.scatter(i_t, cum_mt5[i_t], color='#EF5350', s=40, zorder=5,
                       marker='x', linewidths=2)

    ax1.set_title(f'Equity Curve: Engine vs MT5 Simulador ({label})\n'
                  f'Engine: {e_total} trades | {e_wr:.0f}% WR | PF {e_pf:.2f} | {e_pnl:+,.0f} pts\n'
                  f'MT5 Sim: {m_total} trades | {m_wr:.0f}% WR | PF {m_pf:.2f} | {m_pnl:+,.0f} pts',
                  fontsize=13, color='white', fontweight='bold', pad=15)
    ax1.set_ylabel('Lucro Acumulado (pts)', color='#aaaaaa', fontsize=11)
    ax1.tick_params(colors='#aaaaaa')
    for sp in ['top', 'right']: ax1.spines[sp].set_visible(False)
    for sp in ['bottom', 'left']: ax1.spines[sp].set_color('#555555')
    ax1.grid(True, alpha=0.1, color='#555555')
    ax1.legend(fontsize=11, facecolor='#2a2a3d', edgecolor='#555555', labelcolor='white')

    # --- Drawdown MT5 ---
    ax2 = axes[1]
    ax2.set_facecolor('#1e1e2f')
    dd_vals = tdf_sorted['dd'].values
    ax2.fill_between(x_mt5, dd_vals, 0, alpha=0.4, color='#EF5350')
    ax2.plot(x_mt5, dd_vals, color='#EF5350', linewidth=1, alpha=0.8)
    ax2.set_title(f'Drawdown MT5 Sim (Max: {max_dd:,.0f} pts)', fontsize=13,
                  color='white', fontweight='bold', pad=10)
    ax2.set_ylabel('Drawdown (pts)', color='#aaaaaa', fontsize=10)
    ax2.set_xlabel('Trade #', color='#aaaaaa', fontsize=10)
    ax2.tick_params(colors='#aaaaaa')
    for sp in ['top', 'right']: ax2.spines[sp].set_visible(False)
    for sp in ['bottom', 'left']: ax2.spines[sp].set_color('#555555')
    ax2.grid(True, alpha=0.1, color='#555555')

    plt.tight_layout()
    chart_path = os.path.join(output_dir, 'engine_vs_mt5sim.png')
    plt.savefig(chart_path, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.close()
    print(f"\nGrafico salvo: {chart_path}")

    # Salvar CSV
    csv_path = os.path.join(output_dir, 'trades_mt5sim.csv')
    tdf.to_csv(csv_path, index=False)
    print(f"CSV salvo: {csv_path}")

else:
    print("Nenhum trade no periodo selecionado.")

# ============================================================
# RESUMO FINAL
# ============================================================
print(f"\n{'='*80}")
print("RESUMO FINAL")
print(f"{'='*80}")
print(f"  Engine:  {e_total} trades | WR {e_wr:.1f}% | PF {e_pf:.2f} | P/L {e_pnl:+,.0f} pts")
print(f"  MT5 Sim: {m_total} trades | WR {m_wr:.1f}% | PF {m_pf:.2f} | P/L {m_pnl:+,.0f} pts")
print(f"  Divergencia: {m_total - e_total:+} trades | {m_pnl - e_pnl:+,.0f} pts")
print(f"  Trades extras (so MT5): {len(extra_trades)} | P/L extras: {extra_pnl:+,.0f} pts")
print(f"  Max DD: {max_dd:,.0f} pts | Ratio: {ratio:.2f}x")
