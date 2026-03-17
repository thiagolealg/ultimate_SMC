"""
Gerar imagens de trades mostrando todos os padrões SMC detectados
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
import os
from smc_complete import SMCComplete, SMCCompleteStrategy, SignalDirection, PatternType


def generate_pattern_images():
    """Gerar imagens de trades com padrões detectados"""
    
    # Carregar dados
    df = pd.read_csv('/home/ubuntu/smc_enhanced/data.csv')
    df.columns = [c.lower() for c in df.columns]
    df['time'] = pd.to_datetime(df['time'])
    df.set_index('time', inplace=True)
    if 'volume' not in df.columns:
        df['volume'] = df.get('tick_volume', df.get('real_volume', 1.0))
    
    # Usar amostra
    df = df.iloc[:30000].copy()
    
    print("Calculando indicadores SMC...")
    
    # Criar estratégia
    strategy = SMCCompleteStrategy(
        df,
        swing_length=5,
        risk_reward_ratio=1.0,
        entry_delay_candles=1,
        min_confidence=0.0,
    )
    
    signals = strategy.generate_signals()
    results, stats = strategy.backtest(signals)
    
    print(f"Total de sinais: {len(signals)}")
    print(f"Total de trades: {len(results)}")
    
    # Criar diretório para imagens
    output_dir = '/home/ubuntu/smc_enhanced/trade_images_patterns'
    os.makedirs(output_dir, exist_ok=True)
    
    # Filtrar trades vencedores com padrões interessantes
    winning_trades = [r for r in results if r.hit_tp]
    
    # Separar por padrões
    trades_with_sweep = [r for r in winning_trades if PatternType.LIQUIDITY_SWEEP in r.signal.patterns_detected]
    trades_with_spring = [r for r in winning_trades if PatternType.SPRING in r.signal.patterns_detected]
    trades_with_upthrust = [r for r in winning_trades if PatternType.UPTHRUST in r.signal.patterns_detected]
    trades_with_abc = [r for r in winning_trades if PatternType.ABC_CORRECTION in r.signal.patterns_detected]
    trades_with_fvg = [r for r in winning_trades if PatternType.FVG in r.signal.patterns_detected]
    trades_with_bos = [r for r in winning_trades if PatternType.BOS in r.signal.patterns_detected]
    trades_with_choch = [r for r in winning_trades if PatternType.CHOCH in r.signal.patterns_detected]
    
    print(f"\nTrades vencedores por padrão:")
    print(f"  SWEEP: {len(trades_with_sweep)}")
    print(f"  SPRING: {len(trades_with_spring)}")
    print(f"  UPTHRUST: {len(trades_with_upthrust)}")
    print(f"  ABC: {len(trades_with_abc)}")
    print(f"  FVG: {len(trades_with_fvg)}")
    print(f"  BOS: {len(trades_with_bos)}")
    print(f"  CHoCH: {len(trades_with_choch)}")
    
    def plot_trade(result, df, filename, title_extra=""):
        """Plotar um trade com todos os padrões"""
        signal = result.signal
        
        # Definir janela de visualização
        start_idx = max(0, signal.signal_candle_index - 30)
        end_idx = min(len(df), result.exit_index + 10)
        
        df_window = df.iloc[start_idx:end_idx].copy()
        df_window = df_window.reset_index()
        
        # Ajustar índices
        entry_idx_adj = result.entry_index - start_idx
        exit_idx_adj = result.exit_index - start_idx
        signal_idx_adj = signal.signal_candle_index - start_idx
        
        fig, ax = plt.subplots(figsize=(16, 10))
        
        # Plotar candlesticks
        for i in range(len(df_window)):
            color = 'green' if df_window['close'].iloc[i] >= df_window['open'].iloc[i] else 'red'
            
            # Corpo
            ax.bar(i, df_window['close'].iloc[i] - df_window['open'].iloc[i],
                   bottom=min(df_window['open'].iloc[i], df_window['close'].iloc[i]),
                   color=color, width=0.8, alpha=0.8)
            
            # Sombras
            ax.plot([i, i], [df_window['low'].iloc[i], df_window['high'].iloc[i]],
                    color=color, linewidth=1)
        
        # Plotar Order Block
        ob_start = max(0, signal.signal_candle_index - start_idx - 5)
        ob_end = min(len(df_window), exit_idx_adj + 5)
        
        ob_color = 'blue' if signal.direction == SignalDirection.BULLISH else 'red'
        ax.fill_between(range(ob_start, ob_end), 
                       signal.ob_bottom, signal.ob_top,
                       alpha=0.2, color=ob_color, label='Order Block')
        
        # Linha do meio (entrada)
        midline = (signal.ob_top + signal.ob_bottom) / 2
        ax.axhline(y=midline, color='blue', linestyle='-', linewidth=2, 
                   label=f'Entrada: {midline:.2f}')
        
        # Take Profit
        ax.axhline(y=signal.take_profit, color='green', linestyle='--', linewidth=2,
                   label=f'TP: {signal.take_profit:.2f}')
        
        # Stop Loss
        ax.axhline(y=signal.stop_loss, color='red', linestyle='--', linewidth=2,
                   label=f'SL: {signal.stop_loss:.2f}')
        
        # Marcar entrada
        ax.scatter([entry_idx_adj], [midline], color='blue', s=200, marker='^' if signal.direction == SignalDirection.BULLISH else 'v',
                   zorder=5, label='Entrada')
        
        # Marcar saída
        exit_price = signal.take_profit if result.hit_tp else signal.stop_loss
        ax.scatter([exit_idx_adj], [exit_price], color='green' if result.hit_tp else 'red', 
                   s=200, marker='*', zorder=5, label='Saída (TP)' if result.hit_tp else 'Saída (SL)')
        
        # Marcar sinal
        ax.axvline(x=signal_idx_adj, color='purple', linestyle=':', alpha=0.5, label='Sinal OB')
        
        # Título com padrões
        direction = "LONG" if signal.direction == SignalDirection.BULLISH else "SHORT"
        patterns = [p.value for p in signal.patterns_detected]
        resultado = "WIN" if result.hit_tp else "LOSS"
        
        title = f"{direction} - {resultado} | Confiança: {signal.confidence:.0f} | Alavancagem: {signal.leverage}x\n"
        title += f"Padrões: {', '.join(patterns)}"
        if title_extra:
            title += f"\n{title_extra}"
        
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_xlabel('Candles')
        ax.set_ylabel('Preço')
        ax.legend(loc='upper left', fontsize=10)
        ax.grid(True, alpha=0.3)
        
        # Adicionar informações
        info_text = f"Duração: {result.duration_candles} candles\n"
        info_text += f"OB: {signal.ob_bottom:.2f} - {signal.ob_top:.2f}\n"
        info_text += f"Entry: {result.entry_price:.2f}\n"
        info_text += f"P/L: {result.profit_loss_r:.2f}R"
        
        ax.text(0.98, 0.02, info_text, transform=ax.transAxes, fontsize=10,
                verticalalignment='bottom', horizontalalignment='right',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        plt.tight_layout()
        plt.savefig(filename, dpi=150, bbox_inches='tight')
        plt.close()
    
    # Gerar imagens por categoria
    image_count = 0
    
    # 1. Trades com SWEEP
    print("\nGerando imagens de trades com SWEEP...")
    for i, result in enumerate(trades_with_sweep[:5]):
        filename = f"{output_dir}/sweep_{i+1:02d}_{'LONG' if result.signal.direction == SignalDirection.BULLISH else 'SHORT'}.png"
        plot_trade(result, df, filename, "Liquidity Sweep Detectado")
        image_count += 1
        print(f"  Gerado: {filename}")
    
    # 2. Trades com ABC
    print("\nGerando imagens de trades com ABC...")
    for i, result in enumerate(trades_with_abc[:5]):
        filename = f"{output_dir}/abc_{i+1:02d}_{'LONG' if result.signal.direction == SignalDirection.BULLISH else 'SHORT'}.png"
        plot_trade(result, df, filename, "Padrão ABC Detectado")
        image_count += 1
        print(f"  Gerado: {filename}")
    
    # 3. Trades com FVG
    print("\nGerando imagens de trades com FVG...")
    for i, result in enumerate(trades_with_fvg[:5]):
        filename = f"{output_dir}/fvg_{i+1:02d}_{'LONG' if result.signal.direction == SignalDirection.BULLISH else 'SHORT'}.png"
        plot_trade(result, df, filename, "Fair Value Gap Detectado")
        image_count += 1
        print(f"  Gerado: {filename}")
    
    # 4. Trades com BOS
    print("\nGerando imagens de trades com BOS...")
    for i, result in enumerate(trades_with_bos[:5]):
        filename = f"{output_dir}/bos_{i+1:02d}_{'LONG' if result.signal.direction == SignalDirection.BULLISH else 'SHORT'}.png"
        plot_trade(result, df, filename, "Break of Structure Detectado")
        image_count += 1
        print(f"  Gerado: {filename}")
    
    # 5. Trades com CHoCH
    print("\nGerando imagens de trades com CHoCH...")
    for i, result in enumerate(trades_with_choch[:5]):
        filename = f"{output_dir}/choch_{i+1:02d}_{'LONG' if result.signal.direction == SignalDirection.BULLISH else 'SHORT'}.png"
        plot_trade(result, df, filename, "Change of Character Detectado")
        image_count += 1
        print(f"  Gerado: {filename}")
    
    print(f"\n{'='*60}")
    print(f"Total de imagens geradas: {image_count}")
    print(f"Diretório: {output_dir}")
    
    # Estatísticas por padrão
    print(f"\n{'='*60}")
    print("ESTATÍSTICAS POR PADRÃO")
    print(f"{'='*60}")
    
    pattern_stats = {}
    for pattern_type in PatternType:
        trades_with_pattern = [r for r in results if pattern_type in r.signal.patterns_detected]
        if len(trades_with_pattern) > 0:
            wins = sum(1 for r in trades_with_pattern if r.hit_tp)
            win_rate = wins / len(trades_with_pattern) * 100
            pattern_stats[pattern_type.value] = {
                'trades': len(trades_with_pattern),
                'wins': wins,
                'win_rate': win_rate
            }
    
    print(f"\n{'Padrão':<15} {'Trades':<10} {'Wins':<10} {'Win Rate':<10}")
    print("-" * 45)
    for pattern, stats in sorted(pattern_stats.items(), key=lambda x: x[1]['win_rate'], reverse=True):
        print(f"{pattern:<15} {stats['trades']:<10} {stats['wins']:<10} {stats['win_rate']:.1f}%")
    
    return image_count


if __name__ == "__main__":
    generate_pattern_images()
