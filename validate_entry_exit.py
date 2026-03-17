"""
Validação do Momento de Entrada e Saída - Engine V3
=====================================================

Este script rastreia candle a candle:
1. Quando o OB foi detectado (swing confirmado)
2. Quando a ordem pendente foi criada
3. O entry_delay (não pode entrar antes)
4. Quando o preço tocou a midline (fill)
5. Se o candle do fill NÃO ultrapassou o OB inteiro (filtro de mitigação)
6. Quando TP ou SL foi atingido (a partir do candle SEGUINTE ao fill)
7. Se a projeção 3:1 está correta
8. Se houve lookahead bias em qualquer ponto

Gera relatório detalhado + visualização matplotlib.
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(__file__))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import numpy as np

from smc_engine_v3 import SMCEngineV3, SignalDirection, OrderStatus

# ============================================================
# 1. Carregar dados
# ============================================================
with open('mtwin14400.csv', 'r') as f:
    lines = f.readlines()

candles = []
for line in lines[1:]:
    parts = line.strip().split(',')
    if len(parts) >= 6:
        candles.append({
            'time': parts[0],
            'open': float(parts[1]),
            'high': float(parts[2]),
            'low': float(parts[3]),
            'close': float(parts[4]),
            'volume': float(parts[5]) if len(parts) > 5 else 1.0,
        })

# ============================================================
# 2. Rodar engine com rastreio detalhado
# ============================================================
engine = SMCEngineV3(
    swing_length=5,
    risk_reward_ratio=3.0,
    min_volume_ratio=0.0,
    min_ob_size_atr=0.0,
    use_not_mitigated_filter=True,
    max_pending_candles=150,
    entry_delay_candles=1,
)

# Rastrear todos os eventos por candle
timeline = []
all_events = []

for i, candle in enumerate(candles):
    events = engine.add_candle(candle)
    
    entry = {
        'idx': i,
        'candle': candle,
        'new_obs': events['new_obs'],
        'new_signals': events['new_signals'],
        'filled_orders': events['filled_orders'],
        'closed_trades': events['closed_trades'],
        'expired_orders': events['expired_orders'],
        'cancelled_orders': events['cancelled_orders'],
        'active_obs': len(engine.active_obs),
        'pending_count': len(engine.pending_orders),
        'filled_count': len(engine.filled_orders),
    }
    timeline.append(entry)
    
    if any([events['new_obs'], events['new_signals'], events['filled_orders'], 
            events['closed_trades'], events['expired_orders'], events['cancelled_orders']]):
        all_events.append(entry)

# ============================================================
# 3. Validação detalhada de cada trade
# ============================================================
print("=" * 80)
print("VALIDAÇÃO DO MOMENTO DE ENTRADA E SAÍDA")
print("=" * 80)

validations = []
issues = []

for trade in engine.closed_trades:
    v = {}
    v['order_id'] = trade.order_id
    v['direction'] = trade.direction.name
    v['ob_id'] = trade.ob.ob_id
    v['ob_top'] = trade.ob.top
    v['ob_bottom'] = trade.ob.bottom
    v['ob_midline'] = trade.ob.midline
    v['ob_candle_idx'] = trade.ob.ob_candle_index
    v['ob_confirmation_idx'] = trade.ob.confirmation_index
    v['entry_price'] = trade.entry_price
    v['stop_loss'] = trade.stop_loss
    v['take_profit'] = trade.take_profit
    v['exit_price'] = trade.exit_price
    v['created_at'] = trade.created_at
    v['filled_at'] = trade.filled_at
    v['closed_at'] = trade.closed_at
    v['status'] = trade.status.value
    v['pnl'] = trade.profit_loss
    v['pnl_r'] = trade.profit_loss_r
    
    # ---- VALIDAÇÃO 1: Ordem criada APÓS confirmação do swing ----
    v['check_1_order_after_confirmation'] = trade.created_at >= trade.ob.confirmation_index
    if not v['check_1_order_after_confirmation']:
        issues.append(f"[LOOKAHEAD] {trade.order_id}: Ordem criada no candle {trade.created_at} mas OB confirmado no {trade.ob.confirmation_index}")
    
    # ---- VALIDAÇÃO 2: Entry delay respeitado ----
    v['check_2_entry_delay'] = trade.filled_at > trade.created_at
    if not v['check_2_entry_delay']:
        issues.append(f"[LOOKAHEAD] {trade.order_id}: Fill no candle {trade.filled_at} mas criado no {trade.created_at} (sem delay)")
    
    # ---- VALIDAÇÃO 3: Preço realmente tocou a entry no candle do fill ----
    fill_candle = candles[trade.filled_at]
    if trade.direction == SignalDirection.BULLISH:
        v['check_3_price_touched_entry'] = fill_candle['low'] <= trade.entry_price
        v['fill_candle_low'] = fill_candle['low']
        v['fill_candle_high'] = fill_candle['high']
    else:
        v['check_3_price_touched_entry'] = fill_candle['high'] >= trade.entry_price
        v['fill_candle_low'] = fill_candle['low']
        v['fill_candle_high'] = fill_candle['high']
    
    if not v['check_3_price_touched_entry']:
        issues.append(f"[ERRO] {trade.order_id}: Preço NÃO tocou entry {trade.entry_price} no candle {trade.filled_at} (L={fill_candle['low']}, H={fill_candle['high']})")
    
    # ---- VALIDAÇÃO 4: Candle do fill NÃO ultrapassou o OB inteiro ----
    if trade.direction == SignalDirection.BULLISH:
        v['check_4_ob_not_broken_on_fill'] = fill_candle['low'] > trade.ob.bottom
    else:
        v['check_4_ob_not_broken_on_fill'] = fill_candle['high'] < trade.ob.top
    
    if not v['check_4_ob_not_broken_on_fill']:
        issues.append(f"[WARN] {trade.order_id}: Candle do fill ultrapassou OB inteiro (deveria ter sido cancelado)")
    
    # ---- VALIDAÇÃO 5: TP/SL verificado a partir do candle SEGUINTE ao fill ----
    v['check_5_tp_sl_after_fill'] = trade.closed_at > trade.filled_at
    if not v['check_5_tp_sl_after_fill']:
        issues.append(f"[LOOKAHEAD] {trade.order_id}: TP/SL no candle {trade.closed_at} mas fill no {trade.filled_at} (mesmo candle!)")
    
    # ---- VALIDAÇÃO 6: Preço realmente atingiu TP ou SL no candle de saída ----
    close_candle = candles[trade.closed_at]
    if trade.status == OrderStatus.CLOSED_TP:
        if trade.direction == SignalDirection.BULLISH:
            v['check_6_exit_price_valid'] = close_candle['high'] >= trade.take_profit
        else:
            v['check_6_exit_price_valid'] = close_candle['low'] <= trade.take_profit
    else:  # CLOSED_SL
        if trade.direction == SignalDirection.BULLISH:
            v['check_6_exit_price_valid'] = close_candle['low'] <= trade.stop_loss
        else:
            v['check_6_exit_price_valid'] = close_candle['high'] >= trade.stop_loss
    
    v['close_candle_low'] = close_candle['low']
    v['close_candle_high'] = close_candle['high']
    
    if not v['check_6_exit_price_valid']:
        issues.append(f"[ERRO] {trade.order_id}: Preço NÃO atingiu {'TP' if trade.status == OrderStatus.CLOSED_TP else 'SL'} no candle {trade.closed_at}")
    
    # ---- VALIDAÇÃO 7: Projeção 3:1 correta ----
    risk = abs(trade.entry_price - trade.stop_loss)
    reward = abs(trade.take_profit - trade.entry_price)
    expected_rr = engine.risk_reward_ratio
    actual_rr = reward / risk if risk > 0 else 0
    v['risk_points'] = round(risk, 2)
    v['reward_points'] = round(reward, 2)
    v['actual_rr'] = round(actual_rr, 2)
    v['expected_rr'] = expected_rr
    v['check_7_rr_correct'] = abs(actual_rr - expected_rr) < 0.1
    
    if not v['check_7_rr_correct']:
        issues.append(f"[ERRO] {trade.order_id}: RR esperado {expected_rr}, obtido {actual_rr:.2f}")
    
    # ---- VALIDAÇÃO 8: SL primeiro (pior caso) ----
    # Verificar se no candle de saída, tanto TP quanto SL foram atingidos
    # Se sim, SL deve ter prioridade
    both_hit = False
    if trade.direction == SignalDirection.BULLISH:
        both_hit = close_candle['low'] <= trade.stop_loss and close_candle['high'] >= trade.take_profit
    else:
        both_hit = close_candle['high'] >= trade.stop_loss and close_candle['low'] <= trade.take_profit
    
    v['check_8_sl_priority'] = True
    if both_hit and trade.status == OrderStatus.CLOSED_TP:
        v['check_8_sl_priority'] = False
        issues.append(f"[WARN] {trade.order_id}: Ambos TP e SL atingidos no candle {trade.closed_at}, mas TP foi registrado (deveria ser SL)")
    
    # ---- VALIDAÇÃO 9: Sem lookahead - OB não usa dados futuros ----
    # O OB é baseado em candles ANTES do swing, e o swing é confirmado N candles depois
    v['check_9_no_lookahead'] = trade.ob.ob_candle_index < trade.ob.confirmation_index
    if not v['check_9_no_lookahead']:
        issues.append(f"[LOOKAHEAD] {trade.order_id}: OB candle {trade.ob.ob_candle_index} >= confirmation {trade.ob.confirmation_index}")
    
    # ---- VALIDAÇÃO 10: Verificar se entre fill e close, o SL/TP não foi atingido antes ----
    premature_exit = None
    for check_idx in range(trade.filled_at + 1, trade.closed_at):
        check_c = candles[check_idx]
        if trade.direction == SignalDirection.BULLISH:
            if check_c['low'] <= trade.stop_loss:
                premature_exit = ('SL', check_idx)
                break
            if check_c['high'] >= trade.take_profit:
                premature_exit = ('TP', check_idx)
                break
        else:
            if check_c['high'] >= trade.stop_loss:
                premature_exit = ('SL', check_idx)
                break
            if check_c['low'] <= trade.take_profit:
                premature_exit = ('TP', check_idx)
                break
    
    v['check_10_no_premature_exit'] = premature_exit is None
    if premature_exit:
        issues.append(f"[ERRO] {trade.order_id}: {premature_exit[0]} deveria ter sido atingido no candle {premature_exit[1]} mas trade fechou no {trade.closed_at}")
    
    validations.append(v)

# ============================================================
# 4. Imprimir relatório detalhado
# ============================================================
for v in validations:
    print(f"\n{'─' * 70}")
    print(f"  TRADE: {v['order_id']} | {v['direction']} | OB #{v['ob_id']}")
    print(f"{'─' * 70}")
    print(f"  OB Zone:      top={v['ob_top']:.2f}  bottom={v['ob_bottom']:.2f}  mid={v['ob_midline']:.2f}")
    print(f"  OB Candle:    #{v['ob_candle_idx']}  |  Confirmação: #{v['ob_confirmation_idx']}")
    print(f"  Ordem criada: #{v['created_at']}  |  Filled: #{v['filled_at']}  |  Closed: #{v['closed_at']}")
    print(f"  Entry: {v['entry_price']:.2f}  |  SL: {v['stop_loss']:.2f}  |  TP: {v['take_profit']:.2f}")
    print(f"  Exit:  {v['exit_price']:.2f}  |  Status: {v['status']}")
    print(f"  Risk:  {v['risk_points']} pts  |  Reward: {v['reward_points']} pts  |  RR: {v['actual_rr']}:1")
    print(f"  PnL:   {v['pnl']:.2f} pts  |  PnL(R): {v['pnl_r']:.2f}R")
    print()
    
    checks = [
        ('1. Ordem após confirmação', v['check_1_order_after_confirmation']),
        ('2. Entry delay respeitado', v['check_2_entry_delay']),
        ('3. Preço tocou entry no fill', v['check_3_price_touched_entry']),
        ('4. OB não quebrado no fill', v['check_4_ob_not_broken_on_fill']),
        ('5. TP/SL após candle do fill', v['check_5_tp_sl_after_fill']),
        ('6. Preço atingiu TP/SL na saída', v['check_6_exit_price_valid']),
        ('7. Projeção 3:1 correta', v['check_7_rr_correct']),
        ('8. SL tem prioridade (pior caso)', v['check_8_sl_priority']),
        ('9. Sem lookahead no OB', v['check_9_no_lookahead']),
        ('10. Sem saída prematura', v['check_10_no_premature_exit']),
    ]
    
    for name, passed in checks:
        icon = "✅" if passed else "❌"
        print(f"  {icon} {name}")

# Validação das ordens pendentes que NÃO foram preenchidas
print(f"\n{'═' * 80}")
print("ORDENS PENDENTES (não preenchidas)")
print(f"{'═' * 80}")

for order in engine.pending_orders:
    print(f"\n  Ordem: {order.order_id} | {order.direction.name}")
    print(f"  Entry: {order.entry_price:.2f} | SL: {order.stop_loss:.2f} | TP: {order.take_profit:.2f}")
    print(f"  Criada: #{order.created_at} | Max candle: #{order.max_candle}")
    print(f"  OB #{order.ob.ob_id}: top={order.ob.top:.2f} bottom={order.ob.bottom:.2f}")
    
    # Verificar se o preço chegou perto
    min_dist = float('inf')
    closest_candle = -1
    for ci in range(order.entry_delay_start, len(candles)):
        c = candles[ci]
        if order.direction == SignalDirection.BULLISH:
            dist = c['low'] - order.entry_price
        else:
            dist = order.entry_price - c['high']
        if dist < min_dist:
            min_dist = dist
            closest_candle = ci
    
    if min_dist <= 0:
        print(f"  ⚠️  Preço TOCOU entry no candle #{closest_candle} mas não foi preenchida (verificar filtros)")
    else:
        print(f"  ℹ️  Preço mais próximo: {min_dist:.2f} pts (candle #{closest_candle})")

# Resumo
print(f"\n{'═' * 80}")
print("RESUMO DA VALIDAÇÃO")
print(f"{'═' * 80}")

total_checks = len(validations) * 10
passed_checks = sum(
    sum([
        v['check_1_order_after_confirmation'],
        v['check_2_entry_delay'],
        v['check_3_price_touched_entry'],
        v['check_4_ob_not_broken_on_fill'],
        v['check_5_tp_sl_after_fill'],
        v['check_6_exit_price_valid'],
        v['check_7_rr_correct'],
        v['check_8_sl_priority'],
        v['check_9_no_lookahead'],
        v['check_10_no_premature_exit'],
    ])
    for v in validations
)

print(f"  Trades validados: {len(validations)}")
print(f"  Checks passados:  {passed_checks}/{total_checks}")
print(f"  Issues encontrados: {len(issues)}")

if issues:
    print(f"\n  PROBLEMAS:")
    for issue in issues:
        print(f"    {issue}")
else:
    print(f"\n  ✅ NENHUM PROBLEMA ENCONTRADO - Todas as entradas e saídas estão corretas!")

# ============================================================
# 5. Gerar visualização
# ============================================================
print(f"\n{'═' * 80}")
print("Gerando visualização...")
print(f"{'═' * 80}")

# Cores
BG_COLOR = '#0a0e17'
GRID_COLOR = '#1a2332'
TEXT_COLOR = '#e0e6ed'
GREEN = '#00d4aa'
RED = '#ff4757'
AMBER = '#ffa502'
BLUE = '#3498db'
PURPLE = '#9b59b6'

plt.style.use('dark_background')
plt.rcParams.update({
    'figure.facecolor': BG_COLOR,
    'axes.facecolor': BG_COLOR,
    'axes.edgecolor': GRID_COLOR,
    'axes.labelcolor': TEXT_COLOR,
    'xtick.color': TEXT_COLOR,
    'ytick.color': TEXT_COLOR,
    'text.color': TEXT_COLOR,
    'grid.color': GRID_COLOR,
    'font.family': 'monospace',
    'font.size': 8,
})

# Para cada trade, gerar um subplot mostrando a janela de candles relevante
n_trades = len(engine.closed_trades)
n_pending = min(3, len(engine.pending_orders))  # Mostrar até 3 pendentes
total_plots = n_trades + n_pending

if total_plots == 0:
    print("Nenhum trade para visualizar")
    sys.exit(0)

fig, axes = plt.subplots(total_plots, 1, figsize=(18, 6 * total_plots))
if total_plots == 1:
    axes = [axes]

for plot_idx, trade in enumerate(engine.closed_trades):
    ax = axes[plot_idx]
    
    # Janela: do OB candle até 5 candles após o close
    start = max(0, trade.ob.ob_candle_index - 3)
    end = min(len(candles), trade.closed_at + 5)
    window = range(start, end)
    
    # Desenhar candlestick
    for ci in window:
        c = candles[ci]
        color = GREEN if c['close'] >= c['open'] else RED
        body_bottom = min(c['open'], c['close'])
        body_top = max(c['open'], c['close'])
        body_height = body_top - body_bottom
        
        # Sombra
        ax.plot([ci, ci], [c['low'], c['high']], color=color, linewidth=0.8, alpha=0.6)
        # Corpo
        ax.bar(ci, body_height, bottom=body_bottom, width=0.6, color=color, alpha=0.8, edgecolor=color)
    
    # Zona do OB
    ob = trade.ob
    ax.axhspan(ob.bottom, ob.top, xmin=0, xmax=1, 
               alpha=0.15, color=GREEN if ob.direction == SignalDirection.BULLISH else RED,
               label=f'OB Zone ({ob.bottom:.0f}-{ob.top:.0f})')
    
    # Linhas de preço
    ax.axhline(y=trade.entry_price, color=BLUE, linestyle='--', linewidth=1.2, alpha=0.8, label=f'Entry: {trade.entry_price:.2f}')
    ax.axhline(y=trade.stop_loss, color=RED, linestyle=':', linewidth=1.0, alpha=0.7, label=f'SL: {trade.stop_loss:.2f}')
    ax.axhline(y=trade.take_profit, color=GREEN, linestyle=':', linewidth=1.0, alpha=0.7, label=f'TP: {trade.take_profit:.2f}')
    
    # Marcadores de eventos
    # OB Candle
    ax.annotate('OB', xy=(ob.ob_candle_index, candles[ob.ob_candle_index]['low']),
                xytext=(ob.ob_candle_index, candles[ob.ob_candle_index]['low'] - 15),
                fontsize=9, fontweight='bold', color=AMBER, ha='center',
                arrowprops=dict(arrowstyle='->', color=AMBER, lw=1.2))
    
    # Confirmação
    ax.axvline(x=ob.confirmation_index, color=AMBER, linestyle=':', linewidth=0.8, alpha=0.5)
    ax.annotate('CONF', xy=(ob.confirmation_index, ax.get_ylim()[1] if ax.get_ylim()[1] > 0 else candles[ob.confirmation_index]['high']),
                fontsize=7, color=AMBER, ha='center', va='bottom', rotation=90)
    
    # Ordem criada
    ax.axvline(x=trade.created_at, color=PURPLE, linestyle=':', linewidth=0.8, alpha=0.5)
    ax.annotate('ORDEM', xy=(trade.created_at, candles[trade.created_at]['high'] + 5),
                fontsize=7, color=PURPLE, ha='center', va='bottom')
    
    # Fill
    fill_c = candles[trade.filled_at]
    ax.annotate('FILL', xy=(trade.filled_at, trade.entry_price),
                xytext=(trade.filled_at + 1.5, trade.entry_price),
                fontsize=9, fontweight='bold', color=BLUE, ha='left',
                arrowprops=dict(arrowstyle='->', color=BLUE, lw=1.5))
    ax.plot(trade.filled_at, trade.entry_price, 'o', color=BLUE, markersize=8, zorder=5)
    
    # Close
    close_color = GREEN if trade.status == OrderStatus.CLOSED_TP else RED
    close_label = 'TP' if trade.status == OrderStatus.CLOSED_TP else 'SL'
    ax.annotate(close_label, xy=(trade.closed_at, trade.exit_price),
                xytext=(trade.closed_at + 1.5, trade.exit_price),
                fontsize=9, fontweight='bold', color=close_color, ha='left',
                arrowprops=dict(arrowstyle='->', color=close_color, lw=1.5))
    ax.plot(trade.closed_at, trade.exit_price, 's', color=close_color, markersize=8, zorder=5)
    
    # Título e info
    v = validations[plot_idx]
    all_passed = all([
        v['check_1_order_after_confirmation'], v['check_2_entry_delay'],
        v['check_3_price_touched_entry'], v['check_4_ob_not_broken_on_fill'],
        v['check_5_tp_sl_after_fill'], v['check_6_exit_price_valid'],
        v['check_7_rr_correct'], v['check_8_sl_priority'],
        v['check_9_no_lookahead'], v['check_10_no_premature_exit'],
    ])
    status_icon = "[OK]" if all_passed else "[FAIL]"
    
    ax.set_title(
        f'{status_icon} {trade.order_id} | {trade.direction.name} | '
        f'Entry #{trade.filled_at} → Exit #{trade.closed_at} ({close_label}) | '
        f'PnL: {trade.profit_loss:+.2f} pts ({trade.profit_loss_r:+.1f}R) | '
        f'RR: {v["actual_rr"]}:1',
        fontsize=11, fontweight='bold', pad=10
    )
    
    # Info box com timeline
    info_text = (
        f'OB Candle: #{ob.ob_candle_index}\n'
        f'Swing Conf: #{ob.confirmation_index}\n'
        f'Ordem Criada: #{trade.created_at}\n'
        f'Fill (toque): #{trade.filled_at}\n'
        f'Close (TP/SL): #{trade.closed_at}\n'
        f'Risk: {v["risk_points"]} pts\n'
        f'Reward: {v["reward_points"]} pts'
    )
    ax.text(0.02, 0.98, info_text, transform=ax.transAxes,
            fontsize=8, verticalalignment='top',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='#1a2332', alpha=0.9, edgecolor=GRID_COLOR))
    
    # Checks box
    checks_text = "VALIDAÇÕES:\n"
    check_items = [
        ('Após conf.', v['check_1_order_after_confirmation']),
        ('Delay', v['check_2_entry_delay']),
        ('Toque entry', v['check_3_price_touched_entry']),
        ('OB intacto', v['check_4_ob_not_broken_on_fill']),
        ('TP/SL pós-fill', v['check_5_tp_sl_after_fill']),
        ('Exit válido', v['check_6_exit_price_valid']),
        ('RR 3:1', v['check_7_rr_correct']),
        ('SL priority', v['check_8_sl_priority']),
        ('No lookahead', v['check_9_no_lookahead']),
        ('No premature', v['check_10_no_premature_exit']),
    ]
    for name, passed in check_items:
        icon = "[OK]" if passed else "[X]"
        checks_text += f"  {icon} {name}\n"
    
    ax.text(0.98, 0.98, checks_text, transform=ax.transAxes,
            fontsize=7, verticalalignment='top', horizontalalignment='right',
            fontfamily='monospace',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='#1a2332', alpha=0.9, edgecolor=GRID_COLOR))
    
    ax.set_xlabel('Candle Index')
    ax.set_ylabel('Preço')
    ax.legend(loc='lower left', fontsize=7, framealpha=0.8)
    ax.grid(True, alpha=0.2)

# Plotar ordens pendentes
for pi, order in enumerate(engine.pending_orders[:n_pending]):
    ax = axes[n_trades + pi]
    
    start = max(0, order.ob.ob_candle_index - 3)
    end = len(candles)
    window = range(start, end)
    
    for ci in window:
        c = candles[ci]
        color = GREEN if c['close'] >= c['open'] else RED
        body_bottom = min(c['open'], c['close'])
        body_top = max(c['open'], c['close'])
        body_height = body_top - body_bottom
        ax.plot([ci, ci], [c['low'], c['high']], color=color, linewidth=0.8, alpha=0.6)
        ax.bar(ci, body_height, bottom=body_bottom, width=0.6, color=color, alpha=0.8, edgecolor=color)
    
    ob = order.ob
    ax.axhspan(ob.bottom, ob.top, alpha=0.15, 
               color=GREEN if ob.direction == SignalDirection.BULLISH else RED)
    
    ax.axhline(y=order.entry_price, color=BLUE, linestyle='--', linewidth=1.2, alpha=0.8, label=f'Entry: {order.entry_price:.2f}')
    ax.axhline(y=order.stop_loss, color=RED, linestyle=':', linewidth=1.0, alpha=0.7, label=f'SL: {order.stop_loss:.2f}')
    ax.axhline(y=order.take_profit, color=GREEN, linestyle=':', linewidth=1.0, alpha=0.7, label=f'TP: {order.take_profit:.2f}')
    
    ax.set_title(
        f'[PENDING] {order.order_id} | {order.direction.name} | '
        f'Entry: {order.entry_price:.2f} | SL: {order.stop_loss:.2f} | TP: {order.take_profit:.2f} | '
        f'Criada: #{order.created_at} | Expira: #{order.max_candle}',
        fontsize=11, fontweight='bold', pad=10
    )
    
    ax.set_xlabel('Candle Index')
    ax.set_ylabel('Preço')
    ax.legend(loc='lower left', fontsize=7, framealpha=0.8)
    ax.grid(True, alpha=0.2)

plt.tight_layout()
plt.savefig('/home/ubuntu/validation_entry_exit.png', dpi=150, bbox_inches='tight',
            facecolor=BG_COLOR, edgecolor='none')
plt.close()

print(f"\n✅ Visualização salva em /home/ubuntu/validation_entry_exit.png")
print(f"   {total_plots} gráficos gerados ({n_trades} trades + {n_pending} pendentes)")
