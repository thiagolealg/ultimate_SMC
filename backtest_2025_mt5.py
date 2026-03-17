"""
Backtest Anual 2025 - Dados do MetaTrader 5
=============================================
Puxa todos os candles M1 de 2025 via MT5 e roda o SMCEngineV3.
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
        print("ERRO: Nenhum símbolo WIN encontrado!")
        mt5.shutdown()
        sys.exit(1)

print(f"Símbolo: {symbol}")

# Puxar dados mês a mês (MT5 pode limitar grandes requests)
inicio_ano = datetime(2025, 1, 1)
fim_ano = datetime(2026, 1, 1)

print(f"Buscando candles M1 de 2025 (mês a mês)...")
all_rates = []
for mes in range(1, 13):
    inicio_mes = datetime(2025, mes, 1)
    if mes < 12:
        fim_mes = datetime(2025, mes + 1, 1)
    else:
        fim_mes = datetime(2026, 1, 1)

    rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, inicio_mes, fim_mes)
    if rates is not None and len(rates) > 0:
        all_rates.append(pd.DataFrame(rates))
        print(f"  {inicio_mes.strftime('%b/%Y')}: {len(rates):,} candles")
    else:
        print(f"  {inicio_mes.strftime('%b/%Y')}: sem dados")

mt5.shutdown()

if len(all_rates) == 0:
    print("ERRO: Nenhum dado encontrado para 2025.")
    sys.exit(1)

df = pd.concat(all_rates, ignore_index=True)
df['time'] = pd.to_datetime(df['time'], unit='s')
df = df[df['time'].dt.year == 2025].reset_index(drop=True)
df = df.drop_duplicates(subset='time').sort_values('time').reset_index(drop=True)

dias_pregao = df['time'].dt.date.nunique()
meses_com_dados = df['time'].dt.to_period('M').nunique()
print(f"\nTotal: {len(df):,} candles M1")
print(f"Período: {df['time'].iloc[0]} até {df['time'].iloc[-1]}")
print(f"Meses: {meses_com_dados} | Dias de pregão: {dias_pregao}")

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
    if (i + 1) % 25000 == 0:
        print(f"  {i+1:,} candles...")

print(f"  {len(df):,} candles processados")

# ============================================================
# 3. COLETAR TRADES
# ============================================================
raw_trades = engine.get_all_trades()
if len(raw_trades) == 0:
    print("\nNenhum trade fechado em 2025.")
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
tdf['mes'] = tdf['fill_time'].dt.to_period('M')

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
print(f"PERFORMANCE ANUAL 2025 ({symbol})")
print(f"{'='*80}")
print(f"  Candles: {len(df):,} | Dias: {dias_pregao} | Meses: {meses_com_dados}")
print(f"  Total de trades: {total}")
print(f"  Wins: {wins} | Losses: {losses}")
print(f"  Win Rate: {wr:.1f}%")
print(f"  Profit Factor: {pf:.2f}")
print(f"  Lucro total: {total_pts:+,.2f} pontos")
print(f"  Lucro total: {total_r:+,.2f} R")
print(f"  Expectativa: {exp_r:.2f}R/trade")
print(f"  Trades/dia (média): {total/dias_pregao:.1f}")

# ============================================================
# 5. RESULTADO POR MÊS
# ============================================================
print(f"\n{'='*80}")
print("RESULTADO POR MÊS")
print(f"{'='*80}")

monthly = tdf.groupby('mes').agg(
    trades=('result', 'count'),
    wins=('result', lambda x: (x == 'WIN').sum()),
    losses=('result', lambda x: (x == 'LOSS').sum()),
    pnl_pts=('pnl_pts', 'sum'),
    pnl_r=('pnl_r', 'sum'),
).reset_index()
monthly['wr'] = monthly['wins'] / monthly['trades'] * 100
monthly['pf'] = monthly.apply(
    lambda r: tdf[(tdf['mes'] == r['mes']) & (tdf['result'] == 'WIN')]['pnl_pts'].sum() /
              abs(tdf[(tdf['mes'] == r['mes']) & (tdf['result'] == 'LOSS')]['pnl_pts'].sum())
    if abs(tdf[(tdf['mes'] == r['mes']) & (tdf['result'] == 'LOSS')]['pnl_pts'].sum()) > 0 else float('inf'),
    axis=1
)

print(f"{'Mês':<12} {'Trades':>7} {'Wins':>6} {'Loss':>6} {'WR%':>7} {'PF':>6} {'Lucro(pts)':>14} {'Lucro(R)':>10}")
print("-" * 80)
for _, row in monthly.iterrows():
    pf_str = f"{row['pf']:.2f}" if row['pf'] != float('inf') else "inf"
    print(f"{str(row['mes']):<12} {row['trades']:>7} {row['wins']:>6} {row['losses']:>6} "
          f"{row['wr']:>6.1f}% {pf_str:>6} {row['pnl_pts']:>+14,.2f} {row['pnl_r']:>+10,.2f}")
print("-" * 80)
pf_str = f"{pf:.2f}"
print(f"{'TOTAL 2025':<12} {total:>7} {wins:>6} {losses:>6} "
      f"{wr:>6.1f}% {pf_str:>6} {total_pts:>+14,.2f} {total_r:>+10,.2f}")

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

# Período do drawdown
dd_end_idx = tdf_sorted['drawdown_pts'].idxmin()
dd_start_idx = tdf_sorted.loc[:dd_end_idx, 'cumulative_pts'].idxmax()
dd_start_time = tdf_sorted.loc[dd_start_idx, 'fill_time']
dd_end_time = tdf_sorted.loc[dd_end_idx, 'fill_time']

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

meses_pos = len(monthly[monthly['pnl_pts'] > 0])
meses_neg = len(monthly[monthly['pnl_pts'] <= 0])
best_month = monthly.loc[monthly['pnl_pts'].idxmax()]
worst_month = monthly.loc[monthly['pnl_pts'].idxmin()]

daily = tdf.groupby('dia').agg(pnl_pts=('pnl_pts', 'sum')).reset_index()
dias_pos = len(daily[daily['pnl_pts'] > 0])
dias_neg = len(daily[daily['pnl_pts'] < 0])
dias_zero = len(daily[daily['pnl_pts'] == 0])

print(f"\n{'='*80}")
print("DRAWDOWN & ESTATÍSTICAS")
print(f"{'='*80}")
print(f"  Max Drawdown: {max_dd_pts:,.2f} pts | {max_dd_r:,.2f} R")
print(f"  Período DD: {dd_start_time.strftime('%d/%m/%Y')} ate {dd_end_time.strftime('%d/%m/%Y')}")
print(f"  Ratio Lucro/DD: {ratio:.2f}x")
print(f"  Max losses consecutivas: {max_consecutive_losses}")
print(f"  Max perda consecutiva: {max_consecutive_loss_pts:,.2f} pts")
print(f"  Melhor mês: {best_month['mes']} ({best_month['pnl_pts']:+,.0f} pts, {int(best_month['trades'])} trades)")
print(f"  Pior mês:   {worst_month['mes']} ({worst_month['pnl_pts']:+,.0f} pts, {int(worst_month['trades'])} trades)")
print(f"  Meses positivos: {meses_pos} | Negativos: {meses_neg}")
print(f"  Dias positivos: {dias_pos} | Negativos: {dias_neg} | Zero: {dias_zero}")

# ============================================================
# 7. SIMULAÇÃO FINANCEIRA
# ============================================================
valor_ponto = 0.20
print(f"\n{'='*80}")
print("SIMULAÇÃO FINANCEIRA ANUAL (WIN mini)")
print(f"{'='*80}")
print(f"  Valor do ponto: R$ {valor_ponto:.2f}")
for contratos in [1, 2, 5, 10, 20]:
    lucro = total_pts * valor_ponto * contratos
    lucro_mensal = lucro / meses_com_dados
    print(f"  {contratos:>2} contrato(s): R$ {lucro:>+12,.2f}/ano  |  R$ {lucro_mensal:>+10,.2f}/mês")

# ============================================================
# 8. EQUITY CURVE + GRÁFICOS
# ============================================================
output_dir = os.path.join(os.path.dirname(__file__), 'resultado_2025')
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
# Marcar cada 50 trades
for i in range(0, len(tdf_sorted), max(1, len(tdf_sorted)//30)):
    ax1.scatter(i, cum_pts[i], color=colors[i], s=15, zorder=3, edgecolors='white', linewidths=0.3)
ax1.axhline(y=0, color='#555555', linewidth=0.8, linestyle='--')

# Drawdown shading
dd_vals = tdf_sorted['drawdown_pts'].values
ax1.fill_between(x, cum_pts, tdf_sorted['peak_pts'].values, alpha=0.08, color='#EF5350')

ax1.set_title(f'Equity Curve - ANO 2025 ({symbol})\n'
              f'{total} trades | WR {wr:.1f}% | PF {pf:.2f} | {total_pts:+,.0f} pts ({total_r:+,.1f}R)',
              fontsize=15, color='white', fontweight='bold', pad=15)
ax1.set_ylabel('Lucro Acumulado (pts)', color='#aaaaaa', fontsize=11)
ax1.tick_params(colors='#aaaaaa')
for sp in ['top', 'right']: ax1.spines[sp].set_visible(False)
for sp in ['bottom', 'left']: ax1.spines[sp].set_color('#555555')
ax1.grid(True, alpha=0.1, color='#555555')
ax1.legend(fontsize=10, facecolor='#2a2a3d', edgecolor='#555555', labelcolor='white')

# --- P/L por Mês ---
ax2 = axes[1]
ax2.set_facecolor('#1e1e2f')
bar_colors = ['#66BB6A' if v >= 0 else '#EF5350' for v in monthly['pnl_pts']]
bar_x = range(len(monthly))
ax2.bar(bar_x, monthly['pnl_pts'], color=bar_colors, alpha=0.85, edgecolor='white', linewidth=0.3)
for i, (_, row) in enumerate(monthly.iterrows()):
    va = 'bottom' if row['pnl_pts'] >= 0 else 'top'
    offset = max(abs(monthly['pnl_pts'].max()) * 0.03, 20) * (1 if row['pnl_pts'] >= 0 else -1)
    ax2.text(i, row['pnl_pts'] + offset, f"{row['pnl_pts']:+,.0f}\n{row['wr']:.0f}%WR",
             ha='center', va=va, fontsize=8, color='#cccccc', fontweight='bold')
ax2.axhline(y=0, color='#555555', linewidth=0.8)
ax2.set_title('P/L por Mês', fontsize=13, color='white', fontweight='bold', pad=10)
ax2.set_ylabel('Pontos', color='#aaaaaa', fontsize=10)
tick_labels = [str(row['mes']) for _, row in monthly.iterrows()]
ax2.set_xticks(bar_x)
ax2.set_xticklabels(tick_labels, rotation=45, fontsize=9, color='#aaaaaa')
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
equity_path = os.path.join(output_dir, 'performance_2025.png')
plt.savefig(equity_path, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
plt.close()
print(f"\nGráfico salvo: {equity_path}")

# ============================================================
# RESUMO FINAL
# ============================================================
lucro_anual_1 = total_pts * valor_ponto
print(f"\n{'='*80}")
print("RESUMO ANUAL 2025")
print(f"{'='*80}")
print(f"  {total} trades | WR {wr:.1f}% | PF {pf:.2f}")
print(f"  Lucro: {total_pts:+,.0f} pts | {total_r:+,.1f}R")
print(f"  Max DD: {max_dd_pts:,.0f} pts | Ratio: {ratio:.1f}x")
print(f"  Meses +: {meses_pos}/{meses_com_dados}")
print(f"  Dias +: {dias_pos}/{dias_pregao}")
print(f"  R$ (1 mini): R$ {lucro_anual_1:+,.2f}/ano")

# Salvar CSV
csv_path = os.path.join(output_dir, 'trades_2025.csv')
tdf.to_csv(csv_path, index=False)
print(f"  CSV: {csv_path}")
