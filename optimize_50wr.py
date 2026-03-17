"""
Otimização para atingir ~50% Win Rate com mais trades.
Testa diferentes combinações de filtros no Engine V3.
Usa dados menores (113k candles) para iteração rápida.
"""
import sys
sys.path.insert(0, 'app')
import pandas as pd
import numpy as np
from smc_engine_v3 import SMCEngineV3, SignalDirection

# Carregar dados
df = pd.read_csv('/home/ubuntu/upload/mtwin14400.csv')
df.columns = [c.lower() for c in df.columns]
vol_col = 'tick_volume' if 'tick_volume' in df.columns else 'volume'
print(f"Dados: {len(df)} candles\n")

def run_engine(swing_length=5, rr=3.0, min_vol=1.5, min_size=0.5,
               max_pending=100, not_mitigated=True):
    engine = SMCEngineV3(
        symbol='WIN', swing_length=swing_length, risk_reward_ratio=rr,
        min_volume_ratio=min_vol, min_ob_size_atr=min_size,
        use_not_mitigated_filter=not_mitigated, max_pending_candles=max_pending,
        entry_delay_candles=1,
    )
    for i in range(len(df)):
        row = df.iloc[i]
        engine.add_candle({
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
            'volume': float(row[vol_col])
        })
    
    trades = engine.get_all_trades()
    wins = [t for t in trades if t['status'] == 'closed_tp']
    losses = [t for t in trades if t['status'] == 'closed_sl']
    total = len(wins) + len(losses)
    
    if total == 0:
        return {'trades': 0, 'wr': 0, 'profit': 0, 'pf': 0, 'exp': 0}
    
    wr = len(wins) / total * 100
    profit = sum(t['profit_loss'] for t in trades if t['status'] in ['closed_tp', 'closed_sl'])
    win_pts = sum(t['profit_loss'] for t in wins)
    loss_pts = sum(abs(t['profit_loss']) for t in losses)
    pf = win_pts / loss_pts if loss_pts > 0 else float('inf')
    win_r = len(wins) * rr
    loss_r = len(losses)
    lucro_r = win_r - loss_r
    exp = lucro_r / total
    
    return {
        'trades': total, 'wins': len(wins), 'losses': len(losses),
        'wr': wr, 'profit': profit, 'pf': pf, 'exp': exp,
        'lucro_r': lucro_r, 'win_pts': win_pts, 'loss_pts': loss_pts
    }

# =====================================================================
# TESTE 1: Variação de filtros de volume e tamanho
# =====================================================================
print("=" * 120)
print("TESTE 1: Variação de filtros de volume e tamanho (RR 3:1)")
print("=" * 120)
print(f"{'Vol':>6} {'Size':>6} {'Trades':>8} {'Wins':>6} {'Losses':>8} {'WR%':>8} {'PF':>8} {'Exp(R)':>8} {'Lucro(R)':>10} {'Lucro(pts)':>12}")
print("-" * 110)

configs = [
    # (min_vol, min_size)
    (0.0, 0.0),    # Sem filtros
    (0.5, 0.0),    # Volume baixo
    (1.0, 0.0),    # Volume médio
    (1.0, 0.3),    # Volume médio + tamanho baixo
    (1.0, 0.5),    # Volume médio + tamanho médio
    (1.2, 0.3),    # Volume médio-alto + tamanho baixo
    (1.2, 0.5),    # Volume médio-alto + tamanho médio
    (1.5, 0.3),    # Volume alto + tamanho baixo
    (1.5, 0.5),    # Volume alto + tamanho médio (atual)
    (2.0, 0.5),    # Volume muito alto + tamanho médio
    (1.5, 1.0),    # Volume alto + tamanho grande
]

for min_vol, min_size in configs:
    r = run_engine(min_vol=min_vol, min_size=min_size)
    print(f"{min_vol:>6.1f} {min_size:>6.1f} {r['trades']:>8} {r.get('wins',0):>6} {r.get('losses',0):>8} "
          f"{r['wr']:>7.1f}% {r['pf']:>8.2f} {r['exp']:>8.2f} {r.get('lucro_r',0):>10.0f} {r['profit']:>+12.2f}")

# =====================================================================
# TESTE 2: Variação de max_pending_candles
# =====================================================================
print(f"\n{'='*120}")
print("TESTE 2: Variação de max_pending_candles (RR 3:1, vol=1.0, size=0.3)")
print("=" * 120)
print(f"{'MaxPend':>8} {'Trades':>8} {'Wins':>6} {'Losses':>8} {'WR%':>8} {'PF':>8} {'Exp(R)':>8} {'Lucro(R)':>10} {'Lucro(pts)':>12}")
print("-" * 100)

