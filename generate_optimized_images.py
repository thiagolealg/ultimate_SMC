"""
Geração de Imagens de Trades - Versão Otimizada
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import os
from smc_optimized_final import OrderBlockStrategyOptimized, SignalDirection


def load_data():
    df = pd.read_csv('/home/ubuntu/smc_enhanced/data.csv')
    df.columns = [c.lower() for c in df.columns]
    df['time'] = pd.to_datetime(df['time'])
    df.set_index('time', inplace=True)
    if 'volume' not in df.columns:
        df['volume'] = df.get('tick_volume', df.get('real_volume', 1.0))
    return df


def plot_candlestick(ax, df, start_idx, end_idx):
    for i in range(start_idx, min(end_idx, len(df))):
        idx = i - start_idx
        open_price = df['open'].iloc[i]
        high = df['high'].iloc[i]
        low = df['low'].iloc[i]
        close = df['close'].iloc[i]
        
        color = 'green' if close >= open_price else 'red'
        ax.plot([idx, idx], [low, high], color='black', linewidth=0.5)
        
        body_bottom = min(open_price, close)
        body_height = abs(close - open_price)
        if body_height == 0:
            body_height = 0.1
        rect = Rectangle((idx - 0.3, body_bottom), 0.6, body_height, 
                         facecolor=color, edgecolor='black', linewidth=0.5)
        ax.add_patch(rect)


def generate_trade_images(num_images=20):
    print("=" * 70)
    print(f"GERANDO {num_images} IMAGENS DE TRADES - VERSÃO OTIMIZADA")
    print("=" * 70)
    
    df = load_data()
    df = df.tail(50000)
    
    strategy = OrderBlockStrategyOptimized(
        df,
        swing_length=5,
        risk_reward_ratio=1.0,  # RR 1:1 para Win Rate 71.8%
        entry_delay_candles=1,
        min_volume_ratio=1.5,
        min_ob_size_atr=0.5,
    )
    
    signals = strategy.generate_signals()
    results, stats = strategy.backtest(signals)
    
    winners = [r for r in results if r.hit_tp]
    
    print(f"\nTotal de trades: {len(results)}")
    print(f"Total de trades vencedores: {len(winners)}")
    print(f"Win Rate: {stats['win_rate']:.1f}%")
    print(f"\nGerando {min(num_images, len(winners))} imagens...")
    
    output_dir = '/home/ubuntu/smc_enhanced/trade_images_optimized'
    os.makedirs(output_dir, exist_ok=True)
    
    step = max(1, len(winners) // num_images)
    selected_trades = winners[::step][:num_images]
    
    for i, result in enumerate(selected_trades):
        signal = result.signal
        
        candles_before = 25
        candles_after = 15
        
        start_idx = max(0, signal.ob_candle_index - candles_before)
        end_idx = min(len(df), result.exit_index + candles_after)
        
        fig, ax = plt.subplots(figsize=(16, 9))
        
        plot_candlestick(ax, df, start_idx, end_idx)
        
        ob_candle_rel = signal.ob_candle_index - start_idx
        entry_candle_rel = signal.index - start_idx
        exit_candle_rel = result.exit_index - start_idx
        
        midline = (signal.ob_top + signal.ob_bottom) / 2
        
        ob_width = exit_candle_rel - ob_candle_rel + 2
        ob_color = 'lightblue' if signal.direction == SignalDirection.BULLISH else 'lightcoral'
        ob_rect = Rectangle((ob_candle_rel - 0.5, signal.ob_bottom), 
                            ob_width, signal.ob_top - signal.ob_bottom,
                            facecolor=ob_color, alpha=0.3, 
                            edgecolor='blue' if signal.direction == SignalDirection.BULLISH else 'red',
                            linewidth=2, linestyle='--')
        ax.add_patch(ob_rect)
        
        ax.axhline(y=midline, color='blue', linestyle='-', linewidth=2, 
                   label=f'Entrada (Meio OB): {midline:.2f}')
        ax.axhline(y=signal.stop_loss, color='red', linestyle='--', linewidth=1.5,
                   label=f'Stop Loss: {signal.stop_loss:.2f}')
        ax.axhline(y=signal.take_profit, color='green', linestyle='--', linewidth=1.5,
                   label=f'Take Profit: {signal.take_profit:.2f}')
        
        ax.annotate('OB', xy=(ob_candle_rel, signal.ob_top), 
                   xytext=(ob_candle_rel, signal.ob_top + (signal.ob_top - signal.ob_bottom) * 0.3),
                   fontsize=10, ha='center', color='purple',
                   arrowprops=dict(arrowstyle='->', color='purple'))
        
        marker = '^' if signal.direction == SignalDirection.BULLISH else 'v'
        ax.scatter([entry_candle_rel], [signal.entry_price], color='blue', s=150, zorder=5, marker=marker)
        ax.annotate('ENTRADA', xy=(entry_candle_rel, signal.entry_price),
                   xytext=(entry_candle_rel + 1.5, signal.entry_price),
                   fontsize=9, ha='left', color='blue', fontweight='bold')
        
        ax.scatter([exit_candle_rel], [result.exit_price], color='green', s=150, zorder=5, marker='*')
        ax.annotate('TP HIT', xy=(exit_candle_rel, result.exit_price),
                   xytext=(exit_candle_rel + 1.5, result.exit_price),
                   fontsize=9, ha='left', color='green', fontweight='bold')
        
        direction_str = "LONG" if signal.direction == SignalDirection.BULLISH else "SHORT"
        ax.set_title(f'Trade #{i+1} - {direction_str} | VERSÃO OTIMIZADA (Vol+Size Filter)\n'
                    f'Entrada: {signal.entry_price:.2f} | TP: {signal.take_profit:.2f} | SL: {signal.stop_loss:.2f}\n'
                    f'Lucro: {result.profit_loss:.2f} pts | Vol Ratio: {signal.volume_ratio:.1f}x | OB Size: {signal.ob_size:.2f}',
                    fontsize=12, fontweight='bold')
        
        ax.set_xlabel('Candles')
        ax.set_ylabel('Preço')
        ax.legend(loc='upper left', fontsize=9)
        ax.grid(True, alpha=0.3)
        
        y_min = min(signal.stop_loss, df['low'].iloc[start_idx:end_idx].min()) * 0.9995
        y_max = max(signal.take_profit, df['high'].iloc[start_idx:end_idx].max()) * 1.0005
        ax.set_ylim(y_min, y_max)
        ax.set_xlim(-1, end_idx - start_idx + 1)
        
        filepath = f'{output_dir}/trade_{i+1:02d}_{direction_str}.png'
        plt.tight_layout()
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"   Imagem {i+1}/{num_images} salva")
    
    print(f"\n✓ {num_images} imagens geradas em: {output_dir}")
    return output_dir


if __name__ == "__main__":
    generate_trade_images(20)
