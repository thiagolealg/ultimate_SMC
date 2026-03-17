"""
Debug Engine - Verificação minuciosa dos Order Blocks e Trades
===============================================================
Mostra CADA etapa da detecção: swing -> OB -> ordem -> fill -> close
Para validar se a lógica SMC está correta.
"""
import sys
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from smc_engine_v3 import SMCEngineV3, SignalDirection, OrderBlock

# ============================================================
# 1. CONECTAR E PUXAR DADOS
# ============================================================
print("Conectando ao MetaTrader 5...")
if not mt5.initialize():
    print(f"ERRO: {mt5.last_error()}")
    sys.exit(1)

symbols_to_try = ["WIN$N", "WING26", "WINH26", "WINJ26", "WIN$"]
symbol = None
for s in symbols_to_try:
    if mt5.symbol_info(s) is not None:
        symbol = s
        mt5.symbol_select(s, True)
        break

print(f"Simbolo: {symbol}")

# Puxar dados recentes (fev 2026)
inicio = datetime(2026, 2, 16)
fim = datetime(2026, 2, 24)

rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, inicio, fim)
mt5.shutdown()

if rates is None or len(rates) == 0:
    print("ERRO: Nenhum dado encontrado.")
    sys.exit(1)

df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')
df = df.drop_duplicates(subset='time').sort_values('time').reset_index(drop=True)
print(f"Total: {len(df):,} candles M1")
print(f"Periodo: {df['time'].iloc[0]} ate {df['time'].iloc[-1]}")

# ============================================================
# 2. WARM-UP com dados anteriores (precisa de historico para swings)
# ============================================================
print("\nCarregando warm-up (Jan 2026)...")
if not mt5.initialize():
    sys.exit(1)
warmup_inicio = datetime(2026, 1, 1)
warmup_fim = datetime(2026, 2, 16)
warmup_rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, warmup_inicio, warmup_fim)
mt5.shutdown()

warmup_df = pd.DataFrame(warmup_rates)
warmup_df['time'] = pd.to_datetime(warmup_df['time'], unit='s')
warmup_df = warmup_df.drop_duplicates(subset='time').sort_values('time').reset_index(drop=True)
print(f"Warm-up: {len(warmup_df):,} candles")

# Concatenar
full_df = pd.concat([warmup_df, df], ignore_index=True)
full_df = full_df.drop_duplicates(subset='time').sort_values('time').reset_index(drop=True)
warmup_end = len(warmup_df)
print(f"Total com warm-up: {len(full_df):,} candles (warm-up ate idx {warmup_end})")

# ============================================================
# 3. RODAR ENGINE COM INSTRUMENTAÇÃO
# ============================================================
print("\n" + "="*100)
print("RODANDO ENGINE COM DEBUG DETALHADO")
print("="*100)

engine = SMCEngineV3(
    symbol=symbol,
    swing_length=5,
    risk_reward_ratio=2.0,
    min_volume_ratio=0.0,
    min_ob_size_atr=0.3,
    use_not_mitigated_filter=True,
    max_pending_candles=150,
    entry_delay_candles=1,
    tick_size=5.0,
    min_confidence=0.0,
    max_sl_points=50.0,
    min_patterns=0,
    entry_retracement=0.7,
)

# Rastrear TODOS os eventos
all_obs_detected = []
all_signals = []
all_fills = []
all_closes = []
all_expired = []
all_cancelled = []
all_swings_high = []
all_swings_low = []

prev_swing_highs_count = 0
prev_swing_lows_count = 0

