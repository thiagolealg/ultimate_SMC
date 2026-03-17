"""
Exemplo de Uso - Smart Money Concepts Enhanced
===============================================
Este script demonstra como usar a biblioteca SMC Enhanced para análise de mercado.
"""

import pandas as pd
import numpy as np
from smc_enhanced import (
    SMCEnhanced, 
    OrderBlockStrategy, 
    TradeSignal, 
    BacktestResult,
    SignalDirection,
    validate_ohlc
)


def exemplo_basico():
    """Exemplo básico de uso dos indicadores SMC"""
    print("=" * 60)
    print("EXEMPLO BÁSICO - INDICADORES SMC")
    print("=" * 60)
    
    # Carregar dados
    df = pd.read_csv('/home/ubuntu/smc_enhanced/data.csv')
    df.columns = [c.lower() for c in df.columns]
    df['time'] = pd.to_datetime(df['time'])
    df.set_index('time', inplace=True)
    
    # Usar apenas os últimos 1000 candles para exemplo
    df = df.tail(1000)
    
    # Garantir volume
    if 'volume' not in df.columns:
        df['volume'] = df.get('tick_volume', df.get('real_volume', 1.0))
    
    print(f"\nDados: {len(df)} candles")
    print(f"Período: {df.index[0]} a {df.index[-1]}")
    
    # 1. Calcular Swing Highs/Lows
    print("\n1. Swing Highs/Lows:")
    swing_hl = SMCEnhanced.swing_highs_lows(df, swing_length=5)
    print(f"   - Swing Highs: {(swing_hl['HighLow'] == 1).sum()}")
    print(f"   - Swing Lows: {(swing_hl['HighLow'] == -1).sum()}")
    
    # 2. Calcular FVG
    print("\n2. Fair Value Gaps:")
    fvg = SMCEnhanced.fvg(df)
    print(f"   - FVG Bullish: {(fvg['FVG'] == 1).sum()}")
    print(f"   - FVG Bearish: {(fvg['FVG'] == -1).sum()}")
    
    # 3. Calcular Order Blocks
    print("\n3. Order Blocks:")
    ob = SMCEnhanced.ob(df, swing_hl)
    print(f"   - OB Bullish: {(ob['OB'] == 1).sum()}")
    print(f"   - OB Bearish: {(ob['OB'] == -1).sum()}")
    
    # Mostrar detalhes dos Order Blocks
    ob_valid = ob[ob['OB'].notna()]
    if len(ob_valid) > 0:
        print("\n   Últimos 5 Order Blocks:")
        for idx in ob_valid.tail(5).index:
            row = ob_valid.loc[idx]
            direction = "BULL" if row['OB'] == 1 else "BEAR"
            print(f"      {idx}: {direction} | Top: {row['Top']:.2f} | Bottom: {row['Bottom']:.2f} | %: {row['Percentage']:.1f}")
    
    # 4. Calcular BOS/CHoCH
    print("\n4. BOS / CHoCH:")
    bos_choch = SMCEnhanced.bos_choch(df, swing_hl)
    print(f"   - BOS Bullish: {(bos_choch['BOS'] == 1).sum()}")
    print(f"   - BOS Bearish: {(bos_choch['BOS'] == -1).sum()}")
    print(f"   - CHoCH Bullish: {(bos_choch['CHOCH'] == 1).sum()}")
    print(f"   - CHoCH Bearish: {(bos_choch['CHOCH'] == -1).sum()}")
    
    # 5. Calcular Liquidity
    print("\n5. Liquidity:")
    liq = SMCEnhanced.liquidity(df, swing_hl)
    print(f"   - Liquidity Bullish: {(liq['Liquidity'] == 1).sum()}")
    print(f"   - Liquidity Bearish: {(liq['Liquidity'] == -1).sum()}")
    
    return df, swing_hl


def exemplo_estrategia():
    """Exemplo de uso da estratégia Order Block 3:1"""
    print("\n" + "=" * 60)
    print("EXEMPLO ESTRATÉGIA ORDER BLOCK 3:1")
    print("=" * 60)
    
    # Carregar dados
    df = pd.read_csv('/home/ubuntu/smc_enhanced/data.csv')
    df.columns = [c.lower() for c in df.columns]
    df['time'] = pd.to_datetime(df['time'])
    df.set_index('time', inplace=True)
    
    # Usar apenas os últimos 5000 candles
    df = df.tail(5000)
    
    if 'volume' not in df.columns:
        df['volume'] = df.get('tick_volume', df.get('real_volume', 1.0))
    
    print(f"\nDados: {len(df)} candles")
    
    # Criar estratégia
    strategy = OrderBlockStrategy(
        df,
        swing_length=5,
        risk_reward_ratio=3.0,  # 3:1 Risk:Reward
        min_confidence=50.0,     # Confiança mínima de 50%
        entry_delay_candles=1,   # Entrada 1 candle após o sinal
    )
    
    # Gerar sinais
    print("\n1. Gerando sinais...")
    signals = strategy.generate_signals()
    print(f"   Sinais gerados: {len(signals)}")
    
    # Verificar que nenhuma entrada ocorre no mesmo candle
    same_candle = sum(1 for s in signals if s.index <= s.signal_candle_index)
    print(f"   Entradas no mesmo candle: {same_candle} (deve ser 0)")
    
    if len(signals) > 0:
        # Mostrar alguns sinais
        print("\n2. Últimos 5 sinais:")
        for signal in signals[-5:]:
            direction = "LONG" if signal.direction == SignalDirection.BULLISH else "SHORT"
            print(f"   {direction} | Entry: {signal.entry_price:.2f} | SL: {signal.stop_loss:.2f} | TP: {signal.take_profit:.2f} | Conf: {signal.confidence:.1f}%")
        
        # Executar backtest
        print("\n3. Backtest:")
        results, stats = strategy.backtest(signals)
        
        print(f"   Total trades: {stats['total_trades']}")
        print(f"   Win Rate: {stats['win_rate']:.1f}%")
        print(f"   Profit Factor: {stats['profit_factor']:.2f}")
        print(f"   P/L Total: {stats['total_profit_loss']:.2f}")
        print(f"   Média ganho: {stats['avg_win']:.2f}")
        print(f"   Média perda: {stats['avg_loss']:.2f}")
        
        # Mostrar alguns resultados de trades
        print("\n4. Últimos 5 trades:")
        for result in results[-5:]:
            direction = "LONG" if result.signal.direction == SignalDirection.BULLISH else "SHORT"
            outcome = "TP" if result.hit_tp else ("SL" if result.hit_sl else "OPEN")
            print(f"   {direction} | P/L: {result.profit_loss:.2f} | {outcome} | Duração: {result.duration_candles} candles")
    
    return strategy, signals


