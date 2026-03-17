"""
Configurações do SMC Realtime
"""

import os
from typing import Dict, Any

# Configurações do servidor
SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))

# Configurações padrão do engine SMC
DEFAULT_ENGINE_CONFIG: Dict[str, Any] = {
    "swing_length": int(os.getenv("SWING_LENGTH", "5")),
    "risk_reward_ratio": float(os.getenv("RISK_REWARD_RATIO", "3.0")),
    "min_volume_ratio": float(os.getenv("MIN_VOLUME_RATIO", "1.5")),
    "min_ob_size_atr": float(os.getenv("MIN_OB_SIZE_ATR", "0.5")),
    "max_pending_orders": int(os.getenv("MAX_PENDING_ORDERS", "10")),
    "max_candles_history": int(os.getenv("MAX_CANDLES_HISTORY", "5000")),
    "use_not_mitigated_filter": os.getenv("USE_NOT_MITIGATED_FILTER", "true").lower() == "true"
}

# Símbolos suportados
SUPPORTED_SYMBOLS = os.getenv("SUPPORTED_SYMBOLS", "WINM24,WDOM24,PETR4,VALE3").split(",")

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Alertas
ALERT_WEBHOOK_URL = os.getenv("ALERT_WEBHOOK_URL", "")
ALERT_TELEGRAM_BOT_TOKEN = os.getenv("ALERT_TELEGRAM_BOT_TOKEN", "")
ALERT_TELEGRAM_CHAT_ID = os.getenv("ALERT_TELEGRAM_CHAT_ID", "")
