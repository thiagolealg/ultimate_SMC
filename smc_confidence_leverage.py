"""
Smart Money Concepts - Índice de Confiança para Alavancagem
===========================================================
Sistema de pontuação de 0-100 para determinar alavancagem de contratos

Fatores do Índice de Confiança:
1. Volume Ratio (0-25 pontos)
2. Tamanho do OB vs ATR (0-20 pontos)
3. Alinhamento com Tendência (0-20 pontos)
4. Presença de FVG (0-15 pontos)
5. Distância do Swing (0-10 pontos)
6. Força do Movimento de Confirmação (0-10 pontos)

Sistema de Alavancagem:
- Confiança 0-40: 1x (base)
- Confiança 41-60: 1.5x
- Confiança 61-75: 2x
- Confiança 76-85: 2.5x
- Confiança 86-100: 3x
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple, Dict


class SignalDirection(Enum):
    BULLISH = 1
    BEARISH = -1


@dataclass
class ConfidenceFactors:
    """Fatores que compõem o índice de confiança"""
    volume_score: float = 0.0          # 0-25 pontos
    size_score: float = 0.0            # 0-20 pontos
    trend_score: float = 0.0           # 0-20 pontos
    fvg_score: float = 0.0             # 0-15 pontos
    swing_distance_score: float = 0.0  # 0-10 pontos
    momentum_score: float = 0.0        # 0-10 pontos
    
    @property
    def total(self) -> float:
        """Retorna o índice de confiança total (0-100)"""
        return min(100.0, (
            self.volume_score + 
            self.size_score + 
            self.trend_score + 
            self.fvg_score + 
            self.swing_distance_score + 
            self.momentum_score
        ))
    
    def to_dict(self) -> Dict:
        return {
            'volume_score': self.volume_score,
            'size_score': self.size_score,
            'trend_score': self.trend_score,
            'fvg_score': self.fvg_score,
            'swing_distance_score': self.swing_distance_score,
            'momentum_score': self.momentum_score,
            'total': self.total,
        }


@dataclass
class TradeSignal:
    """Sinal de trade com índice de confiança"""
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
    # Índice de confiança
    confidence_factors: ConfidenceFactors = field(default_factory=ConfidenceFactors)
    # Alavancagem recomendada
    leverage: float = 1.0
    # Dados adicionais
    ob_size: float = 0.0
    volume_ratio: float = 0.0
    
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
    profit_loss_r: float  # Lucro em R (considerando alavancagem)
    hit_tp: bool
    hit_sl: bool
    duration_candles: int
    leverage_used: float


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


class SMCWithConfidence:
    """Smart Money Concepts com Índice de Confiança"""
    
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
        confirmation_strength = np.full(n, np.nan)  # Força do movimento de confirmação
        
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
                    
                    # Calcular força do movimento de confirmação
                    move_size = _close[i] - last_top_level
                    avg_range = np.mean(_high[max(0,i-20):i] - _low[max(0,i-20):i])
                    if avg_range > 0:
                        confirmation_strength[i] = move_size / avg_range
                    
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
                    
                    # Calcular força do movimento de confirmação
                    move_size = last_bottom_level - _close[i]
                    avg_range = np.mean(_high[max(0,i-20):i] - _low[max(0,i-20):i])
                    if avg_range > 0:
                        confirmation_strength[i] = move_size / avg_range
                    
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
            'ConfirmationStrength': confirmation_strength,
        }, index=ohlc.index)
    
    @classmethod
    def detect_fvg(cls, ohlc: pd.DataFrame, index: int, direction: int, lookback: int = 10) -> Tuple[bool, float]:
        """
        Detecta Fair Value Gap e retorna (presente, tamanho)
        """
        if index < 2:
            return False, 0.0
        
        max_gap = 0.0
        found = False
        
        for i in range(max(2, index - lookback), index):
            if direction == 1:  # Bullish FVG
                gap = ohlc['low'].iloc[i] - ohlc['high'].iloc[i-2]
                if gap > 0:
                    found = True
                    max_gap = max(max_gap, gap)
            else:  # Bearish FVG
                gap = ohlc['low'].iloc[i-2] - ohlc['high'].iloc[i]
                if gap > 0:
                    found = True
                    max_gap = max(max_gap, gap)
        
        return found, max_gap


class OrderBlockStrategyWithConfidence:
    """
    Estratégia de Order Block com Índice de Confiança para Alavancagem
    
    Sistema de Pontuação (0-100):
    - Volume Ratio: 0-25 pontos
    - Tamanho OB vs ATR: 0-20 pontos
    - Alinhamento com Tendência: 0-20 pontos
    - Presença de FVG: 0-15 pontos
    - Distância do Swing: 0-10 pontos
    - Força do Momentum: 0-10 pontos
    
    Alavancagem Recomendada:
    - 0-40: 1.0x
    - 41-60: 1.5x
    - 61-75: 2.0x
    - 76-85: 2.5x
    - 86-100: 3.0x
    """
    
    # Configuração de alavancagem por faixa de confiança
    LEVERAGE_TIERS = [
        (0, 40, 1.0),
        (41, 60, 1.5),
        (61, 75, 2.0),
        (76, 85, 2.5),
        (86, 100, 3.0),
    ]
    
    def __init__(
        self,
        ohlc: pd.DataFrame,
        swing_length: int = 5,
        risk_reward_ratio: float = 1.0,
        entry_delay_candles: int = 1,
        min_confidence: float = 0.0,  # Confiança mínima para entrar
        ema_fast: int = 20,
        ema_slow: int = 50,
    ):
        self.ohlc = validate_ohlc(ohlc)
        self.swing_length = swing_length
        self.risk_reward_ratio = risk_reward_ratio
        self.entry_delay_candles = entry_delay_candles
        self.min_confidence = min_confidence
        
        # Calcular indicadores
        self.swings = SMCWithConfidence.swing_highs_lows(self.ohlc, swing_length)
        self.order_blocks = SMCWithConfidence.order_blocks(self.ohlc, swing_length)
        
        # EMAs para tendência
        self.ohlc['ema_fast'] = self.ohlc['close'].ewm(span=ema_fast, adjust=False).mean()
        self.ohlc['ema_slow'] = self.ohlc['close'].ewm(span=ema_slow, adjust=False).mean()
        
        # ATR
        high_low = self.ohlc['high'] - self.ohlc['low']
        self.ohlc['atr'] = high_low.rolling(window=14).mean()
    
    def calculate_confidence(self, ob_index: int, ob_direction: int) -> ConfidenceFactors:
        """
        Calcula o índice de confiança detalhado para um Order Block
        """
        factors = ConfidenceFactors()
        
        ob_top = self.order_blocks['Top'].iloc[ob_index]
        ob_bottom = self.order_blocks['Bottom'].iloc[ob_index]
        ob_volume = self.order_blocks['Volume'].iloc[ob_index]
        ob_candle_idx = int(self.order_blocks['OBCandle'].iloc[ob_index])
        confirmation_strength = self.order_blocks['ConfirmationStrength'].iloc[ob_index]
        
        ob_size = ob_top - ob_bottom
        atr = self.ohlc['atr'].iloc[ob_index]
        
        # 1. VOLUME SCORE (0-25 pontos)
        # Volume > 1x média = 5 pontos
        # Volume > 1.5x média = 15 pontos
        # Volume > 2x média = 20 pontos
        # Volume > 3x média = 25 pontos
        avg_volume = self.ohlc['volume'].iloc[max(0, ob_index-20):ob_index].mean()
        if avg_volume > 0 and not np.isnan(ob_volume):
            volume_ratio = ob_volume / avg_volume
            if volume_ratio >= 3.0:
                factors.volume_score = 25.0
            elif volume_ratio >= 2.0:
                factors.volume_score = 20.0
            elif volume_ratio >= 1.5:
                factors.volume_score = 15.0
            elif volume_ratio >= 1.0:
                factors.volume_score = 5.0
        
        # 2. SIZE SCORE (0-20 pontos)
        # OB > 0.5 ATR = 5 pontos
        # OB > 1.0 ATR = 10 pontos
        # OB > 1.5 ATR = 15 pontos
        # OB > 2.0 ATR = 20 pontos
        if not np.isnan(atr) and atr > 0:
            size_ratio = ob_size / atr
            if size_ratio >= 2.0:
                factors.size_score = 20.0
            elif size_ratio >= 1.5:
                factors.size_score = 15.0
            elif size_ratio >= 1.0:
                factors.size_score = 10.0
            elif size_ratio >= 0.5:
                factors.size_score = 5.0
        
        # 3. TREND SCORE (0-20 pontos)
        # Alinhado com tendência de curto prazo (EMA 20 > EMA 50 para bullish)
        ema_fast = self.ohlc['ema_fast'].iloc[ob_index]
        ema_slow = self.ohlc['ema_slow'].iloc[ob_index]
        
        if not np.isnan(ema_fast) and not np.isnan(ema_slow):
            trend_bullish = ema_fast > ema_slow
            trend_bearish = ema_fast < ema_slow
            
            # Calcular força da tendência
            trend_strength = abs(ema_fast - ema_slow) / ema_slow * 100 if ema_slow > 0 else 0
            
            if (ob_direction == 1 and trend_bullish) or (ob_direction == -1 and trend_bearish):
                # Alinhado com tendência
                if trend_strength >= 2.0:
                    factors.trend_score = 20.0
                elif trend_strength >= 1.0:
                    factors.trend_score = 15.0
                elif trend_strength >= 0.5:
                    factors.trend_score = 10.0
                else:
                    factors.trend_score = 5.0
        
        # 4. FVG SCORE (0-15 pontos)
        # Presença de Fair Value Gap próximo ao OB
        fvg_present, fvg_size = SMCWithConfidence.detect_fvg(
            self.ohlc, ob_index, int(ob_direction)
        )
        if fvg_present:
            if not np.isnan(atr) and atr > 0:
                fvg_ratio = fvg_size / atr
                if fvg_ratio >= 1.0:
                    factors.fvg_score = 15.0
                elif fvg_ratio >= 0.5:
                    factors.fvg_score = 10.0
                else:
                    factors.fvg_score = 5.0
        
        # 5. SWING DISTANCE SCORE (0-10 pontos)
        # Quanto mais próximo do swing, melhor
        swing_idx = ob_candle_idx
        distance = ob_index - swing_idx
        if distance <= 5:
            factors.swing_distance_score = 10.0
        elif distance <= 10:
            factors.swing_distance_score = 7.0
        elif distance <= 20:
            factors.swing_distance_score = 4.0
        else:
            factors.swing_distance_score = 2.0
        
        # 6. MOMENTUM SCORE (0-10 pontos)
        # Força do movimento de confirmação
        if not np.isnan(confirmation_strength):
            if confirmation_strength >= 2.0:
                factors.momentum_score = 10.0
            elif confirmation_strength >= 1.5:
                factors.momentum_score = 7.0
            elif confirmation_strength >= 1.0:
                factors.momentum_score = 5.0
            elif confirmation_strength >= 0.5:
                factors.momentum_score = 3.0
        
        return factors
    
    def get_leverage(self, confidence: float) -> float:
        """Retorna a alavancagem recomendada baseada no índice de confiança"""
        for min_conf, max_conf, leverage in self.LEVERAGE_TIERS:
            if min_conf <= confidence <= max_conf:
                return leverage
        return 1.0
    
    def generate_signals(self) -> List[TradeSignal]:
        """Gera sinais com índice de confiança e alavancagem"""
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
            
            # Calcular índice de confiança
            confidence_factors = self.calculate_confidence(i, int(ob_direction))
            confidence = confidence_factors.total
            
            # Filtrar por confiança mínima
            if confidence < self.min_confidence:
                continue
            
            # Determinar alavancagem
            leverage = self.get_leverage(confidence)
            
            # Calcular volume ratio para registro
            avg_volume = self.ohlc['volume'].iloc[max(0, i-20):i].mean()
            volume_ratio = ob_volume / avg_volume if avg_volume > 0 else 1.0
            
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
                            ob_top=ob_top,
                            ob_bottom=ob_bottom,
                            risk_reward_ratio=self.risk_reward_ratio,
                            signal_candle_index=i,
                            ob_candle_index=int(ob_candle) if not np.isnan(ob_candle) else i,
                            confidence_factors=confidence_factors,
                            leverage=leverage,
                            ob_size=ob_size,
                            volume_ratio=volume_ratio,
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
                            ob_top=ob_top,
                            ob_bottom=ob_bottom,
                            risk_reward_ratio=self.risk_reward_ratio,
                            signal_candle_index=i,
                            ob_candle_index=int(ob_candle) if not np.isnan(ob_candle) else i,
                            confidence_factors=confidence_factors,
                            leverage=leverage,
                            ob_size=ob_size,
                            volume_ratio=volume_ratio,
                        )
                        signals.append(signal)
                        break
        
        return signals
    
    def backtest(self, signals: Optional[List[TradeSignal]] = None) -> Tuple[List[BacktestResult], Dict]:
        """Executa backtest com alavancagem"""
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
                
                # Calcular lucro em R com alavancagem
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
        
        # Calcular estatísticas
        if len(results) > 0:
            winning = [r for r in results if r.hit_tp]
            losing = [r for r in results if r.hit_sl]
            
            total_profit_r = sum(r.profit_loss_r for r in winning)
            total_loss_r = abs(sum(r.profit_loss_r for r in losing))
            
            stats = {
                'total_trades': len(results),
                'winning_trades': len(winning),
                'losing_trades': len(losing),
                'win_rate': len(winning) / len(results) * 100,
                'total_profit_loss': sum(r.profit_loss for r in results),
                'total_profit_loss_r': sum(r.profit_loss_r for r in results),
                'profit_factor': total_profit_r / total_loss_r if total_loss_r > 0 else float('inf'),
                'avg_leverage': np.mean([r.leverage_used for r in results]),
                'avg_duration': np.mean([r.duration_candles for r in results]),
            }
        else:
            stats = {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'total_profit_loss': 0,
                'total_profit_loss_r': 0,
                'profit_factor': 0,
                'avg_leverage': 0,
                'avg_duration': 0,
            }
        
        return results, stats


def analyze_confidence_performance():
    """Analisa a correlação entre confiança e Win Rate"""
    print("=" * 80)
    print("ANÁLISE DO ÍNDICE DE CONFIANÇA")
    print("=" * 80)
    
    # Carregar dados
    df = pd.read_csv('/home/ubuntu/smc_enhanced/data.csv')
    df.columns = [c.lower() for c in df.columns]
    df['time'] = pd.to_datetime(df['time'])
    df.set_index('time', inplace=True)
    if 'volume' not in df.columns:
        df['volume'] = df.get('tick_volume', df.get('real_volume', 1.0))
    
    print(f"\nDados: {len(df)} candles")
    
    # Criar estratégia
    strategy = OrderBlockStrategyWithConfidence(
        df,
        swing_length=5,
        risk_reward_ratio=1.0,
        entry_delay_candles=1,
        min_confidence=0.0,  # Sem filtro para análise
    )
    
    signals = strategy.generate_signals()
    results, stats = strategy.backtest(signals)
    
    print(f"\nTotal de sinais: {len(signals)}")
    print(f"Total de trades: {len(results)}")
    
    # Agrupar por faixa de confiança
    confidence_ranges = [
        (0, 30, "0-30 (Baixa)"),
        (31, 50, "31-50 (Média-Baixa)"),
        (51, 65, "51-65 (Média)"),
        (66, 80, "66-80 (Alta)"),
        (81, 100, "81-100 (Muito Alta)"),
    ]
    
    print("\n" + "=" * 80)
    print("WIN RATE POR FAIXA DE CONFIANÇA")
    print("=" * 80)
    print(f"\n{'Faixa':<25} {'Trades':<10} {'Wins':<10} {'Win Rate':<12} {'Alavancagem':<12} {'Lucro (R)':<12}")
    print("-" * 81)
    
    for min_conf, max_conf, label in confidence_ranges:
        range_results = [r for r in results if min_conf <= r.signal.confidence <= max_conf]
        
        if len(range_results) > 0:
            wins = len([r for r in range_results if r.hit_tp])
            win_rate = wins / len(range_results) * 100
            avg_leverage = np.mean([r.leverage_used for r in range_results])
            total_r = sum(r.profit_loss_r for r in range_results)
            
            print(f"{label:<25} {len(range_results):<10} {wins:<10} {win_rate:.1f}%{'':<6} {avg_leverage:.1f}x{'':<6} {total_r:.1f}R")
    
    # Análise por componente
    print("\n" + "=" * 80)
    print("IMPACTO DE CADA COMPONENTE NO WIN RATE")
    print("=" * 80)
    
    # Volume Score
    print("\n--- Volume Score ---")
    for threshold in [5, 15, 20, 25]:
        filtered = [r for r in results if r.signal.confidence_factors.volume_score >= threshold]
        if len(filtered) > 0:
            wins = len([r for r in filtered if r.hit_tp])
            wr = wins / len(filtered) * 100
            print(f"   Volume Score >= {threshold}: {len(filtered)} trades, Win Rate: {wr:.1f}%")
    
    # Trend Score
    print("\n--- Trend Score ---")
    for threshold in [5, 10, 15, 20]:
        filtered = [r for r in results if r.signal.confidence_factors.trend_score >= threshold]
        if len(filtered) > 0:
            wins = len([r for r in filtered if r.hit_tp])
            wr = wins / len(filtered) * 100
            print(f"   Trend Score >= {threshold}: {len(filtered)} trades, Win Rate: {wr:.1f}%")
    
    # FVG Score
    print("\n--- FVG Score ---")
    for threshold in [5, 10, 15]:
        filtered = [r for r in results if r.signal.confidence_factors.fvg_score >= threshold]
        if len(filtered) > 0:
            wins = len([r for r in filtered if r.hit_tp])
            wr = wins / len(filtered) * 100
            print(f"   FVG Score >= {threshold}: {len(filtered)} trades, Win Rate: {wr:.1f}%")
    
    # Comparação: Com vs Sem Alavancagem
    print("\n" + "=" * 80)
    print("COMPARAÇÃO: COM vs SEM ALAVANCAGEM")
    print("=" * 80)
    
    # Sem alavancagem (todos 1x)
    total_r_no_leverage = sum(
        strategy.risk_reward_ratio if r.hit_tp else -1.0 
        for r in results
    )
    
    # Com alavancagem
    total_r_with_leverage = sum(r.profit_loss_r for r in results)
    
    print(f"\n   Sem Alavancagem: {total_r_no_leverage:.1f}R")
    print(f"   Com Alavancagem: {total_r_with_leverage:.1f}R")
    print(f"   Ganho: {((total_r_with_leverage / total_r_no_leverage) - 1) * 100:.1f}%" if total_r_no_leverage != 0 else "   N/A")
    
    # Mostrar sistema de alavancagem
    print("\n" + "=" * 80)
    print("SISTEMA DE ALAVANCAGEM")
    print("=" * 80)
    print("""
    Confiança 0-40:   1.0x (base)
    Confiança 41-60:  1.5x
    Confiança 61-75:  2.0x
    Confiança 76-85:  2.5x
    Confiança 86-100: 3.0x
    """)


if __name__ == "__main__":
    analyze_confidence_performance()
