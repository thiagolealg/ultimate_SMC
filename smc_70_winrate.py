                        continue
                
                # Bullish OB
                if ob_direction == 1:
                    if current_low <= ob_top:
                        quality_score = self.calculate_quality_score(i, j)
                        
                        if quality_score < self.min_quality_score:
                            break
                        
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
                            quality_score=quality_score,
                        )
                        signals.append(signal)
                        break
                
                # Bearish OB
                elif ob_direction == -1:
                    if current_high >= ob_bottom:
                        quality_score = self.calculate_quality_score(i, j)
                        
                        if quality_score < self.min_quality_score:
                            break
                        
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
                            quality_score=quality_score,
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