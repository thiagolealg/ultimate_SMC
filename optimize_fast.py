"""
Otimização Rápida - Usando amostra menor de dados
"""

import pandas as pd
import numpy as np
from smc_entry_midline import OrderBlockStrategyMidline, validate_ohlc, SMCMidline, SignalDirection


class OrderBlockStrategyOptimized(OrderBlockStrategyMidline):
    """Estratégia otimizada com filtros adicionais"""
    
    def __init__(
        self,
        ohlc: pd.DataFrame,
        swing_length: int = 5,
        risk_reward_ratio: float = 1.0,
        min_confidence: float = 30.0,
        entry_delay_candles: int = 1,
        use_not_mitigated_filter: bool = True,
        # Novos filtros
        use_trend_filter: bool = False,
        use_volume_filter: bool = False,
        use_ob_size_filter: bool = False,
        min_volume_ratio: float = 1.5,
        min_ob_size_atr: float = 0.5,
        ema_fast: int = 20,
        ema_slow: int = 50,
    ):
        # Chamar construtor pai
        super().__init__(
            ohlc, swing_length, risk_reward_ratio, 
            min_confidence, entry_delay_candles, use_not_mitigated_filter
        )
        
        # Filtros adicionais
        self.use_trend_filter = use_trend_filter
        self.use_volume_filter = use_volume_filter
        self.use_ob_size_filter = use_ob_size_filter
        self.min_volume_ratio = min_volume_ratio
        self.min_ob_size_atr = min_ob_size_atr
        
        # Calcular EMAs
        self.ohlc['ema_fast'] = self.ohlc['close'].ewm(span=ema_fast, adjust=False).mean()
        self.ohlc['ema_slow'] = self.ohlc['close'].ewm(span=ema_slow, adjust=False).mean()
        
        # Calcular ATR
        high_low = self.ohlc['high'] - self.ohlc['low']
        self.ohlc['atr'] = high_low.rolling(window=14).mean()
    
    def generate_signals(self):
        """Gera sinais com filtros adicionais"""
        from smc_entry_midline import TradeSignal
        
        signals = []
        n = len(self.ohlc)
        
        ob_indices = self.order_blocks[~self.order_blocks['OB'].isna()].index
        
        for idx in ob_indices:
            i = self.ohlc.index.get_loc(idx)
            
            ob_direction = self.order_blocks['OB'].iloc[i]
            ob_top = self.order_blocks['Top'].iloc[i]
            ob_bottom = self.order_blocks['Bottom'].iloc[i]
            ob_volume = self.order_blocks['Volume'].iloc[i]
            ob_candle = self.order_blocks['OBCandle'].iloc[i]
            
            midline = (ob_top + ob_bottom) / 2
            ob_size = ob_top - ob_bottom
            
            # Filtro de tamanho do OB
            if self.use_ob_size_filter:
                atr = self.ohlc['atr'].iloc[i]
                if not np.isnan(atr) and ob_size < atr * self.min_ob_size_atr:
                    continue
            
            # Filtro de volume
            if self.use_volume_filter:
                avg_volume = self.ohlc['volume'].iloc[max(0, i-20):i].mean()
                if avg_volume > 0:
                    volume_ratio = ob_volume / avg_volume
                    if volume_ratio < self.min_volume_ratio:
                        continue
            
            # Filtro de tendência
            if self.use_trend_filter:
                ema_fast = self.ohlc['ema_fast'].iloc[i]
                ema_slow = self.ohlc['ema_slow'].iloc[i]
                
                if ob_direction == 1 and ema_fast <= ema_slow:
                    continue
                if ob_direction == -1 and ema_fast >= ema_slow:
                    continue
            
            confidence = self.calculate_confidence(i)
            
            if confidence < self.min_confidence:
                continue
            
            entry_start = i + self.entry_delay_candles
            
            for j in range(entry_start, min(n, i + 100)):
                mitigated = self.order_blocks['MitigatedIndex'].iloc[i]
                if self.use_not_mitigated_filter:
                    if not np.isnan(mitigated) and j >= mitigated:
                        break
                
                current_high = self.ohlc['high'].iloc[j]
                current_low = self.ohlc['low'].iloc[j]
                
                if ob_direction == 1:
                    if current_low <= midline <= current_high:
                        entry_price = midline
                        stop_loss = ob_bottom - ob_size * 0.1
                        risk = entry_price - stop_loss
                        
                        if risk <= 0:
                            break
                        
                        take_profit = entry_price + (risk * self.risk_reward_ratio)
                        
                        signal = TradeSignal(
                            index=j,
                            direction=SignalDirection.BULLISH,
                            entry_price=entry_price,
                            stop_loss=stop_loss,
                            take_profit=take_profit,
                            confidence=confidence,
                            ob_top=ob_top,
                            ob_bottom=ob_bottom,
                            risk_reward_ratio=self.risk_reward_ratio,
                            signal_candle_index=i,
                            ob_candle_index=int(ob_candle) if not np.isnan(ob_candle) else i,
                            quality_score=confidence,
                        )
                        signals.append(signal)
                        break
                
                elif ob_direction == -1:
                    if current_low <= midline <= current_high:
                        entry_price = midline
                        stop_loss = ob_top + ob_size * 0.1
                        risk = stop_loss - entry_price
                        
                        if risk <= 0:
                            break
                        
                        take_profit = entry_price - (risk * self.risk_reward_ratio)
                        
                        signal = TradeSignal(
                            index=j,
                            direction=SignalDirection.BEARISH,
                            entry_price=entry_price,
                            stop_loss=stop_loss,
                            take_profit=take_profit,
                            confidence=confidence,
                            ob_top=ob_top,
                            ob_bottom=ob_bottom,
                            risk_reward_ratio=self.risk_reward_ratio,
                            signal_candle_index=i,
                            ob_candle_index=int(ob_candle) if not np.isnan(ob_candle) else i,
                            quality_score=confidence,
                        )
                        signals.append(signal)
                        break
        
        return signals


