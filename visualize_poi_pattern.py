"""
Visualização do Teste de Padrão POI - Candlestick + Swings + OBs
"""

import sys
sys.path.insert(0, '.')
from smc_engine_v3 import SMCEngineV3, SignalDirection
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Rectangle, FancyBboxPatch
import numpy as np

# Recriar os dados do teste
candles = [
    {'open': 100, 'high': 101, 'low': 99, 'close': 101, 'volume': 1000},
    {'open': 101, 'high': 102, 'low': 100, 'close': 102, 'volume': 1000},
    {'open': 102, 'high': 103, 'low': 101, 'close': 103, 'volume': 1000},
    {'open': 103, 'high': 104, 'low': 102, 'close': 104, 'volume': 1000},
    {'open': 104, 'high': 100, 'low': 99, 'close': 100, 'volume': 1000},
    {'open': 100, 'high': 99, 'low': 98, 'close': 98, 'volume': 1000},
    {'open': 98, 'high': 97, 'low': 96, 'close': 96, 'volume': 1000},
    {'open': 96, 'high': 95, 'low': 94, 'close': 94, 'volume': 1000},
    {'open': 94, 'high': 93, 'low': 92, 'close': 92, 'volume': 1000},
    {'open': 92, 'high': 91, 'low': 80, 'close': 80, 'volume': 1000},
    {'open': 80, 'high': 81, 'low': 79, 'close': 81, 'volume': 1000},
    {'open': 81, 'high': 82, 'low': 80, 'close': 82, 'volume': 1000},
    {'open': 82, 'high': 83, 'low': 81, 'close': 83, 'volume': 1000},
    {'open': 83, 'high': 84, 'low': 82, 'close': 84, 'volume': 1000},
    {'open': 84, 'high': 95, 'low': 83, 'close': 95, 'volume': 1000},
    {'open': 95, 'high': 94, 'low': 93, 'close': 93, 'volume': 1000},
    {'open': 93, 'high': 92, 'low': 91, 'close': 91, 'volume': 1000},
    {'open': 91, 'high': 90, 'low': 89, 'close': 89, 'volume': 1000},
    {'open': 89, 'high': 88, 'low': 87, 'close': 87, 'volume': 1000},
    {'open': 87, 'high': 86, 'low': 75, 'close': 75, 'volume': 1000},
    {'open': 75, 'high': 76, 'low': 74, 'close': 76, 'volume': 1000},
    {'open': 76, 'high': 77, 'low': 75, 'close': 77, 'volume': 1000},
    {'open': 77, 'high': 78, 'low': 76, 'close': 78, 'volume': 1000},
    {'open': 78, 'high': 79, 'low': 77, 'close': 79, 'volume': 1000},
    {'open': 79, 'high': 96, 'low': 78, 'close': 96, 'volume': 1000},
]

# Processar com engine
engine = SMCEngineV3(
    symbol='TEST',
    swing_length=5,
    risk_reward_ratio=3.0,
    min_volume_ratio=0.0,
    min_ob_size_atr=0.0,
    use_not_mitigated_filter=True,
    max_pending_candles=150,
    entry_delay_candles=1,
)

for candle in candles:
    engine.add_candle(candle)

# Preparar dados para visualização
opens = [c['open'] for c in candles]
highs = [c['high'] for c in candles]
lows = [c['low'] for c in candles]
closes = [c['close'] for c in candles]
indices = np.arange(len(candles))

# Criar figura
fig, ax = plt.subplots(figsize=(16, 9), dpi=100)
fig.patch.set_facecolor('#0a0e27')
ax.set_facecolor('#0a0e27')

# Desenhar candlesticks
width = 0.6
for i in range(len(candles)):
    o, h, l, c = opens[i], highs[i], lows[i], closes[i]
    
    # Cor: verde se bullish, vermelho se bearish
    color = '#00ff41' if c >= o else '#ff0041'
    
    # Linha high-low
    ax.plot([i, i], [l, h], color=color, linewidth=1.5, alpha=0.8)
    
    # Corpo (open-close)
    body_height = abs(c - o)
    body_bottom = min(o, c)
    rect = Rectangle((i - width/2, body_bottom), width, body_height, 
                     facecolor=color, edgecolor=color, linewidth=1.5, alpha=0.9)
    ax.add_patch(rect)

# Desenhar Swing Highs
for conf_idx, cand_idx, level in engine.swing_highs:
    ax.plot([cand_idx, conf_idx], [level, level], 'o-', color='#ff00ff', 
           linewidth=2, markersize=8, label='Swing High' if cand_idx == engine.swing_highs[0][1] else '')
    ax.text(conf_idx + 0.5, level + 1, f'SH: {level}', color='#ff00ff', fontsize=9, fontweight='bold')