for i in range(len(full_df)):
    row = full_df.iloc[i]
    events = engine.add_candle({
        'open': float(row['open']),
        'high': float(row['high']),
        'low': float(row['low']),
        'close': float(row['close']),
        'volume': float(row.get('real_volume', row.get('tick_volume', 0)))
    })

    t = full_df['time'].iloc[i]

    # Rastrear novos swings (só apos warm-up)
    if i >= warmup_end:
        if len(engine.swing_highs) > prev_swing_highs_count:
            for sh in engine.swing_highs[prev_swing_highs_count:]:
                conf_idx, cand_idx, level = sh
                all_swings_high.append({
                    'confirm_idx': conf_idx,
                    'confirm_time': full_df['time'].iloc[conf_idx],
                    'candidate_idx': cand_idx,
                    'candidate_time': full_df['time'].iloc[cand_idx],
                    'level': level,
                })
        if len(engine.swing_lows) > prev_swing_lows_count:
            for sl in engine.swing_lows[prev_swing_lows_count:]:
                conf_idx, cand_idx, level = sl
                all_swings_low.append({
                    'confirm_idx': conf_idx,
                    'confirm_time': full_df['time'].iloc[conf_idx],
                    'candidate_idx': cand_idx,
                    'candidate_time': full_df['time'].iloc[cand_idx],
                    'level': level,
                })

    prev_swing_highs_count = len(engine.swing_highs)
    prev_swing_lows_count = len(engine.swing_lows)

    # Novos OBs
    for ob_dict in events['new_obs']:
        ob = ob_dict  # é um OrderBlock object
        all_obs_detected.append({
            'idx': i,
            'time': t,
            'ob_id': ob.ob_id,
            'direction': ob.direction.name,
            'top': ob.top,
            'bottom': ob.bottom,
            'midline': ob.midline,
            'size': ob.ob_size,
            'size_atr': ob.ob_size_atr,
            'volume_ratio': ob.volume_ratio,
            'ob_candle_idx': ob.ob_candle_index,
            'ob_candle_time': full_df['time'].iloc[ob.ob_candle_index],
            'confirmation_idx': ob.confirmation_index,
            'ob_candle_O': full_df.iloc[ob.ob_candle_index]['open'],
            'ob_candle_H': full_df.iloc[ob.ob_candle_index]['high'],
            'ob_candle_L': full_df.iloc[ob.ob_candle_index]['low'],
            'ob_candle_C': full_df.iloc[ob.ob_candle_index]['close'],
        })

    # Novos sinais (ordens pendentes)
    for sig in events['new_signals']:
        all_signals.append({
            'idx': i,
            'time': t,
            **sig,
        })

    # Fills
    for fill in events['filled_orders']:
        all_fills.append({
            'idx': i,
            'time': t,
            **fill,
        })

    # Closes
    for close in events['closed_trades']:
        all_closes.append({
            'idx': i,
            'time': t,
            **close,
        })

    # Expired
    for exp in events['expired_orders']:
        all_expired.append({
            'idx': i,
            'time': t,
            **exp,
        })

    # Cancelled
    for canc in events['cancelled_orders']:
        all_cancelled.append({
            'idx': i,
            'time': t,
            **canc,
        })

# ============================================================
# 4. ANALISE DETALHADA - ÚLTIMOS SWINGS
# ============================================================
print(f"\n{'='*100}")
print(f"SWING HIGHS RECENTES (periodo de análise)")
print(f"{'='*100}")
for sh in all_swings_high[-20:]:
    print(f"  Confirmado: {sh['confirm_time']} (idx {sh['confirm_idx']}) | "
          f"Candidato: {sh['candidate_time']} (idx {sh['candidate_idx']}) | "
          f"Level: {sh['level']:.2f}")

print(f"\n{'='*100}")
print(f"SWING LOWS RECENTES (periodo de análise)")
print(f"{'='*100}")
for sl in all_swings_low[-20:]:
    print(f"  Confirmado: {sl['confirm_time']} (idx {sl['confirm_idx']}) | "
          f"Candidato: {sl['candidate_time']} (idx {sl['candidate_idx']}) | "
          f"Level: {sl['level']:.2f}")

