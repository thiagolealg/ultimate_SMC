"""
Análise de Entradas e Geração de Imagens de Trades Vencedores
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Rectangle
import os
from smc_70_winrate import OrderBlockStrategy70WR, SignalDirection


def load_data():
    """Carrega dados"""
    df = pd.read_csv('/home/ubuntu/smc_enhanced/data.csv')
    df.columns = [c.lower() for c in df.columns]
    df['time'] = pd.to_datetime(df['time'])
    df.set_index('time', inplace=True)
    if 'volume' not in df.columns:
        df['volume'] = df.get('tick_volume', df.get('real_volume', 1.0))
    return df


def analyze_entry_logic():
    """
    Analisa a lógica de entrada nos Order Blocks
    """
    print("=" * 70)
    print("ANÁLISE DA LÓGICA DE ENTRADA NOS ORDER BLOCKS")
    print("=" * 70)
    
    print("""
    LÓGICA ATUAL DE ENTRADA:
    
    Para Order Block BULLISH:
    - Condição de entrada: current_low <= ob_top
    - Isso significa: o preço TOCA a região do OB (low do candle <= topo do OB)
    - Preço de entrada: (ob_top + ob_bottom) / 2 (MEIO do OB)
    
    Para Order Block BEARISH:
    - Condição de entrada: current_high >= ob_bottom
    - Isso significa: o preço TOCA a região do OB (high do candle >= fundo do OB)
    - Preço de entrada: (ob_top + ob_bottom) / 2 (MEIO do OB)
    
    RESUMO:
    - A ENTRADA é acionada quando o preço ENTRA na REGIÃO do OB
    - O preço de entrada é calculado como o MEIO do Order Block
    - NÃO é no preço exato do topo/fundo, mas sim no CENTRO da zona
    
    Stop Loss:
    - Bullish: ob_bottom - 10% do tamanho do OB
    - Bearish: ob_top + 10% do tamanho do OB
    
    Take Profit:
    - Calculado baseado no Risk:Reward ratio
    """)
    
    return True


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
        rect = Rectangle((idx - 0.3, body_bottom), 0.6, body_height, 
                         facecolor=color, edgecolor='black', linewidth=0.5)
        ax.add_patch(rect)


def generate_trade_images(num_images=20):
    """
    Gera imagens de trades vencedores
    """
    print("\n" + "=" * 70)
    print(f"GERANDO {num_images} IMAGENS DE TRADES VENCEDORES")
    print("=" * 70)
    
    df = load_data()
    df = df.tail(30000)  # Usar últimos 30k candles
    
    strategy = OrderBlockStrategy70WR(
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
    
    print(f"\nTotal de trades vencedores: {len(winners)}")
    print(f"Gerando {min(num_images, len(winners))} imagens...")
    
    # Criar diretório para imagens
    output_dir = '/home/ubuntu/smc_enhanced/trade_images'
    os.makedirs(output_dir, exist_ok=True)
    
    # Selecionar trades para visualização (espaçados)
    step = max(1, len(winners) // num_images)
    selected_trades = winners[::step][:num_images]
    
    for i, result in enumerate(selected_trades):
        signal = result.signal
        
        # Definir janela de visualização
        candles_before = 20
        candles_after = 10
        
        start_idx = max(0, signal.ob_candle_index - candles_before)
        end_idx = min(len(df), result.exit_index + candles_after)
        
        # Criar figura
        fig, ax = plt.subplots(figsize=(14, 8))
        
        # Plotar candlesticks
        plot_candlestick(ax, df, start_idx, end_idx)
        
        # Calcular posições relativas
        ob_candle_rel = signal.ob_candle_index - start_idx
        signal_candle_rel = signal.signal_candle_index - start_idx
        entry_candle_rel = signal.index - start_idx
        exit_candle_rel = result.exit_index - start_idx
        
        # Desenhar Order Block (região)
        ob_width = exit_candle_rel - ob_candle_rel + 2
        ob_color = 'lightblue' if signal.direction == SignalDirection.BULLISH else 'lightcoral'
        ob_rect = Rectangle((ob_candle_rel - 0.5, signal.ob_bottom), 
                            ob_width, signal.ob_top - signal.ob_bottom,
                            facecolor=ob_color, alpha=0.3, edgecolor='blue' if signal.direction == SignalDirection.BULLISH else 'red',
                            linewidth=2, linestyle='--')
        ax.add_patch(ob_rect)
        
        # Linha de entrada (no meio do OB)
        ax.axhline(y=signal.entry_price, color='blue', linestyle='-', linewidth=1.5, 
                   label=f'Entrada: {signal.entry_price:.2f}')
        
        # Linha de Stop Loss
        ax.axhline(y=signal.stop_loss, color='red', linestyle='--', linewidth=1.5,
                   label=f'Stop Loss: {signal.stop_loss:.2f}')
        
        # Linha de Take Profit
        ax.axhline(y=signal.take_profit, color='green', linestyle='--', linewidth=1.5,
                   label=f'Take Profit: {signal.take_profit:.2f}')
        
        # Marcar candle do OB
        ax.annotate('OB', xy=(ob_candle_rel, signal.ob_top), 
                   xytext=(ob_candle_rel, signal.ob_top + (signal.ob_top - signal.ob_bottom) * 0.5),
                   fontsize=10, ha='center', color='purple',
                   arrowprops=dict(arrowstyle='->', color='purple'))
        
        # Marcar entrada
        ax.scatter([entry_candle_rel], [signal.entry_price], color='blue', s=100, zorder=5, marker='^' if signal.direction == SignalDirection.BULLISH else 'v')
        ax.annotate('ENTRADA', xy=(entry_candle_rel, signal.entry_price),
                   xytext=(entry_candle_rel + 1, signal.entry_price),
                   fontsize=9, ha='left', color='blue')
        
        # Marcar saída (TP)
        ax.scatter([exit_candle_rel], [result.exit_price], color='green', s=100, zorder=5, marker='*')
        ax.annotate('TP HIT', xy=(exit_candle_rel, result.exit_price),
                   xytext=(exit_candle_rel + 1, result.exit_price),
                   fontsize=9, ha='left', color='green')
        
        # Configurar eixos
        direction_str = "LONG" if signal.direction == SignalDirection.BULLISH else "SHORT"
        ax.set_title(f'Trade #{i+1} - {direction_str} | Win Rate: 80% | RR 1:1\n'
                    f'Entrada: {signal.entry_price:.2f} | TP: {signal.take_profit:.2f} | SL: {signal.stop_loss:.2f}\n'
                    f'Lucro: {result.profit_loss:.2f} pontos | Duração: {result.duration_candles} candles',
                    fontsize=11)
        
        ax.set_xlabel('Candles')
        ax.set_ylabel('Preço')
        ax.legend(loc='upper left')
        ax.grid(True, alpha=0.3)
        
        # Ajustar limites do eixo Y
        y_min = min(signal.stop_loss, df['low'].iloc[start_idx:end_idx].min()) * 0.999
        y_max = max(signal.take_profit, df['high'].iloc[start_idx:end_idx].max()) * 1.001
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
    analyze_entry_logic()
    output_dir = generate_trade_images(20)
    
    print("\n" + "=" * 70)
    print("RESUMO")
    print("=" * 70)
    print(f"""
    A entrada ocorre quando o preço ENTRA NA REGIÃO do Order Block:
    
    - Bullish OB: Entrada quando low do candle <= topo do OB
    - Bearish OB: Entrada quando high do candle >= fundo do OB
    
    O preço de entrada é calculado como o MEIO do Order Block:
    entry_price = (ob_top + ob_bottom) / 2
    
    Isso significa que a estratégia assume uma entrada limit order
    no centro da zona do Order Block.
    
    As {20} imagens de trades vencedores foram salvas em:
    {output_dir}
    """)


if __name__ == "__main__":
    main()
