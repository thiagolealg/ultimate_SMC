"""
Validação Rigorosa do SMC Engine
================================
1. Tabela detalhada de cada trade
2. Verifica se OBs mitigados estão sendo usados
3. Valida ordem temporal (sinal antes do toque)
4. Confirma que não há trades retroativos
"""

import sys
import csv
sys.path.insert(0, 'app')

import pandas as pd
from smc_engine import SMCEngine, OrderStatus, SignalDirection

def load_data():
    df = pd.read_csv('/home/ubuntu/upload/mtwin14400.csv')
    df.columns = [c.lower() for c in df.columns]
    return df

def run_validation():
    df = load_data()
    print(f"Dados carregados: {len(df)} candles")
    
    # Usar apenas 20.000 candles para análise detalhada
    df = df.head(20000)
    
    engine = SMCEngine(
        symbol='WINM24',
        swing_length=5,
        risk_reward_ratio=3.0,
        min_volume_ratio=1.5,
        min_ob_size_atr=0.5,
        use_not_mitigated_filter=True
    )
    
    vol_col = 'tick_volume' if 'tick_volume' in df.columns else 'volume'
    
    # Rastrear TUDO
    all_events = []  # Todos os eventos em ordem
    ob_creation_log = {}  # ob_index -> candle_index quando foi criado
    signal_log = {}  # order_id -> candle_index quando sinal foi gerado
    fill_log = {}  # order_id -> candle_index quando ordem foi preenchida
    close_log = {}  # order_id -> candle_index quando ordem foi fechada
    ob_mitigated_log = {}  # ob_index -> candle_index quando foi mitigado
    
    prev_ob_count = 0
    prev_pending_count = 0
    prev_filled_count = 0
    prev_closed_count = 0
    
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
        
        # Detectar novos OBs
        if len(engine.order_blocks) > prev_ob_count:
            for ob in engine.order_blocks[prev_ob_count:]:
                ob_creation_log[ob.index] = i
                all_events.append({
                    'candle_idx': i,
                    'event': 'OB_CREATED',
                    'details': f"OB {ob.direction.name} @ midline={ob.midline:.2f}, "
                              f"top={ob.top:.2f}, bottom={ob.bottom:.2f}, "
                              f"ob_candle_idx={ob.index}, confirm_idx={ob.confirmation_index}"
                })
            prev_ob_count = len(engine.order_blocks)
        
        # Detectar novos sinais/ordens pendentes
        if len(signals) > 0:
            for sig in signals:
                # Encontrar a ordem pendente correspondente
                for order in engine.pending_orders:
                    if order.entry_price == sig.entry_price and order.id not in signal_log:
                        signal_log[order.id] = i
                        all_events.append({
                            'candle_idx': i,
                            'event': 'SIGNAL_CREATED',
                            'details': f"Order {order.id}: {order.direction.name} "
                                      f"LIMIT @ {order.entry_price:.2f}, "
                                      f"SL={order.stop_loss:.2f}, TP={order.take_profit:.2f}, "
                                      f"OB_idx={order.ob.index}, OB_mitigated={order.ob.is_mitigated}"
                        })
        
        # Detectar ordens preenchidas
        if len(engine.filled_orders) > prev_filled_count:
            for order in engine.filled_orders[prev_filled_count:]:
                if order.id not in fill_log:
                    fill_log[order.id] = i
                    ob_mitigated_log[order.ob.index] = i
                    all_events.append({
                        'candle_idx': i,
                        'event': 'ORDER_FILLED',
                        'details': f"Order {order.id}: {order.direction.name} "
                                  f"FILLED @ {order.entry_price:.2f}, "
                                  f"candle_low={candle['low']:.2f}, candle_high={candle['high']:.2f}"
                    })
            prev_filled_count = len(engine.filled_orders)
        
        # Detectar ordens fechadas
        if len(engine.closed_orders) > prev_closed_count:
            for order in engine.closed_orders[prev_closed_count:]:
                if order.id not in close_log:
                    close_log[order.id] = i
                    all_events.append({
                        'candle_idx': i,
                        'event': f"ORDER_CLOSED_{order.status.value.upper()}",
                        'details': f"Order {order.id}: P/L={order.profit_loss:+.2f} pts"
                    })
            prev_closed_count = len(engine.closed_orders)
    
    # ============================================================
    # RELATÓRIO
    # ============================================================
    
    print("\n" + "=" * 100)
    print("TABELA DE TRADES DETALHADA")
    print("=" * 100)
    
    # Cabeçalho
    header = f"{'ID':<10} {'Dir':<8} {'OB_Idx':<8} {'Entry':<12} {'SL':<12} {'TP':<12} " \
             f"{'Signal@':<10} {'Fill@':<10} {'Close@':<10} {'Status':<12} {'P/L':<12} " \
             f"{'OB_Mitig?':<10} {'Conf%':<8}"
    print(header)
    print("-" * 140)
    
    trades_table = []
    
    for order in engine.closed_orders:
        sig_candle = signal_log.get(order.id, '?')
        fill_candle = fill_log.get(order.id, '?')
        close_candle = close_log.get(order.id, '?')
        
        # Verificar se OB estava mitigado ANTES do sinal
        ob_was_mitigated_before_signal = False
        if order.ob.index in ob_mitigated_log:
            mitigated_at = ob_mitigated_log[order.ob.index]
            if isinstance(sig_candle, int) and mitigated_at < sig_candle:
                ob_was_mitigated_before_signal = True
        
        row_data = {
            'id': order.id,
            'direction': order.direction.name,
            'ob_index': order.ob.index,
            'entry_price': order.entry_price,
            'stop_loss': order.stop_loss,
            'take_profit': order.take_profit,
            'signal_candle': sig_candle,
            'fill_candle': fill_candle,
            'close_candle': close_candle,
            'status': order.status.value,
            'profit_loss': order.profit_loss,
            'ob_mitigated_before': ob_was_mitigated_before_signal,
            'confidence': order.confidence
        }
        trades_table.append(row_data)
        
        status_str = "TP ✅" if order.status == OrderStatus.CLOSED_TP else "SL ❌"
        mitig_str = "SIM ⚠️" if ob_was_mitigated_before_signal else "NÃO ✅"
        
        print(f"{order.id:<10} {order.direction.name:<8} {order.ob.index:<8} "
              f"{order.entry_price:<12.2f} {order.stop_loss:<12.2f} {order.take_profit:<12.2f} "
              f"{str(sig_candle):<10} {str(fill_candle):<10} {str(close_candle):<10} "
              f"{status_str:<12} {order.profit_loss:<+12.2f} "
              f"{mitig_str:<10} {order.confidence:<8.1f}")
    
    # ============================================================
    # VALIDAÇÃO 1: OBs MITIGADOS
    # ============================================================
    
    print("\n" + "=" * 100)
    print("VALIDAÇÃO 1: OBs MITIGADOS USADOS PARA TRADE?")
    print("=" * 100)
    
    mitigated_trades = [t for t in trades_table if t['ob_mitigated_before']]
    print(f"Total de trades: {len(trades_table)}")
    print(f"Trades com OB já mitigado: {len(mitigated_trades)}")
    
    if len(mitigated_trades) == 0:
        print("✅ PASSOU: Nenhum trade usa OB já mitigado!")
    else:
        print("❌ FALHOU: Trades usando OBs já mitigados:")
        for t in mitigated_trades:
            print(f"   {t['id']}: OB_idx={t['ob_index']}")
    
    # ============================================================
    # VALIDAÇÃO 2: ORDEM TEMPORAL (SINAL ANTES DO TOQUE)
    # ============================================================
    
    print("\n" + "=" * 100)
    print("VALIDAÇÃO 2: SINAL GERADO ANTES DO TOQUE NA LINHA?")
    print("=" * 100)
    
    temporal_violations = []
    for t in trades_table:
        sig = t['signal_candle']
        fill = t['fill_candle']
        if isinstance(sig, int) and isinstance(fill, int):
            if fill <= sig:
                temporal_violations.append(t)
    
    print(f"Total de trades: {len(trades_table)}")
    print(f"Violações temporais: {len(temporal_violations)}")
    
    if len(temporal_violations) == 0:
        print("✅ PASSOU: Todos os sinais são gerados ANTES do toque!")
    else:
        print("❌ FALHOU: Trades com violação temporal:")
        for t in temporal_violations:
            print(f"   {t['id']}: Signal@{t['signal_candle']} Fill@{t['fill_candle']} "
                  f"(fill deveria ser > signal)")
    
    # ============================================================
    # VALIDAÇÃO 3: TOQUE REAL NA LINHA
    # ============================================================
    
    print("\n" + "=" * 100)
    print("VALIDAÇÃO 3: PREÇO REALMENTE TOCOU A LINHA DO MEIO?")
    print("=" * 100)
    
    touch_violations = []
    for order in engine.closed_orders:
        fill_idx = fill_log.get(order.id)
        if fill_idx is not None and fill_idx < len(df):
            fill_row = df.iloc[fill_idx]
            candle_low = float(fill_row['low'])
            candle_high = float(fill_row['high'])
            midline = order.entry_price
            
            if order.direction == SignalDirection.BULLISH:
                # Buy Limit: LOW deve ser <= midline
                if candle_low > midline:
                    touch_violations.append({
                        'id': order.id,
                        'direction': 'BULLISH',
                        'midline': midline,
                        'candle_low': candle_low,
                        'candle_high': candle_high,
                        'fill_idx': fill_idx
                    })
            else:
                # Sell Limit: HIGH deve ser >= midline
                if candle_high < midline:
                    touch_violations.append({
                        'id': order.id,
                        'direction': 'BEARISH',
                        'midline': midline,
                        'candle_low': candle_low,
                        'candle_high': candle_high,
                        'fill_idx': fill_idx
                    })
    
    print(f"Total de trades: {len(engine.closed_orders)}")
    print(f"Toques inválidos: {len(touch_violations)}")
    
    if len(touch_violations) == 0:
        print("✅ PASSOU: Todos os toques na linha são reais!")
    else:
        print("❌ FALHOU: Trades com toque inválido:")
        for v in touch_violations[:10]:
            print(f"   {v['id']}: {v['direction']} midline={v['midline']:.2f} "
                  f"low={v['candle_low']:.2f} high={v['candle_high']:.2f}")
    
    # ============================================================
    # VALIDAÇÃO 4: OB CONFIRMADO ANTES DO SINAL
    # ============================================================
    
    print("\n" + "=" * 100)
    print("VALIDAÇÃO 4: OB FOI CONFIRMADO ANTES DO SINAL?")
    print("=" * 100)
    
    confirmation_violations = []
    for order in engine.closed_orders:
        sig_idx = signal_log.get(order.id)
        if sig_idx is not None:
            # O sinal deve ser gerado APÓS a confirmação do OB
            if sig_idx <= order.ob.confirmation_index:
                confirmation_violations.append({
                    'id': order.id,
                    'signal_idx': sig_idx,
                    'confirmation_idx': order.ob.confirmation_index
                })
    
    print(f"Total de trades: {len(engine.closed_orders)}")
    print(f"Violações de confirmação: {len(confirmation_violations)}")
    
    if len(confirmation_violations) == 0:
        print("✅ PASSOU: Todos os OBs são confirmados antes do sinal!")
    else:
        print("❌ FALHOU: Sinais gerados antes da confirmação do OB:")
        for v in confirmation_violations[:10]:
            print(f"   {v['id']}: Signal@{v['signal_idx']} Confirm@{v['confirmation_idx']}")
    
    # ============================================================
    # VALIDAÇÃO 5: NÃO FAZ TRADE DO PASSADO
    # ============================================================
    
    print("\n" + "=" * 100)
    print("VALIDAÇÃO 5: SEQUÊNCIA TEMPORAL COMPLETA")
    print("=" * 100)
    
    sequence_violations = []
    for order in engine.closed_orders:
        sig = signal_log.get(order.id, None)
        fill = fill_log.get(order.id, None)
        close = close_log.get(order.id, None)
        ob_created = ob_creation_log.get(order.ob.index, None)
        
        if all(v is not None for v in [ob_created, sig, fill, close]):
            # Sequência correta: OB_criado < Sinal < Fill < Close
            if not (ob_created <= sig < fill <= close):
                sequence_violations.append({
                    'id': order.id,
                    'ob_created': ob_created,
                    'signal': sig,
                    'fill': fill,
                    'close': close
                })
    
    print(f"Total de trades: {len(engine.closed_orders)}")
    print(f"Violações de sequência: {len(sequence_violations)}")
    
    if len(sequence_violations) == 0:
        print("✅ PASSOU: Sequência OB→Sinal→Fill→Close correta em todos os trades!")
    else:
        print("❌ FALHOU: Trades com sequência incorreta:")
        for v in sequence_violations[:10]:
            print(f"   {v['id']}: OB@{v['ob_created']} → Signal@{v['signal']} → "
                  f"Fill@{v['fill']} → Close@{v['close']}")
    
    # ============================================================
    # VALIDAÇÃO 6: VERIFICAR FILL NO MESMO CANDLE DO SINAL
    # ============================================================
    
    print("\n" + "=" * 100)
    print("VALIDAÇÃO 6: FILL NÃO OCORRE NO MESMO CANDLE DO SINAL?")
    print("=" * 100)
    
    same_candle_fills = []
    for order in engine.closed_orders:
        sig = signal_log.get(order.id)
        fill = fill_log.get(order.id)
        if sig is not None and fill is not None and sig == fill:
            same_candle_fills.append({
                'id': order.id,
                'candle': sig
            })
    
    print(f"Total de trades: {len(engine.closed_orders)}")
    print(f"Fills no mesmo candle do sinal: {len(same_candle_fills)}")
    
    if len(same_candle_fills) == 0:
        print("✅ PASSOU: Nenhum fill no mesmo candle do sinal!")
    else:
        print(f"⚠️ ATENÇÃO: {len(same_candle_fills)} fills no mesmo candle do sinal")
        for v in same_candle_fills[:10]:
            print(f"   {v['id']}: Signal e Fill ambos no candle {v['candle']}")
    
    # ============================================================
    # RESUMO FINAL
    # ============================================================
    
    print("\n" + "=" * 100)
    print("RESUMO FINAL DA VALIDAÇÃO")
    print("=" * 100)
    
    tests = [
        ("OBs mitigados não usados", len(mitigated_trades) == 0),
        ("Sinal antes do toque", len(temporal_violations) == 0),
        ("Toque real na linha", len(touch_violations) == 0),
        ("OB confirmado antes do sinal", len(confirmation_violations) == 0),
        ("Sequência temporal correta", len(sequence_violations) == 0),
        ("Fill não no mesmo candle", len(same_candle_fills) == 0),
    ]
    
    for name, passed in tests:
        status = "✅ PASSOU" if passed else "❌ FALHOU"
        print(f"  {status} - {name}")
    
    passed_count = sum(1 for _, p in tests if p)
    print(f"\n  Resultado: {passed_count}/{len(tests)} testes passaram")
    
    # Estatísticas
    stats = engine.get_stats()
    print(f"\n  Trades totais: {stats['closed_orders']}")
    print(f"  Win Rate: {stats['win_rate']:.1f}%")
    print(f"  Lucro total: {stats['total_profit_points']:+.2f} pts")
    
    # Salvar tabela em CSV
    csv_path = '/home/ubuntu/smc_realtime/trades_table.csv'
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=trades_table[0].keys() if trades_table else [])
        writer.writeheader()
        writer.writerows(trades_table)
    print(f"\n  Tabela salva em: {csv_path}")
    
    # Salvar log de eventos
    events_path = '/home/ubuntu/smc_realtime/events_log.csv'
    with open(events_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['candle_idx', 'event', 'details'])
        writer.writeheader()
        writer.writerows(all_events)
    print(f"  Log de eventos salvo em: {events_path}")


if __name__ == "__main__":
    run_validation()
