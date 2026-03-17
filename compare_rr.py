"""
Comparação de Lucro e Win Rate para diferentes Risk:Reward
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


def compare_rr_ratios():
    """
    Compara lucro e Win Rate para RR 1:1, 2:1 e 3:1
    """
    print("=" * 80)
    print("COMPARAÇÃO DE LUCRO E WIN RATE PARA DIFERENTES RISK:REWARD")
    print("=" * 80)
    
    df = load_data()
    
    # Usar todos os dados disponíveis
    print(f"\nDados: {len(df)} candles")
    print(f"Período: {df.index[0]} a {df.index[-1]}")
    
    rr_ratios = [1.0, 2.0, 3.0]
    results_summary = []
    
    for rr in rr_ratios:
        print(f"\n" + "-" * 80)
        print(f"RISK:REWARD {rr}:1")
        print("-" * 80)
        
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
        
        # Calcular lucro em R (unidades de risco)
        total_r = 0
        for result in results:
            if result.hit_tp:
                total_r += rr  # Ganhou RR vezes o risco
            elif result.hit_sl:
                total_r -= 1   # Perdeu 1R
        
        # Estatísticas detalhadas
        winning_trades = stats['winning_trades']
        losing_trades = stats['losing_trades']
        total_trades = stats['total_trades']
        win_rate = stats['win_rate']
        
        # Lucro em pontos (do backtest)
        total_profit_points = stats['total_profit_loss']
        
        # Expectativa por trade
        if total_trades > 0:
            expectancy_r = total_r / total_trades
        else:
            expectancy_r = 0
        
        print(f"\n   TRADES:")
        print(f"   Total de trades: {total_trades}")
        print(f"   Trades vencedores: {winning_trades}")
        print(f"   Trades perdedores: {losing_trades}")
        
        print(f"\n   WIN RATE:")
        print(f"   Win Rate: {win_rate:.1f}%")
        
        print(f"\n   LUCRO:")
        print(f"   Lucro em R (unidades de risco): {total_r:.1f}R")
        print(f"   Lucro em pontos: {total_profit_points:.2f}")
        print(f"   Expectativa por trade: {expectancy_r:.2f}R")
        
        print(f"\n   MÉTRICAS:")
        print(f"   Profit Factor: {stats['profit_factor']:.2f}")
        print(f"   Média de ganho: {stats['avg_win']:.2f}")
        print(f"   Média de perda: {stats['avg_loss']:.2f}")
        
        results_summary.append({
            'RR': f"{rr}:1",
            'Trades': total_trades,
            'Win Rate': f"{win_rate:.1f}%",
            'Lucro (R)': f"{total_r:.1f}R",
            'Lucro (Pontos)': f"{total_profit_points:.2f}",
            'Expectativa/Trade': f"{expectancy_r:.2f}R",
            'Profit Factor': f"{stats['profit_factor']:.2f}",
        })
    
    # Tabela resumo
    print("\n" + "=" * 80)
    print("RESUMO COMPARATIVO")
    print("=" * 80)
    
    print("\n{:<10} {:<10} {:<12} {:<15} {:<18} {:<18} {:<15}".format(
        "R:R", "Trades", "Win Rate", "Lucro (R)", "Lucro (Pontos)", "Expect./Trade", "Profit Factor"
    ))
    print("-" * 100)
    
    for r in results_summary:
        print("{:<10} {:<10} {:<12} {:<15} {:<18} {:<18} {:<15}".format(
            r['RR'],
            r['Trades'],
            r['Win Rate'],
            r['Lucro (R)'],
            r['Lucro (Pontos)'],
            r['Expectativa/Trade'],
            r['Profit Factor'],
        ))
    
    # Análise
    print("\n" + "=" * 80)
    print("ANÁLISE")
    print("=" * 80)
    
    print("""
    1. RR 1:1 tem o MAIOR Win Rate (~80%) mas menor lucro por trade vencedor
    2. RR 3:1 tem o MENOR Win Rate (~52%) mas maior lucro por trade vencedor
    3. O LUCRO TOTAL depende da combinação de Win Rate × RR
    
    Fórmula de Expectativa:
    E = (Win Rate × RR) - (Loss Rate × 1)
    
    Exemplo para RR 3:1 com 52% Win Rate:
    E = (0.52 × 3) - (0.48 × 1) = 1.56 - 0.48 = 1.08R por trade
    
    Exemplo para RR 1:1 com 80% Win Rate:
    E = (0.80 × 1) - (0.20 × 1) = 0.80 - 0.20 = 0.60R por trade
    """)
    
    return results_summary


if __name__ == "__main__":
    compare_rr_ratios()
