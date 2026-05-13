"""
Generate Replay Data — BTC Online
==================================
Busca candles de BTCUSDT e roda o SMC Engine V3,
gerando um JSON completo para o dashboard replay visual.
"""
import requests
import json
import sys
sys.path.insert(0, '/tmp/ultimate_SMC')
from smc_engine_v3 import SMCEngineV3

def fetch_btc_candles(symbol="BTCUSDT", interval="5m", limit=500):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    resp = requests.get(url)
    resp.raise_for_status()
    data = resp.json()
    
    candles = []
    for d in data:
        candles.append({
            'time': int(d[0]) // 1000,
            'open': float(d[1]),
            'high': float(d[2]),
            'low': float(d[3]),
            'close': float(d[4]),
            'volume': float(d[5]),
        })
    return candles

def run():
    print("Buscando 500 candles BTCUSDT 5min...")
    candles = fetch_btc_candles()
    print(f"✅ {len(candles)} candles")

    engine = SMCEngineV3(
        symbol="BTCUSDT",
        swing_length=5,
        risk_reward_ratio=3.0,
        use_not_mitigated_filter=True,
        max_pending_candles=150,
        entry_delay_candles=1,
        tick_size=0.01,
    )

    for candle in candles:
        engine.add_candle(candle)

    # Formatar candles para o dashboard
    formatted_candles = []
    for c in candles:
        from datetime import datetime, timezone
        dt = datetime.fromtimestamp(c['time'], tz=timezone.utc)
        formatted_candles.append({
            'time': dt.strftime('%Y-%m-%d %H:%M:%S'),
            'open': c['open'],
            'high': c['high'],
            'low': c['low'],
            'close': c['close'],
            'volume': c['volume'],
        })

    # Trades
    trades = []
    for t in engine.closed_trades:
        trades.append({
            'id': t.order_id,
            'direction': 'bullish' if t.direction.name == 'BULLISH' else 'bearish',
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

    # Order Blocks
    order_blocks = []
    for ob in engine.active_obs:
        order_blocks.append({
            'id': ob.ob_id,
            'direction': 'bullish' if ob.direction.name == 'BULLISH' else 'bearish',
            'top': ob.top,
            'bottom': ob.bottom,
            'midline': ob.midline,
            'ob_candle_index': ob.ob_candle_index,
            'confirmation_index': ob.confirmation_index,
            'mitigated': ob.mitigated,
            'mitigated_index': ob.mitigated_index,
            'used': ob.used,
            'volume_ratio': ob.volume_ratio,
            'ob_size': ob.ob_size,
            'ob_size_atr': ob.ob_size_atr,
        })

    # Swing points
    swing_highs = [{'conf_idx': sh[0], 'candle_idx': sh[1], 'level': sh[2]} for sh in engine.swing_highs]
    swing_lows = [{'conf_idx': sl[0], 'candle_idx': sl[1], 'level': sl[2]} for sl in engine.swing_lows]

    # Pending orders
    pending_orders = []
    for po in engine.pending_orders:
        pending_orders.append({
            'id': po.order_id,
            'direction': 'bullish' if po.direction.name == 'BULLISH' else 'bearish',
            'entry_price': po.entry_price,
            'sl': po.stop_loss,
            'tp': po.take_profit,
            'ob_id': po.ob.ob_id,
            'created_at': po.created_at,
        })

    # Stats
    stats_raw = engine.get_stats()
    stats = {
        'total_trades': stats_raw['total_trades'],
        'wins': stats_raw['winning_trades'],
        'losses': stats_raw['losing_trades'],
        'win_rate': round(stats_raw['win_rate'], 1),
        'profit_factor': round(stats_raw['profit_factor'], 2),
        'risk_reward_ratio': 3.0,
        'total_pnl': sum(t.profit_loss for t in engine.closed_trades),
        'total_pnl_r': sum(t.profit_loss_r for t in engine.closed_trades),
        'avg_win': sum(t.profit_loss for t in engine.closed_trades if t.profit_loss > 0) / max(1, stats_raw['winning_trades']),
        'avg_loss': sum(t.profit_loss for t in engine.closed_trades if t.profit_loss < 0) / max(1, stats_raw['losing_trades']),
        'candles_processed': stats_raw['candles_processed'],
        'total_obs_in_memory': len(engine.active_obs),
        'active_obs': len([ob for ob in engine.active_obs if not ob.mitigated]),
        'mitigated_obs': len([ob for ob in engine.active_obs if ob.mitigated]),
        'memory_waste_pct': round(len([ob for ob in engine.active_obs if ob.mitigated]) / max(1, len(engine.active_obs)) * 100, 1),
    }

    engine_config = {
        'symbol': 'BTCUSDT',
        'timeframe': '5m',
        'swing_length': 5,
        'risk_reward_ratio': 3.0,
        'max_pending_candles': 150,
        'entry_delay_candles': 1,
        'use_not_mitigated_filter': True,
    }

    # OB accumulation (simplified)
    ob_accumulation = []
    running_pnl = 0
    for t in trades:
        running_pnl += t['pnl_r']
        ob_accumulation.append({
            'trade_num': len(ob_accumulation) + 1,
            'cumulative_r': round(running_pnl, 2),
        })

    result = {
        'candles': formatted_candles,
        'order_blocks': order_blocks,
        'swing_highs': swing_highs,
        'swing_lows': swing_lows,
        'trades': trades,
        'pending_orders': pending_orders,
        'ob_accumulation': ob_accumulation,
        'stats': stats,
        'engine_config': engine_config,
    }

    output_path = '/tmp/ultimate_SMC/dashboard/client/src/data/backtest-data.json'
    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)
    
    print(f"✅ JSON gerado: {output_path}")
    print(f"   {len(formatted_candles)} candles | {len(order_blocks)} OBs | {len(trades)} trades")
    print(f"   Win Rate: {stats['win_rate']}% | PF: {stats['profit_factor']} | Total: {stats['total_pnl_r']}R")

if __name__ == "__main__":
    run()
