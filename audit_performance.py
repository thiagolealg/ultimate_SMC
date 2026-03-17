"""
Auditoria de Performance e Problemas Estruturais
Foco: acúmulo infinito de OBs, memory leaks, complexidade computacional
"""
import sys
import time
import tracemalloc
sys.path.insert(0, '/home/ubuntu/ultimate_SMC')

import pandas as pd
import numpy as np
from smc_engine_v3 import SMCEngineV3, SignalDirection

# Carregar dados
df = pd.read_csv('/home/ubuntu/ultimate_SMC/mtwin14400.csv')
df.columns = [c.lower() for c in df.columns]
vol_col = 'tick_volume' if 'tick_volume' in df.columns else 'volume'

print("=" * 80)
print("AUDITORIA DE PERFORMANCE E PROBLEMAS ESTRUTURAIS")
print("=" * 80)

# ============================================================
# PROBLEMA 1: active_obs NUNCA é limpo
# ============================================================
print("\n>>> PROBLEMA 1: Lista active_obs NUNCA é limpa <<<")
print("-" * 60)

engine = SMCEngineV3(
    symbol='WINM24', swing_length=5, risk_reward_ratio=3.0,
    min_volume_ratio=0.0, min_ob_size_atr=0.0,
    use_not_mitigated_filter=True, max_pending_candles=150,
    entry_delay_candles=1,
)

growth_log = []
for i in range(len(df)):
    row = df.iloc[i]
    engine.add_candle({
        'open': float(row['open']),
        'high': float(row['high']),
        'low': float(row['low']),
        'close': float(row['close']),
        'volume': float(row[vol_col])
    })
    growth_log.append({
        'candle': i,
        'total_obs': len(engine.active_obs),
        'active': sum(1 for ob in engine.active_obs if not ob.mitigated),
        'mitigated': sum(1 for ob in engine.active_obs if ob.mitigated),
        'used': sum(1 for ob in engine.active_obs if ob.used),
    })

print(f"  Candle 0:   active_obs = 0")
for checkpoint in [50, 100, 150, 200, len(df)-1]:
    if checkpoint < len(growth_log):
        g = growth_log[checkpoint]
        print(f"  Candle {checkpoint:3d}: active_obs = {g['total_obs']:3d} "
              f"(ativos: {g['active']}, mitigados: {g['mitigated']}, usados: {g['used']})")

print(f"\n  DIAGNÓSTICO: OBs mitigados permanecem na lista indefinidamente.")
print(f"  No final: {growth_log[-1]['mitigated']} de {growth_log[-1]['total_obs']} OBs são mitigados (mortos)")
print(f"  Isso é {growth_log[-1]['mitigated']/max(1,growth_log[-1]['total_obs'])*100:.0f}% de lixo na lista.")

# ============================================================
# PROBLEMA 2: _check_ob_mitigation itera sobre TODOS os OBs
# ============================================================
print("\n>>> PROBLEMA 2: _check_ob_mitigation - Complexidade O(N) crescente <<<")
print("-" * 60)

# Medir tempo por candle à medida que OBs crescem
engine2 = SMCEngineV3(
    symbol='WINM24', swing_length=5, risk_reward_ratio=3.0,
    min_volume_ratio=0.0, min_ob_size_atr=0.0,
    use_not_mitigated_filter=True, max_pending_candles=150,
    entry_delay_candles=1,
)

times_per_candle = []
for i in range(len(df)):
    row = df.iloc[i]
    t0 = time.perf_counter_ns()
    engine2.add_candle({
        'open': float(row['open']),
        'high': float(row['high']),
        'low': float(row['low']),
        'close': float(row['close']),
        'volume': float(row[vol_col])
    })
    t1 = time.perf_counter_ns()
    times_per_candle.append((t1 - t0) / 1_000)  # microsegundos

