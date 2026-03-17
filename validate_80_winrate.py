"""
Validação Rigorosa do Win Rate de 80%
=====================================
Verificar se o Win Rate alto é legítimo ou se há algum problema.
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


def validate_backtest_logic():
    """
    Valida a lógica do backtest manualmente.
    """
    print("=" * 70)
    print("VALIDAÇÃO MANUAL DO BACKTEST")
    print("=" * 70)
    
    df = load_data()
    df = df.tail(20000)
    
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
    
    print(f"\nTotal de sinais: {len(signals)}")
    print(f"Total de trades: {len(results)}")
    print(f"Win Rate: {stats['win_rate']:.1f}%")
    
    # Verificar alguns trades manualmente
    print("\n" + "-" * 50)
    print("VERIFICAÇÃO MANUAL DE TRADES")
    print("-" * 50)
    
    correct = 0
    incorrect = 0
    
    for i, result in enumerate(results[:20]):  # Verificar primeiros 20
        signal = result.signal
        entry_idx = result.entry_index
        
        # Verificar manualmente
        entry_price = signal.entry_price
        stop_loss = signal.stop_loss
        take_profit = signal.take_profit
        
        # Simular o trade
        actual_hit_tp = False
        actual_hit_sl = False
        actual_exit_idx = None
        
        for j in range(entry_idx + 1, min(len(df), entry_idx + 1000)):
            high = df['high'].iloc[j]
            low = df['low'].iloc[j]
            
            if signal.direction == SignalDirection.BULLISH:
                if low <= stop_loss:
                    actual_hit_sl = True
                    actual_exit_idx = j
                    break
                if high >= take_profit:
                    actual_hit_tp = True
                    actual_exit_idx = j
                    break
            else:
                if high >= stop_loss:
                    actual_hit_sl = True
                    actual_exit_idx = j
                    break
                if low <= take_profit:
                    actual_hit_tp = True
                    actual_exit_idx = j
                    break
        
        # Comparar com resultado do backtest
        if actual_hit_tp == result.hit_tp and actual_hit_sl == result.hit_sl:
            correct += 1
        else:
            incorrect += 1
            print(f"\n   DISCREPÂNCIA no trade {i+1}:")
            print(f"      Backtest: TP={result.hit_tp}, SL={result.hit_sl}")
            print(f"      Manual: TP={actual_hit_tp}, SL={actual_hit_sl}")
    
    print(f"\n   Trades verificados: 20")
    print(f"   Corretos: {correct}")
    print(f"   Incorretos: {incorrect}")
    
    if incorrect == 0:
        print("   ✓ Lógica do backtest está correta!")
    else:
        print("   ✗ Há problemas na lógica do backtest!")


def check_look_ahead_in_signals():
    """
    Verifica se há look-ahead nos sinais.
    """
    print("\n" + "=" * 70)
    print("VERIFICAÇÃO DE LOOK-AHEAD NOS SINAIS")
    print("=" * 70)
    
    df = load_data()
    df = df.tail(20000)
    
    strategy = OrderBlockStrategy70WR(
        df,
        swing_length=5,
        risk_reward_ratio=1.0,
        min_confidence=30.0,
        entry_delay_candles=1,
        use_not_mitigated_filter=True,
    )
    
    signals = strategy.generate_signals()
    
    violations = 0
    
    for signal in signals:
        # Entrada deve ser APÓS o sinal
        if signal.index <= signal.signal_candle_index:
            violations += 1
            print(f"   VIOLAÇÃO: Entry {signal.index} <= Signal {signal.signal_candle_index}")
        
        # Sinal deve ser APÓS o candle do OB
        if signal.signal_candle_index < signal.ob_candle_index:
            violations += 1
            print(f"   VIOLAÇÃO: Signal {signal.signal_candle_index} < OB {signal.ob_candle_index}")
    
    print(f"\n   Total de sinais: {len(signals)}")
    print(f"   Violações: {violations}")
    
    if violations == 0:
        print("   ✓ Nenhuma violação de look-ahead!")
    else:
        print("   ✗ Violações de look-ahead detectadas!")


def analyze_trade_distribution():
    """
    Analisa a distribuição dos trades.
    """
    print("\n" + "=" * 70)
    print("ANÁLISE DA DISTRIBUIÇÃO DOS TRADES")
    print("=" * 70)
    
    df = load_data()
    df = df.tail(20000)
    
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
    
    print(f"\n   Total trades: {len(results)}")
    print(f"   Winning: {stats['winning_trades']}")
    print(f"   Losing: {stats['losing_trades']}")
    print(f"   Win Rate: {stats['win_rate']:.1f}%")
    
    # Analisar por direção
    bull_results = [r for r in results if r.signal.direction == SignalDirection.BULLISH]
    bear_results = [r for r in results if r.signal.direction == SignalDirection.BEARISH]
    
    bull_wins = sum(1 for r in bull_results if r.hit_tp)
    bear_wins = sum(1 for r in bear_results if r.hit_tp)
    
    print(f"\n   Bullish trades: {len(bull_results)}")
    if len(bull_results) > 0:
        print(f"      Win Rate: {bull_wins/len(bull_results)*100:.1f}%")
    
    print(f"\n   Bearish trades: {len(bear_results)}")
    if len(bear_results) > 0:
        print(f"      Win Rate: {bear_wins/len(bear_results)*100:.1f}%")
    
    # Analisar duração
    winning_duration = [r.duration_candles for r in results if r.hit_tp]
    losing_duration = [r.duration_candles for r in results if r.hit_sl]
    
    print(f"\n   Duração média (vencedores): {np.mean(winning_duration):.1f} candles")
    print(f"   Duração média (perdedores): {np.mean(losing_duration):.1f} candles")
    
    # Analisar P/L
    print(f"\n   P/L Total: {stats['total_profit_loss']:.2f}")
    print(f"   P/L Médio: {stats['avg_profit_loss']:.2f}")
    print(f"   Profit Factor: {stats['profit_factor']:.2f}")


def test_with_different_periods():
    """
    Testa em diferentes períodos para verificar consistência.
    """
    print("\n" + "=" * 70)
    print("TESTE EM DIFERENTES PERÍODOS")
    print("=" * 70)
    
    df = load_data()
    
    periods = [
        ('Últimos 10k', df.tail(10000)),
        ('Últimos 20k', df.tail(20000)),
        ('Últimos 30k', df.tail(30000)),
        ('Últimos 50k', df.tail(50000)),
        ('Todos', df),
    ]
    
    for name, data in periods:
        strategy = OrderBlockStrategy70WR(
            data,
            swing_length=5,
            risk_reward_ratio=1.0,
            min_confidence=30.0,
            entry_delay_candles=1,
            use_not_mitigated_filter=True,
        )
        
        signals = strategy.generate_signals()
        results, stats = strategy.backtest(signals)
        
        print(f"\n   {name} ({len(data)} candles):")
        print(f"      Trades: {stats['total_trades']}")
        print(f"      Win Rate: {stats['win_rate']:.1f}%")
        print(f"      Profit Factor: {stats['profit_factor']:.2f}")


def main():
    """Executa todas as validações"""
    validate_backtest_logic()
    check_look_ahead_in_signals()
    analyze_trade_distribution()
    test_with_different_periods()
    
    print("\n" + "=" * 70)
    print("VALIDAÇÃO CONCLUÍDA")
    print("=" * 70)


if __name__ == "__main__":
    main()
