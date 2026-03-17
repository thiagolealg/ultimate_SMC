"""
SMC Trader Live - Bot de Trading em Producao
=============================================
Conecta ao MetaTrader 5, monitora candles M1 em tempo real,
e executa ordens automaticamente via SMCEngineV3.

Uso: python smc_trader_live.py
"""

import sys
import os
import time
import signal
import asyncio
import logging
from logging.handlers import RotatingFileHandler
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple

import MetaTrader5 as mt5

from smc_engine_v3 import SMCEngineV3
from alerts import AlertService


# ============================================================
# CONFIGURACAO
# ============================================================
@dataclass
class Config:
    # MT5
    symbol: str = ""                   # Auto-detectado
    magic_number: int = 240201
    lot_size: float = 1.0              # 1 mini contrato
    slippage_points: int = 20

    # SMC Engine
    swing_length: int = 5
    risk_reward_ratio: float = 2.0       # Otimizado (era 3.0)
    min_volume_ratio: float = 0.0
    min_ob_size_atr: float = 0.3         # Otimizado (era 0.0)
    use_not_mitigated_filter: bool = True
    max_pending_candles: int = 150
    entry_delay_candles: int = 1
    tick_size: float = 5.0               # WIN mini tick = 5 pts
    min_confidence: float = 0.0
    max_sl_points: float = 50.0          # Otimizado: SL max 50 pts
    min_patterns: int = 0
    entry_retracement: float = 0.7       # Otimizado (era 0.5 midline)

    # Risco (0 = sem limite, fiel ao backtest)
    max_open_positions: int = 0
    max_pending_orders: int = 0

    # Horario de negociacao (BRT) - usado apenas para logging, NAO filtra sinais
    trading_start_hour: int = 9
    trading_start_minute: int = 0
    trading_end_hour: int = 18
    trading_end_minute: int = 24

    # Bot
    poll_interval_seconds: float = 1.0
    warmup_candles: int = 10000

    # Alertas Telegram (deixe vazio para desativar)
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")

    # Logging
    log_file: str = "smc_trader.log"
    log_level: str = "INFO"


# ============================================================
# LOGGING
# ============================================================
def setup_logging(config: Config) -> logging.Logger:
    logger = logging.getLogger("smc_trader")
    logger.setLevel(getattr(logging, config.log_level, logging.INFO))

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    # Arquivo rotativo
    fh = RotatingFileHandler(config.log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    # Console
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))
    logger.addHandler(ch)

    return logger


# ============================================================
# ORDER MAPPER: engine order_id <-> MT5 ticket
# ============================================================
class OrderMapper:
    def __init__(self):
        self._engine_to_mt5: Dict[str, int] = {}
        self._mt5_to_engine: Dict[int, str] = {}

    def add(self, engine_id: str, mt5_ticket: int):
        self._engine_to_mt5[engine_id] = mt5_ticket
        self._mt5_to_engine[mt5_ticket] = engine_id

    def get_ticket(self, engine_id: str) -> Optional[int]:
        return self._engine_to_mt5.get(engine_id)

    def get_engine_id(self, mt5_ticket: int) -> Optional[str]:
        return self._mt5_to_engine.get(mt5_ticket)

    def remove_by_engine_id(self, engine_id: str):
        ticket = self._engine_to_mt5.pop(engine_id, None)
        if ticket is not None:
            self._mt5_to_engine.pop(ticket, None)

    def remove_by_ticket(self, mt5_ticket: int):
        eid = self._mt5_to_engine.pop(mt5_ticket, None)
        if eid is not None:
            self._engine_to_mt5.pop(eid, None)

    def all_mappings(self) -> Dict[str, int]:
        return dict(self._engine_to_mt5)


