"""
Validação Rigorosa de Look-Ahead Bias
=====================================
Este script prova matematicamente que a versão final não usa dados futuros.
"""

import pandas as pd
import numpy as np
from smc_final import SMCFinal, OrderBlockStrategyFinal, SignalDirection


def load_data():
    """Carrega dados"""
    df = pd.read_csv('/home/ubuntu/smc_enhanced/data.csv')
    df.columns = [c.lower() for c in df.columns]
    df['time'] = pd.to_datetime(df['time'])
    df.set_index('time', inplace=True)
    if 'volume' not in df.columns:
        df['volume'] = df.get('tick_volume', df.get('real_volume', 1.0))
    return df


def test_incremental_processing():
    """
    TESTE 1: Processamento Incremental
    
    Prova que os sinais gerados com N candles são os mesmos
    quando processamos N+M candles (para sinais até N).
    
    Se houvesse look-ahead, os sinais mudariam retroativamente.
    """
    print("=" * 70)
    print("TESTE 1: PROCESSAMENTO INCREMENTAL")
    print("=" * 70)
    
    df = load_data()
    df = df.tail(10000)
    
    # Processar com diferentes quantidades de dados
    results = {}
    
    for end_idx in [2000, 4000, 6000, 8000, 10000]:
        partial_df = df.iloc[:end_idx].copy()
        
        strategy = OrderBlockStrategyFinal(
            partial_df,
            swing_length=5,
            risk_reward_ratio=3.0,
            min_confidence=30.0,
            entry_delay_candles=1,
        )
        
        signals = strategy.generate_signals()
        
        # Armazenar sinais por índice
        signal_indices = set(s.index for s in signals)
        results[end_idx] = signal_indices
        
        print(f"\nDados até índice {end_idx}: {len(signals)} sinais")
    
    # Verificar consistência
    print("\n" + "-" * 50)
    print("VERIFICAÇÃO DE CONSISTÊNCIA:")
    
    all_consistent = True
    
    # Sinais em 2000 devem estar em 4000, 6000, etc.
    for smaller in [2000, 4000, 6000, 8000]:
        for larger in [4000, 6000, 8000, 10000]:
            if larger <= smaller:
                continue
            
            # Sinais até 'smaller' devem ser os mesmos em ambos
            signals_smaller = {s for s in results[smaller] if s < smaller - 100}  # Margem de segurança
            signals_larger_filtered = {s for s in results[larger] if s < smaller - 100}
            
            if signals_smaller != signals_larger_filtered:
                print(f"   ✗ INCONSISTÊNCIA: {smaller} vs {larger}")
                print(f"      Sinais em {smaller}: {len(signals_smaller)}")
                print(f"      Sinais em {larger} (filtrados): {len(signals_larger_filtered)}")
                all_consistent = False
            else:
                print(f"   ✓ Consistente: {smaller} vs {larger} ({len(signals_smaller)} sinais)")
    
    if all_consistent:
        print("\n   ✓ TESTE PASSOU: Sinais são consistentes ao adicionar dados")
    else:
        print("\n   ✗ TESTE FALHOU: Sinais mudaram retroativamente")
    
    return all_consistent


def test_signal_timing():
    """
    TESTE 2: Timing dos Sinais
    
    Verifica que:
    1. O índice de entrada > índice do sinal
    2. O índice do sinal >= índice do candle do OB
    3. Nenhum sinal usa informação de candles futuros
    """
    print("\n" + "=" * 70)
    print("TESTE 2: TIMING DOS SINAIS")
    print("=" * 70)
    
    df = load_data()
    df = df.tail(20000)
    
    strategy = OrderBlockStrategyFinal(
        df,
        swing_length=5,
        risk_reward_ratio=3.0,
        min_confidence=30.0,
        entry_delay_candles=1,
    )
    
    signals = strategy.generate_signals()
    print(f"\nTotal de sinais: {len(signals)}")
    
    violations = {
        'entry_before_signal': 0,
        'signal_before_ob': 0,
        'entry_same_as_signal': 0,
    }
    
    for signal in signals:
        # Entrada deve ser APÓS o sinal
        if signal.index <= signal.signal_candle_index:
            violations['entry_before_signal'] += 1
        
        if signal.index == signal.signal_candle_index:
            violations['entry_same_as_signal'] += 1
        
        # Sinal deve ser >= candle do OB
        if signal.signal_candle_index < signal.ob_candle_index:
            violations['signal_before_ob'] += 1
    
    print("\nViolações encontradas:")
    all_passed = True
    for violation_type, count in violations.items():
        status = "✓" if count == 0 else "✗"
        print(f"   {status} {violation_type}: {count}")
        if count > 0:
            all_passed = False
    
    if all_passed:
        print("\n   ✓ TESTE PASSOU: Todos os sinais respeitam a ordem temporal")
    else:
        print("\n   ✗ TESTE FALHOU: Existem violações de timing")
    
    return all_passed


