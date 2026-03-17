"""
Investigar por que o engine V3 não gera trades para OBs que o batch tem.
Todos os OBs faltando têm mitigação DEPOIS do fill.
Então o engine deveria gerar a ordem e preencher ANTES da mitigação.
"""

import sys
sys.path.insert(0, 'app')
sys.path.insert(0, '/home/ubuntu/smc_enhanced')

import pandas as pd
import numpy as np
from smc_engine_v3 import SMCEngineV3, SignalDirection, OrderStatus
from smc_touch_validated import SMCStrategyTouchValidated

df = pd.read_csv('/home/ubuntu/upload/mtwin14400.csv')
df.columns = [c.lower() for c in df.columns]
if 'volume' not in df.columns:
    df['volume'] = df.get('tick_volume', df.get('real_volume', 1.0))
vol_col = 'tick_volume' if 'tick_volume' in df.columns else 'volume'

# Batch
strategy = SMCStrategyTouchValidated(
    df, swing_length=5, risk_reward_ratio=3.0,
    entry_delay_candles=1, use_not_mitigated_filter=True,
    min_volume_ratio=1.5, min_ob_size_atr=0.5,
)
signals = strategy.generate_signals()
results, stats = strategy.backtest(signals)

# Batch trade OB indices
batch_ob_indices = set()
for r in results:
    batch_ob_indices.add(r.signal.signal_candle_index)

# Engine V3 - rastrear TUDO
engine = SMCEngineV3(
    symbol='WINM24', swing_length=5, risk_reward_ratio=3.0,
    min_volume_ratio=1.5, min_ob_size_atr=0.5,
    use_not_mitigated_filter=True, max_pending_candles=100,
    entry_delay_candles=1,
)

# Rastrear eventos para OBs faltando
# OBs faltando (primeiros 5): 2184, 3311, 4000, 5098, 7422
missing_obs = [2184, 3311, 4000, 5098, 7422, 8949, 9995]

# Rastrear todas as ordens criadas, canceladas, expiradas
all_created = []
all_cancelled = []
all_expired = []

for i in range(min(len(df), 35000)):
    row = df.iloc[i]
    events = engine.add_candle({
        'open': float(row['open']),
        'high': float(row['high']),
        'low': float(row['low']),
        'close': float(row['close']),
        'volume': float(row[vol_col])
    })
    
    for sig in events['new_signals']:
        all_created.append((i, sig))
    for exp in events['expired_orders']:
        all_expired.append((i, exp))
    for can in events['cancelled_orders']:
        all_cancelled.append((i, can))

# Verificar se os OBs faltando geraram ordens
print("=" * 100)
print("RASTREAMENTO DE OBs FALTANDO")
print("=" * 100)

for ob_idx in missing_obs:
    print(f"\n--- OB confirmado no candle {ob_idx} ---")
    
    # Verificar se OB foi detectado
    ob_found = None
    for ob in engine.active_obs:
        if ob.confirmation_index == ob_idx:
            ob_found = ob
            break
    
    if ob_found:
        print(f"  OB detectado: {ob_found.direction.name}")
        print(f"  Top: {ob_found.top:.2f}, Bottom: {ob_found.bottom:.2f}, Mid: {ob_found.midline:.2f}")
        print(f"  Volume ratio: {ob_found.volume_ratio:.2f}")
        print(f"  Size ATR: {ob_found.ob_size_atr:.2f}")
        print(f"  Mitigated: {ob_found.mitigated} at {ob_found.mitigated_index}")
        print(f"  Used: {ob_found.used}")
        
        # Verificar filtros
        passed_vol = ob_found.volume_ratio >= 1.5
        passed_size = ob_found.ob_size_atr >= 0.5
        print(f"  Filtro volume (>=1.5): {passed_vol} ({ob_found.volume_ratio:.2f})")
        print(f"  Filtro tamanho (>=0.5): {passed_size} ({ob_found.ob_size_atr:.2f})")
    else:
        print(f"  OB NÃO ENCONTRADO!")
        # Verificar se há OBs próximos
        nearby = [ob for ob in engine.active_obs if abs(ob.confirmation_index - ob_idx) <= 5]
        for ob in nearby:
            print(f"    OB próximo: confirm={ob.confirmation_index} dir={ob.direction.name}")
    
    # Verificar se gerou ordem
    order_created = None
    for candle_idx, sig in all_created:
        if candle_idx == ob_idx:
            order_created = sig
            break
    
    if order_created:
        print(f"  Ordem criada: {order_created['order_id']}")
        
        # Verificar se foi cancelada
        for candle_idx, can in all_cancelled:
            if can['order_id'] == order_created['order_id']:
                print(f"  Ordem CANCELADA no candle {candle_idx}: {can['reason']}")
                break
        
        # Verificar se expirou
        for candle_idx, exp in all_expired:
            if exp['order_id'] == order_created['order_id']:
                print(f"  Ordem EXPIROU no candle {candle_idx}")
                break
        
        # Verificar se foi preenchida
        for t in engine.closed_trades:
            if t.created_at == ob_idx:
                print(f"  Trade FECHADO: fill={t.filled_at} close={t.closed_at} {t.status.value} P/L={t.profit_loss:+.2f}")
                break
    else:
        print(f"  Ordem NÃO CRIADA!")
        # Por que não criou?
        if ob_found:
            if not passed_vol:
                print(f"    CAUSA: Volume ratio ({ob_found.volume_ratio:.2f}) < 1.5")
            if not passed_size:
                print(f"    CAUSA: Size ATR ({ob_found.ob_size_atr:.2f}) < 0.5")

# Resumo
print("\n" + "=" * 100)
print("RESUMO")
print("=" * 100)
print(f"Total ordens criadas: {len(all_created)}")
print(f"Total ordens canceladas: {len(all_cancelled)}")
print(f"Total ordens expiradas: {len(all_expired)}")
print(f"Total trades fechados: {len(engine.closed_trades)}")

# Verificar se o batch tem o OB 4000 como BEARISH
for r in results:
    if r.signal.signal_candle_index == 4000:
        print(f"\nBatch OB 4000: {r.signal.direction.name} fill={r.signal.index} P/L={r.profit_loss:+.2f}")
        break

# Comparar OBs do batch vs engine para os primeiros 10000 candles
batch_obs_set = set()
for r in results:
    if r.signal.signal_candle_index < 10000:
        batch_obs_set.add(r.signal.signal_candle_index)

engine_obs_set = set()
for t in engine.closed_trades:
    if t.created_at < 10000:
        engine_obs_set.add(t.created_at)

print(f"\nBatch trades (OB < 10000): {len(batch_obs_set)}")
print(f"Engine trades (OB < 10000): {len(engine_obs_set)}")
print(f"Batch only: {sorted(batch_obs_set - engine_obs_set)}")
print(f"Engine only: {sorted(engine_obs_set - batch_obs_set)}")
