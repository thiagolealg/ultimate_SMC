"""Verificar ordem pendente SMC_415 no MT5"""
import MetaTrader5 as mt5

if not mt5.initialize():
    print(f"ERRO: {mt5.last_error()}")
    exit(1)

# Verificar ordens pendentes
orders = mt5.orders_get()
print("=== ORDENS PENDENTES ===")
if orders:
    for o in orders:
        print(f"  Ticket: {o.ticket}")
        print(f"  Symbol: {o.symbol}")
        print(f"  Type: {o.type} ({'BUY_LIMIT' if o.type==2 else 'SELL_LIMIT' if o.type==3 else 'BUY_STOP' if o.type==4 else 'SELL_STOP' if o.type==5 else o.type})")
        print(f"  Price (entry): {o.price_open:,.0f}")
        print(f"  SL: {o.sl:,.0f}")
        print(f"  TP: {o.tp:,.0f}")
        print(f"  Volume: {o.volume_current}")
        print(f"  Magic: {o.magic}")
        print(f"  Comment: {o.comment}")
        print()
else:
    print("  Nenhuma ordem pendente encontrada")

# Verificar tick atual
mt5.symbol_select("WING26", True)
tick = mt5.symbol_info_tick("WING26")
if tick:
    print(f"=== PRECO ATUAL WING26 ===")
    print(f"  Bid: {tick.bid:,.0f}")
    print(f"  Ask: {tick.ask:,.0f}")
    print(f"  Last: {tick.last:,.0f}")

# Verificar historico de precos dos ultimos 30 min
rates = mt5.copy_rates_from_pos("WING26", mt5.TIMEFRAME_M1, 0, 30)
if rates is not None and len(rates) > 0:
    print(f"\n=== ULTIMOS 30 CANDLES M1 ===")
    max_high = 0
    for r in rates:
        from datetime import datetime
        t = datetime.utcfromtimestamp(r['time']).strftime('%H:%M')
        high = r['high']
        low = r['low']
        if high > max_high:
            max_high = high
        print(f"  {t} | H={high:,.0f} L={low:,.0f} C={r['close']:,.0f}")

    print(f"\n  Max High ultimos 30min: {max_high:,.0f}")
    print(f"  Entry da ordem: 186,690")
    if max_high >= 186690:
        print(f"  >>> PRECO JA TOCOU O ENTRY! Ordem deveria ter sido preenchida.")
    else:
        print(f"  >>> Preco NAO atingiu o entry ainda. Diferenca: {186690 - max_high:,.0f} pts")

# Verificar posicoes abertas
positions = mt5.positions_get()
print(f"\n=== POSICOES ABERTAS ===")
if positions:
    for p in positions:
        print(f"  Ticket: {p.ticket} | {p.symbol} | {'BUY' if p.type==0 else 'SELL'} | "
              f"Entry={p.price_open:,.0f} | SL={p.sl:,.0f} | TP={p.tp:,.0f} | P/L={p.profit:+,.2f}")
else:
    print("  Nenhuma posicao aberta")

mt5.shutdown()
