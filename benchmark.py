"""
Benchmark de Performance do SMC Engine
======================================
Mede o tempo de processamento por candle e identifica gargalos.
"""

import sys
import time
import statistics
sys.path.insert(0, 'app')

import pandas as pd
from smc_engine import SMCEngine

def load_data():
    """Carrega dados reais"""
    # Tentar diferentes caminhos
    for path in ['/home/ubuntu/upload/mtwin14400.csv', '/home/ubuntu/smc_enhanced/data.csv']:
        try:
            df = pd.read_csv(path)
            df.columns = [c.lower() for c in df.columns]
            print(f"Dados carregados: {path} ({len(df)} candles)")
            return df
        except:
            continue
    
    # Gerar dados sintéticos se não encontrar
    import numpy as np
    print("Gerando dados sintéticos para benchmark...")
    n = 50000
    np.random.seed(42)
    prices = 100000 + np.cumsum(np.random.randn(n) * 50)
    df = pd.DataFrame({
        'time': pd.date_range('2020-01-01', periods=n, freq='1min'),
        'open': prices,
        'high': prices + np.abs(np.random.randn(n) * 30),
        'low': prices - np.abs(np.random.randn(n) * 30),
        'close': prices + np.random.randn(n) * 20,
        'tick_volume': np.random.randint(100, 5000, n).astype(float)
    })
    return df


