"""
Smart Money Concepts Enhanced - VERSÃO FINAL SEM LOOK-AHEAD BIAS
================================================================
Versão corrigida e otimizada que NÃO usa dados futuros.

Esta versão usa uma abordagem diferente para detecção de Order Blocks:
- Swings são detectados com confirmação de N candles PASSADOS
- Order Blocks são confirmados quando o preço rompe o swing
- Tudo é marcado no momento da CONFIRMAÇÃO, não da formação

Autor: Baseado em joshyattridge/smart-money-concepts
Versão: 3.0.0 - Final (No Look-Ahead)
"""

import pandas as pd
import numpy as np
from pandas import DataFrame
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass
from enum import Enum
from datetime import datetime


class SignalDirection(Enum):
    """Direção do sinal de trading"""
    BULLISH = 1
    BEARISH = -1


@dataclass
class TradeSignal:
    """Representa um sinal de trading"""
    index: int                      # Índice do candle de entrada
    direction: SignalDirection      # Direção do trade
    entry_price: float              # Preço de entrada
    stop_loss: float                # Stop Loss
    take_profit: float              # Take Profit
    confidence: float               # Confiança (0-100)
    ob_top: float                   # Topo do Order Block
    ob_bottom: float                # Fundo do Order Block
    risk_reward_ratio: float        # Ratio R:R
    signal_candle_index: int        # Índice do candle onde o OB foi confirmado
    ob_candle_index: int            # Índice do candle que forma o OB


@dataclass
class BacktestResult:
    """Resultado de um trade no backtest"""
    signal: TradeSignal
    entry_index: int
    exit_index: int
    exit_price: float
    profit_loss: float
    profit_loss_percent: float
    hit_tp: bool
    hit_sl: bool
    duration_candles: int


def validate_ohlc(ohlc: DataFrame) -> DataFrame:
    """Valida e normaliza DataFrame OHLCV"""
    ohlc = ohlc.copy()
    ohlc.columns = [c.lower() for c in ohlc.columns]
    
    required_cols = ['open', 'high', 'low', 'close']
    for col in required_cols:
        if col not in ohlc.columns:
            raise ValueError(f"Coluna '{col}' não encontrada")
    
    if 'volume' not in ohlc.columns:
        if 'tick_volume' in ohlc.columns:
            ohlc['volume'] = ohlc['tick_volume']
        elif 'real_volume' in ohlc.columns:
            ohlc['volume'] = ohlc['real_volume']
        else:
            ohlc['volume'] = 1.0
    
    return ohlc


