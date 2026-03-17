"""
Backtest de Janeiro/2026 - Dados do MetaTrader 5
"""
import sys
import os
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from datetime import datetime, timedelta
from smc_engine_v3 import SMCEngineV3

# ============================================================
# 1. CONECTAR AO MT5 E PUXAR DADOS
# ============================================================
print("Conectando ao MetaTrader 5...")
if not mt5.initialize():
    print(f"ERRO: {mt5.last_error()}")
    sys.exit(1)

# Detectar símbolo
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
        print("ERRO: Nenhum símbolo WIN encontrado!")
        mt5.shutdown()
        sys.exit(1)

print(f"Símbolo: {symbol}")

inicio = datetime(2026, 1, 1)
fim = datetime(2026, 2, 1)

print(f"Buscando candles M1 de 01/01/2026 até 31/01/2026...")
rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, inicio, fim)
mt5.shutdown()

if rates is None or len(rates) == 0:
    print("ERRO: Nenhum candle encontrado para Janeiro/2026.")
    sys.exit(1)

df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')

# Filtrar apenas janeiro
df = df[df['time'].dt.month == 1].reset_index(drop=True)

dias_pregao = df['time'].dt.date.nunique()
print(f"Total: {len(df):,} candles M1")
print(f"Período: {df['time'].iloc[0]} até {df['time'].iloc[-1]}")
print(f"Dias de pregão: {dias_pregao}")

# ============================================================
# 2. EXECUTAR ENGINE
# ============================================================
print("\nExecutando SMC Engine V3 (RR 3:1)...")

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

for i in range(len(df)):
    row = df.iloc[i]
    engine.add_candle({
        'open': float(row['open']),
        'high': float(row['high']),
        'low': float(row['low']),
        'close': float(row['close']),
        'volume': float(row.get('real_volume', row.get('tick_volume', 0)))
    })
    if (i + 1) % 5000 == 0:
        print(f"  {i+1:,} candles...")

print(f"  {len(df):,} candles processados")

# ============================================================
# 3. COLETAR TRADES
# ============================================================
raw_trades = engine.get_all_trades()

if len(raw_trades) == 0:
    print("\nNenhum trade fechado em Janeiro.")
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
        'wait_candles': t['wait_candles'],
        'duration_candles': t['duration_candles'],
    })

tdf = pd.DataFrame(trade_data)
tdf['fill_time'] = pd.to_datetime(tdf['fill_time'])
tdf['dia'] = tdf['fill_time'].dt.date

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
print(f"RESULTADO JANEIRO/2026 ({symbol})")
print(f"{'='*80}")
print(f"  Candles: {len(df):,} | Dias de pregão: {dias_pregao}")
print(f"  Total de trades: {total}")
print(f"  Wins: {wins} | Losses: {losses}")
print(f"  Win Rate: {wr:.1f}%")
print(f"  Profit Factor: {pf:.2f}")
print(f"  Lucro total: {total_pts:+,.2f} pontos")
print(f"  Lucro total: {total_r:+,.2f} R")
print(f"  Expectativa: {exp_r:.2f}R/trade")

# ============================================================
# 5. RESULTADO POR DIA
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
print("-" * 70)
for _, row in daily.iterrows():
    dia_str = row['dia'].strftime('%d/%m/%Y')
    print(f"{dia_str:<14} {row['trades']:>7} {row['wins']:>6} {row['losses']:>6} "
          f"{row['wr']:>6.1f}% {row['pnl_pts']:>+14,.2f} {row['pnl_r']:>+10,.2f}")
print("-" * 70)
print(f"{'TOTAL':<14} {total:>7} {wins:>6} {losses:>6} "
      f"{wr:>6.1f}% {total_pts:>+14,.2f} {total_r:>+10,.2f}")

# ============================================================
# 6. DRAWDOWN
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
for _, row in tdf_sorted.iterrows():
    if row['result'] == 'LOSS':
        consecutive_losses += 1
        max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
    else:
        consecutive_losses = 0

dias_pos = len(daily[daily['pnl_pts'] > 0])
dias_neg = len(daily[daily['pnl_pts'] < 0])
best_day = daily.loc[daily['pnl_pts'].idxmax()]
worst_day = daily.loc[daily['pnl_pts'].idxmin()]

print(f"\n{'='*80}")
print("DRAWDOWN & ESTATÍSTICAS")
print(f"{'='*80}")
print(f"  Max Drawdown: {max_dd_pts:,.2f} pts | {max_dd_r:,.2f} R")
print(f"  Ratio Lucro/DD: {ratio:.2f}x")
print(f"  Max losses consecutivas: {max_consecutive_losses}")
print(f"  Melhor dia: {best_day['dia'].strftime('%d/%m')} ({best_day['pnl_pts']:+,.0f} pts)")
print(f"  Pior dia:   {worst_day['dia'].strftime('%d/%m')} ({worst_day['pnl_pts']:+,.0f} pts)")
print(f"  Dias positivos: {dias_pos} | Negativos: {dias_neg}")

