"""
Teste Completo de Identificação de Padrões SMC POI - CORRIGIDO
==============================================================

PADRÃO BULLISH (com perna de ALTA inicial):
1. Swing High inicial (perna de ALTA) - candles 0-4
2. Swing Low (perna de baixa) - candles 5-9
3. Swing High (perna de alta) - candles 10-14
4. Swing Low mais baixa (quebra fundo) - candles 15-19
5. Swing High (BOS - rompe alta anterior) - candles 20-24

PADRÃO BEARISH (com perna de BAIXA inicial):
1. Swing Low inicial (perna de BAIXA) - candles 30-34
2. Swing High (perna de alta) - candles 35-39
3. Swing Low (perna de baixa) - candles 40-44
4. Swing High mais alta (quebra topo) - candles 45-49
5. Swing Low (CHoCH - rompe baixa anterior) - candles 50-54
"""

import sys
sys.path.insert(0, '.')
from smc_engine_v3 import SMCEngineV3, SignalDirection

# ============================================================================
# PADRÃO BULLISH: SH inicial (alta) → SL (baixa) → SH (alta) → SL+ (quebra) → SH (BOS)
# ============================================================================
print("="*80)
print("PADRÃO BULLISH - SH (ALTA) → SL → SH → SL+ (quebra) → SH (BOS)")
print("="*80)

engine = SMCEngineV3(
    symbol='TEST',
    swing_length=5,
    risk_reward_ratio=3.0,
    min_volume_ratio=0.0,
    min_ob_size_atr=0.0,
    use_not_mitigated_filter=True,
    max_pending_candles=150,
    entry_delay_candles=1,
)

candles_bullish = [
    # Fase 0: SWING HIGH INICIAL (perna de ALTA) - candles 0-4
    {'open': 50, 'high': 51, 'low': 49, 'close': 51, 'volume': 1000},       # 0
    {'open': 51, 'high': 52, 'low': 50, 'close': 52, 'volume': 1000},       # 1
    {'open': 52, 'high': 53, 'low': 51, 'close': 53, 'volume': 1000},       # 2
    {'open': 53, 'high': 54, 'low': 52, 'close': 54, 'volume': 1000},       # 3
    {'open': 54, 'high': 70, 'low': 53, 'close': 70, 'volume': 1000},       # 4 - Swing High inicial (high=70)
    
    # Fase 1: SWING LOW (perna de BAIXA) - candles 5-9
    {'open': 70, 'high': 69, 'low': 68, 'close': 68, 'volume': 1000},       # 5
    {'open': 68, 'high': 67, 'low': 66, 'close': 66, 'volume': 1000},       # 6
    {'open': 66, 'high': 65, 'low': 64, 'close': 64, 'volume': 1000},       # 7
    {'open': 64, 'high': 63, 'low': 62, 'close': 62, 'volume': 1000},       # 8
    {'open': 62, 'high': 61, 'low': 45, 'close': 45, 'volume': 1000},       # 9 - Swing Low (low=45)
    
    # Fase 2: SWING HIGH (perna de ALTA) - candles 10-14
    {'open': 45, 'high': 46, 'low': 44, 'close': 46, 'volume': 1000},       # 10
    {'open': 46, 'high': 47, 'low': 45, 'close': 47, 'volume': 1000},       # 11
    {'open': 47, 'high': 48, 'low': 46, 'close': 48, 'volume': 1000},       # 12
    {'open': 48, 'high': 49, 'low': 47, 'close': 49, 'volume': 1000},       # 13
    {'open': 49, 'high': 65, 'low': 48, 'close': 65, 'volume': 1000},       # 14 - Swing High (high=65)
    
    # Fase 3: SWING LOW MAIS BAIXA (quebra fundo de 45) - candles 15-19
    {'open': 65, 'high': 64, 'low': 63, 'close': 63, 'volume': 1000},       # 15
    {'open': 63, 'high': 62, 'low': 61, 'close': 61, 'volume': 1000},       # 16
    {'open': 61, 'high': 60, 'low': 59, 'close': 59, 'volume': 1000},       # 17
    {'open': 59, 'high': 58, 'low': 57, 'close': 57, 'volume': 1000},       # 18
    {'open': 57, 'high': 56, 'low': 30, 'close': 30, 'volume': 1000},       # 19 - Swing Low+ (low=30, quebra 45)
    
    # Fase 4: SWING HIGH (BOS - rompe high anterior de 70) - candles 20-24
    {'open': 30, 'high': 31, 'low': 29, 'close': 31, 'volume': 1000},       # 20
    {'open': 31, 'high': 32, 'low': 30, 'close': 32, 'volume': 1000},       # 21
    {'open': 32, 'high': 33, 'low': 31, 'close': 33, 'volume': 1000},       # 22
    {'open': 33, 'high': 34, 'low': 32, 'close': 34, 'volume': 1000},       # 23
    {'open': 34, 'high': 80, 'low': 33, 'close': 80, 'volume': 1000},       # 24 - Swing High (high=80, rompe 70)
]

