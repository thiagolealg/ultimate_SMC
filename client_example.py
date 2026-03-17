"""
Cliente de Exemplo - Envia dados para a API SMC Realtime
========================================================

Este script demonstra como enviar dados de candles para a API
em tempo real usando REST ou WebSocket.
"""

import asyncio
import aiohttp
import json
import pandas as pd
from datetime import datetime
from typing import Optional


class SMCClient:
    """Cliente para a API SMC Realtime"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.ws_url = base_url.replace("http", "ws") + "/ws"
        self.session: Optional[aiohttp.ClientSession] = None
        self.ws: Optional[aiohttp.ClientWebSocketResponse] = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.ws:
            await self.ws.close()
        if self.session:
            await self.session.close()
    
    # ==================== REST API ====================
    
    async def send_candle(self, candle: dict) -> dict:
        """Envia um candle via REST API"""
        async with self.session.post(
            f"{self.base_url}/candle",
            json=candle
        ) as response:
            return await response.json()
    
    async def send_candles_batch(self, symbol: str, candles: list) -> dict:
        """Envia múltiplos candles de uma vez"""
        async with self.session.post(
            f"{self.base_url}/candles/batch",
            json={"symbol": symbol, "candles": candles}
        ) as response:
            return await response.json()
    
    async def get_stats(self, symbol: str = "WINM24") -> dict:
        """Obtém estatísticas do engine"""
        async with self.session.get(
            f"{self.base_url}/stats",
            params={"symbol": symbol}
        ) as response:
            return await response.json()
    
    async def get_pending_orders(self, symbol: str = "WINM24") -> dict:
        """Obtém ordens pendentes"""
        async with self.session.get(
            f"{self.base_url}/orders/pending",
            params={"symbol": symbol}
        ) as response:
            return await response.json()
    
    async def get_filled_orders(self, symbol: str = "WINM24") -> dict:
        """Obtém ordens preenchidas"""
        async with self.session.get(
            f"{self.base_url}/orders/filled",
            params={"symbol": symbol}
        ) as response:
            return await response.json()
    
    async def get_order_blocks(self, symbol: str = "WINM24", limit: int = 50) -> dict:
        """Obtém Order Blocks detectados"""
        async with self.session.get(
            f"{self.base_url}/order_blocks",
            params={"symbol": symbol, "limit": limit}
        ) as response:
            return await response.json()
    
    # ==================== WebSocket ====================
    
    async def connect_ws(self):
        """Conecta via WebSocket"""
        self.ws = await self.session.ws_connect(self.ws_url)
        print(f"Conectado ao WebSocket: {self.ws_url}")
    
    async def send_candle_ws(self, candle: dict):
        """Envia candle via WebSocket"""
        await self.ws.send_json({
            "action": "candle",
            "data": candle
        })
    
    async def receive_ws(self) -> dict:
        """Recebe mensagem do WebSocket"""
        msg = await self.ws.receive()
        if msg.type == aiohttp.WSMsgType.TEXT:
            return json.loads(msg.data)
        return {}


async def example_rest_api():
    """Exemplo de uso da REST API"""
    print("=" * 60)
    print("Exemplo REST API")
    print("=" * 60)
    
    async with SMCClient() as client:
        # Enviar alguns candles de exemplo
        candles = [
            {
                "symbol": "WINM24",
                "time": "2024-01-01 09:00:00",
                "open": 100000,
                "high": 100100,
                "low": 99900,
                "close": 100050,
                "volume": 1000
            },
            {
                "symbol": "WINM24",
                "time": "2024-01-01 09:01:00",
                "open": 100050,
                "high": 100150,
                "low": 99950,
                "close": 100100,
                "volume": 1200
            }
        ]
        
        for candle in candles:
            result = await client.send_candle(candle)
            print(f"Candle enviado: {candle['time']}")
            if result:
                print(f"  Sinais gerados: {len(result)}")
        
        # Obter estatísticas
        stats = await client.get_stats()
        print(f"\nEstatísticas:")
        print(f"  Candles processados: {stats.get('candles_processed', 0)}")
        print(f"  Order Blocks: {stats.get('order_blocks_detected', 0)}")


async def example_websocket():
    """Exemplo de uso do WebSocket"""
    print("=" * 60)
    print("Exemplo WebSocket")
    print("=" * 60)
    
    async with SMCClient() as client:
        await client.connect_ws()
        
        # Enviar candle via WebSocket
        candle = {
            "symbol": "WINM24",
            "time": "2024-01-01 09:02:00",
            "open": 100100,
            "high": 100200,
            "low": 100000,
            "close": 100150,
            "volume": 1500
        }
        
        await client.send_candle_ws(candle)
        print(f"Candle enviado via WS: {candle['time']}")
        
        # Receber resposta
        response = await client.receive_ws()
        print(f"Resposta: {response.get('type')}")


async def example_load_csv():
    """Exemplo de carga de dados de um CSV"""
    print("=" * 60)
    print("Exemplo Carga de CSV")
    print("=" * 60)
    
    # Carregar CSV (ajuste o caminho)
    csv_path = "data/sample.csv"
    
    try:
        df = pd.read_csv(csv_path)
        df.columns = [c.lower() for c in df.columns]
        
        async with SMCClient() as client:
            # Converter para lista de dicts
            candles = []
            for _, row in df.head(1000).iterrows():  # Primeiros 1000 candles
                candles.append({
                    "symbol": "WINM24",
                    "time": str(row.get('time', '')),
                    "open": float(row['open']),
                    "high": float(row['high']),
                    "low": float(row['low']),
                    "close": float(row['close']),
                    "volume": float(row.get('volume', row.get('tick_volume', 1)))
                })
            
            # Enviar em batch
            result = await client.send_candles_batch("WINM24", candles)
            print(f"Resultado: {result}")
            
            # Obter estatísticas
            stats = await client.get_stats()
            print(f"\nEstatísticas após carga:")
            print(f"  Candles: {stats.get('candles_processed', 0)}")
            print(f"  Order Blocks: {stats.get('order_blocks_detected', 0)}")
            print(f"  Win Rate: {stats.get('win_rate', 0):.1f}%")
    
    except FileNotFoundError:
        print(f"Arquivo não encontrado: {csv_path}")
        print("Crie um arquivo CSV com colunas: time, open, high, low, close, volume")


async def main():
    """Executa exemplos"""
    print("\n" + "=" * 60)
    print("SMC Realtime Client - Exemplos")
    print("=" * 60 + "\n")
    
    try:
        await example_rest_api()
        print()
        await example_websocket()
        print()
        await example_load_csv()
    except aiohttp.ClientConnectorError:
        print("ERRO: Não foi possível conectar à API.")
        print("Certifique-se de que o servidor está rodando:")
        print("  docker-compose up -d")


if __name__ == "__main__":
    asyncio.run(main())
