"""
Teste do Smart Money Concepts Enhanced com dados reais
======================================================
Este script testa todos os conceitos SMC com os dados fornecidos pelo usuário.
"""

import pandas as pd
import numpy as np
from smc_enhanced import SMCEnhanced, OrderBlockStrategy, validate_ohlc

def load_data(filepath: str) -> pd.DataFrame:
    """Carrega e prepara os dados do CSV"""
    df = pd.read_csv(filepath)
    
    # Normalizar colunas
    df.columns = [c.lower() for c in df.columns]
    
    # Configurar índice de tempo
    if 'time' in df.columns:
        df['time'] = pd.to_datetime(df['time'])
        df.set_index('time', inplace=True)
    
    # Garantir coluna de volume
    if 'volume' not in df.columns:
        if 'tick_volume' in df.columns:
            df['volume'] = df['tick_volume']
        elif 'real_volume' in df.columns:
            df['volume'] = df['real_volume']
        else:
            df['volume'] = 1.0
    
    return df


def test_all_concepts(df: pd.DataFrame) -> dict:
    """Testa todos os conceitos SMC"""
    results = {}
    
    print("=" * 70)
    print("TESTE COM DADOS REAIS - SMART MONEY CONCEPTS ENHANCED")
    print("=" * 70)
    print(f"\nDados carregados: {len(df)} candles")
    print(f"Período: {df.index[0]} a {df.index[-1]}")
    print(f"Preço: {df['close'].min():.2f} - {df['close'].max():.2f}")
    
    # Teste 1: Swing Highs/Lows
    print("\n" + "-" * 50)
    print("1. SWING HIGHS/LOWS")
    print("-" * 50)
    try:
        swing_hl = SMCEnhanced.swing_highs_lows(df, swing_length=5)
        swing_highs = (swing_hl['HighLow'] == 1).sum()
        swing_lows = (swing_hl['HighLow'] == -1).sum()
        print(f"   Swing Highs detectados: {swing_highs}")
        print(f"   Swing Lows detectados: {swing_lows}")
        print(f"   Total: {swing_highs + swing_lows}")
        results['swing_highs_lows'] = {
            'status': 'PASSED',
            'swing_highs': swing_highs,
            'swing_lows': swing_lows
        }
    except Exception as e:
        print(f"   ERRO: {e}")
        results['swing_highs_lows'] = {'status': 'FAILED', 'error': str(e)}
        swing_hl = None
    
    # Teste 2: FVG
    print("\n" + "-" * 50)
    print("2. FAIR VALUE GAP (FVG)")
    print("-" * 50)
    try:
        fvg = SMCEnhanced.fvg(df)
        bullish_fvg = (fvg['FVG'] == 1).sum()
        bearish_fvg = (fvg['FVG'] == -1).sum()
        print(f"   FVG Bullish: {bullish_fvg}")
        print(f"   FVG Bearish: {bearish_fvg}")
        print(f"   Total: {bullish_fvg + bearish_fvg}")
        results['fvg'] = {
            'status': 'PASSED',
            'bullish': bullish_fvg,
            'bearish': bearish_fvg
        }
    except Exception as e:
        print(f"   ERRO: {e}")
        results['fvg'] = {'status': 'FAILED', 'error': str(e)}
    
    # Teste 3: Order Blocks
    print("\n" + "-" * 50)
    print("3. ORDER BLOCKS")
    print("-" * 50)
    try:
        if swing_hl is not None:
            ob = SMCEnhanced.ob(df, swing_hl)
            bullish_ob = (ob['OB'] == 1).sum()
            bearish_ob = (ob['OB'] == -1).sum()
            
            # Estatísticas de confiança (Percentage)
            ob_valid = ob[ob['OB'].notna()]
            if len(ob_valid) > 0:
                avg_percentage = ob_valid['Percentage'].mean()
                max_percentage = ob_valid['Percentage'].max()
                min_percentage = ob_valid['Percentage'].min()
            else:
                avg_percentage = max_percentage = min_percentage = 0
            
            print(f"   Order Blocks Bullish: {bullish_ob}")
            print(f"   Order Blocks Bearish: {bearish_ob}")
            print(f"   Total: {bullish_ob + bearish_ob}")
            print(f"   Percentage médio: {avg_percentage:.1f}%")
            print(f"   Percentage range: {min_percentage:.1f}% - {max_percentage:.1f}%")
            
            results['order_blocks'] = {
                'status': 'PASSED',
                'bullish': bullish_ob,
                'bearish': bearish_ob,
                'avg_percentage': avg_percentage
            }
        else:
            print("   ERRO: swing_hl não disponível")
            results['order_blocks'] = {'status': 'SKIPPED'}
    except Exception as e:
        print(f"   ERRO: {e}")
        results['order_blocks'] = {'status': 'FAILED', 'error': str(e)}
    
    # Teste 4: BOS/CHoCH
    print("\n" + "-" * 50)
    print("4. BOS / CHoCH")
    print("-" * 50)
    try:
        if swing_hl is not None:
            bos_choch = SMCEnhanced.bos_choch(df, swing_hl)
            bullish_bos = (bos_choch['BOS'] == 1).sum()
            bearish_bos = (bos_choch['BOS'] == -1).sum()
            bullish_choch = (bos_choch['CHOCH'] == 1).sum()
            bearish_choch = (bos_choch['CHOCH'] == -1).sum()
            
            print(f"   BOS Bullish: {bullish_bos}")
            print(f"   BOS Bearish: {bearish_bos}")
            print(f"   CHoCH Bullish: {bullish_choch}")
            print(f"   CHoCH Bearish: {bearish_choch}")
            
            results['bos_choch'] = {
                'status': 'PASSED',
                'bos_bullish': bullish_bos,
                'bos_bearish': bearish_bos,
                'choch_bullish': bullish_choch,
                'choch_bearish': bearish_choch
            }
        else:
            print("   ERRO: swing_hl não disponível")
            results['bos_choch'] = {'status': 'SKIPPED'}
    except Exception as e:
        print(f"   ERRO: {e}")
        results['bos_choch'] = {'status': 'FAILED', 'error': str(e)}
    
    # Teste 5: Liquidity
    print("\n" + "-" * 50)
    print("5. LIQUIDITY")
    print("-" * 50)
    try:
        if swing_hl is not None:
            liq = SMCEnhanced.liquidity(df, swing_hl)
            bullish_liq = (liq['Liquidity'] == 1).sum()
            bearish_liq = (liq['Liquidity'] == -1).sum()
            swept_count = (liq['Swept'] > 0).sum()
            
            print(f"   Liquidity Bullish: {bullish_liq}")
            print(f"   Liquidity Bearish: {bearish_liq}")
            print(f"   Swept (varridas): {swept_count}")
            
            results['liquidity'] = {
                'status': 'PASSED',
                'bullish': bullish_liq,
                'bearish': bearish_liq,
                'swept': swept_count
            }
        else:
            print("   ERRO: swing_hl não disponível")
            results['liquidity'] = {'status': 'SKIPPED'}
    except Exception as e:
        print(f"   ERRO: {e}")
        results['liquidity'] = {'status': 'FAILED', 'error': str(e)}
    
    # Teste 6: Retracements
    print("\n" + "-" * 50)
    print("6. RETRACEMENTS")
    print("-" * 50)
    try:
        if swing_hl is not None:
            ret = SMCEnhanced.retracements(df, swing_hl)
            valid_ret = ret[ret['Direction'] != 0]
            if len(valid_ret) > 0:
                avg_current = valid_ret['CurrentRetracement%'].mean()
                avg_deepest = valid_ret['DeepestRetracement%'].mean()
            else:
                avg_current = avg_deepest = 0
            
            print(f"   Retracements calculados: {len(valid_ret)}")
            print(f"   Retração média atual: {avg_current:.1f}%")
            print(f"   Retração média mais profunda: {avg_deepest:.1f}%")
            
            results['retracements'] = {
                'status': 'PASSED',
                'count': len(valid_ret),
                'avg_current': avg_current,
                'avg_deepest': avg_deepest
            }
        else:
            print("   ERRO: swing_hl não disponível")
            results['retracements'] = {'status': 'SKIPPED'}
    except Exception as e:
        print(f"   ERRO: {e}")
        results['retracements'] = {'status': 'FAILED', 'error': str(e)}
    
    return results


