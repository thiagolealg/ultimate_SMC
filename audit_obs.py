"""
Auditoria de Order Blocks - Análise de acúmulo e performance
"""
import sys
import time
import tracemalloc
sys.path.insert(0, '/home/ubuntu/ultimate_SMC')

import pandas as pd
from smc_engine_v3 import SMCEngineV3
from smc_engine_v2 import SMCEngineV2

# Carregar dados
df = pd.read_csv('/home/ubuntu/ultimate_SMC/mtwin14400.csv')
df.columns = [c.lower() for c in df.columns]
vol_col = 'tick_volume' if 'tick_volume' in df.columns else 'volume'

print(f"=== AUDITORIA DE ORDER BLOCKS ===")
print(f"Dados: {len(df)} candles M1")
print(f"Período: {df['time'].iloc[0]} a {df['time'].iloc[-1]}")
print()

# ============================================================
# TESTE 1: Engine V3 - Análise de acúmulo de OBs
# ============================================================
print("=" * 80)
print("TESTE 1: SMCEngineV3 - Acúmulo de Order Blocks")
print("=" * 80)

# Configuração padrão (sem filtros - mais OBs)
engine_v3_nofilter = SMCEngineV3(
    symbol='WINM24', swing_length=5, risk_reward_ratio=3.0,
    min_volume_ratio=0.0, min_ob_size_atr=0.0,
    use_not_mitigated_filter=True, max_pending_candles=150,
    entry_delay_candles=1,
)

# Configuração com filtros
engine_v3_filtered = SMCEngineV3(
    symbol='WINM24', swing_length=5, risk_reward_ratio=3.0,
    min_volume_ratio=1.5, min_ob_size_atr=0.5,
    use_not_mitigated_filter=True, max_pending_candles=150,
    entry_delay_candles=1,
)

# Rastrear crescimento de OBs ao longo do tempo
ob_count_nofilter = []
ob_count_filtered = []
active_obs_nofilter = []
active_obs_filtered = []
mitigated_nofilter = []
mitigated_filtered = []
pending_nofilter = []
pending_filtered = []
new_obs_per_candle_nf = []
new_obs_per_candle_f = []

tracemalloc.start()
start_time = time.time()

for i in range(len(df)):
    row = df.iloc[i]
    candle = {
        'open': float(row['open']),
        'high': float(row['high']),
        'low': float(row['low']),
        'close': float(row['close']),
        'volume': float(row[vol_col])
    }
    
    events_nf = engine_v3_nofilter.add_candle(candle)
    events_f = engine_v3_filtered.add_candle(candle)
    
    # Rastrear métricas
    total_obs_nf = len(engine_v3_nofilter.active_obs)
    total_obs_f = len(engine_v3_filtered.active_obs)
    
    active_nf = sum(1 for ob in engine_v3_nofilter.active_obs if not ob.mitigated)
    active_f = sum(1 for ob in engine_v3_filtered.active_obs if not ob.mitigated)
    
    mitigated_nf = sum(1 for ob in engine_v3_nofilter.active_obs if ob.mitigated)
    mitigated_f = sum(1 for ob in engine_v3_filtered.active_obs if ob.mitigated)
    
    ob_count_nofilter.append(total_obs_nf)
    ob_count_filtered.append(total_obs_f)
    active_obs_nofilter.append(active_nf)
    active_obs_filtered.append(active_f)
    mitigated_nofilter.append(mitigated_nf)
    mitigated_filtered.append(mitigated_f)
    pending_nofilter.append(len(engine_v3_nofilter.pending_orders))
    pending_filtered.append(len(engine_v3_filtered.pending_orders))
    new_obs_per_candle_nf.append(len(events_nf['new_obs']))
    new_obs_per_candle_f.append(len(events_f['new_obs']))

elapsed = time.time() - start_time
current, peak = tracemalloc.get_traced_memory()
tracemalloc.stop()

print(f"\n--- Sem Filtros (min_volume_ratio=0, min_ob_size_atr=0) ---")
print(f"  Total OBs detectados: {engine_v3_nofilter._ob_counter}")
print(f"  OBs na lista active_obs: {len(engine_v3_nofilter.active_obs)}")
print(f"  OBs NÃO mitigados: {active_obs_nofilter[-1]}")
print(f"  OBs mitigados (ainda na lista): {mitigated_nofilter[-1]}")
print(f"  Ordens pendentes finais: {len(engine_v3_nofilter.pending_orders)}")
print(f"  Trades fechados: {len(engine_v3_nofilter.closed_trades)}")
print(f"  Máx OBs acumulados: {max(ob_count_nofilter)}")
print(f"  Máx OBs ativos: {max(active_obs_nofilter)}")
print(f"  Máx pending: {max(pending_nofilter)}")

