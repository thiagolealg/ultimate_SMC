"""
Geração de Imagens de Trades - Entrada na Linha do Meio do OB
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import os
from smc_entry_midline import OrderBlockStrategyMidline, SignalDirection


def load_data():
    """Carrega dados"""
    df = pd.read_csv('/home/ubuntu/smc_enhanced/data.csv')
    df.columns = [c.lower() for c in df.columns]
    df['time'] = pd.to_datetime(df['time'])
    df.set_index('time', inplace=True)
    if 'volume' not in df.columns:
        df['volume'] = df.get('tick_volume', df.get('real_volume', 1.0))
    return df


def plot_candlestick(ax, df, start_idx, end_idx):
    """Plota candlesticks"""
    for i in range(start_idx, min(end_idx, len(df))):
        idx = i - start_idx
        open_price = df['open'].iloc[i]
        high = df['high'].iloc[i]
        low = df['low'].iloc[i]
        close = df['close'].iloc[i]
        
        color = 'green' if close >= open_price else 'red'
        
        # Wick
        ax.plot([idx, idx], [low, high], color='black', linewidth=0.5)
        
        # Body
        body_bottom = min(open_price, close)
        body_height = abs(close - open_price)
        if body_height == 0:
            body_height = 0.1
        rect = Rectangle((idx - 0.3, body_bottom), 0.6, body_height, 
                         facecolor=color, edgecolor='black', linewidth=0.5)
        ax.add_patch(rect)


def generate_trade_images(num_images=20):
    """
    Gera imagens de trades vencedores com entrada na linha do meio
    """
    print("=" * 70)
    print(f"GERANDO {num_images} IMAGENS DE TRADES VENCEDORES")
    print("Entrada na LINHA DO MEIO do Order Block")
    print("=" * 70)
    
    df = load_data()
    df = df.tail(50000)  # Usar últimos 50k candles
    
    strategy = OrderBlockStrategyMidline(
        df,
        swing_length=5,
        risk_reward_ratio=1.0,
        min_confidence=30.0,
        entry_delay_candles=1,
        use_not_mitigated_filter=True,
    )
    
    signals = strategy.generate_signals()
    results, stats = strategy.backtest(signals)
    
    # Filtrar apenas trades vencedores
    winners = [r for r in results if r.hit_tp]
    
    print(f"\nTotal de trades: {len(results)}")
    print(f"Total de trades vencedores: {len(winners)}")
    print(f"Win Rate: {stats['win_rate']:.1f}%")
    print(f"\nGerando {min(num_images, len(winners))} imagens...")
    
    # Criar diretório para imagens
    output_dir = '/home/ubuntu/smc_enhanced/trade_images_midline'
    os.makedirs(output_dir, exist_ok=True)
    
    # Selecionar trades para visualização (espaçados)
    step = max(1, len(winners) // num_images)
    selected_trades = winners[::step][:num_images]
    
    for i, result in enumerate(selected_trades):
        signal = result.signal
        
        # Definir janela de visualização
        candles_before = 25
        candles_after = 15
        
        start_idx = max(0, signal.ob_candle_index - candles_before)
        end_idx = min(len(df), result.exit_index + candles_after)
        
        # Criar figura
        fig, ax = plt.subplots(figsize=(16, 9))
        
        # Plotar candlesticks
        plot_candlestick(ax, df, start_idx, end_idx)
        
        # Calcular posições relativas
        ob_candle_rel = signal.ob_candle_index - start_idx
        signal_candle_rel = signal.signal_candle_index - start_idx
        entry_candle_rel = signal.index - start_idx
        exit_candle_rel = result.exit_index - start_idx
        
        # Calcular linha do meio
        midline = (signal.ob_top + signal.ob_bottom) / 2
        
        # Desenhar Order Block (região)
        ob_width = exit_candle_rel - ob_candle_rel + 2
        ob_color = 'lightblue' if signal.direction == SignalDirection.BULLISH else 'lightcoral'
        ob_rect = Rectangle((ob_candle_rel - 0.5, signal.ob_bottom), 
                            ob_width, signal.ob_top - signal.ob_bottom,
                            facecolor=ob_color, alpha=0.3, 
                            edgecolor='blue' if signal.direction == SignalDirection.BULLISH else 'red',
                            linewidth=2, linestyle='--')
        ax.add_patch(ob_rect)
        
        # LINHA AZUL - Entrada no meio do OB
        ax.axhline(y=midline, color='blue', linestyle='-', linewidth=2, 
                   label=f'Entrada (Meio OB): {midline:.2f}')
        
        # Linha de Stop Loss
        ax.axhline(y=signal.stop_loss, color='red', linestyle='--', linewidth=1.5,
                   label=f'Stop Loss: {signal.stop_loss:.2f}')
        
        # Linha de Take Profit
        ax.axhline(y=signal.take_profit, color='green', linestyle='--', linewidth=1.5,
                   label=f'Take Profit: {signal.take_profit:.2f}')
        
        # Marcar candle do OB
        ax.annotate('OB', xy=(ob_candle_rel, signal.ob_top), 
                   xytext=(ob_candle_rel, signal.ob_top + (signal.ob_top - signal.ob_bottom) * 0.3),
                   fontsize=10, ha='center', color='purple',
                   arrowprops=dict(arrowstyle='->', color='purple'))
        
        # Marcar entrada (no candle que tocou a linha do meio)
        marker = '^' if signal.direction == SignalDirection.BULLISH else 'v'
        ax.scatter([entry_candle_rel], [signal.entry_price], color='blue', s=150, zorder=5, marker=marker)
        ax.annotate('ENTRADA', xy=(entry_candle_rel, signal.entry_price),
                   xytext=(entry_candle_rel + 1.5, signal.entry_price),
                   fontsize=9, ha='left', color='blue', fontweight='bold')
        
        # Marcar saída (TP)
        ax.scatter([exit_candle_rel], [result.exit_price], color='green', s=150, zorder=5, marker='*')
        ax.annotate('TP HIT', xy=(exit_candle_rel, result.exit_price),
                   xytext=(exit_candle_rel + 1.5, result.exit_price),
                   fontsize=9, ha='left', color='green', fontweight='bold')
        
        # Configurar eixos
        direction_str = "LONG" if signal.direction == SignalDirection.BULLISH else "SHORT"
        ax.set_title(f'Trade #{i+1} - {direction_str} | ENTRADA NA LINHA AZUL (MEIO DO OB)\n'
                    f'Entrada: {signal.entry_price:.2f} | TP: {signal.take_profit:.2f} | SL: {signal.stop_loss:.2f}\n'
                    f'Lucro: {result.profit_loss:.2f} pontos | Duração: {result.duration_candles} candles',
                    fontsize=12, fontweight='bold')
        
        ax.set_xlabel('Candles')
        ax.set_ylabel('Preço')
        ax.legend(loc='upper left', fontsize=9)
        ax.grid(True, alpha=0.3)
        
        # Ajustar limites do eixo Y
        y_min = min(signal.stop_loss, df['low'].iloc[start_idx:end_idx].min()) * 0.9995
        y_max = max(signal.take_profit, df['high'].iloc[start_idx:end_idx].max()) * 1.0005
        ax.set_ylim(y_min, y_max)
        ax.set_xlim(-1, end_idx - start_idx + 1)
        
        # Salvar imagem
        filepath = f'{output_dir}/trade_{i+1:02d}_{direction_str}.png'
        plt.tight_layout()
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"   Imagem {i+1}/{num_images} salva: {filepath}")
    
    print(f"\n✓ {num_images} imagens geradas em: {output_dir}")
    
    return output_dir


def main():
    output_dir = generate_trade_images(20)
    
    print("\n" + "=" * 70)
    print("RESUMO")
    print("=" * 70)
    print(f"""
    LÓGICA DE ENTRADA:
    
    1. Order Block é identificado e confirmado
    2. Calculamos a LINHA DO MEIO: (ob_top + ob_bottom) / 2
    3. Esperamos o preço TOCAR essa linha (candle com low <= midline <= high)
    4. Entrada EXATA no preço da linha do meio
    5. Stop Loss abaixo/acima do OB
    6. Take Profit projetado a partir da entrada
    
    As imagens mostram:
    - Área colorida: Região do Order Block
    - LINHA AZUL: Preço de entrada (meio do OB)
    - Linha verde tracejada: Take Profit
    - Linha vermelha tracejada: Stop Loss
    - Triângulo azul: Ponto de entrada
    - Estrela verde: Ponto de saída (TP atingido)
    """)


if __name__ == "__main__":
    main()
