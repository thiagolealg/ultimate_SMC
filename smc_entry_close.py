"""
Smart Money Concepts - Versão com Entrada no CLOSE do Candle
============================================================
Entrada no CLOSE do candle que tocou o Order Block
Stop Loss e Take Profit projetados a partir do preço de entrada real
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
    """Sinal de trade"""
    index: int                    # Índice do candle de ENTRADA
    direction: SignalDirection    # Direção do trade
    entry_price: float            # Preço de entrada (CLOSE do candle)
    stop_loss: float              # Stop Loss
    take_profit: float            # Take Profit
    confidence: float             # Confiança (0-100)
    ob_top: float                 # Topo do Order Block
    ob_bottom: float              # Fundo do Order Block
    risk_reward_ratio: float      # Ratio R:R
    signal_candle_index: int      # Índice onde OB foi confirmado
    ob_candle_index: int          # Índice do candle que forma o OB
    quality_score: float          # Score de qualidade


@dataclass
class BacktestResult:
    """Resultado de um trade no backtest"""
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


class SMCEntryClose:
    """
    Smart Money Concepts com entrada no CLOSE do candle
    """
    
    @classmethod
    def swing_highs_lows(cls, ohlc: pd.DataFrame, swing_length: int = 5) -> pd.DataFrame:
        """
        Detecta Swing Highs e Lows SEM look-ahead bias.
        Um swing high é confirmado quando swing_length candles subsequentes têm máximas menores.
        """
        ohlc = validate_ohlc(ohlc)
        n = len(ohlc)
        
        swing_high = np.full(n, np.nan)
        swing_low = np.full(n, np.nan)
        swing_high_level = np.full(n, np.nan)
        swing_low_level = np.full(n, np.nan)
        
        for i in range(swing_length, n):
            # Verificar swing high
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
            
            # Verificar swing low
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
        """
        Detecta Order Blocks SEM look-ahead bias.
        """
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
            # Atualizar último swing high
            if swings['swing_high'].iloc[i] == 1:
                last_top_idx = i - swing_length
                last_top_level = swings['swing_high_level'].iloc[i]
            
            # Atualizar último swing low
            if swings['swing_low'].iloc[i] == 1:
                last_bottom_idx = i - swing_length
                last_bottom_level = swings['swing_low_level'].iloc[i]
            
            # Bullish OB: preço rompe acima do último swing high
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
                    
                    # Verificar mitigação
                    for k in range(i + 1, n):
                        if _low[k] <= ob_bottom[i]:
                            mitigated_index[i] = k
                            break
                
                last_top_idx = -1
            
            # Bearish OB: preço rompe abaixo do último swing low
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
                    
                    # Verificar mitigação
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


class OrderBlockStrategyEntryClose:
    """
    Estratégia de Order Block com entrada no CLOSE do candle que tocou o OB.
    """
    
    def __init__(
        self,
        ohlc: pd.DataFrame,
        swing_length: int = 5,
        risk_reward_ratio: float = 1.0,
        min_confidence: float = 30.0,
        entry_delay_candles: int = 1,
        use_not_mitigated_filter: bool = True,
    ):
        self.ohlc = validate_ohlc(ohlc)
        self.swing_length = swing_length
        self.risk_reward_ratio = risk_reward_ratio
        self.min_confidence = min_confidence
        self.entry_delay_candles = entry_delay_candles
        self.use_not_mitigated_filter = use_not_mitigated_filter
        
        # Calcular indicadores
        self.swings = SMCEntryClose.swing_highs_lows(self.ohlc, swing_length)
        self.order_blocks = SMCEntryClose.order_blocks(self.ohlc, swing_length)
    
    def calculate_confidence(self, ob_index: int) -> float:
        """Calcula confiança do Order Block"""
        confidence = 50.0
        
        ob_volume = self.order_blocks['Volume'].iloc[ob_index]
        if not np.isnan(ob_volume):
            avg_volume = self.ohlc['volume'].iloc[max(0, ob_index-20):ob_index].mean()
            if avg_volume > 0 and ob_volume > avg_volume * 1.5:
                confidence += 20
        
        ob_top = self.order_blocks['Top'].iloc[ob_index]
        ob_bottom = self.order_blocks['Bottom'].iloc[ob_index]
        ob_size = ob_top - ob_bottom
        
        avg_range = (self.ohlc['high'] - self.ohlc['low']).iloc[max(0, ob_index-20):ob_index].mean()
        if avg_range > 0 and ob_size > avg_range * 1.2:
            confidence += 15
        
        return min(100.0, confidence)
    
    def generate_signals(self) -> List[TradeSignal]:
        """
        Gera sinais de trade com entrada no CLOSE do candle que tocou o OB.
        """
        signals = []
        n = len(self.ohlc)
        
        ob_indices = self.order_blocks[~self.order_blocks['OB'].isna()].index
        
        for idx in ob_indices:
            i = self.ohlc.index.get_loc(idx)
            
            ob_direction = self.order_blocks['OB'].iloc[i]
            ob_top = self.order_blocks['Top'].iloc[i]
            ob_bottom = self.order_blocks['Bottom'].iloc[i]
            ob_candle = self.order_blocks['OBCandle'].iloc[i]
            
            confidence = self.calculate_confidence(i)
            
            if confidence < self.min_confidence:
                continue
            
            entry_start = i + self.entry_delay_candles
            
            for j in range(entry_start, min(n, i + 100)):
                # Verificar mitigação
                mitigated = self.order_blocks['MitigatedIndex'].iloc[i]
                if self.use_not_mitigated_filter:
                    if not np.isnan(mitigated) and j >= mitigated:
                        break
                
                current_high = self.ohlc['high'].iloc[j]
                current_low = self.ohlc['low'].iloc[j]
                current_close = self.ohlc['close'].iloc[j]
                
                # Bullish OB - preço toca a região do OB
                if ob_direction == 1:
                    if current_low <= ob_top:
                        # ENTRADA NO CLOSE DO CANDLE QUE TOCOU O OB
                        entry_price = current_close
                        
                        # Stop Loss abaixo do fundo do OB
                        stop_loss = ob_bottom - (ob_top - ob_bottom) * 0.1
                        
                        # Calcular risco a partir do preço de entrada real
                        risk = entry_price - stop_loss
                        
                        # Se o risco for negativo ou muito pequeno, pular
                        if risk <= 0:
                            break
                        
                        # Take Profit projetado a partir da entrada
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
                
                # Bearish OB - preço toca a região do OB
                elif ob_direction == -1:
                    if current_high >= ob_bottom:
                        # ENTRADA NO CLOSE DO CANDLE QUE TOCOU O OB
                        entry_price = current_close
                        
                        # Stop Loss acima do topo do OB
                        stop_loss = ob_top + (ob_top - ob_bottom) * 0.1
                        
                        # Calcular risco a partir do preço de entrada real
                        risk = stop_loss - entry_price
                        
                        # Se o risco for negativo ou muito pequeno, pular
                        if risk <= 0:
                            break
                        
                        # Take Profit projetado a partir da entrada
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
    
    def backtest(self, signals: Optional[List[TradeSignal]] = None) -> Tuple[List[BacktestResult], Dict]:
        """
        Executa backtest.
        A entrada é no CLOSE do candle de sinal, então verificamos TP/SL a partir do próximo candle.
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
            
            # Começar a verificar TP/SL a partir do PRÓXIMO candle após a entrada
            for k in range(entry_index + 1, min(n, entry_index + 500)):
                high = self.ohlc['high'].iloc[k]
                low = self.ohlc['low'].iloc[k]
                
                if signal.direction == SignalDirection.BULLISH:
                    # Verificar SL primeiro (mais conservador)
                    if low <= signal.stop_loss:
                        exit_index = k
                        exit_price = signal.stop_loss
                        hit_sl = True
                        break
                    # Verificar TP
                    if high >= signal.take_profit:
                        exit_index = k
                        exit_price = signal.take_profit
                        hit_tp = True
                        break
                else:  # BEARISH
                    # Verificar SL primeiro
                    if high >= signal.stop_loss:
                        exit_index = k
                        exit_price = signal.stop_loss
                        hit_sl = True
                        break
                    # Verificar TP
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
        
        # Calcular estatísticas
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
                'avg_profit_loss': np.mean([r.profit_loss for r in results]),
                'avg_win': np.mean([r.profit_loss for r in winning]) if winning else 0,
                'avg_loss': np.mean([r.profit_loss for r in losing]) if losing else 0,
                'profit_factor': total_profit / total_loss if total_loss > 0 else float('inf'),
                'avg_duration': np.mean([r.duration_candles for r in results]),
            }
        else:
            stats = {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'total_profit_loss': 0,
                'avg_profit_loss': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'profit_factor': 0,
                'avg_duration': 0,
            }
        
        return results, stats


