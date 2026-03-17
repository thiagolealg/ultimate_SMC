"""
Teste final das melhores configurações para ~50% Win Rate.
Testa 3 configurações e mostra resultados detalhados.
"""
import sys
sys.path.insert(0, 'app')
import pandas as pd
import numpy as np
from smc_engine_v3 import SMCEngineV3

# Carregar dados
df = pd.read_csv('/home/ubuntu/upload/mtwin14400.csv')
df.columns = [c.lower() for c in df.columns]
vol_col = 'tick_volume' if 'tick_volume' in df.columns else 'volume'
print(f"Dados: {len(df)} candles\n")

def run_and_report(name, **kwargs):
    engine = SMCEngineV3(symbol='WIN', entry_delay_candles=1, 
                         use_not_mitigated_filter=True, **kwargs)
    for i in range(len(df)):
        row = df.iloc[i]
        engine.add_candle({
            'open': float(row['open']), 'high': float(row['high']),
            'low': float(row['low']), 'close': float(row['close']),
            'volume': float(row[vol_col])
        })
    
    trades = engine.get_all_trades()
    wins = [t for t in trades if t['status'] == 'closed_tp']
    losses = [t for t in trades if t['status'] == 'closed_sl']
    total = len(wins) + len(losses)
    
    if total == 0:
        print(f"\n{name}: 0 trades")
        return
    
    profit = sum(t['profit_loss'] for t in trades if t['status'] in ['closed_tp', 'closed_sl'])
    win_pts = sum(t['profit_loss'] for t in wins)
    loss_pts = sum(abs(t['profit_loss']) for t in losses)
    pf = win_pts / loss_pts if loss_pts > 0 else float('inf')
    rr = kwargs.get('risk_reward_ratio', 3.0)
    lucro_r = len(wins) * rr - len(losses)
    exp = lucro_r / total
    
    # Validação
    invalid_touch = 0
    for t in trades:
        h = df['high'].iloc[t['filled_at']]
        l = df['low'].iloc[t['filled_at']]
        if t['direction'] == 'BULLISH':
            if l > t['entry_price']:
                invalid_touch += 1
        else:
            if h < t['entry_price']:
                invalid_touch += 1
    
    temporal = sum(1 for t in trades if t['filled_at'] <= t['created_at'])
    same_candle = sum(1 for t in trades if t['filled_at'] == t['created_at'])
    
    mit_before = 0
    for t in engine.closed_trades:
        if t.ob.mitigated and t.ob.mitigated_index < t.filled_at:
            mit_before += 1
    
    print(f"\n{'='*80}")
    print(f"  {name}")
    print(f"{'='*80}")
    print(f"  Trades: {total} | Wins: {len(wins)} | Losses: {len(losses)}")
    print(f"  Win Rate: {len(wins)/total*100:.1f}%")
    print(f"  Profit Factor: {pf:.2f}")
    print(f"  Lucro: {profit:+,.2f} pontos | {lucro_r:.0f}R")
    print(f"  Expectativa: {exp:.2f}R/trade")
    print(f"  Trades/mês: ~{total/10:.0f}")
    print(f"  Validação: Toques={invalid_touch} | Temporal={temporal} | SameCandle={same_candle} | Mitigados={mit_before}")
    all_ok = invalid_touch == 0 and temporal == 0 and same_candle == 0 and mit_before == 0
    print(f"  Status: {'✅ TODOS OS TESTES PASSARAM' if all_ok else '❌ FALHAS'}")
    
    return {'trades': total, 'wr': len(wins)/total*100, 'profit': profit, 'lucro_r': lucro_r, 'exp': exp, 'pf': pf}

# Config 1: Sem filtros de volume/tamanho, max_pending=150
print("CONFIG 1: Sem filtros vol/size, max_pending=150")
r1 = run_and_report("SEM FILTROS (vol=0, size=0, maxP=150)",
    swing_length=5, risk_reward_ratio=3.0,
    min_volume_ratio=0.0, min_ob_size_atr=0.0, max_pending_candles=150)

# Config 2: Filtros leves
print("\nCONFIG 2: Filtros leves (vol=1.0, size=0.3, maxP=75)")
r2 = run_and_report("FILTROS LEVES (vol=1.0, size=0.3, maxP=75)",
    swing_length=5, risk_reward_ratio=3.0,
    min_volume_ratio=1.0, min_ob_size_atr=0.3, max_pending_candles=75)

# Config 3: Filtros médios
print("\nCONFIG 3: Filtros médios (vol=1.2, size=0.3, maxP=75)")
r3 = run_and_report("FILTROS MÉDIOS (vol=1.2, size=0.3, maxP=75)",
    swing_length=5, risk_reward_ratio=3.0,
    min_volume_ratio=1.2, min_ob_size_atr=0.3, max_pending_candles=75)

# Config 4: Sem filtros, swing=7
print("\nCONFIG 4: Sem filtros, swing=7")
r4 = run_and_report("SEM FILTROS, SWING=7 (maxP=150)",
    swing_length=7, risk_reward_ratio=3.0,
    min_volume_ratio=0.0, min_ob_size_atr=0.0, max_pending_candles=150)

# Comparação final
print(f"\n{'='*100}")
print(f"COMPARAÇÃO FINAL")
print(f"{'='*100}")
print(f"{'Config':>40} {'Trades':>8} {'WR%':>8} {'PF':>8} {'Exp(R)':>8} {'Lucro(R)':>10} {'Lucro(pts)':>12}")
print("-" * 100)
for name, r in [("Sem filtros maxP=150", r1), ("Filtros leves", r2), 
                ("Filtros médios", r3), ("Sem filtros swing=7", r4)]:
    if r:
        print(f"{name:>40} {r['trades']:>8} {r['wr']:>7.1f}% {r['pf']:>8.2f} {r['exp']:>8.2f} {r['lucro_r']:>10.0f} {r['profit']:>+12.2f}")
