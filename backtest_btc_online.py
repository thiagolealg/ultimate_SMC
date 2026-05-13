"""
Backtest Cego BTC Online
========================
Busca 500 candles de BTCUSDT 5min da Binance e roda o SMC Engine V3
candle a candle, sem lookahead. Resultado honesto.
"""
import requests
import json
import sys
sys.path.insert(0, '/tmp/ultimate_SMC')
from smc_engine_v3 import SMCEngineV3

def fetch_btc_candles(symbol="BTCUSDT", interval="5m", limit=500):
    """Busca candles da Binance"""
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    resp = requests.get(url)
    resp.raise_for_status()
    data = resp.json()
    
    candles = []
    for d in data:
        candles.append({
            'time': int(d[0]) // 1000,  # unix seconds
            'open': float(d[1]),
            'high': float(d[2]),
            'low': float(d[3]),
            'close': float(d[4]),
            'volume': float(d[5]),
        })
    return candles

def run_backtest():
    print("=" * 60)
    print("  SMC ENGINE V3 — BACKTEST CEGO BTC ONLINE")
    print("=" * 60)
    print()
    
    # Buscar dados
    print("[1/3] Buscando 500 candles BTCUSDT 5min da Binance...")
    candles = fetch_btc_candles()
    print(f"      ✅ {len(candles)} candles recebidos")
    print(f"      Período: {candles[0]['open']:.2f} → {candles[-1]['close']:.2f} USDT")
    print()
    
    # Inicializar engine para BTC
    print("[2/3] Rodando SMC Engine V3 candle a candle (sem lookahead)...")
    engine = SMCEngineV3(
        symbol="BTCUSDT",
        swing_length=5,
        risk_reward_ratio=3.0,
        use_not_mitigated_filter=True,
        max_pending_candles=150,
        entry_delay_candles=1,
        tick_size=0.01,  # BTC tick
    )
    
    # Processar candle a candle
    all_events = []
    for i, candle in enumerate(candles):
        events = engine.add_candle(candle)
        if events['closed_trades'] or events['filled_orders'] or events['new_signals']:
            all_events.append((i, events))
    
    print(f"      ✅ Processamento completo!")
    print()
    
    # Resultados
    print("[3/3] RESULTADOS:")
    print("-" * 60)
    
    stats = engine.get_stats()
    trades = engine.get_all_trades()
    
    print(f"  Candles processados:  {stats['candles_processed']}")
    print(f"  Order Blocks detectados: {stats['order_blocks_detected']}")
    print(f"  Ordens pendentes:     {stats['pending_orders']}")
    print(f"  Trades abertos:       {stats['open_trades']}")
    print()
    print(f"  📊 TRADES FECHADOS:   {stats['total_trades']}")
    print(f"     Wins:              {stats['winning_trades']}")
    print(f"     Losses:            {stats['losing_trades']}")
    print(f"     Win Rate:          {stats['win_rate']:.1f}%")
    print(f"     Profit Factor:     {stats['profit_factor']:.2f}")
    print(f"     Total (R):         {stats['total_profit_r']:.2f}R")
    print(f"     Avg por trade (R): {stats['avg_profit_r']:.2f}R")
    print()
    
    if trades:
        print("  📋 DETALHES DOS TRADES:")
        print("  " + "-" * 56)
        print(f"  {'#':<4} {'Dir':<8} {'Entry':<12} {'Exit':<12} {'P&L':<10} {'Status':<10} {'Dur'}")
        print("  " + "-" * 56)
        for i, t in enumerate(trades, 1):
            direction = "🟢 LONG" if t['direction'] == "BULLISH" else "🔴 SHORT"
            pnl_str = f"{t['profit_loss']:.2f}"
            status = "✅ TP" if "tp" in t['status'] else "❌ SL"
            dur = f"{t['duration_candles']}c"
            print(f"  {i:<4} {direction:<8} {t['entry_price']:<12.2f} {t['exit_price']:<12.2f} {pnl_str:<10} {status:<10} {dur}")
        print("  " + "-" * 56)
    else:
        print("  ⚠️  Nenhum trade fechado neste período.")
        print("     (Normal se o mercado não gerou setups suficientes em 500 candles de 5min)")
        if stats['pending_orders'] > 0:
            print(f"     Há {stats['pending_orders']} ordens pendentes aguardando fill.")
        if stats['open_trades'] > 0:
            print(f"     Há {stats['open_trades']} trades abertos aguardando TP/SL.")
    
    print()
    print("=" * 60)
    print("  FIM DO BACKTEST")
    print("=" * 60)
    
    return stats, trades

if __name__ == "__main__":
    stats, trades = run_backtest()
