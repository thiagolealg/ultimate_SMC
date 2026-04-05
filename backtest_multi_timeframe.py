"""
Backtest Multi-Timeframe da Engine SMC V3
==========================================

Roda a engine em múltiplos timeframes (M1, M5, M15, H1, H4, D1) 
usando os mesmos dados de entrada com agregação de candles.
"""

import sys
sys.path.insert(0, '.')
from smc_engine_v3 import SMCEngineV3
import pandas as pd
import json
from datetime import datetime, timedelta

def load_backtest_data():
    """Carrega dados do backtest M1"""
    try:
        with open('dashboard/client/src/data/backtest-data.json', 'r') as f:
            data = json.load(f)
        return data['candles']
    except:
        print("Erro ao carregar dados. Usando dados de teste.")
        return None

def aggregate_candles(candles, multiplier):
    """Agrega candles M1 para timeframes maiores"""
    aggregated = []
    buffer = []
    
    for candle in candles:
        buffer.append(candle)
        
        if len(buffer) == multiplier:
            # Agregar
            agg_candle = {
                'open': buffer[0]['open'],
                'high': max(c['high'] for c in buffer),
                'low': min(c['low'] for c in buffer),
                'close': buffer[-1]['close'],
                'volume': sum(c.get('volume', 0) for c in buffer)
            }
            aggregated.append(agg_candle)
            buffer = []
    
    # Processar buffer restante se houver
    if buffer:
        agg_candle = {
            'open': buffer[0]['open'],
            'high': max(c['high'] for c in buffer),
            'low': min(c['low'] for c in buffer),
            'close': buffer[-1]['close'],
            'volume': sum(c.get('volume', 0) for c in buffer)
        }
        aggregated.append(agg_candle)
    
    return aggregated

def run_backtest_timeframe(candles, timeframe_name, swing_length=5):
    """Roda backtest em um timeframe específico"""
    
    engine = SMCEngineV3(
        symbol='TEST',
        swing_length=swing_length,
        risk_reward_ratio=3.0,
        min_volume_ratio=0.0,
        min_ob_size_atr=0.0,
        use_not_mitigated_filter=True,
        max_pending_candles=150,
        entry_delay_candles=1,
    )
    
    print(f"\n{'='*80}")
    print(f"BACKTEST: {timeframe_name}")
    print(f"{'='*80}")
    print(f"Total de candles: {len(candles)}")
    
    for i, candle in enumerate(candles):
        events = engine.add_candle(candle)
    
    # Coletar estatísticas
    stats = engine.get_stats()
    
    return {
        'timeframe': timeframe_name,
        'candles_count': len(candles),
        'swings_high': len(engine.swing_highs),
        'swings_low': len(engine.swing_lows),
        'order_blocks': len(engine.active_obs),
        'order_blocks_active': sum(1 for ob in engine.active_obs if not ob.mitigated),
        'order_blocks_mitigated': sum(1 for ob in engine.active_obs if ob.mitigated),
        'total_trades': stats['total_trades'],
        'winning_trades': stats['winning_trades'],
        'losing_trades': stats['losing_trades'],
        'total_points': stats['total_profit_points'],
        'win_rate': stats['win_rate'],
        'profit_factor': stats['profit_factor'],
        'expectancy': stats['avg_profit_r'],
        'pending_orders': stats['pending_orders'],
        'open_trades': stats['open_trades'],
    }

def main():
    # Carregar dados
    candles_m1 = load_backtest_data()
    
    if not candles_m1:
        print("Erro: Não foi possível carregar dados de backtest.")
        return
    
    print(f"\n{'='*80}")
    print(f"BACKTEST MULTI-TIMEFRAME - SMC ENGINE V3")
    print(f"{'='*80}")
    print(f"Dados carregados: {len(candles_m1)} candles M1")
    
    # Definir timeframes e multiplicadores
    timeframes = [
        ('M1', 1),
        ('M5', 5),
        ('M15', 15),
        ('H1', 60),
        ('H4', 240),
        ('D1', 1440),
    ]
    
    results = []
    
    for tf_name, multiplier in timeframes:
        # Agregar candles
        if multiplier == 1:
            candles = candles_m1
        else:
            candles = aggregate_candles(candles_m1, multiplier)
        
        # Rodar backtest
        result = run_backtest_timeframe(candles, tf_name)
        results.append(result)
        
        # Imprimir resumo
        print(f"\nRESUMO {tf_name}:")
        print(f"  Candles: {result['candles_count']}")
        print(f"  Swings High: {result['swings_high']}")
        print(f"  Swings Low: {result['swings_low']}")
        print(f"  Order Blocks: {result['order_blocks']} (Ativos: {result['order_blocks_active']}, Mitigados: {result['order_blocks_mitigated']})")
        print(f"  Trades Totais: {result['total_trades']} (Ganhos: {result['winning_trades']}, Perdidos: {result['losing_trades']})")
        print(f"  Total de Pontos: {result['total_points']:.2f}")
        print(f"  Win Rate: {result['win_rate']:.1f}%")
        print(f"  Profit Factor: {result['profit_factor']:.2f}")
        print(f"  Expectancy: {result['expectancy']:.2f}R")
        print(f"  Ordens Pendentes: {result['pending_orders']}, Trades Abertos: {result['open_trades']}")
    
    # Salvar resultados
    with open('backtest_multi_timeframe_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n{'='*80}")
    print(f"RESULTADOS SALVOS: backtest_multi_timeframe_results.json")
    print(f"{'='*80}")
    
    # Criar tabela comparativa
    df = pd.DataFrame(results)
    print("\n" + "="*80)
    print("TABELA COMPARATIVA")
    print("="*80)
    print(df.to_string(index=False))
    
    return results

if __name__ == '__main__':
    results = main()