def test_strategy(df: pd.DataFrame) -> dict:
    """Testa a estratégia de Order Block 3:1"""
    print("\n" + "=" * 70)
    print("TESTE DA ESTRATÉGIA ORDER BLOCK 3:1")
    print("=" * 70)
    
    results = {}
    
    # Testar com diferentes níveis de confiança
    confidence_levels = [30, 50, 70]
    
    for min_conf in confidence_levels:
        print(f"\n--- Confiança mínima: {min_conf}% ---")
        
        try:
            strategy = OrderBlockStrategy(
                df,
                swing_length=5,
                risk_reward_ratio=3.0,
                min_confidence=min_conf,
                entry_delay_candles=1,  # Entrada NÃO no mesmo candle
            )
            
            signals = strategy.generate_signals()
            
            # Verificar que entradas não ocorrem no mesmo candle
            entry_same_candle = 0
            for signal in signals:
                if signal.index <= signal.signal_candle_index:
                    entry_same_candle += 1
            
            print(f"   Sinais gerados: {len(signals)}")
            print(f"   Entradas no mesmo candle do sinal: {entry_same_candle}")
            
            if len(signals) > 0:
                # Distribuição de direção
                bullish = sum(1 for s in signals if s.direction.value == 1)
                bearish = sum(1 for s in signals if s.direction.value == -1)
                print(f"   Sinais Bullish: {bullish}")
                print(f"   Sinais Bearish: {bearish}")
                
                # Estatísticas de confiança
                confidences = [s.confidence for s in signals]
                print(f"   Confiança média: {np.mean(confidences):.1f}%")
                print(f"   Confiança range: {np.min(confidences):.1f}% - {np.max(confidences):.1f}%")
                
                # Backtest
                bt_results, stats = strategy.backtest(signals)
                
                print(f"\n   BACKTEST RESULTADOS:")
                print(f"   Total de trades: {stats['total_trades']}")
                print(f"   Trades vencedores: {stats['winning_trades']}")
                print(f"   Trades perdedores: {stats['losing_trades']}")
                print(f"   Win Rate: {stats['win_rate']:.1f}%")
                print(f"   Profit Factor: {stats['profit_factor']:.2f}")
                print(f"   P/L Total: {stats['total_profit_loss']:.2f}")
                print(f"   P/L Médio: {stats['avg_profit_loss']:.2f}")
                print(f"   Hit TP: {stats['hit_tp_count']}")
                print(f"   Hit SL: {stats['hit_sl_count']}")
                print(f"   Duração média: {stats['avg_duration']:.0f} candles")
                
                results[f'confidence_{min_conf}'] = {
                    'status': 'PASSED',
                    'signals': len(signals),
                    'entry_same_candle': entry_same_candle,
                    'stats': stats
                }
            else:
                print("   Nenhum sinal gerado com este nível de confiança")
                results[f'confidence_{min_conf}'] = {
                    'status': 'PASSED',
                    'signals': 0,
                    'entry_same_candle': 0
                }
                
        except Exception as e:
            print(f"   ERRO: {e}")
            import traceback
            traceback.print_exc()
            results[f'confidence_{min_conf}'] = {'status': 'FAILED', 'error': str(e)}
    
    return results


