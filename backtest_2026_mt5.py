"""
Backtest 2026 - Dados do MetaTrader 5
======================================
Puxa candles M1 de Jan/2026 ate hoje e roda SMCEngineV3
com parametros otimizados (RR=2.0, retrace=0.7, max_sl=50, size=0.3).
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

symbols_to_try = ["WIN$N", "WING26", "WINH26", "WINJ26", "WIN$"]
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

# Puxar dados de 2026
inicio = datetime(2026, 1, 1)
fim = datetime(2026, 3, 1)  # ate amanha para pegar hoje completo

print(f"Buscando candles M1 de {inicio.date()} ate {fim.date()}...")
rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, inicio, fim)
mt5.shutdown()

if rates is None or len(rates) == 0:
    print("ERRO: Nenhum dado encontrado para 2026.")
    sys.exit(1)

df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')
df = df[df['time'].dt.year == 2026].reset_index(drop=True)
df = df.drop_duplicates(subset='time').sort_values('time').reset_index(drop=True)

dias_pregao = df['time'].dt.date.nunique()
semanas = df['time'].dt.isocalendar().week.nunique()
print(f"\nTotal: {len(df):,} candles M1")
print(f"Periodo: {df['time'].iloc[0]} ate {df['time'].iloc[-1]}")
print(f"Dias de pregao: {dias_pregao} | Semanas: {semanas}")

# ============================================================
# 2. EXECUTAR ENGINE - PARAMETROS OTIMIZADOS
# ============================================================
print("\nExecutando SMC Engine V3 (OTIMIZADO: RR=2.0, ret=0.7, sl<=50, size>=0.3*ATR)...")
engine = SMCEngineV3(
    symbol=symbol,
    swing_length=5,
    risk_reward_ratio=2.0,          # Otimizado (era 3.0)
    min_volume_ratio=0.0,
    min_ob_size_atr=0.3,            # Otimizado (era 0.0)
    use_not_mitigated_filter=True,
    max_pending_candles=150,
    entry_delay_candles=1,
    tick_size=5.0,
    min_confidence=0.0,
    max_sl_points=50.0,             # Otimizado: SL max 50 pts
    min_patterns=0,
    entry_retracement=0.7,          # Otimizado (era 0.5 midline)
)

for i in range(len(df)):
    row = df.iloc[i]
    engine.add_candle({
        'open': float(row['open']),
        'high': float(row['high']),
        'low': float(row['low']),
        'close': float(row['close']),
        'volume': float(row.get('real_volume', row.get('tick_volume', 0)))
    })
    if (i + 1) % 10000 == 0:
        print(f"  {i+1:,} candles...")

print(f"  {len(df):,} candles processados")

# ============================================================
# 3. COLETAR TRADES
# ============================================================
raw_trades = engine.get_all_trades()
if not raw_trades or len(raw_trades) == 0:
    print("\nNenhum trade fechado em 2026.")
    sys.exit(0)

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
        'patterns': ','.join(t.get('patterns', [])),
        'wait_candles': t['wait_candles'],
        'duration_candles': t['duration_candles'],
    })

tdf = pd.DataFrame(trade_data)
tdf['fill_time'] = pd.to_datetime(tdf['fill_time'])
tdf['dia'] = tdf['fill_time'].dt.date
tdf['semana'] = tdf['fill_time'].dt.isocalendar().week

wins = len(tdf[tdf['result'] == 'WIN'])
losses = len(tdf[tdf['result'] == 'LOSS'])
total = wins + losses
wr = wins / total * 100 if total > 0 else 0
total_pts = tdf['pnl_pts'].sum()
total_r = tdf['pnl_r'].sum()
win_pts = tdf[tdf['result'] == 'WIN']['pnl_pts'].sum()
loss_pts = abs(tdf[tdf['result'] == 'LOSS']['pnl_pts'].sum())
pf = win_pts / loss_pts if loss_pts > 0 else float('inf')
exp_r = total_r / total if total > 0 else 0

# ============================================================
# 4. RESULTADO GERAL
# ============================================================
print(f"\n{'='*80}")
print(f"PERFORMANCE 2026 ({symbol}) - PARAMETROS OTIMIZADOS")
print(f"{'='*80}")
print(f"  Config: RR=2.0 | retrace=0.7 | max_sl=50 | min_size=0.3*ATR")
print(f"  Candles: {len(df):,} | Dias: {dias_pregao} | Semanas: {semanas}")
print(f"  Total de trades: {total}")
print(f"  Wins: {wins} | Losses: {losses}")
print(f"  Win Rate: {wr:.1f}%")
print(f"  Profit Factor: {pf:.2f}")
print(f"  Lucro total: {total_pts:+,.2f} pontos")
print(f"  Lucro total: {total_r:+,.2f} R")
print(f"  Expectancia: {exp_r:.2f}R/trade")
print(f"  Trades/dia (media): {total/dias_pregao:.1f}")

# ============================================================
# 5. RESULTADO POR SEMANA
# ============================================================
print(f"\n{'='*80}")
print("RESULTADO POR SEMANA")
print(f"{'='*80}")

weekly = tdf.groupby('semana').agg(
    trades=('result', 'count'),
    wins=('result', lambda x: (x == 'WIN').sum()),
    losses=('result', lambda x: (x == 'LOSS').sum()),
    pnl_pts=('pnl_pts', 'sum'),
    pnl_r=('pnl_r', 'sum'),
    first_day=('dia', 'min'),
    last_day=('dia', 'max'),
).reset_index()
weekly['wr'] = weekly['wins'] / weekly['trades'] * 100

print(f"{'Semana':<10} {'Periodo':<25} {'Trades':>7} {'Wins':>6} {'Loss':>6} {'WR%':>7} {'Lucro(pts)':>14} {'Lucro(R)':>10}")
print("-" * 95)
for _, row in weekly.iterrows():
    periodo = f"{row['first_day']} a {row['last_day']}"
    print(f"W{int(row['semana']):<9} {periodo:<25} {row['trades']:>7} {row['wins']:>6} {row['losses']:>6} "
          f"{row['wr']:>6.1f}% {row['pnl_pts']:>+14,.2f} {row['pnl_r']:>+10,.2f}")
print("-" * 95)
pf_str = f"{pf:.2f}"
print(f"{'TOTAL':<10} {'':<25} {total:>7} {wins:>6} {losses:>6} "
      f"{wr:>6.1f}% {total_pts:>+14,.2f} {total_r:>+10,.2f}")

# ============================================================
# 6. RESULTADO POR DIA
# ============================================================
print(f"\n{'='*80}")
print("RESULTADO POR DIA")
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
print("-" * 75)
for _, row in daily.iterrows():
    dow = pd.Timestamp(row['dia']).day_name()[:3]
    print(f"{row['dia']} {dow}  {row['trades']:>7} {row['wins']:>6} {row['losses']:>6} "
          f"{row['wr']:>6.1f}% {row['pnl_pts']:>+14,.2f} {row['pnl_r']:>+10,.2f}")

# ============================================================
# 7. DRAWDOWN
# ============================================================
tdf_sorted = tdf.sort_values('fill_time').reset_index(drop=True)
tdf_sorted['cumulative_pts'] = tdf_sorted['pnl_pts'].cumsum()
tdf_sorted['cumulative_r'] = tdf_sorted['pnl_r'].cumsum()
tdf_sorted['peak_pts'] = tdf_sorted['cumulative_pts'].cummax()
tdf_sorted['drawdown_pts'] = tdf_sorted['cumulative_pts'] - tdf_sorted['peak_pts']
max_dd_pts = tdf_sorted['drawdown_pts'].min()
tdf_sorted['peak_r'] = tdf_sorted['cumulative_r'].cummax()
tdf_sorted['drawdown_r'] = tdf_sorted['cumulative_r'] - tdf_sorted['peak_r']
max_dd_r = tdf_sorted['drawdown_r'].min()
ratio = total_pts / abs(max_dd_pts) if max_dd_pts != 0 else float('inf')

consecutive_losses = 0
max_consecutive_losses = 0
max_consecutive_loss_pts = 0
curr_loss_pts = 0
for _, row in tdf_sorted.iterrows():
    if row['result'] == 'LOSS':
        consecutive_losses += 1
        curr_loss_pts += row['pnl_pts']
        max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
        max_consecutive_loss_pts = min(max_consecutive_loss_pts, curr_loss_pts)
    else:
        consecutive_losses = 0
        curr_loss_pts = 0

dias_pos = len(daily[daily['pnl_pts'] > 0])
dias_neg = len(daily[daily['pnl_pts'] < 0])
dias_zero = len(daily[daily['pnl_pts'] == 0])
semanas_pos = len(weekly[weekly['pnl_pts'] > 0])
semanas_neg = len(weekly[weekly['pnl_pts'] <= 0])

print(f"\n{'='*80}")
print("DRAWDOWN & ESTATISTICAS")
print(f"{'='*80}")
print(f"  Max Drawdown: {max_dd_pts:,.2f} pts | {max_dd_r:,.2f} R")
print(f"  Ratio Lucro/DD: {ratio:.2f}x")
print(f"  Max losses consecutivas: {max_consecutive_losses}")
print(f"  Max perda consecutiva: {max_consecutive_loss_pts:,.2f} pts")
print(f"  Dias positivos: {dias_pos} | Negativos: {dias_neg} | Zero: {dias_zero}")
print(f"  Semanas positivas: {semanas_pos} | Negativas: {semanas_neg}")

# ============================================================
# 8. COMPARACAO COM BASELINE (RR=3.0 sem filtros)
# ============================================================
print(f"\n{'='*80}")
print("COMPARACAO: OTIMIZADO vs BASELINE (RR=3.0, sem filtros)")
print(f"{'='*80}")
print("Rodando baseline...")

engine_base = SMCEngineV3(
    symbol=symbol,
    swing_length=5,
    risk_reward_ratio=3.0,
    min_volume_ratio=0.0,
    min_ob_size_atr=0.0,
    use_not_mitigated_filter=True,
    max_pending_candles=150,
    entry_delay_candles=1,
    tick_size=5.0,
    min_confidence=0.0,
    max_sl_points=0.0,
    min_patterns=0,
    entry_retracement=0.5,
)

for i in range(len(df)):
    row = df.iloc[i]
    engine_base.add_candle({
        'open': float(row['open']),
        'high': float(row['high']),
        'low': float(row['low']),
        'close': float(row['close']),
        'volume': float(row.get('real_volume', row.get('tick_volume', 0)))
    })

base_trades = engine_base.get_all_trades() or []
base_closed = [t for t in base_trades if t['status'] in ('closed_tp', 'closed_sl')]
b_wins = sum(1 for t in base_closed if t['status'] == 'closed_tp')
b_losses = sum(1 for t in base_closed if t['status'] == 'closed_sl')
b_total = b_wins + b_losses
b_wr = b_wins / b_total * 100 if b_total > 0 else 0
b_pnl = sum(t['profit_loss'] for t in base_closed)
b_r = sum(t['profit_loss_r'] for t in base_closed)
b_win_pts = sum(t['profit_loss'] for t in base_closed if t['status'] == 'closed_tp')
b_loss_pts = abs(sum(t['profit_loss'] for t in base_closed if t['status'] == 'closed_sl'))
b_pf = b_win_pts / b_loss_pts if b_loss_pts > 0 else float('inf')
b_exp = b_r / b_total if b_total > 0 else 0

print(f"  {'Metrica':<25} {'Baseline':>15} {'Otimizado':>15} {'Delta':>12}")
print(f"  {'-'*70}")
print(f"  {'Trades':<25} {b_total:>15} {total:>15} {total-b_total:>+12}")
print(f"  {'Win Rate':<25} {b_wr:>14.1f}% {wr:>14.1f}% {wr-b_wr:>+11.1f}%")
print(f"  {'Profit Factor':<25} {b_pf:>15.2f} {pf:>15.2f} {pf-b_pf:>+12.2f}")
print(f"  {'P/L (pts)':<25} {b_pnl:>+15,.0f} {total_pts:>+15,.0f} {total_pts-b_pnl:>+12,.0f}")
print(f"  {'Expectancia (R)':<25} {b_exp:>+15.2f} {exp_r:>+15.2f} {exp_r-b_exp:>+12.2f}")

# ============================================================
# 9. SIMULACAO FINANCEIRA
# ============================================================
valor_ponto = 0.20
meses_dados = max(1, dias_pregao / 21)  # ~21 dias uteis por mes
print(f"\n{'='*80}")
print("SIMULACAO FINANCEIRA (WIN mini)")
print(f"{'='*80}")
print(f"  Valor do ponto: R$ {valor_ponto:.2f}")
print(f"  Periodo: ~{meses_dados:.1f} meses")
for contratos in [1, 2, 5, 10, 20]:
    lucro = total_pts * valor_ponto * contratos
    lucro_mensal = lucro / meses_dados
    print(f"  {contratos:>2} contrato(s): R$ {lucro:>+12,.2f} total  |  R$ {lucro_mensal:>+10,.2f}/mes")

# ============================================================
# 10. EQUITY CURVE + GRAFICOS
# ============================================================
output_dir = os.path.join(os.path.dirname(__file__), 'resultado_2026')
os.makedirs(output_dir, exist_ok=True)

fig, axes = plt.subplots(3, 1, figsize=(18, 16), gridspec_kw={'height_ratios': [3, 1.5, 1.5]})
fig.patch.set_facecolor('#1e1e2f')

# --- Equity Curve ---
ax1 = axes[0]
ax1.set_facecolor('#1e1e2f')
x = range(len(tdf_sorted))
cum_pts = tdf_sorted['cumulative_pts'].values
colors = ['#66BB6A' if r == 'WIN' else '#EF5350' for r in tdf_sorted['result']]
ax1.fill_between(x, 0, cum_pts, alpha=0.12, color='#42A5F5')
ax1.plot(x, cum_pts, color='#42A5F5', linewidth=1.5, label='Equity (pts)')
for i in range(0, len(tdf_sorted), max(1, len(tdf_sorted)//20)):
    ax1.scatter(i, cum_pts[i], color=colors[i], s=20, zorder=3, edgecolors='white', linewidths=0.3)
ax1.axhline(y=0, color='#555555', linewidth=0.8, linestyle='--')

dd_vals = tdf_sorted['drawdown_pts'].values
ax1.fill_between(x, cum_pts, tdf_sorted['peak_pts'].values, alpha=0.08, color='#EF5350')

ax1.set_title(f'Equity Curve - 2026 ({symbol}) OTIMIZADO\n'
              f'{total} trades | WR {wr:.1f}% | PF {pf:.2f} | {total_pts:+,.0f} pts ({total_r:+,.1f}R)\n'
              f'RR=2.0 | ret=0.7 | max_sl=50 | size>=0.3*ATR',
              fontsize=14, color='white', fontweight='bold', pad=15)
ax1.set_ylabel('Lucro Acumulado (pts)', color='#aaaaaa', fontsize=11)
ax1.tick_params(colors='#aaaaaa')
for sp in ['top', 'right']: ax1.spines[sp].set_visible(False)
for sp in ['bottom', 'left']: ax1.spines[sp].set_color('#555555')
ax1.grid(True, alpha=0.1, color='#555555')
ax1.legend(fontsize=10, facecolor='#2a2a3d', edgecolor='#555555', labelcolor='white')

# --- P/L por Semana ---
ax2 = axes[1]
ax2.set_facecolor('#1e1e2f')
bar_colors = ['#66BB6A' if v >= 0 else '#EF5350' for v in weekly['pnl_pts']]
bar_x = range(len(weekly))
ax2.bar(bar_x, weekly['pnl_pts'], color=bar_colors, alpha=0.85, edgecolor='white', linewidth=0.3)
for i, (_, row) in enumerate(weekly.iterrows()):
    va = 'bottom' if row['pnl_pts'] >= 0 else 'top'
    offset = max(abs(weekly['pnl_pts'].max()) * 0.05, 20) * (1 if row['pnl_pts'] >= 0 else -1)
    ax2.text(i, row['pnl_pts'] + offset, f"{row['pnl_pts']:+,.0f}\n{row['wr']:.0f}%WR",
             ha='center', va=va, fontsize=8, color='#cccccc', fontweight='bold')
ax2.axhline(y=0, color='#555555', linewidth=0.8)
ax2.set_title('P/L por Semana', fontsize=13, color='white', fontweight='bold', pad=10)
ax2.set_ylabel('Pontos', color='#aaaaaa', fontsize=10)
tick_labels = [f"W{int(row['semana'])}" for _, row in weekly.iterrows()]
ax2.set_xticks(list(bar_x))
ax2.set_xticklabels(tick_labels, fontsize=9, color='#aaaaaa')
ax2.tick_params(colors='#aaaaaa')
for sp in ['top', 'right']: ax2.spines[sp].set_visible(False)
for sp in ['bottom', 'left']: ax2.spines[sp].set_color('#555555')
ax2.grid(True, alpha=0.1, color='#555555', axis='y')

# --- Drawdown ---
ax3 = axes[2]
ax3.set_facecolor('#1e1e2f')
ax3.fill_between(x, dd_vals, 0, alpha=0.4, color='#EF5350')
ax3.plot(x, dd_vals, color='#EF5350', linewidth=1, alpha=0.8)
ax3.set_title(f'Drawdown (Max: {max_dd_pts:,.0f} pts)', fontsize=13, color='white', fontweight='bold', pad=10)
ax3.set_ylabel('Drawdown (pts)', color='#aaaaaa', fontsize=10)
ax3.set_xlabel('Trade #', color='#aaaaaa', fontsize=10)
ax3.tick_params(colors='#aaaaaa')
for sp in ['top', 'right']: ax3.spines[sp].set_visible(False)
for sp in ['bottom', 'left']: ax3.spines[sp].set_color('#555555')
ax3.grid(True, alpha=0.1, color='#555555')

plt.tight_layout()
equity_path = os.path.join(output_dir, 'performance_2026.png')
plt.savefig(equity_path, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
plt.close()
print(f"\nGrafico salvo: {equity_path}")

# ============================================================
# RESUMO FINAL
# ============================================================
lucro_1 = total_pts * valor_ponto
print(f"\n{'='*80}")
print("RESUMO 2026 (OTIMIZADO)")
print(f"{'='*80}")
print(f"  Config: RR=2.0 | retrace=0.7 | max_sl=50 | min_size=0.3*ATR")
print(f"  {total} trades | WR {wr:.1f}% | PF {pf:.2f}")
print(f"  Lucro: {total_pts:+,.0f} pts | {total_r:+,.1f}R")
print(f"  Max DD: {max_dd_pts:,.0f} pts | Ratio: {ratio:.1f}x")
print(f"  Semanas +: {semanas_pos}/{len(weekly)} | Dias +: {dias_pos}/{dias_pregao}")
print(f"  R$ (1 mini): R$ {lucro_1:+,.2f}")

# Salvar CSV
csv_path = os.path.join(output_dir, 'trades_2026.csv')
tdf.to_csv(csv_path, index=False)
print(f"  CSV: {csv_path}")
