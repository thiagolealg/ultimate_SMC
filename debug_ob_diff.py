"""
Debug: Encontrar por que batch detecta OBs que engine V2 não detecta.
Foco no trade #4 do batch: OB_idx=2184, Entry_idx=2190
"""

import sys
sys.path.insert(0, 'app')
sys.path.insert(0, '/home/ubuntu/smc_enhanced')

import pandas as pd
import numpy as np
from smc_engine_v2 import SMCEngineV2, OrderStatus, SignalDirection
from smc_touch_validated import SMCStrategyTouchValidated, SMCIndicators

def load_data():
    df = pd.read_csv('/home/ubuntu/upload/mtwin14400.csv')
    df.columns = [c.lower() for c in df.columns]
    if 'volume' not in df.columns:
        df['volume'] = df.get('tick_volume', df.get('real_volume', 1.0))
    return df

def main():
    df = load_data()
    
    # Batch: quais OBs foram detectados?
    strategy = SMCStrategyTouchValidated(
        df, swing_length=5, risk_reward_ratio=3.0,
        entry_delay_candles=1, use_not_mitigated_filter=True,
        min_volume_ratio=1.5, min_ob_size_atr=0.5,
    )
    
    ob_data = strategy.order_blocks
    ob_indices = ob_data[~ob_data['OB'].isna()]
    
    # Engine V2
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
    
    # Comparar OBs detectados
    batch_ob_set = set()
    for idx in ob_indices.index:
        i = df.index.get_loc(idx)
        batch_ob_set.add((i, ob_data.loc[idx, 'OB'], ob_data.loc[idx, 'Top'], ob_data.loc[idx, 'Bottom']))
    
    engine_ob_set = set()
    for ob in engine.active_obs:
        engine_ob_set.add((ob.confirmation_index, 1 if ob.direction == SignalDirection.BULLISH else -1, ob.top, ob.bottom))
    
    print(f"Batch OBs: {len(batch_ob_set)}")
    print(f"Engine OBs: {len(engine_ob_set)}")
    
    # OBs no batch mas não no engine
    batch_only = []
    for b_ob in batch_ob_set:
        found = False
        for e_ob in engine_ob_set:
            if abs(b_ob[0] - e_ob[0]) <= 1 and b_ob[1] == e_ob[1] and abs(b_ob[2] - e_ob[2]) < 1:
                found = True
                break
        if not found:
            batch_only.append(b_ob)
    
    engine_only = []
    for e_ob in engine_ob_set:
        found = False
        for b_ob in batch_ob_set:
            if abs(b_ob[0] - e_ob[0]) <= 1 and b_ob[1] == e_ob[1] and abs(b_ob[2] - e_ob[2]) < 1:
                found = True
                break
        if not found:
            engine_only.append(e_ob)
    
    print(f"\nOBs apenas no BATCH: {len(batch_only)}")
    for ob in sorted(batch_only)[:20]:
        print(f"  idx={ob[0]}, dir={'BULL' if ob[1]==1 else 'BEAR'}, top={ob[2]:.2f}, bottom={ob[3]:.2f}")
    
    print(f"\nOBs apenas no ENGINE: {len(engine_only)}")
    for ob in sorted(engine_only)[:20]:
        print(f"  idx={ob[0]}, dir={'BULL' if ob[1]==1 else 'BEAR'}, top={ob[2]:.2f}, bottom={ob[3]:.2f}")
    
    # Investigar o OB 2184 do batch
    print("\n" + "=" * 80)
    print("INVESTIGAÇÃO: OB idx=2184 do batch")
    print("=" * 80)
    
    idx_2184 = df.index[2184]
    if idx_2184 in ob_indices.index:
        ob_info = ob_data.loc[idx_2184]
        print(f"  Direção: {'BULL' if ob_info['OB']==1 else 'BEAR'}")
        print(f"  Top: {ob_info['Top']:.2f}")
        print(f"  Bottom: {ob_info['Bottom']:.2f}")
        print(f"  OB Candle: {ob_info['OBCandle']}")
        print(f"  Mitigated: {ob_info['MitigatedIndex']}")
    
    # Swings do batch
    swings = strategy.swings
    
    # Verificar swings perto de 2184
    print("\n  Swings próximos:")
    for i in range(2170, 2200):
        if swings['swing_high'].iloc[i] == 1:
            print(f"    Swing HIGH em i={i}, level={swings['swing_high_level'].iloc[i]:.2f}")
        if swings['swing_low'].iloc[i] == 1:
            print(f"    Swing LOW em i={i}, level={swings['swing_low_level'].iloc[i]:.2f}")
    
    # Verificar swings do engine perto de 2184
    print("\n  Engine swings próximos:")
    for sh_idx, sh_level in engine.swing_highs:
        if 2170 <= sh_idx <= 2200:
            print(f"    Swing HIGH em idx={sh_idx}, level={sh_level:.2f}")
    for sl_idx, sl_level in engine.swing_lows:
        if 2170 <= sl_idx <= 2200:
            print(f"    Swing LOW em idx={sl_idx}, level={sl_level:.2f}")
    
    # Diferença chave: no batch, o swing é marcado no candle i
    # mas o candidato é i - swing_length
    # No engine, o swing é armazenado como (candidate_idx, level)
    # Mas o OB é confirmado quando close > last_top_level
    # No batch, last_top_idx = i - swing_length (candidato)
    # No engine, last_top_idx = candidate_idx
    
    print("\n" + "=" * 80)
    print("COMPARAÇÃO: Swings batch vs engine (primeiros 100)")
    print("=" * 80)
    
    batch_swings_h = [(i, swings['swing_high_level'].iloc[i]) 
                       for i in range(len(swings)) 
                       if swings['swing_high'].iloc[i] == 1][:100]
    
    engine_swings_h = engine.swing_highs[:100]
    
    print(f"\n  Batch swing highs: {len(batch_swings_h)}")
    print(f"  Engine swing highs: {len(engine_swings_h)}")
    
    # Comparar
    for i in range(min(10, len(batch_swings_h), len(engine_swings_h))):
        b = batch_swings_h[i]
        e = engine_swings_h[i]
        match = "✅" if abs(b[1] - e[1]) < 0.01 else "❌"
        print(f"    Batch: idx={b[0]}, level={b[1]:.2f}  |  Engine: idx={e[0]}, level={e[1]:.2f}  {match}")
    
    # DIFERENÇA CHAVE: No batch, swing é registrado em i (candle de confirmação)
    # mas last_top_idx = i - swing_length (candidato)
    # No engine, swing é registrado em candidate_idx
    # Isso pode causar diferença no OB detection
    
    print("\n" + "=" * 80)
    print("DIFERENÇA CHAVE")
    print("=" * 80)
    print("  BATCH: Swing HIGH registrado em i (confirmação), last_top_idx = i - swing_length")
    print("  ENGINE: Swing HIGH registrado em candidate_idx, last_top_idx = candidate_idx")
    print("  BATCH: OB confirmado quando close[i] > last_top_level (no loop geral)")
    print("  ENGINE: OB confirmado quando close[idx] > last_top_level (no add_candle)")
    print()
    print("  A diferença é que no BATCH, o swing e o OB podem ser detectados")
    print("  no MESMO candle (i), enquanto no ENGINE, o swing é detectado")
    print("  e o last_top_idx é atualizado, mas o OB só é verificado no")
    print("  MESMO candle, e o close pode já ter rompido o swing.")


if __name__ == "__main__":
    main()