def generate_analysis_report(df: pd.DataFrame, output_path: str):
    """Gera um relatório completo de análise"""
    print("\n" + "=" * 70)
    print("GERANDO RELATÓRIO DE ANÁLISE")
    print("=" * 70)
    
    try:
        strategy = OrderBlockStrategy(
            df,
            swing_length=5,
            risk_reward_ratio=3.0,
            min_confidence=40.0,
            entry_delay_candles=1,
        )
        
        analysis_df = strategy.get_analysis_dataframe()
        
        # Salvar análise completa
        analysis_df.to_csv(output_path)
        print(f"\n   Relatório salvo em: {output_path}")
        print(f"   Colunas: {list(analysis_df.columns)}")
        
        # Resumo dos Order Blocks com confiança
        ob_df = analysis_df[analysis_df['OB'].notna()][['OB', 'OB_Top', 'OB_Bottom', 'OB_Confidence']]
        if len(ob_df) > 0:
            print(f"\n   Order Blocks detectados: {len(ob_df)}")
            print("\n   Top 10 Order Blocks por Confiança:")
            top_obs = ob_df.nlargest(10, 'OB_Confidence')
            for idx, row in top_obs.iterrows():
                direction = "BULLISH" if row['OB'] == 1 else "BEARISH"
                print(f"      {idx}: {direction} | Top: {row['OB_Top']:.2f} | Bottom: {row['OB_Bottom']:.2f} | Confiança: {row['OB_Confidence']:.1f}%")
        
        return True
        
    except Exception as e:
        print(f"   ERRO: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # Carregar dados
    data_path = "/home/ubuntu/smc_enhanced/data.csv"
    df = load_data(data_path)
    
    # Testar todos os conceitos
    concept_results = test_all_concepts(df)
    
    # Testar estratégia
    strategy_results = test_strategy(df)
    
    # Gerar relatório
    generate_analysis_report(df, "/home/ubuntu/smc_enhanced/analysis_report.csv")
    
    # Resumo final
    print("\n" + "=" * 70)
    print("RESUMO FINAL")
    print("=" * 70)
    
    all_passed = True
    for name, result in concept_results.items():
        status = "✓" if result['status'] == 'PASSED' else "✗"
        print(f"   {status} {name}: {result['status']}")
        if result['status'] != 'PASSED':
            all_passed = False
    
    for name, result in strategy_results.items():
        status = "✓" if result['status'] == 'PASSED' else "✗"
        print(f"   {status} Strategy {name}: {result['status']}")
        if result['status'] != 'PASSED':
            all_passed = False
    
    if all_passed:
        print("\n   ✓ TODOS OS TESTES PASSARAM!")
    else:
        print("\n   ✗ ALGUNS TESTES FALHARAM")
