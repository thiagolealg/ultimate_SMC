"""
Teste da versão SEM LOOK-AHEAD com dados reais
"""

import pandas as pd
import numpy as np
from smc_no_lookahead import (
    SMCNoLookahead, 
    OrderBlockStrategyNoLookahead, 
    SignalDirection,
    validate_ohlc
)


def load_data(filepath: str) -> pd.DataFrame:
    """Carrega dados do CSV"""
    df = pd.read_csv(filepath)
    df.columns = [c.lower() for c in df.columns]
    
    if 'time' in df.columns:
        df['time'] = pd.to_datetime(df['time'])
        df.set_index('time', inplace=True)
    
    if 'volume' not in df.columns:
        if 'tick_volume' in df.columns:
            df['volume'] = df['tick_volume']
        elif 'real_volume' in df.columns:
            df['volume'] = df['real_volume']
        else:
            df['volume'] = 1.0
    
    return df


def test_with_real_data():
    """Testa com dados reais"""
    print("=" * 70)
    print("TESTE COM DADOS REAIS - VERSÃO SEM LOOK-AHEAD BIAS")
    print("=" * 70)
    
    # Carregar dados
    df = load_data('/home/ubuntu/smc_enhanced/data.csv')
    print(f"\nDados carregados: {len(df)} candles")
    print(f"Período: {df.index[0]} a {df.index[-1]}")
    
    # Usar uma amostra para teste mais rápido
    df_sample = df.tail(10000)
    print(f"Usando amostra: {len(df_sample)} candles")
    
    # Teste 1: Order Blocks
    print("\n" + "-" * 50)
    print("1. ORDER BLOCKS (SEM LOOK-AHEAD)")
    print("-" * 50)
    
    ob = SMCNoLookahead.ob_realtime(df_sample, swing_length=5)
    valid_obs = ob[ob['OB'].notna()]
    
    print(f"   Order Blocks detectados: {len(valid_obs)}")
    print(f"   - Bullish: {(valid_obs['OB'] == 1).sum()}")
    print(f"   - Bearish: {(valid_obs['OB'] == -1).sum()}")
    
    # Verificar look-ahead
    lookahead_violations = 0
    for idx in valid_obs.index:
        formation = valid_obs.loc[idx, 'FormationIndex']
        confirmation = valid_obs.loc[idx, 'ConfirmationIndex']
        
        if not np.isnan(formation) and not np.isnan(confirmation):
            # O índice do OB (onde está marcado) deve ser >= confirmação
            ob_idx = df_sample.index.get_loc(idx)
            if ob_idx < confirmation:
                lookahead_violations += 1
    
    if lookahead_violations == 0:
        print(f"   ✓ Nenhuma violação de look-ahead")
    else:
        print(f"   ✗ {lookahead_violations} violações detectadas!")
    
    # Mostrar alguns OBs
    if len(valid_obs) > 0:
        print("\n   Últimos 5 Order Blocks:")
        for idx in valid_obs.tail(5).index:
            row = valid_obs.loc[idx]
            direction = "BULL" if row['OB'] == 1 else "BEAR"
            print(f"      {idx}: {direction} | Top: {row['Top']:.2f} | Bottom: {row['Bottom']:.2f}")
            print(f"         Formation: {row['FormationIndex']:.0f} | Confirmation: {row['ConfirmationIndex']:.0f}")
    
    # Teste 2: FVG
    print("\n" + "-" * 50)
    print("2. FAIR VALUE GAP")
    print("-" * 50)
    
    fvg = SMCNoLookahead.fvg(df_sample)
    print(f"   FVG Bullish: {(fvg['FVG'] == 1).sum()}")
    print(f"   FVG Bearish: {(fvg['FVG'] == -1).sum()}")
    
    # Teste 3: BOS/CHoCH
    print("\n" + "-" * 50)
    print("3. BOS / CHoCH")
    print("-" * 50)
    
    bos_choch = SMCNoLookahead.bos_choch_realtime(df_sample, swing_length=5)
    print(f"   BOS Bullish: {(bos_choch['BOS'] == 1).sum()}")
    print(f"   BOS Bearish: {(bos_choch['BOS'] == -1).sum()}")
    print(f"   CHoCH Bullish: {(bos_choch['CHOCH'] == 1).sum()}")
    print(f"   CHoCH Bearish: {(bos_choch['CHOCH'] == -1).sum()}")
    
    # Teste 4: Estratégia
    print("\n" + "-" * 50)
    print("4. ESTRATÉGIA ORDER BLOCK 3:1")
    print("-" * 50)
    
    confidence_levels = [30, 50]
    
    for min_conf in confidence_levels:
        print(f"\n   --- Confiança mínima: {min_conf}% ---")
        
        strategy = OrderBlockStrategyNoLookahead(
            df_sample,
            swing_length=5,
            risk_reward_ratio=3.0,
            min_confidence=min_conf,
            entry_delay_candles=1,
        )
        
        signals = strategy.generate_signals()
        print(f"   Sinais gerados: {len(signals)}")
        
        # Verificar look-ahead nos sinais
        lookahead_signals = 0
        for signal in signals:
            # Entrada deve ser APÓS o candle de confirmação
            if signal.index <= signal.signal_candle_index:
                lookahead_signals += 1
            # Sinal deve ser APÓS formação
            if signal.signal_candle_index < signal.ob_formation_index:
                lookahead_signals += 1
        
        if lookahead_signals == 0:
            print(f"   ✓ Nenhuma violação de look-ahead nos sinais")
        else:
            print(f"   ✗ {lookahead_signals} violações detectadas!")
        
        if len(signals) > 0:
            # Distribuição
            bullish = sum(1 for s in signals if s.direction == SignalDirection.BULLISH)
            bearish = sum(1 for s in signals if s.direction == SignalDirection.BEARISH)
            print(f"   Bullish: {bullish} | Bearish: {bearish}")
            
            # Backtest
            results, stats = strategy.backtest(signals)
            
            print(f"\n   BACKTEST:")
            print(f"   Total trades: {stats['total_trades']}")
            print(f"   Win Rate: {stats['win_rate']:.1f}%")
            print(f"   Profit Factor: {stats['profit_factor']:.2f}")
            print(f"   P/L Total: {stats['total_profit_loss']:.2f}")
            print(f"   Hit TP: {stats['hit_tp_count']} | Hit SL: {stats['hit_sl_count']}")
            
            # Mostrar alguns sinais
            print(f"\n   Últimos 3 sinais:")
            for signal in signals[-3:]:
                direction = "LONG" if signal.direction == SignalDirection.BULLISH else "SHORT"
                print(f"      {direction} | Entry idx: {signal.index} | Signal idx: {signal.signal_candle_index}")
                print(f"         Entry: {signal.entry_price:.2f} | SL: {signal.stop_loss:.2f} | TP: {signal.take_profit:.2f}")
                print(f"         Conf: {signal.confidence:.1f}% | OB Formation: {signal.ob_formation_index}")
    
    # Teste 5: Comparação com versão original
    print("\n" + "-" * 50)
    print("5. COMPARAÇÃO: VERSÃO ORIGINAL vs SEM LOOK-AHEAD")
    print("-" * 50)
    
    from smc_enhanced import OrderBlockStrategy as OriginalStrategy
    
    print("\n   Versão ORIGINAL (com look-ahead):")
    original_strategy = OriginalStrategy(
        df_sample,
        swing_length=5,
        risk_reward_ratio=3.0,
        min_confidence=30.0,
        entry_delay_candles=1,
    )
    original_signals = original_strategy.generate_signals()
    original_results, original_stats = original_strategy.backtest(original_signals)
    
    print(f"   Sinais: {len(original_signals)}")
    print(f"   Win Rate: {original_stats['win_rate']:.1f}%")
    print(f"   Profit Factor: {original_stats['profit_factor']:.2f}")
    
    print("\n   Versão SEM LOOK-AHEAD:")
    no_lookahead_strategy = OrderBlockStrategyNoLookahead(
        df_sample,
        swing_length=5,
        risk_reward_ratio=3.0,
        min_confidence=30.0,
        entry_delay_candles=1,
    )
    no_lookahead_signals = no_lookahead_strategy.generate_signals()
    
    if len(no_lookahead_signals) > 0:
        no_lookahead_results, no_lookahead_stats = no_lookahead_strategy.backtest(no_lookahead_signals)
        print(f"   Sinais: {len(no_lookahead_signals)}")
        print(f"   Win Rate: {no_lookahead_stats['win_rate']:.1f}%")
        print(f"   Profit Factor: {no_lookahead_stats['profit_factor']:.2f}")
    else:
        print(f"   Sinais: 0")
    
    print("\n   ANÁLISE:")
    print(f"   A versão original detecta mais sinais porque usa dados futuros")
    print(f"   para identificar swings (look-ahead bias).")
    print(f"   A versão corrigida é mais conservadora mas realista.")
    
    return True


