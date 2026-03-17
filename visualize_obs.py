"""
Visualização da Detecção de Order Blocks - Estado Atual da Engine
"""
import sys
sys.path.insert(0, '/home/ubuntu/ultimate_SMC')

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, Rectangle
from matplotlib.lines import Line2D
from matplotlib.gridspec import GridSpec
from smc_engine_v3 import SMCEngineV3, SignalDirection

# Carregar dados
df = pd.read_csv('/home/ubuntu/ultimate_SMC/mtwin14400.csv')
df.columns = [c.lower() for c in df.columns]
vol_col = 'tick_volume' if 'tick_volume' in df.columns else 'volume'

# Rodar engine V3 sem filtros para capturar TODOS os OBs
engine = SMCEngineV3(
    symbol='WINM24', swing_length=5, risk_reward_ratio=3.0,
    min_volume_ratio=0.0, min_ob_size_atr=0.0,
    use_not_mitigated_filter=True, max_pending_candles=150,
    entry_delay_candles=1,
)

ob_history = []  # rastrear crescimento
for i in range(len(df)):
    row = df.iloc[i]
    events = engine.add_candle({
        'open': float(row['open']),
        'high': float(row['high']),
        'low': float(row['low']),
        'close': float(row['close']),
        'volume': float(row[vol_col])
    })
    ob_history.append({
        'candle': i,
        'total': len(engine.active_obs),
        'active': sum(1 for ob in engine.active_obs if not ob.mitigated),
        'mitigated': sum(1 for ob in engine.active_obs if ob.mitigated),
    })

# ============================================================
# FIGURA PRINCIPAL - 3 painéis
# ============================================================
plt.style.use('dark_background')
plt.rcParams.update({
    'font.family': 'DejaVu Sans',
    'font.size': 9,
    'axes.titlesize': 12,
    'axes.labelsize': 10,
})

fig = plt.figure(figsize=(22, 16))
gs = GridSpec(3, 1, height_ratios=[5, 1.5, 1.5], hspace=0.25, figure=fig)

# ============================================================
# PAINEL 1: Candlestick + Order Blocks
# ============================================================
ax1 = fig.add_subplot(gs[0])

opens = np.array(engine.opens)
highs = np.array(engine.highs)
lows = np.array(engine.lows)
closes = np.array(engine.closes)
n = len(opens)
x = np.arange(n)

# Desenhar candlesticks
for i in range(n):
    color = '#26a69a' if closes[i] >= opens[i] else '#ef5350'
    # Sombra
    ax1.plot([i, i], [lows[i], highs[i]], color=color, linewidth=0.6, alpha=0.7)
    # Corpo
    body_bottom = min(opens[i], closes[i])
    body_top = max(opens[i], closes[i])
    body_height = max(body_top - body_bottom, 0.5)
    rect = Rectangle((i - 0.35, body_bottom), 0.7, body_height,
                      facecolor=color, edgecolor=color, linewidth=0.5, alpha=0.85)
    ax1.add_patch(rect)

# Desenhar Order Blocks
for ob in engine.active_obs:
    is_bullish = ob.direction == SignalDirection.BULLISH
    
    if ob.mitigated:
        # OB mitigado - vermelho/cinza com X
        facecolor = '#ff5252' if is_bullish else '#ff5252'
        alpha = 0.12
        edgecolor = '#ff5252'
        linestyle = '--'
        label_prefix = "MITIGADO"
    else:
        # OB ativo
        facecolor = '#00e676' if is_bullish else '#ff9100'
        alpha = 0.22
        edgecolor = '#00e676' if is_bullish else '#ff9100'
        linestyle = '-'
        label_prefix = "ATIVO"
    
    # Extensão do OB (do candle de formação até mitigação ou fim)
    start_x = ob.ob_candle_index
    if ob.mitigated:
        end_x = ob.mitigated_index
    else:
        end_x = n - 1
    
    width = end_x - start_x
    height = ob.top - ob.bottom
    
    rect = Rectangle((start_x, ob.bottom), width, height,
                      facecolor=facecolor, edgecolor=edgecolor,
                      linewidth=1.2, alpha=alpha, linestyle=linestyle)
    ax1.add_patch(rect)
    
    # Linha do meio (midline)
    ax1.plot([start_x, end_x], [ob.midline, ob.midline],
             color=edgecolor, linewidth=0.8, linestyle=':', alpha=0.6)
    
    # Label do OB
    direction_str = "BULL" if is_bullish else "BEAR"
    ax1.annotate(f"OB#{ob.ob_id} {direction_str}\n{label_prefix}",
                 xy=(start_x + 1, ob.top + 2),
                 fontsize=6.5, color=edgecolor, alpha=0.9,
                 fontweight='bold',
                 bbox=dict(boxstyle='round,pad=0.2', facecolor='black', alpha=0.6, edgecolor=edgecolor, linewidth=0.5))
    
    # Marca de confirmação
    ax1.axvline(x=ob.confirmation_index, color=edgecolor, linewidth=0.4, alpha=0.3, linestyle=':')
    
    # Se mitigado, desenhar X
    if ob.mitigated:
        mid_x = (start_x + end_x) / 2
        mid_y = (ob.top + ob.bottom) / 2
        ax1.plot(mid_x, mid_y, 'x', color='#ff5252', markersize=10, markeredgewidth=2, alpha=0.5)

