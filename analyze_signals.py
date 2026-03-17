"""
Análise Detalhada:
1. Quantos candles são usados para definir cada sinal
2. Quantos trades são feitos por mês
3. Tempo entre sinal → fill → close
4. Expiração de ordens pendentes
"""

import sys
sys.path.insert(0, 'app')

import pandas as pd
import numpy as np
from collections import defaultdict
from smc_engine import SMCEngine, OrderStatus, SignalDirection

def load_data():
    df = pd.read_csv('/home/ubuntu/upload/mtwin14400.csv')
    df.columns = [c.lower() for c in df.columns]
    return df

def analyze():
    df = load_data()
    print(f"Total de candles: {len(df)}")
    
    # Verificar timeframe
    if 'time' in df.columns:
        df['time'] = pd.to_datetime(df['time'])
        if len(df) > 1:
            diff = (df['time'].iloc[1] - df['time'].iloc[0]).total_seconds()
            print(f"Timeframe: {diff} segundos = {diff/60:.0f} minutos")
            print(f"Período: {df['time'].iloc[0]} até {df['time'].iloc[-1]}")
            
            # Calcular candles por mês
            total_months = (df['time'].iloc[-1] - df['time'].iloc[0]).days / 30.44
            candles_per_month = len(df) / total_months if total_months > 0 else 0
            print(f"Total de meses: {total_months:.1f}")
            print(f"Candles por mês: {candles_per_month:.0f}")
    
    # Usar todos os dados
    engine = SMCEngine(
        symbol='WINM24',
        swing_length=5,
        risk_reward_ratio=3.0,
        min_volume_ratio=1.5,
        min_ob_size_atr=0.5,
        use_not_mitigated_filter=True
    )
    
    vol_col = 'tick_volume' if 'tick_volume' in df.columns else 'volume'
    
    # Rastrear eventos
    signal_events = []  # (candle_idx, time, signal_details)
    fill_events = []    # (candle_idx, time, order_id)
    close_events = []   # (candle_idx, time, order_id, status, pnl)
    
    ob_events = []      # (candle_idx, time, ob_details)
    
    prev_ob_count = 0
    prev_pending = set()
    prev_filled = set()
    prev_closed = set()
    
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
        
        signals = engine.add_candle(candle)
        
        # Novos OBs
        if len(engine.order_blocks) > prev_ob_count:
            for ob in engine.order_blocks[prev_ob_count:]:
                ob_events.append({
                    'candle_idx': i,
                    'time': row.get('time', ''),
                    'ob_index': ob.index,
                    'direction': ob.direction.name,
                    'midline': ob.midline,
                    'confirmation_idx': ob.confirmation_index,
                    'candles_to_confirm': ob.confirmation_index - ob.index
                })
            prev_ob_count = len(engine.order_blocks)
        
        # Novos sinais
        for sig in signals:
            signal_events.append({
                'candle_idx': i,
                'time': row.get('time', ''),
                'direction': sig.direction.name,
                'entry_price': sig.entry_price,
                'sl': sig.stop_loss,
                'tp': sig.take_profit,
                'confidence': sig.confidence,
                'patterns': [p.value for p in sig.patterns]
            })
        
        # Novas fills
        current_filled_ids = {o.id for o in engine.filled_orders}
        new_fills = current_filled_ids - prev_filled
        for order in engine.filled_orders:
            if order.id in new_fills:
                fill_events.append({
                    'candle_idx': i,
                    'time': row.get('time', ''),
                    'order_id': order.id,
                    'direction': order.direction.name,
                    'entry_price': order.entry_price,
                    'created_at': order.created_at
                })
        prev_filled = current_filled_ids
        
        # Novos closes
        current_closed_ids = {o.id for o in engine.closed_orders}
        new_closes = current_closed_ids - prev_closed
        for order in engine.closed_orders:
            if order.id in new_closes:
                close_events.append({
                    'candle_idx': i,
                    'time': row.get('time', ''),
                    'order_id': order.id,
                    'direction': order.direction.name,
                    'status': order.status.value,
                    'pnl': order.profit_loss,
                    'filled_at': order.filled_at
                })
        prev_closed = current_closed_ids
    
    # ============================================================
    # ANÁLISE 1: CANDLES USADOS PARA DEFINIÇÃO DE SINAIS
    # ============================================================
    
    print("\n" + "=" * 100)
    print("ANÁLISE 1: CANDLES USADOS PARA DEFINIÇÃO DE SINAIS")
    print("=" * 100)
    
    print(f"\n--- Parâmetros do Engine ---")
    print(f"  swing_length = 5")
    print(f"  Candles necessários para confirmar Swing: {5} (5 candles antes + 5 depois)")
    print(f"  Candles para ATR: 14")
    print(f"  Candles para Volume MA: 20")
    print(f"  Candles para EMA 20: 20")
    print(f"  Candles para EMA 50: 50")
    print(f"  Mínimo para operar: ~50 candles de warmup")
    
    print(f"\n--- Fluxo de Criação de Sinal ---")
    print(f"  1. Swing High/Low detectado no candle [i]")
    print(f"     → Precisa de {5} candles ANTES e {5} candles DEPOIS")
    print(f"     → Confirmação no candle [i + {5}]")
    print(f"  2. OB identificado no candle anterior ao swing [i-1 a i-5]")
    print(f"  3. Filtros aplicados: Volume > 1.5x média, Tamanho > 0.5 ATR")
    print(f"  4. Ordem LIMIT criada no candle de confirmação [i + {5}]")
    print(f"  5. Aguarda preço tocar a linha do meio")
    
    if ob_events:
        candles_to_confirm = [e['candles_to_confirm'] for e in ob_events]
        print(f"\n--- Estatísticas de Confirmação de OB ---")
        print(f"  Total de OBs criados: {len(ob_events)}")
        print(f"  Candles para confirmar (média): {np.mean(candles_to_confirm):.1f}")
        print(f"  Candles para confirmar (min): {min(candles_to_confirm)}")
        print(f"  Candles para confirmar (max): {max(candles_to_confirm)}")
    
    # Tempo entre sinal e fill
    if fill_events:
        wait_candles = []
        for fill in fill_events:
            wait = fill['candle_idx'] - fill['created_at']
            wait_candles.append(wait)
        
        print(f"\n--- Tempo de Espera: Sinal → Fill (Toque na Linha) ---")
        print(f"  Total de fills: {len(fill_events)}")
        print(f"  Candles de espera (média): {np.mean(wait_candles):.1f}")
        print(f"  Candles de espera (mediana): {np.median(wait_candles):.1f}")
        print(f"  Candles de espera (min): {min(wait_candles)}")
        print(f"  Candles de espera (max): {max(wait_candles)}")
        print(f"  Candles de espera (P25): {np.percentile(wait_candles, 25):.0f}")
        print(f"  Candles de espera (P75): {np.percentile(wait_candles, 75):.0f}")
        print(f"  Candles de espera (P95): {np.percentile(wait_candles, 95):.0f}")
        
        # Distribuição
        print(f"\n  Distribuição de espera:")
        bins = [0, 5, 10, 20, 50, 100, 500, 1000, 5000, 20000]
        for j in range(len(bins)-1):
            count = sum(1 for w in wait_candles if bins[j] <= w < bins[j+1])
            pct = count / len(wait_candles) * 100
            bar = "█" * int(pct / 2)
            print(f"    {bins[j]:>5} - {bins[j+1]:>5} candles: {count:>5} ({pct:>5.1f}%) {bar}")
    
    # Tempo entre fill e close
    if close_events:
        trade_duration = []
        for close in close_events:
            if close['filled_at'] is not None:
                dur = close['candle_idx'] - close['filled_at']
                trade_duration.append(dur)
        
        if trade_duration:
            print(f"\n--- Duração do Trade: Fill → Close (TP/SL) ---")
            print(f"  Total de trades fechados: {len(trade_duration)}")
            print(f"  Duração (média): {np.mean(trade_duration):.1f} candles")
            print(f"  Duração (mediana): {np.median(trade_duration):.1f} candles")
            print(f"  Duração (min): {min(trade_duration)}")
            print(f"  Duração (max): {max(trade_duration)}")
    
    # ============================================================
    # ANÁLISE 2: TRADES POR MÊS
    # ============================================================
    
    print("\n" + "=" * 100)
    print("ANÁLISE 2: TRADES POR MÊS")
    print("=" * 100)
    
    if 'time' in df.columns:
        # Agrupar fills por mês
        fills_by_month = defaultdict(int)
        closes_by_month = defaultdict(lambda: {'wins': 0, 'losses': 0, 'pnl': 0})
        
        for fill in fill_events:
            try:
                t = pd.to_datetime(fill['time'])
                month_key = t.strftime('%Y-%m')
                fills_by_month[month_key] += 1
            except:
                pass
        
        for close in close_events:
            try:
                t = pd.to_datetime(close['time'])
                month_key = t.strftime('%Y-%m')
                if close['status'] == 'closed_tp':
                    closes_by_month[month_key]['wins'] += 1
                else:
                    closes_by_month[month_key]['losses'] += 1
                closes_by_month[month_key]['pnl'] += close['pnl']
            except:
                pass
        
        if fills_by_month:
            print(f"\n{'Mês':<12} {'Entradas':<10} {'Wins':<8} {'Losses':<8} {'WR%':<8} {'P/L (pts)':<12}")
            print("-" * 60)
            
            total_entries = 0
            total_wins = 0
            total_losses = 0
            total_pnl = 0
            
            for month in sorted(fills_by_month.keys()):
                entries = fills_by_month[month]
                wins = closes_by_month[month]['wins']
                losses = closes_by_month[month]['losses']
                pnl = closes_by_month[month]['pnl']
                wr = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
                
                total_entries += entries
                total_wins += wins
                total_losses += losses
                total_pnl += pnl
                
                print(f"{month:<12} {entries:<10} {wins:<8} {losses:<8} {wr:<8.1f} {pnl:<+12.2f}")
            
            n_months = len(fills_by_month)
            avg_entries = total_entries / n_months if n_months > 0 else 0
            avg_wr = (total_wins / (total_wins + total_losses) * 100) if (total_wins + total_losses) > 0 else 0
            avg_pnl = total_pnl / n_months if n_months > 0 else 0
            
            print("-" * 60)
            print(f"{'TOTAL':<12} {total_entries:<10} {total_wins:<8} {total_losses:<8} {avg_wr:<8.1f} {total_pnl:<+12.2f}")
            print(f"{'MÉDIA/MÊS':<12} {avg_entries:<10.1f}")
            print(f"\nMeses ativos: {n_months}")
            print(f"Trades por mês (média): {avg_entries:.1f}")
            print(f"P/L por mês (média): {avg_pnl:+.2f} pts")
    
    # ============================================================
    # ANÁLISE 3: PROBLEMA DAS ORDENS ANTIGAS
    # ============================================================
    
    print("\n" + "=" * 100)
    print("ANÁLISE 3: ORDENS PENDENTES MUITO ANTIGAS")
    print("=" * 100)
    
    if fill_events:
        old_fills = [f for f in fill_events if (f['candle_idx'] - f['created_at']) > 100]
        print(f"Ordens preenchidas após > 100 candles de espera: {len(old_fills)}/{len(fill_events)}")
        print(f"Ordens preenchidas após > 500 candles: {sum(1 for f in fill_events if (f['candle_idx'] - f['created_at']) > 500)}")
        print(f"Ordens preenchidas após > 1000 candles: {sum(1 for f in fill_events if (f['candle_idx'] - f['created_at']) > 1000)}")
        
        if old_fills:
            print(f"\nExemplos de ordens muito antigas:")
            for f in sorted(old_fills, key=lambda x: x['candle_idx'] - x['created_at'], reverse=True)[:10]:
                wait = f['candle_idx'] - f['created_at']
                print(f"  {f['order_id']}: Criada@{f['created_at']} Fill@{f['candle_idx']} "
                      f"Espera={wait} candles ({wait*1:.0f} min)")
    
    # ============================================================
    # ANÁLISE 4: IMPACTO DA EXPIRAÇÃO
    # ============================================================
    
    print("\n" + "=" * 100)
    print("ANÁLISE 4: SIMULAÇÃO COM EXPIRAÇÃO DE ORDENS")
    print("=" * 100)
    
    for max_wait in [20, 50, 100, 200, 500]:
        wins = 0
        losses = 0
        pnl = 0
        
        for close in close_events:
            fill_match = next((f for f in fill_events if f['order_id'] == close['order_id']), None)
            if fill_match:
                wait = fill_match['candle_idx'] - fill_match['created_at']
                if wait <= max_wait:
                    if close['status'] == 'closed_tp':
                        wins += 1
                    else:
                        losses += 1
                    pnl += close['pnl']
        
        total = wins + losses
        wr = (wins / total * 100) if total > 0 else 0
        print(f"  Max espera {max_wait:>4} candles: {total:>4} trades, "
              f"WR={wr:>5.1f}%, P/L={pnl:>+10.2f} pts")
    
    # Ordens ainda pendentes
    print(f"\n  Ordens ainda pendentes: {len(engine.pending_orders)}")
    print(f"  Ordens preenchidas (abertas): {len(engine.filled_orders)}")
    
    # Stats finais
    stats = engine.get_stats()
    print(f"\n--- Resumo Final ---")
    print(f"  Candles processados: {stats['candles_processed']}")
    print(f"  OBs detectados: {stats['order_blocks_detected']}")
    print(f"  Trades fechados: {stats['closed_orders']}")
    print(f"  Win Rate: {stats['win_rate']:.1f}%")
    print(f"  Lucro total: {stats['total_profit_points']:+.2f} pts")


if __name__ == "__main__":
    analyze()