for i, candle in enumerate(candles_bullish):
    events = engine.add_candle(candle)
    if events['new_obs']:
        print(f"\n[Candle {i}] OB DETECTADO:")
        for ob in events['new_obs']:
            print(f"  OB {ob.ob_id}: {ob.direction.name}, Top: {ob.top}, Bottom: {ob.bottom}")
    if events['new_signals']:
        print(f"[Candle {i}] SINAL GERADO:")
        for sig in events['new_signals']:
            print(f"  {sig['order_id']}: Entry {sig['entry_price']}, SL {sig['stop_loss']}, TP {sig['take_profit']}")

print("\n" + "-"*80)
print("RESUMO BULLISH:")
print("-"*80)
print(f"Swings High: {len(engine.swing_highs)}")
for conf_idx, cand_idx, level in engine.swing_highs:
    print(f"  Confirmado {conf_idx}, Candidato {cand_idx}, Nível {level}")
print(f"Swings Low: {len(engine.swing_lows)}")
for conf_idx, cand_idx, level in engine.swing_lows:
    print(f"  Confirmado {conf_idx}, Candidato {cand_idx}, Nível {level}")
print(f"Order Blocks: {len(engine.active_obs)}")
for ob in engine.active_obs:
    status = "MITIGADO" if ob.mitigated else "ATIVO"
    print(f"  OB {ob.ob_id}: {ob.direction.name}, Top {ob.top}, Bottom {ob.bottom}, {status}")

# ============================================================================
# PADRÃO BEARISH: SL inicial (baixa) → SH (alta) → SL (baixa) → SH+ (quebra) → SL (CHoCH)
# ============================================================================
print("\n\n" + "="*80)
print("PADRÃO BEARISH - SL (BAIXA) → SH → SL → SH+ (quebra) → SL (CHoCH)")
print("="*80)

# Resetar engine
engine = SMCEngineV3(
    symbol='TEST',
    swing_length=5,
    risk_reward_ratio=3.0,
    min_volume_ratio=0.0,
    min_ob_size_atr=0.0,
    use_not_mitigated_filter=True,
    max_pending_candles=150,
    entry_delay_candles=1,
)