# Desenhar Swing Highs e Lows
for conf_idx, cand_idx, level in engine.swing_highs:
    ax1.plot(cand_idx, level, 'v', color='#ff4081', markersize=6, alpha=0.7)
    ax1.annotate(f'SH', xy=(cand_idx, level + 3), fontsize=5.5, color='#ff4081', ha='center', alpha=0.7)

for conf_idx, cand_idx, level in engine.swing_lows:
    ax1.plot(cand_idx, level, '^', color='#40c4ff', markersize=6, alpha=0.7)
    ax1.annotate(f'SL', xy=(cand_idx, level - 8), fontsize=5.5, color='#40c4ff', ha='center', alpha=0.7)

# Trades fechados
for trade in engine.closed_trades:
    entry_color = '#00e676' if trade.direction == SignalDirection.BULLISH else '#ff9100'
    exit_color = '#00e676' if trade.status.value == 'closed_tp' else '#ff5252'
    
    ax1.plot(trade.filled_at, trade.entry_price, 'D', color=entry_color, markersize=8, zorder=5)
    ax1.plot(trade.closed_at, trade.exit_price, 's', color=exit_color, markersize=8, zorder=5)
    ax1.plot([trade.filled_at, trade.closed_at], [trade.entry_price, trade.exit_price],
             color=exit_color, linewidth=1.5, linestyle='-', alpha=0.6)

# Ordens pendentes
for order in engine.pending_orders:
    ax1.axhline(y=order.entry_price, color='#ffeb3b', linewidth=0.8, linestyle='--', alpha=0.5)
    ax1.annotate(f'PENDING {order.order_id}', xy=(n - 1, order.entry_price),
                 fontsize=5.5, color='#ffeb3b', ha='right', alpha=0.8)

ax1.set_title('Detecção de Order Blocks — Estado Atual da Engine V3\nWINM24 M1 | Todos os OBs detectados (sem filtros de volume/tamanho)',
              fontsize=13, fontweight='bold', color='white', pad=12)
ax1.set_ylabel('Preço (pontos)', fontsize=10)
ax1.set_xlim(-2, n + 5)
ax1.grid(True, alpha=0.1, linewidth=0.3)

# Legenda customizada
legend_elements = [
    Line2D([0], [0], marker='s', color='w', markerfacecolor='#00e676', markersize=10, label='OB Bullish Ativo', alpha=0.8),
    Line2D([0], [0], marker='s', color='w', markerfacecolor='#ff9100', markersize=10, label='OB Bearish Ativo', alpha=0.8),
    Line2D([0], [0], marker='x', color='#ff5252', markersize=10, markeredgewidth=2, label='OB Mitigado (lixo na memória)', linestyle='None'),
    Line2D([0], [0], marker='v', color='#ff4081', markersize=8, label='Swing High', linestyle='None'),
    Line2D([0], [0], marker='^', color='#40c4ff', markersize=8, label='Swing Low', linestyle='None'),
    Line2D([0], [0], marker='D', color='#00e676', markersize=8, label='Entrada (Fill)', linestyle='None'),
    Line2D([0], [0], color='#ffeb3b', linewidth=1.5, linestyle='--', label='Ordem Pendente'),
    mpatches.Patch(facecolor='#ff5252', alpha=0.15, edgecolor='#ff5252', linestyle='--', label='Zona OB Mitigado'),
]
ax1.legend(handles=legend_elements, loc='upper left', fontsize=7.5, framealpha=0.7,
           facecolor='#1a1a2e', edgecolor='#444', ncol=2)

# ============================================================
# PAINEL 2: Acúmulo de OBs ao longo do tempo
# ============================================================
ax2 = fig.add_subplot(gs[1])

candles_arr = [h['candle'] for h in ob_history]
total_arr = [h['total'] for h in ob_history]
active_arr = [h['active'] for h in ob_history]
mitigated_arr = [h['mitigated'] for h in ob_history]