stats_nf = engine_v3_nofilter.get_stats()
print(f"  Win Rate: {stats_nf['win_rate']:.1f}%")
print(f"  Profit Factor: {stats_nf['profit_factor']:.2f}")
print(f"  Total Trades: {stats_nf['total_trades']}")

print(f"\n--- Com Filtros (min_volume_ratio=1.5, min_ob_size_atr=0.5) ---")
print(f"  Total OBs detectados: {engine_v3_filtered._ob_counter}")
print(f"  OBs na lista active_obs: {len(engine_v3_filtered.active_obs)}")
print(f"  OBs NÃO mitigados: {active_obs_filtered[-1]}")
print(f"  OBs mitigados (ainda na lista): {mitigated_filtered[-1]}")
print(f"  Ordens pendentes finais: {len(engine_v3_filtered.pending_orders)}")
print(f"  Trades fechados: {len(engine_v3_filtered.closed_trades)}")
print(f"  Máx OBs acumulados: {max(ob_count_filtered)}")
print(f"  Máx OBs ativos: {max(active_obs_filtered)}")
print(f"  Máx pending: {max(pending_filtered)}")

stats_f = engine_v3_filtered.get_stats()
print(f"  Win Rate: {stats_f['win_rate']:.1f}%")
print(f"  Profit Factor: {stats_f['profit_factor']:.2f}")
print(f"  Total Trades: {stats_f['total_trades']}")

print(f"\n--- Performance ---")
print(f"  Tempo total: {elapsed:.3f}s")
print(f"  Tempo por candle: {elapsed/len(df)*1000:.3f}ms")
print(f"  Memória pico: {peak / 1024 / 1024:.2f} MB")

# ============================================================
# TESTE 2: Engine V2 - Análise comparativa
# ============================================================
print("\n" + "=" * 80)
print("TESTE 2: SMCEngineV2 - Análise comparativa")
print("=" * 80)

engine_v2 = SMCEngineV2(
    symbol='WINM24', swing_length=5, risk_reward_ratio=3.0,
    min_volume_ratio=1.5, min_ob_size_atr=0.5,
    use_not_mitigated_filter=True, max_pending_candles=100,
    entry_delay_candles=1,
)

v2_ob_counts = []
v2_active_counts = []

for i in range(len(df)):
    row = df.iloc[i]
    engine_v2.add_candle({
        'open': float(row['open']),
        'high': float(row['high']),
        'low': float(row['low']),
        'close': float(row['close']),
        'volume': float(row[vol_col])
    })
    v2_ob_counts.append(len(engine_v2.active_obs))
    v2_active_counts.append(sum(1 for ob in engine_v2.active_obs if not ob.is_mitigated))

stats_v2 = engine_v2.get_stats()
print(f"  Total OBs na lista: {len(engine_v2.active_obs)}")
print(f"  OBs NÃO mitigados: {v2_active_counts[-1]}")
print(f"  Máx OBs acumulados: {max(v2_ob_counts)}")
print(f"  Máx OBs ativos: {max(v2_active_counts)}")
print(f"  Trades: {stats_v2['closed_orders']}")
print(f"  Win Rate: {stats_v2['win_rate']:.1f}%")

# ============================================================
# TESTE 3: Análise de OBs duplicados/sobrepostos
# ============================================================
print("\n" + "=" * 80)
print("TESTE 3: Análise de OBs duplicados/sobrepostos")
print("=" * 80)

obs_v3 = engine_v3_nofilter.active_obs
overlapping_count = 0
duplicate_count = 0

for i in range(len(obs_v3)):
    for j in range(i+1, len(obs_v3)):
        ob_a = obs_v3[i]
        ob_b = obs_v3[j]
        
        if ob_a.direction != ob_b.direction:
            continue
        
        # Verificar sobreposição
        overlap = min(ob_a.top, ob_b.top) - max(ob_a.bottom, ob_b.bottom)
        if overlap > 0:
            size_a = ob_a.top - ob_a.bottom
            size_b = ob_b.top - ob_b.bottom
            overlap_pct = overlap / min(size_a, size_b) if min(size_a, size_b) > 0 else 0
            
            if overlap_pct > 0.8:
                duplicate_count += 1
            elif overlap_pct > 0.3:
                overlapping_count += 1

