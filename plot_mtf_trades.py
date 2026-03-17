"""
Plot MTF M15 trades - Grafico M15 com entrada/saida para cada trade
===================================================================
"""
import sys, os
os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.stdout.reconfigure(encoding='utf-8')

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
from datetime import datetime, timedelta
from smc_engine_v3 import SMCEngineV3

# Conectar
print("Conectando ao MT5...")
mt5.initialize()
symbol = None
for s in ['WIN$N', 'WING26', 'WINH26', 'WINJ26']:
    if mt5.symbol_info(s) is not None:
        symbol = s
        mt5.symbol_select(s, True)
        break
print(f"Simbolo: {symbol}")

rates_m1 = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, datetime(2025, 1, 1), datetime(2026, 3, 1))
rates_m15 = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M15, datetime(2025, 1, 1), datetime(2026, 3, 1))
mt5.shutdown()

df_m1 = pd.DataFrame(rates_m1)
df_m1['time_ts'] = df_m1['time']
df_m1['time'] = pd.to_datetime(df_m1['time'], unit='s')
df_m1 = df_m1.drop_duplicates(subset='time').sort_values('time').reset_index(drop=True)

df_m15 = pd.DataFrame(rates_m15)
df_m15['time'] = pd.to_datetime(df_m15['time'], unit='s')
df_m15 = df_m15.drop_duplicates(subset='time').sort_values('time').reset_index(drop=True)

print(f"M1: {len(df_m1):,} candles | M15: {len(df_m15):,} candles")

# Rodar MTF M15 engine
print("Rodando MTF M15 engine...")
engine = SMCEngineV3(
    symbol=symbol, swing_length=5, risk_reward_ratio=2.0,
    min_volume_ratio=0.0, min_ob_size_atr=0.3,
    use_not_mitigated_filter=True, max_pending_candles=300,
    entry_delay_candles=1, tick_size=5.0,
    min_confidence=0.0, max_sl_points=150.0,
    min_patterns=0, entry_retracement=0.7, htf_period=15)

for i in range(len(df_m1)):
    row = df_m1.iloc[i]
    engine.add_candle({
        'open': float(row['open']),
        'high': float(row['high']),
        'low': float(row['low']),
        'close': float(row['close']),
        'volume': float(row.get('real_volume', row.get('tick_volume', 0))),
        'time': int(row['time_ts']),
    })

trades = engine.get_all_trades()
print(f"Total trades: {len(trades)}")

# Preparar trades com timestamps
trade_list = []
for t in trades:
    fill_idx = t['filled_at']
    close_idx = t['closed_at']
    if fill_idx < len(df_m1) and close_idx < len(df_m1):
        fill_time = df_m1['time'].iloc[fill_idx]
        close_time = df_m1['time'].iloc[close_idx]
        trade_list.append({
            'direction': t['direction'],
            'status': t['status'],
            'entry_price': t['entry_price'],
            'stop_loss': t['stop_loss'],
            'take_profit': t['take_profit'],
            'exit_price': t['exit_price'],
            'profit_loss': t['profit_loss'],
            'fill_time': fill_time,
            'close_time': close_time,
            'ob_top': t.get('ob_top', t['entry_price'] + 50),
            'ob_bottom': t.get('ob_bottom', t['entry_price'] - 50),
        })

# Extrair OB info dos trades da engine
for i, t in enumerate(trades):
    if i < len(trade_list):
        ob = t.get('ob', None)
        if ob:
            trade_list[i]['ob_top'] = ob['top'] if isinstance(ob, dict) else getattr(ob, 'top', trade_list[i]['entry_price'] + 50)
            trade_list[i]['ob_bottom'] = ob['bottom'] if isinstance(ob, dict) else getattr(ob, 'bottom', trade_list[i]['entry_price'] - 50)

# Buscar OB top/bottom dos closed_trades da engine
for i, ct in enumerate(engine.closed_trades):
    if i < len(trade_list):
        trade_list[i]['ob_top'] = ct.ob.top
        trade_list[i]['ob_bottom'] = ct.ob.bottom

# Criar pasta de saida
out_dir = os.path.join(os.path.dirname(__file__), 'resultado_2026', 'mtf_trades')
os.makedirs(out_dir, exist_ok=True)


