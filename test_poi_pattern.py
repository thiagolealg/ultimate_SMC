"""
Teste de Identificação de POI (Point of Interest) - Padrão SMC Clássico
=========================================================================

Padrão testado:
1. ALTA (Swing High) - candles 0-4
2. BAIXA (Swing Low) - candles 5-9  
3. ALTA (Swing High) - candles 10-14
4. BAIXA MAIS BAIXA (quebrando fundo anterior) - candles 15-19
5. ALTA APÓS (BOS/CHoCH) - candles 20-24

Esperado:
- Swing High em candle 4 (nível 100)
- Swing Low em candle 9 (nível 80)
- Swing High em candle 14 (nível 95)
- Swing Low em candle 19 (nível 75 - quebra o fundo anterior de 80)
- BOS/CHoCH quando close > 95 (rompe swing high anterior)
- Order Block BEARISH detectado quando close < 80 (rompe swing low)
"""

import sys
sys.path.insert(0, '.')
from smc_engine_v3 import SMCEngineV3, SignalDirection
import json

# Configurar engine com swing_length=5
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

# Criar candles sintéticos simulando o padrão
# Base: 100 (nível de referência)
candles = [
    # Fase 1: ALTA (Swing High em 4)
    {'open': 100, 'high': 101, 'low': 99, 'close': 101, 'volume': 1000},   # 0
    {'open': 101, 'high': 102, 'low': 100, 'close': 102, 'volume': 1000},  # 1
    {'open': 102, 'high': 103, 'low': 101, 'close': 103, 'volume': 1000},  # 2
    {'open': 103, 'high': 104, 'low': 102, 'close': 104, 'volume': 1000},  # 3
    {'open': 104, 'high': 100, 'low': 99, 'close': 100, 'volume': 1000},   # 4 - Swing High confirmado em 4 (high=100)
    
    # Fase 2: BAIXA (Swing Low em 9)
    {'open': 100, 'high': 99, 'low': 98, 'close': 98, 'volume': 1000},     # 5
    {'open': 98, 'high': 97, 'low': 96, 'close': 96, 'volume': 1000},      # 6
    {'open': 96, 'high': 95, 'low': 94, 'close': 94, 'volume': 1000},      # 7
    {'open': 94, 'high': 93, 'low': 92, 'close': 92, 'volume': 1000},      # 8
    {'open': 92, 'high': 91, 'low': 80, 'close': 80, 'volume': 1000},      # 9 - Swing Low confirmado em 9 (low=80)
    
    # Fase 3: ALTA (Swing High em 14)
    {'open': 80, 'high': 81, 'low': 79, 'close': 81, 'volume': 1000},      # 10
    {'open': 81, 'high': 82, 'low': 80, 'close': 82, 'volume': 1000},      # 11
    {'open': 82, 'high': 83, 'low': 81, 'close': 83, 'volume': 1000},      # 12
    {'open': 83, 'high': 84, 'low': 82, 'close': 84, 'volume': 1000},      # 13
    {'open': 84, 'high': 95, 'low': 83, 'close': 95, 'volume': 1000},      # 14 - Swing High confirmado em 14 (high=95)
    
    # Fase 4: BAIXA MAIS BAIXA (quebrando fundo anterior de 80)
    {'open': 95, 'high': 94, 'low': 93, 'close': 93, 'volume': 1000},      # 15
    {'open': 93, 'high': 92, 'low': 91, 'close': 91, 'volume': 1000},      # 16
    {'open': 91, 'high': 90, 'low': 89, 'close': 89, 'volume': 1000},      # 17
    {'open': 89, 'high': 88, 'low': 87, 'close': 87, 'volume': 1000},      # 18
    {'open': 87, 'high': 86, 'low': 75, 'close': 75, 'volume': 1000},      # 19 - Swing Low confirmado em 19 (low=75, quebra 80)
    
    # Fase 5: ALTA APÓS (BOS/CHoCH quando close > 95)
    {'open': 75, 'high': 76, 'low': 74, 'close': 76, 'volume': 1000},      # 20
    {'open': 76, 'high': 77, 'low': 75, 'close': 77, 'volume': 1000},      # 21
    {'open': 77, 'high': 78, 'low': 76, 'close': 78, 'volume': 1000},      # 22
    {'open': 78, 'high': 79, 'low': 77, 'close': 79, 'volume': 1000},      # 23
    {'open': 79, 'high': 96, 'low': 78, 'close': 96, 'volume': 1000},      # 24 - ROMPE swing high anterior (95) -> BOS/CHoCH
]