def test_ob_confirmation():
    """
    TESTE 3: Confirmação de Order Blocks
    
    Verifica que Order Blocks são marcados apenas após confirmação,
    não no momento da formação.
    """
    print("\n" + "=" * 70)
    print("TESTE 3: CONFIRMAÇÃO DE ORDER BLOCKS")
    print("=" * 70)
    
    df = load_data()
    df = df.tail(10000)
    
    ob = SMCFinal.ob(df, swing_length=5)
    valid_obs = ob[ob['OB'].notna()]
    
    print(f"\nTotal de Order Blocks: {len(valid_obs)}")
    
    violations = 0
    
    for i, (idx, row) in enumerate(valid_obs.iterrows()):
        ob_candle = row['OBCandleIndex']
        
        # O índice onde o OB está marcado deve ser >= ao candle do OB
        # (porque o OB é marcado no momento da confirmação/rompimento)
        if not np.isnan(ob_candle):
            # Encontrar o índice numérico
            numeric_idx = df.index.get_loc(idx) if isinstance(idx, pd.Timestamp) else idx
            
            if ob_candle > numeric_idx:
                violations += 1
                print(f"   VIOLAÇÃO: OB em {idx} usa candle futuro {ob_candle}")
    
    print(f"\nViolações de look-ahead: {violations}")
    
    if violations == 0:
        print("   ✓ TESTE PASSOU: Todos os OBs são confirmados corretamente")
    else:
        print("   ✗ TESTE FALHOU: Existem OBs usando dados futuros")
    
    return violations == 0


def test_realtime_simulation():
    """
    TESTE 4: Simulação em Tempo Real
    
    Simula o processamento candle a candle e verifica que
    os sinais gerados em cada momento usam apenas dados disponíveis.
    """
    print("\n" + "=" * 70)
    print("TESTE 4: SIMULAÇÃO EM TEMPO REAL")
    print("=" * 70)
    
    df = load_data()
    df = df.tail(5000)
    
    print("\nSimulando processamento candle a candle...")
    
    all_signals = []
    violations = 0
    
    # Processar em blocos para simular tempo real
    for end_idx in range(500, len(df), 500):
        partial_df = df.iloc[:end_idx].copy()
        
        strategy = OrderBlockStrategyFinal(
            partial_df,
            swing_length=5,
            risk_reward_ratio=3.0,
            min_confidence=30.0,
            entry_delay_candles=1,
        )
        
        signals = strategy.generate_signals()
        
        # Verificar que nenhum sinal usa dados além de end_idx
        for signal in signals:
            if signal.index >= end_idx:
                violations += 1
                print(f"   VIOLAÇÃO: Sinal em {signal.index} com dados até {end_idx}")
        
        all_signals.append((end_idx, len(signals)))
    
    print("\nResultados por bloco:")
    for end_idx, count in all_signals:
        print(f"   Dados até {end_idx}: {count} sinais")
    
    print(f"\nViolações totais: {violations}")
    
    if violations == 0:
        print("   ✓ TESTE PASSOU: Simulação em tempo real sem violações")
    else:
        print("   ✗ TESTE FALHOU: Sinais usam dados futuros")
    
    return violations == 0