def exemplo_analise_completa():
    """Exemplo de análise completa com DataFrame"""
    print("\n" + "=" * 60)
    print("EXEMPLO ANÁLISE COMPLETA")
    print("=" * 60)
    
    # Carregar dados
    df = pd.read_csv('/home/ubuntu/smc_enhanced/data.csv')
    df.columns = [c.lower() for c in df.columns]
    df['time'] = pd.to_datetime(df['time'])
    df.set_index('time', inplace=True)
    
    # Usar últimos 2000 candles
    df = df.tail(2000)
    
    if 'volume' not in df.columns:
        df['volume'] = df.get('tick_volume', df.get('real_volume', 1.0))
    
    # Criar estratégia
    strategy = OrderBlockStrategy(
        df,
        swing_length=5,
        risk_reward_ratio=3.0,
        min_confidence=40.0,
        entry_delay_candles=1,
    )
    
    # Obter DataFrame com todos os indicadores
    analysis_df = strategy.get_analysis_dataframe()
    
    print(f"\nDataFrame de análise: {len(analysis_df)} linhas")
    print(f"Colunas disponíveis:")
    for col in analysis_df.columns:
        print(f"   - {col}")
    
    # Filtrar Order Blocks com alta confiança
    high_conf_obs = analysis_df[
        (analysis_df['OB'].notna()) & 
        (analysis_df['OB_Confidence'] >= 60)
    ]
    
    print(f"\nOrder Blocks com confiança >= 60%: {len(high_conf_obs)}")
    
    if len(high_conf_obs) > 0:
        print("\nDetalhes:")
        for idx in high_conf_obs.index:
            row = high_conf_obs.loc[idx]
            direction = "BULLISH" if row['OB'] == 1 else "BEARISH"
            print(f"   {idx}: {direction}")
            print(f"      Top: {row['OB_Top']:.2f}")
            print(f"      Bottom: {row['OB_Bottom']:.2f}")
            print(f"      Confiança: {row['OB_Confidence']:.1f}%")
            print(f"      Volume: {row['OB_Volume']:.0f}")
    
    # Salvar análise
    output_path = '/home/ubuntu/smc_enhanced/example_analysis.csv'
    analysis_df.to_csv(output_path)
    print(f"\nAnálise salva em: {output_path}")
    
    return analysis_df


def exemplo_customizado():
    """Exemplo de configuração customizada"""
    print("\n" + "=" * 60)
    print("EXEMPLO CONFIGURAÇÃO CUSTOMIZADA")
    print("=" * 60)
    
    # Carregar dados
    df = pd.read_csv('/home/ubuntu/smc_enhanced/data.csv')
    df.columns = [c.lower() for c in df.columns]
    df['time'] = pd.to_datetime(df['time'])
    df.set_index('time', inplace=True)
    df = df.tail(3000)
    
    if 'volume' not in df.columns:
        df['volume'] = df.get('tick_volume', df.get('real_volume', 1.0))
    
    # Testar diferentes configurações
    configs = [
        {'swing_length': 3, 'rr': 2.0, 'conf': 40},
        {'swing_length': 5, 'rr': 3.0, 'conf': 50},
        {'swing_length': 10, 'rr': 4.0, 'conf': 60},
    ]
    
    print("\nComparando configurações:\n")
    
    for config in configs:
        strategy = OrderBlockStrategy(
            df,
            swing_length=config['swing_length'],
            risk_reward_ratio=config['rr'],
            min_confidence=config['conf'],
            entry_delay_candles=1,
        )
        
        signals = strategy.generate_signals()
        
        if len(signals) > 0:
            results, stats = strategy.backtest(signals)
            print(f"Swing={config['swing_length']}, RR={config['rr']}, Conf={config['conf']}%:")
            print(f"   Sinais: {len(signals)}")
            print(f"   Win Rate: {stats['win_rate']:.1f}%")
            print(f"   Profit Factor: {stats['profit_factor']:.2f}")
            print(f"   P/L Total: {stats['total_profit_loss']:.2f}")
            print()
        else:
            print(f"Swing={config['swing_length']}, RR={config['rr']}, Conf={config['conf']}%:")
            print(f"   Nenhum sinal gerado")
            print()


if __name__ == "__main__":
    # Executar todos os exemplos
    exemplo_basico()
    exemplo_estrategia()
    exemplo_analise_completa()
    exemplo_customizado()
    
    print("\n" + "=" * 60)
    print("EXEMPLOS CONCLUÍDOS")
    print("=" * 60)
