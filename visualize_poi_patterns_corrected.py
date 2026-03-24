"""
Visualização dos Padrões SMC POI Corrigidos
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Rectangle, FancyBboxPatch
import numpy as np

# Dados BULLISH
candles_bullish = [
    {'open': 50, 'high': 51, 'low': 49, 'close': 51},       # 0
    {'open': 51, 'high': 52, 'low': 50, 'close': 52},       # 1
    {'open': 52, 'high': 53, 'low': 51, 'close': 53},       # 2
    {'open': 53, 'high': 54, 'low': 52, 'close': 54},       # 3
    {'open': 54, 'high': 70, 'low': 53, 'close': 70},       # 4 - SH inicial
    {'open': 70, 'high': 69, 'low': 68, 'close': 68},       # 5
    {'open': 68, 'high': 67, 'low': 66, 'close': 66},       # 6
    {'open': 66, 'high': 65, 'low': 64, 'close': 64},       # 7
    {'open': 64, 'high': 63, 'low': 62, 'close': 62},       # 8
    {'open': 62, 'high': 61, 'low': 45, 'close': 45},       # 9 - SL
    {'open': 45, 'high': 46, 'low': 44, 'close': 46},       # 10
    {'open': 46, 'high': 47, 'low': 45, 'close': 47},       # 11
    {'open': 47, 'high': 48, 'low': 46, 'close': 48},       # 12
    {'open': 48, 'high': 49, 'low': 47, 'close': 49},       # 13
    {'open': 49, 'high': 65, 'low': 48, 'close': 65},       # 14 - SH
    {'open': 65, 'high': 64, 'low': 63, 'close': 63},       # 15
    {'open': 63, 'high': 62, 'low': 61, 'close': 61},       # 16
    {'open': 61, 'high': 60, 'low': 59, 'close': 59},       # 17
    {'open': 59, 'high': 58, 'low': 57, 'close': 57},       # 18
    {'open': 57, 'high': 56, 'low': 30, 'close': 30},       # 19 - SL+ (quebra)
    {'open': 30, 'high': 31, 'low': 29, 'close': 31},       # 20
    {'open': 31, 'high': 32, 'low': 30, 'close': 32},       # 21
    {'open': 32, 'high': 33, 'low': 31, 'close': 33},       # 22
    {'open': 33, 'high': 34, 'low': 32, 'close': 34},       # 23
    {'open': 34, 'high': 80, 'low': 33, 'close': 80},       # 24 - SH BOS
]

# Dados BEARISH
candles_bearish = [
    {'open': 100, 'high': 101, 'low': 99, 'close': 101},    # 0
    {'open': 101, 'high': 102, 'low': 100, 'close': 102},   # 1
    {'open': 102, 'high': 103, 'low': 101, 'close': 103},   # 2
    {'open': 103, 'high': 104, 'low': 102, 'close': 104},   # 3
    {'open': 104, 'high': 95, 'low': 85, 'close': 85},      # 4 - SL inicial
    {'open': 85, 'high': 86, 'low': 84, 'close': 86},       # 5
    {'open': 86, 'high': 87, 'low': 85, 'close': 87},       # 6
    {'open': 87, 'high': 88, 'low': 86, 'close': 88},       # 7
    {'open': 88, 'high': 89, 'low': 87, 'close': 89},       # 8
    {'open': 89, 'high': 115, 'low': 88, 'close': 115},     # 9 - SH
    {'open': 115, 'high': 114, 'low': 113, 'close': 113},   # 10
    {'open': 113, 'high': 112, 'low': 111, 'close': 111},   # 11
    {'open': 111, 'high': 110, 'low': 109, 'close': 109},   # 12
    {'open': 109, 'high': 108, 'low': 107, 'close': 107},   # 13
    {'open': 107, 'high': 106, 'low': 95, 'close': 95},     # 14 - SL
    {'open': 95, 'high': 96, 'low': 94, 'close': 96},       # 15
    {'open': 96, 'high': 97, 'low': 95, 'close': 97},       # 16
    {'open': 97, 'high': 98, 'low': 96, 'close': 98},       # 17
    {'open': 98, 'high': 99, 'low': 97, 'close': 99},       # 18
    {'open': 99, 'high': 130, 'low': 98, 'close': 130},     # 19 - SH+ (quebra)
    {'open': 130, 'high': 129, 'low': 128, 'close': 128},   # 20
    {'open': 128, 'high': 127, 'low': 126, 'close': 126},   # 21
    {'open': 126, 'high': 125, 'low': 124, 'close': 124},   # 22
    {'open': 124, 'high': 123, 'low': 122, 'close': 122},   # 23
    {'open': 122, 'high': 121, 'low': 50, 'close': 50},     # 24 - SL CHoCH
]

def plot_candlestick(ax, candles, title, pattern_name):
    """Plot candlestick chart com swings e OBs"""
    
    x = np.arange(len(candles))
    
    # Plotar candlesticks
    for i, candle in enumerate(candles):
        o, h, l, c = candle['open'], candle['high'], candle['low'], candle['close']
        
        # Cor do candle
        color = '#00AA00' if c >= o else '#AA0000'
        
        # Linha high-low (wick)
        ax.plot([i, i], [l, h], color=color, linewidth=0.5)
        
        # Corpo do candle
        body_height = abs(c - o)
        body_bottom = min(o, c)
        rect = Rectangle((i - 0.3, body_bottom), 0.6, body_height, 
                         facecolor=color, edgecolor=color, linewidth=1)
        ax.add_patch(rect)
    
    # Adicionar swings e OBs conforme o padrão
    if pattern_name == "BULLISH":
        # SH inicial (candle 4)
        ax.plot(4, 70, marker='^', markersize=12, color='#FF6B00', label='SH Inicial', zorder=5)
        ax.text(4, 72, 'SH\n70', ha='center', fontsize=9, fontweight='bold')
        
        # SL (candle 9)
        ax.plot(9, 45, marker='v', markersize=12, color='#0066FF', label='SL', zorder=5)
        ax.text(9, 42, 'SL\n45', ha='center', fontsize=9, fontweight='bold')
        
        # SH (candle 14)
        ax.plot(14, 65, marker='^', markersize=12, color='#FF6B00', zorder=5)
        ax.text(14, 67, 'SH\n65', ha='center', fontsize=9, fontweight='bold')
        
        # SL+ (candle 19) - quebra fundo
        ax.plot(19, 30, marker='v', markersize=14, color='#FF0000', label='SL+ (Quebra)', zorder=5)
        ax.text(19, 27, 'SL+\n30', ha='center', fontsize=9, fontweight='bold', color='#FF0000')
        
        # SH BOS (candle 24)
        ax.plot(24, 80, marker='^', markersize=14, color='#00FF00', label='SH BOS', zorder=5)
        ax.text(24, 82, 'SH\n80', ha='center', fontsize=9, fontweight='bold', color='#00FF00')
        
        # OB BEARISH (entre SH inicial e SL)
        ax.axhspan(45, 46, xmin=0.35, xmax=0.42, alpha=0.3, color='#FF0000', label='OB BEARISH (Mitigado)')
        
        # OB BULLISH (entre SL+ e SH BOS)
        ax.axhspan(45, 62, xmin=0.76, xmax=1.0, alpha=0.3, color='#00AA00', label='OB BULLISH (Ativo)')
        
    else:  # BEARISH
        # SL inicial (candle 4)
        ax.plot(4, 85, marker='v', markersize=12, color='#0066FF', label='SL Inicial', zorder=5)
        ax.text(4, 82, 'SL\n85', ha='center', fontsize=9, fontweight='bold')
        
        # SH (candle 9)
        ax.plot(9, 115, marker='^', markersize=12, color='#FF6B00', label='SH', zorder=5)
        ax.text(9, 117, 'SH\n115', ha='center', fontsize=9, fontweight='bold')
        
        # SL (candle 14)
        ax.plot(14, 95, marker='v', markersize=12, color='#0066FF', zorder=5)
        ax.text(14, 92, 'SL\n95', ha='center', fontsize=9, fontweight='bold')
        
        # SH+ (candle 19) - quebra topo
        ax.plot(19, 130, marker='^', markersize=14, color='#FF0000', label='SH+ (Quebra)', zorder=5)
        ax.text(19, 132, 'SH+\n130', ha='center', fontsize=9, fontweight='bold', color='#FF0000')
        
        # SL CHoCH (candle 24)
        ax.plot(24, 50, marker='v', markersize=14, color='#0066FF', label='SL CHoCH', zorder=5)
        ax.text(24, 47, 'SL\n50', ha='center', fontsize=9, fontweight='bold', color='#0066FF')
        
        # OB BULLISH (entre SL inicial e SH)
        ax.axhspan(85, 104, xmin=0.15, xmax=0.42, alpha=0.3, color='#00AA00', label='OB BULLISH (Mitigado)')
        
        # OB BEARISH (entre SH+ e SL CHoCH)
        ax.axhspan(95, 96, xmin=0.76, xmax=1.0, alpha=0.3, color='#FF0000', label='OB BEARISH (Ativo)')
    
    ax.set_xlim(-1, len(candles))
    ax.set_xlabel('Candle', fontsize=11, fontweight='bold')
    ax.set_ylabel('Preço', fontsize=11, fontweight='bold')
    ax.set_title(title, fontsize=13, fontweight='bold', pad=15)
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.legend(loc='upper left', fontsize=9, framealpha=0.9)

# Criar figura com dois subplots
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 12))
fig.suptitle('Padrões SMC POI - Identificação Corrigida', fontsize=16, fontweight='bold', y=0.995)

plot_candlestick(ax1, candles_bullish, 
                 'PADRÃO BULLISH: SH (ALTA) → SL → SH → SL+ (Quebra) → SH (BOS)',
                 'BULLISH')

plot_candlestick(ax2, candles_bearish,
                 'PADRÃO BEARISH: SL (BAIXA) → SH → SL → SH+ (Quebra) → SL (CHoCH)',
                 'BEARISH')

plt.tight_layout()
plt.savefig('/home/ubuntu/ultimate_SMC/poi_patterns_corrected.png', dpi=150, bbox_inches='tight')
print("✓ Visualização salva: poi_patterns_corrected.png")
plt.close()

# Criar figura de resumo com tabela
fig, ax = plt.subplots(figsize=(14, 8))
ax.axis('off')

# Título
fig.text(0.5, 0.95, 'Padrões SMC POI - Resumo Completo', 
         ha='center', fontsize=16, fontweight='bold')

# Tabela BULLISH
bullish_data = [
    ['Fase', 'Candle', 'Tipo', 'Nível', 'Descrição'],
    ['1', '4', 'SH Inicial', '70', 'Perna de ALTA inicial'],
    ['2', '9', 'SL', '45', 'Perna de BAIXA'],
    ['3', '14', 'SH', '65', 'Perna de ALTA'],
    ['4', '19', 'SL+', '30', 'Quebra fundo (< 45)'],
    ['5', '24', 'SH BOS', '80', 'Rompe SH inicial (> 70)'],
]

# Tabela BEARISH
bearish_data = [
    ['Fase', 'Candle', 'Tipo', 'Nível', 'Descrição'],
    ['1', '4', 'SL Inicial', '85', 'Perna de BAIXA inicial'],
    ['2', '9', 'SH', '115', 'Perna de ALTA'],
    ['3', '14', 'SL', '95', 'Perna de BAIXA'],
    ['4', '19', 'SH+', '130', 'Quebra topo (> 115)'],
    ['5', '24', 'SL CHoCH', '50', 'Rompe SL inicial (< 85)'],
]

# Plotar tabelas
y_start = 0.80
cell_height = 0.11

# BULLISH
fig.text(0.5, y_start + 0.05, 'PADRÃO BULLISH', ha='center', fontsize=13, fontweight='bold', color='#00AA00')
for i, row in enumerate(bullish_data):
    y = y_start - (i * cell_height)
    if i == 0:
        for j, cell in enumerate(row):
            fig.text(0.1 + j*0.18, y, cell, fontsize=11, fontweight='bold', ha='center', 
                    bbox=dict(boxstyle='round', facecolor='#00AA00', alpha=0.3))
    else:
        for j, cell in enumerate(row):
            fig.text(0.1 + j*0.18, y, str(cell), fontsize=10, ha='center')

# BEARISH
y_start = 0.40
fig.text(0.5, y_start + 0.05, 'PADRÃO BEARISH', ha='center', fontsize=13, fontweight='bold', color='#0066FF')
for i, row in enumerate(bearish_data):
    y = y_start - (i * cell_height)
    if i == 0:
        for j, cell in enumerate(row):
            fig.text(0.1 + j*0.18, y, cell, fontsize=11, fontweight='bold', ha='center',
                    bbox=dict(boxstyle='round', facecolor='#0066FF', alpha=0.3))
    else:
        for j, cell in enumerate(row):
            fig.text(0.1 + j*0.18, y, str(cell), fontsize=10, ha='center')

# Legenda
fig.text(0.5, 0.02, 'SH = Swing High | SL = Swing Low | BOS = Break of Structure | CHoCH = Change of Character', 
         ha='center', fontsize=10, style='italic', color='#666666')

plt.savefig('/home/ubuntu/ultimate_SMC/poi_patterns_summary.png', dpi=150, bbox_inches='tight')
print("✓ Resumo salvo: poi_patterns_summary.png")
plt.close()

print("\n✓ Visualizações criadas com sucesso!")