# Desenhar Swing Lows
for conf_idx, cand_idx, level in engine.swing_lows:
    ax.plot([cand_idx, conf_idx], [level, level], 'o-', color='#00ffff', 
           linewidth=2, markersize=8, label='Swing Low' if cand_idx == engine.swing_lows[0][1] else '')
    ax.text(conf_idx + 0.5, level - 1.5, f'SL: {level}', color='#00ffff', fontsize=9, fontweight='bold')

# Desenhar Order Blocks
for ob in engine.active_obs:
    color = '#ffff00' if ob.direction == SignalDirection.BULLISH else '#ff8800'
    alpha = 0.3 if ob.mitigated else 0.5
    
    # Zona do OB (do candle do OB até o candle de confirmação)
    ob_rect = FancyBboxPatch((ob.ob_candle_index - 0.4, ob.bottom), 
                            ob.confirmation_index - ob.ob_candle_index + 0.8, 
                            ob.top - ob.bottom,
                            boxstyle="round,pad=0.05", 
                            facecolor=color, edgecolor=color, 
                            linewidth=2, alpha=alpha, linestyle='--')
    ax.add_patch(ob_rect)
    
    # Midline
    ax.axhline(y=ob.midline, xmin=(ob.ob_candle_index - 0.5) / len(candles), 
              xmax=(ob.confirmation_index + 0.5) / len(candles),
              color=color, linestyle=':', linewidth=2, alpha=0.7)
    
    # Label
    status = 'MITIGADO' if ob.mitigated else 'ATIVO'
    label_text = f"OB{ob.ob_id} {ob.direction.name[:1]} {status}"
    ax.text(ob.ob_candle_index, ob.top + 2, label_text, color=color, fontsize=8, fontweight='bold')

# Anotações de fases
phases = [
    (2, 102, "FASE 1: ALTA\n(Swing High)", '#ff00ff'),
    (7, 82, "FASE 2: BAIXA\n(Swing Low)", '#00ffff'),
    (12, 97, "FASE 3: ALTA\n(Swing High)", '#ff00ff'),
    (17, 77, "FASE 4: BAIXA MAIS BAIXA\n(Quebra fundo)", '#00ffff'),
    (22, 98, "FASE 5: ALTA APÓS\n(BOS/CHoCH)", '#00ff00'),
]

for idx, price, text, color in phases:
    ax.annotate(text, xy=(idx, price), xytext=(idx, price + 5),
               fontsize=9, color=color, fontweight='bold',
               bbox=dict(boxstyle='round,pad=0.3', facecolor='#0a0e27', edgecolor=color, linewidth=1.5),
               ha='center', va='bottom')

# Configurar eixos
ax.set_xlim(-1, len(candles))
ax.set_ylim(70, 110)
ax.set_xlabel('Candle Index', color='#ffffff', fontsize=11, fontweight='bold')
ax.set_ylabel('Preço', color='#ffffff', fontsize=11, fontweight='bold')
ax.set_title('Teste de Padrão SMC: Alta → Baixa → Alta → Baixa Mais Baixa → Alta Após\n' + 
            'Identificação de Swings, Order Blocks e BOS/CHoCH',
            color='#ffffff', fontsize=14, fontweight='bold', pad=20)

# Grid
ax.grid(True, alpha=0.2, color='#ffffff', linestyle='--', linewidth=0.5)
ax.set_facecolor('#0a0e27')

# Legenda
legend_elements = [
    mpatches.Patch(facecolor='#00ff41', edgecolor='#00ff41', label='Bullish Candle'),
    mpatches.Patch(facecolor='#ff0041', edgecolor='#ff0041', label='Bearish Candle'),
    mpatches.Patch(facecolor='#ff00ff', edgecolor='#ff00ff', alpha=0.5, label='Swing High'),
    mpatches.Patch(facecolor='#00ffff', edgecolor='#00ffff', alpha=0.5, label='Swing Low'),
    mpatches.Patch(facecolor='#ffff00', edgecolor='#ffff00', alpha=0.5, label='OB Bullish'),
    mpatches.Patch(facecolor='#ff8800', edgecolor='#ff8800', alpha=0.5, label='OB Bearish'),
]
ax.legend(handles=legend_elements, loc='upper left', fontsize=10, 
         facecolor='#0a0e27', edgecolor='#ffffff', framealpha=0.9)

# Estilo dos ticks
ax.tick_params(colors='#ffffff', labelsize=10)
for spine in ax.spines.values():
    spine.set_edgecolor('#ffffff')
    spine.set_linewidth(1.5)

plt.tight_layout()
plt.savefig('poi_pattern_test.png', dpi=150, facecolor='#0a0e27', edgecolor='none')
print("Visualização salva em: poi_pattern_test.png")

