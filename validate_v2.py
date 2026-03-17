"""
Validação: Comparar Engine V2 (candle a candle) vs smc_touch_validated.py (batch)
"""

import sys
sys.path.insert(0, 'app')
sys.path.insert(0, '/home/ubuntu/smc_enhanced')

import pandas as pd
import numpy as np
from smc_engine_v2 import SMCEngineV2, OrderStatus, SignalDirection
from smc_touch_validated import SMCStrategyTouchValidated

def load_data(path, n=None):
    df = pd.read_csv(path)
    df.columns = [c.lower() for c in df.columns]
    if 'volume' not in df.columns:
        df['volume'] = df.get('tick_volume', df.get('real_volume', 1.0))
    if n:
        df = df.head(n)
    return df

def test_engine_v2(df):
    """Testa engine V2 candle a candle"""
    engine = SMCEngineV2(
        symbol='WINM24',
        swing_length=5,
        risk_reward_ratio=3.0,
        min_volume_ratio=1.5,
        min_ob_size_atr=0.5,
        use_not_mitigated_filter=True,
        max_pending_candles=100,
        entry_delay_candles=1,
    )
    
    vol_col = 'tick_volume' if 'tick_volume' in df.columns else 'volume'
    
    for i in range(len(df)):
        row = df.iloc[i]
        candle = {
            'time': str(row.get('time', '')),
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
            'volume': float(row[vol_col])
        }
        engine.add_candle(candle)
    
    return engine

def test_batch(df):
    """Testa versão batch (smc_touch_validated.py)"""
    strategy = SMCStrategyTouchValidated(
        df,
        swing_length=5,
        risk_reward_ratio=3.0,
        entry_delay_candles=1,
        use_not_mitigated_filter=True,
        min_volume_ratio=1.5,
        min_ob_size_atr=0.5,
    )
    signals = strategy.generate_signals()
    results, stats = strategy.backtest(signals)
    return results, stats