def test_strategy():
    """Testa a estratégia com dados reais"""
    print("=" * 70)
    print("TESTE - ENTRADA NO CLOSE DO CANDLE QUE TOCOU O OB")
    print("=" * 70)
    
    # Carregar dados
    df = pd.read_csv('/home/ubuntu/smc_enhanced/data.csv')
    df.columns = [c.lower() for c in df.columns]
    df['time'] = pd.to_datetime(df['time'])
    df.set_index('time', inplace=True)
    
    print(f"\nDados: {len(df)} candles")
    
    # Testar com diferentes RR
    for rr in [1.0, 2.0, 3.0]:
        print(f"\n{'-'*50}")
        print(f"RISK:REWARD {rr}:1")
        print(f"{'-'*50}")
        
        strategy = OrderBlockStrategyEntryClose(
            df,
            swing_length=5,
            risk_reward_ratio=rr,
            min_confidence=30.0,
            entry_delay_candles=1,
            use_not_mitigated_filter=True,
        )
        
        signals = strategy.generate_signals()
        results, stats = strategy.backtest(signals)
        
        # Calcular lucro em R
        total_r = 0
        for result in results:
            if result.hit_tp:
                total_r += rr
            elif result.hit_sl:
                total_r -= 1
        
        expectancy = total_r / len(results) if len(results) > 0 else 0
        
        print(f"\n   Trades: {stats['total_trades']}")
        print(f"   Win Rate: {stats['win_rate']:.1f}%")
        print(f"   Profit Factor: {stats['profit_factor']:.2f}")
        print(f"   Lucro (R): {total_r:.1f}R")
        print(f"   Lucro (Pontos): {stats['total_profit_loss']:.2f}")
        print(f"   Expectativa: {expectancy:.2f}R por trade")
        print(f"   Duração média: {stats['avg_duration']:.1f} candles")


if __name__ == "__main__":
    test_strategy()
