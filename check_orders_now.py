"""Verifica estado atual das ordens e posicoes no MT5"""
import MetaTrader5 as mt5

if not mt5.initialize():
    print(f"ERRO: {mt5.last_error()}")
    exit(1)

mt5.symbol_select("WING26", True)

# Ordens pendentes
orders = mt5.orders_get()
print("=== ORDENS PENDENTES NO MT5 ===")
if orders:
    bot_orders = [o for o in orders if o.magic == 240201]
    other_orders = [o for o in orders if o.magic != 240201]

    if bot_orders:
        print(f"  Bot (magic=240201): {len(bot_orders)} ordens")
        for o in bot_orders:
            type_names = {2: 'BUY_LIMIT', 3: 'SELL_LIMIT', 4: 'BUY_STOP', 5: 'SELL_STOP'}
            print(f"    #{o.ticket} | {type_names.get(o.type, o.type)} | "
                  f"Entry={o.price_open:,.0f} | SL={o.sl:,.0f} | TP={o.tp:,.0f} | "
                  f"Comment={o.comment}")
    else:
        print("  Bot (magic=240201): NENHUMA")

    if other_orders:
        print(f"  Outras: {len(other_orders)} ordens")
else:
    print("  NENHUMA ordem pendente")

# Posicoes abertas
positions = mt5.positions_get()
print("\n=== POSICOES ABERTAS NO MT5 ===")
if positions:
    for p in positions:
        print(f"  #{p.ticket} | {p.symbol} | {'BUY' if p.type==0 else 'SELL'} | "
              f"Entry={p.price_open:,.0f} | SL={p.sl:,.0f} | TP={p.tp:,.0f} | "
              f"P/L={p.profit:+,.2f} | Magic={p.magic}")
else:
    print("  NENHUMA posicao aberta")

# Historico de deals de hoje
from datetime import datetime
hoje_inicio = datetime(2026, 2, 10, 0, 0)
hoje_fim = datetime(2026, 2, 10, 23, 59)
deals = mt5.history_deals_get(hoje_inicio, hoje_fim)
print(f"\n=== DEALS DE HOJE ===")
if deals:
    bot_deals = [d for d in deals if d.magic == 240201]
    print(f"  Total deals: {len(deals)} | Bot: {len(bot_deals)}")
    for d in bot_deals:
        type_names = {0: 'BUY', 1: 'SELL'}
        entry_names = {0: 'IN', 1: 'OUT', 2: 'INOUT', 3: 'OUT_BY'}
        reason_names = {0: 'CLIENT', 3: 'SL', 4: 'TP', 5: 'SO'}
        print(f"    #{d.ticket} | {d.symbol} | {type_names.get(d.type, d.type)} | "
              f"{entry_names.get(d.entry, d.entry)} | "
              f"Price={d.price:,.0f} | Vol={d.volume} | "
              f"P/L={d.profit:+,.2f} | Reason={reason_names.get(d.reason, d.reason)} | "
              f"Comment={d.comment}")
else:
    print("  NENHUM deal hoje")

# Historico de ordens de hoje
orders_hist = mt5.history_orders_get(hoje_inicio, hoje_fim)
print(f"\n=== HISTORICO DE ORDENS HOJE ===")
if orders_hist:
    bot_hist = [o for o in orders_hist if o.magic == 240201]
    print(f"  Total: {len(orders_hist)} | Bot: {len(bot_hist)}")
    state_names = {0: 'STARTED', 1: 'PLACED', 2: 'CANCELED', 3: 'PARTIAL', 4: 'FILLED', 5: 'REJECTED'}
    type_names = {2: 'BUY_LIMIT', 3: 'SELL_LIMIT', 4: 'BUY_STOP', 5: 'SELL_STOP'}
    for o in bot_hist:
        print(f"    #{o.ticket} | {type_names.get(o.type, o.type)} | "
              f"Entry={o.price_open:,.0f} | State={state_names.get(o.state, o.state)} | "
              f"Comment={o.comment}")
else:
    print("  NENHUMA ordem no historico")

mt5.shutdown()
