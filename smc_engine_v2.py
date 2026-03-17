"""
SMC Engine V2 - Tempo Real sem Look-Ahead Bias
================================================

Lógica idêntica ao smc_touch_validated.py, mas processando candle a candle.

REGRAS FUNDAMENTAIS:
1. Swing High/Low: Confirmado APENAS quando N candles posteriores confirmam
2. Order Block: Marcado no candle de CONFIRMAÇÃO (quando preço rompe swing)
3. Mitigação: Verificada APENAS com dados PASSADOS (nunca futuro)
4. Entrada: Ordem LIMIT na linha do meio, preenchida quando preço TOCA
5. TP/SL: Verificados a partir do PRÓXIMO candle após fill
6. Expiração: Ordens pendentes expiram após max_pending_candles
"""

import numpy as np
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Deque
from collections import deque
import time


# ==================== ENUMS ====================

class SignalDirection(Enum):
    BULLISH = 1
    BEARISH = -1

class PatternType(Enum):
    ORDER_BLOCK = "OB"
    BOS = "BOS"
    CHOCH = "CHoCH"
    FVG = "FVG"
    LIQUIDITY_SWEEP = "SWEEP"

class OrderStatus(Enum):
    PENDING = "pending"         # Ordem limit aguardando
    FILLED = "filled"           # Ordem executada, trade aberto
    CLOSED_TP = "closed_tp"     # Fechado no Take Profit
    CLOSED_SL = "closed_sl"     # Fechado no Stop Loss
    EXPIRED = "expired"         # Ordem expirada (não tocou a linha)
    CANCELLED = "cancelled"     # Cancelada (OB mitigado)


# ==================== DATA CLASSES ====================

@dataclass
class OrderBlock:
    """Order Block detectado"""
    id: str
    direction: SignalDirection
    ob_candle_index: int        # Índice do candle que formou o OB
    confirmation_index: int     # Índice do candle que CONFIRMOU o OB
    top: float
    bottom: float
    midline: float
    volume: float
    is_mitigated: bool = False  # Se já foi tocado/mitigado
    mitigated_at: int = -1      # Índice do candle que mitigou
    
    @property
    def size(self):
        return self.top - self.bottom


@dataclass
class PendingOrder:
    """Ordem limit pendente"""
    id: str
    direction: SignalDirection
    entry_price: float          # Preço da linha do meio (limit)
    stop_loss: float
    take_profit: float
    ob_id: str                  # ID do Order Block associado
    ob_top: float
    ob_bottom: float
    created_at_index: int       # Candle em que a ordem foi criada
    patterns: List[PatternType] = field(default_factory=list)
    confidence: float = 0.0
    status: OrderStatus = OrderStatus.PENDING
    filled_at_index: int = -1
    closed_at_index: int = -1
    profit_loss: float = 0.0
    risk_points: float = 0.0


# ==================== CACHE INCREMENTAL ====================

class IncrementalCache:
    """Cache incremental para cálculos O(1) por candle"""
    
    def __init__(self):
        # Dados OHLCV
        self.opens: List[float] = []
        self.highs: List[float] = []
        self.lows: List[float] = []
        self.closes: List[float] = []
        self.volumes: List[float] = []
        
        # EMA incremental
        self.ema20: float = 0.0
        self.ema50: float = 0.0
        self.ema20_values: List[float] = []
        self.ema50_values: List[float] = []
        self.ema20_mult = 2.0 / 21.0
        self.ema50_mult = 2.0 / 51.0
        
        # ATR incremental (SMA de 14 períodos do range)
        self.atr_window: Deque[float] = deque(maxlen=14)
        self.atr: float = 0.0
        
        # Volume MA incremental (SMA de 20 períodos)
        self.vol_window: Deque[float] = deque(maxlen=20)
        self.avg_volume: float = 0.0
        
        # Contagem
        self.count: int = 0
    
    def add_candle(self, o: float, h: float, l: float, c: float, v: float):
        """Adiciona candle e atualiza todos os caches em O(1)"""
        self.opens.append(o)
        self.highs.append(h)
        self.lows.append(l)
        self.closes.append(c)
        self.volumes.append(v)
        self.count += 1
        
        # ATR
        tr = h - l
        self.atr_window.append(tr)
        if len(self.atr_window) >= 14:
            self.atr = sum(self.atr_window) / len(self.atr_window)
        
        # Volume MA
        self.vol_window.append(v)
        if len(self.vol_window) >= 20:
            self.avg_volume = sum(self.vol_window) / len(self.vol_window)
        
        # EMA 20
        if self.count <= 20:
            self.ema20 = sum(self.closes[-min(self.count, 20):]) / min(self.count, 20)
        else:
            self.ema20 = (c - self.ema20) * self.ema20_mult + self.ema20
        self.ema20_values.append(self.ema20)
        
        # EMA 50
        if self.count <= 50:
            self.ema50 = sum(self.closes[-min(self.count, 50):]) / min(self.count, 50)
        else:
            self.ema50 = (c - self.ema50) * self.ema50_mult + self.ema50
        self.ema50_values.append(self.ema50)


