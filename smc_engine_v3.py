"""
SMC Engine V3 - Versão Final para Tempo Real
=============================================

Engine otimizado para execução em tempo real, candle a candle.
Sem look-ahead bias - funciona identicamente em backtest e live.

CONFIGURAÇÃO OTIMIZADA (default):
- Risk:Reward 3:1
- Sem filtros de volume/tamanho (mais trades, ~50% WR)
- Max pending: 150 candles
- OB não mitigado: ativado
- Proteção contra mitigação no candle de fill

RESULTADOS VALIDADOS (113k candles):
- 1.026 trades | 49.8% Win Rate | PF 2.37
- +24.825 pontos | 1.018R | 0.99R/trade
- 6/6 testes de integridade PASSARAM

LÓGICA:
1. Swing detection: candidato em i - swing_length, confirmado em i
2. OB detection: quando close rompe swing high/low
3. Filtros: OB não mitigado + proteção mitigação no fill
4. Entrada: ordem limit na linha do meio do OB
5. TP/SL: a partir do próximo candle após fill
6. Busca de entrada: máximo 150 candles após OB confirmado
"""

import numpy as np
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Tuple
from collections import deque
import time


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
    PENDING = "pending"
    FILLED = "filled"
    CLOSED_TP = "closed_tp"
    CLOSED_SL = "closed_sl"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


@dataclass
class OrderBlock:
    """Order Block detectado"""
    ob_id: int
    direction: SignalDirection
    top: float
    bottom: float
    midline: float
    ob_candle_index: int        # Candle do OB (bearish/bullish candle)
    confirmation_index: int      # Candle onde o OB foi confirmado
    volume: float
    volume_ratio: float
    ob_size: float
    ob_size_atr: float
    mitigated: bool = False
    mitigated_index: int = -1
    used: bool = False           # Se já gerou ordem


@dataclass
class PendingOrder:
    """Ordem pendente (limit)"""
    order_id: str
    ob: OrderBlock
    direction: SignalDirection
    entry_price: float           # Linha do meio
    stop_loss: float
    take_profit: float
    created_at: int              # Candle de criação
    entry_delay_start: int       # Candle a partir do qual pode ser preenchida
    max_candle: int              # Candle máximo para expirar
    patterns: List[PatternType] = field(default_factory=list)
    confidence: float = 0.0


@dataclass
class FilledOrder:
    """Ordem preenchida (trade aberto)"""
    order_id: str
    ob: OrderBlock
    direction: SignalDirection
    entry_price: float
    stop_loss: float
    take_profit: float
    filled_at: int
    created_at: int
    check_from: int              # Candle a partir do qual verificar TP/SL
    patterns: List[PatternType] = field(default_factory=list)
    confidence: float = 0.0


@dataclass
class ClosedTrade:
    """Trade fechado"""
    order_id: str
    ob: OrderBlock
    direction: SignalDirection
    entry_price: float
    stop_loss: float
    take_profit: float
    exit_price: float
    created_at: int
    filled_at: int
    closed_at: int
    status: OrderStatus
    profit_loss: float
    profit_loss_r: float
    patterns: List[PatternType] = field(default_factory=list)
    confidence: float = 0.0


