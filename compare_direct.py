"""
Comparação direta: entender por que batch tem 48% WR e engine V2 tem 20% WR.

A diferença principal é que o batch usa mitigated_index com LOOK-AHEAD:
- Linha 464: for k in range(i + 1, n):  ← olha TODOS os candles futuros
- Isso significa que o batch SABE quando o OB será mitigado no futuro
- E para de buscar entrada nesse ponto

O engine V2 NÃO tem esse look-ahead, então:
- Permite que ordens fiquem pendentes por muito tempo
- Ordens preenchidas em OBs que já foram "ultrapassados" perdem

SOLUÇÃO: No engine V2, verificar mitigação em TEMPO REAL:
- A cada candle, verificar se o preço ultrapassou o OB
- Se sim, marcar como mitigado e cancelar ordens pendentes
- Isso é equivalente ao batch mas SEM look-ahead

PROBLEMA REAL: O batch busca entrada em range(i+1, i+100) e verifica
mitigação DENTRO desse loop. O engine V2 cria uma ordem pendente e
espera. A diferença é que o batch verifica candle a candle se o OB
foi mitigado ANTES de verificar o toque.

Vamos replicar essa lógica exata no engine V2.
"""

import sys
sys.path.insert(0, 'app')
sys.path.insert(0, '/home/ubuntu/smc_enhanced')

import pandas as pd
import numpy as np
from smc_engine_v2 import SMCEngineV2, OrderStatus, SignalDirection
from smc_touch_validated import SMCStrategyTouchValidated

def load_data():
    df = pd.read_csv('/home/ubuntu/upload/mtwin14400.csv')
    df.columns = [c.lower() for c in df.columns]
    if 'volume' not in df.columns:
        df['volume'] = df.get('tick_volume', df.get('real_volume', 1.0))
    return df

def main():
    df = load_data()
    print(f"Dados: {len(df)} candles")
    
    # ========== BATCH ==========
    print("\n--- BATCH (smc_touch_validated.py) ---")
    strategy = SMCStrategyTouchValidated(
        df, swing_length=5, risk_reward_ratio=3.0,
        entry_delay_candles=1, use_not_mitigated_filter=True,
        min_volume_ratio=1.5, min_ob_size_atr=0.5,
    )
    signals = strategy.generate_signals()
    results, stats = strategy.backtest(signals)
    
    print(f"  Trades: {stats['total_trades']}")
    print(f"  Win Rate: {stats['win_rate']:.1f}%")
    print(f"  Lucro (R): {stats['total_profit_loss_r']:.1f}R")
    
    # Analisar espera dos sinais batch
    waits = [s.index - s.signal_candle_index for s in signals]
    print(f"  Espera média: {np.mean(waits):.1f} candles")
    print(f"  Espera max: {max(waits)} candles")
    
    # Verificar mitigação no batch
    ob_data = strategy.order_blocks
    ob_indices = ob_data[~ob_data['OB'].isna()].index
    
    total_obs = len(ob_indices)
    mitigated_obs = sum(1 for idx in ob_indices if not np.isnan(ob_data.loc[idx, 'MitigatedIndex']))
    print(f"  OBs totais: {total_obs}")
    print(f"  OBs mitigados: {mitigated_obs}")
    
    # Verificar: quantos sinais teriam sido gerados SEM o filtro de mitigação?
    print("\n--- BATCH SEM FILTRO MITIGAÇÃO ---")
    strategy2 = SMCStrategyTouchValidated(
        df, swing_length=5, risk_reward_ratio=3.0,
        entry_delay_candles=1, use_not_mitigated_filter=False,
        min_volume_ratio=1.5, min_ob_size_atr=0.5,
    )
    signals2 = strategy2.generate_signals()
    results2, stats2 = strategy2.backtest(signals2)
    
    print(f"  Trades: {stats2['total_trades']}")
    print(f"  Win Rate: {stats2['win_rate']:.1f}%")
    print(f"  Lucro (R): {stats2['total_profit_loss_r']:.1f}R")
    
    # ========== ENGINE V2 ==========
    print("\n--- ENGINE V2 (candle a candle) ---")
    engine = SMCEngineV2(
        symbol='WINM24', swing_length=5, risk_reward_ratio=3.0,
        min_volume_ratio=1.5, min_ob_size_atr=0.5,
        use_not_mitigated_filter=True, max_pending_candles=100,
        entry_delay_candles=1,
    )
    
    vol_col = 'tick_volume' if 'tick_volume' in df.columns else 'volume'
    for i in range(len(df)):
        row = df.iloc[i]
        engine.add_candle({
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
            'volume': float(row[vol_col])
        })
    
    stats_v2 = engine.get_stats()
    trades_v2 = engine.get_all_trades()
    
    print(f"  Trades: {stats_v2['closed_orders']}")
    print(f"  Win Rate: {stats_v2['win_rate']:.1f}%")
    print(f"  Lucro: {stats_v2['total_profit_points']:+.2f} pts")
    print(f"  OBs detectados: {stats_v2['order_blocks_detected']}")
    
    if trades_v2:
        waits_v2 = [t['wait_candles'] for t in trades_v2]
        print(f"  Espera média: {np.mean(waits_v2):.1f} candles")
        print(f"  Espera max: {max(waits_v2)} candles")
    
    # Comparar primeiros trades
    print("\n" + "=" * 100)
    print("PRIMEIROS 10 TRADES - BATCH")
    print("=" * 100)
    for i, r in enumerate(results[:10]):
        s = r.signal
        print(f"  #{i+1}: Dir={s.direction.name} OB_idx={s.signal_candle_index} "
              f"Entry_idx={s.index} Entry={s.entry_price:.2f} "
              f"SL={s.stop_loss:.2f} TP={s.take_profit:.2f} "
              f"Exit_idx={r.exit_index} P/L={r.profit_loss:+.2f} "
              f"{'TP' if r.hit_tp else 'SL'}")
    
    print("\n" + "=" * 100)
    print("PRIMEIROS 10 TRADES - ENGINE V2")
    print("=" * 100)
    for i, t in enumerate(trades_v2[:10]):
        print(f"  #{i+1}: Dir={t['direction']} Created={t['created_at']} "
              f"Fill={t['filled_at']} Entry={t['entry_price']:.2f} "
              f"SL={t['stop_loss']:.2f} TP={t['take_profit']:.2f} "
              f"Close={t['closed_at']} P/L={t['profit_loss']:+.2f} "
              f"{t['status']}")
    
    # ========== ANÁLISE: POR QUE A DIFERENÇA? ==========
    print("\n" + "=" * 100)
    print("ANÁLISE DA DIFERENÇA")
    print("=" * 100)
    
    # Contar ordens expiradas e canceladas
    expired = sum(1 for o in engine.closed_orders if o.status == OrderStatus.EXPIRED)
    cancelled = sum(1 for o in engine.closed_orders if o.status == OrderStatus.CANCELLED)
    total_orders = engine.order_counter
    
    print(f"  Total de ordens criadas: {total_orders}")
    print(f"  Ordens preenchidas (trades): {stats_v2['closed_orders']}")
    print(f"  Ordens expiradas: {expired}")
    print(f"  Ordens canceladas (OB mitigado): {cancelled}")
    print(f"  Ordens ainda pendentes: {len(engine.pending_orders)}")
    print(f"  Ordens ainda abertas: {len(engine.filled_orders)}")


if __name__ == "__main__":
    main()
