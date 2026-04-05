"""
Visualização Comparativa Multi-Timeframe
"""

import json
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# Carregar resultados
with open('backtest_multi_timeframe_results.json', 'r') as f:
    results = json.load(f)

# Criar figura com múltiplos subplots
fig = plt.figure(figsize=(16, 12))
fig.suptitle('Backtest Multi-Timeframe - SMC Engine V3', fontsize=16, fontweight='bold')

# 1. Comparação de Order Blocks
ax1 = plt.subplot(2, 3, 1)
timeframes = [r['timeframe'] for r in results]
obs_total = [r['order_blocks'] for r in results]
obs_active = [r['order_blocks_active'] for r in results]
obs_mitigated = [r['order_blocks_mitigated'] for r in results]

x = np.arange(len(timeframes))
width = 0.35

bars1 = ax1.bar(x - width/2, obs_active, width, label='Ativos', color='#00AA00', alpha=0.8)
bars2 = ax1.bar(x + width/2, obs_mitigated, width, label='Mitigados', color='#FF0000', alpha=0.8)

ax1.set_xlabel('Timeframe', fontweight='bold')
ax1.set_ylabel('Quantidade', fontweight='bold')
ax1.set_title('Order Blocks por Timeframe', fontweight='bold')
ax1.set_xticks(x)
ax1.set_xticklabels(timeframes)
ax1.legend()
ax1.grid(True, alpha=0.3, axis='y')

# Adicionar valores nas barras
for bar in bars1:
    height = bar.get_height()
    if height > 0:
        ax1.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height)}', ha='center', va='bottom', fontsize=9)
for bar in bars2:
    height = bar.get_height()
    if height > 0:
        ax1.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height)}', ha='center', va='bottom', fontsize=9)

# 2. Comparação de Swings
ax2 = plt.subplot(2, 3, 2)
swings_high = [r['swings_high'] for r in results]
swings_low = [r['swings_low'] for r in results]

bars1 = ax2.bar(x - width/2, swings_high, width, label='Swing High', color='#FF6B00', alpha=0.8)
bars2 = ax2.bar(x + width/2, swings_low, width, label='Swing Low', color='#0066FF', alpha=0.8)

ax2.set_xlabel('Timeframe', fontweight='bold')
ax2.set_ylabel('Quantidade', fontweight='bold')
ax2.set_title('Swings Detectados por Timeframe', fontweight='bold')
ax2.set_xticks(x)
ax2.set_xticklabels(timeframes)
ax2.legend()
ax2.grid(True, alpha=0.3, axis='y')

# Adicionar valores nas barras
for bar in bars1:
    height = bar.get_height()
    if height > 0:
        ax2.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height)}', ha='center', va='bottom', fontsize=9)
for bar in bars2:
    height = bar.get_height()
    if height > 0:
        ax2.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height)}', ha='center', va='bottom', fontsize=9)

# 3. Comparação de Trades
ax3 = plt.subplot(2, 3, 3)
total_trades = [r['total_trades'] for r in results]
winning_trades = [r['winning_trades'] for r in results]
losing_trades = [r['losing_trades'] for r in results]

bars1 = ax3.bar(x - width/2, winning_trades, width, label='Ganhos', color='#00AA00', alpha=0.8)
bars2 = ax3.bar(x + width/2, losing_trades, width, label='Perdidos', color='#FF0000', alpha=0.8)

ax3.set_xlabel('Timeframe', fontweight='bold')
ax3.set_ylabel('Quantidade', fontweight='bold')
ax3.set_title('Trades por Timeframe', fontweight='bold')
ax3.set_xticks(x)
ax3.set_xticklabels(timeframes)
ax3.legend()
ax3.grid(True, alpha=0.3, axis='y')

# Adicionar valores nas barras
for bar in bars1:
    height = bar.get_height()
    if height > 0:
        ax3.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height)}', ha='center', va='bottom', fontsize=9)
for bar in bars2:
    height = bar.get_height()
    if height > 0:
        ax3.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height)}', ha='center', va='bottom', fontsize=9)

# 4. Win Rate
ax4 = plt.subplot(2, 3, 4)
win_rates = [r['win_rate'] for r in results]
colors = ['#00AA00' if wr > 0 else '#CCCCCC' for wr in win_rates]
bars = ax4.bar(timeframes, win_rates, color=colors, alpha=0.8)

ax4.set_ylabel('Win Rate (%)', fontweight='bold')
ax4.set_title('Win Rate por Timeframe', fontweight='bold')
ax4.set_ylim(0, 110)
ax4.grid(True, alpha=0.3, axis='y')

# Adicionar valores nas barras
for bar, wr in zip(bars, win_rates):
    height = bar.get_height()
    ax4.text(bar.get_x() + bar.get_width()/2., height,
            f'{wr:.1f}%', ha='center', va='bottom', fontsize=9, fontweight='bold')

# 5. Total de Pontos
ax5 = plt.subplot(2, 3, 5)
total_points = [r['total_points'] for r in results]
colors = ['#00AA00' if tp > 0 else '#CCCCCC' for tp in total_points]
bars = ax5.bar(timeframes, total_points, color=colors, alpha=0.8)