for max_pend in [20, 30, 50, 75, 100, 150, 200]:
    r = run_engine(min_vol=1.0, min_size=0.3, max_pending=max_pend)
    print(f"{max_pend:>8} {r['trades']:>8} {r.get('wins',0):>6} {r.get('losses',0):>8} "
          f"{r['wr']:>7.1f}% {r['pf']:>8.2f} {r['exp']:>8.2f} {r.get('lucro_r',0):>10.0f} {r['profit']:>+12.2f}")

# =====================================================================
# TESTE 3: Variação de swing_length
# =====================================================================
print(f"\n{'='*120}")
print("TESTE 3: Variação de swing_length (RR 3:1, vol=1.0, size=0.3)")
print("=" * 120)
print(f"{'SwLen':>6} {'Trades':>8} {'Wins':>6} {'Losses':>8} {'WR%':>8} {'PF':>8} {'Exp(R)':>8} {'Lucro(R)':>10} {'Lucro(pts)':>12}")
print("-" * 100)

for sw in [3, 4, 5, 7, 10]:
    r = run_engine(swing_length=sw, min_vol=1.0, min_size=0.3)
    print(f"{sw:>6} {r['trades']:>8} {r.get('wins',0):>6} {r.get('losses',0):>8} "
          f"{r['wr']:>7.1f}% {r['pf']:>8.2f} {r['exp']:>8.2f} {r.get('lucro_r',0):>10.0f} {r['profit']:>+12.2f}")

# =====================================================================
# TESTE 4: Melhores combinações
# =====================================================================
print(f"\n{'='*120}")
print("TESTE 4: Top combinações para ~50% WR com mais trades")
print("=" * 120)
print(f"{'SwLen':>6} {'Vol':>6} {'Size':>6} {'MaxP':>6} {'Trades':>8} {'WR%':>8} {'PF':>8} {'Exp(R)':>8} {'Lucro(R)':>10} {'Lucro(pts)':>12}")
print("-" * 110)

combos = [
    (3, 1.0, 0.3, 50),
    (3, 1.0, 0.5, 50),
    (3, 1.2, 0.3, 50),
    (4, 1.0, 0.3, 50),
    (4, 1.0, 0.3, 75),
    (4, 1.2, 0.3, 50),
    (5, 1.0, 0.3, 50),
    (5, 1.0, 0.3, 75),
    (5, 1.2, 0.3, 75),
    (7, 1.0, 0.3, 50),
    (7, 1.0, 0.5, 50),
    (10, 0.5, 0.3, 50),
    (10, 1.0, 0.3, 50),
]

results = []
for sw, vol, size, maxp in combos:
    r = run_engine(swing_length=sw, min_vol=vol, min_size=size, max_pending=maxp)
    r['config'] = (sw, vol, size, maxp)
    results.append(r)
    print(f"{sw:>6} {vol:>6.1f} {size:>6.1f} {maxp:>6} {r['trades']:>8} "
          f"{r['wr']:>7.1f}% {r['pf']:>8.2f} {r['exp']:>8.2f} {r.get('lucro_r',0):>10.0f} {r['profit']:>+12.2f}")

# Melhor resultado por WR ~50%
print(f"\n{'='*120}")
print("RANKING: Melhores configs por proximidade a 50% WR + mais trades")
print("=" * 120)
# Score = trades * (1 - abs(wr - 50) / 50) * expectativa
for r in results:
    wr_score = 1 - abs(r['wr'] - 50) / 50
    r['score'] = r['trades'] * wr_score * max(r['exp'], 0)

results.sort(key=lambda x: x['score'], reverse=True)
print(f"{'#':>3} {'SwLen':>6} {'Vol':>6} {'Size':>6} {'MaxP':>6} {'Trades':>8} {'WR%':>8} {'Exp(R)':>8} {'Lucro(R)':>10} {'Score':>10}")
print("-" * 90)
for i, r in enumerate(results[:10]):
    sw, vol, size, maxp = r['config']
    print(f"{i+1:>3} {sw:>6} {vol:>6.1f} {size:>6.1f} {maxp:>6} {r['trades']:>8} "
          f"{r['wr']:>7.1f}% {r['exp']:>8.2f} {r.get('lucro_r',0):>10.0f} {r['score']:>10.1f}")
