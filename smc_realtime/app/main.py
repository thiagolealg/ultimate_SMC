"""
SMC Realtime API - API REST e WebSocket para estratégias SMC em tempo real
=========================================================================

Endpoints:
- POST /candle - Recebe novo candle
- GET /signals - Lista sinais ativos
- GET /orders/pending - Lista ordens pendentes
- GET /orders/filled - Lista ordens preenchidas
- GET /stats - Estatísticas do engine
- WebSocket /ws - Comunicação em tempo real
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from smc_engine import SMCEngine, get_engine, TradeSignal, SignalDirection

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Modelos Pydantic
class CandleInput(BaseModel):
    symbol: str = "WINM24"
    time: str
    open: float
    high: float
    low: float
    close: float
    volume: float = 1.0


class CandleBatch(BaseModel):
    symbol: str = "WINM24"
    candles: List[CandleInput]


class EngineConfig(BaseModel):
    symbol: str = "WINM24"
    swing_length: int = 5
    risk_reward_ratio: float = 3.0
    min_volume_ratio: float = 1.5
    min_ob_size_atr: float = 0.5
    use_not_mitigated_filter: bool = True


class SignalResponse(BaseModel):
    timestamp: str
    symbol: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    ob_top: float
    ob_bottom: float
    risk_reward_ratio: float
    patterns: List[str]
    confidence: float
    risk_points: float
    reward_points: float


# Gerenciador de WebSocket
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket conectado. Total: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"WebSocket desconectado. Total: {len(self.active_connections)}")
    
    async def broadcast(self, message: dict):
        """Envia mensagem para todos os clientes conectados"""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Erro ao enviar mensagem: {e}")


manager = ConnectionManager()


# Lifecycle
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("SMC Realtime API iniciando...")
    yield
    logger.info("SMC Realtime API encerrando...")


# Criar aplicação FastAPI
app = FastAPI(
    title="SMC Realtime API",
    description="API para estratégias Smart Money Concepts em tempo real",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Endpoints REST

@app.get("/")
async def root():
    """Health check"""
    return {
        "status": "online",
        "service": "SMC Realtime API",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat()
    }


@app.post("/engine/create")
async def create_engine(config: EngineConfig):
    """Cria ou reconfigura um engine para um símbolo"""
    from smc_engine import engines
    
    engine = SMCEngine(
        symbol=config.symbol,
        swing_length=config.swing_length,
        risk_reward_ratio=config.risk_reward_ratio,
        min_volume_ratio=config.min_volume_ratio,
        min_ob_size_atr=config.min_ob_size_atr,
        use_not_mitigated_filter=config.use_not_mitigated_filter
    )
    
    engines[config.symbol] = engine
    
    return {
        "status": "created",
        "symbol": config.symbol,
        "config": config.dict()
    }


@app.post("/candle", response_model=List[SignalResponse])
async def receive_candle(candle: CandleInput):
    """
    Recebe um novo candle e processa em tempo real.
    Retorna lista de sinais gerados.
    """
    engine = get_engine(candle.symbol)
    
    signals = engine.add_candle({
        'time': candle.time,
        'open': candle.open,
        'high': candle.high,
        'low': candle.low,
        'close': candle.close,
        'volume': candle.volume
    })
    
    # Converter sinais para response
    response_signals = []
    for signal in signals:
        sig_response = SignalResponse(
            timestamp=signal.timestamp,
            symbol=signal.symbol,
            direction=signal.direction.name,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            ob_top=signal.ob_top,
            ob_bottom=signal.ob_bottom,
            risk_reward_ratio=signal.risk_reward_ratio,
            patterns=[p.value for p in signal.patterns],
            confidence=signal.confidence,
            risk_points=signal.risk_points,
            reward_points=signal.reward_points
        )
        response_signals.append(sig_response)
        
        # Broadcast via WebSocket
        await manager.broadcast({
            "type": "signal",
            "data": sig_response.dict()
        })
    
    return response_signals


@app.post("/candles/batch")
async def receive_candles_batch(batch: CandleBatch):
    """
    Recebe múltiplos candles de uma vez (para carga inicial ou histórico).
    """
    engine = get_engine(batch.symbol)
    all_signals = []
    
    for candle in batch.candles:
        signals = engine.add_candle({
            'time': candle.time,
            'open': candle.open,
            'high': candle.high,
            'low': candle.low,
            'close': candle.close,
            'volume': candle.volume
        })
        all_signals.extend(signals)
    
    return {
        "status": "processed",
        "candles_processed": len(batch.candles),
        "signals_generated": len(all_signals)
    }


@app.get("/orders/pending")
async def get_pending_orders(symbol: str = "WINM24"):
    """Lista ordens pendentes (limit orders aguardando execução)"""
    engine = get_engine(symbol)
    return {
        "symbol": symbol,
        "orders": engine.get_pending_orders()
    }


@app.get("/orders/filled")
async def get_filled_orders(symbol: str = "WINM24"):
    """Lista ordens preenchidas (trades abertos)"""
    engine = get_engine(symbol)
    return {
        "symbol": symbol,
        "orders": engine.get_filled_orders()
    }


@app.get("/orders/closed")
async def get_closed_orders(symbol: str = "WINM24"):
    """Lista ordens fechadas (histórico de trades)"""
    engine = get_engine(symbol)
    return {
        "symbol": symbol,
        "orders": [
            {
                'id': o.id,
                'symbol': o.symbol,
                'direction': o.direction.name,
                'entry_price': o.entry_price,
                'stop_loss': o.stop_loss,
                'take_profit': o.take_profit,
                'profit_loss': o.profit_loss,
                'status': o.status.value,
                'patterns': [p.value for p in o.patterns],
                'confidence': o.confidence
            }
            for o in engine.closed_orders
        ]
    }


@app.delete("/orders/{order_id}")
async def cancel_order(order_id: str, symbol: str = "WINM24"):
    """Cancela uma ordem pendente"""
    engine = get_engine(symbol)
    success = engine.cancel_order(order_id)
    
    if success:
        return {"status": "cancelled", "order_id": order_id}
    else:
        raise HTTPException(status_code=404, detail="Ordem não encontrada")


@app.get("/stats")
async def get_stats(symbol: str = "WINM24"):
    """Retorna estatísticas do engine"""
    engine = get_engine(symbol)
    return engine.get_stats()


@app.get("/order_blocks")
async def get_order_blocks(symbol: str = "WINM24", limit: int = 50):
    """Lista Order Blocks detectados"""
    engine = get_engine(symbol)
    
    obs = engine.order_blocks[-limit:]
    return {
        "symbol": symbol,
        "total": len(engine.order_blocks),
        "order_blocks": [
            {
                'index': ob.index,
                'direction': ob.direction.name,
                'top': ob.top,
                'bottom': ob.bottom,
                'midline': ob.midline,
                'is_mitigated': ob.is_mitigated,
                'patterns': [p.value for p in ob.patterns],
                'confidence': ob.confidence
            }
            for ob in obs
        ]
    }


# WebSocket

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket para comunicação em tempo real.
    
    Mensagens enviadas:
    - {"type": "signal", "data": {...}} - Novo sinal de trade
    - {"type": "order_filled", "data": {...}} - Ordem preenchida
    - {"type": "order_closed", "data": {...}} - Ordem fechada
    - {"type": "stats", "data": {...}} - Estatísticas atualizadas
    
    Mensagens recebidas:
    - {"action": "subscribe", "symbol": "WINM24"} - Inscrever em símbolo
    - {"action": "candle", "data": {...}} - Enviar candle
    """
    await manager.connect(websocket)
    
    try:
        while True:
            data = await websocket.receive_json()
            
            action = data.get("action")
            
            if action == "candle":
                # Processar candle recebido via WebSocket
                candle_data = data.get("data", {})
                symbol = candle_data.get("symbol", "WINM24")
                engine = get_engine(symbol)
                
                signals = engine.add_candle(candle_data)
                
                # Enviar sinais de volta
                for signal in signals:
                    await websocket.send_json({
                        "type": "signal",
                        "data": {
                            "timestamp": signal.timestamp,
                            "symbol": signal.symbol,
                            "direction": signal.direction.name,
                            "entry_price": signal.entry_price,
                            "stop_loss": signal.stop_loss,
                            "take_profit": signal.take_profit,
                            "patterns": [p.value for p in signal.patterns],
                            "confidence": signal.confidence
                        }
                    })
                
                # Enviar stats atualizadas
                await websocket.send_json({
                    "type": "stats",
                    "data": engine.get_stats()
                })
            
            elif action == "get_stats":
                symbol = data.get("symbol", "WINM24")
                engine = get_engine(symbol)
                await websocket.send_json({
                    "type": "stats",
                    "data": engine.get_stats()
                })
            
            elif action == "get_pending":
                symbol = data.get("symbol", "WINM24")
                engine = get_engine(symbol)
                await websocket.send_json({
                    "type": "pending_orders",
                    "data": engine.get_pending_orders()
                })
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Erro no WebSocket: {e}")
        manager.disconnect(websocket)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        workers=1
    )
