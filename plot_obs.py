"""
Plot OBs detectados pela engine sobre o gráfico de preço
Para comparar visualmente com o chart do MT5
"""
import sys
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Rectangle
from datetime import datetime, timedelta
from smc_engine_v3 import SMCEngineV3, SignalDirection

# ============================================================
# 1. PUXAR DADOS
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

# Warmup + periodo de análise
warmup_inicio = datetime(2026, 1, 1)
fim = datetime(2026, 2, 24)
rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, warmup_inicio, fim)
mt5.shutdown()

df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')
df = df.drop_duplicates(subset='time').sort_values('time').reset_index(drop=True)
print(f"Total: {len(df):,} candles M1")

# ============================================================
# 2. RODAR ENGINE
# ============================================================
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

all_obs = []
all_trades = []
all_signals = []

for i in range(len(df)):
    row = df.iloc[i]
    events = engine.add_candle({
        'open': float(row['open']),
        'high': float(row['high']),
        'low': float(row['low']),
        'close': float(row['close']),
        'volume': float(row.get('real_volume', row.get('tick_volume', 0)))
    })

    for ob in events['new_obs']:
        all_obs.append({
            'ob_id': ob.ob_id,
            'direction': ob.direction.name,
            'top': ob.top,
            'bottom': ob.bottom,
            'midline': ob.midline,
            'size': ob.ob_size,
            'size_atr': ob.ob_size_atr,
            'ob_candle_idx': ob.ob_candle_index,
            'ob_candle_time': df['time'].iloc[ob.ob_candle_index],
            'confirmation_idx': ob.confirmation_index,
            'confirmation_time': df['time'].iloc[ob.confirmation_index],
            'mitigated': ob.mitigated,
            'used': ob.used,
        })

    for sig in events['new_signals']:
        all_signals.append({
            'idx': i,
            'time': df['time'].iloc[i],
            **sig,
        })

trades = engine.get_all_trades()
for t in trades:
    t['fill_time'] = df['time'].iloc[t['filled_at']]
    t['close_time'] = df['time'].iloc[t['closed_at']]
    t['create_time'] = df['time'].iloc[t['created_at']]

# ============================================================
# 3. CRIAR GRÁFICO - Visão ampla (últimos dias) em 15min
# ============================================================

# Agregar para 15min para visualização
vis_start = datetime(2026, 2, 10)
vis_df = df[df['time'] >= vis_start].copy()

# Resample para 15min
vis_df = vis_df.set_index('time')
ohlc_15m = vis_df.resample('15min').agg({
    'open': 'first',
    'high': 'max',
    'low': 'min',
    'close': 'last',
}).dropna().reset_index()

print(f"\nGráfico: {len(ohlc_15m)} candles 15min desde {vis_start.date()}")

# Filtrar OBs do período visível que geraram sinais
vis_obs = [ob for ob in all_obs if ob['confirmation_time'] >= vis_start]
vis_signals = [s for s in all_signals if s['time'] >= vis_start]
vis_trades = [t for t in trades if t['fill_time'] >= vis_start]

print(f"OBs no período: {len(vis_obs)}")
print(f"Sinais no período: {len(vis_signals)}")
print(f"Trades no período: {len(vis_trades)}")

# ============================================================
# PLOT 1: Chart completo com TODOS os OBs
# ============================================================
fig, ax = plt.subplots(1, 1, figsize=(30, 16))
fig.patch.set_facecolor('#1a1a2e')
ax.set_facecolor('#1a1a2e')

# Plotar candles 15min
for i, row in ohlc_15m.iterrows():
    color = '#26a69a' if row['close'] >= row['open'] else '#ef5350'
    body_bottom = min(row['open'], row['close'])
    body_top = max(row['open'], row['close'])
    body_height = max(body_top - body_bottom, 1)

    # Wick
    ax.plot([i, i], [row['low'], row['high']], color=color, linewidth=0.5, alpha=0.7)
    # Body
    ax.add_patch(Rectangle((i - 0.35, body_bottom), 0.7, body_height,
                           facecolor=color, edgecolor=color, alpha=0.85))

