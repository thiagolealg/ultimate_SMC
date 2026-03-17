"""
Comparação de resultados com diferentes tamanhos de amostra
"""

import pandas as pd
import numpy as np
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


def test_sample(df, sample_name):
    """Testa uma amostra específica"""
    print(f"\n{'='*60}")
    print(f"AMOSTRA: {sample_name} ({len(df)} candles)")
    print(f"{'='*60}")
    
    for rr in [1.0, 2.0, 3.0]:
        strategy = OrderBlockStrategy70WR(
            df,
            swing_length=5,
            risk_reward_ratio=rr,
            min_confidence=30.0,
            entry_delay_candles=1,
            use_not_mitigated_filter=True,
        )
        
        signals = strategy.generate_signals()
        results, stats = strategy.backtest(signals)
        
        # Calcular lucro em R
        total_r = 0
        for result in results:
            if result.hit_tp:
                total_r += rr
            elif result.hit_sl:
                total_r -= 1
        
        expectancy = total_r / len(results) if len(results) > 0 else 0
        
        print(f"\nRR {rr}:1:")
        print(f"   Trades: {stats['total_trades']}")
        print(f"   Win Rate: {stats['win_rate']:.1f}%")
        print(f"   Profit Factor: {stats['profit_factor']:.2f}")
        print(f"   Lucro (R): {total_r:.1f}R")
        print(f"   Lucro (Pontos): {stats['total_profit_loss']:.2f}")
        print(f"   Expectativa: {expectancy:.2f}R")


def main():
    df = load_data()
    
    print("="*60)
    print("COMPARAÇÃO DE RESULTADOS POR TAMANHO DE AMOSTRA")
    print("="*60)
    print(f"\nTotal de dados disponíveis: {len(df)} candles")
    
    # Testar com diferentes amostras
    test_sample(df.tail(20000), "Últimos 20.000 candles")
    test_sample(df.tail(50000), "Últimos 50.000 candles")
    test_sample(df, "TODOS os dados (113.314 candles)")


if __name__ == "__main__":
    main()