def benchmark_current_engine():
    """Benchmark do engine atual"""
    df = load_data()
    
    engine = SMCEngine(
        symbol='WINM24',
        swing_length=5,
        risk_reward_ratio=3.0,
        min_volume_ratio=1.5,
        min_ob_size_atr=0.5,
        use_not_mitigated_filter=True
    )
    
    vol_col = 'tick_volume' if 'tick_volume' in df.columns else 'volume'
    
    # Warmup (primeiros 100 candles)
    print("\n=== WARMUP (100 candles) ===")
    warmup_times = []
    for i in range(min(100, len(df))):
        row = df.iloc[i]
        candle = {
            'time': str(row.get('time', '')),
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
            'volume': float(row[vol_col])
        }
        t0 = time.perf_counter_ns()
        engine.add_candle(candle)
        t1 = time.perf_counter_ns()
        warmup_times.append((t1 - t0) / 1_000_000)  # ms
    
    print(f"Warmup média: {statistics.mean(warmup_times):.4f} ms")
    
    # Benchmark principal (1000 candles)
    print("\n=== BENCHMARK PRINCIPAL (1000 candles) ===")
    times = []
    signal_count = 0
    
    start_idx = 100
    end_idx = min(1100, len(df))
    
    for i in range(start_idx, end_idx):
        row = df.iloc[i]
        candle = {
            'time': str(row.get('time', '')),
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
            'volume': float(row[vol_col])
        }
        t0 = time.perf_counter_ns()
        signals = engine.add_candle(candle)
        t1 = time.perf_counter_ns()
        
        elapsed_ms = (t1 - t0) / 1_000_000
        times.append(elapsed_ms)
        signal_count += len(signals)
    
    # Estatísticas
    print(f"Candles processados: {len(times)}")
    print(f"Sinais gerados: {signal_count}")
    print(f"")
    print(f"Tempo por candle:")
    print(f"  Média:   {statistics.mean(times):.4f} ms")
    print(f"  Mediana: {statistics.median(times):.4f} ms")
    print(f"  Min:     {min(times):.4f} ms")
    print(f"  Max:     {max(times):.4f} ms")
    print(f"  P95:     {sorted(times)[int(len(times)*0.95)]:.4f} ms")
    print(f"  P99:     {sorted(times)[int(len(times)*0.99)]:.4f} ms")
    print(f"  Desvio:  {statistics.stdev(times):.4f} ms")
    
    target = 1.0  # ms
    under_target = sum(1 for t in times if t < target)
    print(f"\n  < {target}ms: {under_target}/{len(times)} ({under_target/len(times)*100:.1f}%)")
    
    # Benchmark com muitos candles (5000)
    print("\n=== BENCHMARK LONGO (5000 candles) ===")
    long_times = []
    end_idx2 = min(6100, len(df))
    
    for i in range(1100, end_idx2):
        row = df.iloc[i]
        candle = {
            'time': str(row.get('time', '')),
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
            'volume': float(row[vol_col])
        }
        t0 = time.perf_counter_ns()
        engine.add_candle(candle)
        t1 = time.perf_counter_ns()
        
        long_times.append((t1 - t0) / 1_000_000)
    
    print(f"Candles processados: {len(long_times)}")
    print(f"Total OBs: {len(engine.order_blocks)}")
    print(f"Total ordens fechadas: {len(engine.closed_orders)}")
    print(f"")
    print(f"Tempo por candle:")
    print(f"  Média:   {statistics.mean(long_times):.4f} ms")
    print(f"  Mediana: {statistics.median(long_times):.4f} ms")
    print(f"  P95:     {sorted(long_times)[int(len(long_times)*0.95)]:.4f} ms")
    print(f"  P99:     {sorted(long_times)[int(len(long_times)*0.99)]:.4f} ms")
    
    under_target = sum(1 for t in long_times if t < target)
    print(f"\n  < {target}ms: {under_target}/{len(long_times)} ({under_target/len(long_times)*100:.1f}%)")
    
    # Profiling por função
    print("\n=== PROFILING POR FUNÇÃO ===")
    profile_engine = SMCEngine(symbol='PROFILE', swing_length=5, risk_reward_ratio=3.0)
    
    # Carregar 200 candles primeiro
    for i in range(200):
        row = df.iloc[i]
        profile_engine.add_candle({
            'time': str(row.get('time', '')),
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
            'volume': float(row[vol_col])
        })
    
    # Medir cada função individualmente
    row = df.iloc[200]
    candle = {
        'time': str(row.get('time', '')),
        'open': float(row['open']),
        'high': float(row['high']),
        'low': float(row['low']),
        'close': float(row['close']),
        'volume': float(row[vol_col]),
        'index': profile_engine.candle_count
    }
    
    # _update_indicators
    profile_engine.candles.append(candle)
    profile_engine.candle_count += 1
    
    times_indicators = []
    for _ in range(1000):
        t0 = time.perf_counter_ns()
        profile_engine._update_indicators()
        t1 = time.perf_counter_ns()
        times_indicators.append((t1 - t0) / 1_000_000)
    
    times_patterns = []
    for _ in range(1000):
        t0 = time.perf_counter_ns()
        profile_engine._detect_patterns()
        t1 = time.perf_counter_ns()
        times_patterns.append((t1 - t0) / 1_000_000)
    
    times_pending = []
    for _ in range(1000):
        t0 = time.perf_counter_ns()
        profile_engine._check_pending_orders(candle)
        t1 = time.perf_counter_ns()
        times_pending.append((t1 - t0) / 1_000_000)
    
    times_filled = []
    for _ in range(1000):
        t0 = time.perf_counter_ns()
        profile_engine._check_filled_orders(candle)
        t1 = time.perf_counter_ns()
        times_filled.append((t1 - t0) / 1_000_000)
    
    times_signals = []
    for _ in range(1000):
        t0 = time.perf_counter_ns()
        profile_engine._generate_signals(candle)
        t1 = time.perf_counter_ns()
        times_signals.append((t1 - t0) / 1_000_000)
    
    print(f"  _update_indicators:   {statistics.mean(times_indicators):.4f} ms (média)")
    print(f"  _detect_patterns:     {statistics.mean(times_patterns):.4f} ms (média)")
    print(f"  _check_pending_orders:{statistics.mean(times_pending):.4f} ms (média)")
    print(f"  _check_filled_orders: {statistics.mean(times_filled):.4f} ms (média)")
    print(f"  _generate_signals:    {statistics.mean(times_signals):.4f} ms (média)")
    
    total_funcs = (statistics.mean(times_indicators) + statistics.mean(times_patterns) +
                   statistics.mean(times_pending) + statistics.mean(times_filled) +
                   statistics.mean(times_signals))
    print(f"  TOTAL FUNÇÕES:        {total_funcs:.4f} ms")
    
    # Identificar gargalos
    print("\n=== GARGALOS IDENTIFICADOS ===")
    funcs = {
        '_update_indicators': statistics.mean(times_indicators),
        '_detect_patterns': statistics.mean(times_patterns),
        '_check_pending_orders': statistics.mean(times_pending),
        '_check_filled_orders': statistics.mean(times_filled),
        '_generate_signals': statistics.mean(times_signals)
    }
    
    sorted_funcs = sorted(funcs.items(), key=lambda x: x[1], reverse=True)
    for name, t in sorted_funcs:
        pct = (t / total_funcs * 100) if total_funcs > 0 else 0
        bar = "█" * int(pct / 2)
        print(f"  {name:30s} {t:.4f} ms ({pct:.1f}%) {bar}")


if __name__ == "__main__":
    benchmark_current_engine()