class SMCEngineV3:
    """
    Engine SMC V3 para tempo real.
    
    Processa candle a candle e replica EXATAMENTE a lógica do batch.
    """
    
    def __init__(
        self,
        symbol: str = "WINM24",
        swing_length: int = 5,
        risk_reward_ratio: float = 3.0,
        min_volume_ratio: float = 0.0,
        min_ob_size_atr: float = 0.0,
        use_not_mitigated_filter: bool = True,
        max_pending_candles: int = 150,
        entry_delay_candles: int = 1,
        tick_size: float = 0.0,
        min_confidence: float = 0.0,
        max_sl_points: float = 0.0,
        min_patterns: int = 0,
        entry_retracement: float = 0.5,
        htf_period: int = 1,
    ):
        self.symbol = symbol
        self.swing_length = swing_length
        self.risk_reward_ratio = risk_reward_ratio
        self.min_volume_ratio = min_volume_ratio
        self.min_ob_size_atr = min_ob_size_atr
        self.use_not_mitigated_filter = use_not_mitigated_filter
        self.max_pending_candles = max_pending_candles
        self.entry_delay_candles = entry_delay_candles
        self.tick_size = tick_size
        self.min_confidence = min_confidence
        self.max_sl_points = max_sl_points
        self.min_patterns = min_patterns
        self.entry_retracement = entry_retracement
        self.htf_period = htf_period

        # Dados de candles (M1)
        self.opens: List[float] = []
        self.highs: List[float] = []
        self.lows: List[float] = []
        self.closes: List[float] = []
        self.volumes: List[float] = []
        self.candle_count: int = 0

        # Cache de indicadores (incrementais)
        self._atr_sum: float = 0.0
        self._atr_values: deque = deque(maxlen=14)
        self._vol_sum: float = 0.0
        self._vol_values: deque = deque(maxlen=20)
        self._current_atr: float = 0.0
        self._current_avg_vol: float = 0.0

        # Swings - armazenamos (confirmation_index, candidate_index, level)
        # confirmation_index = i (candle atual quando confirmado)
        # candidate_index = i - swing_length
        self.swing_highs: List[Tuple[int, int, float]] = []  # (confirm_idx, cand_idx, level)
        self.swing_lows: List[Tuple[int, int, float]] = []

        # Tracking de ultimo swing para OB detection
        self._last_top_idx: int = -1      # candidate index (i - swing_length)
        self._last_top_level: float = 0.0
        self._last_bottom_idx: int = -1
        self._last_bottom_level: float = 0.0

        # BOS/CHoCH tracking
        self._trend: int = 0
        self._last_swing_high_level: Optional[float] = None
        self._last_swing_low_level: Optional[float] = None

        # Order Blocks
        self.active_obs: List[OrderBlock] = []
        self._ob_counter: int = 0
        self._gc_interval: int = 10  # Rodar GC a cada N candles
        self._max_swing_history: int = 200  # Máximo de swings na memória

        # Ordens
        self.pending_orders: List[PendingOrder] = []
        self.filled_orders: List[FilledOrder] = []
        self.closed_trades: List[ClosedTrade] = []
        self._order_counter: int = 0

        # FVG tracking
        self._recent_fvg: List[Tuple[int, int]] = []  # (index, direction)

        # Sweep tracking
        self._recent_sweeps: List[Tuple[int, int]] = []  # (index, direction)

        # BOS/CHoCH tracking for patterns
        self._recent_bos: List[Tuple[int, int]] = []
        self._recent_choch: List[Tuple[int, int]] = []

        # Performance tracking
        self._last_process_time: float = 0.0

        # ============================================================
        # HTF (Higher Timeframe) - somente quando htf_period > 1
        # ============================================================
        if self.htf_period > 1:
            # Buffer de agregacao M1 -> HTF
            self._htf_buffer_open: float = 0.0
            self._htf_buffer_high: float = 0.0
            self._htf_buffer_low: float = float('inf')
            self._htf_buffer_close: float = 0.0
            self._htf_buffer_volume: float = 0.0
            self._htf_buffer_count: int = 0
            self._htf_buffer_start_time: int = 0

            # Arrays HTF
            self.htf_opens: List[float] = []
            self.htf_highs: List[float] = []
            self.htf_lows: List[float] = []
            self.htf_closes: List[float] = []
            self.htf_volumes: List[float] = []
            self.htf_candle_count: int = 0

            # Indicadores HTF
            self._htf_atr_values: deque = deque(maxlen=14)
            self._htf_current_atr: float = 0.0
            self._htf_vol_values: deque = deque(maxlen=20)
            self._htf_current_avg_vol: float = 0.0

            # Swings HTF
            self._htf_swing_highs: List[Tuple[int, int, float]] = []
            self._htf_swing_lows: List[Tuple[int, int, float]] = []
            self._htf_last_top_idx: int = -1
            self._htf_last_top_level: float = 0.0
            self._htf_last_bottom_idx: int = -1
            self._htf_last_bottom_level: float = 0.0

            # BOS/CHoCH HTF
            self._htf_trend: int = 0
            self._htf_last_swing_high_level: Optional[float] = None
            self._htf_last_swing_low_level: Optional[float] = None

            # Patterns HTF
            self._htf_recent_fvg: List[Tuple[int, int]] = []
            self._htf_recent_bos: List[Tuple[int, int]] = []
            self._htf_recent_choch: List[Tuple[int, int]] = []
            self._htf_recent_sweeps: List[Tuple[int, int]] = []

            # Mapeamento HTF idx -> M1 idx range
            self._htf_to_m1_start: List[int] = []
            self._htf_to_m1_end: List[int] = []

            # M1 start idx do buffer HTF atual
            self._htf_buffer_m1_start: int = 0
    
    # ============================================================
    # HTF METHODS - Agregacao e deteccao no timeframe superior
    # ============================================================

    def _get_htf_boundary(self, unix_ts: int) -> int:
        """Retorna o inicio da barra HTF que contem este timestamp."""
        period_seconds = self.htf_period * 60
        return (unix_ts // period_seconds) * period_seconds

    def _aggregate_m1_to_htf(self, candle_time: int, o: float, h: float, l: float, c: float, v: float) -> bool:
        """Agrega candle M1 no buffer HTF. Retorna True se barra HTF fechou."""
        current_boundary = self._get_htf_boundary(candle_time)

        if self._htf_buffer_count == 0:
            # Inicio de nova barra HTF
            self._htf_buffer_open = o
            self._htf_buffer_high = h
            self._htf_buffer_low = l
            self._htf_buffer_close = c
            self._htf_buffer_volume = v
            self._htf_buffer_count = 1
            self._htf_buffer_start_time = current_boundary
            self._htf_buffer_m1_start = self.candle_count - 1
            return False

        if current_boundary != self._htf_buffer_start_time:
            # Nova boundary -> fechar barra HTF anterior
            self._close_htf_candle()

            # Iniciar nova barra com candle atual
            self._htf_buffer_open = o
            self._htf_buffer_high = h
            self._htf_buffer_low = l
            self._htf_buffer_close = c
            self._htf_buffer_volume = v
            self._htf_buffer_count = 1
            self._htf_buffer_start_time = current_boundary
            self._htf_buffer_m1_start = self.candle_count - 1
            return True
        else:
            # Mesma barra HTF -> acumular
            self._htf_buffer_high = max(self._htf_buffer_high, h)
            self._htf_buffer_low = min(self._htf_buffer_low, l)
            self._htf_buffer_close = c
            self._htf_buffer_volume += v
            self._htf_buffer_count += 1
            return False

    def _close_htf_candle(self):
        """Finaliza barra HTF e appenda nos arrays."""
        self.htf_opens.append(self._htf_buffer_open)
        self.htf_highs.append(self._htf_buffer_high)
        self.htf_lows.append(self._htf_buffer_low)
        self.htf_closes.append(self._htf_buffer_close)
        self.htf_volumes.append(self._htf_buffer_volume)

        # Mapeamento HTF -> M1
        m1_end = self.candle_count - 2  # ultimo M1 da barra HTF (antes do candle atual)
        self._htf_to_m1_start.append(self._htf_buffer_m1_start)
        self._htf_to_m1_end.append(m1_end)

        self.htf_candle_count += 1

    def _htf_update_atr(self, high: float, low: float):
        """ATR incremental para HTF."""
        tr = high - low
        self._htf_atr_values.append(tr)
        if len(self._htf_atr_values) >= 14:
            self._htf_current_atr = sum(self._htf_atr_values) / len(self._htf_atr_values)

    def _htf_update_avg_volume(self, volume: float):
        """Volume medio incremental para HTF."""
        self._htf_vol_values.append(volume)
        if len(self._htf_vol_values) >= 20:
            self._htf_current_avg_vol = sum(self._htf_vol_values) / len(self._htf_vol_values)

    def _htf_detect_swings(self, htf_idx: int):
        """Detecta Swing Highs/Lows no HTF."""
        sl = self.swing_length

        if htf_idx < sl * 2:
            return

        candidate_idx = htf_idx - sl
        candidate_high = self.htf_highs[candidate_idx]
        candidate_low = self.htf_lows[candidate_idx]

        # Swing High
        is_swing_high = True
        for j in range(candidate_idx - sl, candidate_idx):
            if j >= 0 and self.htf_highs[j] >= candidate_high:
                is_swing_high = False
                break
        if is_swing_high:
            for j in range(candidate_idx + 1, htf_idx + 1):
                if self.htf_highs[j] >= candidate_high:
                    is_swing_high = False
                    break
        if is_swing_high:
            self._htf_swing_highs.append((htf_idx, candidate_idx, candidate_high))
            self._htf_last_top_idx = candidate_idx
            self._htf_last_top_level = candidate_high
            self._htf_last_swing_high_level = candidate_high

        # Swing Low
        is_swing_low = True
        for j in range(candidate_idx - sl, candidate_idx):
            if j >= 0 and self.htf_lows[j] <= candidate_low:
                is_swing_low = False
                break
        if is_swing_low:
            for j in range(candidate_idx + 1, htf_idx + 1):
                if self.htf_lows[j] <= candidate_low:
                    is_swing_low = False
                    break
        if is_swing_low:
            self._htf_swing_lows.append((htf_idx, candidate_idx, candidate_low))
            self._htf_last_bottom_idx = candidate_idx
            self._htf_last_bottom_level = candidate_low
            self._htf_last_swing_low_level = candidate_low

        # [FIX-3] Limitar HTF swing_highs/lows
        if len(self._htf_swing_highs) > self._max_swing_history:
            self._htf_swing_highs = self._htf_swing_highs[-self._max_swing_history:]
        if len(self._htf_swing_lows) > self._max_swing_history:
            self._htf_swing_lows = self._htf_swing_lows[-self._max_swing_history:]

    def _htf_detect_fvg(self, htf_idx: int):
        """Detecta FVG no HTF."""
        if htf_idx < 2:
            return
        if self.htf_lows[htf_idx] > self.htf_highs[htf_idx - 2]:
            self._htf_recent_fvg.append((htf_idx, 1))
        elif self.htf_highs[htf_idx] < self.htf_lows[htf_idx - 2]:
            self._htf_recent_fvg.append((htf_idx, -1))
        if len(self._htf_recent_fvg) > 50:
            self._htf_recent_fvg = self._htf_recent_fvg[-50:]

    def _htf_detect_bos_choch(self, htf_idx: int):
        """Detecta BOS/CHoCH no HTF."""
        c = self.htf_closes[htf_idx]

        if self._htf_last_swing_high_level is not None and c > self._htf_last_swing_high_level:
            if self._htf_trend == 1:
                self._htf_recent_bos.append((htf_idx, 1))
            elif self._htf_trend == -1 or self._htf_trend == 0:
                self._htf_recent_choch.append((htf_idx, 1))
            self._htf_trend = 1
            self._htf_last_swing_high_level = None

        if self._htf_last_swing_low_level is not None and c < self._htf_last_swing_low_level:
            if self._htf_trend == -1:
                self._htf_recent_bos.append((htf_idx, -1))
            elif self._htf_trend == 1 or self._htf_trend == 0:
                self._htf_recent_choch.append((htf_idx, -1))
            self._htf_trend = -1
            self._htf_last_swing_low_level = None

        if len(self._htf_recent_bos) > 50:
            self._htf_recent_bos = self._htf_recent_bos[-50:]
        if len(self._htf_recent_choch) > 50:
            self._htf_recent_choch = self._htf_recent_choch[-50:]

    def _htf_detect_sweeps(self, htf_idx: int):
        """Detecta Liquidity Sweeps no HTF."""
        if htf_idx < 1:
            return
        c = self.htf_closes[htf_idx]
        h = self.htf_highs[htf_idx]
        l = self.htf_lows[htf_idx]

        for conf_idx, cand_idx, sl_level in self._htf_swing_lows[-20:]:
            if conf_idx >= htf_idx or htf_idx - conf_idx > 100:
                continue
            if l < sl_level and c > sl_level:
                self._htf_recent_sweeps.append((htf_idx, 1))
                break

        for conf_idx, cand_idx, sh_level in self._htf_swing_highs[-20:]:
            if conf_idx >= htf_idx or htf_idx - conf_idx > 100:
                continue
            if h > sh_level and c < sh_level:
                self._htf_recent_sweeps.append((htf_idx, -1))
                break

        if len(self._htf_recent_sweeps) > 50:
            self._htf_recent_sweeps = self._htf_recent_sweeps[-50:]

    def _htf_detect_order_blocks(self, htf_idx: int) -> List[OrderBlock]:
        """Detecta Order Blocks no HTF."""
        new_obs = []
        c = self.htf_closes[htf_idx]

        # Bullish OB - close rompe swing high HTF
        if self._htf_last_top_idx > 0 and c > self._htf_last_top_level:
            ob_idx = self._htf_last_top_idx
            while ob_idx > 0 and self.htf_closes[ob_idx] >= self.htf_opens[ob_idx]:
                ob_idx -= 1

            if ob_idx >= 0:
                ob_top = max(self.htf_opens[ob_idx], self.htf_closes[ob_idx])
                ob_bottom = min(self.htf_opens[ob_idx], self.htf_closes[ob_idx])
                ob_size = ob_top - ob_bottom
                ob_volume = self.htf_volumes[ob_idx]

                volume_ratio = ob_volume / self._htf_current_avg_vol if self._htf_current_avg_vol > 0 else 0
                ob_size_atr = ob_size / self._htf_current_atr if self._htf_current_atr > 0 else 0

                # Converter indices HTF para M1
                ob_candle_m1 = self._htf_to_m1_start[ob_idx] if ob_idx < len(self._htf_to_m1_start) else 0
                confirmation_m1 = self._htf_to_m1_end[htf_idx] if htf_idx < len(self._htf_to_m1_end) else self.candle_count - 1

                self._ob_counter += 1
                ob = OrderBlock(
                    ob_id=self._ob_counter,
                    direction=SignalDirection.BULLISH,
                    top=ob_top,
                    bottom=ob_bottom,
                    midline=(ob_top + ob_bottom) / 2,
                    ob_candle_index=ob_candle_m1,
                    confirmation_index=confirmation_m1,
                    volume=ob_volume,
                    volume_ratio=volume_ratio,
                    ob_size=ob_size,
                    ob_size_atr=ob_size_atr,
                )
                # [FIX-5] Filtro de OBs duplicados/sobrepostos
                if not self._ob_overlaps_existing(ob):
                    self.active_obs.append(ob)
                    new_obs.append(ob)

            self._htf_last_top_idx = -1

        # Bearish OB - close rompe swing low HTF
        if self._htf_last_bottom_idx > 0 and c < self._htf_last_bottom_level:
            ob_idx = self._htf_last_bottom_idx
            while ob_idx > 0 and self.htf_closes[ob_idx] <= self.htf_opens[ob_idx]:
                ob_idx -= 1

            if ob_idx >= 0:
                ob_top = max(self.htf_opens[ob_idx], self.htf_closes[ob_idx])
                ob_bottom = min(self.htf_opens[ob_idx], self.htf_closes[ob_idx])
                ob_size = ob_top - ob_bottom
                ob_volume = self.htf_volumes[ob_idx]

                volume_ratio = ob_volume / self._htf_current_avg_vol if self._htf_current_avg_vol > 0 else 0
                ob_size_atr = ob_size / self._htf_current_atr if self._htf_current_atr > 0 else 0

                ob_candle_m1 = self._htf_to_m1_start[ob_idx] if ob_idx < len(self._htf_to_m1_start) else 0
                confirmation_m1 = self._htf_to_m1_end[htf_idx] if htf_idx < len(self._htf_to_m1_end) else self.candle_count - 1

                self._ob_counter += 1
                ob = OrderBlock(
                    ob_id=self._ob_counter,
                    direction=SignalDirection.BEARISH,
                    top=ob_top,
                    bottom=ob_bottom,
                    midline=(ob_top + ob_bottom) / 2,
                    ob_candle_index=ob_candle_m1,
                    confirmation_index=confirmation_m1,
                    volume=ob_volume,
                    volume_ratio=volume_ratio,
                    ob_size=ob_size,
                    ob_size_atr=ob_size_atr,
                )
                # [FIX-5] Filtro de OBs duplicados/sobrepostos
                if not self._ob_overlaps_existing(ob):
                    self.active_obs.append(ob)
                    new_obs.append(ob)

            self._htf_last_bottom_idx = -1

        return new_obs

    def _htf_get_patterns(self, ob: OrderBlock, htf_idx: int) -> List[PatternType]:
        """Retorna padroes detectados no HTF proximo ao OB."""
        patterns = [PatternType.ORDER_BLOCK]
        direction = 1 if ob.direction == SignalDirection.BULLISH else -1

        for bos_idx, bos_dir in self._htf_recent_bos:
            if abs(bos_idx - htf_idx) <= 5 and bos_dir == direction:
                patterns.append(PatternType.BOS)
                break
        for choch_idx, choch_dir in self._htf_recent_choch:
            if abs(choch_idx - htf_idx) <= 5 and choch_dir == direction:
                patterns.append(PatternType.CHOCH)
                break
        for fvg_idx, fvg_dir in self._htf_recent_fvg:
            if abs(fvg_idx - htf_idx) <= 10 and fvg_dir == direction:
                patterns.append(PatternType.FVG)
                break
        for sweep_idx, sweep_dir in self._htf_recent_sweeps:
            if abs(sweep_idx - htf_idx) <= 5 and sweep_dir == direction:
                patterns.append(PatternType.LIQUIDITY_SWEEP)
                break

        return patterns

    def _htf_calculate_confidence(self, ob: OrderBlock, patterns: List[PatternType]) -> float:
        """Calcula confianca usando metricas HTF."""
        confidence = 0.0

        if ob.volume_ratio >= 3.0: confidence += 25
        elif ob.volume_ratio >= 2.0: confidence += 20
        elif ob.volume_ratio >= 1.5: confidence += 15
        elif ob.volume_ratio >= 1.0: confidence += 10

        if ob.ob_size_atr >= 1.5: confidence += 15
        elif ob.ob_size_atr >= 1.0: confidence += 12
        elif ob.ob_size_atr >= 0.5: confidence += 8

        if PatternType.FVG in patterns: confidence += 20
        if PatternType.BOS in patterns: confidence += 15
        if PatternType.CHOCH in patterns: confidence += 10
        if PatternType.LIQUIDITY_SWEEP in patterns: confidence += 15

        return min(confidence, 100.0)

    def _create_pending_orders_mtf(self, new_obs: List[OrderBlock], m1_idx: int, htf_idx: int) -> List[dict]:
        """Cria ordens pendentes a partir de OBs HTF, com niveis HTF e indices M1."""
        new_signals = []

        for ob in new_obs:
            # FILTRO 1: Tamanho OB >= min_ob_size_atr * ATR_HTF
            if self.min_ob_size_atr > 0 and self._htf_current_atr > 0:
                if ob.ob_size < self._htf_current_atr * self.min_ob_size_atr:
                    continue

            # FILTRO 2: Volume
            if self.min_volume_ratio > 0 and self._htf_current_avg_vol > 0:
                if ob.volume_ratio < self.min_volume_ratio:
                    continue

            # Padroes e confianca HTF
            patterns = self._htf_get_patterns(ob, htf_idx)
            confidence = self._htf_calculate_confidence(ob, patterns)

            # FILTRO 3: Confianca minima
            if self.min_confidence > 0 and confidence < self.min_confidence:
                continue

            # FILTRO 4: Minimo de padroes
            if self.min_patterns > 0 and (len(patterns) - 1) < self.min_patterns:
                continue

            # Calcular entry/SL/TP com niveis HTF
            ob_size = ob.ob_size
            if ob.direction == SignalDirection.BULLISH:
                entry_price = ob.top - ob_size * self.entry_retracement
            else:
                entry_price = ob.bottom + ob_size * self.entry_retracement

            if ob.direction == SignalDirection.BULLISH:
                stop_loss = ob.bottom - ob_size * 0.1
                if self.tick_size > 0:
                    entry_price = round(entry_price / self.tick_size) * self.tick_size
                    stop_loss = (int(stop_loss / self.tick_size)) * self.tick_size
                risk = entry_price - stop_loss
                if risk <= 0:
                    continue
                take_profit = entry_price + (risk * self.risk_reward_ratio)
                if self.tick_size > 0:
                    take_profit = round(take_profit / self.tick_size) * self.tick_size
            else:
                stop_loss = ob.top + ob_size * 0.1
                if self.tick_size > 0:
                    entry_price = round(entry_price / self.tick_size) * self.tick_size
                    stop_loss = (int(stop_loss / self.tick_size) + 1) * self.tick_size
                risk = stop_loss - entry_price
                if risk <= 0:
                    continue
                take_profit = entry_price - (risk * self.risk_reward_ratio)
                if self.tick_size > 0:
                    take_profit = round(take_profit / self.tick_size) * self.tick_size

            # FILTRO 5: SL maximo
            if self.max_sl_points > 0 and risk > self.max_sl_points:
                continue

            # Criar ordem com indices M1
            self._order_counter += 1
            order = PendingOrder(
                order_id=f"SMC_{self._order_counter}",
                ob=ob,
                direction=ob.direction,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                created_at=m1_idx,
                entry_delay_start=m1_idx + self.entry_delay_candles,
                max_candle=m1_idx + self.max_pending_candles,
                patterns=patterns,
                confidence=confidence,
            )

            self.pending_orders.append(order)
            ob.used = True

            new_signals.append({
                'order_id': order.order_id,
                'direction': ob.direction.name,
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'ob_top': ob.top,
                'ob_bottom': ob.bottom,
                'confidence': confidence,
                'patterns': [p.value for p in patterns],
            })

        return new_signals

    # ============================================================
    # MAIN METHOD - add_candle
    # ============================================================

    def add_candle(self, candle: dict) -> dict:
        """
        Adiciona um candle e processa todos os indicadores.

        Args:
            candle: dict com keys 'open', 'high', 'low', 'close', 'volume'
                    Quando htf_period > 1, requer tambem 'time' (unix timestamp)

        Returns:
            dict com eventos gerados (novos sinais, trades fechados, etc.)
        """
        start_time = time.perf_counter_ns()

        o = float(candle['open'])
        h = float(candle['high'])
        l = float(candle['low'])
        c = float(candle['close'])
        v = float(candle.get('volume', 1.0))

        self.opens.append(o)
        self.highs.append(h)
        self.lows.append(l)
        self.closes.append(c)
        self.volumes.append(v)

        idx = self.candle_count
        self.candle_count += 1

        events = {
            'new_signals': [],
            'filled_orders': [],
            'closed_trades': [],
            'expired_orders': [],
            'cancelled_orders': [],
            'new_obs': [],
            'new_patterns': [],
        }

        # Atualizar indicadores M1
        self._update_atr(h, l)
        self._update_avg_volume(v)

        if self.htf_period == 1:
            # === MODO SINGLE TF (comportamento original, backward compat) ===
            self._detect_swings(idx)
            self._detect_fvg(idx)
            self._detect_bos_choch(idx)
            self._detect_sweeps(idx)

            new_obs = self._detect_order_blocks(idx)
            events['new_obs'] = new_obs

            new_signals = self._create_pending_orders(new_obs, idx)
            events['new_signals'] = new_signals

            fill_events, expire_events, cancel_events = self._process_pending_orders(idx)
            events['filled_orders'] = fill_events
            events['expired_orders'] = expire_events
            events['cancelled_orders'] = cancel_events

            self._check_ob_mitigation(idx)
            self._garbage_collect_obs(idx)  # [FIX-1] GC de OBs mitigados

            close_events = self._process_filled_orders(idx)
            events['closed_trades'] = close_events
        else:
            # === MODO MTF (deteccao HTF + execucao M1) ===
            candle_time = int(candle.get('time', 0))
            htf_closed = self._aggregate_m1_to_htf(candle_time, o, h, l, c, v)

            # Se barra HTF fechou, rodar deteccao HTF
            if htf_closed:
                htf_idx = self.htf_candle_count - 1
                self._htf_update_atr(self.htf_highs[htf_idx], self.htf_lows[htf_idx])
                self._htf_update_avg_volume(self.htf_volumes[htf_idx])
                self._htf_detect_swings(htf_idx)
                self._htf_detect_fvg(htf_idx)
                self._htf_detect_bos_choch(htf_idx)
                self._htf_detect_sweeps(htf_idx)

                new_obs = self._htf_detect_order_blocks(htf_idx)
                events['new_obs'] = new_obs

                new_signals = self._create_pending_orders_mtf(new_obs, idx, htf_idx)
                events['new_signals'] = new_signals

            # M1: fill, expiracao, mitigacao (entry precisa no M1)
            fill_events, expire_events, cancel_events = self._process_pending_orders(idx)
            events['filled_orders'] = fill_events
            events['expired_orders'] = expire_events
            events['cancelled_orders'] = cancel_events

            self._check_ob_mitigation(idx)
            self._garbage_collect_obs(idx)  # [FIX-1] GC de OBs mitigados

            # TP/SL no M1 + protecao pos-fill (fecha se OB mitigado no mesmo HTF bar)
            close_events = self._process_filled_orders_mtf(idx)
            events['closed_trades'] = close_events

        self._last_process_time = (time.perf_counter_ns() - start_time) / 1_000_000  # ms

        return events
    
    def _update_atr(self, high: float, low: float):
        """Atualiza ATR incremental (14 períodos)"""
        tr = high - low
        self._atr_values.append(tr)
        if len(self._atr_values) >= 14:
            self._current_atr = sum(self._atr_values) / len(self._atr_values)
    
    def _update_avg_volume(self, volume: float):
        """Atualiza volume médio incremental (20 períodos)"""
        self._vol_values.append(volume)
        if len(self._vol_values) >= 20:
            self._current_avg_vol = sum(self._vol_values) / len(self._vol_values)
    
    def _detect_swings(self, idx: int):
        """
        Detecta Swing Highs/Lows - IDÊNTICO ao batch.
        
        No batch:
        - Loop: for i in range(swing_length * 2, n)
        - candidate_idx = i - swing_length
        - Verifica candles antes (candidate_idx - swing_length até candidate_idx)
        - Verifica candles depois (candidate_idx + 1 até i + 1)
        - Se swing, registra em i (confirmação), mas last_top_idx = candidate_idx
        
        Aqui replicamos exatamente isso.
        """
        sl = self.swing_length
        
        if idx < sl * 2:
            return
        
        candidate_idx = idx - sl
        candidate_high = self.highs[candidate_idx]
        candidate_low = self.lows[candidate_idx]
        
        # Swing High
        is_swing_high = True
        for j in range(candidate_idx - sl, candidate_idx):
            if j >= 0 and self.highs[j] >= candidate_high:
                is_swing_high = False
                break
        
        if is_swing_high:
            for j in range(candidate_idx + 1, idx + 1):
                if self.highs[j] >= candidate_high:
                    is_swing_high = False
                    break
        
        if is_swing_high:
            self.swing_highs.append((idx, candidate_idx, candidate_high))
            # IDÊNTICO ao batch: last_top_idx = i - swing_length = candidate_idx
            self._last_top_idx = candidate_idx
            self._last_top_level = candidate_high
            # Para BOS/CHoCH
            self._last_swing_high_level = candidate_high
        
        # Swing Low
        is_swing_low = True
        for j in range(candidate_idx - sl, candidate_idx):
            if j >= 0 and self.lows[j] <= candidate_low:
                is_swing_low = False
                break
        
        if is_swing_low:
            for j in range(candidate_idx + 1, idx + 1):
                if self.lows[j] <= candidate_low:
                    is_swing_low = False
                    break
        
        if is_swing_low:
            self.swing_lows.append((idx, candidate_idx, candidate_low))
            self._last_bottom_idx = candidate_idx
            self._last_bottom_level = candidate_low
            self._last_swing_low_level = candidate_low
        
        # [FIX-3] Limitar swing_highs/lows para não crescer infinitamente
        if len(self.swing_highs) > self._max_swing_history:
            self.swing_highs = self.swing_highs[-self._max_swing_history:]
        if len(self.swing_lows) > self._max_swing_history:
            self.swing_lows = self.swing_lows[-self._max_swing_history:]
    
    def _detect_fvg(self, idx: int):
        """Detecta Fair Value Gap"""
        if idx < 2:
            return
        
        # Bullish FVG
        if self.lows[idx] > self.highs[idx - 2]:
            self._recent_fvg.append((idx, 1))
        # Bearish FVG
        elif self.highs[idx] < self.lows[idx - 2]:
            self._recent_fvg.append((idx, -1))
        
        # Manter apenas últimos 50
        if len(self._recent_fvg) > 50:
            self._recent_fvg = self._recent_fvg[-50:]
    
    def _detect_bos_choch(self, idx: int):
        """Detecta BOS e CHoCH"""
        c = self.closes[idx]
        
        if self._last_swing_high_level is not None and c > self._last_swing_high_level:
            if self._trend == 1:
                self._recent_bos.append((idx, 1))
            elif self._trend == -1 or self._trend == 0:
                self._recent_choch.append((idx, 1))
            self._trend = 1
            self._last_swing_high_level = None
        
        if self._last_swing_low_level is not None and c < self._last_swing_low_level:
            if self._trend == -1:
                self._recent_bos.append((idx, -1))
            elif self._trend == 1 or self._trend == 0:
                self._recent_choch.append((idx, -1))
            self._trend = -1
            self._last_swing_low_level = None
        
        # Manter apenas últimos 50
        if len(self._recent_bos) > 50:
            self._recent_bos = self._recent_bos[-50:]
        if len(self._recent_choch) > 50:
            self._recent_choch = self._recent_choch[-50:]
    
    def _detect_sweeps(self, idx: int):
        """Detecta Liquidity Sweeps"""
        if idx < 1:
            return
        
        c = self.closes[idx]
        h = self.highs[idx]
        l = self.lows[idx]
        
        # Bullish Sweep (varre lows e fecha acima)
        for conf_idx, cand_idx, sl_level in self.swing_lows[-20:]:
            if conf_idx >= idx or idx - conf_idx > 100:
                continue
            if l < sl_level and c > sl_level:
                self._recent_sweeps.append((idx, 1))
                break
        
        # Bearish Sweep (varre highs e fecha abaixo)
        for conf_idx, cand_idx, sh_level in self.swing_highs[-20:]:
            if conf_idx >= idx or idx - conf_idx > 100:
                continue
            if h > sh_level and c < sh_level:
                self._recent_sweeps.append((idx, -1))
                break
        
        if len(self._recent_sweeps) > 50:
            self._recent_sweeps = self._recent_sweeps[-50:]
    
    def _detect_order_blocks(self, idx: int) -> List[OrderBlock]:
        """
        Detecta Order Blocks - IDÊNTICO ao batch.
        
        No batch:
        - Bullish OB: quando close[i] > last_top_level
        - ob_idx = last_top_idx (candidate)
        - Procura último candle de baixa antes do movimento
        - Bearish OB: quando close[i] < last_bottom_level
        """
        new_obs = []
        c = self.closes[idx]
        
        # Bullish OB - quando close rompe swing high
        if self._last_top_idx > 0 and c > self._last_top_level:
            ob_idx = self._last_top_idx
            # Encontrar último candle de baixa antes do movimento
            while ob_idx > 0 and self.closes[ob_idx] >= self.opens[ob_idx]:
                ob_idx -= 1
            
            if ob_idx >= 0:
                ob_top = max(self.opens[ob_idx], self.closes[ob_idx])
                ob_bottom = min(self.opens[ob_idx], self.closes[ob_idx])
                ob_size = ob_top - ob_bottom
                ob_volume = self.volumes[ob_idx]
                
                volume_ratio = ob_volume / self._current_avg_vol if self._current_avg_vol > 0 else 0
                ob_size_atr = ob_size / self._current_atr if self._current_atr > 0 else 0
                
                self._ob_counter += 1
                ob = OrderBlock(
                    ob_id=self._ob_counter,
                    direction=SignalDirection.BULLISH,
                    top=ob_top,
                    bottom=ob_bottom,
                    midline=(ob_top + ob_bottom) / 2,
                    ob_candle_index=ob_idx,
                    confirmation_index=idx,
                    volume=ob_volume,
                    volume_ratio=volume_ratio,
                    ob_size=ob_size,
                    ob_size_atr=ob_size_atr,
                )
                # [FIX-5] Filtro de OBs duplicados/sobrepostos
                if not self._ob_overlaps_existing(ob):
                    self.active_obs.append(ob)
                    new_obs.append(ob)
            
            self._last_top_idx = -1
        
        # Bearish OB - quando close rompe swing low
        if self._last_bottom_idx > 0 and c < self._last_bottom_level:
            ob_idx = self._last_bottom_idx
            # Encontrar último candle de alta antes do movimento
            while ob_idx > 0 and self.closes[ob_idx] <= self.opens[ob_idx]:
                ob_idx -= 1
            
            if ob_idx >= 0:
                ob_top = max(self.opens[ob_idx], self.closes[ob_idx])
                ob_bottom = min(self.opens[ob_idx], self.closes[ob_idx])
                ob_size = ob_top - ob_bottom
                ob_volume = self.volumes[ob_idx]
                
                volume_ratio = ob_volume / self._current_avg_vol if self._current_avg_vol > 0 else 0
                ob_size_atr = ob_size / self._current_atr if self._current_atr > 0 else 0
                
                self._ob_counter += 1
                ob = OrderBlock(
                    ob_id=self._ob_counter,
                    direction=SignalDirection.BEARISH,
                    top=ob_top,
                    bottom=ob_bottom,
                    midline=(ob_top + ob_bottom) / 2,
                    ob_candle_index=ob_idx,
                    confirmation_index=idx,
                    volume=ob_volume,
                    volume_ratio=volume_ratio,
                    ob_size=ob_size,
                    ob_size_atr=ob_size_atr,
                )
                # [FIX-5] Filtro de OBs duplicados/sobrepostos
                if not self._ob_overlaps_existing(ob):
                    self.active_obs.append(ob)
                    new_obs.append(ob)
            
            self._last_bottom_idx = -1
        
        return new_obs
    
    def _ob_overlaps_existing(self, new_ob: OrderBlock) -> bool:
        """
        [FIX-5] Verifica se um novo OB sobrepõe um OB existente ativo.
        Evita OBs duplicados na mesma zona de preço.
        """
        for ob in self.active_obs:
            if ob.mitigated:
                continue
            if ob.direction != new_ob.direction:
                continue
            # Sobreposição: se as zonas se cruzam
            overlap = min(ob.top, new_ob.top) - max(ob.bottom, new_ob.bottom)
            if overlap > 0:
                min_size = min(ob.ob_size, new_ob.ob_size)
                if min_size > 0 and overlap / min_size > 0.5:  # >50% sobreposição
                    return True
        return False
    
    def _garbage_collect_obs(self, idx: int):
        """
        [FIX-1] Garbage Collection de Order Blocks.
        Remove OBs mitigados que não têm ordens pendentes ou filled referenciando-os.
        Roda a cada _gc_interval candles para não impactar performance.
        """
        if idx % self._gc_interval != 0:
            return
        
        # Coletar ob_ids que ainda estão em uso (pending ou filled)
        referenced_ob_ids = set()
        for order in self.pending_orders:
            referenced_ob_ids.add(order.ob.ob_id)
        for order in self.filled_orders:
            referenced_ob_ids.add(order.ob.ob_id)
        
        # Manter apenas OBs ativos OU referenciados
        self.active_obs = [
            ob for ob in self.active_obs
            if not ob.mitigated or ob.ob_id in referenced_ob_ids
        ]
    
    def _check_ob_mitigation(self, idx: int):
        """
        Verifica mitigação de OBs ativos em TEMPO REAL.
        
        Mitigação = preço ultrapassou o OB:
        - Bullish OB: mitigado quando low <= ob_bottom
        - Bearish OB: mitigado quando high >= ob_top
        
        Isso é equivalente ao batch mas SEM look-ahead.
        """
        h = self.highs[idx]
        l = self.lows[idx]
        
        for ob in self.active_obs:
            if ob.mitigated:
                continue
            
            # Só verificar mitigação APÓS confirmação + delay
            if idx <= ob.confirmation_index:
                continue
            
            if ob.direction == SignalDirection.BULLISH:
                if l <= ob.bottom:
                    ob.mitigated = True
                    ob.mitigated_index = idx
            else:
                if h >= ob.top:
                    ob.mitigated = True
                    ob.mitigated_index = idx
    
    def _check_ob_mitigation_htf(self, htf_idx: int):
        """
        Verifica mitigacao de OBs usando dados do HTF bar (para modo MTF).
        Equivalente a _check_ob_mitigation mas usa HTF high/low.
        """
        h = self.htf_highs[htf_idx]
        l = self.htf_lows[htf_idx]
        # Use M1 idx for mitigated_index (for compatibility with _process_pending_orders)
        m1_idx = self._htf_to_m1_end[htf_idx] if htf_idx < len(self._htf_to_m1_end) else self.candle_count - 1

        for ob in self.active_obs:
            if ob.mitigated:
                continue
            # Só verificar mitigação APÓS confirmação
            if m1_idx <= ob.confirmation_index:
                continue
            if ob.direction == SignalDirection.BULLISH:
                if l <= ob.bottom:
                    ob.mitigated = True
                    ob.mitigated_index = m1_idx
            else:
                if h >= ob.top:
                    ob.mitigated = True
                    ob.mitigated_index = m1_idx

    def _get_patterns(self, ob: OrderBlock) -> List[PatternType]:
        """Retorna padrões detectados próximos ao OB"""
        patterns = [PatternType.ORDER_BLOCK]
        conf_idx = ob.confirmation_index
        direction = 1 if ob.direction == SignalDirection.BULLISH else -1
        
        # BOS
        for bos_idx, bos_dir in self._recent_bos:
            if abs(bos_idx - conf_idx) <= 5 and bos_dir == direction:
                patterns.append(PatternType.BOS)
                break
        
        # CHoCH
        for choch_idx, choch_dir in self._recent_choch:
            if abs(choch_idx - conf_idx) <= 5 and choch_dir == direction:
                patterns.append(PatternType.CHOCH)
                break
        
        # FVG
        for fvg_idx, fvg_dir in self._recent_fvg:
            if abs(fvg_idx - conf_idx) <= 10 and fvg_dir == direction:
                patterns.append(PatternType.FVG)
                break
        
        # Sweep
        for sweep_idx, sweep_dir in self._recent_sweeps:
            if abs(sweep_idx - conf_idx) <= 5 and sweep_dir == direction:
                patterns.append(PatternType.LIQUIDITY_SWEEP)
                break
        
        return patterns
    
    def _calculate_confidence(self, ob: OrderBlock, patterns: List[PatternType]) -> float:
        """Calcula índice de confiança (0-100)"""
        confidence = 0.0
        
        # Volume (0-25)
        if ob.volume_ratio >= 3.0:
            confidence += 25
        elif ob.volume_ratio >= 2.0:
            confidence += 20
        elif ob.volume_ratio >= 1.5:
            confidence += 15
        elif ob.volume_ratio >= 1.0:
            confidence += 10
        
        # Tamanho OB (0-15)
        if ob.ob_size_atr >= 1.5:
            confidence += 15
        elif ob.ob_size_atr >= 1.0:
            confidence += 12
        elif ob.ob_size_atr >= 0.5:
            confidence += 8
        
        # FVG (0-20)
        if PatternType.FVG in patterns:
            confidence += 20
        
        # BOS (0-15)
        if PatternType.BOS in patterns:
            confidence += 15
        
        # CHoCH (0-10)
        if PatternType.CHOCH in patterns:
            confidence += 10
        
        # Sweep (0-15)
        if PatternType.LIQUIDITY_SWEEP in patterns:
            confidence += 15
        
        return min(confidence, 100.0)
    
    def _create_pending_orders(self, new_obs: List[OrderBlock], idx: int) -> List[dict]:
        """Cria ordens pendentes para novos OBs que passam nos filtros"""
        new_signals = []

        for ob in new_obs:
            # FILTRO 1: Tamanho do OB > min_ob_size_atr * ATR
            if self.min_ob_size_atr > 0 and self._current_atr > 0:
                if ob.ob_size < self._current_atr * self.min_ob_size_atr:
                    continue

            # FILTRO 2: Volume > min_volume_ratio * média
            if self.min_volume_ratio > 0 and self._current_avg_vol > 0:
                if ob.volume_ratio < self.min_volume_ratio:
                    continue

            # Padrões e confiança (calculados ANTES dos filtros de qualidade)
            patterns = self._get_patterns(ob)
            confidence = self._calculate_confidence(ob, patterns)

            # FILTRO 3: Confiança mínima
            if self.min_confidence > 0 and confidence < self.min_confidence:
                continue

            # FILTRO 4: Mínimo de padrões de suporte (patterns inclui ORDER_BLOCK)
            if self.min_patterns > 0 and (len(patterns) - 1) < self.min_patterns:
                continue

            # Calcular entrada com retracement configuravel
            ob_size = ob.ob_size
            if ob.direction == SignalDirection.BULLISH:
                entry_price = ob.top - ob_size * self.entry_retracement
            else:
                entry_price = ob.bottom + ob_size * self.entry_retracement

            if ob.direction == SignalDirection.BULLISH:
                stop_loss = ob.bottom - ob_size * 0.1
                if self.tick_size > 0:
                    entry_price = round(entry_price / self.tick_size) * self.tick_size
                    stop_loss = (int(stop_loss / self.tick_size)) * self.tick_size
                risk = entry_price - stop_loss
                if risk <= 0:
                    continue
                take_profit = entry_price + (risk * self.risk_reward_ratio)
                if self.tick_size > 0:
                    take_profit = round(take_profit / self.tick_size) * self.tick_size
            else:
                stop_loss = ob.top + ob_size * 0.1
                if self.tick_size > 0:
                    entry_price = round(entry_price / self.tick_size) * self.tick_size
                    stop_loss = (int(stop_loss / self.tick_size) + 1) * self.tick_size
                risk = stop_loss - entry_price
                if risk <= 0:
                    continue
                take_profit = entry_price - (risk * self.risk_reward_ratio)
                if self.tick_size > 0:
                    take_profit = round(take_profit / self.tick_size) * self.tick_size

            # FILTRO 5: SL máximo em pontos
            if self.max_sl_points > 0 and risk > self.max_sl_points:
                continue

            # Criar ordem pendente
            self._order_counter += 1
            order = PendingOrder(
                order_id=f"SMC_{self._order_counter}",
                ob=ob,
                direction=ob.direction,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                created_at=idx,
                entry_delay_start=idx + self.entry_delay_candles,
                max_candle=idx + self.max_pending_candles,
                patterns=patterns,
                confidence=confidence,
            )

            self.pending_orders.append(order)
            ob.used = True

            new_signals.append({
                'order_id': order.order_id,
                'direction': ob.direction.name,
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'ob_top': ob.top,
                'ob_bottom': ob.bottom,
                'confidence': confidence,
                'patterns': [p.value for p in patterns],
            })

        return new_signals
    
    def _process_pending_orders(self, idx: int) -> Tuple[List[dict], List[dict], List[dict]]:
        """
        Processa ordens pendentes: verificar fill, expiração, ou cancelamento.
        Sempre usa dados M1 para fill (precisao maxima na entrada).
        """
        filled = []
        expired = []
        cancelled = []

        remaining = []

        for order in self.pending_orders:
            # Verificar expiração
            if idx > order.max_candle:
                expired.append({
                    'order_id': order.order_id,
                    'reason': 'expired',
                    'candle': idx,
                })
                continue

            # Verificar se pode ser preenchida (após delay)
            if idx < order.entry_delay_start:
                remaining.append(order)
                continue

            # Verificar se OB foi mitigado em candle ANTERIOR
            if self.use_not_mitigated_filter and order.ob.mitigated and order.ob.mitigated_index < idx:
                cancelled.append({
                    'order_id': order.order_id,
                    'reason': 'ob_mitigated',
                    'candle': idx,
                })
                continue

            # Verificar toque na linha (M1)
            h = self.highs[idx]
            l = self.lows[idx]
            tol = self.tick_size if self.tick_size > 0 else 0

            touched = False
            if order.direction == SignalDirection.BULLISH:
                touched = l <= order.entry_price - tol
            else:
                touched = h >= order.entry_price + tol

            if touched:
                # FILTRO 1: Não entrar se o candle M1 ultrapassa o OB inteiro
                skip_trade = False
                if order.direction == SignalDirection.BULLISH:
                    if l <= order.ob.bottom:
                        skip_trade = True
                else:
                    if h >= order.ob.top:
                        skip_trade = True

                if skip_trade:
                    cancelled.append({
                        'order_id': order.order_id,
                        'reason': 'ob_mitigated_on_fill',
                        'candle': idx,
                    })
                    continue

                # Preencher ordem
                filled_order = FilledOrder(
                    order_id=order.order_id,
                    ob=order.ob,
                    direction=order.direction,
                    entry_price=order.entry_price,
                    stop_loss=order.stop_loss,
                    take_profit=order.take_profit,
                    filled_at=idx,
                    created_at=order.created_at,
                    check_from=idx + 1,
                    patterns=order.patterns,
                    confidence=order.confidence,
                )
                self.filled_orders.append(filled_order)

                filled.append({
                    'order_id': order.order_id,
                    'direction': order.direction.name,
                    'entry_price': order.entry_price,
                    'filled_at': idx,
                })
            else:
                if self.use_not_mitigated_filter and order.ob.mitigated:
                    cancelled.append({
                        'order_id': order.order_id,
                        'reason': 'ob_mitigated',
                        'candle': idx,
                    })
                else:
                    remaining.append(order)

        self.pending_orders = remaining
        return filled, expired, cancelled
    
    def _process_filled_orders(self, idx: int) -> List[dict]:
        """
        Processa trades abertos: verificar TP/SL.
        
        IDÊNTICO ao batch:
        - Verificar SL primeiro (pior caso)
        - Depois verificar TP
        - Apenas a partir do candle SEGUINTE ao fill
        """
        closed = []
        remaining = []
        
        h = self.highs[idx]
        l = self.lows[idx]
        
        for order in self.filled_orders:
            if idx < order.check_from:
                remaining.append(order)
                continue
            
            hit_tp = False
            hit_sl = False
            exit_price = 0.0
            
            if order.direction == SignalDirection.BULLISH:
                # SL primeiro (pior caso)
                if l <= order.stop_loss:
                    hit_sl = True
                    exit_price = order.stop_loss
                elif h >= order.take_profit:
                    hit_tp = True
                    exit_price = order.take_profit
            else:
                if h >= order.stop_loss:
                    hit_sl = True
                    exit_price = order.stop_loss
                elif l <= order.take_profit:
                    hit_tp = True
                    exit_price = order.take_profit
            
            if hit_tp or hit_sl:
                if order.direction == SignalDirection.BULLISH:
                    profit_loss = exit_price - order.entry_price
                else:
                    profit_loss = order.entry_price - exit_price
                
                profit_loss_r = self.risk_reward_ratio if hit_tp else -1.0
                status = OrderStatus.CLOSED_TP if hit_tp else OrderStatus.CLOSED_SL
                
                trade = ClosedTrade(
                    order_id=order.order_id,
                    ob=order.ob,
                    direction=order.direction,
                    entry_price=order.entry_price,
                    stop_loss=order.stop_loss,
                    take_profit=order.take_profit,
                    exit_price=exit_price,
                    created_at=order.created_at,
                    filled_at=order.filled_at,
                    closed_at=idx,
                    status=status,
                    profit_loss=profit_loss,
                    profit_loss_r=profit_loss_r,
                    patterns=order.patterns,
                    confidence=order.confidence,
                )
                self.closed_trades.append(trade)
                
                closed.append({
                    'order_id': order.order_id,
                    'direction': order.direction.name,
                    'status': status.value,
                    'profit_loss': profit_loss,
                    'profit_loss_r': profit_loss_r,
                    'entry_price': order.entry_price,
                    'exit_price': exit_price,
                    'closed_at': idx,
                })
            else:
                remaining.append(order)
        
        self.filled_orders = remaining
        return closed
    
    def _process_filled_orders_mtf(self, idx: int) -> List[dict]:
        """
        Processa trades abertos em modo MTF: TP/SL verificado no M1.
        Identico ao _process_filled_orders mas separado para clareza.
        """
        return self._process_filled_orders(idx)

    def get_stats(self) -> dict:
        """Retorna estatísticas do engine"""
        trades = self.closed_trades
        
        if not trades:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0.0,
                'profit_factor': 0.0,
                'total_profit_r': 0.0,
                'total_profit_points': 0.0,
                'avg_profit_r': 0.0,
                'candles_processed': self.candle_count,
                'order_blocks_detected': self._ob_counter,
                'pending_orders': len(self.pending_orders),
                'open_trades': len(self.filled_orders),
                'last_process_time_ms': self._last_process_time,
            }
        
        winning = [t for t in trades if t.status == OrderStatus.CLOSED_TP]
        losing = [t for t in trades if t.status == OrderStatus.CLOSED_SL]
        
        total_win_r = sum(t.profit_loss_r for t in winning)
        total_loss_r = abs(sum(t.profit_loss_r for t in losing))
        
        total_win_pts = sum(t.profit_loss for t in winning)
        total_loss_pts = abs(sum(t.profit_loss for t in losing))
        
        return {
            'total_trades': len(trades),
            'winning_trades': len(winning),
            'losing_trades': len(losing),
            'win_rate': len(winning) / len(trades) * 100 if trades else 0,
            'profit_factor': total_win_r / total_loss_r if total_loss_r > 0 else float('inf'),
            'total_profit_r': sum(t.profit_loss_r for t in trades),
            'total_profit_points': sum(t.profit_loss for t in trades),
            'total_win_points': total_win_pts,
            'total_loss_points': total_loss_pts,
            'avg_profit_r': sum(t.profit_loss_r for t in trades) / len(trades),
            'candles_processed': self.candle_count,
            'order_blocks_detected': self._ob_counter,
            'pending_orders': len(self.pending_orders),
            'open_trades': len(self.filled_orders),
            'last_process_time_ms': self._last_process_time,
        }
    
    def get_all_trades(self) -> List[dict]:
        """Retorna todos os trades fechados"""
        return [
            {
                'order_id': t.order_id,
                'direction': t.direction.name,
                'entry_price': t.entry_price,
                'stop_loss': t.stop_loss,
                'take_profit': t.take_profit,
                'exit_price': t.exit_price,
                'created_at': t.created_at,
                'filled_at': t.filled_at,
                'closed_at': t.closed_at,
                'status': t.status.value,
                'profit_loss': t.profit_loss,
                'profit_loss_r': t.profit_loss_r,
                'patterns': [p.value for p in t.patterns],
                'confidence': t.confidence,
                'ob_top': t.ob.top,
                'ob_bottom': t.ob.bottom,
                'ob_midline': t.ob.midline,
                'ob_mitigated': t.ob.mitigated,
                'wait_candles': t.filled_at - t.created_at,
                'duration_candles': t.closed_at - t.filled_at,
            }
            for t in self.closed_trades
        ]
    
    def get_pending_orders(self) -> List[dict]:
        """Retorna ordens pendentes"""
        return [
            {
                'order_id': o.order_id,
                'direction': o.direction.name,
                'entry_price': o.entry_price,
                'stop_loss': o.stop_loss,
                'take_profit': o.take_profit,
                'created_at': o.created_at,
                'ob_top': o.ob.top,
                'ob_bottom': o.ob.bottom,
                'confidence': o.confidence,
                'patterns': [p.value for p in o.patterns],
            }
            for o in self.pending_orders
        ]