class SMCFinal:
    """
    Smart Money Concepts - Versão Final SEM Look-Ahead Bias
    
    Abordagem:
    1. Swings são identificados usando apenas dados PASSADOS
    2. Um swing high é confirmado quando temos N candles com máximas menores
    3. Um swing low é confirmado quando temos N candles com mínimas maiores
    4. Order Blocks são marcados quando o preço ROMPE o swing
    """
    
    __version__ = "3.0.0-final"

    @classmethod
    def swing_highs_lows(cls, ohlc: DataFrame, swing_length: int = 5) -> DataFrame:
        """
        Swing Highs and Lows - SEM LOOK-AHEAD
        
        Um swing high no índice i é confirmado no índice i + swing_length
        quando todos os candles de i+1 até i+swing_length têm máximas menores.
        
        O swing é MARCADO no candle de CONFIRMAÇÃO (não no candle de formação).
        Isso garante que em tempo real, só vemos o swing quando ele é confirmado.
        """
        ohlc = validate_ohlc(ohlc)
        n = len(ohlc)
        
        if n < swing_length + 1:
            return pd.DataFrame({
                'HighLow': [np.nan] * n,
                'Level': [np.nan] * n,
                'SwingIndex': [np.nan] * n,  # Índice onde o swing foi formado
            })
        
        highs = ohlc['high'].values
        lows = ohlc['low'].values
        
        swing_type = np.full(n, np.nan)
        swing_level = np.full(n, np.nan)
        swing_index = np.full(n, np.nan)
        
        # Para cada candle, verificar se ele confirma um swing anterior
        for i in range(swing_length, n):
            # Verificar se o candle em (i - swing_length) é um swing high
            # Condição: todos os candles de (i - swing_length + 1) até i têm high menor
            potential_high_idx = i - swing_length
            is_swing_high = True
            
            for j in range(potential_high_idx + 1, i + 1):
                if highs[j] >= highs[potential_high_idx]:
                    is_swing_high = False
                    break
            
            if is_swing_high:
                # Verificar também que é maior que os swing_length candles anteriores
                is_highest = True
                for j in range(max(0, potential_high_idx - swing_length), potential_high_idx):
                    if highs[j] > highs[potential_high_idx]:
                        is_highest = False
                        break
                
                if is_highest:
                    # Marcar no candle de confirmação (i)
                    swing_type[i] = 1
                    swing_level[i] = highs[potential_high_idx]
                    swing_index[i] = potential_high_idx
            
            # Verificar swing low
            potential_low_idx = i - swing_length
            is_swing_low = True
            
            for j in range(potential_low_idx + 1, i + 1):
                if lows[j] <= lows[potential_low_idx]:
                    is_swing_low = False
                    break
            
            if is_swing_low:
                is_lowest = True
                for j in range(max(0, potential_low_idx - swing_length), potential_low_idx):
                    if lows[j] < lows[potential_low_idx]:
                        is_lowest = False
                        break
                
                if is_lowest and np.isnan(swing_type[i]):  # Não sobrescrever swing high
                    swing_type[i] = -1
                    swing_level[i] = lows[potential_low_idx]
                    swing_index[i] = potential_low_idx
        
        return pd.DataFrame({
            'HighLow': swing_type,
            'Level': swing_level,
            'SwingIndex': swing_index,
        })

    @classmethod
    def fvg(cls, ohlc: DataFrame) -> DataFrame:
        """Fair Value Gap - sem look-ahead (já era correto)"""
        ohlc = validate_ohlc(ohlc)
        n = len(ohlc)
        
        if n < 3:
            return pd.DataFrame({
                'FVG': [np.nan] * n,
                'Top': [np.nan] * n,
                'Bottom': [np.nan] * n,
                'MitigatedIndex': [np.nan] * n,
            })
        
        fvg = np.zeros(n, dtype=np.int32)
        top = np.zeros(n, dtype=np.float32)
        bottom = np.zeros(n, dtype=np.float32)
        mitigated_index = np.zeros(n, dtype=np.int32)
        
        for i in range(2, n):
            if ohlc['low'].iloc[i] > ohlc['high'].iloc[i-2]:
                fvg[i] = 1
                top[i] = ohlc['low'].iloc[i]
                bottom[i] = ohlc['high'].iloc[i-2]
            elif ohlc['high'].iloc[i] < ohlc['low'].iloc[i-2]:
                fvg[i] = -1
                top[i] = ohlc['low'].iloc[i-2]
                bottom[i] = ohlc['high'].iloc[i]
        
        # Mitigação
        for i in range(2, n):
            if fvg[i] != 0:
                for j in range(i + 1, n):
                    if fvg[i] == 1 and ohlc['low'].iloc[j] <= bottom[i]:
                        mitigated_index[i] = j
                        break
                    elif fvg[i] == -1 and ohlc['high'].iloc[j] >= top[i]:
                        mitigated_index[i] = j
                        break
        
        fvg = np.where(fvg != 0, fvg, np.nan)
        top = np.where(~np.isnan(fvg), top, np.nan)
        bottom = np.where(~np.isnan(fvg), bottom, np.nan)
        mitigated_index = np.where(~np.isnan(fvg), mitigated_index, np.nan)
        
        return pd.DataFrame({
            'FVG': fvg,
            'Top': top,
            'Bottom': bottom,
            'MitigatedIndex': mitigated_index,
        })

    @classmethod
    def ob(cls, ohlc: DataFrame, swing_length: int = 5) -> DataFrame:
        """
        Order Blocks - SEM LOOK-AHEAD
        
        Processo:
        1. Detectar swings confirmados (usando swing_highs_lows)
        2. Quando o preço FECHA acima de um swing high confirmado -> Bullish OB
        3. Quando o preço FECHA abaixo de um swing low confirmado -> Bearish OB
        4. O OB é marcado no candle de ROMPIMENTO
        
        O candle do OB é o último candle bearish (para bullish OB) ou
        bullish (para bearish OB) antes do rompimento.
        """
        ohlc = validate_ohlc(ohlc)
        n = len(ohlc)
        
        if n < swing_length * 2 + 1:
            return pd.DataFrame({
                'OB': [np.nan] * n,
                'Top': [np.nan] * n,
                'Bottom': [np.nan] * n,
                'OBVolume': [np.nan] * n,
                'Percentage': [np.nan] * n,
                'OBCandleIndex': [np.nan] * n,
                'MitigatedIndex': [np.nan] * n,
            })
        
        _open = ohlc['open'].values
        _high = ohlc['high'].values
        _low = ohlc['low'].values
        _close = ohlc['close'].values
        _volume = ohlc['volume'].values
        
        ob = np.zeros(n, dtype=np.int32)
        top_arr = np.zeros(n, dtype=np.float32)
        bottom_arr = np.zeros(n, dtype=np.float32)
        ob_volume = np.zeros(n, dtype=np.float32)
        percentage = np.zeros(n, dtype=np.float32)
        ob_candle_idx = np.zeros(n, dtype=np.int32)
        mitigated_idx = np.zeros(n, dtype=np.int32)
        
        # Rastrear swings confirmados que ainda não foram rompidos
        confirmed_highs = []  # Lista de (swing_index, level, confirmation_index)
        confirmed_lows = []
        
        # Rastrear OBs ativos para mitigação
        active_bullish = []
        active_bearish = []
        
        for i in range(swing_length, n):
            # Verificar se um novo swing foi confirmado neste candle
            potential_swing_idx = i - swing_length
            
            # Swing High
            if potential_swing_idx >= swing_length:
                is_swing_high = True
                # Verificar que é o mais alto nos swing_length candles depois
                for j in range(potential_swing_idx + 1, i + 1):
                    if _high[j] >= _high[potential_swing_idx]:
                        is_swing_high = False
                        break
                
                # Verificar que é o mais alto nos swing_length candles antes
                if is_swing_high:
                    for j in range(potential_swing_idx - swing_length, potential_swing_idx):
                        if _high[j] > _high[potential_swing_idx]:
                            is_swing_high = False
                            break
                
                if is_swing_high:
                    # Verificar se já não foi confirmado
                    already = any(h[0] == potential_swing_idx for h in confirmed_highs)
                    if not already:
                        confirmed_highs.append((potential_swing_idx, _high[potential_swing_idx], i))
            
            # Swing Low
            if potential_swing_idx >= swing_length:
                is_swing_low = True
                for j in range(potential_swing_idx + 1, i + 1):
                    if _low[j] <= _low[potential_swing_idx]:
                        is_swing_low = False
                        break
                
                if is_swing_low:
                    for j in range(potential_swing_idx - swing_length, potential_swing_idx):
                        if _low[j] < _low[potential_swing_idx]:
                            is_swing_low = False
                            break
                
                if is_swing_low:
                    already = any(l[0] == potential_swing_idx for l in confirmed_lows)
                    if not already:
                        confirmed_lows.append((potential_swing_idx, _low[potential_swing_idx], i))
            
            # Verificar rompimento de swing high (Bullish OB)
            for h_idx, (swing_idx, level, conf_idx) in enumerate(confirmed_highs.copy()):
                # Só considerar swings confirmados ANTES deste candle
                if conf_idx >= i:
                    continue
                
                # Rompimento: close acima do swing high
                if _close[i] > level:
                    # Encontrar o candle do OB (último bearish antes do rompimento)
                    ob_idx = i - 1
                    for j in range(i - 1, max(swing_idx, conf_idx), -1):
                        if _close[j] < _open[j]:  # Candle bearish
                            ob_idx = j
                            break
                    
                    # Marcar OB no candle atual (rompimento)
                    ob[i] = 1
                    top_arr[i] = _high[ob_idx]
                    bottom_arr[i] = _low[ob_idx]
                    ob_candle_idx[i] = ob_idx
                    
                    # Volume
                    vol = _volume[ob_idx]
                    if ob_idx > 0:
                        vol += _volume[ob_idx - 1]
                    ob_volume[i] = vol
                    
                    # Percentage (baseado em volume relativo)
                    avg_vol = _volume[max(0, i-20):i].mean() if i > 20 else _volume[:i].mean()
                    if avg_vol > 0:
                        percentage[i] = min(100, (vol / avg_vol) * 50)
                    else:
                        percentage[i] = 50
                    
                    active_bullish.append(i)
                    confirmed_highs.remove((swing_idx, level, conf_idx))
                    break
            
            # Verificar rompimento de swing low (Bearish OB)
            for l_idx, (swing_idx, level, conf_idx) in enumerate(confirmed_lows.copy()):
                if conf_idx >= i:
                    continue
                
                if _close[i] < level:
                    ob_idx = i - 1
                    for j in range(i - 1, max(swing_idx, conf_idx), -1):
                        if _close[j] > _open[j]:  # Candle bullish
                            ob_idx = j
                            break
                    
                    ob[i] = -1
                    top_arr[i] = _high[ob_idx]
                    bottom_arr[i] = _low[ob_idx]
                    ob_candle_idx[i] = ob_idx
                    
                    vol = _volume[ob_idx]
                    if ob_idx > 0:
                        vol += _volume[ob_idx - 1]
                    ob_volume[i] = vol
                    
                    avg_vol = _volume[max(0, i-20):i].mean() if i > 20 else _volume[:i].mean()
                    if avg_vol > 0:
                        percentage[i] = min(100, (vol / avg_vol) * 50)
                    else:
                        percentage[i] = 50
                    
                    active_bearish.append(i)
                    confirmed_lows.remove((swing_idx, level, conf_idx))
                    break
            
            # Verificar mitigação
            for ob_i in active_bullish.copy():
                if _low[i] < bottom_arr[ob_i]:
                    mitigated_idx[ob_i] = i
                    active_bullish.remove(ob_i)
            
            for ob_i in active_bearish.copy():
                if _high[i] > top_arr[ob_i]:
                    mitigated_idx[ob_i] = i
                    active_bearish.remove(ob_i)
        
        # Converter zeros para NaN
        ob = np.where(ob != 0, ob, np.nan)
        top_arr = np.where(~np.isnan(ob), top_arr, np.nan)
        bottom_arr = np.where(~np.isnan(ob), bottom_arr, np.nan)
        ob_volume = np.where(~np.isnan(ob), ob_volume, np.nan)
        percentage = np.where(~np.isnan(ob), percentage, np.nan)
        ob_candle_idx = np.where(~np.isnan(ob), ob_candle_idx, np.nan)
        mitigated_idx = np.where(~np.isnan(ob), mitigated_idx, np.nan)
        
        return pd.DataFrame({
            'OB': ob,
            'Top': top_arr,
            'Bottom': bottom_arr,
            'OBVolume': ob_volume,
            'Percentage': percentage,
            'OBCandleIndex': ob_candle_idx,
            'MitigatedIndex': mitigated_idx,
        })

    @classmethod
    def bos_choch(cls, ohlc: DataFrame, swing_length: int = 5) -> DataFrame:
        """BOS/CHoCH - SEM LOOK-AHEAD"""
        ohlc = validate_ohlc(ohlc)
        n = len(ohlc)
        
        if n < swing_length * 2 + 1:
            return pd.DataFrame({
                'BOS': [np.nan] * n,
                'CHOCH': [np.nan] * n,
                'Level': [np.nan] * n,
            })
        
        _high = ohlc['high'].values
        _low = ohlc['low'].values
        _close = ohlc['close'].values
        
        bos = np.zeros(n, dtype=np.int32)
        choch = np.zeros(n, dtype=np.int32)
        level = np.zeros(n, dtype=np.float32)
        
        confirmed_highs = []
        confirmed_lows = []
        trend = 0
        
        for i in range(swing_length, n):
            potential_idx = i - swing_length
            
            # Confirmar swings
            if potential_idx >= swing_length:
                # Swing High
                is_high = True
                for j in range(potential_idx + 1, i + 1):
                    if _high[j] >= _high[potential_idx]:
                        is_high = False
                        break
                if is_high:
                    for j in range(potential_idx - swing_length, potential_idx):
                        if _high[j] > _high[potential_idx]:
                            is_high = False
                            break
                if is_high:
                    already = any(h[0] == potential_idx for h in confirmed_highs)
                    if not already:
                        confirmed_highs.append((potential_idx, _high[potential_idx], i))
                
                # Swing Low
                is_low = True
                for j in range(potential_idx + 1, i + 1):
                    if _low[j] <= _low[potential_idx]:
                        is_low = False
                        break
                if is_low:
                    for j in range(potential_idx - swing_length, potential_idx):
                        if _low[j] < _low[potential_idx]:
                            is_low = False
                            break
                if is_low:
                    already = any(l[0] == potential_idx for l in confirmed_lows)
                    if not already:
                        confirmed_lows.append((potential_idx, _low[potential_idx], i))
            
            # Verificar BOS/CHoCH
            for h_idx, (swing_idx, h_level, conf_idx) in enumerate(confirmed_highs.copy()):
                if conf_idx >= i:
                    continue
                if _close[i] > h_level:
                    if trend == 1:
                        bos[i] = 1
                    else:
                        choch[i] = 1
                        trend = 1
                    level[i] = h_level
                    confirmed_highs.remove((swing_idx, h_level, conf_idx))
                    break
            
            for l_idx, (swing_idx, l_level, conf_idx) in enumerate(confirmed_lows.copy()):
                if conf_idx >= i:
                    continue
                if _close[i] < l_level:
                    if trend == -1:
                        bos[i] = -1
                    else:
                        choch[i] = -1
                        trend = -1
                    level[i] = l_level
                    confirmed_lows.remove((swing_idx, l_level, conf_idx))
                    break
        
        bos = np.where(bos != 0, bos, np.nan)
        choch = np.where(choch != 0, choch, np.nan)
        level = np.where((~np.isnan(bos)) | (~np.isnan(choch)), level, np.nan)
        
        return pd.DataFrame({
            'BOS': bos,
            'CHOCH': choch,
            'Level': level,
        })