ax2.fill_between(candles_arr, total_arr, color='#ff5252', alpha=0.3, label='Total OBs na memória')
ax2.fill_between(candles_arr, mitigated_arr, color='#ff5252', alpha=0.5, label='OBs mitigados (lixo)')
ax2.fill_between(candles_arr, active_arr, color='#00e676', alpha=0.5, label='OBs ativos (úteis)')

ax2.set_title('Acúmulo de Order Blocks na Lista active_obs — Crescimento Linear Sem Limpeza',
              fontsize=11, fontweight='bold', color='white', pad=8)
ax2.set_ylabel('Qtd OBs', fontsize=10)
ax2.set_xlim(-2, n + 5)
ax2.grid(True, alpha=0.1, linewidth=0.3)
ax2.legend(loc='upper left', fontsize=8, framealpha=0.7, facecolor='#1a1a2e', edgecolor='#444')

# Anotação do problema
final_total = total_arr[-1]
final_mitigated = mitigated_arr[-1]
pct_lixo = final_mitigated / max(1, final_total) * 100
ax2.annotate(f'{final_mitigated}/{final_total} OBs = {pct_lixo:.0f}% LIXO\nNunca removidos da memória!',
             xy=(n - 1, final_total), xytext=(n * 0.6, final_total + 1),
             fontsize=9, color='#ff5252', fontweight='bold',
             arrowprops=dict(arrowstyle='->', color='#ff5252', lw=1.5),
             bbox=dict(boxstyle='round,pad=0.4', facecolor='#1a1a2e', edgecolor='#ff5252', linewidth=1.5))

# ============================================================
# PAINEL 3: Projeção de crescimento para operação contínua
# ============================================================
ax3 = fig.add_subplot(gs[2])

# Projetar crescimento linear
obs_per_candle = engine._ob_counter / len(df)
projection_candles = np.arange(0, 130000, 100)
projection_obs = projection_candles * obs_per_candle

# Marcos
marcos = {
    '1 dia\n(480)': 480,
    '1 semana\n(2.400)': 2400,
    '1 mês\n(10.560)': 10560,
    '3 meses\n(31.680)': 31680,
    '6 meses\n(63.360)': 63360,
    '1 ano\n(120.960)': 120960,
}

ax3.fill_between(projection_candles, projection_obs, color='#ff5252', alpha=0.3)
ax3.plot(projection_candles, projection_obs, color='#ff5252', linewidth=2, label='OBs acumulados (sem limpeza)')

# Linha de "limpeza ideal" - apenas ativos
active_ratio = active_arr[-1] / max(1, total_arr[-1])
projection_active = np.full_like(projection_obs, active_arr[-1] * 1.5)  # ~estável
ax3.plot(projection_candles, projection_active, color='#00e676', linewidth=2, linestyle='--',
         label=f'OBs necessários (~{int(active_arr[-1] * 1.5)} com limpeza)')

for label, candle_count in marcos.items():
    obs_at = candle_count * obs_per_candle
    ax3.axvline(x=candle_count, color='#666', linewidth=0.5, linestyle=':')
    ax3.annotate(label, xy=(candle_count, obs_at), xytext=(candle_count, obs_at + 200),
                 fontsize=6.5, color='#aaa', ha='center',
                 arrowprops=dict(arrowstyle='->', color='#666', lw=0.8))

ax3.set_title('Projeção: Crescimento de OBs em Operação Contínua (M1)',
              fontsize=11, fontweight='bold', color='white', pad=8)
ax3.set_xlabel('Candles processados', fontsize=10)
ax3.set_ylabel('OBs na memória', fontsize=10)
ax3.set_xlim(0, 130000)
ax3.grid(True, alpha=0.1, linewidth=0.3)
ax3.legend(loc='upper left', fontsize=8, framealpha=0.7, facecolor='#1a1a2e', edgecolor='#444')

# Anotação final
ax3.annotate(f'~5.450 OBs em 1 ano\nSem garbage collection!',
             xy=(120960, 120960 * obs_per_candle),
             xytext=(90000, 120960 * obs_per_candle + 800),
             fontsize=9, color='#ff5252', fontweight='bold',
             arrowprops=dict(arrowstyle='->', color='#ff5252', lw=1.5),
             bbox=dict(boxstyle='round,pad=0.4', facecolor='#1a1a2e', edgecolor='#ff5252', linewidth=1.5))

plt.savefig('/home/ubuntu/ob_detection_audit.png', dpi=180, bbox_inches='tight',
            facecolor='#0d1117', edgecolor='none')
plt.close()

print("Imagem salva em /home/ubuntu/ob_detection_audit.png")