def main():
    print("=" * 100)
    print("VALIDAÇÃO: ENGINE V2 vs SMC_TOUCH_VALIDATED")
    print("=" * 100)
    
    # Usar dados menores primeiro para validação
    df = load_data('/home/ubuntu/upload/mtwin14400.csv')
    print(f"Dados: {len(df)} candles")
    
    # ========== TESTE BATCH ==========
    print("\n--- Teste BATCH (smc_touch_validated.py) ---")
    results_batch, stats_batch = test_batch(df)
    print(f"  Trades: {stats_batch['total_trades']}")
    print(f"  Win Rate: {stats_batch['win_rate']:.1f}%")
    print(f"  Profit Factor: {stats_batch['profit_factor']:.2f}")
    print(f"  Lucro (R): {stats_batch['total_profit_loss_r']:.1f}R")
    
    # Calcular lucro em pontos
    batch_pts = sum(r.profit_loss for r in results_batch)
    print(f"  Lucro (pts): {batch_pts:+.2f}")
    
    # ========== TESTE ENGINE V2 ==========
    print("\n--- Teste ENGINE V2 (candle a candle) ---")
    engine = test_engine_v2(df)
    stats_v2 = engine.get_stats()
    print(f"  Trades: {stats_v2['closed_orders']}")
    print(f"  Win Rate: {stats_v2['win_rate']:.1f}%")
    print(f"  Profit Factor: {stats_v2['profit_factor']:.2f}")
    print(f"  Lucro (pts): {stats_v2['total_profit_points']:+.2f}")
    print(f"  OBs detectados: {stats_v2['order_blocks_detected']}")
    print(f"  OBs ativos: {stats_v2['active_obs']}")
    print(f"  Ordens pendentes: {stats_v2['pending_orders']}")
    
    # ========== COMPARAÇÃO ==========
    print("\n" + "=" * 100)
    print("COMPARAÇÃO")
    print("=" * 100)
    
    print(f"\n{'Métrica':<25} {'BATCH':<20} {'ENGINE V2':<20} {'Diferença':<15}")
    print("-" * 80)
    print(f"{'Trades':<25} {stats_batch['total_trades']:<20} {stats_v2['closed_orders']:<20} "
          f"{stats_v2['closed_orders'] - stats_batch['total_trades']:<15}")
    print(f"{'Win Rate':<25} {stats_batch['win_rate']:<20.1f} {stats_v2['win_rate']:<20.1f} "
          f"{stats_v2['win_rate'] - stats_batch['win_rate']:<15.1f}")
    print(f"{'Profit Factor':<25} {stats_batch['profit_factor']:<20.2f} {stats_v2['profit_factor']:<20.2f}")
    print(f"{'Lucro (pts)':<25} {batch_pts:<20.2f} {stats_v2['total_profit_points']:<20.2f}")
    
    # ========== VALIDAÇÃO DE INTEGRIDADE ==========
    print("\n" + "=" * 100)
    print("VALIDAÇÃO DE INTEGRIDADE")
    print("=" * 100)
    
    trades = engine.get_all_trades()
    
    # Teste 1: Nenhum trade com OB mitigado
    print("\n--- Teste 1: OBs Mitigados ---")
    mitigated_trades = 0
    for trade in trades:
        ob = next((ob for ob in engine.active_obs if ob.id == trade['ob_id']), None)
        if ob and ob.is_mitigated and ob.mitigated_at < trade['filled_at']:
            mitigated_trades += 1
    print(f"  Trades com OB mitigado ANTES do fill: {mitigated_trades}")
    if mitigated_trades == 0:
        print("  ✅ PASSOU")
    else:
        print("  ❌ FALHOU")
    
    # Teste 2: Sequência temporal correta
    print("\n--- Teste 2: Sequência Temporal ---")
    violations = 0
    for trade in trades:
        if trade['filled_at'] <= trade['created_at']:
            violations += 1
        if trade['closed_at'] <= trade['filled_at']:
            violations += 1
    print(f"  Violações temporais: {violations}")
    if violations == 0:
        print("  ✅ PASSOU")
    else:
        print("  ❌ FALHOU")
    
    # Teste 3: Fill não no mesmo candle do sinal
    print("\n--- Teste 3: Fill após sinal ---")
    same_candle = sum(1 for t in trades if t['filled_at'] <= t['created_at'])
    print(f"  Fills no mesmo candle ou antes: {same_candle}")
    if same_candle == 0:
        print("  ✅ PASSOU")
    else:
        print("  ❌ FALHOU")
    
    # Teste 4: Toque real na linha
    print("\n--- Teste 4: Toque Real na Linha ---")
    invalid_touches = 0
    for trade in trades:
        fill_idx = trade['filled_at']
        entry = trade['entry_price']
        if trade['direction'] == 'BULLISH':
            if engine.cache.lows[fill_idx] > entry:
                invalid_touches += 1
        else:
            if engine.cache.highs[fill_idx] < entry:
                invalid_touches += 1
    print(f"  Toques inválidos: {invalid_touches}")
    if invalid_touches == 0:
        print("  ✅ PASSOU")
    else:
        print("  ❌ FALHOU")
    
    # Teste 5: TP/SL correto
    print("\n--- Teste 5: TP/SL Correto ---")
    tp_sl_errors = 0
    for trade in trades:
        close_idx = trade['closed_at']
        if trade['status'] == 'closed_tp':
            if trade['direction'] == 'BULLISH':
                if engine.cache.highs[close_idx] < trade['take_profit']:
                    tp_sl_errors += 1
            else:
                if engine.cache.lows[close_idx] > trade['take_profit']:
                    tp_sl_errors += 1
        elif trade['status'] == 'closed_sl':
            if trade['direction'] == 'BULLISH':
                if engine.cache.lows[close_idx] > trade['stop_loss']:
                    tp_sl_errors += 1
            else:
                if engine.cache.highs[close_idx] < trade['stop_loss']:
                    tp_sl_errors += 1
    print(f"  Erros de TP/SL: {tp_sl_errors}")
    if tp_sl_errors == 0:
        print("  ✅ PASSOU")
    else:
        print("  ❌ FALHOU")
    
    # ========== TABELA DE TRADES ==========
    print("\n" + "=" * 100)
    print("TABELA DE TRADES (Engine V2)")
    print("=" * 100)
    
    if trades:
        print(f"\n{'ID':<12} {'Dir':<10} {'Entry':<14} {'SL':<14} {'TP':<14} "
              f"{'Criado':<8} {'Fill':<8} {'Close':<8} {'Status':<12} {'P/L':<12} "
              f"{'Espera':<8} {'Duração':<8} {'Padrões':<20}")
        print("-" * 150)
        
        for t in trades[:50]:
            print(f"{t['id']:<12} {t['direction']:<10} {t['entry_price']:<14.2f} "
                  f"{t['stop_loss']:<14.2f} {t['take_profit']:<14.2f} "
                  f"{t['created_at']:<8} {t['filled_at']:<8} {t['closed_at']:<8} "
                  f"{t['status']:<12} {t['profit_loss']:<+12.2f} "
                  f"{t['wait_candles']:<8} {t['duration']:<8} "
                  f"{','.join(t['patterns']):<20}")
    
    # ========== TRADES POR MÊS ==========
    if 'time' in df.columns:
        print("\n" + "=" * 100)
        print("TRADES POR MÊS")
        print("=" * 100)
        
        df_time = pd.to_datetime(df['time'])
        
        from collections import defaultdict
        monthly = defaultdict(lambda: {'wins': 0, 'losses': 0, 'pnl': 0.0, 'trades': 0})
        
        for t in trades:
            try:
                month = df_time.iloc[t['filled_at']].strftime('%Y-%m')
                monthly[month]['trades'] += 1
                if t['status'] == 'closed_tp':
                    monthly[month]['wins'] += 1
                else:
                    monthly[month]['losses'] += 1
                monthly[month]['pnl'] += t['profit_loss']
            except:
                pass
        
        print(f"\n{'Mês':<12} {'Trades':<10} {'Wins':<8} {'Losses':<8} {'WR%':<8} {'P/L (pts)':<12}")
        print("-" * 60)
        
        total_t = total_w = total_l = 0
        total_pnl = 0.0
        
        for month in sorted(monthly.keys()):
            m = monthly[month]
            wr = (m['wins'] / m['trades'] * 100) if m['trades'] > 0 else 0
            total_t += m['trades']
            total_w += m['wins']
            total_l += m['losses']
            total_pnl += m['pnl']
            print(f"{month:<12} {m['trades']:<10} {m['wins']:<8} {m['losses']:<8} "
                  f"{wr:<8.1f} {m['pnl']:<+12.2f}")
        
        n_months = len(monthly)
        avg_wr = (total_w / total_t * 100) if total_t > 0 else 0
        print("-" * 60)
        print(f"{'TOTAL':<12} {total_t:<10} {total_w:<8} {total_l:<8} "
              f"{avg_wr:<8.1f} {total_pnl:<+12.2f}")
        print(f"{'MÉDIA/MÊS':<12} {total_t/n_months if n_months else 0:<10.1f}")


if __name__ == "__main__":
    main()
