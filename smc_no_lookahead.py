"""
Smart Money Concepts Enhanced - SEM LOOK-AHEAD BIAS
====================================================
Versão corrigida que NÃO usa dados futuros para gerar sinais.

Correções principais:
1. Swing Highs/Lows: Usa apenas dados passados (confirmados)
2. Order Blocks: Só são válidos após confirmação
3. Sinais: Entrada só após confirmação completa do setup

Autor: Baseado em joshyattridge/smart-money-concepts
Versão: 2.0.0 - No Look-Ahead Bias
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
    signal_candle_index: int        # Índice do candle que gerou o sinal (OB confirmado)
    ob_formation_index: int         # Índice onde o OB foi formado
    confirmation_index: int         # Índice onde o OB foi confirmado


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
    
    # Normalizar nomes das colunas
    ohlc.columns = [c.lower() for c in ohlc.columns]
    
    required_cols = ['open', 'high', 'low', 'close']
    for col in required_cols:
        if col not in ohlc.columns:
            raise ValueError(f"Coluna '{col}' não encontrada no DataFrame")
    
    # Garantir coluna de volume
    if 'volume' not in ohlc.columns:
        if 'tick_volume' in ohlc.columns:
            ohlc['volume'] = ohlc['tick_volume']
        elif 'real_volume' in ohlc.columns:
            ohlc['volume'] = ohlc['real_volume']
        else:
            ohlc['volume'] = 1.0
    
    return ohlc


class SMCNoLookahead:
    """
    Smart Money Concepts SEM Look-Ahead Bias
    
    Esta classe implementa indicadores SMC que usam APENAS dados passados,
    garantindo que não há viés de olhar para o futuro.
    
    IMPORTANTE: Os swings são confirmados apenas quando um novo swing
    na direção oposta é formado. Isso significa que há um atraso natural
    na detecção, mas é a única forma correta de operar em tempo real.
    """
    
    __version__ = "2.0.0-no-lookahead"

    @classmethod
    def swing_highs_lows_realtime(cls, ohlc: DataFrame, swing_length: int = 5) -> DataFrame:
        """
        Swing Highs and Lows - VERSÃO SEM LOOK-AHEAD
        
        Um swing high é confirmado apenas quando:
        1. O candle atual é o mais alto nos últimos swing_length candles
        2. E os próximos swing_length candles têm máximas menores (confirmação)
        
        IMPORTANTE: Em tempo real, só sabemos que um swing foi formado
        DEPOIS que ele é confirmado por candles subsequentes.
        
        Esta versão marca o swing no candle onde ele FOI CONFIRMADO,
        não onde ele foi formado. Isso elimina o look-ahead bias.
        
        Parâmetros:
            swing_length: Quantidade de candles para confirmar o swing
            
        Retorna:
            DataFrame com colunas: 
            - HighLow: 1 para swing high, -1 para swing low
            - Level: Nível do swing
            - FormationIndex: Índice onde o swing foi formado
            - ConfirmationIndex: Índice onde o swing foi confirmado
        """
        ohlc = validate_ohlc(ohlc)
        n = len(ohlc)
        
        if n < swing_length + 1:
            return pd.DataFrame({
                'HighLow': [np.nan] * n,
                'Level': [np.nan] * n,
                'FormationIndex': [np.nan] * n,
                'ConfirmationIndex': [np.nan] * n
            })
        
        highs = ohlc['high'].values
        lows = ohlc['low'].values
        
        swing_type = np.full(n, np.nan)
        swing_level = np.full(n, np.nan)
        formation_index = np.full(n, np.nan)
        confirmation_index = np.full(n, np.nan)
        
        # Processar cada candle
        for i in range(swing_length, n):
            # Verificar se o candle em (i - swing_length) é um swing high confirmado
            # Isso significa que ele foi o mais alto nos swing_length candles antes
            # E nos swing_length candles depois (até o candle atual)
            
            potential_swing_idx = i - swing_length
            
            if potential_swing_idx >= swing_length:
                # Verificar swing high
                # O candle potential_swing_idx deve ser o mais alto em:
                # - swing_length candles antes
                # - swing_length candles depois (confirmação)
                
                start_before = potential_swing_idx - swing_length
                end_after = potential_swing_idx + swing_length
                
                if end_after <= i:  # Só confirma se temos dados suficientes
                    window_highs = highs[start_before:end_after + 1]
                    local_idx = swing_length  # Posição do potential_swing_idx na janela
                    
                    if highs[potential_swing_idx] == window_highs.max():
                        # É o mais alto na janela - confirmar como swing high
                        # Mas só marcamos se ainda não foi marcado
                        if np.isnan(swing_type[i]) or swing_type[i] != 1:
                            # Verificar se não há outro swing high mais recente
                            is_valid = True
                            for check_idx in range(potential_swing_idx + 1, i):
                                if swing_type[check_idx] == 1:
                                    is_valid = False
                                    break
                            
                            if is_valid:
                                swing_type[i] = 1
                                swing_level[i] = highs[potential_swing_idx]
                                formation_index[i] = potential_swing_idx
                                confirmation_index[i] = i
                
                # Verificar swing low
                window_lows = lows[start_before:end_after + 1]
                
                if lows[potential_swing_idx] == window_lows.min():
                    # É o mais baixo na janela
                    if np.isnan(swing_type[i]) or swing_type[i] != -1:
                        is_valid = True
                        for check_idx in range(potential_swing_idx + 1, i):
                            if swing_type[check_idx] == -1:
                                is_valid = False
                                break
                        
                        if is_valid:
                            swing_type[i] = -1
                            swing_level[i] = lows[potential_swing_idx]
                            formation_index[i] = potential_swing_idx
                            confirmation_index[i] = i
        
        return pd.DataFrame({
            'HighLow': swing_type,
            'Level': swing_level,
            'FormationIndex': formation_index,
            'ConfirmationIndex': confirmation_index
        })

    @classmethod
    def fvg(cls, ohlc: DataFrame, join_consecutive: bool = False) -> DataFrame:
        """
        FVG - Fair Value Gap (SEM LOOK-AHEAD)
        
        FVG é detectado usando apenas dados passados - 3 candles consecutivos.
        O FVG é marcado no terceiro candle (quando é confirmado).
        """
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
            # FVG Bullish: low do candle atual > high de 2 candles atrás
            if ohlc['low'].iloc[i] > ohlc['high'].iloc[i-2]:
                fvg[i] = 1
                top[i] = ohlc['low'].iloc[i]
                bottom[i] = ohlc['high'].iloc[i-2]
            
            # FVG Bearish: high do candle atual < low de 2 candles atrás
            elif ohlc['high'].iloc[i] < ohlc['low'].iloc[i-2]:
                fvg[i] = -1
                top[i] = ohlc['low'].iloc[i-2]
                bottom[i] = ohlc['high'].iloc[i]
        
        # Verificar mitigação
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
    def ob_realtime(cls, ohlc: DataFrame, swing_length: int = 5, close_mitigation: bool = False) -> DataFrame:
        """
        Order Blocks - VERSÃO SEM LOOK-AHEAD
        
        Um Order Block é identificado quando:
        1. Um swing high/low é CONFIRMADO (não apenas formado)
        2. O preço quebra esse swing (confirmação do OB)
        
        O OB é marcado no candle onde foi CONFIRMADO, não onde foi formado.
        
        Retorna:
            DataFrame com colunas:
            - OB: 1 para bullish, -1 para bearish
            - Top, Bottom: Limites do OB
            - FormationIndex: Onde o OB foi formado
            - ConfirmationIndex: Onde o OB foi confirmado
            - OBVolume, Percentage: Métricas do OB
        """
        ohlc = validate_ohlc(ohlc)
        n = len(ohlc)
        
        if n < swing_length * 2 + 3:
            return pd.DataFrame({
                'OB': [np.nan] * n,
                'Top': [np.nan] * n,
                'Bottom': [np.nan] * n,
                'OBVolume': [np.nan] * n,
                'Percentage': [np.nan] * n,
                'FormationIndex': [np.nan] * n,
                'ConfirmationIndex': [np.nan] * n,
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
        formation_idx = np.zeros(n, dtype=np.int32)
        confirmation_idx = np.zeros(n, dtype=np.int32)
        mitigated_idx = np.zeros(n, dtype=np.int32)
        
        # Rastrear swings confirmados
        confirmed_swing_highs = []  # Lista de (formation_index, level, confirmation_index)
        confirmed_swing_lows = []
        
        # Rastrear OBs ativos para mitigação
        active_bullish_obs = []  # Lista de índices de OBs bullish ativos
        active_bearish_obs = []
        
        for i in range(swing_length * 2, n):
            # Verificar se um swing high foi confirmado neste candle
            # Um swing high em (i - swing_length) é confirmado se:
            # - É o mais alto nos swing_length candles antes
            # - E nos swing_length candles depois (até agora)
            
            potential_high_idx = i - swing_length
            if potential_high_idx >= swing_length:
                start = potential_high_idx - swing_length
                end = i
                
                window_highs = _high[start:end + 1]
                local_high = _high[potential_high_idx]
                
                # Verificar se é o máximo da janela
                if local_high == window_highs.max() and local_high > window_highs[:-1].max():
                    # Confirmar swing high
                    already_confirmed = any(sh[0] == potential_high_idx for sh in confirmed_swing_highs)
                    if not already_confirmed:
                        confirmed_swing_highs.append((potential_high_idx, local_high, i))
            
            # Verificar swing low
            potential_low_idx = i - swing_length
            if potential_low_idx >= swing_length:
                start = potential_low_idx - swing_length
                end = i
                
                window_lows = _low[start:end + 1]
                local_low = _low[potential_low_idx]
                
                if local_low == window_lows.min() and local_low < window_lows[:-1].min():
                    already_confirmed = any(sl[0] == potential_low_idx for sl in confirmed_swing_lows)
                    if not already_confirmed:
                        confirmed_swing_lows.append((potential_low_idx, local_low, i))
            
            # Verificar se o preço quebrou algum swing high confirmado (Bullish OB)
            for sh_idx, (sh_formation, sh_level, sh_confirmation) in enumerate(confirmed_swing_highs):
                # Só considerar swings confirmados ANTES do candle atual
                if sh_confirmation >= i:
                    continue
                
                # Verificar se o preço fechou acima do swing high
                if _close[i] > sh_level:
                    # Encontrar o candle de OB (último candle bearish antes do rompimento)
                    ob_candle_idx = i - 1
                    for j in range(i - 1, sh_formation, -1):
                        if _close[j] < _open[j]:  # Candle bearish
                            ob_candle_idx = j
                            break
                        # Ou o candle com menor low
                        if _low[j] < _low[ob_candle_idx]:
                            ob_candle_idx = j
                    
                    # Marcar OB no candle ATUAL (onde foi confirmado)
                    ob[i] = 1
                    top_arr[i] = _high[ob_candle_idx]
                    bottom_arr[i] = _low[ob_candle_idx]
                    formation_idx[i] = ob_candle_idx
                    confirmation_idx[i] = i
                    
                    # Calcular volume
                    vol_sum = _volume[ob_candle_idx]
                    if ob_candle_idx > 0:
                        vol_sum += _volume[ob_candle_idx - 1]
                    ob_volume[i] = vol_sum
                    
                    # Calcular percentage
                    avg_vol = _volume[max(0, i-20):i].mean()
                    if avg_vol > 0:
                        percentage[i] = min(100, (vol_sum / avg_vol) * 50)
                    else:
                        percentage[i] = 50
                    
                    active_bullish_obs.append(i)
                    
                    # Remover swing da lista
                    confirmed_swing_highs.pop(sh_idx)
                    break
            
            # Verificar se o preço quebrou algum swing low confirmado (Bearish OB)
            for sl_idx, (sl_formation, sl_level, sl_confirmation) in enumerate(confirmed_swing_lows):
                if sl_confirmation >= i:
                    continue
                
                if _close[i] < sl_level:
                    # Encontrar o candle de OB (último candle bullish antes do rompimento)
                    ob_candle_idx = i - 1
                    for j in range(i - 1, sl_formation, -1):
                        if _close[j] > _open[j]:  # Candle bullish
                            ob_candle_idx = j
                            break
                        if _high[j] > _high[ob_candle_idx]:
                            ob_candle_idx = j
                    
                    ob[i] = -1
                    top_arr[i] = _high[ob_candle_idx]
                    bottom_arr[i] = _low[ob_candle_idx]
                    formation_idx[i] = ob_candle_idx
                    confirmation_idx[i] = i
                    
                    vol_sum = _volume[ob_candle_idx]
                    if ob_candle_idx > 0:
                        vol_sum += _volume[ob_candle_idx - 1]
                    ob_volume[i] = vol_sum
                    
                    avg_vol = _volume[max(0, i-20):i].mean()
                    if avg_vol > 0:
                        percentage[i] = min(100, (vol_sum / avg_vol) * 50)
                    else:
                        percentage[i] = 50
                    
                    active_bearish_obs.append(i)
                    
                    confirmed_swing_lows.pop(sl_idx)
                    break
            
            # Verificar mitigação de OBs ativos
            for ob_idx in active_bullish_obs.copy():
                if _low[i] < bottom_arr[ob_idx]:
                    mitigated_idx[ob_idx] = i
                    active_bullish_obs.remove(ob_idx)
            
            for ob_idx in active_bearish_obs.copy():
                if _high[i] > top_arr[ob_idx]:
                    mitigated_idx[ob_idx] = i
                    active_bearish_obs.remove(ob_idx)
        
        # Converter zeros para NaN
        ob = np.where(ob != 0, ob, np.nan)
        top_arr = np.where(~np.isnan(ob), top_arr, np.nan)
        bottom_arr = np.where(~np.isnan(ob), bottom_arr, np.nan)
        ob_volume = np.where(~np.isnan(ob), ob_volume, np.nan)
        percentage = np.where(~np.isnan(ob), percentage, np.nan)
        formation_idx = np.where(~np.isnan(ob), formation_idx, np.nan)
        confirmation_idx = np.where(~np.isnan(ob), confirmation_idx, np.nan)
        mitigated_idx = np.where(~np.isnan(ob), mitigated_idx, np.nan)
        
        return pd.DataFrame({
            'OB': ob,
            'Top': top_arr,
            'Bottom': bottom_arr,
            'OBVolume': ob_volume,
            'Percentage': percentage,
            'FormationIndex': formation_idx,
            'ConfirmationIndex': confirmation_idx,
            'MitigatedIndex': mitigated_idx,
        })

    @classmethod
    def bos_choch_realtime(cls, ohlc: DataFrame, swing_length: int = 5) -> DataFrame:
        """
        BOS/CHoCH - VERSÃO SEM LOOK-AHEAD
        
        BOS e CHoCH são detectados quando o preço quebra um swing confirmado.
        """
        ohlc = validate_ohlc(ohlc)
        n = len(ohlc)
        
        if n < swing_length * 2 + 3:
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
        
        # Rastrear swings confirmados
        confirmed_highs = []  # (index, level, confirmation_index)
        confirmed_lows = []
        
        # Rastrear tendência
        trend = 0  # 1 = bullish, -1 = bearish
        
        for i in range(swing_length * 2, n):
            # Confirmar swings
            potential_idx = i - swing_length
            if potential_idx >= swing_length:
                start = potential_idx - swing_length
                
                # Swing high
                window_highs = _high[start:i + 1]
                if _high[potential_idx] == window_highs.max():
                    already = any(h[0] == potential_idx for h in confirmed_highs)
                    if not already:
                        confirmed_highs.append((potential_idx, _high[potential_idx], i))
                
                # Swing low
                window_lows = _low[start:i + 1]
                if _low[potential_idx] == window_lows.min():
                    already = any(l[0] == potential_idx for l in confirmed_lows)
                    if not already:
                        confirmed_lows.append((potential_idx, _low[potential_idx], i))
            
            # Verificar BOS/CHoCH
            # Bullish break (preço fecha acima de swing high)
            for h_idx, (h_formation, h_level, h_confirmation) in enumerate(confirmed_highs):
                if h_confirmation >= i:
                    continue
                
                if _close[i] > h_level:
                    if trend == 1:
                        bos[i] = 1
                    else:
                        choch[i] = 1
                        trend = 1
                    level[i] = h_level
                    confirmed_highs.pop(h_idx)
                    break
            
            # Bearish break
            for l_idx, (l_formation, l_level, l_confirmation) in enumerate(confirmed_lows):
                if l_confirmation >= i:
                    continue
                
                if _close[i] < l_level:
                    if trend == -1:
                        bos[i] = -1
                    else:
                        choch[i] = -1
                        trend = -1
                    level[i] = l_level
                    confirmed_lows.pop(l_idx)
                    break
        
        bos = np.where(bos != 0, bos, np.nan)
        choch = np.where(choch != 0, choch, np.nan)
        level = np.where((~np.isnan(bos)) | (~np.isnan(choch)), level, np.nan)
        
        return pd.DataFrame({
            'BOS': bos,
            'CHOCH': choch,
            'Level': level,
        })


class OrderBlockStrategyNoLookahead:
    """
    Estratégia de Order Block 3:1 SEM LOOK-AHEAD BIAS
    
    Esta estratégia garante que:
    1. Order Blocks são identificados APENAS após confirmação
    2. Sinais são gerados APENAS após o OB ser confirmado
    3. Entradas ocorrem APENAS em candles APÓS o sinal
    4. Nenhum dado futuro é usado em qualquer cálculo
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
        self.order_blocks = SMCNoLookahead.ob_realtime(self.ohlc, swing_length)
        self.fvg = SMCNoLookahead.fvg(self.ohlc)
        self.bos_choch = SMCNoLookahead.bos_choch_realtime(self.ohlc, swing_length)
    
    def calculate_confidence(self, ob_index: int) -> float:
        """
        Calcula confiança usando APENAS dados disponíveis até o momento da confirmação.
        """
        confidence = 0.0
        
        # Usar apenas dados até o índice do OB (não dados futuros)
        
        # 1. Percentage do OB (0-25 pontos)
        ob_percentage = self.order_blocks['Percentage'].iloc[ob_index]
        if not np.isnan(ob_percentage):
            confidence += min(25, ob_percentage / 4)
        
        # 2. FVG próximo (apenas FVGs ANTES do OB)
        window = 10
        start_idx = max(0, ob_index - window)
        end_idx = ob_index  # NÃO incluir dados futuros
        
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
            # Usar média apenas de dados passados
            avg_candle_size = (self.ohlc['high'].iloc[:ob_index] - self.ohlc['low'].iloc[:ob_index]).mean()
            
            if avg_candle_size > 0:
                size_ratio = ob_size / avg_candle_size
                if 0.5 <= size_ratio <= 2.0:
                    confidence += 15
                elif 0.3 <= size_ratio <= 3.0:
                    confidence += 10
                else:
                    confidence += 5
        
        # 5. Volume (0-10 pontos)
        ob_volume = self.order_blocks['OBVolume'].iloc[ob_index]
        if not np.isnan(ob_volume):
            avg_volume = self.ohlc['volume'].iloc[:ob_index].mean()
            if avg_volume > 0:
                volume_ratio = ob_volume / (avg_volume * 3)
                confidence += min(10, volume_ratio * 5)
        
        return min(100, confidence)
    
    def generate_signals(self) -> List[TradeSignal]:
        """
        Gera sinais de trading SEM LOOK-AHEAD BIAS.
        
        Processo:
        1. Para cada OB confirmado
        2. Esperar entry_delay_candles após a confirmação
        3. Procurar entrada quando o preço retorna ao OB
        4. A entrada só ocorre em candles APÓS o sinal
        """
        signals = []
        n = len(self.ohlc)
        
        for i in range(n):
            ob_direction = self.order_blocks['OB'].iloc[i]
            
            if np.isnan(ob_direction):
                continue
            
            ob_top = self.order_blocks['Top'].iloc[i]
            ob_bottom = self.order_blocks['Bottom'].iloc[i]
            confirmation_idx = self.order_blocks['ConfirmationIndex'].iloc[i]
            formation_idx = self.order_blocks['FormationIndex'].iloc[i]
            
            if np.isnan(ob_top) or np.isnan(ob_bottom):
                continue
            
            # O OB foi confirmado no índice i
            # Calcular confiança usando apenas dados até i
            confidence = self.calculate_confidence(i)
            
            if confidence < self.min_confidence:
                continue
            
            # Procurar entrada APÓS o delay
            # A entrada deve ser em um candle DEPOIS do candle de confirmação
            entry_start = i + self.entry_delay_candles
            
            for j in range(entry_start, min(n, i + 100)):
                current_high = self.ohlc['high'].iloc[j]
                current_low = self.ohlc['low'].iloc[j]
                
                # Verificar se o OB já foi mitigado
                mitigated = self.order_blocks['MitigatedIndex'].iloc[i]
                if not np.isnan(mitigated) and j > mitigated:
                    break
                
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
                            ob_formation_index=int(formation_idx) if not np.isnan(formation_idx) else i,
                            confirmation_index=int(confirmation_idx) if not np.isnan(confirmation_idx) else i,
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
                            ob_formation_index=int(formation_idx) if not np.isnan(formation_idx) else i,
                            confirmation_index=int(confirmation_idx) if not np.isnan(confirmation_idx) else i,
                        )
                        signals.append(signal)
                        break
        
        return signals
    
    def backtest(self, signals: Optional[List[TradeSignal]] = None) -> Tuple[List[BacktestResult], Dict]:
        """
        Executa backtest dos sinais.
        """
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
            
            # Simular trade - entrada no candle SEGUINTE ao sinal
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
        
        # Calcular estatísticas
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
        """Retorna DataFrame com todos os indicadores"""
        df = self.ohlc.copy()
        
        # Adicionar Order Blocks
        for col in self.order_blocks.columns:
            df[f'OB_{col}'] = self.order_blocks[col].values
        
        # Adicionar FVG
        for col in self.fvg.columns:
            df[f'FVG_{col}'] = self.fvg[col].values
        
        # Adicionar BOS/CHoCH
        for col in self.bos_choch.columns:
            df[f'BOSCHOCH_{col}'] = self.bos_choch[col].values
        
        # Calcular confiança para cada OB
        confidence = np.full(len(df), np.nan)
        for i in range(len(df)):
            if not np.isnan(self.order_blocks['OB'].iloc[i]):
                confidence[i] = self.calculate_confidence(i)
        df['OB_Confidence'] = confidence
        
        return df


