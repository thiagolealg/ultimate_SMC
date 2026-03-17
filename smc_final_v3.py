"""
Smart Money Concepts - Versão Final V3
======================================
Biblioteca completa com todos os padrões SMC e Wyckoff
COM FILTROS DE ALTA ASSERTIVIDADE:
- OB não mitigado (primeiro toque apenas)
- Volume > 1.5x média
- Tamanho OB > 0.5 ATR

Baseado na versão otimizada que atingiu 71.8% Win Rate
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple, Dict


class SignalDirection(Enum):
    BULLISH = 1
    BEARISH = -1


class PatternType(Enum):
    ORDER_BLOCK = "OB"
    BOS = "BOS"
    CHOCH = "CHoCH"
    FVG = "FVG"
    LIQUIDITY_SWEEP = "SWEEP"
    ABC_CORRECTION = "ABC"
    SPRING = "SPRING"
    UPTHRUST = "UPTHRUST"


@dataclass
class ConfidenceFactors:
    """Fatores do índice de confiança"""
    volume_score: float = 0.0          # 0-25 pontos
    fvg_score: float = 0.0             # 0-20 pontos
    trend_score: float = 0.0           # 0-15 pontos
    size_score: float = 0.0            # 0-15 pontos
    sweep_score: float = 0.0           # 0-15 pontos
    wyckoff_score: float = 0.0         # 0-10 pontos
    
    @property
    def total(self) -> float:
        return min(100.0, (
            self.volume_score + 
            self.fvg_score +
            self.trend_score + 
            self.size_score + 
            self.sweep_score +
            self.wyckoff_score
        ))
    
    def get_breakdown(self) -> str:
        parts = []
        if self.volume_score > 0:
            parts.append(f"Vol:{self.volume_score:.0f}")
        if self.fvg_score > 0:
            parts.append(f"FVG:{self.fvg_score:.0f}")
        if self.trend_score > 0:
            parts.append(f"Trend:{self.trend_score:.0f}")
        if self.size_score > 0:
            parts.append(f"Size:{self.size_score:.0f}")
        if self.sweep_score > 0:
            parts.append(f"Sweep:{self.sweep_score:.0f}")
        if self.wyckoff_score > 0:
            parts.append(f"Wyck:{self.wyckoff_score:.0f}")
        return " | ".join(parts)


@dataclass
class TradeSignal:
    """Sinal de trade"""
    index: int
    direction: SignalDirection
    entry_price: float
    stop_loss: float
    take_profit: float
    ob_top: float
    ob_bottom: float
    risk_reward_ratio: float
    signal_candle_index: int
    ob_candle_index: int
    confidence_factors: ConfidenceFactors
    leverage: float = 1.0
    patterns_detected: List[PatternType] = field(default_factory=list)
    
    @property
    def confidence(self) -> float:
        return self.confidence_factors.total


@dataclass
class BacktestResult:
    """Resultado de um trade no backtest"""
    signal: TradeSignal
    entry_index: int
    exit_index: int
    entry_price: float
    exit_price: float
    profit_loss: float
    profit_loss_r: float
    hit_tp: bool
    hit_sl: bool
    duration_candles: int
    leverage_used: float = 1.0


def validate_ohlc(ohlc: pd.DataFrame) -> pd.DataFrame:
    """Valida e normaliza DataFrame OHLC"""
    df = ohlc.copy()
    df.columns = [c.lower() for c in df.columns]
    
    required = ['open', 'high', 'low', 'close']
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Coluna '{col}' não encontrada")
    
    if 'volume' not in df.columns:
        df['volume'] = df.get('tick_volume', df.get('real_volume', 1.0))
    
    return df


class SMCFinalV3:
    """
    Smart Money Concepts - Biblioteca Completa
    """
    
    @classmethod
    def swing_highs_lows(cls, ohlc: pd.DataFrame, swing_length: int = 5) -> pd.DataFrame:
        """Detecta Swing Highs e Lows SEM look-ahead bias"""
        ohlc = validate_ohlc(ohlc)
        n = len(ohlc)
        
        swing_high = np.zeros(n)
        swing_low = np.zeros(n)
        swing_high_level = np.full(n, np.nan)
        swing_low_level = np.full(n, np.nan)
        
        _high = ohlc['high'].values
        _low = ohlc['low'].values
        
        for i in range(swing_length, n):
            # Swing High
            candidate_idx = i - swing_length
            candidate_high = _high[candidate_idx]
            
            is_swing_high = True
            for j in range(candidate_idx - swing_length, candidate_idx):
                if j >= 0 and _high[j] >= candidate_high:
                    is_swing_high = False
                    break
            
            if is_swing_high:
                for j in range(candidate_idx + 1, i + 1):
                    if _high[j] >= candidate_high:
                        is_swing_high = False
                        break
            
            if is_swing_high:
                swing_high[i] = 1
                swing_high_level[i] = candidate_high
            
            # Swing Low
            candidate_low = _low[candidate_idx]
            
            is_swing_low = True
            for j in range(candidate_idx - swing_length, candidate_idx):
                if j >= 0 and _low[j] <= candidate_low:
                    is_swing_low = False
                    break
            
            if is_swing_low:
                for j in range(candidate_idx + 1, i + 1):
                    if _low[j] <= candidate_low:
                        is_swing_low = False
                        break
            
            if is_swing_low:
                swing_low[i] = 1
                swing_low_level[i] = candidate_low
        
        return pd.DataFrame({
            'swing_high': swing_high,
            'swing_low': swing_low,
            'swing_high_level': swing_high_level,
            'swing_low_level': swing_low_level,
        }, index=ohlc.index)
    
    @classmethod
    def bos_choch(cls, ohlc: pd.DataFrame, swing_length: int = 5) -> pd.DataFrame:
        """Detecta BOS e CHoCH"""
        ohlc = validate_ohlc(ohlc)
        swings = cls.swing_highs_lows(ohlc, swing_length)
        
        n = len(ohlc)
        bos = np.full(n, np.nan)
        choch = np.full(n, np.nan)
        
        _close = ohlc['close'].values
        
        last_swing_high = None
        last_swing_low = None
        trend = 0
        
        for i in range(swing_length, n):
            if swings['swing_high'].iloc[i] == 1:
                last_swing_high = swings['swing_high_level'].iloc[i]
            
            if swings['swing_low'].iloc[i] == 1:
                last_swing_low = swings['swing_low_level'].iloc[i]
            
            if last_swing_high is not None and _close[i] > last_swing_high:
                if trend == 1:
                    bos[i] = 1
                elif trend == -1 or trend == 0:
                    choch[i] = 1
                trend = 1
                last_swing_high = None
            
            if last_swing_low is not None and _close[i] < last_swing_low:
                if trend == -1:
                    bos[i] = -1
                elif trend == 1 or trend == 0:
                    choch[i] = -1
                trend = -1
                last_swing_low = None
        
        return pd.DataFrame({
            'BOS': bos,
            'CHoCH': choch,
        }, index=ohlc.index)
    
    @classmethod
    def fair_value_gap(cls, ohlc: pd.DataFrame) -> pd.DataFrame:
        """Detecta FVG"""
        ohlc = validate_ohlc(ohlc)
        n = len(ohlc)
        
        fvg = np.full(n, np.nan)
        fvg_top = np.full(n, np.nan)
        fvg_bottom = np.full(n, np.nan)
        
        _high = ohlc['high'].values
        _low = ohlc['low'].values
        
        for i in range(2, n):
            if _low[i] > _high[i-2]:
                fvg[i] = 1
                fvg_top[i] = _low[i]
                fvg_bottom[i] = _high[i-2]
            elif _high[i] < _low[i-2]:
                fvg[i] = -1
                fvg_top[i] = _low[i-2]
                fvg_bottom[i] = _high[i]
        
        return pd.DataFrame({
            'FVG': fvg,
            'FVG_Top': fvg_top,
            'FVG_Bottom': fvg_bottom,
        }, index=ohlc.index)
    
    @classmethod
    def liquidity_sweep(cls, ohlc: pd.DataFrame, swing_length: int = 5) -> pd.DataFrame:
        """Detecta Liquidity Sweeps"""
        ohlc = validate_ohlc(ohlc)
        swings = cls.swing_highs_lows(ohlc, swing_length)
        
        n = len(ohlc)
        sweep = np.full(n, np.nan)
        sweep_strength = np.full(n, np.nan)
        
        _high = ohlc['high'].values
        _low = ohlc['low'].values
        _close = ohlc['close'].values
        
        swing_lows = []
        swing_highs = []
        
        for i in range(n):
            if swings['swing_low'].iloc[i] == 1:
                swing_lows.append((i, swings['swing_low_level'].iloc[i]))
            if swings['swing_high'].iloc[i] == 1:
                swing_highs.append((i, swings['swing_high_level'].iloc[i]))
            
            # Bullish Sweep
            for sl_idx, sl_level in swing_lows:
                if sl_idx < i - 100 or sl_idx >= i:
                    continue
                
                if _low[i] < sl_level and _close[i] > sl_level:
                    sweep_depth = (sl_level - _low[i]) / sl_level
                    if sweep_depth >= 0.001:
                        sweep[i] = 1
                        sweep_strength[i] = sweep_depth * 100
                        break
            
            # Bearish Sweep
            for sh_idx, sh_level in swing_highs:
                if sh_idx < i - 100 or sh_idx >= i:
                    continue
                
                if _high[i] > sh_level and _close[i] < sh_level:
                    sweep_depth = (_high[i] - sh_level) / sh_level
                    if sweep_depth >= 0.001:
                        sweep[i] = -1
                        sweep_strength[i] = sweep_depth * 100
                        break
        
        return pd.DataFrame({
            'Sweep': sweep,
            'Sweep_Strength': sweep_strength,
        }, index=ohlc.index)
    
    @classmethod
    def wyckoff_spring(cls, ohlc: pd.DataFrame, swing_length: int = 5, lookback: int = 50) -> pd.DataFrame:
        """Detecta Spring (Wyckoff)"""
        ohlc = validate_ohlc(ohlc)
        swings = cls.swing_highs_lows(ohlc, swing_length)
        
        n = len(ohlc)
        spring = np.full(n, np.nan)
        spring_quality = np.full(n, np.nan)
        
        _low = ohlc['low'].values
        _close = ohlc['close'].values
        _volume = ohlc['volume'].values
        
        for i in range(lookback, n):
            support_levels = []
            for j in range(i - lookback, i):
                if swings['swing_low'].iloc[j] == 1:
                    support_levels.append(swings['swing_low_level'].iloc[j])
            
            if len(support_levels) < 2:
                continue
            
            support_zone = min(support_levels)
            tolerance = support_zone * 0.002
            touches = sum(1 for sl in support_levels if abs(sl - support_zone) <= tolerance)
            
            if touches >= 2:
                if _low[i] < support_zone - tolerance and _close[i] > support_zone:
                    spring[i] = 1
                    depth = (support_zone - _low[i]) / support_zone * 100
                    avg_vol = np.mean(_volume[max(0, i-20):i])
                    vol_ratio = _volume[i] / avg_vol if avg_vol > 0 else 1
                    spring_quality[i] = min(100, depth * 10 + vol_ratio * 10 + touches * 10)
        
        return pd.DataFrame({
            'Spring': spring,
            'Spring_Quality': spring_quality,
        }, index=ohlc.index)
    
    @classmethod
    def wyckoff_upthrust(cls, ohlc: pd.DataFrame, swing_length: int = 5, lookback: int = 50) -> pd.DataFrame:
        """Detecta Upthrust (Wyckoff)"""
        ohlc = validate_ohlc(ohlc)
        swings = cls.swing_highs_lows(ohlc, swing_length)
        
        n = len(ohlc)
        upthrust = np.full(n, np.nan)
        upthrust_quality = np.full(n, np.nan)
        
        _high = ohlc['high'].values
        _close = ohlc['close'].values
        _volume = ohlc['volume'].values
        
        for i in range(lookback, n):
            resistance_levels = []
            for j in range(i - lookback, i):
                if swings['swing_high'].iloc[j] == 1:
                    resistance_levels.append(swings['swing_high_level'].iloc[j])
            
            if len(resistance_levels) < 2:
                continue
            
            resistance_zone = max(resistance_levels)
            tolerance = resistance_zone * 0.002
            touches = sum(1 for rl in resistance_levels if abs(rl - resistance_zone) <= tolerance)
            
            if touches >= 2:
                if _high[i] > resistance_zone + tolerance and _close[i] < resistance_zone:
                    upthrust[i] = -1
                    depth = (_high[i] - resistance_zone) / resistance_zone * 100
                    avg_vol = np.mean(_volume[max(0, i-20):i])
                    vol_ratio = _volume[i] / avg_vol if avg_vol > 0 else 1
                    upthrust_quality[i] = min(100, depth * 10 + vol_ratio * 10 + touches * 10)
        
        return pd.DataFrame({
            'Upthrust': upthrust,
            'Upthrust_Quality': upthrust_quality,
        }, index=ohlc.index)
    
    @classmethod
    def order_blocks(cls, ohlc: pd.DataFrame, swing_length: int = 5) -> pd.DataFrame:
        """Detecta Order Blocks"""
        ohlc = validate_ohlc(ohlc)
        swings = cls.swing_highs_lows(ohlc, swing_length)
        
        n = len(ohlc)
        ob_direction = np.full(n, np.nan)
        ob_top = np.full(n, np.nan)
        ob_bottom = np.full(n, np.nan)
        ob_volume = np.full(n, np.nan)
        ob_candle_index = np.full(n, np.nan)
        mitigated_index = np.full(n, np.nan)
        
        _open = ohlc['open'].values
        _high = ohlc['high'].values
        _low = ohlc['low'].values
        _close = ohlc['close'].values
        _volume = ohlc['volume'].values
        
        last_top_idx = -1
        last_top_level = 0
        last_bottom_idx = -1
        last_bottom_level = 0
        
        for i in range(swing_length, n):
            if swings['swing_high'].iloc[i] == 1:
                last_top_idx = i - swing_length
                last_top_level = swings['swing_high_level'].iloc[i]
            
            if swings['swing_low'].iloc[i] == 1:
                last_bottom_idx = i - swing_length
                last_bottom_level = swings['swing_low_level'].iloc[i]
            
            # Bullish OB
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
            
            # Bearish OB
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


class SMCStrategyFinalV3:
    """
    Estratégia SMC Final V3
    
    FILTROS DE ALTA ASSERTIVIDADE:
    - OB não mitigado (primeiro toque apenas)
    - Volume > 1.5x média
    - Tamanho OB > 0.5 ATR
    
    Entrada: Linha do meio do OB
    """
    
    LEVERAGE_TIERS = [
        (0, 30, 1.0),
        (31, 50, 1.5),
        (51, 70, 2.0),
        (71, 85, 2.5),
        (86, 100, 3.0),
    ]
    
    def __init__(
        self,
        ohlc: pd.DataFrame,
        swing_length: int = 5,
        risk_reward_ratio: float = 1.0,
        entry_delay_candles: int = 1,
        min_confidence: float = 0.0,
        # FILTROS DE ALTA ASSERTIVIDADE
        use_not_mitigated_filter: bool = True,
        min_volume_ratio: float = 1.5,
        min_ob_size_atr: float = 0.5,
    ):
        self.ohlc = validate_ohlc(ohlc)
        self.swing_length = swing_length
        self.risk_reward_ratio = risk_reward_ratio
        self.entry_delay_candles = entry_delay_candles
        self.min_confidence = min_confidence
        
        self.use_not_mitigated_filter = use_not_mitigated_filter
        self.min_volume_ratio = min_volume_ratio
        self.min_ob_size_atr = min_ob_size_atr
        
        # Calcular indicadores
        print("Calculando indicadores SMC...")
        self.swings = SMCFinalV3.swing_highs_lows(self.ohlc, swing_length)
        self.order_blocks = SMCFinalV3.order_blocks(self.ohlc, swing_length)
        self.bos_choch = SMCFinalV3.bos_choch(self.ohlc, swing_length)
        self.fvg = SMCFinalV3.fair_value_gap(self.ohlc)
        self.sweeps = SMCFinalV3.liquidity_sweep(self.ohlc, swing_length)
        self.springs = SMCFinalV3.wyckoff_spring(self.ohlc, swing_length)
        self.upthrusts = SMCFinalV3.wyckoff_upthrust(self.ohlc, swing_length)
        
        # ATR e Volume médio
        self.ohlc['atr'] = (self.ohlc['high'] - self.ohlc['low']).rolling(14).mean()
        self.ohlc['avg_volume'] = self.ohlc['volume'].rolling(20).mean()
        self.ohlc['ema_fast'] = self.ohlc['close'].ewm(span=20, adjust=False).mean()
        self.ohlc['ema_slow'] = self.ohlc['close'].ewm(span=50, adjust=False).mean()
        
        print("Indicadores calculados!")
    
    def calculate_confidence(self, ob_index: int, ob_direction: int) -> ConfidenceFactors:
        """Calcula índice de confiança"""
        factors = ConfidenceFactors()
        
        ob_top = self.order_blocks['Top'].iloc[ob_index]
        ob_bottom = self.order_blocks['Bottom'].iloc[ob_index]
        ob_volume = self.order_blocks['Volume'].iloc[ob_index]
        ob_size = ob_top - ob_bottom
        atr = self.ohlc['atr'].iloc[ob_index]
        
        # 1. VOLUME SCORE (0-25)
        avg_volume = self.ohlc['avg_volume'].iloc[ob_index]
        if avg_volume > 0 and not np.isnan(ob_volume):
            volume_ratio = ob_volume / avg_volume
            if volume_ratio >= 3.0:
                factors.volume_score = 25.0
            elif volume_ratio >= 2.5:
                factors.volume_score = 20.0
            elif volume_ratio >= 2.0:
                factors.volume_score = 15.0
            elif volume_ratio >= 1.5:
                factors.volume_score = 10.0
        
        # 2. FVG SCORE (0-20)
        for j in range(max(0, ob_index - 10), ob_index + 1):
            if not np.isnan(self.fvg['FVG'].iloc[j]):
                fvg_dir = self.fvg['FVG'].iloc[j]
                if (ob_direction == 1 and fvg_dir == 1) or (ob_direction == -1 and fvg_dir == -1):
                    fvg_size = abs(self.fvg['FVG_Top'].iloc[j] - self.fvg['FVG_Bottom'].iloc[j])
                    if not np.isnan(atr) and atr > 0:
                        fvg_ratio = fvg_size / atr
                        if fvg_ratio >= 1.0:
                            factors.fvg_score = 20.0
                        elif fvg_ratio >= 0.5:
                            factors.fvg_score = 15.0
                        else:
                            factors.fvg_score = 10.0
                    break
        
        # 3. TREND SCORE (0-15)
        ema_fast = self.ohlc['ema_fast'].iloc[ob_index]
        ema_slow = self.ohlc['ema_slow'].iloc[ob_index]
        close = self.ohlc['close'].iloc[ob_index]
        
        if not np.isnan(ema_fast) and not np.isnan(ema_slow):
            if ob_direction == 1:
                if close > ema_fast > ema_slow:
                    factors.trend_score = 15.0
                elif close > ema_fast:
                    factors.trend_score = 10.0
                elif ema_fast > ema_slow:
                    factors.trend_score = 5.0
            else:
                if close < ema_fast < ema_slow:
                    factors.trend_score = 15.0
                elif close < ema_fast:
                    factors.trend_score = 10.0
                elif ema_fast < ema_slow:
                    factors.trend_score = 5.0
        
        # 4. SIZE SCORE (0-15)
        if not np.isnan(atr) and atr > 0:
            size_ratio = ob_size / atr
            if size_ratio >= 1.5:
                factors.size_score = 15.0
            elif size_ratio >= 1.0:
                factors.size_score = 10.0
            elif size_ratio >= 0.5:
                factors.size_score = 5.0
        
        # 5. SWEEP SCORE (0-15)
        for j in range(max(0, ob_index - 5), ob_index + 1):
            if not np.isnan(self.sweeps['Sweep'].iloc[j]):
                sweep_dir = self.sweeps['Sweep'].iloc[j]
                if (ob_direction == 1 and sweep_dir == 1) or (ob_direction == -1 and sweep_dir == -1):
                    factors.sweep_score = 15.0
                    break
        
        # 6. WYCKOFF SCORE (0-10)
        for j in range(max(0, ob_index - 5), ob_index + 1):
            if ob_direction == 1 and not np.isnan(self.springs['Spring'].iloc[j]):
                factors.wyckoff_score = 10.0
                break
            if ob_direction == -1 and not np.isnan(self.upthrusts['Upthrust'].iloc[j]):
                factors.wyckoff_score = 10.0
                break
        
        return factors
    
    def get_leverage(self, confidence: float) -> float:
        for min_conf, max_conf, leverage in self.LEVERAGE_TIERS:
            if min_conf <= confidence <= max_conf:
                return leverage
        return 1.0
    
    def get_patterns_at_index(self, index: int, direction: int) -> List[PatternType]:
        """Retorna padrões detectados"""
        patterns = [PatternType.ORDER_BLOCK]
        
        for j in range(max(0, index - 5), index + 1):
            if not np.isnan(self.bos_choch['BOS'].iloc[j]):
                patterns.append(PatternType.BOS)
                break
            if not np.isnan(self.bos_choch['CHoCH'].iloc[j]):
                patterns.append(PatternType.CHOCH)
                break
        
        for j in range(max(0, index - 10), index + 1):
            if not np.isnan(self.fvg['FVG'].iloc[j]):
                patterns.append(PatternType.FVG)
                break
        
        for j in range(max(0, index - 5), index + 1):
            if not np.isnan(self.sweeps['Sweep'].iloc[j]):
                patterns.append(PatternType.LIQUIDITY_SWEEP)
                break
        
        for j in range(max(0, index - 5), index + 1):
            if direction == 1 and not np.isnan(self.springs['Spring'].iloc[j]):
                patterns.append(PatternType.SPRING)
                break
            if direction == -1 and not np.isnan(self.upthrusts['Upthrust'].iloc[j]):
                patterns.append(PatternType.UPTHRUST)
                break
        
        return patterns
    
    def generate_signals(self) -> List[TradeSignal]:
        """Gera sinais com filtros de alta assertividade"""
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
            
            # FILTRO 1: Tamanho do OB > 0.5 ATR
            atr = self.ohlc['atr'].iloc[i]
            if self.min_ob_size_atr > 0 and not np.isnan(atr):
                if ob_size < atr * self.min_ob_size_atr:
                    continue
            
            # FILTRO 2: Volume > 1.5x média
            avg_volume = self.ohlc['avg_volume'].iloc[i]
            if self.min_volume_ratio > 0 and avg_volume > 0 and not np.isnan(ob_volume):
                volume_ratio = ob_volume / avg_volume
                if volume_ratio < self.min_volume_ratio:
                    continue
            
            # Calcular confiança
            confidence_factors = self.calculate_confidence(i, int(ob_direction))
            confidence = confidence_factors.total
            
            if confidence < self.min_confidence:
                continue
            
            leverage = self.get_leverage(confidence)
            patterns = self.get_patterns_at_index(i, int(ob_direction))
            
            entry_start = i + self.entry_delay_candles
            
            for j in range(entry_start, min(n, i + 100)):
                # FILTRO 3: OB não mitigado
                if self.use_not_mitigated_filter:
                    mitigated = self.order_blocks['MitigatedIndex'].iloc[i]
                    if not np.isnan(mitigated) and j >= mitigated:
                        break
                
                current_high = self.ohlc['high'].iloc[j]
                current_low = self.ohlc['low'].iloc[j]
                
                # Bullish OB
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
                            ob_top=ob_top,
                            ob_bottom=ob_bottom,
                            risk_reward_ratio=self.risk_reward_ratio,
                            signal_candle_index=i,
                            ob_candle_index=int(ob_candle) if not np.isnan(ob_candle) else i,
                            confidence_factors=confidence_factors,
                            leverage=leverage,
                            patterns_detected=patterns,
                        )
                        signals.append(signal)
                        break
                
                # Bearish OB
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
                            ob_top=ob_top,
                            ob_bottom=ob_bottom,
                            risk_reward_ratio=self.risk_reward_ratio,
                            signal_candle_index=i,
                            ob_candle_index=int(ob_candle) if not np.isnan(ob_candle) else i,
                            confidence_factors=confidence_factors,
                            leverage=leverage,
                            patterns_detected=patterns,
                        )
                        signals.append(signal)
                        break
        
        return signals
    
    def backtest(self, signals: Optional[List[TradeSignal]] = None) -> Tuple[List[BacktestResult], Dict]:
        """Executa backtest"""
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
                
                if hit_tp:
                    profit_loss_r = self.risk_reward_ratio * signal.leverage
                else:
                    profit_loss_r = -1.0 * signal.leverage
                
                results.append(BacktestResult(
                    signal=signal,
                    entry_index=entry_index,
                    exit_index=exit_index,
                    entry_price=signal.entry_price,
                    exit_price=exit_price,
                    profit_loss=profit_loss,
                    profit_loss_r=profit_loss_r,
                    hit_tp=hit_tp,
                    hit_sl=hit_sl,
                    duration_candles=exit_index - entry_index,
                    leverage_used=signal.leverage,
                ))
        
        # Estatísticas
        if len(results) > 0:
            winning = [r for r in results if r.hit_tp]
            losing = [r for r in results if r.hit_sl]
            
            total_profit = sum(r.profit_loss_r for r in winning)
            total_loss = abs(sum(r.profit_loss_r for r in losing))
            
            stats = {
                'total_trades': len(results),
                'winning_trades': len(winning),
                'losing_trades': len(losing),
                'win_rate': len(winning) / len(results) * 100,
                'profit_factor': total_profit / total_loss if total_loss > 0 else float('inf'),
                'total_profit_loss_r': sum(r.profit_loss_r for r in results),
                'avg_profit_loss_r': sum(r.profit_loss_r for r in results) / len(results),
                'avg_duration': sum(r.duration_candles for r in results) / len(results),
                'avg_leverage': sum(r.leverage_used for r in results) / len(results),
            }
        else:
            stats = {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'profit_factor': 0,
                'total_profit_loss_r': 0,
                'avg_profit_loss_r': 0,
                'avg_duration': 0,
                'avg_leverage': 1.0,
            }
        
        return results, stats


# ==================== TESTES ====================

if __name__ == "__main__":
    print("=" * 80)
    print("SMART MONEY CONCEPTS - VERSÃO FINAL V3")
    print("=" * 80)
    
    # Carregar dados
    df = pd.read_csv('/home/ubuntu/smc_enhanced/data.csv')
    df.columns = [c.lower() for c in df.columns]
    df['time'] = pd.to_datetime(df['time'])
    df.set_index('time', inplace=True)
    if 'volume' not in df.columns:
        df['volume'] = df.get('tick_volume', df.get('real_volume', 1.0))
    
    # Usar amostra para teste rápido
    df_sample = df.iloc[:30000].copy()
    print(f"Dados: {len(df_sample)} candles (amostra)")
    
    # Testar com filtros
    print("\n" + "=" * 80)
    print("RESULTADOS COM FILTROS DE ALTA ASSERTIVIDADE")
    print("=" * 80)
    
    for rr in [1.0, 2.0, 3.0]:
        strategy = SMCStrategyFinalV3(
            df_sample,
            swing_length=5,
            risk_reward_ratio=rr,
            entry_delay_candles=1,
            min_confidence=0.0,
            use_not_mitigated_filter=True,
            min_volume_ratio=1.5,
            min_ob_size_atr=0.5,
        )
        signals = strategy.generate_signals()
        results, stats = strategy.backtest(signals)
        
        print(f"\nRR {rr}:1")
        print(f"   Trades: {stats['total_trades']}")
        print(f"   Win Rate: {stats['win_rate']:.1f}%")
        print(f"   Profit Factor: {stats['profit_factor']:.2f}")
        print(f"   Lucro Total: {stats['total_profit_loss_r']:.1f}R")
        print(f"   Expectativa: {stats['avg_profit_loss_r']:.2f}R/trade")
    
    # Win Rate por padrão
    print("\n" + "=" * 80)
    print("WIN RATE POR PADRÃO")
    print("=" * 80)
    
    strategy = SMCStrategyFinalV3(
        df_sample,
        swing_length=5,
        risk_reward_ratio=1.0,
        entry_delay_candles=1,
        use_not_mitigated_filter=True,
        min_volume_ratio=1.5,
        min_ob_size_atr=0.5,
    )
    signals = strategy.generate_signals()
    results, stats = strategy.backtest(signals)
    
    pattern_stats = {}
    for pattern_type in PatternType:
        trades_with_pattern = [r for r in results if pattern_type in r.signal.patterns_detected]
        if len(trades_with_pattern) > 0:
            wins = sum(1 for r in trades_with_pattern if r.hit_tp)
            win_rate = wins / len(trades_with_pattern) * 100
            pattern_stats[pattern_type.value] = {
                'trades': len(trades_with_pattern),
                'wins': wins,
                'win_rate': win_rate
            }
    
    print(f"\n{'Padrão':<15} {'Trades':<10} {'Wins':<10} {'Win Rate':<10}")
    print("-" * 45)
    for pattern, pstats in sorted(pattern_stats.items(), key=lambda x: x[1]['win_rate'], reverse=True):
        print(f"{pattern:<15} {pstats['trades']:<10} {pstats['wins']:<10} {pstats['win_rate']:.1f}%")
