"""
Backtest do Mês - Dados do MetaTrader 5
========================================
Puxa candles M1 do mês atual via MT5 e roda o SMCEngineV3.
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
from smc_engine_v3 import SMCEngineV3, OrderStatus, SignalDirection

# ============================================================
# 1. CONECTAR AO MT5
# ============================================================
print("Conectando ao MetaTrader 5...")
if not mt5.initialize():
    print(f"ERRO: Falha ao inicializar MT5: {mt5.last_error()}")
    sys.exit(1)

info = mt5.terminal_info()
print(f"MT5 conectado: {info.name} (Build {info.build})")

# Detectar símbolo WIN
symbols_to_try = ["WIN$N", "WING26", "WINH26", "WINJ26", "WIN$", "WINM25"]
symbol = None
for s in symbols_to_try:
    sym_info = mt5.symbol_info(s)
    if sym_info is not None:
        symbol = s
        if not sym_info.visible:
            mt5.symbol_select(s, True)
        break
if symbol is None:
    all_symbols = mt5.symbols_get()
    win_symbols = [s.name for s in all_symbols if s.name.startswith("WIN")]
    if win_symbols:
        symbol = win_symbols[0]
        mt5.symbol_select(symbol, True)
    else:
        print("ERRO: Nenhum símbolo WIN encontrado!")
        mt5.shutdown()
        sys.exit(1)

print(f"Símbolo: {symbol}")

# ============================================================
# 2. PUXAR DADOS DO MÊS (M1)
# ============================================================
agora = datetime.now()
inicio_mes = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
fim = agora + timedelta(hours=1)

print(f"\nBuscando candles M1 de {inicio_mes.strftime('%d/%m/%Y')} até {agora.strftime('%d/%m/%Y')}...")
rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, inicio_mes, fim)

if rates is None or len(rates) == 0:
    print(f"ERRO: Nenhum candle encontrado para o mês.")
    print(f"Último erro MT5: {mt5.last_error()}")
    mt5.shutdown()
    sys.exit(1)

df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')

print(f"Total: {len(df):,} candles de 1 minuto")
print(f"Período: {df['time'].iloc[0]} até {df['time'].iloc[-1]}")
print(f"Abertura mês: {df['open'].iloc[0]:,.0f} | Último: {df['close'].iloc[-1]:,.0f}")

# Dias de pregão
dias_pregao = df['time'].dt.date.nunique()
print(f"Dias de pregão: {dias_pregao}")

mt5.shutdown()

# ============================================================
# 3. EXECUTAR ENGINE V3
# ============================================================
print("\nExecutando SMC Engine V3...")
print("  Config: RR 3:1 | max_pending=150 | sem filtros vol/size")

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
        print(f"  Processados {i+1:,} candles...")

print(f"  Processados {len(df):,} candles (completo)")

# ============================================================
# 4. COLETAR TRADES
# ============================================================
raw_trades = engine.get_all_trades()

if len(raw_trades) == 0:
    print("\nNenhum trade fechado no mês.")
    sys.exit(0)

# Construir DataFrame
trade_data = []
for t in raw_trades:
    fill_idx = t['filled_at']
    close_idx = t['closed_at']
    fill_time = df['time'].iloc[fill_idx] if fill_idx < len(df) else None
    close_time = df['time'].iloc[close_idx] if close_idx < len(df) else None

    trade_data.append({
        'id': t['order_id'],
        'direction': t['direction'],
        'fill_time': fill_time,
        'close_time': close_time,
        'fill_index': fill_idx,
        'close_index': close_idx,
        'created_at': t['created_at'],
        'entry': t['entry_price'],
        'tp': t['take_profit'],
        'sl': t['stop_loss'],
        'result': 'WIN' if t['status'] == 'closed_tp' else 'LOSS',
        'pnl_pts': t['profit_loss'],
        'pnl_r': t['profit_loss_r'],
        'ob_top': t['ob_top'],
        'ob_bottom': t['ob_bottom'],
        'ob_midline': t['ob_midline'],
        'confidence': t['confidence'],
        'patterns': str(t['patterns']),
        'wait_candles': t['wait_candles'],
        'duration_candles': t['duration_candles'],
    })

tdf = pd.DataFrame(trade_data)
tdf['fill_time'] = pd.to_datetime(tdf['fill_time'])
tdf['close_time'] = pd.to_datetime(tdf['close_time'])
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
# 5. RESULTADO GERAL
# ============================================================
mes_str = inicio_mes.strftime('%B/%Y').upper()
print(f"\n{'='*80}")
print(f"RESULTADO DO MÊS - {mes_str} ({symbol})")
print(f"{'='*80}")
print(f"  Candles processados: {len(df):,}")
print(f"  Dias de pregão: {dias_pregao}")
print(f"  Total de trades: {total}")
print(f"  Wins: {wins} | Losses: {losses}")
print(f"  Win Rate: {wr:.1f}%")
print(f"  Profit Factor: {pf:.2f}")
print(f"  Lucro total: {total_pts:+,.2f} pontos")
print(f"  Lucro total: {total_r:+,.2f} R")
print(f"  Expectativa: {exp_r:.2f}R/trade")
print(f"  Média espera: {tdf['wait_candles'].mean():.1f} candles")
print(f"  Média duração: {tdf['duration_candles'].mean():.1f} candles")

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
print("-" * 70)
for _, row in daily.iterrows():
    dia_str = row['dia'].strftime('%d/%m/%Y')
    print(f"{dia_str:<14} {row['trades']:>7} {row['wins']:>6} {row['losses']:>6} "
          f"{row['wr']:>6.1f}% {row['pnl_pts']:>+14,.2f} {row['pnl_r']:>+10,.2f}")

print("-" * 70)
print(f"{'TOTAL':<14} {total:>7} {wins:>6} {losses:>6} "
      f"{wr:>6.1f}% {total_pts:>+14,.2f} {total_r:>+10,.2f}")

# ============================================================
# 7. DRAWDOWN
# ============================================================
print(f"\n{'='*80}")
print("DRAWDOWN ANALYSIS")
print(f"{'='*80}")

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

# Losses consecutivas
consecutive_losses = 0
max_consecutive_losses = 0
consecutive_loss_pts = 0
max_consecutive_loss_pts = 0
for _, row in tdf_sorted.iterrows():
    if row['result'] == 'LOSS':
        consecutive_losses += 1
        consecutive_loss_pts += row['pnl_pts']
        max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
        max_consecutive_loss_pts = min(max_consecutive_loss_pts, consecutive_loss_pts)
    else:
        consecutive_losses = 0
        consecutive_loss_pts = 0

print(f"  Max Drawdown: {max_dd_pts:,.2f} pts | {max_dd_r:,.2f} R")
print(f"  Ratio Lucro/DD: {ratio:.2f}x")
print(f"  Max losses consecutivas: {max_consecutive_losses}")
print(f"  Max perda consecutiva: {max_consecutive_loss_pts:,.2f} pts")

# Melhor e pior dia
best_day = daily.loc[daily['pnl_pts'].idxmax()]
worst_day = daily.loc[daily['pnl_pts'].idxmin()]
print(f"  Melhor dia: {best_day['dia'].strftime('%d/%m')} ({best_day['pnl_pts']:+,.0f} pts, {int(best_day['trades'])} trades)")
print(f"  Pior dia:   {worst_day['dia'].strftime('%d/%m')} ({worst_day['pnl_pts']:+,.0f} pts, {int(worst_day['trades'])} trades)")

# Dias positivos vs negativos
dias_pos = len(daily[daily['pnl_pts'] > 0])
dias_neg = len(daily[daily['pnl_pts'] < 0])
dias_zero = len(daily[daily['pnl_pts'] == 0])
print(f"  Dias positivos: {dias_pos} | Negativos: {dias_neg} | Zero: {dias_zero}")

# ============================================================
# 8. LISTA DE TRADES
# ============================================================
print(f"\n{'='*80}")
print("TODOS OS TRADES")
print(f"{'='*80}")
print(f"{'#':>3} {'Dia':>10} {'Hora':>5} {'Dir':>7} {'Entry':>10} {'SL':>10} {'TP':>10} "
      f"{'Result':>6} {'P/L pts':>10} {'P/L R':>7} {'Conf':>5}")
print("-" * 100)
for idx, t in tdf_sorted.iterrows():
    dia_str = t['fill_time'].strftime('%d/%m')
    hora_str = t['fill_time'].strftime('%H:%M')
    print(f"{idx+1:>3} {dia_str:>10} {hora_str:>5} {t['direction']:>7} {t['entry']:>10,.0f} "
          f"{t['sl']:>10,.0f} {t['tp']:>10,.0f} {t['result']:>6} "
          f"{t['pnl_pts']:>+10,.0f} {t['pnl_r']:>+7.1f} {t['confidence']:>4.0f}%")

# ============================================================
# 9. CURVA DE EQUITY
# ============================================================
output_dir = os.path.join(os.path.dirname(__file__), 'trades_mes')
os.makedirs(output_dir, exist_ok=True)

fig, axes = plt.subplots(2, 1, figsize=(16, 12), gridspec_kw={'height_ratios': [2, 1]})
fig.patch.set_facecolor('#1e1e2f')

# --- Equity Curve ---
ax1 = axes[0]
ax1.set_facecolor('#1e1e2f')

x = range(len(tdf_sorted))
cum_pts = tdf_sorted['cumulative_pts'].values
colors = ['#66BB6A' if r == 'WIN' else '#EF5350' for r in tdf_sorted['result']]

ax1.fill_between(x, 0, cum_pts, alpha=0.15, color='#42A5F5')
ax1.plot(x, cum_pts, color='#42A5F5', linewidth=2, label='Equity (pts)')

for i in range(len(tdf_sorted)):
    ax1.scatter(i, cum_pts[i], color=colors[i], s=40, zorder=3, edgecolors='white', linewidths=0.5)

ax1.axhline(y=0, color='#555555', linewidth=0.8, linestyle='--')
ax1.set_title(f'Equity Curve - {mes_str} ({symbol})\n'
              f'{total} trades | WR {wr:.1f}% | PF {pf:.2f} | {total_pts:+,.0f} pts ({total_r:+,.1f}R)',
              fontsize=14, color='white', fontweight='bold', pad=15)
ax1.set_ylabel('Lucro Acumulado (pts)', color='#aaaaaa', fontsize=11)
ax1.tick_params(colors='#aaaaaa')
ax1.spines['top'].set_visible(False)
ax1.spines['right'].set_visible(False)
ax1.spines['bottom'].set_color('#555555')
ax1.spines['left'].set_color('#555555')
ax1.grid(True, alpha=0.1, color='#555555')
ax1.legend(fontsize=10, facecolor='#2a2a3d', edgecolor='#555555', labelcolor='white')

# --- P/L por dia (barras) ---
ax2 = axes[1]
ax2.set_facecolor('#1e1e2f')

bar_colors = ['#66BB6A' if v >= 0 else '#EF5350' for v in daily['pnl_pts']]
bar_x = range(len(daily))
ax2.bar(bar_x, daily['pnl_pts'], color=bar_colors, alpha=0.85, edgecolor='white', linewidth=0.3)

for i, (_, row) in enumerate(daily.iterrows()):
    va = 'bottom' if row['pnl_pts'] >= 0 else 'top'
    offset = 5 if row['pnl_pts'] >= 0 else -5
    ax2.text(i, row['pnl_pts'] + offset, f"{row['pnl_pts']:+,.0f}",
             ha='center', va=va, fontsize=7, color='#cccccc', fontweight='bold')

ax2.axhline(y=0, color='#555555', linewidth=0.8)
ax2.set_title('P/L por Dia', fontsize=12, color='white', fontweight='bold', pad=10)
ax2.set_ylabel('Pontos', color='#aaaaaa', fontsize=10)
ax2.set_xlabel('Dia', color='#aaaaaa', fontsize=10)
tick_labels = [row['dia'].strftime('%d/%m') for _, row in daily.iterrows()]
ax2.set_xticks(bar_x)
ax2.set_xticklabels(tick_labels, rotation=45, fontsize=8, color='#aaaaaa')
ax2.tick_params(colors='#aaaaaa')
ax2.spines['top'].set_visible(False)
ax2.spines['right'].set_visible(False)
ax2.spines['bottom'].set_color('#555555')
ax2.spines['left'].set_color('#555555')
ax2.grid(True, alpha=0.1, color='#555555', axis='y')

plt.tight_layout()
equity_path = os.path.join(output_dir, 'equity_curve_mes.png')
plt.savefig(equity_path, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
plt.close()
print(f"\nEquity curve salva: {equity_path}")

# ============================================================
# 10. GERAR IMAGENS DOS TRADES
# ============================================================
def plot_candlestick(ax, df_slice):
    for j in range(len(df_slice)):
        row = df_slice.iloc[j]
        o, h, l, c = row['open'], row['high'], row['low'], row['close']
        color = '#26a69a' if c >= o else '#ef5350'
        edge = '#1b7a6e' if c >= o else '#c62828'
        ax.plot([j, j], [l, h], color='#555555', linewidth=0.6, zorder=1)
        body_bottom = min(o, c)
        body_height = max(abs(c - o), 0.5)
        rect = Rectangle((j - 0.35, body_bottom), 0.7, body_height,
                          facecolor=color, edgecolor=edge, linewidth=0.5, zorder=2)
        ax.add_patch(rect)

print(f"\nGerando imagens de {len(raw_trades)} trades...")

for idx, t in enumerate(raw_trades):
    created_at = t['created_at']
    filled_at = t['filled_at']
    closed_at = t['closed_at']
    direction = t['direction']
    entry = t['entry_price']
    sl = t['stop_loss']
    tp = t['take_profit']
    ob_top = t['ob_top']
    ob_bottom = t['ob_bottom']
    midline = t['ob_midline']
    status = t['status']
    pnl = t['profit_loss']
    pnl_r = t['profit_loss_r']
    is_win = status == 'closed_tp'

    start = max(0, created_at - 15)
    end = min(len(df), closed_at + 8 + 1)
    df_slice = df.iloc[start:end].reset_index(drop=True)

    ob_rel = created_at - start
    fill_rel = filled_at - start
    close_rel = closed_at - start

    fig, ax = plt.subplots(figsize=(16, 9))
    fig.patch.set_facecolor('#1e1e2f')
    ax.set_facecolor('#1e1e2f')

    plot_candlestick(ax, df_slice)

    # Order Block
    ob_width = close_rel - ob_rel + 3
    ob_color = '#2196F3' if direction == 'BULLISH' else '#F44336'
    ob_rect = Rectangle((ob_rel - 0.5, ob_bottom), ob_width, ob_top - ob_bottom,
                         facecolor=ob_color, alpha=0.12, edgecolor=ob_color,
                         linewidth=1.5, linestyle='--', zorder=0)
    ax.add_patch(ob_rect)

    line_start = ob_rel - 1
    line_end = close_rel + 2
    ax.hlines(y=entry, xmin=line_start, xmax=line_end, color='#42A5F5', linewidth=1.8, linestyle='-', label=f'Entry: {entry:,.0f}', zorder=3)
    ax.hlines(y=sl, xmin=line_start, xmax=line_end, color='#EF5350', linewidth=1.5, linestyle='--', label=f'SL: {sl:,.0f}', zorder=3)
    ax.hlines(y=tp, xmin=line_start, xmax=line_end, color='#66BB6A', linewidth=1.5, linestyle='--', label=f'TP: {tp:,.0f}', zorder=3)

    ax.annotate('OB', xy=(ob_rel, ob_top), fontsize=9, ha='center', color='#BB86FC', fontweight='bold',
                xytext=(ob_rel, ob_top + (ob_top - ob_bottom) * 0.8),
                arrowprops=dict(arrowstyle='->', color='#BB86FC', lw=1.5))

    marker = '^' if direction == 'BULLISH' else 'v'
    ax.scatter([fill_rel], [entry], color='#42A5F5', s=120, zorder=5, marker=marker, edgecolors='white', linewidths=0.8)
    ax.annotate('FILL', xy=(fill_rel, entry), xytext=(fill_rel + 1.2, entry), fontsize=8, color='#42A5F5', fontweight='bold', va='center')

    close_color = '#66BB6A' if is_win else '#EF5350'
    close_label = 'TP HIT' if is_win else 'SL HIT'
    exit_price = tp if is_win else sl
    ax.scatter([close_rel], [exit_price], color=close_color, s=150, zorder=5, marker='*', edgecolors='white', linewidths=0.8)
    ax.annotate(close_label, xy=(close_rel, exit_price), xytext=(close_rel + 1.2, exit_price), fontsize=8, color=close_color, fontweight='bold', va='center')

    fill_time = df['time'].iloc[filled_at].strftime('%d/%m %H:%M') if filled_at < len(df) else '?'
    close_time_str = df['time'].iloc[closed_at].strftime('%H:%M') if closed_at < len(df) else '?'
    dir_str = "LONG" if direction == 'BULLISH' else "SHORT"
    result_str = "WIN" if is_win else "LOSS"
    result_color = '#66BB6A' if is_win else '#EF5350'

    ax.set_title(f'Trade #{idx+1}  |  {dir_str}  |  {result_str}  |  {pnl:+,.0f} pts ({pnl_r:+.1f}R)\n'
                 f'Entry: {entry:,.0f}  |  SL: {sl:,.0f}  |  TP: {tp:,.0f}  |  Fill: {fill_time}  |  Close: {close_time_str}',
                 fontsize=13, color='white', fontweight='bold', pad=15)

    ax.text(0.98, 0.95, f"  {result_str} {pnl:+,.0f} pts  ", transform=ax.transAxes,
            fontsize=14, fontweight='bold', color='white', ha='right', va='top',
            bbox=dict(boxstyle='round,pad=0.4', facecolor=result_color, alpha=0.85))

    ax.set_xlabel('Candles', color='#aaaaaa', fontsize=10)
    ax.set_ylabel('Preço', color='#aaaaaa', fontsize=10)
    ax.tick_params(colors='#aaaaaa')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_color('#555555')
    ax.spines['left'].set_color('#555555')
    ax.grid(True, alpha=0.1, color='#555555')

    n_ticks = min(10, len(df_slice))
    tick_step = max(1, len(df_slice) // n_ticks)
    tick_positions = list(range(0, len(df_slice), tick_step))
    tick_labels_list = [df_slice['time'].iloc[p].strftime('%H:%M') for p in tick_positions]
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels_list, rotation=45, fontsize=8, color='#aaaaaa')

    all_prices = [ob_top, ob_bottom, sl, tp, entry]
    y_min = min(df_slice['low'].min(), min(all_prices))
    y_max = max(df_slice['high'].max(), max(all_prices))
    margin = (y_max - y_min) * 0.08
    ax.set_ylim(y_min - margin, y_max + margin)
    ax.set_xlim(-1, len(df_slice) + 1)
    ax.legend(loc='upper left', fontsize=9, facecolor='#2a2a3d', edgecolor='#555555', labelcolor='white')

    filepath = os.path.join(output_dir, f'trade_{idx+1:02d}_{dir_str}_{result_str}.png')
    plt.tight_layout()
    plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.close()

    if (idx + 1) % 10 == 0 or idx == len(raw_trades) - 1:
        print(f"  [{idx+1}/{len(raw_trades)}] imagens geradas...")

# ============================================================
# RESUMO FINAL
# ============================================================
print(f"\n{'='*80}")
print("RESUMO FINAL")
print(f"{'='*80}")
print(f"  Mês: {mes_str}")
print(f"  Símbolo: {symbol}")
print(f"  Total trades: {total}")
print(f"  Win Rate: {wr:.1f}%")
print(f"  Profit Factor: {pf:.2f}")
print(f"  Lucro: {total_pts:+,.2f} pts | {total_r:+,.2f} R")
print(f"  Expectativa: {exp_r:.2f}R/trade")
print(f"  Max Drawdown: {max_dd_pts:,.2f} pts")
print(f"  Ratio Lucro/DD: {ratio:.2f}x")
print(f"  Dias positivos: {dias_pos}/{len(daily)}")
print(f"\n  Imagens salvas em: {output_dir}")
print(f"  Total de imagens: {len(raw_trades) + 1} (trades + equity curve)")
