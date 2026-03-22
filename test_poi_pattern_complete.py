"""
Teste Completo de Identificação de Padrões SMC POI
====================================================

PADRÃO BULLISH (com perna de baixa inicial):
1. Swing Low inicial (perna de baixa) - candles 0-4
2. Swing High (perna de alta) - candles 5-9
3. Swing Low (perna de baixa) - candles 10-14
4. Swing Low mais baixa (quebra fundo) - candles 15-19
5. Swing High (BOS - rompe alta anterior) - candles 20-24

PADRÃO BEARISH (com perna de alta inicial):
1. Swing High inicial (perna de alta) - candles 30-34
2. Swing Low (perna de baixa) - candles 35-39
3. Swing High (perna de alta) - candles 40-44
4. Swing High mais alta (quebra topo) - candles 45-49
5. Swing Low (CHoCH - rompe baixa anterior) - candles 50-54
"""

import sys
sys.path.insert(0, '.')
from smc_engine_v3 import SMCEngineV3, SignalDirection

# Configurar engine
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

# ============================================================================
# PADRÃO BULLISH: SL inicial → SH → SL → SL+ (quebra) → SH (BOS)
# ============================================================================
print("="*80)
print("PADRÃO BULLISH - Swing Low inicial → Alta → Baixa → Baixa+ → Alta (BOS)")
print("="*80)