# Processar candles
events_log = []
for i, candle in enumerate(candles):
    events = engine.add_candle(candle)
    
    event_record = {
        'candle_idx': i,
        'ohlc': candle,
        'new_obs': len(events['new_obs']),
        'new_signals': len(events['new_signals']),
        'swing_highs': len(engine.swing_highs),
        'swing_lows': len(engine.swing_lows),
        'active_obs': len([ob for ob in engine.active_obs if not ob.mitigated]),
        'mitigated_obs': len([ob for ob in engine.active_obs if ob.mitigated]),
        'events': events,
    }
    
    if events['new_obs']:
        print(f"\n[Candle {i}] NOVO ORDER BLOCK DETECTADO:")
        for ob in events['new_obs']:
            print(f"  ID: {ob.ob_id}, Direction: {ob.direction.name}, Top: {ob.top}, Bottom: {ob.bottom}, Midline: {ob.midline}")
    
    if events['new_signals']:
        print(f"\n[Candle {i}] NOVO SINAL GERADO:")
        for sig in events['new_signals']:
            print(f"  Order: {sig['order_id']}, Direction: {sig['direction']}, Entry: {sig['entry_price']}, SL: {sig['stop_loss']}, TP: {sig['take_profit']}")
    
    if events['filled_orders']:
        print(f"\n[Candle {i}] ORDEM PREENCHIDA:")
        for fill in events['filled_orders']:
            print(f"  Order: {fill['order_id']}, Entry: {fill['entry_price']}")
    
    if events['closed_trades']:
        print(f"\n[Candle {i}] TRADE FECHADO:")
        for close in events['closed_trades']:
            print(f"  Order: {close['order_id']}, Exit: {close['exit_price']}, P&L: {close['pnl']} pts ({close['pnl_r']}R)")
    
    events_log.append(event_record)

# Resumo final
print("\n" + "="*80)
print("RESUMO DO TESTE")
print("="*80)

stats = engine.get_stats()
print(f"\nSwing Highs detectados: {len(engine.swing_highs)}")
for conf_idx, cand_idx, level in engine.swing_highs:
    print(f"  Confirmado em {conf_idx}, Candidato em {cand_idx}, Nível: {level}")

print(f"\nSwing Lows detectados: {len(engine.swing_lows)}")
for conf_idx, cand_idx, level in engine.swing_lows:
    print(f"  Confirmado em {conf_idx}, Candidato em {cand_idx}, Nível: {level}")

print(f"\nOrder Blocks detectados: {len(engine.active_obs)}")
for ob in engine.active_obs:
    status = "MITIGADO" if ob.mitigated else "ATIVO"
    print(f"  OB {ob.ob_id}: {ob.direction.name}, Top: {ob.top}, Bottom: {ob.bottom}, Status: {status}")

print(f"\nOrdens pendentes: {len(engine.pending_orders)}")
for order in engine.pending_orders:
    print(f"  {order.order_id}: {order.direction.name}, Entry: {order.entry_price}, SL: {order.stop_loss}, TP: {order.take_profit}")

print(f"\nTrades fechados: {stats['total_trades']}")
for trade in engine.closed_trades:
    print(f"  {trade.order_id}: {trade.direction.name}, Entry: {trade.entry_price}, Exit: {trade.exit_price}, P&L: {trade.profit_loss} pts ({trade.profit_loss_r}R)")

print(f"\nEstatísticas:")
print(f"  Win Rate: {stats['win_rate']:.1f}%")
print(f"  Total P&L: {stats['total_profit_points']:.2f} pts")
print(f"  Profit Factor: {stats['profit_factor']:.2f}")

# Salvar log em JSON
with open('test_poi_pattern_log.json', 'w') as f:
    # Converter eventos para serializáveis
    def make_serializable(obj):
        if hasattr(obj, '__dict__'):
            return obj.__dict__
        elif isinstance(obj, list):
            return [make_serializable(item) for item in obj]
        elif isinstance(obj, dict):
            return {k: make_serializable(v) for k, v in obj.items()}
        else:
            return obj
    
    json.dump(make_serializable(events_log), f, indent=2, default=str)

print("\nLog salvo em: test_poi_pattern_log.json")