class OrderBlockStrategyFinal:
    """
    Estratégia Order Block 3:1 - VERSÃO FINAL SEM LOOK-AHEAD
    
    Garantias:
    1. Order Blocks são identificados apenas após confirmação
    2. Sinais são gerados apenas após o OB ser confirmado
    3. Entradas ocorrem apenas em candles APÓS o sinal
    4. Nenhum dado futuro é usado
    """
    
    def __init__(
        self,
        ohlc: DataFrame,
        swing_length: int = 5,
        risk_reward_ratio: float = 3.0,
        min_confidence: float = 50.0,
        entry_delay_candles: int = 1,
    ):
        self.ohlc = validate_ohlc(ohlc)
        self.swing_length = swing_length
        self.risk_reward_ratio = risk_reward_ratio
        self.min_confidence = min_confidence
        self.entry_delay_candles = max(1, entry_delay_candles)
        
        # Calcular indicadores
        self.order_blocks = SMCFinal.ob(self.ohlc, swing_length)
        self.fvg = SMCFinal.fvg(self.ohlc)
        self.bos_choch = SMCFinal.bos_choch(self.ohlc, swing_length)
    
    def calculate_confidence(self, ob_index: int) -> float:
        """Calcula confiança usando apenas dados até ob_index"""
        confidence = 0.0
        
        # 1. Percentage do OB (0-25 pontos)
        ob_percentage = self.order_blocks['Percentage'].iloc[ob_index]
        if not np.isnan(ob_percentage):
            confidence += min(25, ob_percentage / 4)
        
        # 2. FVG próximo (apenas ANTES do OB)
        window = 10
        start_idx = max(0, ob_index - window)
        end_idx = ob_index
        
        fvg_nearby = self.fvg['FVG'].iloc[start_idx:end_idx]
        ob_direction = self.order_blocks['OB'].iloc[ob_index]
        
        if not np.isnan(ob_direction):
            matching_fvg = fvg_nearby[fvg_nearby == ob_direction].count()
            confidence += min(25, matching_fvg * 8)
        
        # 3. BOS/CHoCH (apenas ANTES do OB)
        bos_nearby = self.bos_choch['BOS'].iloc[start_idx:end_idx]
        choch_nearby = self.bos_choch['CHOCH'].iloc[start_idx:end_idx]
        
        if not np.isnan(ob_direction):
            matching_bos = bos_nearby[bos_nearby == ob_direction].count()
            matching_choch = choch_nearby[choch_nearby == ob_direction].count()
            confidence += min(15, matching_bos * 5)
            confidence += min(10, matching_choch * 10)
        
        # 4. Tamanho do OB (0-15 pontos)
        ob_top = self.order_blocks['Top'].iloc[ob_index]
        ob_bottom = self.order_blocks['Bottom'].iloc[ob_index]
        
        if not np.isnan(ob_top) and not np.isnan(ob_bottom):
            ob_size = abs(ob_top - ob_bottom)
            avg_candle = (self.ohlc['high'].iloc[:ob_index] - self.ohlc['low'].iloc[:ob_index]).mean()
            
            if avg_candle > 0:
                ratio = ob_size / avg_candle
                if 0.5 <= ratio <= 2.0:
                    confidence += 15
                elif 0.3 <= ratio <= 3.0:
                    confidence += 10
                else:
                    confidence += 5
        
        # 5. Volume (0-10 pontos)
        ob_volume = self.order_blocks['OBVolume'].iloc[ob_index]
        if not np.isnan(ob_volume):
            avg_vol = self.ohlc['volume'].iloc[:ob_index].mean()
            if avg_vol > 0:
                vol_ratio = ob_volume / (avg_vol * 3)
                confidence += min(10, vol_ratio * 5)
        
        return min(100, confidence)
    
    def generate_signals(self) -> List[TradeSignal]:
        """Gera sinais SEM look-ahead bias"""
        signals = []
        n = len(self.ohlc)
        
        for i in range(n):
            ob_direction = self.order_blocks['OB'].iloc[i]
            
            if np.isnan(ob_direction):
                continue
            
            ob_top = self.order_blocks['Top'].iloc[i]
            ob_bottom = self.order_blocks['Bottom'].iloc[i]
            ob_candle = self.order_blocks['OBCandleIndex'].iloc[i]
            
            if np.isnan(ob_top) or np.isnan(ob_bottom):
                continue
            
            confidence = self.calculate_confidence(i)
            
            if confidence < self.min_confidence:
                continue
            
            # Procurar entrada APÓS o delay
            entry_start = i + self.entry_delay_candles
            
            for j in range(entry_start, min(n, i + 100)):
                # Verificar mitigação
                mitigated = self.order_blocks['MitigatedIndex'].iloc[i]
                if not np.isnan(mitigated) and j > mitigated:
                    break
                
                current_high = self.ohlc['high'].iloc[j]
                current_low = self.ohlc['low'].iloc[j]
                
                # Bullish OB
                if ob_direction == 1:
                    if current_low <= ob_top:
                        entry_price = (ob_top + ob_bottom) / 2
                        stop_loss = ob_bottom - (ob_top - ob_bottom) * 0.1
                        risk = entry_price - stop_loss
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
                        )
                        signals.append(signal)
                        break
                
                # Bearish OB
                elif ob_direction == -1:
                    if current_high >= ob_bottom:
                        entry_price = (ob_top + ob_bottom) / 2
                        stop_loss = ob_top + (ob_top - ob_bottom) * 0.1
                        risk = stop_loss - entry_price
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
            
            for j in range(entry_index + 1, n):
                high = self.ohlc['high'].iloc[j]
                low = self.ohlc['low'].iloc[j]
                
                if signal.direction == SignalDirection.BULLISH:
                    if low <= signal.stop_loss:
                        exit_index = j
                        exit_price = signal.stop_loss
                        hit_sl = True
                        break
                    if high >= signal.take_profit:
                        exit_index = j
                        exit_price = signal.take_profit
                        hit_tp = True
                        break
                
                elif signal.direction == SignalDirection.BEARISH:
                    if high >= signal.stop_loss:
                        exit_index = j
                        exit_price = signal.stop_loss
                        hit_sl = True
                        break
                    if low <= signal.take_profit:
                        exit_index = j
                        exit_price = signal.take_profit
                        hit_tp = True
                        break
            
            if exit_index is None:
                continue
            
            if signal.direction == SignalDirection.BULLISH:
                profit_loss = exit_price - signal.entry_price
            else:
                profit_loss = signal.entry_price - exit_price
            
            profit_loss_percent = (profit_loss / signal.entry_price) * 100
            
            result = BacktestResult(
                signal=signal,
                entry_index=entry_index,
                exit_index=exit_index,
                exit_price=exit_price,
                profit_loss=profit_loss,
                profit_loss_percent=profit_loss_percent,
                hit_tp=hit_tp,
                hit_sl=hit_sl,
                duration_candles=exit_index - entry_index,
            )
            results.append(result)
        
        # Estatísticas
        if len(results) == 0:
            stats = {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0.0,
                'total_profit_loss': 0.0,
                'avg_profit_loss': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0,
                'profit_factor': 0.0,
                'avg_confidence': 0.0,
                'avg_duration': 0.0,
                'hit_tp_count': 0,
                'hit_sl_count': 0,
            }
        else:
            winning = [r for r in results if r.profit_loss > 0]
            losing = [r for r in results if r.profit_loss <= 0]
            
            total_wins = sum(r.profit_loss for r in winning)
            total_losses = abs(sum(r.profit_loss for r in losing))
            
            stats = {
                'total_trades': len(results),
                'winning_trades': len(winning),
                'losing_trades': len(losing),
                'win_rate': (len(winning) / len(results)) * 100,
                'total_profit_loss': sum(r.profit_loss for r in results),
                'avg_profit_loss': np.mean([r.profit_loss for r in results]),
                'avg_win': np.mean([r.profit_loss for r in winning]) if winning else 0.0,
                'avg_loss': np.mean([r.profit_loss for r in losing]) if losing else 0.0,
                'profit_factor': total_wins / total_losses if total_losses > 0 else float('inf'),
                'avg_confidence': np.mean([r.signal.confidence for r in results]),
                'avg_duration': np.mean([r.duration_candles for r in results]),
                'hit_tp_count': sum(1 for r in results if r.hit_tp),
                'hit_sl_count': sum(1 for r in results if r.hit_sl),
            }
        
        return results, stats
    
    def get_analysis_dataframe(self) -> DataFrame:
        """Retorna DataFrame com análise completa"""
        df = self.ohlc.copy()
        
        for col in self.order_blocks.columns:
            df[f'OB_{col}'] = self.order_blocks[col].values
        
        for col in self.fvg.columns:
            df[f'FVG_{col}'] = self.fvg[col].values
        
        for col in self.bos_choch.columns:
            df[f'BOSCHOCH_{col}'] = self.bos_choch[col].values
        
        confidence = np.full(len(df), np.nan)
        for i in range(len(df)):
            if not np.isnan(self.order_blocks['OB'].iloc[i]):
                confidence[i] = self.calculate_confidence(i)
        df['OB_Confidence'] = confidence
        
        return df