ax5.set_ylabel('Pontos', fontweight='bold')
ax5.set_title('Total de Pontos por Timeframe', fontweight='bold')
ax5.grid(True, alpha=0.3, axis='y')

# Adicionar valores nas barras
for bar, tp in zip(bars, total_points):
    height = bar.get_height()
    if height != 0:
        ax5.text(bar.get_x() + bar.get_width()/2., height,
                f'{tp:.1f}', ha='center', va='bottom', fontsize=9, fontweight='bold')

# 6. Expectancy (R)
ax6 = plt.subplot(2, 3, 6)
expectancy = [r['expectancy'] for r in results]
colors = ['#00AA00' if e > 0 else '#CCCCCC' for e in expectancy]
bars = ax6.bar(timeframes, expectancy, color=colors, alpha=0.8)

ax6.set_ylabel('Expectancy (R)', fontweight='bold')
ax6.set_title('Expectancy por Timeframe', fontweight='bold')
ax6.grid(True, alpha=0.3, axis='y')

# Adicionar valores nas barras
for bar, e in zip(bars, expectancy):
    height = bar.get_height()
    if height != 0:
        ax6.text(bar.get_x() + bar.get_width()/2., height,
                f'{e:.2f}R', ha='center', va='bottom', fontsize=9, fontweight='bold')

plt.tight_layout()
plt.savefig('/home/ubuntu/ultimate_SMC/backtest_multi_timeframe_comparison.png', dpi=150, bbox_inches='tight')
print("✓ Visualização salva: backtest_multi_timeframe_comparison.png")
plt.close()

# Criar tabela resumida
fig, ax = plt.subplots(figsize=(16, 8))
ax.axis('off')

fig.text(0.5, 0.95, 'Backtest Multi-Timeframe - Resumo Completo', 
         ha='center', fontsize=16, fontweight='bold')

# Preparar dados da tabela
table_data = []
table_data.append(['TF', 'Candles', 'SH', 'SL', 'OB', 'OB Ativos', 'Trades', 'Ganhos', 'Perdidos', 'Pontos', 'Win Rate', 'Expectancy'])

for r in results:
    table_data.append([
        r['timeframe'],
        str(r['candles_count']),
        str(r['swings_high']),
        str(r['swings_low']),
        str(r['order_blocks']),
        str(r['order_blocks_active']),
        str(r['total_trades']),
        str(r['winning_trades']),
        str(r['losing_trades']),
        f"{r['total_points']:.2f}",
        f"{r['win_rate']:.1f}%",
        f"{r['expectancy']:.2f}R",
    ])

# Plotar tabela
cell_height = 0.08
y_start = 0.85

for i, row in enumerate(table_data):
    y = y_start - (i * cell_height)
    
    # Cor de fundo para header
    if i == 0:
        for j, cell in enumerate(row):
            fig.text(0.05 + j*0.077, y, cell, fontsize=10, fontweight='bold', ha='left',
                    bbox=dict(boxstyle='round', facecolor='#0066FF', alpha=0.3))
    else:
        # Alternar cores de linha
        bg_color = '#F0F0F0' if i % 2 == 0 else 'white'
        for j, cell in enumerate(row):
            # Destacar M1 (primeira linha de dados)
            if i == 1:
                cell_color = '#00AA00'
                alpha = 0.2
            else:
                cell_color = '#CCCCCC'
                alpha = 0.1
            
            fig.text(0.05 + j*0.077, y, str(cell), fontsize=9, ha='left',
                    bbox=dict(boxstyle='round', facecolor=cell_color, alpha=alpha))

# Adicionar legenda
fig.text(0.5, 0.02, 'TF=Timeframe | SH=Swing High | SL=Swing Low | OB=Order Block | Destaque em verde: M1 (timeframe com dados suficientes)', 
         ha='center', fontsize=9, style='italic', color='#666666')

plt.savefig('/home/ubuntu/ultimate_SMC/backtest_multi_timeframe_table.png', dpi=150, bbox_inches='tight')
print("✓ Tabela salva: backtest_multi_timeframe_table.png")
plt.close()

print("\n✓ Visualizações criadas com sucesso!")
print("\nRESUMO DOS RESULTADOS:")
print("="*80)
print(f"M1 (Timeframe com dados suficientes):")
print(f"  - Order Blocks: {results[0]['order_blocks']} detectados ({results[0]['order_blocks_active']} ativos)")
print(f"  - Trades: {results[0]['total_trades']} (Ganhos: {results[0]['winning_trades']}, Perdidos: {results[0]['losing_trades']})")
print(f"  - Performance: {results[0]['total_points']:.2f} pontos, Win Rate {results[0]['win_rate']:.1f}%, Expectancy {results[0]['expectancy']:.2f}R")
print(f"\nTimeframes maiores (M5-D1):")
print(f"  - Dados insuficientes para análise (agregação resulta em poucos candles)")
print(f"  - Recomendação: Usar dataset maior (semanas/meses de dados) para análise multi-timeframe")