# Criar figura com resumo
fig2, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 10), dpi=100)
fig2.patch.set_facecolor('#0a0e27')

# Painel 1: Resumo de Swings
ax1.set_facecolor('#0a0e27')
ax1.axis('off')
swing_text = "SWINGS DETECTADOS\n" + "="*40 + "\n\n"
for i, (conf_idx, cand_idx, level) in enumerate(engine.swing_highs):
    swing_text += f"Swing High #{i+1}:\n  Nível: {level}\n  Confirmado em: candle {conf_idx}\n  Candidato em: candle {cand_idx}\n\n"
for i, (conf_idx, cand_idx, level) in enumerate(engine.swing_lows):
    swing_text += f"Swing Low #{i+1}:\n  Nível: {level}\n  Confirmado em: candle {conf_idx}\n  Candidato em: candle {cand_idx}\n\n"
ax1.text(0.05, 0.95, swing_text, transform=ax1.transAxes, fontsize=10, 
        verticalalignment='top', fontfamily='monospace', color='#00ff41',
        bbox=dict(boxstyle='round', facecolor='#1a1e37', edgecolor='#00ff41', linewidth=2))

# Painel 2: Resumo de Order Blocks
ax2.set_facecolor('#0a0e27')
ax2.axis('off')
ob_text = "ORDER BLOCKS DETECTADOS\n" + "="*40 + "\n\n"
for ob in engine.active_obs:
    status = "MITIGADO" if ob.mitigated else "ATIVO"
    ob_text += f"OB #{ob.ob_id} - {ob.direction.name}:\n"
    ob_text += f"  Top: {ob.top}, Bottom: {ob.bottom}\n"
    ob_text += f"  Midline: {ob.midline}\n"
    ob_text += f"  Status: {status}\n"
    ob_text += f"  OB Candle: {ob.ob_candle_index}\n"
    ob_text += f"  Confirmation: {ob.confirmation_index}\n\n"
ax2.text(0.05, 0.95, ob_text, transform=ax2.transAxes, fontsize=10, 
        verticalalignment='top', fontfamily='monospace', color='#ffff00',
        bbox=dict(boxstyle='round', facecolor='#1a1e37', edgecolor='#ffff00', linewidth=2))

# Painel 3: Resumo de Ordens
ax3.set_facecolor('#0a0e27')
ax3.axis('off')
orders_text = "ORDENS PENDENTES\n" + "="*40 + "\n\n"
if engine.pending_orders:
    for order in engine.pending_orders:
        orders_text += f"{order.order_id} - {order.direction.name}:\n"
        orders_text += f"  Entry: {order.entry_price}\n"
        orders_text += f"  SL: {order.stop_loss}\n"
        orders_text += f"  TP: {order.take_profit}\n"
        orders_text += f"  Created: candle {order.created_at}\n\n"
else:
    orders_text += "Nenhuma ordem pendente\n"
ax3.text(0.05, 0.95, orders_text, transform=ax3.transAxes, fontsize=10, 
        verticalalignment='top', fontfamily='monospace', color='#00ffff',
        bbox=dict(boxstyle='round', facecolor='#1a1e37', edgecolor='#00ffff', linewidth=2))

# Painel 4: Estatísticas
ax4.set_facecolor('#0a0e27')
ax4.axis('off')
stats = engine.get_stats()
stats_text = "ESTATÍSTICAS\n" + "="*40 + "\n\n"
stats_text += f"Total de Swings High: {len(engine.swing_highs)}\n"
stats_text += f"Total de Swings Low: {len(engine.swing_lows)}\n"
stats_text += f"Total de OBs: {len(engine.active_obs)}\n"
stats_text += f"OBs Ativos: {sum(1 for ob in engine.active_obs if not ob.mitigated)}\n"
stats_text += f"OBs Mitigados: {sum(1 for ob in engine.active_obs if ob.mitigated)}\n"
stats_text += f"Ordens Pendentes: {len(engine.pending_orders)}\n"
stats_text += f"Trades Fechados: {stats['total_trades']}\n"
stats_text += f"Win Rate: {stats['win_rate']:.1f}%\n"
ax4.text(0.05, 0.95, stats_text, transform=ax4.transAxes, fontsize=11, 
        verticalalignment='top', fontfamily='monospace', color='#ff00ff', fontweight='bold',
        bbox=dict(boxstyle='round', facecolor='#1a1e37', edgecolor='#ff00ff', linewidth=2))

plt.tight_layout()
plt.savefig('poi_pattern_summary.png', dpi=150, facecolor='#0a0e27', edgecolor='none')
print("Resumo salvo em: poi_pattern_summary.png")

plt.close('all')