print(f"  Total OBs analisados: {len(obs_v3)}")
print(f"  OBs quase duplicados (>80% overlap): {duplicate_count}")
print(f"  OBs sobrepostos (>30% overlap): {overlapping_count}")

# ============================================================
# TESTE 4: Análise de OBs por direção e status
# ============================================================
print("\n" + "=" * 80)
print("TESTE 4: Distribuição de OBs")
print("=" * 80)

from smc_engine_v3 import SignalDirection

bullish_total = sum(1 for ob in obs_v3 if ob.direction == SignalDirection.BULLISH)
bearish_total = sum(1 for ob in obs_v3 if ob.direction == SignalDirection.BEARISH)
bullish_active = sum(1 for ob in obs_v3 if ob.direction == SignalDirection.BULLISH and not ob.mitigated)
bearish_active = sum(1 for ob in obs_v3 if ob.direction == SignalDirection.BEARISH and not ob.mitigated)
bullish_mitigated = sum(1 for ob in obs_v3 if ob.direction == SignalDirection.BULLISH and ob.mitigated)
bearish_mitigated = sum(1 for ob in obs_v3 if ob.direction == SignalDirection.BEARISH and ob.mitigated)
used_count = sum(1 for ob in obs_v3 if ob.used)
unused_count = sum(1 for ob in obs_v3 if not ob.used)

print(f"  Bullish OBs: {bullish_total} (ativos: {bullish_active}, mitigados: {bullish_mitigated})")
print(f"  Bearish OBs: {bearish_total} (ativos: {bearish_active}, mitigados: {bearish_mitigated})")
print(f"  OBs que geraram ordens: {used_count}")
print(f"  OBs sem ordens: {unused_count}")

# ============================================================
# TESTE 5: Análise de _check_ob_mitigation - complexidade O(n)
# ============================================================
print("\n" + "=" * 80)
print("TESTE 5: Análise de complexidade da mitigação")
print("=" * 80)

# Simular cenário com muitos candles
print(f"  Tamanho da lista active_obs no final: {len(engine_v3_nofilter.active_obs)}")
print(f"  Cada candle itera sobre TODOS os {len(engine_v3_nofilter.active_obs)} OBs para verificar mitigação")
print(f"  Complexidade por candle: O({len(engine_v3_nofilter.active_obs)})")
print(f"  Complexidade total: O({len(df)} × {len(engine_v3_nofilter.active_obs)}) = O({len(df) * len(engine_v3_nofilter.active_obs)})")

# ============================================================
# TESTE 6: Simulação com dados maiores (projeção)
# ============================================================
print("\n" + "=" * 80)
print("TESTE 6: Projeção para datasets maiores")
print("=" * 80)

candles_per_day = 480  # ~8h de pregão em M1
candles_per_month = candles_per_day * 22
candles_per_year = candles_per_day * 252

# Projetar crescimento linear de OBs
obs_per_candle = engine_v3_nofilter._ob_counter / len(df)
print(f"  Taxa de criação de OBs: {obs_per_candle:.4f} OBs/candle")
print(f"  Projeção 1 dia ({candles_per_day} candles): ~{int(obs_per_candle * candles_per_day)} OBs acumulados")
print(f"  Projeção 1 mês ({candles_per_month} candles): ~{int(obs_per_candle * candles_per_month)} OBs acumulados")
print(f"  Projeção 1 ano ({candles_per_year} candles): ~{int(obs_per_candle * candles_per_year)} OBs acumulados")
print(f"  Projeção 113k candles (validação original): ~{int(obs_per_candle * 113000)} OBs acumulados")

# Memória estimada por OB
import sys as _sys
ob_sample = engine_v3_nofilter.active_obs[0] if engine_v3_nofilter.active_obs else None
if ob_sample:
    ob_size = _sys.getsizeof(ob_sample)
    print(f"\n  Tamanho estimado por OB: ~{ob_size} bytes")
    print(f"  Memória para 1k OBs: ~{ob_size * 1000 / 1024:.1f} KB")
    print(f"  Memória para 10k OBs: ~{ob_size * 10000 / 1024 / 1024:.2f} MB")
    print(f"  Memória para 100k OBs: ~{ob_size * 100000 / 1024 / 1024:.2f} MB")

print("\n=== FIM DA AUDITORIA ===")