def test_optimizations():
    """Testa diferentes combinações de filtros"""
    print("=" * 80)
    print("OTIMIZAÇÃO DE PERFORMANCE - TESTANDO FILTROS")
    print("=" * 80)
    
    # Carregar dados
    df = pd.read_csv('/home/ubuntu/smc_enhanced/data.csv')
    df.columns = [c.lower() for c in df.columns]
    df['time'] = pd.to_datetime(df['time'])
    df.set_index('time', inplace=True)
    if 'volume' not in df.columns:
        df['volume'] = df.get('tick_volume', df.get('real_volume', 1.0))
    
    print(f"\nDados: {len(df)} candles")
    
    # Configurações para testar
    configs = [
        {"name": "Base (sem filtros)", "trend": False, "volume": False, "size": False},
        {"name": "Filtro de Tendência (EMA 20/50)", "trend": True, "volume": False, "size": False},
        {"name": "Filtro de Volume (>1.5x)", "trend": False, "volume": True, "size": False, "vol_ratio": 1.5},
        {"name": "Filtro de Volume (>2x)", "trend": False, "volume": True, "size": False, "vol_ratio": 2.0},
        {"name": "Filtro de Tamanho OB (>0.5 ATR)", "trend": False, "volume": False, "size": True, "size_atr": 0.5},
        {"name": "Filtro de Tamanho OB (>1.0 ATR)", "trend": False, "volume": False, "size": True, "size_atr": 1.0},
        {"name": "Tendência + Volume 1.5x", "trend": True, "volume": True, "size": False, "vol_ratio": 1.5},
        {"name": "Tendência + Tamanho 0.5 ATR", "trend": True, "volume": False, "size": True, "size_atr": 0.5},
        {"name": "Volume + Tamanho", "trend": False, "volume": True, "size": True, "vol_ratio": 1.5, "size_atr": 0.5},
        {"name": "TODOS (Trend+Vol+Size)", "trend": True, "volume": True, "size": True, "vol_ratio": 1.5, "size_atr": 0.5},
    ]
    
    results_summary = []
    
    for config in configs:
        print(f"\n{'-'*60}")
        print(f"Testando: {config['name']}")
        print(f"{'-'*60}")
        
        strategy = OrderBlockStrategyOptimized(
            df,
            swing_length=5,
            risk_reward_ratio=1.0,
            min_confidence=30.0,
            entry_delay_candles=1,
            use_not_mitigated_filter=True,
            use_trend_filter=config.get('trend', False),
            use_volume_filter=config.get('volume', False),
            use_ob_size_filter=config.get('size', False),
            min_volume_ratio=config.get('vol_ratio', 1.5),
            min_ob_size_atr=config.get('size_atr', 0.5),
        )
        
        signals = strategy.generate_signals()
        results, stats = strategy.backtest(signals)
        
        # Calcular lucro em R
        total_r = 0
        for result in results:
            if result.hit_tp:
                total_r += 1.0
            elif result.hit_sl:
                total_r -= 1.0
        
        expectancy = total_r / len(results) if len(results) > 0 else 0
        
        print(f"   Trades: {stats['total_trades']}")
        print(f"   Win Rate: {stats['win_rate']:.1f}%")
        print(f"   Lucro (R): {total_r:.1f}R")
        print(f"   Expectativa: {expectancy:.2f}R")
        print(f"   Profit Factor: {stats['profit_factor']:.2f}")
        
        results_summary.append({
            'config': config['name'],
            'trades': stats['total_trades'],
            'win_rate': stats['win_rate'],
            'lucro_r': total_r,
            'expectancy': expectancy,
            'pf': stats['profit_factor'],
        })
    
    # Ordenar por expectativa
    results_summary.sort(key=lambda x: x['expectancy'], reverse=True)
    
    print("\n" + "=" * 80)
    print("RANKING POR EXPECTATIVA (RR 1:1)")
    print("=" * 80)
    print(f"\n{'Config':<35} {'Trades':<8} {'WinRate':<10} {'Lucro(R)':<10} {'Expect.':<10} {'PF':<8}")
    print("-" * 81)
    
    for r in results_summary:
        print(f"{r['config']:<35} {r['trades']:<8} {r['win_rate']:.1f}%{'':<4} {r['lucro_r']:.0f}R{'':<5} {r['expectancy']:.2f}R{'':<4} {r['pf']:.2f}")
    
    # Encontrar melhor configuração
    best = results_summary[0]
    
    # Testar diferentes RR com melhor configuração
    print("\n" + "=" * 80)
    print(f"TESTANDO DIFERENTES R:R COM MELHOR CONFIG: {best['config']}")
    print("=" * 80)
    
    # Determinar quais filtros usar baseado no nome
    use_trend = "Tendência" in best['config'] or "Trend" in best['config'] or "TODOS" in best['config']
    use_volume = "Volume" in best['config'] or "Vol" in best['config'] or "TODOS" in best['config']
    use_size = "Tamanho" in best['config'] or "Size" in best['config'] or "TODOS" in best['config']
    
    rr_results = []
    
    for rr in [1.0, 1.5, 2.0, 2.5, 3.0]:
        strategy = OrderBlockStrategyOptimized(
            df,
            swing_length=5,
            risk_reward_ratio=rr,
            min_confidence=30.0,
            entry_delay_candles=1,
            use_not_mitigated_filter=True,
            use_trend_filter=use_trend,
            use_volume_filter=use_volume,
            use_ob_size_filter=use_size,
            min_volume_ratio=1.5,
            min_ob_size_atr=0.5,
        )
        
        signals = strategy.generate_signals()
        results, stats = strategy.backtest(signals)
        
        total_r = 0
        for result in results:
            if result.hit_tp:
                total_r += rr
            elif result.hit_sl:
                total_r -= 1.0
        
        expectancy = total_r / len(results) if len(results) > 0 else 0
        
        rr_results.append({
            'rr': rr,
            'trades': stats['total_trades'],
            'win_rate': stats['win_rate'],
            'lucro_r': total_r,
            'expectancy': expectancy,
            'pf': stats['profit_factor'],
        })
        
        print(f"\n   RR {rr}:1 -> Trades: {stats['total_trades']}, Win Rate: {stats['win_rate']:.1f}%, Lucro: {total_r:.1f}R, Expect: {expectancy:.2f}R, PF: {stats['profit_factor']:.2f}")
    
    # Encontrar melhor RR
    rr_results.sort(key=lambda x: x['expectancy'], reverse=True)
    best_rr = rr_results[0]
    
    print("\n" + "=" * 80)
    print("MELHOR CONFIGURAÇÃO ENCONTRADA")
    print("=" * 80)
    print(f"""
    Filtros: {best['config']}
    R:R: {best_rr['rr']}:1
    
    Resultados:
    - Trades: {best_rr['trades']}
    - Win Rate: {best_rr['win_rate']:.1f}%
    - Lucro Total: {best_rr['lucro_r']:.1f}R
    - Expectativa: {best_rr['expectancy']:.2f}R por trade
    - Profit Factor: {best_rr['pf']:.2f}
    """)


if __name__ == "__main__":
    test_optimizations()