# ============================================================
# 5. ANALISE DETALHADA - OBs DETECTADOS
# ============================================================
print(f"\n{'='*100}")
print(f"ORDER BLOCKS DETECTADOS (periodo de análise): {len(all_obs_detected)}")
print(f"{'='*100}")
for ob in all_obs_detected:
    bull_bear = "ALTA" if "BULL" in ob['direction'] else "BAIXA"
    ob_candle_dir = "ALTA" if ob['ob_candle_C'] > ob['ob_candle_O'] else "BAIXA" if ob['ob_candle_C'] < ob['ob_candle_O'] else "DOJI"

    # Para Bullish OB, o candle deveria ser de BAIXA
    # Para Bearish OB, o candle deveria ser de ALTA
    expected = "BAIXA" if "BULL" in ob['direction'] else "ALTA"
    correct = "OK" if ob_candle_dir == expected else f"ERRADO (esperava {expected}, é {ob_candle_dir})"

    dist_candles = ob['confirmation_idx'] - ob['ob_candle_idx']

    print(f"\n  OB #{ob['ob_id']}: {ob['direction']} ({bull_bear})")
    print(f"    Confirmação: {ob['time']} (idx {ob['idx']})")
    print(f"    Candle OB:   {ob['ob_candle_time']} (idx {ob['ob_candle_idx']}) | Distância: {dist_candles} candles atrás")
    print(f"    OB Candle:   O={ob['ob_candle_O']:.2f} H={ob['ob_candle_H']:.2f} L={ob['ob_candle_L']:.2f} C={ob['ob_candle_C']:.2f} -> {ob_candle_dir} {correct}")
    print(f"    Zona OB:     Top={ob['top']:.2f} Bot={ob['bottom']:.2f} Mid={ob['midline']:.2f} Size={ob['size']:.2f} ({ob['size_atr']:.2f} ATR)")
    print(f"    Volume ratio: {ob['volume_ratio']:.2f}")

# ============================================================
# 6. ANALISE DETALHADA - SINAIS GERADOS (ordens pendentes)
# ============================================================
print(f"\n{'='*100}")
print(f"SINAIS GERADOS (ordens pendentes): {len(all_signals)}")
print(f"{'='*100}")
for sig in all_signals:
    risk = abs(sig['entry_price'] - sig['stop_loss'])
    print(f"\n  {sig['order_id']}: {sig['direction']}")
    print(f"    Criado: {sig['time']} (idx {sig['idx']})")
    print(f"    Entry: {sig['entry_price']:.2f} | SL: {sig['stop_loss']:.2f} | TP: {sig['take_profit']:.2f}")
    print(f"    Risk: {risk:.2f} pts | OB: [{sig['ob_bottom']:.2f} - {sig['ob_top']:.2f}]")
    print(f"    Confiança: {sig['confidence']:.0f} | Padrões: {sig['patterns']}")

# ============================================================
# 7. ANALISE DETALHADA - FILLS
# ============================================================
print(f"\n{'='*100}")
print(f"ORDENS PREENCHIDAS: {len(all_fills)}")
print(f"{'='*100}")
for fill in all_fills:
    fill_idx = fill['filled_at']
    candle = full_df.iloc[fill_idx]
    print(f"\n  {fill['order_id']}: {fill['direction']} preenchida em {fill['time']} (idx {fill_idx})")
    print(f"    Entry: {fill['entry_price']:.2f}")
    print(f"    Candle fill: O={candle['open']:.2f} H={candle['high']:.2f} L={candle['low']:.2f} C={candle['close']:.2f}")
    if fill['direction'] == 'BULLISH':
        print(f"    Verificação: Low ({candle['low']:.2f}) <= Entry-tick ({fill['entry_price']-5:.2f})? "
              f"{'SIM' if candle['low'] <= fill['entry_price']-5 else 'NÃO - BUG!'}")
    else:
        print(f"    Verificação: High ({candle['high']:.2f}) >= Entry+tick ({fill['entry_price']+5:.2f})? "
              f"{'SIM' if candle['high'] >= fill['entry_price']+5 else 'NÃO - BUG!'}")