candles_bearish = [
    # Fase 0: SWING LOW INICIAL (perna de BAIXA) - candles 0-4
    {'open': 100, 'high': 101, 'low': 99, 'close': 101, 'volume': 1000},    # 0
    {'open': 101, 'high': 102, 'low': 100, 'close': 102, 'volume': 1000},   # 1
    {'open': 102, 'high': 103, 'low': 101, 'close': 103, 'volume': 1000},   # 2
    {'open': 103, 'high': 104, 'low': 102, 'close': 104, 'volume': 1000},   # 3
    {'open': 104, 'high': 95, 'low': 85, 'close': 85, 'volume': 1000},      # 4 - Swing Low inicial (low=85)
    
    # Fase 1: SWING HIGH (perna de ALTA) - candles 5-9
    {'open': 85, 'high': 86, 'low': 84, 'close': 86, 'volume': 1000},       # 5
    {'open': 86, 'high': 87, 'low': 85, 'close': 87, 'volume': 1000},       # 6
    {'open': 87, 'high': 88, 'low': 86, 'close': 88, 'volume': 1000},       # 7
    {'open': 88, 'high': 89, 'low': 87, 'close': 89, 'volume': 1000},       # 8
    {'open': 89, 'high': 115, 'low': 88, 'close': 115, 'volume': 1000},     # 9 - Swing High (high=115)
    
    # Fase 2: SWING LOW (perna de BAIXA) - candles 10-14
    {'open': 115, 'high': 114, 'low': 113, 'close': 113, 'volume': 1000},   # 10
    {'open': 113, 'high': 112, 'low': 111, 'close': 111, 'volume': 1000},   # 11
    {'open': 111, 'high': 110, 'low': 109, 'close': 109, 'volume': 1000},   # 12
    {'open': 109, 'high': 108, 'low': 107, 'close': 107, 'volume': 1000},   # 13
    {'open': 107, 'high': 106, 'low': 95, 'close': 95, 'volume': 1000},     # 14 - Swing Low (low=95)
    
    # Fase 3: SWING HIGH MAIS ALTA (quebra topo de 115) - candles 15-19
    {'open': 95, 'high': 96, 'low': 94, 'close': 96, 'volume': 1000},       # 15
    {'open': 96, 'high': 97, 'low': 95, 'close': 97, 'volume': 1000},       # 16
    {'open': 97, 'high': 98, 'low': 96, 'close': 98, 'volume': 1000},       # 17
    {'open': 98, 'high': 99, 'low': 97, 'close': 99, 'volume': 1000},       # 18
    {'open': 99, 'high': 130, 'low': 98, 'close': 130, 'volume': 1000},     # 19 - Swing High+ (high=130, quebra 115)
    
    # Fase 4: SWING LOW (CHoCH - rompe low anterior de 85) - candles 20-24
    {'open': 130, 'high': 129, 'low': 128, 'close': 128, 'volume': 1000},   # 20
    {'open': 128, 'high': 127, 'low': 126, 'close': 126, 'volume': 1000},   # 21
    {'open': 126, 'high': 125, 'low': 124, 'close': 124, 'volume': 1000},   # 22
    {'open': 124, 'high': 123, 'low': 122, 'close': 122, 'volume': 1000},   # 23
    {'open': 122, 'high': 121, 'low': 50, 'close': 50, 'volume': 1000},     # 24 - Swing Low (low=50, rompe 85)
]

for i, candle in enumerate(candles_bearish):
    events = engine.add_candle(candle)
    if events['new_obs']:
        print(f"\n[Candle {i}] OB DETECTADO:")
        for ob in events['new_obs']:
            print(f"  OB {ob.ob_id}: {ob.direction.name}, Top: {ob.top}, Bottom: {ob.bottom}")
    if events['new_signals']:
        print(f"[Candle {i}] SINAL GERADO:")
        for sig in events['new_signals']:
            print(f"  {sig['order_id']}: Entry {sig['entry_price']}, SL {sig['stop_loss']}, TP {sig['take_profit']}")

print("\n" + "-"*80)
print("RESUMO BEARISH:")
print("-"*80)
print(f"Swings High: {len(engine.swing_highs)}")
for conf_idx, cand_idx, level in engine.swing_highs:
    print(f"  Confirmado {conf_idx}, Candidato {cand_idx}, Nível {level}")
print(f"Swings Low: {len(engine.swing_lows)}")
for conf_idx, cand_idx, level in engine.swing_lows:
    print(f"  Confirmado {conf_idx}, Candidato {cand_idx}, Nível {level}")
print(f"Order Blocks: {len(engine.active_obs)}")
for ob in engine.active_obs:
    status = "MITIGADO" if ob.mitigated else "ATIVO"
    print(f"  OB {ob.ob_id}: {ob.direction.name}, Top {ob.top}, Bottom {ob.bottom}, {status}")

print("\n" + "="*80)
print("TESTES CONCLUÍDOS")
print("="*80)
