"""
Validação V2: Investigar diferença entre batch e engine V2.
Testar com e sem expiração para igualar resultados.
"""

import sys
sys.path.insert(0, 'app')
sys.path.insert(0, '/home/ubuntu/smc_enhanced')

import pandas as pd
import numpy as np
from smc_engine_v2 import SMCEngineV2, OrderStatus, SignalDirection

def load_data():
    df = pd.read_csv('/home/ubuntu/upload/mtwin14400.csv')
    df.columns = [c.lower() for c in df.columns]
    if 'volume' not in df.columns:
        df['volume'] = df.get('tick_volume', df.get('real_volume', 1.0))
    return df

def run_engine(df, max_pending=100):
    engine = SMCEngineV2(
        symbol='WINM24',
        swing_length=5,
        risk_reward_ratio=3.0,
        min_volume_ratio=1.5,
        min_ob_size_atr=0.5,
        use_not_mitigated_filter=True,
        max_pending_candles=max_pending,
        entry_delay_candles=1,
    )
    
    vol_col = 'tick_volume' if 'tick_volume' in df.columns else 'volume'
    
    for i in range(len(df)):
        row = df.iloc[i]
        candle = {
            'time': str(row.get('time', '')),
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
            'volume': float(row[vol_col])
        }
        engine.add_candle(candle)
    
    return engine

def main():
    df = load_data()
    print(f"Dados: {len(df)} candles")
    
    # Testar com diferentes max_pending
    print("\n" + "=" * 100)
    print("TESTE: IMPACTO DA EXPIRAÇÃO DE ORDENS")
    print("=" * 100)
    
    for max_pending in [100, 200, 500, 1000, 10000]:
        engine = run_engine(df, max_pending=max_pending)
        stats = engine.get_stats()
        trades = engine.get_all_trades()
        
        # Calcular por padrão
        pattern_wins = {}
        for t in trades:
            for p in t['patterns']:
                if p not in pattern_wins:
                    pattern_wins[p] = {'wins': 0, 'losses': 0}
                if t['status'] == 'closed_tp':
                    pattern_wins[p]['wins'] += 1
                else:
                    pattern_wins[p]['losses'] += 1
        
        print(f"\n  Max Pending: {max_pending} candles")
        print(f"    Trades: {stats['closed_orders']}")
        print(f"    Win Rate: {stats['win_rate']:.1f}%")
        print(f"    PF: {stats['profit_factor']:.2f}")
        print(f"    Lucro: {stats['total_profit_points']:+.2f} pts")
        print(f"    Win pts: {stats['total_win_points']:+.2f}")
        print(f"    Loss pts: {stats['total_loss_points']:+.2f}")
        
        if trades:
            waits = [t['wait_candles'] for t in trades]
            print(f"    Espera média: {np.mean(waits):.1f} candles")
            print(f"    Espera max: {max(waits)} candles")
            print(f"    Duração média: {np.mean([t['duration'] for t in trades]):.1f} candles")
        
        print(f"    Padrões:")
        for p, v in sorted(pattern_wins.items()):
            total = v['wins'] + v['losses']
            wr = v['wins'] / total * 100 if total > 0 else 0
            print(f"      {p:<10} {total:>5} trades, WR={wr:.1f}%")
    
    # Usar a melhor configuração e gerar tabela
    print("\n" + "=" * 100)
    print("VALIDAÇÃO DE INTEGRIDADE (max_pending=100)")
    print("=" * 100)
    
    engine = run_engine(df, max_pending=100)
    trades = engine.get_all_trades()
    
    # Teste 1: OBs Mitigados
    mitigated_trades = 0
    for trade in trades:
        ob = next((ob for ob in engine.active_obs if ob.id == trade['ob_id']), None)
        if ob and ob.is_mitigated and ob.mitigated_at < trade['filled_at']:
            mitigated_trades += 1
    print(f"\n  OBs mitigados usados: {mitigated_trades} → {'✅ PASSOU' if mitigated_trades == 0 else '❌ FALHOU'}")
    
    # Teste 2: Sequência temporal
    violations = sum(1 for t in trades if t['filled_at'] <= t['created_at'] or t['closed_at'] <= t['filled_at'])
    print(f"  Violações temporais: {violations} → {'✅ PASSOU' if violations == 0 else '❌ FALHOU'}")
    
    # Teste 3: Toque real
    invalid_touches = 0
    for t in trades:
        if t['direction'] == 'BULLISH':
            if engine.cache.lows[t['filled_at']] > t['entry_price']:
                invalid_touches += 1
        else:
            if engine.cache.highs[t['filled_at']] < t['entry_price']:
                invalid_touches += 1
    print(f"  Toques inválidos: {invalid_touches} → {'✅ PASSOU' if invalid_touches == 0 else '❌ FALHOU'}")
    
    # Teste 4: TP/SL correto
    tp_sl_errors = 0
    for t in trades:
        ci = t['closed_at']
        if t['status'] == 'closed_tp':
            if t['direction'] == 'BULLISH' and engine.cache.highs[ci] < t['take_profit']:
                tp_sl_errors += 1
            elif t['direction'] == 'BEARISH' and engine.cache.lows[ci] > t['take_profit']:
                tp_sl_errors += 1
        elif t['status'] == 'closed_sl':
            if t['direction'] == 'BULLISH' and engine.cache.lows[ci] > t['stop_loss']:
                tp_sl_errors += 1
            elif t['direction'] == 'BEARISH' and engine.cache.highs[ci] < t['stop_loss']:
                tp_sl_errors += 1
    print(f"  Erros TP/SL: {tp_sl_errors} → {'✅ PASSOU' if tp_sl_errors == 0 else '❌ FALHOU'}")
    
    # Tabela de trades
    print("\n" + "=" * 100)
    print("TABELA DE TRADES (primeiros 30)")
    print("=" * 100)
    
    print(f"\n{'ID':<12} {'Dir':<10} {'Entry':<14} {'SL':<14} {'TP':<14} "
          f"{'Criado':<8} {'Fill':<8} {'Close':<8} {'Status':<12} {'P/L':<12} "
          f"{'Espera':<8} {'Dur':<6} {'Conf':<6}")
    print("-" * 140)
    
    for t in trades[:30]:
        print(f"{t['id']:<12} {t['direction']:<10} {t['entry_price']:<14.2f} "
              f"{t['stop_loss']:<14.2f} {t['take_profit']:<14.2f} "
              f"{t['created_at']:<8} {t['filled_at']:<8} {t['closed_at']:<8} "
              f"{t['status']:<12} {t['profit_loss']:<+12.2f} "
              f"{t['wait_candles']:<8} {t['duration']:<6} {t['confidence']:<6.1f}")


if __name__ == "__main__":
    main()