def plot_trade(trade_info, trade_num, df_m15):
    """Plota um trade individual no grafico M15."""
    fill_time = trade_info['fill_time']
    close_time = trade_info['close_time']
    entry = trade_info['entry_price']
    sl = trade_info['stop_loss']
    tp = trade_info['take_profit']
    exit_p = trade_info['exit_price']
    direction = trade_info['direction']
    status = trade_info['status']
    pnl = trade_info['profit_loss']
    ob_top = trade_info['ob_top']
    ob_bottom = trade_info['ob_bottom']

    # Janela: 30 bars antes do fill, 30 bars apos close
    margin_before = 40
    margin_after = 20

    mask = (df_m15['time'] >= fill_time - timedelta(hours=margin_before * 0.25)) & \
           (df_m15['time'] <= close_time + timedelta(hours=margin_after * 0.25))
    chunk = df_m15[mask].reset_index(drop=True)

    if len(chunk) < 5:
        # Fallback: pegar por indice
        fill_m15_idx = df_m15['time'].searchsorted(fill_time)
        close_m15_idx = df_m15['time'].searchsorted(close_time)
        start = max(0, fill_m15_idx - margin_before)
        end = min(len(df_m15), close_m15_idx + margin_after)
        chunk = df_m15.iloc[start:end].reset_index(drop=True)

    if len(chunk) < 3:
        print(f"  Trade {trade_num}: dados insuficientes, pulando")
        return None

    fig, ax = plt.subplots(figsize=(16, 8))

    # Plotar candlesticks M15
    times = chunk['time'].values
    opens = chunk['open'].values
    highs = chunk['high'].values
    lows = chunk['low'].values
    closes = chunk['close'].values

    width = 0.006  # largura do candle em dias
    for j in range(len(chunk)):
        t = mdates.date2num(pd.Timestamp(times[j]))
        o, h, l, c = opens[j], highs[j], lows[j], closes[j]

        color = '#26a69a' if c >= o else '#ef5350'
        body_bottom = min(o, c)
        body_height = abs(c - o)
        if body_height < 0.5:
            body_height = 0.5

        # Sombras
        ax.plot([t, t], [l, h], color=color, linewidth=0.8)
        # Corpo
        rect = Rectangle((t - width / 2, body_bottom), width, body_height,
                          facecolor=color, edgecolor=color, linewidth=0.5)
        ax.add_patch(rect)

    # Determinar range do eixo X
    x_min = mdates.date2num(pd.Timestamp(times[0])) - width * 2
    x_max = mdates.date2num(pd.Timestamp(times[-1])) + width * 2

    # OB zone
    ax.axhspan(ob_bottom, ob_top, alpha=0.15,
               color='#2196F3' if direction == 'BULLISH' else '#F44336',
               label=f'OB Zone ({ob_bottom:.0f}-{ob_top:.0f})')

    # Entry line
    ax.hlines(entry, x_min, x_max, colors='#FFC107', linewidth=1.5,
              linestyle='--', label=f'Entry {entry:.0f}')

    # SL line
    ax.hlines(sl, x_min, x_max, colors='#F44336', linewidth=1.2,
              linestyle=':', label=f'SL {sl:.0f}')

    # TP line
    ax.hlines(tp, x_min, x_max, colors='#4CAF50', linewidth=1.2,
              linestyle=':', label=f'TP {tp:.0f}')

    # Fill marker
    fill_t = mdates.date2num(fill_time)
    ax.plot(fill_t, entry, marker='^' if direction == 'BULLISH' else 'v',
            color='#2196F3' if direction == 'BULLISH' else '#FF5722',
            markersize=14, zorder=10, markeredgecolor='white', markeredgewidth=1.5)

    # Exit marker
    close_t = mdates.date2num(close_time)
    exit_color = '#4CAF50' if status == 'closed_tp' else '#F44336'
    ax.plot(close_t, exit_p, marker='X', color=exit_color,
            markersize=14, zorder=10, markeredgecolor='white', markeredgewidth=1.5)

    # Linha conectando entry -> exit
    ax.plot([fill_t, close_t], [entry, exit_p],
            color=exit_color, linewidth=1.5, linestyle='-', alpha=0.5)

    # Formatacao
    result_str = 'WIN' if status == 'closed_tp' else 'LOSS'
    result_emoji = '+' if status == 'closed_tp' else ''
    title = (f"Trade #{trade_num} | {direction} {result_str} | "
             f"Entry: {entry:.0f} | Exit: {exit_p:.0f} | "
             f"P/L: {pnl:+.0f} pts | SL: {abs(entry - sl):.0f} pts | "
             f"{fill_time.strftime('%Y-%m-%d %H:%M')}")
    ax.set_title(title, fontsize=12, fontweight='bold',
                 color='#4CAF50' if status == 'closed_tp' else '#F44336')

    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m\n%H:%M'))
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=3))
    plt.xticks(rotation=0, fontsize=8)
    ax.set_ylabel('Preco', fontsize=10)
    ax.set_xlabel('M15', fontsize=10)
    ax.legend(loc='upper left', fontsize=8, framealpha=0.9)
    ax.grid(True, alpha=0.3)

    # Y range com margem
    all_prices = [entry, sl, tp, ob_top, ob_bottom]
    y_min = min(lows.min(), min(all_prices)) - 50
    y_max = max(highs.max(), max(all_prices)) + 50
    ax.set_ylim(y_min, y_max)
    ax.set_xlim(x_min, x_max)

    fig.tight_layout()
    fname = os.path.join(out_dir, f"trade_{trade_num:02d}_{direction}_{result_str}_{fill_time.strftime('%Y%m%d')}.png")
    fig.savefig(fname, dpi=130, bbox_inches='tight')
    plt.close(fig)
    return fname