# Dividir em quartis
q1 = times_per_candle[:len(times_per_candle)//4]
q4 = times_per_candle[3*len(times_per_candle)//4:]

print(f"  Tempo médio 1o quartil (poucos OBs): {np.mean(q1):.1f} μs/candle")
print(f"  Tempo médio 4o quartil (mais OBs):   {np.mean(q4):.1f} μs/candle")
print(f"  Degradação: {np.mean(q4)/max(1,np.mean(q1)):.1f}x")

# ============================================================
# PROBLEMA 3: swing_highs e swing_lows crescem infinitamente
# ============================================================
print("\n>>> PROBLEMA 3: Listas swing_highs/swing_lows crescem infinitamente <<<")
print("-" * 60)

print(f"  swing_highs: {len(engine.swing_highs)} entradas")
print(f"  swing_lows:  {len(engine.swing_lows)} entradas")
print(f"  _recent_fvg: {len(engine._recent_fvg)} entradas (limitado a 50)")
print(f"  _recent_bos: {len(engine._recent_bos)} entradas (limitado a 50)")
print(f"  _recent_choch: {len(engine._recent_choch)} entradas (limitado a 50)")
print(f"  _recent_sweeps: {len(engine._recent_sweeps)} entradas (limitado a 50)")

print(f"\n  DIAGNÓSTICO: swing_highs e swing_lows NÃO têm limite.")
print(f"  Projeção 113k candles: ~{int(len(engine.swing_highs)/len(df)*113000)} swing_highs")
print(f"  Projeção 113k candles: ~{int(len(engine.swing_lows)/len(df)*113000)} swing_lows")

# ============================================================
# PROBLEMA 4: Listas opens/highs/lows/closes crescem infinitamente
# ============================================================
print("\n>>> PROBLEMA 4: Arrays OHLCV crescem infinitamente <<<")
print("-" * 60)

print(f"  opens:   {len(engine.opens)} floats ({len(engine.opens) * 8 / 1024:.1f} KB)")
print(f"  highs:   {len(engine.highs)} floats ({len(engine.highs) * 8 / 1024:.1f} KB)")
print(f"  lows:    {len(engine.lows)} floats ({len(engine.lows) * 8 / 1024:.1f} KB)")
print(f"  closes:  {len(engine.closes)} floats ({len(engine.closes) * 8 / 1024:.1f} KB)")
print(f"  volumes: {len(engine.volumes)} floats ({len(engine.volumes) * 8 / 1024:.1f} KB)")

total_ohlcv_bytes = len(engine.opens) * 8 * 5
print(f"  Total OHLCV: {total_ohlcv_bytes / 1024:.1f} KB")
print(f"  Projeção 113k candles: {113000 * 8 * 5 / 1024 / 1024:.1f} MB")
print(f"  Projeção 1M candles:   {1000000 * 8 * 5 / 1024 / 1024:.1f} MB")

print(f"\n  DIAGNÓSTICO: V3 armazena TODOS os candles em listas Python.")
print(f"  V2 faz o mesmo (IncrementalCache). Realtime usa deque(maxlen=5000).")

# ============================================================
# PROBLEMA 5: Realtime engine (smc_realtime) - diferenças críticas
# ============================================================
print("\n>>> PROBLEMA 5: Divergências entre engines <<<")
print("-" * 60)

divergences = [
    ("Detecção de OB", 
     "V3: OB = último candle de baixa/alta ANTES do swing (busca para trás)",
     "Realtime: OB = candle de baixa/alta nos 5 candles antes do swing"),
    ("Definição de OB top/bottom",
     "V3: top = max(open, close), bottom = min(open, close) do candle OB",
     "Realtime: top = high, bottom = low do candle OB (inclui sombras)"),
    ("Mitigação",
     "V3: _check_ob_mitigation verifica low<=bottom (bullish) ou high>=top (bearish)",
     "Realtime: marca is_mitigated=True quando ordem é preenchida"),
    ("Expiração de ordens",
     "V3: max_pending_candles=150 (expiração automática)",
     "Realtime: SEM expiração de ordens pendentes"),
    ("Proteção fill",
     "V3: Cancela se candle de fill ultrapassa OB inteiro",
     "Realtime: SEM proteção contra mitigação no fill"),
    ("Limpeza de OBs",
     "V3: NUNCA remove OBs da lista active_obs",
     "Realtime: NUNCA remove OBs da lista order_blocks"),
    ("Armazenamento OHLCV",
     "V3: Listas Python infinitas",
     "Realtime: deque(maxlen=5000) - limitado"),
    ("Geração de sinais",
     "V3: Gera sinal APENAS para novos OBs",
     "Realtime: Gera sinal para TODOS os OBs não mitigados a cada candle"),
    ("Filtro de duplicatas",
     "V3: Sem filtro de OBs duplicados/sobrepostos",
     "Realtime: _ob_exists verifica midline similar (0.1 ATR)"),
]

for i, (area, v3_desc, rt_desc) in enumerate(divergences, 1):
    print(f"\n  {i}. {area}:")
    print(f"     V3:       {v3_desc}")
    print(f"     Realtime: {rt_desc}")

# ============================================================
# PROBLEMA 6: Realtime gera sinais repetidos
# ============================================================
print("\n\n>>> PROBLEMA 6: Realtime gera sinais repetidos <<<")
print("-" * 60)
print(f"  Na engine realtime (smc_realtime/app/smc_engine.py):")
print(f"  _generate_signals() itera sobre TODOS os order_blocks a cada candle.")
print(f"  Usa _has_pending_order_for_ob() para evitar duplicatas,")
print(f"  MAS se a ordem for preenchida, o OB continua gerando sinais")
print(f"  até ser marcado como mitigado.")
print(f"  ")
print(f"  Além disso, _generate_signals verifica 'current_candle[index] <= ob.confirmation_index'")
print(f"  mas NÃO verifica se o OB já gerou um trade que foi fechado.")

# ============================================================
# RESUMO DE PROBLEMAS
# ============================================================
print("\n" + "=" * 80)
print("RESUMO DE PROBLEMAS IDENTIFICADOS")
print("=" * 80)

problems = [
    ("CRÍTICO", "active_obs/order_blocks NUNCA são limpos", 
     "OBs mitigados permanecem na lista indefinidamente, causando crescimento linear de memória e degradação de performance"),
    ("CRÍTICO", "Realtime gera sinais para TODOS os OBs a cada candle",
     "Loop O(N) sobre todos os OBs não mitigados em cada candle, gerando sinais repetidos"),
    ("ALTO", "swing_highs/swing_lows crescem infinitamente (V3)",
     "Listas de swings nunca são podadas, consumindo memória desnecessária"),
    ("ALTO", "Arrays OHLCV crescem infinitamente (V3)",
     "Todos os candles são armazenados em listas Python sem limite"),
    ("ALTO", "Divergência de lógica entre V3 e Realtime",
     "OB top/bottom usa open/close na V3 mas high/low na Realtime; mitigação tem lógica diferente"),
    ("MÉDIO", "Sem filtro de OBs duplicados/sobrepostos (V3)",
     "OBs com regiões muito próximas podem ser criados, gerando trades redundantes"),
    ("MÉDIO", "Sem expiração de ordens na engine Realtime",
     "Ordens pendentes nunca expiram, acumulando-se indefinidamente"),
    ("MÉDIO", "Sem proteção contra mitigação no fill (Realtime)",
     "Trade pode ser aberto em candle que já ultrapassou o OB inteiro"),
    ("BAIXO", "_check_ob_mitigation verifica OBs já mitigados",
     "Loop desnecessário sobre OBs que já foram marcados como mitigados"),
]

for severity, title, desc in problems:
    print(f"\n  [{severity}] {title}")
    print(f"    {desc}")

print("\n=== FIM DA AUDITORIA DE PERFORMANCE ===")
