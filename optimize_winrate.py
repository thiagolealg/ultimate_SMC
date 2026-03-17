"""
Otimização de Win Rate para 70%
================================
Análise dos fatores que influenciam o Win Rate e otimização dos parâmetros.
"""

import pandas as pd
import numpy as np
from smc_final import SMCFinal, OrderBlockStrategyFinal, SignalDirection, validate_ohlc, TradeSignal, BacktestResult
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass


def load_data():
    """Carrega dados"""
    df = pd.read_csv('/home/ubuntu/smc_enhanced/data.csv')
    df.columns = [c.lower() for c in df.columns]
    df['time'] = pd.to_datetime(df['time'])
    df.set_index('time', inplace=True)
    if 'volume' not in df.columns:
        df['volume'] = df.get('tick_volume', df.get('real_volume', 1.0))
    return df


def analyze_winning_trades():
    """
    Analisa as características dos trades vencedores vs perdedores
    para identificar filtros que aumentam o Win Rate.
    """
    print("=" * 70)
    print("ANÁLISE DE TRADES VENCEDORES vs PERDEDORES")
    print("=" * 70)
    
    df = load_data()
    df = df.tail(50000)  # Usar mais dados para análise
    
    strategy = OrderBlockStrategyFinal(
        df,
        swing_length=5,
        risk_reward_ratio=3.0,
        min_confidence=20.0,  # Baixa confiança para pegar todos
        entry_delay_candles=1,
    )
    
    signals = strategy.generate_signals()
    results, stats = strategy.backtest(signals)
    
    print(f"\nTotal de trades: {len(results)}")
    print(f"Win Rate atual: {stats['win_rate']:.1f}%")
    
    # Separar vencedores e perdedores
    winners = [r for r in results if r.hit_tp]
    losers = [r for r in results if r.hit_sl]
    
    print(f"Vencedores: {len(winners)}")
    print(f"Perdedores: {len(losers)}")
    
    # Analisar características
    print("\n" + "-" * 50)
    print("ANÁLISE DE CONFIANÇA")
    print("-" * 50)
    
    winner_conf = [r.signal.confidence for r in winners]
    loser_conf = [r.signal.confidence for r in losers]
    
    print(f"Confiança média vencedores: {np.mean(winner_conf):.1f}")
    print(f"Confiança média perdedores: {np.mean(loser_conf):.1f}")
    
    # Win rate por faixa de confiança
    print("\nWin Rate por faixa de confiança:")
    for min_conf in [20, 30, 40, 50, 60, 70, 80]:
        filtered_winners = [r for r in winners if r.signal.confidence >= min_conf]
        filtered_losers = [r for r in losers if r.signal.confidence >= min_conf]
        total = len(filtered_winners) + len(filtered_losers)
        if total > 0:
            wr = len(filtered_winners) / total * 100
            print(f"   Conf >= {min_conf}%: Win Rate = {wr:.1f}% ({total} trades)")
    
    # Analisar tamanho do OB
    print("\n" + "-" * 50)
    print("ANÁLISE DE TAMANHO DO OB")
    print("-" * 50)
    
    winner_sizes = [abs(r.signal.ob_top - r.signal.ob_bottom) for r in winners]
    loser_sizes = [abs(r.signal.ob_top - r.signal.ob_bottom) for r in losers]
    
    print(f"Tamanho médio OB vencedores: {np.mean(winner_sizes):.2f}")
    print(f"Tamanho médio OB perdedores: {np.mean(loser_sizes):.2f}")
    
    # Analisar direção
    print("\n" + "-" * 50)
    print("ANÁLISE POR DIREÇÃO")
    print("-" * 50)
    
    bull_winners = [r for r in winners if r.signal.direction == SignalDirection.BULLISH]
    bull_losers = [r for r in losers if r.signal.direction == SignalDirection.BULLISH]
    bear_winners = [r for r in winners if r.signal.direction == SignalDirection.BEARISH]
    bear_losers = [r for r in losers if r.signal.direction == SignalDirection.BEARISH]
    
    bull_total = len(bull_winners) + len(bull_losers)
    bear_total = len(bear_winners) + len(bear_losers)
    
    if bull_total > 0:
        print(f"Bullish: Win Rate = {len(bull_winners)/bull_total*100:.1f}% ({bull_total} trades)")
    if bear_total > 0:
        print(f"Bearish: Win Rate = {len(bear_winners)/bear_total*100:.1f}% ({bear_total} trades)")
    
    # Analisar duração
    print("\n" + "-" * 50)
    print("ANÁLISE DE DURAÇÃO")
    print("-" * 50)
    
    winner_duration = [r.duration_candles for r in winners]
    loser_duration = [r.duration_candles for r in losers]
    
    print(f"Duração média vencedores: {np.mean(winner_duration):.1f} candles")
    print(f"Duração média perdedores: {np.mean(loser_duration):.1f} candles")
    
    return results, strategy


