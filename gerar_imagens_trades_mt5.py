"""
Gerar Imagens dos Trades do Dia - Dados do MT5
================================================
Puxa candles M1 do MT5, roda SMCEngineV3, e gera imagem de cada trade.
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
from smc_engine_v3 import SMCEngineV3, SignalDirection

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'trades_hoje')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================
# 1. CONECTAR AO MT5 E PUXAR DADOS
# ============================================================
print("Conectando ao MetaTrader 5...")
if not mt5.initialize():
    print(f"ERRO: Falha ao inicializar MT5: {mt5.last_error()}")
    sys.exit(1)

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

# Buscar último pregão
rates = None
dia_backtest = None
for dias_atras in range(0, 7):
    dia = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=dias_atras)
    fim = dia + timedelta(hours=23, minutes=59)
    r = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, dia, fim)
    if r is not None and len(r) > 10:
        rates = r
        dia_backtest = dia
        break

if rates is None:
    print("ERRO: Nenhum candle encontrado nos últimos 7 dias.")
    mt5.shutdown()
    sys.exit(1)

df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')
print(f"Pregão: {dia_backtest.strftime('%d/%m/%Y')} | {len(df)} candles M1")
mt5.shutdown()

# ============================================================
# 2. RODAR ENGINE E COLETAR TRADES COM CONTEXTO
# ============================================================
engine = SMCEngineV3(
    symbol=symbol,
    swing_length=5,
    risk_reward_ratio=3.0,
    min_volume_ratio=0.0,
    min_ob_size_atr=0.0,
    use_not_mitigated_filter=True,
    max_pending_candles=150,
    entry_delay_candles=1,
)

# Guardar info de cada sinal/fill/close para associar aos candles
signal_info = {}  # order_id -> {created_at, ob_top, ob_bottom, ...}
trade_events = []  # lista de trades completos

for i in range(len(df)):
    row = df.iloc[i]
    events = engine.add_candle({
        'open': float(row['open']),
        'high': float(row['high']),
        'low': float(row['low']),
        'close': float(row['close']),
        'volume': float(row.get('real_volume', row.get('tick_volume', 0)))
    })

    if events.get('new_signals'):
        for sig in events['new_signals']:
            signal_info[sig['order_id']] = sig

# Coletar trades fechados
raw_trades = engine.get_all_trades()
print(f"Trades fechados: {len(raw_trades)}")

if len(raw_trades) == 0:
    print("Nenhum trade fechado para gerar imagens.")
    sys.exit(0)


# ============================================================
# 3. GERAR IMAGENS
# ============================================================
def plot_candlestick(ax, df_slice, offset=0):
    """Plota candlesticks a partir de um slice do DataFrame."""
    for j in range(len(df_slice)):
        row = df_slice.iloc[j]
        o, h, l, c = row['open'], row['high'], row['low'], row['close']
        color = '#26a69a' if c >= o else '#ef5350'
        edge = '#1b7a6e' if c >= o else '#c62828'

        # Pavio
        ax.plot([j + offset, j + offset], [l, h], color='#555555', linewidth=0.6, zorder=1)

        # Corpo
        body_bottom = min(o, c)
        body_height = max(abs(c - o), 0.5)
        rect = Rectangle((j + offset - 0.35, body_bottom), 0.7, body_height,
                          facecolor=color, edgecolor=edge, linewidth=0.5, zorder=2)
        ax.add_patch(rect)


print(f"\nGerando imagens em: {OUTPUT_DIR}")

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

    # Janela de visualização: candles antes do OB até depois do close
    candles_before = 15
    candles_after = 8
    start = max(0, created_at - candles_before)
    end = min(len(df), closed_at + candles_after + 1)
    df_slice = df.iloc[start:end].reset_index(drop=True)

    # Posições relativas
    ob_rel = created_at - start
    fill_rel = filled_at - start
    close_rel = closed_at - start

    fig, ax = plt.subplots(figsize=(16, 9))
    fig.patch.set_facecolor('#1e1e2f')
    ax.set_facecolor('#1e1e2f')

    # Plotar candles
    plot_candlestick(ax, df_slice)

    # Order Block (zona)
    ob_width = close_rel - ob_rel + 3
    ob_color = '#2196F3' if direction == 'BULLISH' else '#F44336'
    ob_rect = Rectangle((ob_rel - 0.5, ob_bottom), ob_width, ob_top - ob_bottom,
                         facecolor=ob_color, alpha=0.12, edgecolor=ob_color,
                         linewidth=1.5, linestyle='--', zorder=0)
    ax.add_patch(ob_rect)

    # Linhas de Entry, SL, TP
    line_start = ob_rel - 1
    line_end = close_rel + 2

    ax.hlines(y=entry, xmin=line_start, xmax=line_end, color='#42A5F5',
              linewidth=1.8, linestyle='-', label=f'Entry: {entry:,.0f}', zorder=3)
    ax.hlines(y=sl, xmin=line_start, xmax=line_end, color='#EF5350',
              linewidth=1.5, linestyle='--', label=f'SL: {sl:,.0f}', zorder=3)
    ax.hlines(y=tp, xmin=line_start, xmax=line_end, color='#66BB6A',
              linewidth=1.5, linestyle='--', label=f'TP: {tp:,.0f}', zorder=3)

    # Midline do OB
    ax.hlines(y=midline, xmin=ob_rel - 0.5, xmax=ob_rel + ob_width - 0.5,
              color='#FFA726', linewidth=1, linestyle=':', alpha=0.7, zorder=3)

    # Região TP (verde) e SL (vermelho) sombreada
    if direction == 'BULLISH':
        ax.axhspan(entry, tp, alpha=0.04, color='green', zorder=0)
        ax.axhspan(sl, entry, alpha=0.04, color='red', zorder=0)
    else:
        ax.axhspan(tp, entry, alpha=0.04, color='green', zorder=0)
        ax.axhspan(entry, sl, alpha=0.04, color='red', zorder=0)

    # Marcador OB
    ax.annotate('OB', xy=(ob_rel, ob_top), fontsize=9, ha='center', color='#BB86FC',
                fontweight='bold',
                xytext=(ob_rel, ob_top + (ob_top - ob_bottom) * 0.8),
                arrowprops=dict(arrowstyle='->', color='#BB86FC', lw=1.5))

    # Marcador Fill
    marker = '^' if direction == 'BULLISH' else 'v'
    ax.scatter([fill_rel], [entry], color='#42A5F5', s=120, zorder=5, marker=marker,
               edgecolors='white', linewidths=0.8)
    ax.annotate('FILL', xy=(fill_rel, entry),
                xytext=(fill_rel + 1.2, entry), fontsize=8, color='#42A5F5',
                fontweight='bold', va='center')

    # Marcador Close
    close_color = '#66BB6A' if is_win else '#EF5350'
    close_label = 'TP HIT' if is_win else 'SL HIT'
    exit_price = tp if is_win else sl
    ax.scatter([close_rel], [exit_price], color=close_color, s=150, zorder=5,
               marker='*', edgecolors='white', linewidths=0.8)
    ax.annotate(close_label, xy=(close_rel, exit_price),
                xytext=(close_rel + 1.2, exit_price), fontsize=8, color=close_color,
                fontweight='bold', va='center')

    # Timestamps
    fill_time = df['time'].iloc[filled_at].strftime('%H:%M') if filled_at < len(df) else '?'
    close_time = df['time'].iloc[closed_at].strftime('%H:%M') if closed_at < len(df) else '?'

    # Título
    dir_str = "LONG" if direction == 'BULLISH' else "SHORT"
    result_str = "WIN" if is_win else "LOSS"
    result_color = '#66BB6A' if is_win else '#EF5350'

    title = (f'Trade #{idx+1}  |  {dir_str}  |  {result_str}  |  '
             f'{pnl:+,.0f} pts ({pnl_r:+.1f}R)\n'
             f'Entry: {entry:,.0f}  |  SL: {sl:,.0f}  |  TP: {tp:,.0f}  |  '
             f'Fill: {fill_time}  |  Close: {close_time}')
    ax.set_title(title, fontsize=13, color='white', fontweight='bold', pad=15)

    # Badge de resultado
    badge_text = f"  {result_str} {pnl:+,.0f} pts  "
    ax.text(0.98, 0.95, badge_text, transform=ax.transAxes,
            fontsize=14, fontweight='bold', color='white',
            ha='right', va='top',
            bbox=dict(boxstyle='round,pad=0.4', facecolor=result_color, alpha=0.85))

    # Eixos
    ax.set_xlabel('Candles', color='#aaaaaa', fontsize=10)
    ax.set_ylabel('Preço', color='#aaaaaa', fontsize=10)
    ax.tick_params(colors='#aaaaaa')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_color('#555555')
    ax.spines['left'].set_color('#555555')
    ax.grid(True, alpha=0.1, color='#555555')

    # X tick labels com horários
    n_ticks = min(10, len(df_slice))
    tick_step = max(1, len(df_slice) // n_ticks)
    tick_positions = list(range(0, len(df_slice), tick_step))
    tick_labels = [df_slice['time'].iloc[p].strftime('%H:%M') for p in tick_positions]
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels, rotation=45, fontsize=8, color='#aaaaaa')

    # Limites Y com margem
    all_prices = [ob_top, ob_bottom, sl, tp, entry]
    price_min = df_slice['low'].min()
    price_max = df_slice['high'].max()
    y_min = min(price_min, min(all_prices))
    y_max = max(price_max, max(all_prices))
    margin = (y_max - y_min) * 0.08
    ax.set_ylim(y_min - margin, y_max + margin)
    ax.set_xlim(-1, len(df_slice) + 1)

    # Legenda
    legend = ax.legend(loc='upper left', fontsize=9, facecolor='#2a2a3d',
                       edgecolor='#555555', labelcolor='white')

    # Info box
    info_text = (f'{symbol} M1 | {dia_backtest.strftime("%d/%m/%Y")}\n'
                 f'Confidence: {t["confidence"]:.0f}%\n'
                 f'Wait: {t["wait_candles"]} candles\n'
                 f'Duration: {t["duration_candles"]} candles')
    ax.text(0.02, 0.02, info_text, transform=ax.transAxes,
            fontsize=8, color='#999999', va='bottom',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='#2a2a3d', alpha=0.8, edgecolor='#555555'))

    # Salvar
    filepath = os.path.join(OUTPUT_DIR, f'trade_{idx+1:02d}_{dir_str}_{result_str}.png')
    plt.tight_layout()
    plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.close()
    print(f"  [{idx+1}/{len(raw_trades)}] {filepath}")

print(f"\nPronto! {len(raw_trades)} imagens salvas em: {OUTPUT_DIR}")