# ============================================================
# MT5 MANAGER
# ============================================================
class MT5Manager:
    # Contratos especificos primeiro (tradeaeis), depois continuos (so leitura)
    SYMBOLS_TO_TRY = ["WINH26", "WINJ26", "WINM26", "WING26", "WIN$N", "WIN$"]

    def __init__(self, logger: logging.Logger):
        self.log = logger
        self.symbol: str = ""          # Simbolo para dados (candles)
        self.trade_symbol: str = ""    # Simbolo para ordens (contrato real)

    # ------ conexao ------
    def initialize(self, preferred_symbol: str = "") -> bool:
        if not mt5.initialize():
            self.log.error(f"Falha ao inicializar MT5: {mt5.last_error()}")
            return False

        info = mt5.terminal_info()
        self.log.info(f"MT5 conectado: {info.name} (Build {info.build})")

        # Detectar simbolo para dados
        if preferred_symbol:
            sym_info = mt5.symbol_info(preferred_symbol)
            if sym_info is not None:
                self.symbol = preferred_symbol
                if not sym_info.visible:
                    mt5.symbol_select(preferred_symbol, True)
                self.log.info(f"Simbolo dados: {self.symbol}")

        if not self.symbol:
            for s in self.SYMBOLS_TO_TRY:
                sym_info = mt5.symbol_info(s)
                if sym_info is not None:
                    self.symbol = s
                    if not sym_info.visible:
                        mt5.symbol_select(s, True)
                    self.log.info(f"Simbolo dados detectado: {self.symbol}")
                    break

        if not self.symbol:
            all_symbols = mt5.symbols_get()
            win_symbols = [s.name for s in all_symbols if s.name.startswith("WIN")]
            if win_symbols:
                self.symbol = win_symbols[0]
                mt5.symbol_select(self.symbol, True)
                self.log.info(f"Simbolo dados encontrado: {self.symbol}")

        if not self.symbol:
            self.log.error("Nenhum simbolo WIN encontrado!")
            return False

        # Detectar simbolo tradeable (contrato real com trade_mode=4 e bid>0)
        self.trade_symbol = ""
        all_symbols = mt5.symbols_get()
        win_contracts = [s for s in all_symbols
                         if s.name.startswith("WIN")
                         and not s.name.startswith("WIN$")
                         and not s.name.startswith("WIN@")
                         and "_" not in s.name  # Ignora rolagens (WINV25_71R etc)
                         and s.trade_mode == 4]  # SYMBOL_TRADE_MODE_FULL
        for s in win_contracts:
            mt5.symbol_select(s.name, True)
            tick = mt5.symbol_info_tick(s.name)
            if tick and tick.bid > 0:
                self.trade_symbol = s.name
                break

        if not self.trade_symbol:
            self.trade_symbol = self.symbol  # fallback
            self.log.warning(f"Nenhum contrato tradeable encontrado, usando {self.symbol}")
        else:
            self.log.info(f"Simbolo trade: {self.trade_symbol}")

        return True

    def shutdown(self):
        mt5.shutdown()
        self.log.info("MT5 desconectado")

    # ------ candles ------
    def get_latest_candle(self) -> Optional[dict]:
        """Retorna o ultimo candle M1 FECHADO (indice 1)."""
        rates = mt5.copy_rates_from_pos(self.symbol, mt5.TIMEFRAME_M1, 1, 1)
        if rates is None or len(rates) == 0:
            return None
        r = rates[0]
        return {
            'time': int(r['time']),
            'open': float(r['open']),
            'high': float(r['high']),
            'low': float(r['low']),
            'close': float(r['close']),
            'volume': float(r['real_volume']) if r['real_volume'] > 0 else float(r['tick_volume']),
        }

    def get_historical_candles(self, count: int) -> list:
        """Retorna os ultimos `count` candles M1 fechados."""
        rates = mt5.copy_rates_from_pos(self.symbol, mt5.TIMEFRAME_M1, 1, count)
        if rates is None:
            return []
        result = []
        for r in rates:
            result.append({
                'time': int(r['time']),
                'open': float(r['open']),
                'high': float(r['high']),
                'low': float(r['low']),
                'close': float(r['close']),
                'volume': float(r['real_volume']) if r['real_volume'] > 0 else float(r['tick_volume']),
            })
        return result

    # ------ ordens ------
    def place_limit_order(self, direction: str, entry_price: float, sl: float, tp: float,
                          lot: float, magic: int, comment: str = "SMC") -> Tuple[bool, int, str]:
        """Coloca ordem pendente. Escolhe LIMIT ou STOP conforme preco atual."""
        sym_info = mt5.symbol_info(self.trade_symbol)
        if sym_info is None:
            return False, 0, f"Symbol info indisponivel para {self.trade_symbol}"

        tick = mt5.symbol_info_tick(self.trade_symbol)
        if tick is None or tick.bid == 0:
            return False, 0, f"Tick info indisponivel para {self.trade_symbol}"

        # Escolher tipo de ordem baseado no preco atual
        if direction == "BULLISH":
            if entry_price < tick.ask:
                order_type = mt5.ORDER_TYPE_BUY_LIMIT   # Entry abaixo do preco -> LIMIT
            else:
                order_type = mt5.ORDER_TYPE_BUY_STOP    # Entry acima do preco -> STOP
        else:
            if entry_price > tick.bid:
                order_type = mt5.ORDER_TYPE_SELL_LIMIT   # Entry acima do preco -> LIMIT
            else:
                order_type = mt5.ORDER_TYPE_SELL_STOP    # Entry abaixo do preco -> STOP

        # Verificar stops level minimo
        stops_level = sym_info.trade_stops_level
        if stops_level > 0:
            if direction == "BULLISH":
                min_sl_dist = stops_level
                if abs(entry_price - sl) < min_sl_dist:
                    sl = entry_price - min_sl_dist
                if abs(tp - entry_price) < min_sl_dist:
                    tp = entry_price + min_sl_dist
            else:
                min_sl_dist = stops_level
                if abs(sl - entry_price) < min_sl_dist:
                    sl = entry_price + min_sl_dist
                if abs(entry_price - tp) < min_sl_dist:
                    tp = entry_price - min_sl_dist

        request = {
            "action": mt5.TRADE_ACTION_PENDING,
            "symbol": self.trade_symbol,
            "volume": lot,
            "type": order_type,
            "price": entry_price,
            "sl": sl,
            "tp": tp,
            "deviation": 20,
            "magic": magic,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_DAY,
            "type_filling": mt5.ORDER_FILLING_RETURN,
        }

        type_name = {
            mt5.ORDER_TYPE_BUY_LIMIT: "BUY_LIMIT",
            mt5.ORDER_TYPE_BUY_STOP: "BUY_STOP",
            mt5.ORDER_TYPE_SELL_LIMIT: "SELL_LIMIT",
            mt5.ORDER_TYPE_SELL_STOP: "SELL_STOP",
        }.get(order_type, str(order_type))
        self.log.debug(f"  MT5 request: {type_name} @ {entry_price:,.0f} SL={sl:,.0f} TP={tp:,.0f} "
                       f"(ask={tick.ask:,.0f} bid={tick.bid:,.0f})")

        result = mt5.order_send(request)
        if result is None:
            return False, 0, f"order_send retornou None: {mt5.last_error()}"

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return False, 0, f"Retcode {result.retcode}: {result.comment}"

        return True, result.order, ""

    def cancel_order(self, ticket: int, max_retries: int = 3) -> Tuple[bool, str]:
        """
        Cancela ordem pendente pelo ticket com retries.
        Retorna (sucesso, status):
          - (True, 'cancelled') - ordem cancelada com sucesso
          - (True, 'not_found') - ordem nao existe (ja cancelada/preenchida)
          - (True, 'filled') - ordem ja foi preenchida (virou posicao)
          - (False, 'failed') - falha ao cancelar, ordem ainda pendente
        """
        for attempt in range(1, max_retries + 1):
            # Verificar se a ordem ainda existe antes de tentar cancelar
            orders = mt5.orders_get(ticket=ticket)
            if orders is None or len(orders) == 0:
                # Ordem nao existe - verificar se virou posicao
                positions = mt5.positions_get(ticket=ticket)
                if positions is not None and len(positions) > 0:
                    self.log.warning(f"cancel_order({ticket}): ordem ja preenchida! "
                                     f"Posicao aberta @ {positions[0].price_open:,.0f}")
                    return True, 'filled'
                self.log.info(f"cancel_order({ticket}): ordem nao encontrada no MT5 (tentativa {attempt})")
                return True, 'not_found'

            request = {
                "action": mt5.TRADE_ACTION_REMOVE,
                "order": ticket,
            }
            result = mt5.order_send(request)
            if result is not None and result.retcode == mt5.TRADE_RETCODE_DONE:
                self.log.info(f"cancel_order({ticket}): cancelada com sucesso (tentativa {attempt})")
                return True, 'cancelled'

            code = result.retcode if result else "None"
            comment = result.comment if result else "None"
            self.log.warning(f"cancel_order({ticket}): tentativa {attempt}/{max_retries} falhou: "
                             f"retcode={code} {comment}")

            if attempt < max_retries:
                time.sleep(1)

        # Verificacao final: a ordem ainda existe?
        orders = mt5.orders_get(ticket=ticket)
        if orders is None or len(orders) == 0:
            # Verificar se virou posicao
            positions = mt5.positions_get(ticket=ticket)
            if positions is not None and len(positions) > 0:
                self.log.warning(f"cancel_order({ticket}): ordem preenchida durante retries!")
                return True, 'filled'
            self.log.info(f"cancel_order({ticket}): ordem desapareceu apos retries")
            return True, 'not_found'

        self.log.error(f"cancel_order({ticket}): FALHA apos {max_retries} tentativas! Ordem ainda ativa!")
        return False, 'failed'

    def get_pending_orders(self, magic: int) -> list:
        """Lista ordens pendentes do bot (filtradas por magic)."""
        orders = mt5.orders_get(symbol=self.trade_symbol)
        if orders is None:
            return []
        return [o for o in orders if o.magic == magic]

    def get_positions(self, magic: int) -> list:
        """Lista posicoes abertas do bot (filtradas por magic)."""
        positions = mt5.positions_get(symbol=self.trade_symbol)
        if positions is None:
            return []
        return [p for p in positions if p.magic == magic]

    def find_position_by_comment(self, comment: str, magic: int):
        """Busca posicao aberta pelo comment (order_id). Retorna position ou None."""
        positions = mt5.positions_get(symbol=self.trade_symbol)
        if positions is None:
            return None
        for p in positions:
            if p.magic == magic and p.comment == comment:
                return p
        return None

    def close_position(self, position_ticket: int) -> Tuple[bool, str]:
        """Fecha posicao aberta pelo ticket a mercado."""
        positions = mt5.positions_get(ticket=position_ticket)
        if positions is None or len(positions) == 0:
            return True, "posicao ja fechada"

        pos = positions[0]
        # Tipo inverso para fechar
        close_type = mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.trade_symbol,
            "volume": pos.volume,
            "type": close_type,
            "position": position_ticket,
            "deviation": 20,
            "magic": pos.magic,
            "comment": f"CLOSE_{pos.comment}",
            "type_filling": mt5.ORDER_FILLING_RETURN,
        }

        result = mt5.order_send(request)
        if result is None:
            return False, f"order_send retornou None: {mt5.last_error()}"
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return False, f"Retcode {result.retcode}: {result.comment}"
        return True, "OK"


