                    break
        
        return patterns
    
    def generate_signals(self) -> List[TradeSignal]:
        """Gera sinais com validação rigorosa de toque na linha"""
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
            
            # Linha do meio do OB
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
            
            # Buscar entrada
            entry_start = i + self.entry_delay_candles
            direction = SignalDirection.BULLISH if ob_direction == 1 else SignalDirection.BEARISH
            
            for j in range(entry_start, min(n, i + 100)):
                # FILTRO 3: OB não mitigado
                if self.use_not_mitigated_filter:
                    mitigated = self.order_blocks['MitigatedIndex'].iloc[i]
                    if not np.isnan(mitigated) and j >= mitigated:
                        break
                
                current_high = self.ohlc['high'].iloc[j]
                current_low = self.ohlc['low'].iloc[j]
                current_open = self.ohlc['open'].iloc[j]
                current_close = self.ohlc['close'].iloc[j]
                
                # VALIDAR TOQUE NA LINHA
                touch_validation = TouchValidator.validate_touch(
                    candle_high=current_high,
                    candle_low=current_low,
                    candle_open=current_open,
                    candle_close=current_close,
                    target_line=midline,
                    direction=direction,
                    candle_index=j,
                    tolerance_pct=self.touch_tolerance_pct
                )
                
                if touch_validation.is_valid:
                    # Entrada no preço da linha (ordem limit)
                    entry_price = midline
                    
                    if direction == SignalDirection.BULLISH:
                        stop_loss = ob_bottom - ob_size * 0.1
                        risk = entry_price - stop_loss
                        
                        if risk <= 0:
                            break
                        
                        take_profit = entry_price + (risk * self.risk_reward_ratio)
                    else:
                        stop_loss = ob_top + ob_size * 0.1
                        risk = stop_loss - entry_price