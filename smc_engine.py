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
