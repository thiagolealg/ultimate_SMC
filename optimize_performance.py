"""
Otimização Avançada da Estratégia SMC
=====================================
Testar diferentes filtros e parâmetros para melhorar Win Rate e Expectativa
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple, Dict


class SignalDirection(Enum):
    BULLISH = 1
    BEARISH = -1


@dataclass
class TradeSignal:
    index: int
    direction: SignalDirection
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence: float
    ob_top: float
    ob_bottom: float
    risk_reward_ratio: float
    signal_candle_index: int
    ob_candle_index: int
    quality_score: float
    # Novos campos para análise
    ob_size: float = 0.0
    volume_ratio: float = 0.0
    trend_aligned: bool = False
    fvg_present: bool = False
    bos_present: bool = False


@dataclass
class BacktestResult:
    signal: TradeSignal
    entry_index: int
    exit_index: int
    entry_price: float
    exit_price: float
    profit_loss: float
    hit_tp: bool
    hit_sl: bool
    duration_candles: int


def validate_ohlc(ohlc: pd.DataFrame) -> pd.DataFrame:
    df = ohlc.copy()
    df.columns = [c.lower() for c in df.columns]
    required = ['open', 'high', 'low', 'close']
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Coluna '{col}' não encontrada")
    if 'volume' not in df.columns:
        df['volume'] = df.get('tick_volume', df.get('real_volume', 1.0))
    return df


class SMCOptimized:
    """SMC Otimizado com múltiplos filtros"""
    
    @classmethod
    def swing_highs_lows(cls, ohlc: pd.DataFrame, swing_length: int = 5) -> pd.DataFrame:
        ohlc = validate_ohlc(ohlc)
        n = len(ohlc)
        
        swing_high = np.full(n, np.nan)
        swing_low = np.full(n, np.nan)
        swing_high_level = np.full(n, np.nan)
        swing_low_level = np.full(n, np.nan)
        
        for i in range(swing_length, n):
            potential_high_idx = i - swing_length
            potential_high = ohlc['high'].iloc[potential_high_idx]
            
            is_swing_high = True
            for j in range(potential_high_idx - swing_length, potential_high_idx):
                if j >= 0 and ohlc['high'].iloc[j] >= potential_high:
                    is_swing_high = False
                    break
            
            if is_swing_high:
                for j in range(potential_high_idx + 1, i + 1):
                    if ohlc['high'].iloc[j] >= potential_high:
                        is_swing_high = False
                        break
            
            if is_swing_high:
                swing_high[i] = 1
                swing_high_level[i] = potential_high
            
            potential_low_idx = i - swing_length
            potential_low = ohlc['low'].iloc[potential_low_idx]
            
            is_swing_low = True
            for j in range(potential_low_idx - swing_length, potential_low_idx):
                if j >= 0 and ohlc['low'].iloc[j] <= potential_low:
                    is_swing_low = False
                    break
            
            if is_swing_low:
                for j in range(potential_low_idx + 1, i + 1):
                    if ohlc['low'].iloc[j] <= potential_low:
                        is_swing_low = False
                        break
            
            if is_swing_low:
                swing_low[i] = 1
                swing_low_level[i] = potential_low
        
        return pd.DataFrame({
            'swing_high': swing_high,
            'swing_low': swing_low,
            'swing_high_level': swing_high_level,
            'swing_low_level': swing_low_level,
        }, index=ohlc.index)
    
    @classmethod
    def order_blocks(cls, ohlc: pd.DataFrame, swing_length: int = 5) -> pd.DataFrame:
        ohlc = validate_ohlc(ohlc)
        n = len(ohlc)
        
        ob_direction = np.full(n, np.nan)
        ob_top = np.full(n, np.nan)
        ob_bottom = np.full(n, np.nan)
        ob_volume = np.full(n, np.nan)
        ob_candle_index = np.full(n, np.nan)
        mitigated_index = np.full(n, np.nan)
        
        swings = cls.swing_highs_lows(ohlc, swing_length)
        
        _open = ohlc['open'].values
        _high = ohlc['high'].values
        _low = ohlc['low'].values
        _close = ohlc['close'].values
        _volume = ohlc['volume'].values
        
        last_top_idx = -1
        last_top_level = 0.0
        last_bottom_idx = -1
        last_bottom_level = float('inf')
        
        for i in range(swing_length, n):
            if swings['swing_high'].iloc[i] == 1:
                last_top_idx = i - swing_length
                last_top_level = swings['swing_high_level'].iloc[i]
            
            if swings['swing_low'].iloc[i] == 1:
                last_bottom_idx = i - swing_length
                last_bottom_level = swings['swing_low_level'].iloc[i]
            
            if last_top_idx > 0 and _close[i] > last_top_level:
                ob_idx = last_top_idx
                while ob_idx > 0 and _close[ob_idx] >= _open[ob_idx]:
                    ob_idx -= 1
                
                if ob_idx >= 0:
                    ob_direction[i] = 1
                    ob_top[i] = max(_open[ob_idx], _close[ob_idx])
                    ob_bottom[i] = min(_open[ob_idx], _close[ob_idx])
                    ob_volume[i] = _volume[ob_idx]
                    ob_candle_index[i] = ob_idx
                    
                    for k in range(i + 1, n):
                        if _low[k] <= ob_bottom[i]:
                            mitigated_index[i] = k
                            break
                
                last_top_idx = -1
            
            if last_bottom_idx > 0 and _close[i] < last_bottom_level:
                ob_idx = last_bottom_idx
                while ob_idx > 0 and _close[ob_idx] <= _open[ob_idx]:
                    ob_idx -= 1
                
                if ob_idx >= 0:
                    ob_direction[i] = -1
                    ob_top[i] = max(_open[ob_idx], _close[ob_idx])
                    ob_bottom[i] = min(_open[ob_idx], _close[ob_idx])
                    ob_volume[i] = _volume[ob_idx]
                    ob_candle_index[i] = ob_idx
                    
                    for k in range(i + 1, n):
                        if _high[k] >= ob_top[i]:
                            mitigated_index[i] = k
                            break
                
                last_bottom_idx = -1
        
        return pd.DataFrame({
            'OB': ob_direction,
            'Top': ob_top,
            'Bottom': ob_bottom,
            'Volume': ob_volume,
            'OBCandle': ob_candle_index,
            'MitigatedIndex': mitigated_index,
        }, index=ohlc.index)
    
    @classmethod
    def detect_fvg(cls, ohlc: pd.DataFrame, index: int, direction: int) -> bool:
        """Detecta Fair Value Gap próximo ao índice"""
        if index < 2:
            return False
        
        for i in range(max(0, index - 10), index):
            if i < 2:
                continue
            
            if direction == 1:  # Bullish FVG
                if ohlc['low'].iloc[i] > ohlc['high'].iloc[i-2]:
                    return True
            else:  # Bearish FVG
                if ohlc['high'].iloc[i] < ohlc['low'].iloc[i-2]:
                    return True
        
        return False


class OrderBlockStrategyOptimized:
    """Estratégia otimizada com múltiplos filtros"""
    
    def __init__(
        self,
        ohlc: pd.DataFrame,
        swing_length: int = 5,
        risk_reward_ratio: float = 1.0,
        min_confidence: float = 30.0,
        entry_delay_candles: int = 1,
        # Filtros de otimização
        use_trend_filter: bool = False,
        use_volume_filter: bool = False,
        use_ob_size_filter: bool = False,
        use_fvg_filter: bool = False,
        use_time_filter: bool = False,
        min_ob_size_atr: float = 0.5,
        min_volume_ratio: float = 1.0,
        ema_fast: int = 20,
        ema_slow: int = 50,
    ):
        self.ohlc = validate_ohlc(ohlc)
        self.swing_length = swing_length
        self.risk_reward_ratio = risk_reward_ratio
        self.min_confidence = min_confidence
        self.entry_delay_candles = entry_delay_candles
        
        # Filtros
        self.use_trend_filter = use_trend_filter
        self.use_volume_filter = use_volume_filter
        self.use_ob_size_filter = use_ob_size_filter
        self.use_fvg_filter = use_fvg_filter
        self.use_time_filter = use_time_filter
        self.min_ob_size_atr = min_ob_size_atr
        self.min_volume_ratio = min_volume_ratio
        
        # Calcular indicadores
        self.swings = SMCOptimized.swing_highs_lows(self.ohlc, swing_length)
        self.order_blocks = SMCOptimized.order_blocks(self.ohlc, swing_length)
        
        # Calcular EMAs para filtro de tendência
        self.ohlc['ema_fast'] = self.ohlc['close'].ewm(span=ema_fast, adjust=False).mean()
        self.ohlc['ema_slow'] = self.ohlc['close'].ewm(span=ema_slow, adjust=False).mean()
        
        # Calcular ATR para filtro de tamanho
        high_low = self.ohlc['high'] - self.ohlc['low']
        self.ohlc['atr'] = high_low.rolling(window=14).mean()
    
    def generate_signals(self) -> List[TradeSignal]:
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
            volume_ratio = 1.0
            if self.use_volume_filter:
                avg_volume = self.ohlc['volume'].iloc[max(0, i-20):i].mean()
                if avg_volume > 0:
                    volume_ratio = ob_volume / avg_volume
                    if volume_ratio < self.min_volume_ratio:
                        continue
            
            # Filtro de tendência
            trend_aligned = True
            if self.use_trend_filter:
                ema_fast = self.ohlc['ema_fast'].iloc[i]
                ema_slow = self.ohlc['ema_slow'].iloc[i]
                
                if ob_direction == 1 and ema_fast <= ema_slow:
                    trend_aligned = False
                    continue
                if ob_direction == -1 and ema_fast >= ema_slow:
                    trend_aligned = False
                    continue
            
            # Filtro de FVG
            fvg_present = False
            if self.use_fvg_filter:
                fvg_present = SMCOptimized.detect_fvg(self.ohlc, i, int(ob_direction))
                if not fvg_present:
                    continue
            
            entry_start = i + self.entry_delay_candles
            
            for j in range(entry_start, min(n, i + 100)):
                mitigated = self.order_blocks['MitigatedIndex'].iloc[i]
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
                            confidence=50.0,
                            ob_top=ob_top,
                            ob_bottom=ob_bottom,
                            risk_reward_ratio=self.risk_reward_ratio,
                            signal_candle_index=i,
                            ob_candle_index=int(ob_candle) if not np.isnan(ob_candle) else i,
                            quality_score=50.0,
                            ob_size=ob_size,
                            volume_ratio=volume_ratio,
                            trend_aligned=trend_aligned,
                            fvg_present=fvg_present,
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
                            confidence=50.0,
                            ob_top=ob_top,
                            ob_bottom=ob_bottom,
                            risk_reward_ratio=self.risk_reward_ratio,
                            signal_candle_index=i,
                            ob_candle_index=int(ob_candle) if not np.isnan(ob_candle) else i,
                            quality_score=50.0,
                            ob_size=ob_size,
                            volume_ratio=volume_ratio,
                            trend_aligned=trend_aligned,
                            fvg_present=fvg_present,
                        )
                        signals.append(signal)
                        break
        
        return signals
    
    def backtest(self, signals: Optional[List[TradeSignal]] = None) -> Tuple[List[BacktestResult], Dict]:
        if signals is None:
            signals = self.generate_signals()
        
        results = []
        n = len(self.ohlc)
        
        for signal in signals:
            entry_index = signal.index
            exit_index = None
            exit_price = None
            hit_tp = False
            hit_sl = False
            
            for k in range(entry_index + 1, min(n, entry_index + 500)):
                high = self.ohlc['high'].iloc[k]
                low = self.ohlc['low'].iloc[k]
                
                if signal.direction == SignalDirection.BULLISH:
                    if low <= signal.stop_loss:
                        exit_index = k
                        exit_price = signal.stop_loss
                        hit_sl = True
                        break
                    if high >= signal.take_profit:
                        exit_index = k
                        exit_price = signal.take_profit
                        hit_tp = True
                        break
                else:
                    if high >= signal.stop_loss:
                        exit_index = k
                        exit_price = signal.stop_loss
                        hit_sl = True
                        break
                    if low <= signal.take_profit:
                        exit_index = k
                        exit_price = signal.take_profit
                        hit_tp = True
                        break
            
            if exit_index is not None:
                if signal.direction == SignalDirection.BULLISH:
                    profit_loss = exit_price - signal.entry_price
                else:
                    profit_loss = signal.entry_price - exit_price
                
                results.append(BacktestResult(
                    signal=signal,
                    entry_index=entry_index,
                    exit_index=exit_index,
                    entry_price=signal.entry_price,
                    exit_price=exit_price,
                    profit_loss=profit_loss,
                    hit_tp=hit_tp,
                    hit_sl=hit_sl,
                    duration_candles=exit_index - entry_index,
                ))
        
        if len(results) > 0:
            winning = [r for r in results if r.hit_tp]
            losing = [r for r in results if r.hit_sl]
            
            total_profit = sum(r.profit_loss for r in winning)
            total_loss = abs(sum(r.profit_loss for r in losing))
            
            stats = {
                'total_trades': len(results),
                'winning_trades': len(winning),
                'losing_trades': len(losing),
                'win_rate': len(winning) / len(results) * 100 if len(results) > 0 else 0,
                'total_profit_loss': sum(r.profit_loss for r in results),
                'profit_factor': total_profit / total_loss if total_loss > 0 else float('inf'),
            }
        else:
            stats = {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'total_profit_loss': 0,
                'profit_factor': 0,
            }
        
        return results, stats


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
        {"name": "Base (sem filtros)", "trend": False, "volume": False, "size": False, "fvg": False},
        {"name": "Filtro de Tendência", "trend": True, "volume": False, "size": False, "fvg": False},
        {"name": "Filtro de Volume (>1.5x)", "trend": False, "volume": True, "size": False, "fvg": False, "vol_ratio": 1.5},
        {"name": "Filtro de Volume (>2x)", "trend": False, "volume": True, "size": False, "fvg": False, "vol_ratio": 2.0},
        {"name": "Filtro de Tamanho OB (>0.5 ATR)", "trend": False, "volume": False, "size": True, "fvg": False, "size_atr": 0.5},
        {"name": "Filtro de Tamanho OB (>1.0 ATR)", "trend": False, "volume": False, "size": True, "fvg": False, "size_atr": 1.0},
        {"name": "Filtro FVG", "trend": False, "volume": False, "size": False, "fvg": True},
        {"name": "Tendência + Volume", "trend": True, "volume": True, "size": False, "fvg": False, "vol_ratio": 1.5},
        {"name": "Tendência + Tamanho", "trend": True, "volume": False, "size": True, "fvg": False, "size_atr": 0.5},
        {"name": "Volume + Tamanho", "trend": False, "volume": True, "size": True, "fvg": False, "vol_ratio": 1.5, "size_atr": 0.5},
        {"name": "Tendência + Volume + Tamanho", "trend": True, "volume": True, "size": True, "fvg": False, "vol_ratio": 1.5, "size_atr": 0.5},
        {"name": "TODOS os filtros", "trend": True, "volume": True, "size": True, "fvg": True, "vol_ratio": 1.5, "size_atr": 0.5},
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
            use_trend_filter=config.get('trend', False),
            use_volume_filter=config.get('volume', False),
            use_ob_size_filter=config.get('size', False),
            use_fvg_filter=config.get('fvg', False),
            min_volume_ratio=config.get('vol_ratio', 1.0),
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
    print("RANKING POR EXPECTATIVA")
    print("=" * 80)
    print(f"\n{'Config':<40} {'Trades':<10} {'Win Rate':<12} {'Lucro (R)':<12} {'Expect.':<10} {'PF':<8}")
    print("-" * 92)
    
    for r in results_summary:
        print(f"{r['config']:<40} {r['trades']:<10} {r['win_rate']:.1f}%{'':<6} {r['lucro_r']:.1f}R{'':<6} {r['expectancy']:.2f}R{'':<4} {r['pf']:.2f}")
    
    # Testar diferentes RR com melhor configuração
    print("\n" + "=" * 80)
    print("TESTANDO DIFERENTES R:R COM MELHOR CONFIGURAÇÃO")
    print("=" * 80)
    
    best_config = results_summary[0]
    print(f"\nMelhor configuração: {best_config['config']}")
    
    for rr in [1.0, 1.5, 2.0, 2.5, 3.0]:
        strategy = OrderBlockStrategyOptimized(
            df,
            swing_length=5,
            risk_reward_ratio=rr,
            min_confidence=30.0,
            entry_delay_candles=1,
            use_trend_filter=True,
            use_volume_filter=True,
            use_ob_size_filter=True,
            use_fvg_filter=False,
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
        
        print(f"\n   RR {rr}:1 -> Trades: {stats['total_trades']}, Win Rate: {stats['win_rate']:.1f}%, Lucro: {total_r:.1f}R, Expect: {expectancy:.2f}R")


if __name__ == "__main__":
    test_optimizations()
