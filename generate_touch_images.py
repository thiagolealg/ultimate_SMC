"""
Gerar imagens de trades comprovando o toque na linha do Order Block
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
import os
from smc_touch_validated import SMCStrategyTouchValidated, SignalDirection, PatternType

# Criar diretório para imagens
os.makedirs('/home/ubuntu/smc_enhanced/trade_images_touch', exist_ok=True)

# Carregar dados
df = pd.read_csv('/home/ubuntu/smc_enhanced/data.csv')
df.columns = [c.lower() for c in df.columns]
df['time'] = pd.to_datetime(df['time'])
df.set_index('time', inplace=True)
if 'volume' not in df.columns:
    df['volume'] = df.get('tick_volume', df.get('real_volume', 1.0))

print(f"Dados: {len(df)} candles")

# Criar estratégia
strategy = SMCStrategyTouchValidated(
    df,
    swing_length=5,
    risk_reward_ratio=1.0,
    entry_delay_candles=1,
    use_not_mitigated_filter=True,
    min_volume_ratio=1.5,
    min_ob_size_atr=0.5,
)

signals = strategy.generate_signals()
results, stats = strategy.backtest(signals)

print(f"Total de trades: {len(results)}")
print(f"Win Rate: {stats['win_rate']:.1f}%")

# Filtrar apenas vencedores
winning_trades = [r for r in results if r.hit_tp]
print(f"Trades vencedores: {len(winning_trades)}")

# Gerar 20 imagens de trades vencedores
num_images = min(20, len(winning_trades))
selected_trades = winning_trades[:num_images]

for idx, result in enumerate(selected_trades):
    signal = result.signal
    
    # Janela de visualização
    start_idx = max(0, signal.ob_candle_index - 10)
    end_idx = min(len(df), result.exit_index + 10)
    
    df_window = df.iloc[start_idx:end_idx].copy()
    df_window = df_window.reset_index()
    
    # Criar figura
    fig, ax = plt.subplots(figsize=(14, 8))
    
    # Plotar candles
    for i, row in df_window.iterrows():
        color = 'green' if row['close'] >= row['open'] else 'red'
        
        # Corpo do candle
        ax.add_patch(mpatches.Rectangle(
            (i - 0.3, min(row['open'], row['close'])),
            0.6,
            abs(row['close'] - row['open']) or 0.01,
            facecolor=color,
            edgecolor='black',
            linewidth=0.5
        ))
        
        # Pavio
        ax.plot([i, i], [row['low'], row['high']], color='black', linewidth=0.5)
    
    # Índices relativos
    ob_rel_idx = signal.ob_candle_index - start_idx
    entry_rel_idx = signal.index - start_idx
    exit_rel_idx = result.exit_index - start_idx
    
    # Área do Order Block
    ob_color = 'lightblue' if signal.direction == SignalDirection.BULLISH else 'lightcoral'
    ax.axhspan(signal.ob_bottom, signal.ob_top, alpha=0.3, color=ob_color, label='Order Block')
    
    # LINHA DO MEIO (LINHA DE ENTRADA) - DESTACADA
    ax.axhline(y=signal.ob_midline, color='blue', linestyle='-', linewidth=2.5, label=f'Linha do Meio (Entrada): {signal.ob_midline:.2f}')
    
    # Linha de entrada (preço exato)
    ax.axhline(y=signal.entry_price, color='blue', linestyle='--', linewidth=1, alpha=0.5)
    
    # Take Profit
    ax.axhline(y=signal.take_profit, color='green', linestyle='--', linewidth=1.5, label=f'Take Profit: {signal.take_profit:.2f}')
    
    # Stop Loss
    ax.axhline(y=signal.stop_loss, color='red', linestyle='--', linewidth=1.5, label=f'Stop Loss: {signal.stop_loss:.2f}')
    
    # Marcar candle do OB
    if 0 <= ob_rel_idx < len(df_window):
        ax.axvline(x=ob_rel_idx, color='purple', linestyle=':', alpha=0.5, label='Candle OB')
    
    # Marcar entrada
    if 0 <= entry_rel_idx < len(df_window):
        entry_candle = df_window.iloc[entry_rel_idx]
        
        # Destacar o toque na linha
        if signal.direction == SignalDirection.BULLISH:
            # Para LONG: mostrar que o LOW tocou a linha
            ax.scatter([entry_rel_idx], [entry_candle['low']], marker='v', s=200, color='blue', 
                      zorder=5, label=f'LOW tocou linha: {entry_candle["low"]:.2f}')
            ax.scatter([entry_rel_idx], [signal.entry_price], marker='^', s=200, color='blue', 
                      zorder=5, edgecolors='black', linewidths=2, label=f'Entrada: {signal.entry_price:.2f}')
        else:
            # Para SHORT: mostrar que o HIGH tocou a linha
            ax.scatter([entry_rel_idx], [entry_candle['high']], marker='^', s=200, color='blue', 
                      zorder=5, label=f'HIGH tocou linha: {entry_candle["high"]:.2f}')
            ax.scatter([entry_rel_idx], [signal.entry_price], marker='v', s=200, color='blue', 
                      zorder=5, edgecolors='black', linewidths=2, label=f'Entrada: {signal.entry_price:.2f}')
    
    # Marcar saída
    if 0 <= exit_rel_idx < len(df_window):
        ax.scatter([exit_rel_idx], [result.exit_price], marker='*', s=300, color='lime', 
                  zorder=5, edgecolors='black', linewidths=1, label=f'Saída (TP): {result.exit_price:.2f}')
    
    # Adicionar seta mostrando o toque
    if 0 <= entry_rel_idx < len(df_window):
        entry_candle = df_window.iloc[entry_rel_idx]
        if signal.direction == SignalDirection.BULLISH:
            ax.annotate('', xy=(entry_rel_idx, signal.ob_midline), 
                       xytext=(entry_rel_idx, entry_candle['low']),
                       arrowprops=dict(arrowstyle='->', color='blue', lw=2))
        else:
            ax.annotate('', xy=(entry_rel_idx, signal.ob_midline), 
                       xytext=(entry_rel_idx, entry_candle['high']),
                       arrowprops=dict(arrowstyle='->', color='blue', lw=2))
    
    # Informações do trade
    direction_str = 'LONG' if signal.direction == SignalDirection.BULLISH else 'SHORT'
    patterns_str = ', '.join([p.value for p in signal.patterns_detected])
    
    info_text = (
        f"Trade #{idx+1} - {direction_str}\n"
        f"Padrões: {patterns_str}\n"
        f"Linha do Meio: {signal.ob_midline:.2f}\n"
        f"Entrada: {signal.entry_price:.2f}\n"
        f"Stop Loss: {signal.stop_loss:.2f}\n"
        f"Take Profit: {signal.take_profit:.2f}\n"
        f"Resultado: +{result.profit_loss_r:.1f}R\n"
        f"Duração: {result.duration_candles} candles\n"
        f"Toque: {signal.touch_validation.touch_type}"
    )
    
    ax.text(0.02, 0.98, info_text, transform=ax.transAxes, fontsize=9,
            verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
    
    # Configurar eixos
    ax.set_xlim(-1, len(df_window))
    
    # Calcular limites Y com margem
    y_min = min(df_window['low'].min(), signal.stop_loss) * 0.9995
    y_max = max(df_window['high'].max(), signal.take_profit) * 1.0005
    ax.set_ylim(y_min, y_max)
    
    ax.set_xlabel('Candles')
    ax.set_ylabel('Preço')
    ax.set_title(f'Trade {idx+1}: {direction_str} - Toque Validado na Linha do Meio')
    ax.legend(loc='upper right', fontsize=8)
    ax.grid(True, alpha=0.3)
    
    # Salvar
    filename = f'/home/ubuntu/smc_enhanced/trade_images_touch/trade_{idx+1:02d}_{direction_str}.png'
    plt.savefig(filename, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"Imagem salva: {filename}")

print(f"\n{num_images} imagens geradas em /home/ubuntu/smc_enhanced/trade_images_touch/")