def test_different_rr_ratios():
    """
    Testa diferentes ratios de Risk:Reward para encontrar o melhor Win Rate.
    """
    print("\n" + "=" * 70)
    print("TESTE DE DIFERENTES RISK:REWARD RATIOS")
    print("=" * 70)
    
    df = load_data()
    df = df.tail(50000)
    
    # Testar diferentes RR
    rr_ratios = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0]
    
    print("\nResultados por Risk:Reward:")
    print("-" * 50)
    
    best_wr = 0
    best_rr = 0
    
    for rr in rr_ratios:
        strategy = OrderBlockStrategyFinal(
            df,
            swing_length=5,
            risk_reward_ratio=rr,
            min_confidence=30.0,
            entry_delay_candles=1,
        )
        
        signals = strategy.generate_signals()
        results, stats = strategy.backtest(signals)
        
        wr = stats['win_rate']
        pf = stats['profit_factor']
        
        # Calcular expectativa
        if wr > 0:
            expectancy = (wr/100 * rr) - ((100-wr)/100 * 1)
        else:
            expectancy = 0
        
        print(f"   RR {rr:.1f}: Win Rate = {wr:.1f}%, PF = {pf:.2f}, Expectancy = {expectancy:.2f}R")
        
        if wr > best_wr:
            best_wr = wr
            best_rr = rr
    
    print(f"\nMelhor Win Rate: {best_wr:.1f}% com RR {best_rr}")
    
    return best_rr, best_wr


def test_trend_filter():
    """
    Testa filtro de tendência para aumentar Win Rate.
    """
    print("\n" + "=" * 70)
    print("TESTE DE FILTRO DE TENDÊNCIA")
    print("=" * 70)
    
    df = load_data()
    df = df.tail(50000)
    
    # Calcular médias móveis
    df['ema_20'] = df['close'].ewm(span=20).mean()
    df['ema_50'] = df['close'].ewm(span=50).mean()
    df['ema_200'] = df['close'].ewm(span=200).mean()
    
    strategy = OrderBlockStrategyFinal(
        df,
        swing_length=5,
        risk_reward_ratio=2.0,  # RR menor para maior WR
        min_confidence=30.0,
        entry_delay_candles=1,
    )
    
    signals = strategy.generate_signals()
    results, stats = strategy.backtest(signals)
    
    print(f"\nSem filtro de tendência:")
    print(f"   Win Rate: {stats['win_rate']:.1f}%")
    print(f"   Trades: {len(results)}")
    
    # Filtrar por tendência (EMA 20 > EMA 50)
    filtered_results_trend = []
    for r in results:
        idx = r.entry_index
        if idx < len(df):
            if r.signal.direction == SignalDirection.BULLISH:
                # Só long se EMA20 > EMA50
                if df['ema_20'].iloc[idx] > df['ema_50'].iloc[idx]:
                    filtered_results_trend.append(r)
            else:
                # Só short se EMA20 < EMA50
                if df['ema_20'].iloc[idx] < df['ema_50'].iloc[idx]:
                    filtered_results_trend.append(r)
    
    if len(filtered_results_trend) > 0:
        winners = sum(1 for r in filtered_results_trend if r.hit_tp)
        wr = winners / len(filtered_results_trend) * 100
        print(f"\nCom filtro EMA20 > EMA50:")
        print(f"   Win Rate: {wr:.1f}%")
        print(f"   Trades: {len(filtered_results_trend)}")
    
    # Filtrar por tendência forte (EMA 20 > EMA 50 > EMA 200)
    filtered_results_strong = []
    for r in results:
        idx = r.entry_index
        if idx < len(df):
            if r.signal.direction == SignalDirection.BULLISH:
                if df['ema_20'].iloc[idx] > df['ema_50'].iloc[idx] > df['ema_200'].iloc[idx]:
                    filtered_results_strong.append(r)
            else:
                if df['ema_20'].iloc[idx] < df['ema_50'].iloc[idx] < df['ema_200'].iloc[idx]:
                    filtered_results_strong.append(r)
    
    if len(filtered_results_strong) > 0:
        winners = sum(1 for r in filtered_results_strong if r.hit_tp)
        wr = winners / len(filtered_results_strong) * 100
        print(f"\nCom filtro EMA20 > EMA50 > EMA200:")
        print(f"   Win Rate: {wr:.1f}%")
        print(f"   Trades: {len(filtered_results_strong)}")


