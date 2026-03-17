"""
SMC Engine - Motor de Estratégias Smart Money Concepts para Tempo Real
======================================================================

Engine otimizado para processar dados em tempo real minuto a minuto.
Inclui todas as estratégias SMC com validação de toque na linha.
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Tuple
from collections import deque
import logging

logger = logging.getLogger(__name__)


class SignalDirection(Enum):
    BULLISH = 1
    BEARISH = -1


class PatternType(Enum):
    ORDER_BLOCK = "OB"
    BOS = "BOS"
    CHOCH = "CHoCH"
    FVG = "FVG"
    LIQUIDITY_SWEEP = "SWEEP"
    SPRING = "SPRING"
    UPTHRUST = "UPTHRUST"


class OrderStatus(Enum):
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    CLOSED_TP = "closed_tp"
    CLOSED_SL = "closed_sl"


@dataclass
class OrderBlock:
    """Representa um Order Block identificado"""
    index: int
    direction: SignalDirection
    top: float
    bottom: float
    midline: float
    volume: float
    confirmation_index: int
    is_mitigated: bool = False
    patterns: List[PatternType] = field(default_factory=list)
    confidence: float = 0.0
    
    def contains_price(self, price: float) -> bool:
        return self.bottom <= price <= self.top


@dataclass
class PendingOrder:
    """Ordem pendente (limit)"""
    id: str
    symbol: str
    direction: SignalDirection
    entry_price: float
    stop_loss: float
    take_profit: float
    volume: float
    ob: OrderBlock
    created_at: int  # índice do candle
    status: OrderStatus = OrderStatus.PENDING
    filled_at: Optional[int] = None
    closed_at: Optional[int] = None
    profit_loss: float = 0.0
    patterns: List[PatternType] = field(default_factory=list)
    confidence: float = 0.0


@dataclass
class TradeSignal:
    """Sinal de trade gerado"""
    timestamp: str
    symbol: str
    direction: SignalDirection
    entry_price: float
    stop_loss: float
    take_profit: float
    ob_top: float
    ob_bottom: float
    risk_reward_ratio: float
    patterns: List[PatternType]
    confidence: float
    risk_points: float
    reward_points: float


class SMCEngine:
    """
    Engine de estratégias SMC para processamento em tempo real.
    
    Otimizado para:
    - Receber dados minuto a minuto
    - Processar incrementalmente (sem recalcular tudo)
    - Gerenciar ordens pendentes
    - Validar toque na linha do OB
    """
    
    def __init__(
        self,
        symbol: str = "WINM24",
        swing_length: int = 5,
        risk_reward_ratio: float = 3.0,
        min_volume_ratio: float = 1.5,
        min_ob_size_atr: float = 0.5,
        max_pending_orders: int = 10,
        max_candles_history: int = 5000,
        use_not_mitigated_filter: bool = True
    ):
        self.symbol = symbol
        self.swing_length = swing_length
        self.risk_reward_ratio = risk_reward_ratio
        self.min_volume_ratio = min_volume_ratio
        self.min_ob_size_atr = min_ob_size_atr
        self.max_pending_orders = max_pending_orders
        self.max_candles_history = max_candles_history
        self.use_not_mitigated_filter = use_not_mitigated_filter
        
        # Dados históricos (buffer circular)
        self.candles: deque = deque(maxlen=max_candles_history)
        self.candle_count = 0
        
        # Cache de indicadores
        self.swing_highs: Dict[int, float] = {}
        self.swing_lows: Dict[int, float] = {}
        self.order_blocks: List[OrderBlock] = []
        self.fvgs: List[Dict] = []
        
        # Ordens
        self.pending_orders: List[PendingOrder] = []
        self.filled_orders: List[PendingOrder] = []
        self.closed_orders: List[PendingOrder] = []
        
        # Métricas
        self.atr = 0.0
        self.volume_ma = 0.0
        self.ema_20 = 0.0
        self.ema_50 = 0.0
        
        # Contadores
        self.order_id_counter = 0
        
        logger.info(f"SMCEngine inicializado para {symbol}")
    
    def add_candle(self, candle: Dict) -> List[TradeSignal]:
        """
        Adiciona um novo candle e processa em tempo real.
        
        Args:
            candle: Dict com keys: time, open, high, low, close, volume
        
        Returns:
            Lista de sinais de trade gerados
        """
        # Normalizar candle
        candle = {
            'time': candle.get('time', ''),
            'open': float(candle.get('open', 0)),
            'high': float(candle.get('high', 0)),
            'low': float(candle.get('low', 0)),
            'close': float(candle.get('close', 0)),
            'volume': float(candle.get('volume', candle.get('tick_volume', 1))),
            'index': self.candle_count
        }
        
        self.candles.append(candle)
        self.candle_count += 1
        
        # Atualizar indicadores
        self._update_indicators()
        
        # Verificar ordens pendentes
        self._check_pending_orders(candle)
        
        # Verificar ordens preenchidas (TP/SL)
        self._check_filled_orders(candle)
        
        # Detectar novos padrões
        self._detect_patterns()
        
        # Gerar novos sinais
        signals = self._generate_signals(candle)
        
        return signals
    
    def _update_indicators(self):
        """Atualiza indicadores incrementalmente"""
        if len(self.candles) < 20:
            return
        
        # ATR (14 períodos)
        if len(self.candles) >= 14:
            highs = [c['high'] for c in list(self.candles)[-14:]]
            lows = [c['low'] for c in list(self.candles)[-14:]]
            closes = [c['close'] for c in list(self.candles)[-15:-1]]
            
            tr_sum = 0
            for i in range(14):
                tr = max(
                    highs[i] - lows[i],
                    abs(highs[i] - closes[i]) if i < len(closes) else 0,
                    abs(lows[i] - closes[i]) if i < len(closes) else 0
                )
                tr_sum += tr
            self.atr = tr_sum / 14
        
        # Volume MA (20 períodos)
        if len(self.candles) >= 20:
            volumes = [c['volume'] for c in list(self.candles)[-20:]]
            self.volume_ma = sum(volumes) / 20
        
        # EMAs
        closes = [c['close'] for c in self.candles]
        if len(closes) >= 20:
            self.ema_20 = self._calculate_ema(closes, 20)
        if len(closes) >= 50:
            self.ema_50 = self._calculate_ema(closes, 50)
    
    def _calculate_ema(self, data: List[float], period: int) -> float:
        """Calcula EMA"""
        if len(data) < period:
            return 0.0
        
        multiplier = 2 / (period + 1)
        ema = sum(data[:period]) / period
        
        for price in data[period:]:
            ema = (price - ema) * multiplier + ema
        
        return ema
    
    def _detect_patterns(self):
        """Detecta padrões SMC incrementalmente"""
        if len(self.candles) < self.swing_length * 2 + 1:
            return
        
        candles_list = list(self.candles)
        n = len(candles_list)
        
        # Detectar Swing High/Low confirmado
        check_idx = n - self.swing_length - 1
        if check_idx < self.swing_length:
            return
        
        # Swing High
        is_swing_high = True
        pivot_high = candles_list[check_idx]['high']
        for i in range(check_idx - self.swing_length, check_idx + self.swing_length + 1):
            if i != check_idx and i >= 0 and i < n:
                if candles_list[i]['high'] > pivot_high:
                    is_swing_high = False
                    break
        
        if is_swing_high:
            self.swing_highs[check_idx] = pivot_high
            self._check_bearish_ob(check_idx, candles_list)
        
        # Swing Low
        is_swing_low = True
        pivot_low = candles_list[check_idx]['low']
        for i in range(check_idx - self.swing_length, check_idx + self.swing_length + 1):
            if i != check_idx and i >= 0 and i < n:
                if candles_list[i]['low'] < pivot_low:
                    is_swing_low = False
                    break
        
        if is_swing_low:
            self.swing_lows[check_idx] = pivot_low
            self._check_bullish_ob(check_idx, candles_list)
        
        # Detectar FVG
        self._detect_fvg(candles_list)
    
    def _check_bullish_ob(self, swing_low_idx: int, candles: List[Dict]):
        """Verifica e cria OB Bullish após swing low confirmado"""
        if swing_low_idx < 2:
            return
        
        # Encontrar candle de baixa antes do swing low
        for i in range(swing_low_idx - 1, max(0, swing_low_idx - 5), -1):
            candle = candles[i]
            if candle['close'] < candle['open']:  # Candle de baixa
                # Verificar filtros
                if self.atr > 0:
                    ob_size = candle['high'] - candle['low']
                    if ob_size < self.min_ob_size_atr * self.atr:
                        continue
                
                if self.volume_ma > 0:
                    if candle['volume'] < self.min_volume_ratio * self.volume_ma:
                        continue
                
                # Criar OB
                ob = OrderBlock(
                    index=i,
                    direction=SignalDirection.BULLISH,
                    top=candle['high'],
                    bottom=candle['low'],
                    midline=(candle['high'] + candle['low']) / 2,
                    volume=candle['volume'],
                    confirmation_index=swing_low_idx + self.swing_length,
                    patterns=[PatternType.ORDER_BLOCK]
                )
                
                # Calcular confiança
                ob.confidence = self._calculate_confidence(ob, candles)
                
                # Verificar se já existe OB similar
                if not self._ob_exists(ob):
                    self.order_blocks.append(ob)
                    logger.info(f"OB Bullish detectado: {ob.midline:.2f}")
                
                break
    
    def _check_bearish_ob(self, swing_high_idx: int, candles: List[Dict]):
        """Verifica e cria OB Bearish após swing high confirmado"""
        if swing_high_idx < 2:
            return
        
        # Encontrar candle de alta antes do swing high
        for i in range(swing_high_idx - 1, max(0, swing_high_idx - 5), -1):
            candle = candles[i]
            if candle['close'] > candle['open']:  # Candle de alta
                # Verificar filtros
                if self.atr > 0:
                    ob_size = candle['high'] - candle['low']
                    if ob_size < self.min_ob_size_atr * self.atr:
                        continue
                
                if self.volume_ma > 0:
                    if candle['volume'] < self.min_volume_ratio * self.volume_ma:
                        continue
                
                # Criar OB
                ob = OrderBlock(
                    index=i,
                    direction=SignalDirection.BEARISH,
                    top=candle['high'],
                    bottom=candle['low'],
                    midline=(candle['high'] + candle['low']) / 2,
                    volume=candle['volume'],
                    confirmation_index=swing_high_idx + self.swing_length,
                    patterns=[PatternType.ORDER_BLOCK]
                )
                
                ob.confidence = self._calculate_confidence(ob, candles)
                
                if not self._ob_exists(ob):
                    self.order_blocks.append(ob)
                    logger.info(f"OB Bearish detectado: {ob.midline:.2f}")
                
                break
    
    def _detect_fvg(self, candles: List[Dict]):
        """Detecta Fair Value Gaps"""
        if len(candles) < 3:
            return
        
        c1 = candles[-3]
        c2 = candles[-2]
        c3 = candles[-1]
        
        # FVG Bullish: gap entre high do c1 e low do c3
        if c3['low'] > c1['high']:
            fvg = {
                'type': 'bullish',
                'top': c3['low'],
                'bottom': c1['high'],
                'index': len(candles) - 2
            }
            self.fvgs.append(fvg)
        
        # FVG Bearish: gap entre low do c1 e high do c3
        if c3['high'] < c1['low']:
            fvg = {
                'type': 'bearish',
                'top': c1['low'],
                'bottom': c3['high'],
                'index': len(candles) - 2
            }
            self.fvgs.append(fvg)
    
    def _calculate_confidence(self, ob: OrderBlock, candles: List[Dict]) -> float:
        """Calcula índice de confiança do OB"""
        confidence = 0.0
        
        # Volume score (0-25)
        if self.volume_ma > 0:
            vol_ratio = ob.volume / self.volume_ma
            confidence += min(25, vol_ratio * 10)
        
        # Tamanho do OB vs ATR (0-15)
        if self.atr > 0:
            size_ratio = (ob.top - ob.bottom) / self.atr
            confidence += min(15, size_ratio * 10)
        
        # Tendência (0-15)
        if self.ema_20 > 0 and self.ema_50 > 0:
            if ob.direction == SignalDirection.BULLISH and self.ema_20 > self.ema_50:
                confidence += 15
            elif ob.direction == SignalDirection.BEARISH and self.ema_20 < self.ema_50:
                confidence += 15
        
        # FVG próximo (0-20)
        for fvg in self.fvgs[-10:]:
            if ob.direction == SignalDirection.BULLISH and fvg['type'] == 'bullish':
                if abs(fvg['bottom'] - ob.top) < self.atr * 0.5:
                    confidence += 20
                    ob.patterns.append(PatternType.FVG)
                    break
            elif ob.direction == SignalDirection.BEARISH and fvg['type'] == 'bearish':
                if abs(fvg['top'] - ob.bottom) < self.atr * 0.5:
                    confidence += 20
                    ob.patterns.append(PatternType.FVG)
                    break
        
        # BOS/CHoCH (0-15)
        # Simplificado: verificar se houve quebra de estrutura recente
        if len(self.swing_highs) > 1 and len(self.swing_lows) > 1:
            confidence += 10
            ob.patterns.append(PatternType.BOS)
        
        return min(100, confidence)
    
    def _ob_exists(self, new_ob: OrderBlock) -> bool:
        """Verifica se OB similar já existe"""
        for ob in self.order_blocks[-50:]:
            if (ob.direction == new_ob.direction and 
                abs(ob.midline - new_ob.midline) < self.atr * 0.1):
                return True
        return False
    
    def _generate_signals(self, current_candle: Dict) -> List[TradeSignal]:
        """Gera sinais de trade para OBs não mitigados"""
        signals = []
        
        for ob in self.order_blocks:
            # Pular OBs já mitigados
            if self.use_not_mitigated_filter and ob.is_mitigated:
                continue
            
            # Verificar se já existe ordem pendente para este OB
            if self._has_pending_order_for_ob(ob):
                continue
            
            # Verificar se o OB já foi confirmado
            if current_candle['index'] <= ob.confirmation_index:
                continue
            
            # Criar ordem pendente
            if ob.direction == SignalDirection.BULLISH:
                entry_price = ob.midline
                sl_distance = ob.top - ob.bottom
                stop_loss = ob.bottom - sl_distance * 0.1
                take_profit = entry_price + (entry_price - stop_loss) * self.risk_reward_ratio
                
            else:  # BEARISH
                entry_price = ob.midline
                sl_distance = ob.top - ob.bottom
                stop_loss = ob.top + sl_distance * 0.1
                take_profit = entry_price - (stop_loss - entry_price) * self.risk_reward_ratio
            
            # Criar ordem pendente
            self.order_id_counter += 1
            order = PendingOrder(
                id=f"SMC_{self.order_id_counter}",
                symbol=self.symbol,
                direction=ob.direction,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                volume=1.0,
                ob=ob,
                created_at=current_candle['index'],
                patterns=ob.patterns.copy(),
                confidence=ob.confidence
            )
            
            self.pending_orders.append(order)
            
            # Criar sinal
            risk_points = abs(entry_price - stop_loss)
            reward_points = abs(take_profit - entry_price)
            
            signal = TradeSignal(
                timestamp=current_candle['time'],
                symbol=self.symbol,
                direction=ob.direction,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                ob_top=ob.top,
                ob_bottom=ob.bottom,
                risk_reward_ratio=self.risk_reward_ratio,
                patterns=ob.patterns.copy(),
                confidence=ob.confidence,
                risk_points=risk_points,
                reward_points=reward_points
            )
            
            signals.append(signal)
            logger.info(f"Sinal gerado: {ob.direction.name} @ {entry_price:.2f}, "
                       f"SL: {stop_loss:.2f}, TP: {take_profit:.2f}, "
                       f"Confiança: {ob.confidence:.1f}%")
        
        return signals
    
    def _has_pending_order_for_ob(self, ob: OrderBlock) -> bool:
        """Verifica se já existe ordem pendente para este OB"""
        for order in self.pending_orders:
            if order.ob.index == ob.index:
                return True
        return False
    
    def _check_pending_orders(self, candle: Dict):
        """Verifica se ordens pendentes foram preenchidas"""
        for order in self.pending_orders[:]:
            if order.status != OrderStatus.PENDING:
                continue
            
            # Validar toque na linha
            filled = False
            
            if order.direction == SignalDirection.BULLISH:
                # Buy Limit: executada se LOW <= entry_price
                if candle['low'] <= order.entry_price:
                    filled = True
            else:
                # Sell Limit: executada se HIGH >= entry_price
                if candle['high'] >= order.entry_price:
                    filled = True
            
            if filled:
                order.status = OrderStatus.FILLED
                order.filled_at = candle['index']
                order.ob.is_mitigated = True
                
                self.pending_orders.remove(order)
                self.filled_orders.append(order)
                
                logger.info(f"Ordem {order.id} PREENCHIDA @ {order.entry_price:.2f}")
    
    def _check_filled_orders(self, candle: Dict):
        """Verifica se ordens preenchidas atingiram TP ou SL"""
        for order in self.filled_orders[:]:
            if order.status != OrderStatus.FILLED:
                continue
            
            hit_tp = False
            hit_sl = False
            
            if order.direction == SignalDirection.BULLISH:
                # LONG: TP se HIGH >= take_profit, SL se LOW <= stop_loss
                if candle['high'] >= order.take_profit:
                    hit_tp = True
                elif candle['low'] <= order.stop_loss:
                    hit_sl = True
            else:
                # SHORT: TP se LOW <= take_profit, SL se HIGH >= stop_loss
                if candle['low'] <= order.take_profit:
                    hit_tp = True
                elif candle['high'] >= order.stop_loss:
                    hit_sl = True
            
            if hit_tp:
                order.status = OrderStatus.CLOSED_TP
                order.closed_at = candle['index']
                order.profit_loss = abs(order.take_profit - order.entry_price)
                
                self.filled_orders.remove(order)
                self.closed_orders.append(order)
                
                logger.info(f"Ordem {order.id} FECHADA TP +{order.profit_loss:.2f} pts")
            
            elif hit_sl:
                order.status = OrderStatus.CLOSED_SL
                order.closed_at = candle['index']
                order.profit_loss = -abs(order.entry_price - order.stop_loss)
                
                self.filled_orders.remove(order)
                self.closed_orders.append(order)
                
                logger.info(f"Ordem {order.id} FECHADA SL {order.profit_loss:.2f} pts")
    
    def get_stats(self) -> Dict:
        """Retorna estatísticas do engine"""
        total_trades = len(self.closed_orders)
        winning_trades = sum(1 for o in self.closed_orders if o.status == OrderStatus.CLOSED_TP)
        losing_trades = sum(1 for o in self.closed_orders if o.status == OrderStatus.CLOSED_SL)
        
        total_profit = sum(o.profit_loss for o in self.closed_orders)
        
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        return {
            'symbol': self.symbol,
            'candles_processed': self.candle_count,
            'order_blocks_detected': len(self.order_blocks),
            'pending_orders': len(self.pending_orders),
            'filled_orders': len(self.filled_orders),
            'closed_orders': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'total_profit_points': total_profit,
            'atr': self.atr,
            'ema_20': self.ema_20,
            'ema_50': self.ema_50
        }
    
    def get_pending_orders(self) -> List[Dict]:
        """Retorna ordens pendentes"""
        return [
            {
                'id': o.id,
                'symbol': o.symbol,
                'direction': o.direction.name,
                'entry_price': o.entry_price,
                'stop_loss': o.stop_loss,
                'take_profit': o.take_profit,
                'patterns': [p.value for p in o.patterns],
                'confidence': o.confidence,
                'created_at': o.created_at
            }
            for o in self.pending_orders
        ]
    
    def get_filled_orders(self) -> List[Dict]:
        """Retorna ordens preenchidas (abertas)"""
        return [
            {
                'id': o.id,
                'symbol': o.symbol,
                'direction': o.direction.name,
                'entry_price': o.entry_price,
                'stop_loss': o.stop_loss,
                'take_profit': o.take_profit,
                'patterns': [p.value for p in o.patterns],
                'confidence': o.confidence,
                'filled_at': o.filled_at
            }
            for o in self.filled_orders
        ]
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancela uma ordem pendente"""
        for order in self.pending_orders:
            if order.id == order_id:
                order.status = OrderStatus.CANCELLED
                self.pending_orders.remove(order)
                logger.info(f"Ordem {order_id} cancelada")
                return True
        return False


# Instância global para uso na API
engines: Dict[str, SMCEngine] = {}


def get_engine(symbol: str) -> SMCEngine:
    """Obtém ou cria engine para um símbolo"""
    if symbol not in engines:
        engines[symbol] = SMCEngine(symbol=symbol)
    return engines[symbol]
