"""
Investigar por que o engine V3 tem trades EXTRAS que o batch não tem.
"""
import sys
sys.path.insert(0, 'app')
sys.path.insert(0, '/home/ubuntu/smc_enhanced')

import pandas as pd
import numpy as np
from smc_engine_v3 import SMCEngineV3, SignalDirection
from smc_touch_validated import SMCStrategyTouchValidated

df = pd.read_csv('/home/ubuntu/upload/mtwin14400.csv')
df.columns = [c.lower() for c in df.columns]
if 'volume' not in df.columns:
    df['volume'] = df.get('tick_volume', df.get('real_volume', 1.0))
vol_col = 'tick_volume' if 'tick_volume' in df.columns else 'volume'

# BATCH
strategy = SMCStrategyTouchValidated(
    df, swing_length=5, risk_reward_ratio=3.0,
    entry_delay_candles=1, use_not_mitigated_filter=True,
    min_volume_ratio=1.5, min_ob_size_atr=0.5,
)
signals = strategy.generate_signals()
results, stats = strategy.backtest(signals)

# ENGINE V3
engine = SMCEngineV3(
    symbol='WINM24', swing_length=5, risk_reward_ratio=3.0,
    min_volume_ratio=1.5, min_ob_size_atr=0.5,
    use_not_mitigated_filter=True, max_pending_candles=100,
    entry_delay_candles=1,
)
for i in range(len(df)):
    row = df.iloc[i]
    engine.add_candle({
        'open': float(row['open']),
        'high': float(row['high']),
        'low': float(row['low']),
        'close': float(row['close']),
        'volume': float(row[vol_col])
    })

# Batch OB indices
batch_ob_set = set()
for r in results:
    batch_ob_set.add(r.signal.signal_candle_index)

# Engine OB indices
engine_ob_set = set()
for t in engine.closed_trades:
    engine_ob_set.add(t.created_at)

# Extra trades (engine has, batch doesn't)
extra = engine_ob_set - batch_ob_set

print(f"Batch trades: {len(batch_ob_set)}")
print(f"Engine trades: {len(engine_ob_set)}")
print(f"Extra trades no engine: {len(extra)}")

# Investigar os primeiros 10 extras
ob_data = strategy.order_blocks
print("\n" + "=" * 100)
print("TRADES EXTRAS NO ENGINE (engine tem, batch NÃO tem)")
print("=" * 100)

for ob_idx in sorted(extra)[:15]:
    # Encontrar o trade no engine
    for t in engine.closed_trades:
        if t.created_at == ob_idx:
            # Verificar se esse OB existe no batch
            # O batch usa confirmation_index diferente (pode ser +/- swing_length)
            
            # Verificar no batch data
            # O batch armazena OBs com índice do candle de confirmação
            # Verificar se há OB próximo no batch
            batch_ob_nearby = None
            for bi in range(max(0, ob_idx - 10), min(len(ob_data), ob_idx + 10)):
                if ob_data['OB'].iloc[bi] != 0:
                    batch_ob_nearby = bi
                    break
            
            # Verificar mitigação no batch
            mitigated_batch = None
            if batch_ob_nearby is not None:
                mitigated_batch = ob_data['MitigatedIndex'].iloc[batch_ob_nearby]
            
            result_str = "TP" if t.status.value == 'closed_tp' else "SL"
            
            print(f"\n  Engine OB={ob_idx} Fill={t.filled_at} {t.direction.name:8s} "
                  f"{result_str} P/L={t.profit_loss:+.2f}")
            print(f"    Entry={t.entry_price:.2f} SL={t.stop_loss:.2f} TP={t.take_profit:.2f}")
            print(f"    OB mitigated: {t.ob.mitigated} at {t.ob.mitigated_index}")
            
            if batch_ob_nearby is not None:
                print(f"    Batch OB nearby: idx={batch_ob_nearby} "
                      f"mitigated={mitigated_batch if not np.isnan(mitigated_batch) else 'N/A'}")
                if not np.isnan(mitigated_batch):
                    mit_idx = int(mitigated_batch)
                    if mit_idx < t.filled_at:
                        print(f"    >>> BATCH: OB mitigado em {mit_idx} ANTES do fill {t.filled_at}")
                        print(f"    >>> BATCH usa look-ahead para saber que OB será mitigado!")
                    elif mit_idx >= t.filled_at:
                        print(f"    >>> BATCH: OB mitigado em {mit_idx} DEPOIS do fill {t.filled_at}")
            else:
                print(f"    Batch: OB NÃO encontrado próximo")
                # Verificar se o OB não passou nos filtros do batch
                # Verificar volume e tamanho
                print(f"    Volume ratio: {t.ob.volume_ratio:.2f}")
                print(f"    Size ATR: {t.ob.ob_size_atr:.2f}")
            
            break

# Resumo
extra_tp = sum(1 for t in engine.closed_trades if t.created_at in extra and t.status.value == 'closed_tp')
extra_sl = sum(1 for t in engine.closed_trades if t.created_at in extra and t.status.value == 'closed_sl')
print(f"\n\nResumo trades extras:")
print(f"  TP: {extra_tp}")
print(f"  SL: {extra_sl}")
print(f"  Win Rate extras: {extra_tp/(extra_tp+extra_sl)*100:.1f}%")
print(f"  Impacto: {extra_tp * 3 - extra_sl}R")