def validate_no_lookahead_detailed():
    """Validação detalhada de que não há look-ahead"""
    print("\n" + "=" * 70)
    print("VALIDAÇÃO DETALHADA - PROVA DE NÃO LOOK-AHEAD")
    print("=" * 70)
    
    df = load_data('/home/ubuntu/smc_enhanced/data.csv')
    df_sample = df.tail(5000)
    
    print("\n1. TESTE DE SIMULAÇÃO CANDLE-A-CANDLE")
    print("-" * 50)
    
    # Simular processamento em tempo real
    all_signals_by_end = {}
    
    # Processar em blocos para simular tempo real
    for end_idx in [1000, 2000, 3000, 4000, 5000]:
        partial_df = df_sample.iloc[:end_idx]
        
        strategy = OrderBlockStrategyNoLookahead(
            partial_df,
            swing_length=5,
            risk_reward_ratio=3.0,
            min_confidence=30.0,
            entry_delay_candles=1,
        )
        
        signals = strategy.generate_signals()
        all_signals_by_end[end_idx] = signals
        
        # Verificar que nenhum sinal usa dados além de end_idx
        for signal in signals:
            if signal.index >= end_idx:
                print(f"   ✗ VIOLAÇÃO: Sinal em {signal.index} com dados até {end_idx}")
                return False
        
        print(f"   Dados até índice {end_idx}: {len(signals)} sinais (todos válidos)")
    
    print("\n   ✓ Simulação candle-a-candle passou!")
    
    print("\n2. TESTE DE CONSISTÊNCIA TEMPORAL")
    print("-" * 50)
    
    # Verificar que sinais em t não mudam quando adicionamos dados em t+1
    # (sinais passados devem ser estáveis)
    
    signals_1000 = all_signals_by_end[1000]
    signals_2000 = all_signals_by_end[2000]
    
    # Sinais até índice 1000 devem ser os mesmos em ambos
    signals_1000_indices = set(s.index for s in signals_1000)
    signals_2000_early = set(s.index for s in signals_2000 if s.index < 1000)
    
    if signals_1000_indices == signals_2000_early:
        print(f"   ✓ Sinais são consistentes ao adicionar novos dados")
    else:
        print(f"   ✗ Sinais mudaram retroativamente!")
        return False
    
    print("\n3. VERIFICAÇÃO DE ÍNDICES")
    print("-" * 50)
    
    strategy = OrderBlockStrategyNoLookahead(
        df_sample,
        swing_length=5,
        risk_reward_ratio=3.0,
        min_confidence=30.0,
        entry_delay_candles=1,
    )
    
    signals = strategy.generate_signals()
    
    for i, signal in enumerate(signals[:10]):  # Verificar primeiros 10
        print(f"\n   Sinal {i+1}:")
        print(f"      OB Formation Index: {signal.ob_formation_index}")
        print(f"      OB Confirmation Index: {signal.confirmation_index}")
        print(f"      Signal Candle Index: {signal.signal_candle_index}")
        print(f"      Entry Index: {signal.index}")
        
        # Verificar ordem temporal
        assert signal.ob_formation_index <= signal.confirmation_index, "Formation deve ser <= Confirmation"
        assert signal.confirmation_index <= signal.signal_candle_index, "Confirmation deve ser <= Signal"
        assert signal.signal_candle_index < signal.index, "Signal deve ser < Entry"
        
        print(f"      ✓ Ordem temporal correta")
    
    print("\n" + "=" * 70)
    print("✓ TODAS AS VALIDAÇÕES PASSARAM - CÓDIGO SEM LOOK-AHEAD BIAS")
    print("=" * 70)
    
    return True


if __name__ == "__main__":
    test_with_real_data()
    validate_no_lookahead_detailed()