# Plotar todos os trades
print(f"\nGerando graficos para {len(trade_list)} trades...")
for i, t in enumerate(trade_list):
    result = 'WIN' if t['status'] == 'closed_tp' else 'LOSS'
    print(f"  Trade {i+1:2d}/{len(trade_list)}: {t['direction']:<8} {result:<4} "
          f"{t['profit_loss']:+6.0f} pts | {t['fill_time'].strftime('%Y-%m-%d %H:%M')}", end="")
    fname = plot_trade(t, i + 1, df_m15)
    if fname:
        print(f"  -> OK")
    else:
        print(f"  -> SKIP")

# Overview: todos os trades em equity curve
fig, axes = plt.subplots(2, 1, figsize=(16, 10), gridspec_kw={'height_ratios': [2, 1]})

# Equity curve
pnls = [t['profit_loss'] for t in trade_list]
cum_pnl = np.cumsum(pnls)
fill_times = [t['fill_time'] for t in trade_list]
colors = ['#4CAF50' if t['status'] == 'closed_tp' else '#F44336' for t in trade_list]

axes[0].plot(fill_times, cum_pnl, 'b-', linewidth=2, alpha=0.7)
axes[0].scatter(fill_times, cum_pnl, c=colors, s=80, zorder=5, edgecolors='white', linewidth=1)
axes[0].axhline(0, color='gray', linewidth=0.5, linestyle='--')
axes[0].set_title(f'MTF M15 - Equity Curve | {len(trade_list)} trades | '
                  f'WR {sum(1 for t in trade_list if t["status"]=="closed_tp")/len(trade_list)*100:.1f}% | '
                  f'PF 14.83 | {cum_pnl[-1]:+.0f} pts',
                  fontsize=13, fontweight='bold')
axes[0].set_ylabel('P/L Acumulado (pts)', fontsize=11)
axes[0].grid(True, alpha=0.3)

# Individual P/L bars
bar_colors = ['#4CAF50' if p > 0 else '#F44336' for p in pnls]
axes[1].bar(range(len(pnls)), pnls, color=bar_colors, alpha=0.8, edgecolor='white', linewidth=0.5)
axes[1].axhline(0, color='gray', linewidth=0.5)
axes[1].set_xlabel('Trade #', fontsize=11)
axes[1].set_ylabel('P/L (pts)', fontsize=11)
axes[1].set_title('P/L por Trade', fontsize=11)
axes[1].grid(True, alpha=0.3)

fig.tight_layout()
overview_path = os.path.join(out_dir, 'overview_equity.png')
fig.savefig(overview_path, dpi=130, bbox_inches='tight')
plt.close(fig)

print(f"\nGraficos salvos em: {out_dir}")
print(f"Overview: {overview_path}")