# ============================================================
# 8. ANALISE DETALHADA - TRADES FECHADOS
# ============================================================
print(f"\n{'='*100}")
print(f"TRADES FECHADOS: {len(all_closes)}")
print(f"{'='*100}")
for close in all_closes:
    close_idx = close['closed_at']
    candle = full_df.iloc[close_idx]
    result = "WIN" if 'tp' in close['status'] else "LOSS"
    print(f"\n  {close['order_id']}: {close['direction']} -> {result} ({close['profit_loss']:+.2f} pts)")
    print(f"    Fechado: {close['time']} (idx {close_idx})")
    print(f"    Entry: {close['entry_price']:.2f} -> Exit: {close['exit_price']:.2f}")
    print(f"    Candle close: O={candle['open']:.2f} H={candle['high']:.2f} L={candle['low']:.2f} C={candle['close']:.2f}")
    if close['direction'] == 'BULLISH':
        if result == 'LOSS':
            print(f"    Verificação SL: Low ({candle['low']:.2f}) <= SL ({close['exit_price']:.2f})? "
                  f"{'SIM' if candle['low'] <= close['exit_price'] else 'NÃO - BUG!'}")
        else:
            print(f"    Verificação TP: High ({candle['high']:.2f}) >= TP ({close['exit_price']:.2f})? "
                  f"{'SIM' if candle['high'] >= close['exit_price'] else 'NÃO - BUG!'}")
    else:
        if result == 'LOSS':
            print(f"    Verificação SL: High ({candle['high']:.2f}) >= SL ({close['exit_price']:.2f})? "
                  f"{'SIM' if candle['high'] >= close['exit_price'] else 'NÃO - BUG!'}")
        else:
            print(f"    Verificação TP: Low ({candle['low']:.2f}) <= TP ({close['exit_price']:.2f})? "
                  f"{'SIM' if candle['low'] <= close['exit_price'] else 'NÃO - BUG!'}")

# ============================================================
# 9. ORDENS EXPIRADAS E CANCELADAS
# ============================================================
print(f"\n{'='*100}")
print(f"ORDENS EXPIRADAS: {len(all_expired)} | CANCELADAS: {len(all_cancelled)}")
print(f"{'='*100}")
for exp in all_expired:
    print(f"  EXPIRADA: {exp['order_id']} em {exp['time']}")
for canc in all_cancelled:
    print(f"  CANCELADA: {canc['order_id']} em {canc['time']} - Motivo: {canc['reason']}")

# ============================================================
# 10. VERIFICAÇÕES DE INTEGRIDADE
# ============================================================
print(f"\n{'='*100}")
print("VERIFICAÇÕES DE INTEGRIDADE")
print(f"{'='*100}")

# A. OB candle direction correta?
ob_dir_errors = 0
for ob in all_obs_detected:
    if "BULL" in ob['direction']:
        # Bullish OB = candle de baixa (close < open)
        if ob['ob_candle_C'] >= ob['ob_candle_O']:
            ob_dir_errors += 1
            print(f"  ERRO OB #{ob['ob_id']}: Bullish OB mas candle OB é de ALTA (O={ob['ob_candle_O']:.2f} C={ob['ob_candle_C']:.2f})")
    else:
        # Bearish OB = candle de alta (close > open)
        if ob['ob_candle_C'] <= ob['ob_candle_O']:
            ob_dir_errors += 1
            print(f"  ERRO OB #{ob['ob_id']}: Bearish OB mas candle OB é de BAIXA (O={ob['ob_candle_O']:.2f} C={ob['ob_candle_C']:.2f})")
print(f"  OB direction errors: {ob_dir_errors} {'OK' if ob_dir_errors == 0 else 'PROBLEMAS!'}")

# B. OB candle distance - quão longe do swing está?
print(f"\n  Distância do candle OB ao swing (confirmação):")
for ob in all_obs_detected:
    dist = ob['confirmation_idx'] - ob['ob_candle_idx']
    flag = " <-- MUITO LONGE!" if dist > 30 else ""
    print(f"    OB #{ob['ob_id']}: {dist} candles{flag}")

# C. OB size zero?
for ob in all_obs_detected:
    if ob['size'] == 0:
        print(f"  ERRO: OB #{ob['ob_id']} tem tamanho ZERO (doji)")

# D. Verificar se entry está dentro do OB
for sig in all_signals:
    if sig['entry_price'] > sig['ob_top'] or sig['entry_price'] < sig['ob_bottom']:
        print(f"  ERRO: {sig['order_id']} entry {sig['entry_price']:.2f} FORA do OB [{sig['ob_bottom']:.2f}-{sig['ob_top']:.2f}]")

# E. Verificar risk > 0
for sig in all_signals:
    risk = abs(sig['entry_price'] - sig['stop_loss'])
    if risk <= 0:
        print(f"  ERRO: {sig['order_id']} risk <= 0!")
    elif risk > 50:
        print(f"  AVISO: {sig['order_id']} risk = {risk:.2f} > 50 (deveria ser filtrado)")

