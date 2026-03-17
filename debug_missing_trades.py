"""
Investigar exatamente quais trades o batch tem que o engine V3 não tem,
e por que. Isso vai revelar se o batch usa look-ahead na mitigação.
"""

import sys
sys.path.insert(0, 'app')
sys.path.insert(0, '/home/ubuntu/smc_enhanced')

import pandas as pd
import numpy as np
from smc_engine_v3 import SMCEngineV3, SignalDirection
from smc_touch_validated import SMCStrategyTouchValidated

def load_data():
    df = pd.read_csv('/home/ubuntu/upload/mtwin14400.csv')
    df.columns = [c.lower() for c in df.columns]
    if 'volume' not in df.columns:
        df['volume'] = df.get('tick_volume', df.get('real_volume', 1.0))
    return df

def main():
    df = load_data()
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
    
    # Criar sets de trades por (ob_index, fill_index)
    batch_trades = {}
    for r in results:
        key = (r.signal.signal_candle_index, r.signal.index)
        batch_trades[key] = r
    
    engine_trades = {}
    for t in engine.closed_trades:
        key = (t.created_at, t.filled_at)
        engine_trades[key] = t
    
    # Trades no batch mas não no engine
    missing = []
    for key, r in batch_trades.items():
        if key not in engine_trades:
            missing.append((key, r))
    
    # Trades no engine mas não no batch
    extra = []
    for key, t in engine_trades.items():
        if key not in batch_trades:
            extra.append((key, t))
    
    print(f"Trades no BATCH: {len(batch_trades)}")
    print(f"Trades no ENGINE: {len(engine_trades)}")
    print(f"Trades FALTANDO no engine: {len(missing)}")
    print(f"Trades EXTRAS no engine: {len(extra)}")
    
    # Analisar os trades faltando
    print("\n" + "=" * 100)
    print("TRADES FALTANDO NO ENGINE (batch tem, engine não)")
    print("=" * 100)
    
    ob_data = strategy.order_blocks
    
    tp_missing = 0
    sl_missing = 0
    
    for (ob_idx, fill_idx), r in sorted(missing)[:30]:
        s = r.signal
        
        # Verificar mitigação no batch
        mitigated = ob_data['MitigatedIndex'].iloc[ob_idx]
        mitigated_str = f"{int(mitigated)}" if not np.isnan(mitigated) else "N/A"
        
        # O que aconteceu no engine?
        # O OB foi detectado? Verificar
        ob_found = False
        ob_mitigated_engine = False
        ob_mitigated_at = -1
        for ob in engine.active_obs:
            if ob.confirmation_index == ob_idx:
                ob_found = True
                ob_mitigated_engine = ob.mitigated
                ob_mitigated_at = ob.mitigated_index
                break
        
        result_str = "TP" if r.hit_tp else "SL"
        if r.hit_tp:
            tp_missing += 1
        else:
            sl_missing += 1
        
        # A mitigação no batch acontece DEPOIS do fill?
        mitigated_after_fill = not np.isnan(mitigated) and int(mitigated) > fill_idx
        mitigated_before_fill = not np.isnan(mitigated) and int(mitigated) <= fill_idx
        
        # No engine, a mitigação aconteceu ANTES do fill?
        engine_mit_before = ob_mitigated_engine and ob_mitigated_at <= fill_idx
        engine_mit_after = ob_mitigated_engine and ob_mitigated_at > fill_idx
        
        print(f"\n  OB={ob_idx:>6d} Fill={fill_idx:>6d} {s.direction.name:8s} {result_str} P/L={r.profit_loss:>+8.2f}")
        print(f"    Batch mitigated_index: {mitigated_str}")
        print(f"    Batch mitigated AFTER fill: {mitigated_after_fill}")
        print(f"    Engine OB found: {ob_found}")
        print(f"    Engine OB mitigated: {ob_mitigated_engine} at {ob_mitigated_at}")
        print(f"    Engine mitigated BEFORE fill: {engine_mit_before}")
        
        # EXPLICAÇÃO
        if engine_mit_before and mitigated_after_fill:
            print(f"    >>> CAUSA: Engine detecta mitigação em tempo real ANTES do fill,")
            print(f"    >>> mas o batch sabe (look-ahead) que mitigação é no {mitigated_str} (DEPOIS do fill {fill_idx})")
            print(f"    >>> O batch PERMITE o trade porque sabe que a mitigação é futura")
    
    print(f"\n\nResumo trades faltando:")
    print(f"  TP (vencedores): {tp_missing}")
    print(f"  SL (perdedores): {sl_missing}")
    print(f"  Impacto: {tp_missing * 3 - sl_missing}R perdidos")
    
    # SOLUÇÃO: O engine precisa verificar mitigação de forma diferente
    # A mitigação no batch é: preço ultrapassou ob_bottom (bullish) ou ob_top (bearish)
    # MAS o batch verifica isso DEPOIS de calcular todos os OBs
    # O engine verifica a cada candle
    # 
    # O problema é que no engine, quando o preço toca o OB (fill), ele pode
    # também estar mitigando o OB no mesmo candle!
    #
    # Exemplo: OB bullish com bottom=100, midline=105
    # Candle: low=98 (toca midline E ultrapassa bottom)
    # Engine: marca como mitigado E não preenche
    # Batch: preenche porque verifica mitigação separadamente
    
    print("\n" + "=" * 100)
    print("ANÁLISE: Mitigação no mesmo candle do fill")
    print("=" * 100)
    
    same_candle_count = 0
    for (ob_idx, fill_idx), r in sorted(missing):
        s = r.signal
        mitigated = ob_data['MitigatedIndex'].iloc[ob_idx]
        
        if not np.isnan(mitigated) and int(mitigated) == fill_idx:
            same_candle_count += 1
    
    for (ob_idx, fill_idx), r in sorted(missing):
        s = r.signal
        for ob in engine.active_obs:
            if ob.confirmation_index == ob_idx:
                if ob.mitigated and ob.mitigated_index == fill_idx:
                    print(f"  OB={ob_idx} Fill={fill_idx}: Mitigação e fill NO MESMO CANDLE!")
                    print(f"    OB: top={ob.top:.2f} bottom={ob.bottom:.2f} midline={ob.midline:.2f}")
                    print(f"    Candle: high={df['high'].iloc[fill_idx]:.2f} low={df['low'].iloc[fill_idx]:.2f}")
                    if ob.direction == SignalDirection.BULLISH:
                        print(f"    Fill: low({df['low'].iloc[fill_idx]:.2f}) <= midline({ob.midline:.2f})")
                        print(f"    Mitigação: low({df['low'].iloc[fill_idx]:.2f}) <= bottom({ob.bottom:.2f})")
                    else:
                        print(f"    Fill: high({df['high'].iloc[fill_idx]:.2f}) >= midline({ob.midline:.2f})")
                        print(f"    Mitigação: high({df['high'].iloc[fill_idx]:.2f}) >= top({ob.top:.2f})")
                break
    
    print(f"\n  Total mitigação no mesmo candle do fill: {same_candle_count}")


if __name__ == "__main__":
    main()
