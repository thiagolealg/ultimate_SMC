import sys, json
sys.path.insert(0, '.')
import pandas as pd
from smc_engine_v3 import SMCEngineV3, SignalDirection

df = pd.read_csv('mtwin14400.csv')
df.columns = [c.lower() for c in df.columns]
vol_col = 'tick_volume' if 'tick_volume' in df.columns else 'volume'

engine = SMCEngineV3(
    symbol='WINM24', swing_length=5, risk_reward_ratio=3.0,
    min_volume_ratio=0.0, min_ob_size_atr=0.0,
    use_not_mitigated_filter=True, max_pending_candles=150,
    entry_delay_candles=1,
)

ob_accumulation = []
for i in range(len(df)):
    row = df.iloc[i]
    engine.add_candle({
        'open': float(row['open']),
        'high': float(row['high']),
        'low': float(row['low']),
        'close': float(row['close']),
        'volume': float(row[vol_col])
    })
    total = len(engine.active_obs)
    active = sum(1 for ob in engine.active_obs if not ob.mitigated)
    mitigated = sum(1 for ob in engine.active_obs if ob.mitigated)
    ob_accumulation.append({'candle': i, 'total': total, 'active': active, 'mitigated': mitigated})

candles = []
for i in range(len(df)):
    row = df.iloc[i]
    candles.append({
        'time': row['time'],
        'open': float(row['open']),
        'high': float(row['high']),
        'low': float(row['low']),
        'close': float(row['close']),
        'volume': float(row[vol_col])
    })

obs = []
for ob in engine.active_obs:
    obs.append({
        'id': ob.ob_id,
        'direction': 'bullish' if ob.direction == SignalDirection.BULLISH else 'bearish',
        'top': ob.top,
        'bottom': ob.bottom,
        'midline': ob.midline,
        'ob_candle_index': ob.ob_candle_index,
        'confirmation_index': ob.confirmation_index,
        'mitigated': ob.mitigated,
        'mitigated_index': ob.mitigated_index if ob.mitigated else None,
        'used': ob.used,
        'volume_ratio': round(ob.volume_ratio, 2),
        'ob_size': round(ob.ob_size, 2),
        'ob_size_atr': round(ob.ob_size_atr, 2),
    })

swing_highs = [{'conf_idx': s[0], 'candle_idx': s[1], 'level': s[2]} for s in engine.swing_highs]
swing_lows = [{'conf_idx': s[0], 'candle_idx': s[1], 'level': s[2]} for s in engine.swing_lows]

trades = []
for t in engine.closed_trades:
    trades.append({
        'id': t.order_id,
        'direction': 'bullish' if t.direction == SignalDirection.BULLISH else 'bearish',
        'entry_price': t.entry_price,
        'exit_price': t.exit_price,
        'sl': t.stop_loss,
        'tp': t.take_profit,
        'pnl': t.profit_loss,
        'pnl_r': t.profit_loss_r,
        'status': t.status.value,
        'filled_at': t.filled_at,
        'closed_at': t.closed_at,
        'ob_id': t.ob.ob_id,
        'patterns': [p.value for p in t.patterns],
        'confidence': t.confidence,
    })

pending = []
for o in engine.pending_orders:
    pending.append({
        'id': o.order_id,
        'direction': 'bullish' if o.direction == SignalDirection.BULLISH else 'bearish',
        'entry_price': o.entry_price,
        'sl': o.stop_loss,
        'tp': o.take_profit,
        'ob_id': o.ob.ob_id,
        'created_at': o.created_at,
    })

stats = engine.get_stats()

# Calculate extra metrics
total_wins = stats['winning_trades']
total_losses = stats['losing_trades']
total_trades = stats['total_trades']
win_points = stats.get('total_win_points', 0)
loss_points = stats.get('total_loss_points', 0)

data = {
    'candles': candles,
    'order_blocks': obs,
    'swing_highs': swing_highs,
    'swing_lows': swing_lows,
    'trades': trades,
    'pending_orders': pending,
    'ob_accumulation': ob_accumulation,
    'stats': {
        'total_trades': total_trades,
        'wins': total_wins,
        'losses': total_losses,
        'win_rate': round(stats['win_rate'], 1),
        'profit_factor': round(stats['profit_factor'], 2) if stats['profit_factor'] != float('inf') else 999.0,
        'total_pnl': round(stats['total_profit_points'], 2),
        'total_pnl_r': round(stats['total_profit_r'], 2),
        'avg_pnl_r': round(stats['avg_profit_r'], 2),
        'total_win_points': round(win_points, 2),
        'total_loss_points': round(loss_points, 2),
        'avg_win': round(win_points / max(1, total_wins), 2),
        'avg_loss': round(loss_points / max(1, total_losses), 2),
        'expectancy_r': round(stats['avg_profit_r'], 2),
        'risk_reward_ratio': 3.0,
        'order_blocks_detected': stats['order_blocks_detected'],
        'active_obs': sum(1 for ob in engine.active_obs if not ob.mitigated),
        'mitigated_obs': sum(1 for ob in engine.active_obs if ob.mitigated),
        'pending_orders_count': len(engine.pending_orders),
        'ob_counter': engine._ob_counter,
        'total_obs_in_memory': len(engine.active_obs),
        'memory_waste_pct': round(sum(1 for ob in engine.active_obs if ob.mitigated) / max(1, len(engine.active_obs)) * 100, 1),
        'candles_processed': stats['candles_processed'],
    },
    'engine_config': {
        'symbol': 'WINM24',
        'swing_length': 5,
        'risk_reward_ratio': 3.0,
        'min_volume_ratio': 0.0,
        'min_ob_size_atr': 0.0,
        'use_not_mitigated_filter': True,
        'max_pending_candles': 150,
        'entry_delay_candles': 1,
    }
}

with open('/home/ubuntu/smc-dashboard/client/src/data/backtest-data.json', 'w') as f:
    json.dump(data, f, indent=2, default=str)

print('OK')
print(f'Candles: {len(candles)}, OBs: {len(obs)}, Trades: {len(trades)}, Pending: {len(pending)}')