# ============================================================
# TRADING BOT
# ============================================================
class TradingBot:
    def __init__(self, config: Config, logger: logging.Logger):
        self.cfg = config
        self.log = logger
        self.mt5 = MT5Manager(logger)
        self.mapper = OrderMapper()
        self.engine: Optional[SMCEngineV3] = None
        self.alert_service = AlertService(
            telegram_bot_token=config.telegram_bot_token,
            telegram_chat_id=config.telegram_chat_id,
        )
        self.running = False
        self.last_candle_time: int = 0

        # Contadores
        self.signals_count = 0
        self.orders_placed = 0
        self.orders_cancelled = 0
        self.trades_closed = 0
        self.total_pnl_pts = 0.0

    # ------ startup ------
    def start(self) -> bool:
        # Conectar MT5
        if not self.mt5.initialize(self.cfg.symbol):
            return False

        # Atualizar simbolo na config
        self.cfg.symbol = self.mt5.symbol

        # Criar engine
        self.engine = SMCEngineV3(
            symbol=self.cfg.symbol,
            swing_length=self.cfg.swing_length,
            risk_reward_ratio=self.cfg.risk_reward_ratio,
            min_volume_ratio=self.cfg.min_volume_ratio,
            min_ob_size_atr=self.cfg.min_ob_size_atr,
            use_not_mitigated_filter=self.cfg.use_not_mitigated_filter,
            max_pending_candles=self.cfg.max_pending_candles,
            entry_delay_candles=self.cfg.entry_delay_candles,
            tick_size=self.cfg.tick_size,
            min_confidence=self.cfg.min_confidence,
            max_sl_points=self.cfg.max_sl_points,
            min_patterns=self.cfg.min_patterns,
            entry_retracement=self.cfg.entry_retracement,
        )

        # Warm-up
        self._warm_up()

        # Limpar ordens orfas e sincronizar pendentes da engine
        self._clean_orphan_orders()
        self._sync_pending_orders()

        return True

    def _warm_up(self):
        """Carrega candles historicos para inicializar o engine."""
        self.log.info(f"Warm-up: carregando {self.cfg.warmup_candles} candles historicos...")
        candles = self.mt5.get_historical_candles(self.cfg.warmup_candles)

        if not candles:
            self.log.warning("Nenhum candle historico encontrado para warm-up!")
            return

        for c in candles:
            self.engine.add_candle({
                'open': c['open'],
                'high': c['high'],
                'low': c['low'],
                'close': c['close'],
                'volume': c['volume'],
            })

        self.last_candle_time = candles[-1]['time']
        self.log.info(f"Warm-up completo: {len(candles)} candles | "
                      f"Engine: {self.engine.candle_count} candles processados")

        # Stats apos warm-up
        stats = self.engine.get_stats()
        self.log.info(f"  Pending: {stats['pending_orders']} | "
                      f"Filled: {stats['open_trades']} | "
                      f"OBs: {stats['order_blocks_detected']}")

    def _clean_orphan_orders(self):
        """Cancela ordens pendentes anteriores deste bot."""
        orders = self.mt5.get_pending_orders(self.cfg.magic_number)
        if orders:
            self.log.info(f"Encontradas {len(orders)} ordens orfas do bot - cancelando...")
            for o in orders:
                success, status = self.mt5.cancel_order(o.ticket)
                if success:
                    self.log.info(f"  Cancelada ordem orfa #{o.ticket} ({status})")
                else:
                    self.log.warning(f"  Falha ao cancelar ordem orfa #{o.ticket}")

        positions = self.mt5.get_positions(self.cfg.magic_number)
        if positions:
            self.log.warning(f"ATENCAO: {len(positions)} posicoes abertas do bot encontradas!")
            for p in positions:
                self.log.warning(f"  Posicao #{p.ticket}: {'BUY' if p.type == 0 else 'SELL'} "
                                 f"{p.volume} lotes @ {p.price_open:.0f} | P/L: {p.profit:+.2f}")

    def _sync_pending_orders(self):
        """Coloca no MT5 as ordens pendentes que a engine tem apos warm-up."""
        pending = self.engine.get_pending_orders()
        if not pending:
            return

        self.log.info(f"Sincronizando {len(pending)} ordens pendentes da engine...")
        for sig in pending:
            direction = sig['direction']
            entry = sig['entry_price']
            sl = sig['stop_loss']
            tp = sig['take_profit']
            order_id = sig['order_id']
            confidence = sig['confidence']
            patterns = sig['patterns']

            ok, ticket, err = self.mt5.place_limit_order(
                direction=direction,
                entry_price=entry,
                sl=sl,
                tp=tp,
                lot=self.cfg.lot_size,
                magic=self.cfg.magic_number,
                comment=order_id,
            )

            if ok:
                self.mapper.add(order_id, ticket)
                self.log.info(f"  Ordem {order_id}: {direction} @ {entry:,.0f} | "
                              f"SL={sl:,.0f} TP={tp:,.0f} | Conf={confidence:.0f}% | "
                              f"Ticket={ticket}")
            else:
                self.log.error(f"  Falha {order_id}: {err}")

    # ------ trading hours ------
    def is_trading_hours(self) -> bool:
        now = datetime.now()
        start = now.replace(hour=self.cfg.trading_start_hour, minute=self.cfg.trading_start_minute,
                            second=0, microsecond=0)
        end = now.replace(hour=self.cfg.trading_end_hour, minute=self.cfg.trading_end_minute,
                          second=0, microsecond=0)
        return start <= now <= end

    # ------ risk checks ------
    def can_place_order(self) -> Tuple[bool, str]:
        # Se limites = 0, sem restricao (fiel ao backtest)
        if self.cfg.max_open_positions > 0:
            positions = self.mt5.get_positions(self.cfg.magic_number)
            if len(positions) >= self.cfg.max_open_positions:
                return False, f"Max posicoes ({self.cfg.max_open_positions}) atingido"

        if self.cfg.max_pending_orders > 0:
            pending = self.mt5.get_pending_orders(self.cfg.magic_number)
            if len(pending) >= self.cfg.max_pending_orders:
                return False, f"Max pendentes ({self.cfg.max_pending_orders}) atingido"

        return True, ""

    # ------ event processors ------
    def _process_new_signals(self, signals: list):
        for sig in signals:
            self.signals_count += 1
            direction = sig['direction']
            entry = sig['entry_price']
            sl = sig['stop_loss']
            tp = sig['take_profit']
            conf = sig['confidence']
            patterns = sig.get('patterns', [])
            oid = sig['order_id']

            self.log.info(f"SINAL #{oid}: {direction} | Entry={entry:,.0f} | "
                          f"SL={sl:,.0f} | TP={tp:,.0f} | Conf={conf:.0f}% | {patterns}")

            # Verificar risco (se limites configurados)
            can, reason = self.can_place_order()
            if not can:
                self.log.info(f"  -> {reason}, ignorando sinal {oid}")
                continue

            # Colocar ordem no MT5
            success, ticket, error = self.mt5.place_limit_order(
                direction=direction,
                entry_price=entry,
                sl=sl,
                tp=tp,
                lot=self.cfg.lot_size,
                magic=self.cfg.magic_number,
                comment=oid,
            )

            if success:
                self.mapper.add(oid, ticket)
                self.orders_placed += 1
                self.log.info(f"  -> ORDEM COLOCADA: {direction} Limit #{ticket} @ {entry:,.0f}")

                # Alerta Telegram
                self._send_alert('signal', {
                    'symbol': self.cfg.symbol,
                    'direction': direction,
                    'entry_price': entry,
                    'stop_loss': sl,
                    'take_profit': tp,
                    'risk_reward_ratio': self.cfg.risk_reward_ratio,
                    'confidence': conf,
                    'patterns': [str(p) for p in patterns] if patterns else [],
                })
            else:
                self.log.error(f"  -> FALHA ao colocar ordem: {error}")

    def _process_filled_orders(self, filled: list):
        for f in filled:
            oid = f['order_id']
            ticket = self.mapper.get_ticket(oid)
            self.log.info(f"FILL: {oid} (ticket={ticket}) | {f['direction']} @ {f['entry_price']:,.0f}")

            self._send_alert('filled', {
                'symbol': self.cfg.symbol,
                'direction': f['direction'],
                'entry_price': f['entry_price'],
                'stop_loss': 0,
                'take_profit': 0,
            })

    def _process_closed_trades(self, closed: list):
        for t in closed:
            oid = t['order_id']
            status = t['status']
            pnl = t['profit_loss']
            pnl_r = t['profit_loss_r']
            self.trades_closed += 1
            self.total_pnl_pts += pnl

            result_str = "WIN" if status == "closed_tp" else "LOSS"
            self.log.info(f"TRADE FECHADO: {oid} | {result_str} | {pnl:+,.0f} pts ({pnl_r:+.1f}R)")

            # Verificar se posicao MT5 ainda existe (pode ter timing diferente)
            ticket = self.mapper.get_ticket(oid)
            if ticket:
                pos = self.mt5.find_position_by_comment(oid, self.cfg.magic_number)
                if pos is not None:
                    self.log.warning(f"  Engine fechou {oid} mas posicao MT5 ainda aberta! "
                                     f"MT5 deve fechar via TP/SL. Ticket={ticket}")

            # Limpar mapeamento
            self.mapper.remove_by_engine_id(oid)

            # Alerta
            self._send_alert('closed', {
                'symbol': self.cfg.symbol,
                'profit_loss': pnl,
                'direction': t['direction'],
                'status': status,
            })

    def _process_expired_orders(self, expired: list):
        for e in expired:
            oid = e['order_id']
            ticket = self.mapper.get_ticket(oid)
            if ticket:
                success, status = self.mt5.cancel_order(ticket)
                if success and status == 'cancelled':
                    self.orders_cancelled += 1
                    self.log.info(f"EXPIRADA: {oid} (ticket={ticket}) -> cancelada OK")
                elif success and status == 'filled':
                    # Ordem expirou na engine, mas MT5 ja preencheu!
                    # Fechar posicao a mercado (engine nao quer esse trade)
                    self.log.warning(f"EXPIRADA: {oid} (ticket={ticket}) -> MT5 ja preencheu! Fechando posicao...")
                    self._force_close_position(ticket, oid)
                elif success:
                    self.orders_cancelled += 1
                    self.log.info(f"EXPIRADA: {oid} (ticket={ticket}) -> {status}")
                else:
                    self.log.error(f"EXPIRADA: {oid} (ticket={ticket}) -> FALHA ao cancelar!")
                self.mapper.remove_by_engine_id(oid)
            else:
                self.log.debug(f"Ordem expirada {oid} sem ticket MT5 mapeado")

    def _process_cancelled_orders(self, cancelled: list):
        for c in cancelled:
            oid = c['order_id']
            reason = c.get('reason', '?')
            ticket = self.mapper.get_ticket(oid)
            if ticket:
                success, status = self.mt5.cancel_order(ticket)
                if success and status == 'cancelled':
                    self.orders_cancelled += 1
                    self.log.info(f"CANCELADA: {oid} (ticket={ticket}) motivo={reason} -> cancelada OK")
                elif success and status == 'filled':
                    # Engine cancelou (OB mitigado), mas MT5 ja preencheu!
                    # Fechar posicao a mercado (engine nao quer esse trade)
                    self.log.warning(f"CANCELADA: {oid} (ticket={ticket}) motivo={reason} "
                                     f"-> MT5 ja preencheu! Fechando posicao...")
                    self._force_close_position(ticket, oid)
                elif success:
                    self.orders_cancelled += 1
                    self.log.info(f"CANCELADA: {oid} (ticket={ticket}) motivo={reason} -> {status}")
                else:
                    self.log.error(f"CANCELADA: {oid} (ticket={ticket}) motivo={reason} -> FALHA ao cancelar!")
                self.mapper.remove_by_engine_id(oid)
            else:
                self.log.debug(f"Ordem cancelada {oid} sem ticket MT5 (motivo: {reason})")

    def _force_close_position(self, ticket: int, oid: str):
        """Fecha posicao que o MT5 preencheu mas a engine nao quer."""
        ok, msg = self.mt5.close_position(ticket)
        if ok:
            self.log.warning(f"  Posicao #{ticket} ({oid}) fechada a mercado: {msg}")
            self._send_alert('closed', {
                'symbol': self.cfg.symbol,
                'profit_loss': 0,
                'direction': 'UNKNOWN',
                'status': 'force_closed',
            })
        else:
            self.log.error(f"  FALHA ao fechar posicao #{ticket} ({oid}): {msg}")

    # ------ cross-check MT5 ------
    def _sync_mt5_state(self):
        """Verifica consistencia entre mapper e MT5. Cancela orfas."""
        mappings = self.mapper.all_mappings()
        mapped_tickets = set(mappings.values())

        mt5_pending = self.mt5.get_pending_orders(self.cfg.magic_number)
        mt5_pending_tickets = {o.ticket for o in mt5_pending}
        mt5_position_tickets = {p.ticket for p in self.mt5.get_positions(self.cfg.magic_number)}
        mt5_all = mt5_pending_tickets | mt5_position_tickets

        # 1. Limpar mapper: tickets que sumiram do MT5
        for eid, ticket in list(mappings.items()):
            if ticket not in mt5_all:
                self.log.info(f"Sync: {eid} (ticket={ticket}) nao encontrado no MT5 - removendo mapeamento")
                self.mapper.remove_by_engine_id(eid)

        # 2. Detectar orfas: ordens pendentes no MT5 que NAO estao no mapper
        for o in mt5_pending:
            if o.ticket not in mapped_tickets:
                self.log.warning(f"Sync: ordem orfa detectada #{o.ticket} @ {o.price_open:,.0f} "
                                 f"comment={o.comment} - cancelando...")
                success, status = self.mt5.cancel_order(o.ticket)
                if success and status != 'filled':
                    self.log.info(f"  Ordem orfa #{o.ticket} cancelada ({status})")
                elif success and status == 'filled':
                    # Ordem orfa foi preenchida - fechar posicao
                    self.log.warning(f"  Ordem orfa #{o.ticket} ja preenchida! Fechando posicao...")
                    ok, msg = self.mt5.close_position(o.ticket)
                    if ok:
                        self.log.warning(f"  Posicao orfa #{o.ticket} fechada: {msg}")
                    else:
                        self.log.error(f"  FALHA ao fechar posicao orfa #{o.ticket}: {msg}")
                else:
                    self.log.error(f"  FALHA ao cancelar ordem orfa #{o.ticket}")

        # 3. Detectar posicoes orfas: posicoes abertas que NAO estao no mapper
        # (pode acontecer se MT5 preencheu uma ordem que a engine ja cancelou/expirou)
        mt5_positions = self.mt5.get_positions(self.cfg.magic_number)
        for p in mt5_positions:
            if p.ticket not in mapped_tickets:
                # Verificar se o comment parece ser do nosso bot (SMC_xxx)
                if p.comment and p.comment.startswith("SMC_"):
                    self.log.warning(f"Sync: posicao orfa detectada #{p.ticket} "
                                     f"{'BUY' if p.type == 0 else 'SELL'} @ {p.price_open:,.0f} "
                                     f"P/L={p.profit:+.2f} comment={p.comment}")
                    # NAO fechar automaticamente - posicao tem TP/SL proprio
                    # Apenas logar para monitoramento. Se quiser fechar, descomente:
                    # ok, msg = self.mt5.close_position(p.ticket)
                    # self.log.warning(f"  Posicao orfa #{p.ticket} fechada: {msg}")

    # ------ alerts ------
    def _send_alert(self, alert_type: str, data: dict):
        if not self.cfg.telegram_bot_token:
            return
        try:
            loop = asyncio.new_event_loop()
            if alert_type == 'signal':
                loop.run_until_complete(self.alert_service.send_signal_alert(data))
            elif alert_type == 'filled':
                loop.run_until_complete(self.alert_service.send_order_filled_alert(data))
            elif alert_type == 'closed':
                loop.run_until_complete(self.alert_service.send_order_closed_alert(data))
            loop.close()
        except Exception as e:
            self.log.error(f"Erro ao enviar alerta: {e}")

    # ------ main loop ------
    def run(self):
        self.running = True
        self.log.info("Loop principal iniciado - aguardando candles...")

        candle_check_count = 0
        last_stats_time = time.time()

        while self.running:
            try:
                # Buscar ultimo candle fechado
                candle = self.mt5.get_latest_candle()
                if candle is None:
                    time.sleep(self.cfg.poll_interval_seconds)
                    continue

                # Verificar se eh novo
                if candle['time'] == self.last_candle_time:
                    time.sleep(self.cfg.poll_interval_seconds)
                    continue

                self.last_candle_time = candle['time']
                candle_check_count += 1
                candle_time_str = datetime.utcfromtimestamp(candle['time']).strftime('%H:%M')

                self.log.info(f"--- Candle M1 {candle_time_str} | "
                              f"O={candle['open']:,.0f} H={candle['high']:,.0f} "
                              f"L={candle['low']:,.0f} C={candle['close']:,.0f} ---")

                # Alimentar engine
                events = self.engine.add_candle({
                    'open': candle['open'],
                    'high': candle['high'],
                    'low': candle['low'],
                    'close': candle['close'],
                    'volume': candle['volume'],
                })

                # Processar eventos
                if events['new_signals']:
                    self._process_new_signals(events['new_signals'])

                if events['filled_orders']:
                    self._process_filled_orders(events['filled_orders'])

                if events['closed_trades']:
                    self._process_closed_trades(events['closed_trades'])

                if events['expired_orders']:
                    self._process_expired_orders(events['expired_orders'])

                if events['cancelled_orders']:
                    self._process_cancelled_orders(events['cancelled_orders'])

                # Cross-check MT5 a cada candle para detectar orfas rapidamente
                self._sync_mt5_state()

                # Stats a cada 5 minutos
                now = time.time()
                if now - last_stats_time >= 300:
                    last_stats_time = now
                    stats = self.engine.get_stats()
                    self.log.info(
                        f"[STATS] Engine: {stats['total_trades']} trades | "
                        f"WR={stats['win_rate']:.1f}% | PF={stats['profit_factor']:.2f} | "
                        f"Pending={stats['pending_orders']} | Open={stats['open_trades']}"
                    )
                    self.log.info(
                        f"[STATS] Bot: sinais={self.signals_count} | "
                        f"ordens={self.orders_placed} | canceladas={self.orders_cancelled} | "
                        f"trades={self.trades_closed} | P/L={self.total_pnl_pts:+,.0f} pts"
                    )

                time.sleep(self.cfg.poll_interval_seconds)

            except KeyboardInterrupt:
                self.log.info("Ctrl+C detectado")
                self.running = False
            except Exception as e:
                self.log.error(f"Erro no loop: {e}", exc_info=True)
                time.sleep(5)

    def stop(self):
        self.running = False

    def shutdown(self):
        self.running = False
        self.log.info("Encerrando bot...")

        # Resumo final
        self.log.info("=" * 60)
        self.log.info("RESUMO DA SESSAO")
        self.log.info("=" * 60)
        self.log.info(f"  Sinais recebidos: {self.signals_count}")
        self.log.info(f"  Ordens colocadas: {self.orders_placed}")
        self.log.info(f"  Ordens canceladas: {self.orders_cancelled}")
        self.log.info(f"  Trades fechados: {self.trades_closed}")
        self.log.info(f"  P/L total: {self.total_pnl_pts:+,.0f} pts")

        # Listar ordens/posicoes restantes
        pending = self.mt5.get_pending_orders(self.cfg.magic_number)
        positions = self.mt5.get_positions(self.cfg.magic_number)
        if pending:
            self.log.info(f"  Ordens pendentes ativas: {len(pending)}")
            for o in pending:
                self.log.info(f"    #{o.ticket}: {o.type} @ {o.price_open:.0f}")
        if positions:
            self.log.info(f"  Posicoes abertas: {len(positions)}")
            for p in positions:
                self.log.info(f"    #{p.ticket}: {'BUY' if p.type == 0 else 'SELL'} "
                              f"{p.volume} @ {p.price_open:.0f} P/L={p.profit:+.2f}")

        if pending or positions:
            self.log.info("  NOTA: Ordens/posicoes NAO foram canceladas automaticamente.")

        self.log.info("=" * 60)
        self.mt5.shutdown()


