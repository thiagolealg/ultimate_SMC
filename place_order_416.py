"""Script para colocar ordem pendente SMC_416 que falhou por Trade disabled"""
import MetaTrader5 as mt5

if not mt5.initialize():
    print(f"ERRO: {mt5.last_error()}")
    exit(1)

# Listar todos os simbolos WIN e verificar quais sao tradeaeis
all_syms = mt5.symbols_get()
win_syms = [s for s in all_syms if s.name.startswith("WIN")]

print("=== Simbolos WIN disponiveis ===")
for s in win_syms:
    tick = mt5.symbol_info_tick(s.name)
    bid = tick.bid if tick else 0
    ask = tick.ask if tick else 0
    trade_mode = s.trade_mode  # 0=disabled, 4=full
    print(f"  {s.name:<12} | trade_mode={trade_mode} | bid={bid:,.0f} | ask={ask:,.0f} | trade_calc_mode={s.trade_calc_mode}")

# Encontrar simbolo tradeable
tradeable_symbol = None
for s in win_syms:
    if s.trade_mode == 4:  # SYMBOL_TRADE_MODE_FULL
        tick = mt5.symbol_info_tick(s.name)
        if tick and tick.bid > 0:
            tradeable_symbol = s.name
            print(f"\n>>> Simbolo tradeable: {tradeable_symbol}")
            break

if not tradeable_symbol:
    # Tentar os contratos especificos
    for name in ["WINH26", "WING26", "WINJ26"]:
        info = mt5.symbol_info(name)
        if info and info.trade_mode > 0:
            mt5.symbol_select(name, True)
            tick = mt5.symbol_info_tick(name)
            if tick and tick.bid > 0:
                tradeable_symbol = name
                print(f"\n>>> Simbolo tradeable: {tradeable_symbol}")
                break

if not tradeable_symbol:
    print("\nERRO: Nenhum simbolo WIN tradeable encontrado!")
    mt5.shutdown()
    exit(1)

mt5.symbol_select(tradeable_symbol, True)
tick = mt5.symbol_info_tick(tradeable_symbol)
sym = mt5.symbol_info(tradeable_symbol)
print(f"\nSimbolo: {tradeable_symbol}")
print(f"Bid: {tick.bid:,.0f} | Ask: {tick.ask:,.0f}")
print(f"Stops level: {sym.trade_stops_level}")
print(f"Trade mode: {sym.trade_mode}")

# SMC_416: BEARISH | Entry=186690 | SL=186700 | TP=186660
entry = 186690.0
sl = 186700.0
tp = 186660.0

if entry > tick.bid:
    order_type = mt5.ORDER_TYPE_SELL_LIMIT
    type_name = "SELL_LIMIT"
else:
    order_type = mt5.ORDER_TYPE_SELL_STOP
    type_name = "SELL_STOP"

print(f"\nEntry={entry:,.0f} vs Bid={tick.bid:,.0f} -> {type_name}")

request = {
    "action": mt5.TRADE_ACTION_PENDING,
    "symbol": tradeable_symbol,
    "volume": 1.0,
    "type": order_type,
    "price": entry,
    "sl": sl,
    "tp": tp,
    "deviation": 20,
    "magic": 240201,
    "comment": "SMC_416",
    "type_time": mt5.ORDER_TIME_DAY,
    "type_filling": mt5.ORDER_FILLING_RETURN,
}

print(f"Enviando: {type_name} {tradeable_symbol} @ {entry:,.0f} SL={sl:,.0f} TP={tp:,.0f}")
result = mt5.order_send(request)
print(f"Resultado: retcode={result.retcode} comment={result.comment}")
if result.retcode == mt5.TRADE_RETCODE_DONE:
    print(f"SUCESSO! Ticket: {result.order}")
else:
    print(f"FALHA: {result.retcode} - {result.comment}")

mt5.shutdown()