# ============================================================
# 11. CADEIA COMPLETA DE CADA TRADE
# ============================================================
print(f"\n{'='*100}")
print("CADEIA COMPLETA: SWING -> OB -> SINAL -> FILL -> CLOSE")
print(f"{'='*100}")

trades = engine.get_all_trades()
# Filtrar trades do periodo de análise
for t in trades:
    fill_time = full_df['time'].iloc[t['filled_at']]
    if fill_time < pd.Timestamp(inicio):
        continue

    close_time = full_df['time'].iloc[t['closed_at']]
    create_time = full_df['time'].iloc[t['created_at']]
    result = "WIN" if t['status'] == 'closed_tp' else "LOSS"

    # Encontrar o OB correspondente
    ob_info = None
    for ob in all_obs_detected:
        # Procurar pelo OB que gerou essa ordem
        for sig in all_signals:
            if sig['order_id'] == t['order_id']:
                ob_info = ob if abs(ob['top'] - t['ob_top']) < 1 and abs(ob['bottom'] - t['ob_bottom']) < 1 else ob_info

    print(f"\n  {'='*80}")
    print(f"  TRADE {t['order_id']}: {t['direction']} -> {result} ({t['profit_loss']:+.2f} pts | {t['profit_loss_r']:+.1f}R)")
    print(f"  {'='*80}")
    print(f"    OB Zone:      [{t['ob_bottom']:.2f} - {t['ob_top']:.2f}] (size={t['ob_top']-t['ob_bottom']:.2f})")
    print(f"    Criação:      {create_time} (idx {t['created_at']})")
    print(f"    Entry:        {t['entry_price']:.2f}")
    print(f"    SL:           {t['stop_loss']:.2f}")
    print(f"    TP:           {t['take_profit']:.2f}")
    print(f"    Fill:         {fill_time} (idx {t['filled_at']}) - esperou {t['wait_candles']} candles")
    print(f"    Close:        {close_time} (idx {t['closed_at']}) - durou {t['duration_candles']} candles")
    print(f"    Exit:         {t['exit_price']:.2f}")
    print(f"    Padrões:      {t['patterns']}")
    print(f"    Confiança:    {t['confidence']:.0f}")

    # Mostrar candles ao redor do fill
    fill_idx = t['filled_at']
    print(f"    Candles ao redor do FILL:")
    for j in range(max(0, fill_idx-3), min(len(full_df), fill_idx+4)):
        marker = " <-- FILL" if j == fill_idx else ""
        c = full_df.iloc[j]
        print(f"      [{j}] {full_df['time'].iloc[j]} O={c['open']:.2f} H={c['high']:.2f} L={c['low']:.2f} C={c['close']:.2f}{marker}")

    # Mostrar candles ao redor do close
    close_idx = t['closed_at']
    print(f"    Candles ao redor do CLOSE:")
    for j in range(max(0, close_idx-2), min(len(full_df), close_idx+3)):
        marker = f" <-- {result}" if j == close_idx else ""
        c = full_df.iloc[j]
        print(f"      [{j}] {full_df['time'].iloc[j]} O={c['open']:.2f} H={c['high']:.2f} L={c['low']:.2f} C={c['close']:.2f}{marker}")

# ============================================================
# 12. RESUMO
# ============================================================
stats = engine.get_stats()
print(f"\n{'='*100}")
print("RESUMO")
print(f"{'='*100}")
print(f"  OBs detectados no periodo: {len(all_obs_detected)}")
print(f"  Sinais gerados: {len(all_signals)}")
print(f"  Ordens preenchidas: {len(all_fills)}")
print(f"  Trades fechados: {len(all_closes)}")
print(f"  Expiradas: {len(all_expired)}")
print(f"  Canceladas: {len(all_cancelled)}")
print(f"  Canceladas por mitigação: {sum(1 for c in all_cancelled if c['reason'] == 'ob_mitigated')}")
print(f"  Canceladas por mitigação no fill: {sum(1 for c in all_cancelled if c['reason'] == 'ob_mitigated_on_fill')}")
print(f"  Total OBs engine: {stats['order_blocks_detected']}")
print(f"  Pending agora: {stats['pending_orders']}")
print(f"  Open trades agora: {stats['open_trades']}")