# ============================================================
# MAIN
# ============================================================
bot: Optional[TradingBot] = None


def signal_handler(signum, frame):
    global bot
    if bot:
        bot.stop()


def main():
    global bot

    config = Config()
    logger = setup_logging(config)

    # Signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info("=" * 60)
    logger.info("SMC TRADER LIVE - Iniciando")
    logger.info("=" * 60)
    logger.info(f"Risk/Reward: {config.risk_reward_ratio}:1")
    logger.info(f"Entry Retracement: {config.entry_retracement}")
    logger.info(f"Min OB Size ATR: {config.min_ob_size_atr}")
    logger.info(f"Max SL Points: {config.max_sl_points}")
    logger.info(f"Min Confidence: {config.min_confidence}")
    logger.info(f"Min Patterns: {config.min_patterns}")
    logger.info(f"Lote: {config.lot_size}")
    logger.info(f"Max posicoes: {'SEM LIMITE (fiel ao backtest)' if config.max_open_positions == 0 else config.max_open_positions}")
    logger.info(f"Max pendentes: {'SEM LIMITE (fiel ao backtest)' if config.max_pending_orders == 0 else config.max_pending_orders}")
    logger.info(f"Mercado: {config.trading_start_hour:02d}:{config.trading_start_minute:02d} - "
                f"{config.trading_end_hour:02d}:{config.trading_end_minute:02d}")
    logger.info(f"Telegram: {'SIM' if config.telegram_bot_token else 'NAO'}")
    logger.info("=" * 60)

    bot = TradingBot(config, logger)

    if not bot.start():
        logger.error("Falha ao iniciar bot!")
        sys.exit(1)

    try:
        bot.run()
    except Exception as e:
        logger.critical(f"Erro fatal: {e}", exc_info=True)
    finally:
        bot.shutdown()


if __name__ == "__main__":
    main()