# ============================================================
# 7. SIMULAÇÃO FINANCEIRA
# ============================================================
print(f"\n{'='*80}")
print("SIMULAÇÃO FINANCEIRA (1 contrato WIN)")
print(f"{'='*80}")
valor_ponto = 0.20  # R$ 0,20 por ponto do mini índice
lucro_brl = total_pts * valor_ponto
print(f"  Valor do ponto (mini): R$ {valor_ponto:.2f}")
print(f"  Lucro bruto: R$ {lucro_brl:+,.2f}")

for contratos in [1, 2, 5, 10]:
    lucro = total_pts * valor_ponto * contratos
    print(f"  {contratos:>2} contrato(s): R$ {lucro:+,.2f}")

# ============================================================
# 8. EQUITY CURVE
# ============================================================
output_dir = os.path.join(os.path.dirname(__file__), 'trades_janeiro')
os.makedirs(output_dir, exist_ok=True)

fig, axes = plt.subplots(2, 1, figsize=(16, 12), gridspec_kw={'height_ratios': [2, 1]})
fig.patch.set_facecolor('#1e1e2f')

ax1 = axes[0]
ax1.set_facecolor('#1e1e2f')
x = range(len(tdf_sorted))
cum_pts = tdf_sorted['cumulative_pts'].values
colors = ['#66BB6A' if r == 'WIN' else '#EF5350' for r in tdf_sorted['result']]
ax1.fill_between(x, 0, cum_pts, alpha=0.15, color='#42A5F5')
ax1.plot(x, cum_pts, color='#42A5F5', linewidth=2, label='Equity (pts)')
for i in range(len(tdf_sorted)):
    ax1.scatter(i, cum_pts[i], color=colors[i], s=30, zorder=3, edgecolors='white', linewidths=0.4)
ax1.axhline(y=0, color='#555555', linewidth=0.8, linestyle='--')
ax1.set_title(f'Equity Curve - JANEIRO/2026 ({symbol})\n'
              f'{total} trades | WR {wr:.1f}% | PF {pf:.2f} | {total_pts:+,.0f} pts ({total_r:+,.1f}R)',
              fontsize=14, color='white', fontweight='bold', pad=15)
ax1.set_ylabel('Lucro Acumulado (pts)', color='#aaaaaa', fontsize=11)
ax1.tick_params(colors='#aaaaaa')
for spine in ['top', 'right']:
    ax1.spines[spine].set_visible(False)
for spine in ['bottom', 'left']:
    ax1.spines[spine].set_color('#555555')
ax1.grid(True, alpha=0.1, color='#555555')
ax1.legend(fontsize=10, facecolor='#2a2a3d', edgecolor='#555555', labelcolor='white')

ax2 = axes[1]
ax2.set_facecolor('#1e1e2f')
bar_colors = ['#66BB6A' if v >= 0 else '#EF5350' for v in daily['pnl_pts']]
bar_x = range(len(daily))
ax2.bar(bar_x, daily['pnl_pts'], color=bar_colors, alpha=0.85, edgecolor='white', linewidth=0.3)
for i, (_, row) in enumerate(daily.iterrows()):
    va = 'bottom' if row['pnl_pts'] >= 0 else 'top'
    offset = max(abs(daily['pnl_pts'].max()) * 0.03, 10) * (1 if row['pnl_pts'] >= 0 else -1)
    ax2.text(i, row['pnl_pts'] + offset, f"{row['pnl_pts']:+,.0f}",
             ha='center', va=va, fontsize=7, color='#cccccc', fontweight='bold')
ax2.axhline(y=0, color='#555555', linewidth=0.8)
ax2.set_title('P/L por Dia', fontsize=12, color='white', fontweight='bold', pad=10)
ax2.set_ylabel('Pontos', color='#aaaaaa', fontsize=10)
tick_labels = [row['dia'].strftime('%d/%m') for _, row in daily.iterrows()]
ax2.set_xticks(bar_x)
ax2.set_xticklabels(tick_labels, rotation=45, fontsize=7, color='#aaaaaa')
ax2.tick_params(colors='#aaaaaa')
for spine in ['top', 'right']:
    ax2.spines[spine].set_visible(False)
for spine in ['bottom', 'left']:
    ax2.spines[spine].set_color('#555555')
ax2.grid(True, alpha=0.1, color='#555555', axis='y')

plt.tight_layout()
equity_path = os.path.join(output_dir, 'equity_curve_janeiro.png')
plt.savefig(equity_path, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
plt.close()
print(f"\nEquity curve salva: {equity_path}")

# ============================================================
# RESUMO FINAL
# ============================================================
print(f"\n{'='*80}")
print("RESUMO JANEIRO/2026")
print(f"{'='*80}")
print(f"  Trades: {total} | WR: {wr:.1f}% | PF: {pf:.2f}")
print(f"  Lucro: {total_pts:+,.0f} pts | {total_r:+,.1f}R")
print(f"  Max DD: {max_dd_pts:,.0f} pts | Ratio: {ratio:.1f}x")
print(f"  Dias +: {dias_pos} | Dias -: {dias_neg}")
print(f"  R$ (1 mini): R$ {lucro_brl:+,.2f}")