candles_bullish = [
    # Fase 0: SWING LOW INICIAL (perna de baixa) - candles 0-4
    {'open': 100, 'high': 101, 'low': 99, 'close': 101, 'volume': 1000},    # 0
    {'open': 101, 'high': 102, 'low': 100, 'close': 102, 'volume': 1000},   # 1
    {'open': 102, 'high': 103, 'low': 101, 'close': 103, 'volume': 1000},   # 2
    {'open': 103, 'high': 104, 'low': 102, 'close': 104, 'volume': 1000},   # 3
    {'open': 104, 'high': 95, 'low': 85, 'close': 85, 'volume': 1000},      # 4 - Swing Low inicial (low=85)
    
    # Fase 1: SWING HIGH (perna de alta) - candles 5-9
    {'open': 85, 'high': 86, 'low': 84, 'close': 86, 'volume': 1000},       # 5
    {'open': 86, 'high': 87, 'low': 85, 'close': 87, 'volume': 1000},       # 6
    {'open': 87, 'high': 88, 'low': 86, 'close': 88, 'volume': 1000},       # 7
    {'open': 88, 'high': 89, 'low': 87, 'close': 89, 'volume': 1000},       # 8
    {'open': 89, 'high': 105, 'low': 88, 'close': 105, 'volume': 1000},     # 9 - Swing High (high=105)
    
    # Fase 2: SWING LOW (perna de baixa) - candles 10-14
    {'open': 105, 'high': 104, 'low': 103, 'close': 103, 'volume': 1000},   # 10
    {'open': 103, 'high': 102, 'low': 101, 'close': 101, 'volume': 1000},   # 11
    {'open': 101, 'high': 100, 'low': 99, 'close': 99, 'volume': 1000},     # 12
    {'open': 99, 'high': 98, 'low': 97, 'close': 97, 'volume': 1000},       # 13
    {'open': 97, 'high': 96, 'low': 90, 'close': 90, 'volume': 1000},       # 14 - Swing Low (low=90)
    
    # Fase 3: SWING LOW MAIS BAIXA (quebra fundo de 85) - candles 15-19
    {'open': 90, 'high': 89, 'low': 88, 'close': 88, 'volume': 1000},       # 15
    {'open': 88, 'high': 87, 'low': 86, 'close': 86, 'volume': 1000},       # 16
    {'open': 86, 'high': 85, 'low': 84, 'close': 84, 'volume': 1000},       # 17
    {'open': 84, 'high': 83, 'low': 82, 'close': 82, 'volume': 1000},       # 18
    {'open': 82, 'high': 81, 'low': 75, 'close': 75, 'volume': 1000},       # 19 - Swing Low+ (low=75, quebra 85)
    
    # Fase 4: SWING HIGH (BOS - rompe high anterior de 105) - candles 20-24
    {'open': 75, 'high': 76, 'low': 74, 'close': 76, 'volume': 1000},       # 20
    {'open': 76, 'high': 77, 'low': 75, 'close': 77, 'volume': 1000},       # 21
    {'open': 77, 'high': 78, 'low': 76, 'close': 78, 'volume': 1000},       # 22
    {'open': 78, 'high': 79, 'low': 77, 'close': 79, 'volume': 1000},       # 23
    {'open': 79, 'high': 110, 'low': 78, 'close': 110, 'volume': 1000},     # 24 - Swing High (high=110, rompe 105)
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
# PADRÃO BEARISH: SH inicial → SL → SH → SH+ (quebra) → SL (CHoCH)
# ============================================================================
print("\n\n" + "="*80)
print("PADRÃO BEARISH - Swing High inicial → Baixa → Alta → Alta+ → Baixa (CHoCH)")
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
    # Fase 0: SWING HIGH INICIAL (perna de alta) - candles 0-4
    {'open': 50, 'high': 51, 'low': 49, 'close': 51, 'volume': 1000},       # 0
    {'open': 51, 'high': 52, 'low': 50, 'close': 52, 'volume': 1000},       # 1
    {'open': 52, 'high': 53, 'low': 51, 'close': 53, 'volume': 1000},       # 2
    {'open': 53, 'high': 54, 'low': 52, 'close': 54, 'volume': 1000},       # 3
    {'open': 54, 'high': 70, 'low': 53, 'close': 70, 'volume': 1000},       # 4 - Swing High inicial (high=70)
    
    # Fase 1: SWING LOW (perna de baixa) - candles 5-9
    {'open': 70, 'high': 69, 'low': 68, 'close': 68, 'volume': 1000},       # 5
    {'open': 68, 'high': 67, 'low': 66, 'close': 66, 'volume': 1000},       # 6
    {'open': 66, 'high': 65, 'low': 64, 'close': 64, 'volume': 1000},       # 7
    {'open': 64, 'high': 63, 'low': 62, 'close': 62, 'volume': 1000},       # 8
    {'open': 62, 'high': 61, 'low': 45, 'close': 45, 'volume': 1000},       # 9 - Swing Low (low=45)
    
    # Fase 2: SWING HIGH (perna de alta) - candles 10-14
    {'open': 45, 'high': 46, 'low': 44, 'close': 46, 'volume': 1000},       # 10
    {'open': 46, 'high': 47, 'low': 45, 'close': 47, 'volume': 1000},       # 11
    {'open': 47, 'high': 48, 'low': 46, 'close': 48, 'volume': 1000},       # 12
    {'open': 48, 'high': 49, 'low': 47, 'close': 49, 'volume': 1000},       # 13
    {'open': 49, 'high': 65, 'low': 48, 'close': 65, 'volume': 1000},       # 14 - Swing High (high=65)
    
    # Fase 3: SWING HIGH MAIS ALTA (quebra topo de 70) - candles 15-19
    {'open': 65, 'high': 66, 'low': 64, 'close': 66, 'volume': 1000},       # 15
    {'open': 66, 'high': 67, 'low': 65, 'close': 67, 'volume': 1000},       # 16
    {'open': 67, 'high': 68, 'low': 66, 'close': 68, 'volume': 1000},       # 17
    {'open': 68, 'high': 69, 'low': 67, 'close': 69, 'volume': 1000},       # 18
    {'open': 69, 'high': 80, 'low': 68, 'close': 80, 'volume': 1000},       # 19 - Swing High+ (high=80, quebra 70)
    
    # Fase 4: SWING LOW (CHoCH - rompe low anterior de 45) - candles 20-24
    {'open': 80, 'high': 79, 'low': 78, 'close': 78, 'volume': 1000},       # 20
    {'open': 78, 'high': 77, 'low': 76, 'close': 76, 'volume': 1000},       # 21
    {'open': 76, 'high': 75, 'low': 74, 'close': 74, 'volume': 1000},       # 22
    {'open': 74, 'high': 73, 'low': 72, 'close': 72, 'volume': 1000},       # 23
    {'open': 72, 'high': 71, 'low': 30, 'close': 30, 'volume': 1000},       # 24 - Swing Low (low=30, rompe 45)
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