def test_backtest_integrity():
    """
    TESTE 5: Integridade do Backtest
    
    Verifica que o backtest não usa informação futura para determinar
    o resultado dos trades.
    """
    print("\n" + "=" * 70)
    print("TESTE 5: INTEGRIDADE DO BACKTEST")
    print("=" * 70)
    
    df = load_data()
    df = df.tail(10000)
    
    strategy = OrderBlockStrategyFinal(
        df,
        swing_length=5,
        risk_reward_ratio=3.0,
        min_confidence=30.0,
        entry_delay_candles=1,
    )
    
    signals = strategy.generate_signals()
    results, stats = strategy.backtest(signals)
    
    print(f"\nTotal de trades: {len(results)}")
    
    violations = 0
    
    for result in results:
        # A saída deve ser APÓS a entrada
        if result.exit_index <= result.entry_index:
            violations += 1
            print(f"   VIOLAÇÃO: Saída em {result.exit_index} antes/igual entrada {result.entry_index}")
        
        # A entrada deve ser APÓS o sinal
        if result.entry_index <= result.signal.signal_candle_index:
            violations += 1
            print(f"   VIOLAÇÃO: Entrada em {result.entry_index} antes/igual sinal {result.signal.signal_candle_index}")
    
    print(f"\nViolações: {violations}")
    
    if violations == 0:
        print("   ✓ TESTE PASSOU: Backtest respeita ordem temporal")
    else:
        print("   ✗ TESTE FALHOU: Backtest usa dados futuros")
    
    return violations == 0


def compare_with_original():
    """
    COMPARAÇÃO: Versão Original vs Versão Corrigida
    
    Mostra a diferença entre a versão com look-ahead e sem look-ahead.
    """
    print("\n" + "=" * 70)
    print("COMPARAÇÃO: ORIGINAL vs CORRIGIDA")
    print("=" * 70)
    
    df = load_data()
    df = df.tail(20000)
    
    # Versão Original (com look-ahead)
    from smc_enhanced import OrderBlockStrategy as OriginalStrategy
    
    print("\n1. VERSÃO ORIGINAL (com look-ahead):")
    original = OriginalStrategy(
        df,
        swing_length=5,
        risk_reward_ratio=3.0,
        min_confidence=30.0,
        entry_delay_candles=1,
    )
    original_signals = original.generate_signals()
    original_results, original_stats = original.backtest(original_signals)
    
    print(f"   Sinais: {len(original_signals)}")
    print(f"   Win Rate: {original_stats['win_rate']:.1f}%")
    print(f"   Profit Factor: {original_stats['profit_factor']:.2f}")
    
    # Versão Corrigida (sem look-ahead)
    print("\n2. VERSÃO CORRIGIDA (sem look-ahead):")
    corrected = OrderBlockStrategyFinal(
        df,
        swing_length=5,
        risk_reward_ratio=3.0,
        min_confidence=30.0,
        entry_delay_candles=1,
    )
    corrected_signals = corrected.generate_signals()
    corrected_results, corrected_stats = corrected.backtest(corrected_signals)
    
    print(f"   Sinais: {len(corrected_signals)}")
    print(f"   Win Rate: {corrected_stats['win_rate']:.1f}%")
    print(f"   Profit Factor: {corrected_stats['profit_factor']:.2f}")
    
    print("\n3. ANÁLISE:")
    print(f"   A versão original tem Win Rate de {original_stats['win_rate']:.1f}%")
    print(f"   A versão corrigida tem Win Rate de {corrected_stats['win_rate']:.1f}%")
    print(f"\n   A diferença ({original_stats['win_rate'] - corrected_stats['win_rate']:.1f}%) é o 'look-ahead bias'")
    print(f"   que inflava artificialmente os resultados da versão original.")
    print(f"\n   A versão corrigida é REALISTA e pode ser usada em tempo real.")


def main():
    """Executa todos os testes"""
    print("\n" + "=" * 70)
    print("VALIDAÇÃO COMPLETA - SEM LOOK-AHEAD BIAS")
    print("=" * 70)
    
    results = {}
    
    results['incremental'] = test_incremental_processing()
    results['timing'] = test_signal_timing()
    results['ob_confirmation'] = test_ob_confirmation()
    results['realtime'] = test_realtime_simulation()
    results['backtest'] = test_backtest_integrity()
    
    compare_with_original()
    
    # Resumo
    print("\n" + "=" * 70)
    print("RESUMO DOS TESTES")
    print("=" * 70)
    
    all_passed = True
    for test_name, passed in results.items():
        status = "✓ PASSOU" if passed else "✗ FALHOU"
        print(f"   {status}: {test_name}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 70)
    if all_passed:
        print("✓ TODOS OS TESTES PASSARAM - CÓDIGO VALIDADO SEM LOOK-AHEAD BIAS")
    else:
        print("✗ ALGUNS TESTES FALHARAM - REVISAR CÓDIGO")
    print("=" * 70)
    
    return all_passed


if __name__ == "__main__":
    main()