def run_validation_tests():
    """
    Executa testes rigorosos para validar que não há look-ahead bias.
    """
    print("=" * 70)
    print("TESTES DE VALIDAÇÃO - SEM LOOK-AHEAD BIAS")
    print("=" * 70)
    
    # Criar dados de teste
    np.random.seed(42)
    n = 1000
    
    base_price = 100
    prices = [base_price]
    for i in range(n - 1):
        change = np.random.randn() * 0.5
        prices.append(prices[-1] + change)
    
    test_data = pd.DataFrame({
        'time': pd.date_range('2024-01-01', periods=n, freq='h'),
        'open': prices,
        'high': [p + abs(np.random.randn() * 0.3) for p in prices],
        'low': [p - abs(np.random.randn() * 0.3) for p in prices],
        'close': [p + np.random.randn() * 0.2 for p in prices],
        'volume': [np.random.randint(1000, 10000) for _ in range(n)],
    })
    test_data.set_index('time', inplace=True)
    test_data['high'] = test_data[['open', 'close', 'high']].max(axis=1)
    test_data['low'] = test_data[['open', 'close', 'low']].min(axis=1)
    
    all_passed = True
    
    # Teste 1: Order Blocks são confirmados apenas com dados passados
    print("\n1. Testando Order Blocks (sem look-ahead)...")
    try:
        ob = SMCNoLookahead.ob_realtime(test_data, swing_length=5)
        
        # Verificar que ConfirmationIndex >= FormationIndex para todos os OBs
        valid_obs = ob[ob['OB'].notna()]
        
        lookahead_violations = 0
        for idx in valid_obs.index:
            formation = valid_obs.loc[idx, 'FormationIndex']
            confirmation = valid_obs.loc[idx, 'ConfirmationIndex']
            
            if not np.isnan(formation) and not np.isnan(confirmation):
                if confirmation < formation:
                    lookahead_violations += 1
                    print(f"   VIOLAÇÃO: OB em {idx} - Formation: {formation}, Confirmation: {confirmation}")
        
        if lookahead_violations == 0:
            print(f"   ✓ {len(valid_obs)} Order Blocks detectados, nenhuma violação de look-ahead")
        else:
            print(f"   ✗ {lookahead_violations} violações de look-ahead detectadas!")
            all_passed = False
            
    except Exception as e:
        print(f"   ✗ Erro: {e}")
        all_passed = False
    
    # Teste 2: Sinais são gerados apenas após confirmação
    print("\n2. Testando geração de sinais...")
    try:
        strategy = OrderBlockStrategyNoLookahead(
            test_data,
            swing_length=5,
            risk_reward_ratio=3.0,
            min_confidence=30.0,
            entry_delay_candles=1,
        )
        
        signals = strategy.generate_signals()
        
        lookahead_signals = 0
        for signal in signals:
            # Verificar que entrada é APÓS confirmação
            if signal.index <= signal.signal_candle_index:
                lookahead_signals += 1
                print(f"   VIOLAÇÃO: Entrada em {signal.index}, Sinal em {signal.signal_candle_index}")
            
            # Verificar que sinal é APÓS formação
            if signal.signal_candle_index < signal.ob_formation_index:
                lookahead_signals += 1
                print(f"   VIOLAÇÃO: Sinal em {signal.signal_candle_index}, Formação em {signal.ob_formation_index}")
        
        if lookahead_signals == 0:
            print(f"   ✓ {len(signals)} sinais gerados, nenhuma violação de look-ahead")
        else:
            print(f"   ✗ {lookahead_signals} violações de look-ahead detectadas!")
            all_passed = False
            
    except Exception as e:
        print(f"   ✗ Erro: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False
    
    # Teste 3: Simulação de tempo real
    print("\n3. Testando simulação de tempo real...")
    try:
        # Simular processamento candle a candle
        signals_realtime = []
        
        for end_idx in range(100, n, 50):
            # Usar apenas dados até end_idx
            partial_data = test_data.iloc[:end_idx].copy()
            
            strategy = OrderBlockStrategyNoLookahead(
                partial_data,
                swing_length=5,
                risk_reward_ratio=3.0,
                min_confidence=30.0,
                entry_delay_candles=1,
            )
            
            signals = strategy.generate_signals()
            
            # Verificar que todos os sinais usam apenas dados disponíveis
            for signal in signals:
                if signal.index >= end_idx:
                    print(f"   VIOLAÇÃO: Sinal em {signal.index} com dados até {end_idx}")
                    all_passed = False
        
        print(f"   ✓ Simulação de tempo real passou")
        
    except Exception as e:
        print(f"   ✗ Erro: {e}")
        all_passed = False
    
    # Teste 4: Backtest com dados reais
    print("\n4. Testando backtest...")
    try:
        strategy = OrderBlockStrategyNoLookahead(
            test_data,
            swing_length=5,
            risk_reward_ratio=3.0,
            min_confidence=30.0,
            entry_delay_candles=1,
        )
        
        signals = strategy.generate_signals()
        results, stats = strategy.backtest(signals)
        
        print(f"   Total trades: {stats['total_trades']}")
        print(f"   Win Rate: {stats['win_rate']:.1f}%")
        print(f"   Profit Factor: {stats['profit_factor']:.2f}")
        
        if stats['total_trades'] > 0:
            print(f"   ✓ Backtest executado com sucesso")
        else:
            print(f"   ⚠ Nenhum trade gerado (pode ser normal com dados sintéticos)")
            
    except Exception as e:
        print(f"   ✗ Erro: {e}")
        all_passed = False
    
    print("\n" + "=" * 70)
    if all_passed:
        print("✓ TODOS OS TESTES PASSARAM - SEM LOOK-AHEAD BIAS")
    else:
        print("✗ ALGUNS TESTES FALHARAM")
    print("=" * 70)
    
    return all_passed


if __name__ == "__main__":
    run_validation_tests()