# Plotar OBs como zonas
for ob in vis_obs:
    # Encontrar posição x correspondente
    conf_time = ob['confirmation_time']
    # Encontrar o candle 15m mais próximo
    x_start = None
    for j, row in ohlc_15m.iterrows():
        if row['time'] >= conf_time:
            x_start = j
            break

    if x_start is None:
        continue

    # Verificar se gerou sinal
    generated_signal = ob['used']

    # Cor: azul para bullish, vermelho para bearish
    if ob['direction'] == 'BULLISH':
        color = '#2196F3' if generated_signal else '#2196F3'
        alpha = 0.25 if generated_signal else 0.08
    else:
        color = '#FF5722' if generated_signal else '#FF5722'
        alpha = 0.25 if generated_signal else 0.08

    # Desenhar zona do OB
    width = min(30, len(ohlc_15m) - x_start)
    rect = Rectangle((x_start, ob['bottom']), width, ob['top'] - ob['bottom'],
                     facecolor=color, edgecolor=color, alpha=alpha, linewidth=0.5)
    ax.add_patch(rect)

    # Label só para OBs que geraram sinal
    if generated_signal:
        label = f"OB#{ob['ob_id']}"
        ax.text(x_start + 0.5, ob['top'] + 20, label, fontsize=6, color=color,
                fontweight='bold', alpha=0.8)

# Plotar trades
for t in vis_trades:
    fill_time = t['fill_time']
    close_time = t['close_time']

    # Encontrar posição x
    x_fill = None
    x_close = None
    for j, row in ohlc_15m.iterrows():
        if x_fill is None and row['time'] >= fill_time:
            x_fill = j
        if x_close is None and row['time'] >= close_time:
            x_close = j

    if x_fill is None:
        continue
    if x_close is None:
        x_close = x_fill + 1

    result = 'WIN' if t['status'] == 'closed_tp' else 'LOSS'

    # Entry marker
    marker_color = '#66BB6A' if result == 'WIN' else '#EF5350'
    ax.scatter(x_fill, t['entry_price'], color=marker_color, s=100, zorder=5,
              marker='v' if t['direction'] == 'BEARISH' else '^',
              edgecolors='white', linewidths=0.5)

    # SL/TP lines
    ax.plot([x_fill - 1, x_fill + 3], [t['stop_loss'], t['stop_loss']],
            color='#EF5350', linewidth=0.8, linestyle='--', alpha=0.6)
    ax.plot([x_fill - 1, x_fill + 3], [t['take_profit'], t['take_profit']],
            color='#66BB6A', linewidth=0.8, linestyle='--', alpha=0.6)

    # Label
    ax.text(x_fill + 1, t['entry_price'] + 30,
            f"{t['order_id']}\n{result} {t['profit_loss']:+.0f}",
            fontsize=7, color=marker_color, fontweight='bold')

# Formatação
ax.set_title(f'SMC Engine V3 - OBs Detectados ({symbol}) 15min\n'
             f'Azul=Bullish OB | Vermelho=Bearish OB | Forte=gerou sinal | Fraco=filtrado\n'
             f'Total OBs: {len(vis_obs)} | Sinais: {len(vis_signals)} | Trades: {len(vis_trades)}',
             fontsize=14, color='white', fontweight='bold')
ax.set_ylabel('Preço', color='#aaaaaa')

