"""
Serviço de Alertas - Envia notificações de sinais via Telegram e Webhook
"""

import asyncio
import aiohttp
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class AlertService:
    """Serviço de alertas para sinais de trade"""
    
    def __init__(
        self,
        telegram_bot_token: str = "",
        telegram_chat_id: str = "",
        webhook_url: str = ""
    ):
        self.telegram_bot_token = telegram_bot_token
        self.telegram_chat_id = telegram_chat_id
        self.webhook_url = webhook_url
    
    async def send_signal_alert(self, signal: Dict[str, Any]):
        """Envia alerta de novo sinal"""
        tasks = []
        
        if self.telegram_bot_token and self.telegram_chat_id:
            tasks.append(self._send_telegram(signal))
        
        if self.webhook_url:
            tasks.append(self._send_webhook(signal))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _send_telegram(self, signal: Dict[str, Any]):
        """Envia mensagem via Telegram"""
        try:
            direction_emoji = "🟢" if signal.get("direction") == "BULLISH" else "🔴"
            patterns = ", ".join(signal.get("patterns", []))
            
            message = f"""
{direction_emoji} *NOVO SINAL SMC*

📊 *Símbolo:* {signal.get('symbol')}
📈 *Direção:* {signal.get('direction')}
💰 *Entrada:* {signal.get('entry_price', 0):.2f}
🛑 *Stop Loss:* {signal.get('stop_loss', 0):.2f}
🎯 *Take Profit:* {signal.get('take_profit', 0):.2f}
📐 *R:R:* {signal.get('risk_reward_ratio', 0):.1f}
🎲 *Confiança:* {signal.get('confidence', 0):.1f}%
🏷️ *Padrões:* {patterns}

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
            
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            
            async with aiohttp.ClientSession() as session:
                await session.post(url, json={
                    "chat_id": self.telegram_chat_id,
                    "text": message,
                    "parse_mode": "Markdown"
                })
            
            logger.info("Alerta Telegram enviado")
        
        except Exception as e:
            logger.error(f"Erro ao enviar Telegram: {e}")
    
    async def _send_webhook(self, signal: Dict[str, Any]):
        """Envia dados via Webhook"""
        try:
            payload = {
                "event": "new_signal",
                "timestamp": datetime.now().isoformat(),
                "data": signal
            }
            
            async with aiohttp.ClientSession() as session:
                await session.post(
                    self.webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
            
            logger.info("Alerta Webhook enviado")
        
        except Exception as e:
            logger.error(f"Erro ao enviar Webhook: {e}")
    
    async def send_order_filled_alert(self, order: Dict[str, Any]):
        """Envia alerta de ordem preenchida"""
        if self.telegram_bot_token and self.telegram_chat_id:
            try:
                direction_emoji = "🟢" if order.get("direction") == "BULLISH" else "🔴"
                
                message = f"""
✅ *ORDEM PREENCHIDA*

{direction_emoji} *{order.get('symbol')}* {order.get('direction')}
💰 *Entrada:* {order.get('entry_price', 0):.2f}
🛑 *SL:* {order.get('stop_loss', 0):.2f}
🎯 *TP:* {order.get('take_profit', 0):.2f}

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
                
                url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
                
                async with aiohttp.ClientSession() as session:
                    await session.post(url, json={
                        "chat_id": self.telegram_chat_id,
                        "text": message,
                        "parse_mode": "Markdown"
                    })
            
            except Exception as e:
                logger.error(f"Erro ao enviar alerta de ordem: {e}")
    
    async def send_order_closed_alert(self, order: Dict[str, Any]):
        """Envia alerta de ordem fechada"""
        if self.telegram_bot_token and self.telegram_chat_id:
            try:
                is_win = order.get("profit_loss", 0) > 0
                result_emoji = "🎉" if is_win else "😔"
                
                message = f"""
{result_emoji} *ORDEM FECHADA*

📊 *{order.get('symbol')}*
💵 *Resultado:* {order.get('profit_loss', 0):+.2f} pts
📈 *Status:* {"TP atingido" if is_win else "SL atingido"}

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
                
                url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
                
                async with aiohttp.ClientSession() as session:
                    await session.post(url, json={
                        "chat_id": self.telegram_chat_id,
                        "text": message,
                        "parse_mode": "Markdown"
                    })
            
            except Exception as e:
                logger.error(f"Erro ao enviar alerta de fechamento: {e}")


# Instância global
alert_service: Optional[AlertService] = None


def get_alert_service() -> AlertService:
    """Obtém instância do serviço de alertas"""
    global alert_service
    if alert_service is None:
        import os
        alert_service = AlertService(
            telegram_bot_token=os.getenv("ALERT_TELEGRAM_BOT_TOKEN", ""),
            telegram_chat_id=os.getenv("ALERT_TELEGRAM_CHAT_ID", ""),
            webhook_url=os.getenv("ALERT_WEBHOOK_URL", "")
        )
    return alert_service
