"""Cancelar todas ordens orfas do bot no MT5"""
import MetaTrader5 as mt5
import time

if not mt5.initialize():
    print(f"ERRO: {mt5.last_error()}")
    exit(1)

mt5.symbol_select("WING26", True)

orders = mt5.orders_get()
if not orders:
    print("Nenhuma ordem pendente")
    mt5.shutdown()
    exit(0)

bot_orders = [o for o in orders if o.magic == 240201]
print(f"Encontradas {len(bot_orders)} ordens do bot (magic=240201)")

for o in bot_orders:
    type_names = {2: 'BUY_LIMIT', 3: 'SELL_LIMIT', 4: 'BUY_STOP', 5: 'SELL_STOP'}
    print(f"\n  Cancelando #{o.ticket} | {type_names.get(o.type, o.type)} @ {o.price_open:,.0f} | {o.comment}")

    for attempt in range(3):
        request = {"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket}
        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            print(f"    OK! Cancelada com sucesso (tentativa {attempt+1})")
            break
        else:
            code = result.retcode if result else "None"
            comment = result.comment if result else "None"
            print(f"    Tentativa {attempt+1} falhou: retcode={code} {comment}")
            time.sleep(1)
    else:
        print(f"    FALHA apos 3 tentativas!")

# Verificar resultado
time.sleep(1)
remaining = mt5.orders_get()
bot_remaining = [o for o in remaining if o.magic == 240201] if remaining else []
print(f"\nOrdens restantes do bot: {len(bot_remaining)}")
for o in bot_remaining:
    print(f"  #{o.ticket} @ {o.price_open:,.0f} | {o.comment}")

mt5.shutdown()