# X-axis com datas
tick_positions = list(range(0, len(ohlc_15m), max(1, len(ohlc_15m)//20)))
tick_labels = [ohlc_15m.iloc[i]['time'].strftime('%d/%m\n%H:%M') for i in tick_positions]
ax.set_xticks(tick_positions)
ax.set_xticklabels(tick_labels, fontsize=8, color='#aaaaaa')
ax.tick_params(colors='#aaaaaa')

for sp in ['top', 'right']:
    ax.spines[sp].set_visible(False)
for sp in ['bottom', 'left']:
    ax.spines[sp].set_color('#555555')
ax.grid(True, alpha=0.1, color='#555555')

# Legend
bull_patch = mpatches.Patch(color='#2196F3', alpha=0.3, label='Bullish OB')
bear_patch = mpatches.Patch(color='#FF5722', alpha=0.3, label='Bearish OB')
win_marker = plt.Line2D([0], [0], marker='^', color='w', markerfacecolor='#66BB6A', markersize=10, label='WIN')
loss_marker = plt.Line2D([0], [0], marker='v', color='w', markerfacecolor='#EF5350', markersize=10, label='LOSS')
ax.legend(handles=[bull_patch, bear_patch, win_marker, loss_marker],
         loc='upper left', fontsize=10, facecolor='#2a2a3d', edgecolor='#555555', labelcolor='white')

plt.tight_layout()
path1 = 'resultado_2026/obs_chart_15m.png'
plt.savefig(path1, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
plt.close()
print(f"\nSalvo: {path1}")

# ============================================================
# PLOT 2: Zoom no dia 23/02 em M1
# ============================================================
zoom_start = datetime(2026, 2, 23, 9, 0)
zoom_end = datetime(2026, 2, 23, 18, 35)
zoom_df = df[(df['time'] >= zoom_start) & (df['time'] <= zoom_end)].reset_index(drop=True)

zoom_obs = [ob for ob in all_obs
            if ob['confirmation_time'] >= zoom_start and ob['confirmation_time'] <= zoom_end]
zoom_signals = [s for s in all_signals
                if s['time'] >= zoom_start and s['time'] <= zoom_end]
zoom_trades = [t for t in trades
               if t['fill_time'] >= zoom_start and t['fill_time'] <= zoom_end]

print(f"\nZoom 23/02: {len(zoom_df)} candles M1")
print(f"OBs: {len(zoom_obs)} | Sinais: {len(zoom_signals)} | Trades: {len(zoom_trades)}")

fig2, ax2 = plt.subplots(1, 1, figsize=(36, 16))
fig2.patch.set_facecolor('#1a1a2e')
ax2.set_facecolor('#1a1a2e')

# Candles M1
for i, row in zoom_df.iterrows():
    color = '#26a69a' if row['close'] >= row['open'] else '#ef5350'
    body_bottom = min(row['open'], row['close'])
    body_top = max(row['open'], row['close'])
    body_height = max(body_top - body_bottom, 1)

    ax2.plot([i, i], [row['low'], row['high']], color=color, linewidth=0.5, alpha=0.7)
    ax2.add_patch(Rectangle((i - 0.35, body_bottom), 0.7, body_height,
                            facecolor=color, edgecolor=color, alpha=0.85))

# OBs do dia
for ob in zoom_obs:
    conf_time = ob['confirmation_time']
    x_start = None
    for j, row in zoom_df.iterrows():
        if row['time'] >= conf_time:
            x_start = j
            break

    if x_start is None:
        continue

    generated_signal = ob['used']

    if ob['direction'] == 'BULLISH':
        color = '#2196F3'
        alpha = 0.3 if generated_signal else 0.08
        edge_alpha = 0.8 if generated_signal else 0.2
    else:
        color = '#FF5722'
        alpha = 0.3 if generated_signal else 0.08
        edge_alpha = 0.8 if generated_signal else 0.2

    width = min(60, len(zoom_df) - x_start)
    rect = Rectangle((x_start, ob['bottom']), width, ob['top'] - ob['bottom'],
                     facecolor=color, edgecolor=color, alpha=alpha, linewidth=0.5)
    ax2.add_patch(rect)

    # Linha na midline
    if generated_signal:
        ax2.plot([x_start, x_start + width], [ob['midline'], ob['midline']],
                color=color, linewidth=0.5, linestyle=':', alpha=0.5)

    # Label
    dist = ob['confirmation_idx'] - ob['ob_candle_idx']
    label = f"OB#{ob['ob_id']} ({ob['direction'][:4]}) sz={ob['size']:.0f} dist={dist}"
    y_pos = ob['top'] + 15 if ob['direction'] == 'BULLISH' else ob['bottom'] - 25
    ax2.text(x_start + 1, y_pos, label, fontsize=5.5, color=color,
            fontweight='bold' if generated_signal else 'normal',
            alpha=0.9 if generated_signal else 0.4)

# Trades do dia
for t in zoom_trades:
    fill_time = t['fill_time']
    close_time = t['close_time']

    x_fill = None
    x_close = None
    for j, row in zoom_df.iterrows():
        if x_fill is None and row['time'] >= fill_time:
            x_fill = j
        if x_close is None and row['time'] >= close_time:
            x_close = j

    if x_fill is None:
        continue
    if x_close is None:
        x_close = x_fill + 1

    result = 'WIN' if t['status'] == 'closed_tp' else 'LOSS'
    marker_color = '#66BB6A' if result == 'WIN' else '#EF5350'

    # Entry
    ax2.scatter(x_fill, t['entry_price'], color=marker_color, s=120, zorder=5,
              marker='v' if t['direction'] == 'BEARISH' else '^',
              edgecolors='white', linewidths=0.8)

    # SL/TP
    ax2.plot([x_fill - 3, x_fill + 8], [t['stop_loss'], t['stop_loss']],
            color='#EF5350', linewidth=1, linestyle='--', alpha=0.7)
    ax2.plot([x_fill - 3, x_fill + 8], [t['take_profit'], t['take_profit']],
            color='#66BB6A', linewidth=1, linestyle='--', alpha=0.7)

    # Entry line
    ax2.plot([x_fill - 3, x_fill + 8], [t['entry_price'], t['entry_price']],
            color='#FFC107', linewidth=0.8, linestyle='-', alpha=0.5)

    # Label
    ax2.text(x_fill + 2, t['entry_price'] + 40,
            f"{t['order_id']}\n{result} {t['profit_loss']:+.0f}pts\nSL={t['stop_loss']:.0f} TP={t['take_profit']:.0f}",
            fontsize=7, color=marker_color, fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='#1a1a2e', edgecolor=marker_color, alpha=0.8))

# Swing highs/lows do dia
for sh in engine.swing_highs:
    conf_idx, cand_idx, level = sh
    if cand_idx < len(df) and df['time'].iloc[cand_idx] >= zoom_start and df['time'].iloc[cand_idx] <= zoom_end:
        for j, row in zoom_df.iterrows():
            if row['time'] == df['time'].iloc[cand_idx]:
                ax2.scatter(j, level + 20, color='#FFD700', s=30, marker='v', zorder=4, alpha=0.6)
                break

for sl in engine.swing_lows:
    conf_idx, cand_idx, level = sl
    if cand_idx < len(df) and df['time'].iloc[cand_idx] >= zoom_start and df['time'].iloc[cand_idx] <= zoom_end:
        for j, row in zoom_df.iterrows():
            if row['time'] == df['time'].iloc[cand_idx]:
                ax2.scatter(j, level - 20, color='#FFD700', s=30, marker='^', zorder=4, alpha=0.6)
                break

# Formatação
ax2.set_title(f'SMC Engine V3 - Zoom 23/02/2026 ({symbol}) M1\n'
              f'OBs: {len(zoom_obs)} | Sinais: {len(zoom_signals)} | Trades: {len(zoom_trades)}\n'
              f'Triângulos amarelos = Swing Points | Zonas = Order Blocks',
              fontsize=14, color='white', fontweight='bold')
ax2.set_ylabel('Preço', color='#aaaaaa')

tick_positions2 = list(range(0, len(zoom_df), max(1, len(zoom_df)//30)))
tick_labels2 = [zoom_df.iloc[i]['time'].strftime('%H:%M') for i in tick_positions2]
ax2.set_xticks(tick_positions2)
ax2.set_xticklabels(tick_labels2, fontsize=7, color='#aaaaaa', rotation=45)
ax2.tick_params(colors='#aaaaaa')

for sp in ['top', 'right']:
    ax2.spines[sp].set_visible(False)
for sp in ['bottom', 'left']:
    ax2.spines[sp].set_color('#555555')
ax2.grid(True, alpha=0.1, color='#555555')

plt.tight_layout()
path2 = 'resultado_2026/obs_chart_23feb_m1.png'
plt.savefig(path2, dpi=150, bbox_inches='tight', facecolor=fig2.get_facecolor())
plt.close()
print(f"Salvo: {path2}")

# ============================================================
# RESUMO dos OBs do dia 23/02
# ============================================================
print(f"\n{'='*80}")
print(f"OBs DETECTADOS EM 23/02/2026")
print(f"{'='*80}")
for ob in zoom_obs:
    dist = ob['confirmation_idx'] - ob['ob_candle_idx']
    sig = "-> SINAL" if ob['used'] else "  (filtrado)"
    print(f"  OB#{ob['ob_id']:>4d} {ob['direction']:>8s} [{ob['bottom']:>10.2f} - {ob['top']:>10.2f}] "
          f"sz={ob['size']:>6.0f} ({ob['size_atr']:.2f}ATR) dist={dist:>3d} "
          f"conf={ob['confirmation_time'].strftime('%H:%M')} {sig}")