def test_ob_quality_filters():
    """
    Testa filtros de qualidade do Order Block.
    """
    print("\n" + "=" * 70)
    print("TESTE DE FILTROS DE QUALIDADE DO OB")
    print("=" * 70)
    
    df = load_data()
    df = df.tail(50000)
    
    strategy = OrderBlockStrategyFinal(
        df,
        swing_length=5,
        risk_reward_ratio=2.0,
        min_confidence=30.0,
        entry_delay_candles=1,
    )
    
    signals = strategy.generate_signals()
    results, stats = strategy.backtest(signals)
    
    print(f"\nBase (sem filtros adicionais):")
    print(f"   Win Rate: {stats['win_rate']:.1f}%")
    print(f"   Trades: {len(results)}")
    
    # Filtro 1: OB com FVG próximo
    ob_data = strategy.order_blocks
    fvg_data = strategy.fvg
    
    # Filtro 2: Apenas primeiro toque no OB
    # (já implementado na estratégia)
    
    # Filtro 3: OB não mitigado
    filtered_not_mitigated = []
    for r in results:
        signal_idx = r.signal.signal_candle_index
        mitigated = ob_data['MitigatedIndex'].iloc[signal_idx]
        if np.isnan(mitigated) or r.entry_index < mitigated:
            filtered_not_mitigated.append(r)
    
    if len(filtered_not_mitigated) > 0:
        winners = sum(1 for r in filtered_not_mitigated if r.hit_tp)
        wr = winners / len(filtered_not_mitigated) * 100
        print(f"\nFiltro: OB não mitigado antes da entrada:")
        print(f"   Win Rate: {wr:.1f}%")
        print(f"   Trades: {len(filtered_not_mitigated)}")


def optimize_for_70_winrate():
    """
    Otimização específica para atingir 70% de Win Rate.
    """
    print("\n" + "=" * 70)
    print("OTIMIZAÇÃO PARA 70% WIN RATE")
    print("=" * 70)
    
    df = load_data()
    df = df.tail(80000)  # Usar mais dados
    
    # Calcular indicadores adicionais
    df['ema_20'] = df['close'].ewm(span=20).mean()
    df['ema_50'] = df['close'].ewm(span=50).mean()
    df['atr'] = (df['high'] - df['low']).rolling(14).mean()
    
    best_config = None
    best_wr = 0
    best_trades = 0
    
    # Grid search de parâmetros
    configs = []
    
    for swing_len in [3, 5, 7]:
        for rr in [1.0, 1.5, 2.0]:
            for min_conf in [40, 50, 60, 70]:
                for use_trend in [True, False]:
                    configs.append({
                        'swing_length': swing_len,
                        'rr': rr,
                        'min_conf': min_conf,
                        'use_trend': use_trend,
                    })
    
    print(f"\nTestando {len(configs)} configurações...")
    
    results_list = []
    
    for config in configs:
        strategy = OrderBlockStrategyFinal(
            df,
            swing_length=config['swing_length'],
            risk_reward_ratio=config['rr'],
            min_confidence=config['min_conf'],
            entry_delay_candles=1,
        )
        
        signals = strategy.generate_signals()
        results, stats = strategy.backtest(signals)
        
        if config['use_trend'] and len(results) > 0:
            # Aplicar filtro de tendência
            filtered = []
            for r in results:
                idx = r.entry_index
                if idx < len(df):
                    if r.signal.direction == SignalDirection.BULLISH:
                        if df['ema_20'].iloc[idx] > df['ema_50'].iloc[idx]:
                            filtered.append(r)
                    else:
                        if df['ema_20'].iloc[idx] < df['ema_50'].iloc[idx]:
                            filtered.append(r)
            
            if len(filtered) > 0:
                winners = sum(1 for r in filtered if r.hit_tp)
                wr = winners / len(filtered) * 100
                trades = len(filtered)
            else:
                wr = 0
                trades = 0
        else:
            wr = stats['win_rate']
            trades = len(results)
        
        results_list.append({
            'config': config,
            'win_rate': wr,
            'trades': trades,
        })
        
        if wr >= 70 and trades > best_trades:
            best_config = config
            best_wr = wr
            best_trades = trades
    
    # Ordenar por Win Rate
    results_list.sort(key=lambda x: (-x['win_rate'], -x['trades']))
    
    print("\nTop 10 configurações:")
    print("-" * 70)
    for i, r in enumerate(results_list[:10]):
        c = r['config']
        print(f"{i+1}. WR={r['win_rate']:.1f}% | Trades={r['trades']} | "
              f"Swing={c['swing_length']} RR={c['rr']} Conf={c['min_conf']} Trend={c['use_trend']}")
    
    if best_config:
        print(f"\n✓ MELHOR CONFIGURAÇÃO COM WR >= 70%:")
        print(f"   Win Rate: {best_wr:.1f}%")
        print(f"   Trades: {best_trades}")
        print(f"   Parâmetros: {best_config}")
    else:
        print("\n⚠ Nenhuma configuração atingiu 70% Win Rate")
        print("   Configurações com maior Win Rate listadas acima")
    
    return results_list


if __name__ == "__main__":
    analyze_winning_trades()
    test_different_rr_ratios()
    test_trend_filter()
    test_ob_quality_filters()
    results = optimize_for_70_winrate()