def run_tests():
    """Executa testes de validação"""
    print("=" * 70)
    print("TESTES - SMC FINAL (SEM LOOK-AHEAD)")
    print("=" * 70)
    
    # Carregar dados reais
    df = pd.read_csv('/home/ubuntu/smc_enhanced/data.csv')
    df.columns = [c.lower() for c in df.columns]
    df['time'] = pd.to_datetime(df['time'])
    df.set_index('time', inplace=True)
    if 'volume' not in df.columns:
        df['volume'] = df.get('tick_volume', df.get('real_volume', 1.0))
    
    # Usar amostra
    df = df.tail(20000)
    print(f"\nDados: {len(df)} candles")
    
    # Testar Order Blocks
    print("\n1. ORDER BLOCKS:")
    ob = SMCFinal.ob(df, swing_length=5)
    valid_obs = ob[ob['OB'].notna()]
    print(f"   Detectados: {len(valid_obs)}")
    print(f"   Bullish: {(valid_obs['OB'] == 1).sum()}")
    print(f"   Bearish: {(valid_obs['OB'] == -1).sum()}")
    
    # Verificar look-ahead
    violations = 0
    df_reset = df.reset_index()
    for i, idx in enumerate(valid_obs.index):
        ob_candle = valid_obs.loc[idx, 'OBCandleIndex']
        # O índice numérico do OB no DataFrame
        try:
            ob_idx = df_reset[df_reset['time'] == idx].index[0] if isinstance(idx, pd.Timestamp) else idx
        except:
            ob_idx = i
        if not np.isnan(ob_candle) and ob_candle > ob_idx:
            violations += 1
    print(f"   Violações de look-ahead: {violations}")
    
    # Testar estratégia
    print("\n2. ESTRATÉGIA:")
    for conf in [30, 40, 50]:
        strategy = OrderBlockStrategyFinal(
            df,
            swing_length=5,
            risk_reward_ratio=3.0,
            min_confidence=conf,
            entry_delay_candles=1,
        )
        
        signals = strategy.generate_signals()
        
        # Verificar look-ahead
        signal_violations = 0
        for s in signals:
            if s.index <= s.signal_candle_index:
                signal_violations += 1
        
        print(f"\n   Confiança {conf}%:")
        print(f"   Sinais: {len(signals)}")
        print(f"   Violações: {signal_violations}")
        
        if len(signals) > 0:
            results, stats = strategy.backtest(signals)
            print(f"   Win Rate: {stats['win_rate']:.1f}%")
            print(f"   Profit Factor: {stats['profit_factor']:.2f}")
            print(f"   P/L Total: {stats['total_profit_loss']:.2f}")
    
    print("\n" + "=" * 70)
    print("TESTES CONCLUÍDOS")
    print("=" * 70)


if __name__ == "__main__":
    run_tests()