# ==================== SMC ENGINE V2 ====================

class SMCEngineV2:
    """
    Engine SMC para tempo real - processa candle a candle.
    
    Lógica idêntica ao smc_touch_validated.py:
    - Swing confirmado após swing_length candles
    - OB marcado no candle de confirmação
    - Mitigação verificada apenas com dados passados
    - Entrada na linha do meio (ordem limit)
    - TP/SL verificados após fill
    """
    
    def __init__(
        self,
        symbol: str = "WINM24",
        swing_length: int = 5,
        risk_reward_ratio: float = 3.0,
        min_volume_ratio: float = 1.5,
        min_ob_size_atr: float = 0.5,
        use_not_mitigated_filter: bool = True,
        max_pending_candles: int = 100,
        entry_delay_candles: int = 1,
    ):
        self.symbol = symbol
        self.swing_length = swing_length
        self.risk_reward_ratio = risk_reward_ratio
        self.min_volume_ratio = min_volume_ratio
        self.min_ob_size_atr = min_ob_size_atr
        self.use_not_mitigated_filter = use_not_mitigated_filter
        self.max_pending_candles = max_pending_candles
        self.entry_delay_candles = entry_delay_candles
        
        # Cache incremental
        self.cache = IncrementalCache()
        
        # Swings
        self.swing_highs: List[tuple] = []   # (index, level)
        self.swing_lows: List[tuple] = []    # (index, level)
        
        # Último swing pendente de confirmação
        self.last_top_idx: int = -1
        self.last_top_level: float = 0.0
        self.last_bottom_idx: int = -1
        self.last_bottom_level: float = 0.0
        
        # Tendência para BOS/CHoCH
        self.trend: int = 0  # 0=indefinido, 1=alta, -1=baixa
        self.last_bos_choch_high: Optional[float] = None
        self.last_bos_choch_low: Optional[float] = None
        
        # Order Blocks ativos (não mitigados)
        self.active_obs: List[OrderBlock] = []
        self.ob_counter: int = 0
        
        # FVGs recentes
        self.recent_fvgs: Deque[tuple] = deque(maxlen=50)  # (index, direction, top, bottom)
        
        # Sweeps recentes
        self.recent_sweeps: Deque[tuple] = deque(maxlen=50)  # (index, direction)
        
        # BOS/CHoCH recentes
        self.recent_bos: Deque[tuple] = deque(maxlen=50)  # (index, direction)
        self.recent_choch: Deque[tuple] = deque(maxlen=50)  # (index, direction)
        
        # Ordens
        self.pending_orders: List[PendingOrder] = []
        self.filled_orders: List[PendingOrder] = []
        self.closed_orders: List[PendingOrder] = []
        
        # Contadores
        self.order_counter: int = 0
        self.total_wins: int = 0
        self.total_losses: int = 0
        self.total_profit_points: float = 0.0
    
    def add_candle(self, candle: dict) -> List[dict]:
        """
        Processa um novo candle e retorna eventos gerados.
        
        Fluxo:
        1. Armazena candle no cache
        2. Detecta swings (confirmados)
        3. Detecta OBs (quando preço rompe swing)
        4. Detecta FVG, BOS/CHoCH, Sweeps
        5. Verifica mitigação de OBs ativos (com dados PASSADOS)
        6. Cria ordens limit para novos OBs válidos
        7. Verifica fills de ordens pendentes
        8. Verifica TP/SL de ordens preenchidas
        9. Expira ordens antigas
        
        Returns:
            Lista de eventos (novos sinais, fills, closes)
        """
        o = float(candle['open'])
        h = float(candle['high'])
        l = float(candle['low'])
        c = float(candle['close'])
        v = float(candle.get('volume', candle.get('tick_volume', 1.0)))
        
        self.cache.add_candle(o, h, l, c, v)
        idx = self.cache.count - 1
        
        events = []
        
        if self.cache.count < self.swing_length * 2 + 1:
            return events
        
        # ========== PASSO 1: Detectar Swings Confirmados ==========
        self._detect_swings(idx)
        
        # ========== PASSO 2: Detectar OBs (quando preço rompe swing) ==========
        new_obs = self._detect_order_blocks(idx)
        
        # ========== PASSO 3: Detectar FVG ==========
        self._detect_fvg(idx)
        
        # ========== PASSO 4: Detectar BOS/CHoCH ==========
        self._detect_bos_choch(idx)
        
        # ========== PASSO 5: Detectar Sweeps ==========
        self._detect_sweeps(idx)
        
        # ========== PASSO 6: Verificar mitigação de OBs (APENAS PASSADO) ==========
        self._check_mitigation(idx)
        
        # ========== PASSO 7: Criar ordens para novos OBs válidos ==========
        for ob in new_obs:
            order_events = self._create_order_for_ob(ob, idx)
            events.extend(order_events)
        
        # ========== PASSO 8: Verificar fills de ordens pendentes ==========
        fill_events = self._check_pending_fills(idx)
        events.extend(fill_events)
        
        # ========== PASSO 9: Verificar TP/SL de ordens preenchidas ==========
        close_events = self._check_filled_orders(idx)
        events.extend(close_events)
        
        # ========== PASSO 10: Expirar ordens antigas ==========
        expire_events = self._expire_old_orders(idx)
        events.extend(expire_events)
        
        return events
    
    # ==================== DETECÇÃO DE SWINGS ====================
    
    def _detect_swings(self, idx: int):
        """
        Detecta Swing High/Low CONFIRMADO.
        
        Um swing é confirmado no candle atual (idx) para o candidato
        em (idx - swing_length). Precisamos de swing_length candles
        antes E depois do candidato.
        """
        sl = self.swing_length
        candidate_idx = idx - sl
        
        if candidate_idx < sl:
            return
        
        highs = self.cache.highs
        lows = self.cache.lows
        
        candidate_high = highs[candidate_idx]
        candidate_low = lows[candidate_idx]
        
        # Verificar Swing High
        is_swing_high = True
        # Candles ANTES do candidato
        for j in range(candidate_idx - sl, candidate_idx):
            if j >= 0 and highs[j] >= candidate_high:
                is_swing_high = False
                break
        # Candles DEPOIS do candidato (até o candle atual)
        if is_swing_high:
            for j in range(candidate_idx + 1, idx + 1):
                if highs[j] >= candidate_high:
                    is_swing_high = False
                    break
        
        if is_swing_high:
            self.swing_highs.append((candidate_idx, candidate_high))
            # Atualizar último topo para detecção de OB
            self.last_top_idx = candidate_idx
            self.last_top_level = candidate_high
            # Para BOS/CHoCH
            self.last_bos_choch_high = candidate_high
        
        # Verificar Swing Low
        is_swing_low = True
        for j in range(candidate_idx - sl, candidate_idx):
            if j >= 0 and lows[j] <= candidate_low:
                is_swing_low = False
                break
        if is_swing_low:
            for j in range(candidate_idx + 1, idx + 1):
                if lows[j] <= candidate_low:
                    is_swing_low = False
                    break
        
        if is_swing_low:
            self.swing_lows.append((candidate_idx, candidate_low))
            self.last_bottom_idx = candidate_idx
            self.last_bottom_level = candidate_low
            self.last_bos_choch_low = candidate_low
    
    # ==================== DETECÇÃO DE ORDER BLOCKS ====================
    
    def _detect_order_blocks(self, idx: int) -> List[OrderBlock]:
        """
        Detecta Order Blocks quando o preço rompe um swing.
        
        Lógica idêntica ao smc_touch_validated.py:
        - Bullish OB: Close > último swing high → OB = último candle de baixa antes do swing
        - Bearish OB: Close < último swing low → OB = último candle de alta antes do swing
        """
        new_obs = []
        closes = self.cache.closes
        opens = self.cache.opens
        highs = self.cache.highs
        lows = self.cache.lows
        volumes = self.cache.volumes
        
        # Bullish OB - preço rompe swing high
        if self.last_top_idx > 0 and closes[idx] > self.last_top_level:
            ob_idx = self.last_top_idx
            # Encontrar último candle de BAIXA antes do movimento
            while ob_idx > 0 and closes[ob_idx] >= opens[ob_idx]:
                ob_idx -= 1
            
            if ob_idx >= 0:
                self.ob_counter += 1
                ob = OrderBlock(
                    id=f"OB_{self.ob_counter}",
                    direction=SignalDirection.BULLISH,
                    ob_candle_index=ob_idx,
                    confirmation_index=idx,
                    top=max(opens[ob_idx], closes[ob_idx]),
                    bottom=min(opens[ob_idx], closes[ob_idx]),
                    midline=(max(opens[ob_idx], closes[ob_idx]) + min(opens[ob_idx], closes[ob_idx])) / 2,
                    volume=volumes[ob_idx],
                )
                
                # Verificar se OB já foi mitigado NO PASSADO
                # (preço já tocou a região do OB entre confirmação e agora)
                for k in range(ob.confirmation_index, idx):
                    if lows[k] <= ob.bottom:
                        ob.is_mitigated = True
                        ob.mitigated_at = k
                        break
                
                self.active_obs.append(ob)
                if not ob.is_mitigated:
                    new_obs.append(ob)
            
            self.last_top_idx = -1
        
        # Bearish OB - preço rompe swing low
        if self.last_bottom_idx > 0 and closes[idx] < self.last_bottom_level:
            ob_idx = self.last_bottom_idx
            # Encontrar último candle de ALTA antes do movimento
            while ob_idx > 0 and closes[ob_idx] <= opens[ob_idx]:
                ob_idx -= 1
            
            if ob_idx >= 0:
                self.ob_counter += 1
                ob = OrderBlock(
                    id=f"OB_{self.ob_counter}",
                    direction=SignalDirection.BEARISH,
                    ob_candle_index=ob_idx,
                    confirmation_index=idx,
                    top=max(opens[ob_idx], closes[ob_idx]),
                    bottom=min(opens[ob_idx], closes[ob_idx]),
                    midline=(max(opens[ob_idx], closes[ob_idx]) + min(opens[ob_idx], closes[ob_idx])) / 2,
                    volume=volumes[ob_idx],
                )
                
                # Verificar mitigação no PASSADO
                for k in range(ob.confirmation_index, idx):
                    if highs[k] >= ob.top:
                        ob.is_mitigated = True
                        ob.mitigated_at = k
                        break
                
                self.active_obs.append(ob)
                if not ob.is_mitigated:
                    new_obs.append(ob)
            
            self.last_bottom_idx = -1
        
        return new_obs
    
    # ==================== DETECÇÃO DE FVG ====================
    
    def _detect_fvg(self, idx: int):
        """Detecta Fair Value Gap no candle atual"""
        if idx < 2:
            return
        
        highs = self.cache.highs
        lows = self.cache.lows
        
        # Bullish FVG: low[i] > high[i-2]
        if lows[idx] > highs[idx - 2]:
            self.recent_fvgs.append((idx, 1, lows[idx], highs[idx - 2]))
        
        # Bearish FVG: high[i] < low[i-2]
        elif highs[idx] < lows[idx - 2]:
            self.recent_fvgs.append((idx, -1, lows[idx - 2], highs[idx]))
    
    # ==================== DETECÇÃO DE BOS/CHoCH ====================
    
    def _detect_bos_choch(self, idx: int):
        """Detecta Break of Structure e Change of Character"""
        closes = self.cache.closes
        
        # Rompimento de swing high
        if self.last_bos_choch_high is not None and closes[idx] > self.last_bos_choch_high:
            if self.trend == 1:
                self.recent_bos.append((idx, 1))
            elif self.trend == -1 or self.trend == 0:
                self.recent_choch.append((idx, 1))
            self.trend = 1
            self.last_bos_choch_high = None
        
        # Rompimento de swing low
        if self.last_bos_choch_low is not None and closes[idx] < self.last_bos_choch_low:
            if self.trend == -1:
                self.recent_bos.append((idx, -1))
            elif self.trend == 1 or self.trend == 0:
                self.recent_choch.append((idx, -1))
            self.trend = -1
            self.last_bos_choch_low = None
    
    # ==================== DETECÇÃO DE SWEEPS ====================
    
    def _detect_sweeps(self, idx: int):
        """Detecta Liquidity Sweeps"""
        if idx < 1:
            return
        
        highs = self.cache.highs
        lows = self.cache.lows
        closes = self.cache.closes
        
        # Bullish Sweep: varre low anterior e fecha acima
        for sh_idx, sh_level in self.swing_lows[-20:]:
            if sh_idx >= idx or idx - sh_idx > 100:
                continue
            if lows[idx] < sh_level and closes[idx] > sh_level:
                self.recent_sweeps.append((idx, 1))
                break
        
        # Bearish Sweep: varre high anterior e fecha abaixo
        for sh_idx, sh_level in self.swing_highs[-20:]:
            if sh_idx >= idx or idx - sh_idx > 100:
                continue
            if highs[idx] > sh_level and closes[idx] < sh_level:
                self.recent_sweeps.append((idx, -1))
                break
    
    # ==================== MITIGAÇÃO DE OBs ====================
    
    def _check_mitigation(self, idx: int):
        """
        Verifica se OBs ativos foram mitigados pelo candle ATUAL.
        
        Mitigação = preço tocou a região do OB:
        - Bullish OB: mitigado quando LOW <= OB bottom
        - Bearish OB: mitigado quando HIGH >= OB top
        
        Isso usa APENAS o candle atual (passado), nunca o futuro.
        """
        highs = self.cache.highs
        lows = self.cache.lows
        
        for ob in self.active_obs:
            if ob.is_mitigated:
                continue
            
            # Só verificar OBs que já foram confirmados
            if idx <= ob.confirmation_index:
                continue
            
            if ob.direction == SignalDirection.BULLISH:
                # Bullish OB mitigado quando preço cai abaixo do bottom
                if lows[idx] <= ob.bottom:
                    ob.is_mitigated = True
                    ob.mitigated_at = idx
                    # Cancelar ordens pendentes deste OB
                    self._cancel_orders_for_ob(ob.id, idx)
            else:
                # Bearish OB mitigado quando preço sobe acima do top
                if highs[idx] >= ob.top:
                    ob.is_mitigated = True
                    ob.mitigated_at = idx
                    self._cancel_orders_for_ob(ob.id, idx)
    
    def _cancel_orders_for_ob(self, ob_id: str, idx: int):
        """Cancela ordens pendentes de um OB mitigado"""
        to_remove = []
        for order in self.pending_orders:
            if order.ob_id == ob_id:
                order.status = OrderStatus.CANCELLED
                order.closed_at_index = idx
                self.closed_orders.append(order)
                to_remove.append(order)
        
        for order in to_remove:
            self.pending_orders.remove(order)
    
    # ==================== CRIAÇÃO DE ORDENS ====================
    
    def _create_order_for_ob(self, ob: OrderBlock, idx: int) -> List[dict]:
        """
        Cria ordem limit para um Order Block válido.
        
        Filtros aplicados:
        1. OB não mitigado
        2. Volume > min_volume_ratio × média
        3. Tamanho > min_ob_size_atr × ATR
        """
        events = []
        
        # FILTRO 1: OB não mitigado
        if self.use_not_mitigated_filter and ob.is_mitigated:
            return events
        
        # FILTRO 2: Tamanho do OB > 0.5 ATR
        if self.cache.atr > 0 and self.min_ob_size_atr > 0:
            if ob.size < self.cache.atr * self.min_ob_size_atr:
                return events
        
        # FILTRO 3: Volume > 1.5x média
        if self.cache.avg_volume > 0 and self.min_volume_ratio > 0:
            volume_ratio = ob.volume / self.cache.avg_volume
            if volume_ratio < self.min_volume_ratio:
                return events
        
        # Calcular entrada, SL, TP
        entry_price = ob.midline
        ob_size = ob.size
        
        if ob.direction == SignalDirection.BULLISH:
            stop_loss = ob.bottom - ob_size * 0.1
            risk = entry_price - stop_loss
            if risk <= 0:
                return events
            take_profit = entry_price + (risk * self.risk_reward_ratio)
        else:
            stop_loss = ob.top + ob_size * 0.1
            risk = stop_loss - entry_price
            if risk <= 0:
                return events
            take_profit = entry_price - (risk * self.risk_reward_ratio)
        
        # Detectar padrões presentes
        patterns = self._get_patterns_at(idx, ob.direction)
        
        # Calcular confiança
        confidence = self._calculate_confidence(ob, patterns)
        
        # Criar ordem
        self.order_counter += 1
        order = PendingOrder(
            id=f"SMC_{self.order_counter}",
            direction=ob.direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            ob_id=ob.id,
            ob_top=ob.top,
            ob_bottom=ob.bottom,
            created_at_index=idx,
            patterns=patterns,
            confidence=confidence,
            risk_points=risk,
        )
        
        self.pending_orders.append(order)
        
        events.append({
            'type': 'new_signal',
            'order_id': order.id,
            'direction': order.direction.name,
            'entry_price': entry_price,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'ob_id': ob.id,
            'ob_top': ob.top,
            'ob_bottom': ob.bottom,
            'midline': ob.midline,
            'confidence': confidence,
            'patterns': [p.value for p in patterns],
            'risk_points': risk,
            'candle_index': idx,
        })
        
        return events
    
    # ==================== VERIFICAÇÃO DE FILLS ====================
    
    def _check_pending_fills(self, idx: int) -> List[dict]:
        """
        Verifica se ordens pendentes foram preenchidas.
        
        Ordem LIMIT:
        - BULLISH: preenchida quando LOW <= entry_price
        - BEARISH: preenchida quando HIGH >= entry_price
        
        IMPORTANTE: Só verifica a partir de entry_delay_candles após criação
        """
        events = []
        to_fill = []
        
        highs = self.cache.highs
        lows = self.cache.lows
        
        for order in self.pending_orders:
            # Respeitar delay de entrada
            if idx < order.created_at_index + self.entry_delay_candles:
                continue
            
            # Verificar se OB foi mitigado (cancelar)
            if self.use_not_mitigated_filter:
                ob = next((ob for ob in self.active_obs if ob.id == order.ob_id), None)
                if ob and ob.is_mitigated and ob.mitigated_at <= idx:
                    order.status = OrderStatus.CANCELLED
                    order.closed_at_index = idx
                    self.closed_orders.append(order)
                    to_fill.append(order)
                    continue
            
            filled = False
            if order.direction == SignalDirection.BULLISH:
                # Buy Limit: preenchida quando LOW <= entry_price
                if lows[idx] <= order.entry_price:
                    filled = True
            else:
                # Sell Limit: preenchida quando HIGH >= entry_price
                if highs[idx] >= order.entry_price:
                    filled = True
            
            if filled:
                order.status = OrderStatus.FILLED
                order.filled_at_index = idx
                self.filled_orders.append(order)
                to_fill.append(order)
                
                events.append({
                    'type': 'order_filled',
                    'order_id': order.id,
                    'direction': order.direction.name,
                    'entry_price': order.entry_price,
                    'candle_index': idx,
                })
        
        for order in to_fill:
            if order in self.pending_orders:
                self.pending_orders.remove(order)
        
        return events
    
    # ==================== VERIFICAÇÃO DE TP/SL ====================
    
    def _check_filled_orders(self, idx: int) -> List[dict]:
        """
        Verifica TP/SL de ordens preenchidas.
        
        IMPORTANTE: Só verifica a partir do PRÓXIMO candle após fill.
        """
        events = []
        to_close = []
        
        highs = self.cache.highs
        lows = self.cache.lows
        
        for order in self.filled_orders:
            # Só verificar a partir do PRÓXIMO candle após fill
            if idx <= order.filled_at_index:
                continue
            
            closed = False
            
            if order.direction == SignalDirection.BULLISH:
                # Verificar SL primeiro (pior caso)
                if lows[idx] <= order.stop_loss:
                    order.status = OrderStatus.CLOSED_SL
                    order.profit_loss = order.stop_loss - order.entry_price
                    closed = True
                # Verificar TP
                elif highs[idx] >= order.take_profit:
                    order.status = OrderStatus.CLOSED_TP
                    order.profit_loss = order.take_profit - order.entry_price
                    closed = True
            else:
                # Verificar SL primeiro (pior caso)
                if highs[idx] >= order.stop_loss:
                    order.status = OrderStatus.CLOSED_SL
                    order.profit_loss = order.entry_price - order.stop_loss
                    closed = True
                # Verificar TP
                elif lows[idx] <= order.take_profit:
                    order.status = OrderStatus.CLOSED_TP
                    order.profit_loss = order.entry_price - order.take_profit
                    closed = True
            
            if closed:
                order.closed_at_index = idx
                self.closed_orders.append(order)
                to_close.append(order)
                
                if order.status == OrderStatus.CLOSED_TP:
                    self.total_wins += 1
                else:
                    self.total_losses += 1
                self.total_profit_points += order.profit_loss
                
                events.append({
                    'type': 'order_closed',
                    'order_id': order.id,
                    'direction': order.direction.name,
                    'status': order.status.value,
                    'entry_price': order.entry_price,
                    'exit_price': order.take_profit if order.status == OrderStatus.CLOSED_TP else order.stop_loss,
                    'profit_loss': order.profit_loss,
                    'candle_index': idx,
                    'duration': idx - order.filled_at_index,
                })
        
        for order in to_close:
            if order in self.filled_orders:
                self.filled_orders.remove(order)
        
        return events
    
    # ==================== EXPIRAÇÃO DE ORDENS ====================
    
    def _expire_old_orders(self, idx: int) -> List[dict]:
        """Expira ordens pendentes que passaram do limite de candles"""
        events = []
        to_expire = []
        
        for order in self.pending_orders:
            if idx - order.created_at_index > self.max_pending_candles:
                order.status = OrderStatus.EXPIRED
                order.closed_at_index = idx
                self.closed_orders.append(order)
                to_expire.append(order)
                
                events.append({
                    'type': 'order_expired',
                    'order_id': order.id,
                    'direction': order.direction.name,
                    'candle_index': idx,
                    'age': idx - order.created_at_index,
                })
        
        for order in to_expire:
            self.pending_orders.remove(order)
        
        return events
    
    # ==================== PADRÕES ====================
    
    def _get_patterns_at(self, idx: int, direction: SignalDirection) -> List[PatternType]:
        """Retorna padrões detectados próximos ao índice"""
        patterns = [PatternType.ORDER_BLOCK]
        dir_val = 1 if direction == SignalDirection.BULLISH else -1
        
        # BOS nos últimos 5 candles
        for bos_idx, bos_dir in self.recent_bos:
            if idx - 5 <= bos_idx <= idx and bos_dir == dir_val:
                patterns.append(PatternType.BOS)
                break
        
        # CHoCH nos últimos 5 candles
        for choch_idx, choch_dir in self.recent_choch:
            if idx - 5 <= choch_idx <= idx and choch_dir == dir_val:
                patterns.append(PatternType.CHOCH)
                break
        
        # FVG nos últimos 10 candles
        for fvg_idx, fvg_dir, _, _ in self.recent_fvgs:
            if idx - 10 <= fvg_idx <= idx and fvg_dir == dir_val:
                patterns.append(PatternType.FVG)
                break
        
        # Sweep nos últimos 5 candles
        for sweep_idx, sweep_dir in self.recent_sweeps:
            if idx - 5 <= sweep_idx <= idx and sweep_dir == dir_val:
                patterns.append(PatternType.LIQUIDITY_SWEEP)
                break
        
        return patterns
    
    # ==================== CONFIANÇA ====================
    
    def _calculate_confidence(self, ob: OrderBlock, patterns: List[PatternType]) -> float:
        """Calcula índice de confiança (0-100)"""
        confidence = 0.0
        
        # Volume (0-25)
        if self.cache.avg_volume > 0:
            vol_ratio = ob.volume / self.cache.avg_volume
            confidence += min(25, vol_ratio * 10)
        
        # FVG presente (0-20)
        if PatternType.FVG in patterns:
            confidence += 20
        
        # Tendência alinhada (0-15)
        if self.cache.count > 50:
            ema20 = self.cache.ema20
            ema50 = self.cache.ema50
            if ob.direction == SignalDirection.BULLISH and ema20 > ema50:
                confidence += 15
            elif ob.direction == SignalDirection.BEARISH and ema20 < ema50:
                confidence += 15
        
        # Tamanho do OB (0-15)
        if self.cache.atr > 0:
            size_ratio = ob.size / self.cache.atr
            confidence += min(15, size_ratio * 10)
        
        # Sweep (0-15)
        if PatternType.LIQUIDITY_SWEEP in patterns:
            confidence += 15
        
        # BOS/CHoCH (0-10)
        if PatternType.BOS in patterns:
            confidence += 10
        elif PatternType.CHOCH in patterns:
            confidence += 10
        
        return min(100, confidence)
    
    # ==================== STATS ====================
    
    def get_stats(self) -> dict:
        """Retorna estatísticas do engine"""
        total = self.total_wins + self.total_losses
        win_rate = (self.total_wins / total * 100) if total > 0 else 0
        
        total_win_pts = sum(o.profit_loss for o in self.closed_orders if o.status == OrderStatus.CLOSED_TP)
        total_loss_pts = abs(sum(o.profit_loss for o in self.closed_orders if o.status == OrderStatus.CLOSED_SL))
        pf = total_win_pts / total_loss_pts if total_loss_pts > 0 else float('inf')
        
        return {
            'symbol': self.symbol,
            'candles_processed': self.cache.count,
            'order_blocks_detected': len(self.active_obs),
            'active_obs': sum(1 for ob in self.active_obs if not ob.is_mitigated),
            'pending_orders': len(self.pending_orders),
            'filled_orders': len(self.filled_orders),
            'closed_orders': total,
            'total_wins': self.total_wins,
            'total_losses': self.total_losses,
            'win_rate': win_rate,
            'profit_factor': pf,
            'total_profit_points': self.total_profit_points,
            'total_win_points': total_win_pts,
            'total_loss_points': total_loss_pts,
        }
    
    def get_all_trades(self) -> List[dict]:
        """Retorna tabela de todos os trades fechados"""
        trades = []
        for order in self.closed_orders:
            if order.status in (OrderStatus.CLOSED_TP, OrderStatus.CLOSED_SL):
                trades.append({
                    'id': order.id,
                    'ob_id': order.ob_id,
                    'direction': order.direction.name,
                    'entry_price': order.entry_price,
                    'stop_loss': order.stop_loss,
                    'take_profit': order.take_profit,
                    'ob_top': order.ob_top,
                    'ob_bottom': order.ob_bottom,
                    'created_at': order.created_at_index,
                    'filled_at': order.filled_at_index,
                    'closed_at': order.closed_at_index,
                    'status': order.status.value,
                    'profit_loss': order.profit_loss,
                    'risk_points': order.risk_points,
                    'patterns': [p.value for p in order.patterns],
                    'confidence': order.confidence,
                    'duration': order.closed_at_index - order.filled_at_index,
                    'wait_candles': order.filled_at_index - order.created_at_index,
                })
        return trades