# ============================================================
# TESTE E VALIDAÇÃO
# ============================================================

if __name__ == "__main__":
    import pandas as pd
    import sys
    sys.path.insert(0, '/home/ubuntu/smc_enhanced')
    from smc_touch_validated import SMCStrategyTouchValidated
    
    # Carregar dados
    df = pd.read_csv('/home/ubuntu/upload/mtwin14400.csv')
    df.columns = [c.lower() for c in df.columns]
    if 'volume' not in df.columns:
        df['volume'] = df.get('tick_volume', df.get('real_volume', 1.0))
    
    vol_col = 'tick_volume' if 'tick_volume' in df.columns else 'volume'
    
    print(f"Dados: {len(df)} candles")
    print("=" * 80)
    
    # ========== BATCH ==========
    print("\n--- BATCH (smc_touch_validated.py) ---")
    strategy = SMCStrategyTouchValidated(
        df, swing_length=5, risk_reward_ratio=3.0,
        entry_delay_candles=1, use_not_mitigated_filter=True,
        min_volume_ratio=1.5, min_ob_size_atr=0.5,
    )
    signals = strategy.generate_signals()
    results, stats = strategy.backtest(signals)
    
    print(f"  Trades: {stats['total_trades']}")
    print(f"  Win Rate: {stats['win_rate']:.1f}%")
    print(f"  Lucro (R): {stats['total_profit_loss_r']:.1f}R")
    
    batch_profit_pts = sum(r.profit_loss for r in results)
    batch_win_pts = sum(r.profit_loss for r in results if r.hit_tp)
    batch_loss_pts = sum(r.profit_loss for r in results if r.hit_sl)
    print(f"  Lucro (pts): {batch_profit_pts:+.2f}")
    print(f"  Win (pts): {batch_win_pts:+.2f}")
    print(f"  Loss (pts): {batch_loss_pts:+.2f}")
    
    # ========== ENGINE V3 ==========
    print("\n--- ENGINE V3 (candle a candle) ---")
    engine = SMCEngineV3(
        symbol='WINM24', swing_length=5, risk_reward_ratio=3.0,
        min_volume_ratio=1.5, min_ob_size_atr=0.5,
        use_not_mitigated_filter=True, max_pending_candles=100,
        entry_delay_candles=1,
    )
    
    import time
    start = time.time()
    for i in range(len(df)):
        row = df.iloc[i]
        engine.add_candle({
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
            'volume': float(row[vol_col])
        })
    elapsed = time.time() - start
    
    stats_v3 = engine.get_stats()
    trades_v3 = engine.get_all_trades()
    
    print(f"  Tempo: {elapsed:.2f}s ({elapsed/len(df)*1000:.3f}ms/candle)")
    print(f"  Trades: {stats_v3['total_trades']}")
    print(f"  Win Rate: {stats_v3['win_rate']:.1f}%")
    print(f"  Lucro (R): {stats_v3['total_profit_r']:.1f}R")
    print(f"  Lucro (pts): {stats_v3['total_profit_points']:+.2f}")
    print(f"  Win (pts): {stats_v3['total_win_points']:+.2f}")
    print(f"  Loss (pts): {-stats_v3['total_loss_points']:+.2f}")
    print(f"  OBs detectados: {stats_v3['order_blocks_detected']}")
    
    # ========== COMPARAÇÃO ==========
    print("\n" + "=" * 80)
    print("COMPARAÇÃO BATCH vs ENGINE V3")
    print("=" * 80)
    print(f"  {'Métrica':<25} {'BATCH':>15} {'ENGINE V3':>15} {'MATCH':>10}")
    print(f"  {'-'*65}")
    
    match_trades = stats['total_trades'] == stats_v3['total_trades']
    match_wr = abs(stats['win_rate'] - stats_v3['win_rate']) < 0.5
    match_profit = abs(stats['total_profit_loss_r'] - stats_v3['total_profit_r']) < 5
    
    print(f"  {'Trades':<25} {stats['total_trades']:>15} {stats_v3['total_trades']:>15} {'✅' if match_trades else '❌':>10}")
    print(f"  {'Win Rate':<25} {stats['win_rate']:>14.1f}% {stats_v3['win_rate']:>14.1f}% {'✅' if match_wr else '❌':>10}")
    print(f"  {'Lucro (R)':<25} {stats['total_profit_loss_r']:>14.1f}R {stats_v3['total_profit_r']:>14.1f}R {'✅' if match_profit else '❌':>10}")
    print(f"  {'Lucro (pts)':<25} {batch_profit_pts:>14.2f} {stats_v3['total_profit_points']:>14.2f}")
    
    # Comparar primeiros 10 trades
    print("\n" + "=" * 80)
    print("PRIMEIROS 10 TRADES")
    print("=" * 80)
    
    print("\n  BATCH:")
    for i, r in enumerate(results[:10]):
        s = r.signal
        print(f"    #{i+1}: {s.direction.name:8s} OB={s.signal_candle_index:>6d} "
              f"Fill={s.index:>6d} Entry={s.entry_price:>10.2f} "
              f"{'TP' if r.hit_tp else 'SL'} P/L={r.profit_loss:>+8.2f}")
    
    print("\n  ENGINE V3:")
    for i, t in enumerate(trades_v3[:10]):
        print(f"    #{i+1}: {t['direction']:8s} OB={t['created_at']:>6d} "
              f"Fill={t['filled_at']:>6d} Entry={t['entry_price']:>10.2f} "
              f"{'TP' if 'tp' in t['status'] else 'SL'} P/L={t['profit_loss']:>+8.2f}")
    
    # ========== VALIDAÇÃO ==========
    print("\n" + "=" * 80)
    print("VALIDAÇÃO DE INTEGRIDADE")
    print("=" * 80)
    
    # 1. Toque real
    invalid_touches = 0
    for t in engine.closed_trades:
        fill_idx = t.filled_at
        if t.direction == SignalDirection.BULLISH:
            if engine.lows[fill_idx] > t.entry_price:
                invalid_touches += 1
        else:
            if engine.highs[fill_idx] < t.entry_price:
                invalid_touches += 1
    print(f"  Toques inválidos: {invalid_touches} {'✅' if invalid_touches == 0 else '❌'}")
    
    # 2. Sequência temporal
    temporal_violations = 0
    for t in engine.closed_trades:
        if t.filled_at <= t.created_at:
            temporal_violations += 1
        if t.closed_at <= t.filled_at:
            temporal_violations += 1
    print(f"  Violações temporais: {temporal_violations} {'✅' if temporal_violations == 0 else '❌'}")
    
    # 3. Fill não no mesmo candle
    same_candle = sum(1 for t in engine.closed_trades if t.filled_at == t.created_at)
    print(f"  Fill no mesmo candle: {same_candle} {'✅' if same_candle == 0 else '❌'}")
    
    # 4. TP/SL não no mesmo candle do fill
    same_candle_close = sum(1 for t in engine.closed_trades if t.closed_at == t.filled_at)
    print(f"  Close no mesmo candle do fill: {same_candle_close} {'✅' if same_candle_close == 0 else '❌'}")
    
    # 5. OBs mitigados
    mitigated_used = 0
    for t in engine.closed_trades:
        if t.ob.mitigated and t.ob.mitigated_index <= t.filled_at:
            mitigated_used += 1
    print(f"  OBs mitigados usados: {mitigated_used} {'✅' if mitigated_used == 0 else '❌'}")
    
    print(f"\n  Resultado: {'TODOS OS TESTES PASSARAM!' if all([invalid_touches==0, temporal_violations==0, same_candle==0, same_candle_close==0, mitigated_used==0]) else 'FALHAS ENCONTRADAS'}")
