import logging
import time
import shutil
from pathlib import Path
from typing import List, Dict, Optional
from decimal import Decimal
from datetime import datetime, timedelta
import threading
import pandas as pd
from sqlalchemy.orm import Session
from binance.exceptions import BinanceAPIException

from core.exchange import BinanceExchange
from core.risk import RiskManager
from core.strategy import StrategyFactory, MultiTimeframeAnalyzer
from core.utils import notify, safe_decimal
from db.models import (
    DatabaseManager, Trade, Order, Balance, Performance
)

class BackupManager:
    """Gerencia backup automático de database"""
    
    def __init__(self, settings):
        """
        Initialize backup manager
        
        Args:
            settings: Settings object
        """
        self.logger = logging.getLogger('TradingBot.BackupManager')
        self.db_path = Path(settings.DATABASE_URL.replace('sqlite:///', ''))
        self.backup_dir = Path('db/backups')
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger.info(f"Backup manager initialized. Backup dir: {self.backup_dir}")
    
    def backup(self) -> bool:
        """
        Fazer backup do database
        
        Returns:
            True se sucesso, False se falhou
        """
        try:
            if not self.db_path.exists():
                self.logger.warning(f"Database file not found: {self.db_path}")
                return False
            
            # Nome do backup: db_backup_2025-10-29_14-30-45.db
            timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
            backup_name = f"db_backup_{timestamp}.db"
            backup_path = self.backup_dir / backup_name
            
            # Copiar arquivo
            shutil.copy2(self.db_path, backup_path)
            
            self.logger.info(f"✅ Backup criado: {backup_path}")
            
            # Limpar backups antigos (manter apenas últimos 7)
            self._cleanup_old_backups()
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Backup falhou: {e}", exc_info=True)
            return False
    
    def _cleanup_old_backups(self, keep_count: int = 7) -> None:
        """
        Deletar backups antigos (manter apenas últimos N)
        
        Args:
            keep_count: Número de backups para manter
        """
        try:
            backups = sorted(self.backup_dir.glob('db_backup_*.db'))
            
            if len(backups) > keep_count:
                to_delete = backups[:-keep_count]
                
                for backup in to_delete:
                    backup.unlink()
                    self.logger.info(f"Deletado backup antigo: {backup.name}")
                    
        except Exception as e:
            self.logger.error(f"Erro ao limpar backups antigos: {e}")


class TestnetTrade:
    """Representa uma posição aberta no testnet com suporte a partial TP (igual backtest)"""
    
    def __init__(
        self,
        symbol: str,
        side: str,
        entry_price: Decimal,
        quantity: Decimal,
        entry_time: datetime,
        stop_loss: Decimal,
        take_profit: Decimal
    ):
        self.symbol = symbol
        self.side = side
        self.entry_price = entry_price
        self.initial_quantity = quantity  # Quantidade inicial
        self.quantity = quantity  # Quantidade atual
        self.entry_time = entry_time
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        
        
        # Take Profit Parcial (3 níveis) - IGUAL AO BACKTEST
        distance = abs(take_profit - entry_price)
        if side == 'BUY':
            self.tp1 = entry_price + (distance * Decimal('0.5'))   # 50% do caminho
            self.tp2 = entry_price + (distance * Decimal('0.75'))  # 75% do caminho
            self.tp3 = take_profit  # 100%
        else:  # SELL
            self.tp1 = entry_price - (distance * Decimal('0.5'))
            self.tp2 = entry_price - (distance * Decimal('0.75'))
            self.tp3 = take_profit
        
        self.tp1_hit = False
        self.tp2_hit = False
        self.tp3_hit = False
        
        self.exit_price: Optional[Decimal] = None
        self.exit_time: Optional[datetime] = None
        self.pnl: Decimal = Decimal('0')
        self.pnl_percent: float = 0.0
        self.fees: Decimal = Decimal('0')
        self.status: str = 'OPEN'
        self.exit_reason: str = ''
        self.partial_exits: List[Dict] = []
    
    def check_partial_tp(
        self,
        current_price: Decimal,
        current_time: datetime,
        fee_rate: Decimal
    ) -> Optional[str]:
        """
        Verifica e executa take profits parciais
        Retorna: 'TP1', 'TP2', 'TP3', ou None
        EXATAMENTE IGUAL AO BACKTEST
        """
        if self.quantity <= 0:
            return None
        
        hit_tp = None
        quantity_to_close = Decimal('0')
        
        # Check TP1 (30% position)
        if not self.tp1_hit:
            if (self.side == 'BUY' and current_price >= self.tp1) or \
               (self.side == 'SELL' and current_price <= self.tp1):
                self.tp1_hit = True
                quantity_to_close = self.initial_quantity * Decimal('0.3')
                hit_tp = 'TP1'
        
        # Check TP2 (40% position)
        elif not self.tp2_hit:
            if (self.side == 'BUY' and current_price >= self.tp2) or \
               (self.side == 'SELL' and current_price <= self.tp2):
                self.tp2_hit = True
                quantity_to_close = self.initial_quantity * Decimal('0.4')
                hit_tp = 'TP2'
        
        # Check TP3 (30% remaining)
        elif not self.tp3_hit:
            if (self.side == 'BUY' and current_price >= self.tp3) or \
               (self.side == 'SELL' and current_price <= self.tp3):
                self.tp3_hit = True
                quantity_to_close = self.quantity  # Resto
                hit_tp = 'TP3'
        
        if hit_tp and quantity_to_close > 0:
            # Calculate partial PnL
            if self.side == 'BUY':
                partial_pnl = (current_price - self.entry_price) * quantity_to_close
            else:
                partial_pnl = (self.entry_price - current_price) * quantity_to_close
            
            # Calculate partial fees
            entry_value = self.entry_price * quantity_to_close
            exit_value = current_price * quantity_to_close
            partial_fees = (entry_value + exit_value) * fee_rate
            
            # Net partial PnL
            partial_pnl -= partial_fees
            
            # Update totals
            self.pnl += partial_pnl
            self.fees += partial_fees
            self.quantity -= quantity_to_close
            
            # Record partial exit
            self.partial_exits.append({
                'time': current_time,
                'price': current_price,
                'quantity': quantity_to_close,
                'pnl': partial_pnl,
                'level': hit_tp
            })
            
            # If all closed, mark as complete
            if self.quantity <= Decimal('0.0001'):
                self.status = 'CLOSED'
                self.exit_price = current_price
                self.exit_time = current_time
                self.exit_reason = 'TAKE_PROFIT_FULL'
                
                # Calculate final PnL percentage
                total_entry_value = self.entry_price * self.initial_quantity
                self.pnl_percent = float((self.pnl / total_entry_value) * 100)
            
            return hit_tp
        
        return None
    
    def close(
        self,
        exit_price: Decimal,
        exit_time: datetime,
        reason: str,
        fee_rate: Decimal
    ) -> None:
        """Fecha posição restante (stop loss ou saída manual)"""
        if self.quantity <= 0:
            return
        
        self.exit_price = exit_price
        self.exit_time = exit_time
        self.exit_reason = reason
        self.status = 'CLOSED'
        
        # Calculate PnL for remaining quantity
        if self.side == 'BUY':
            remaining_pnl = (exit_price - self.entry_price) * self.quantity
        else:
            remaining_pnl = (self.entry_price - exit_price) * self.quantity
        
        # Calculate fees for remaining
        entry_value = self.entry_price * self.quantity
        exit_value = exit_price * self.quantity
        remaining_fees = (entry_value + exit_value) * fee_rate
        
        # Add to totals
        self.pnl += remaining_pnl - remaining_fees
        self.fees += remaining_fees
        
        # Calculate final PnL percentage
        total_entry_value = self.entry_price * self.initial_quantity
        self.pnl_percent = float((self.pnl / total_entry_value) * 100)
        
        self.quantity = Decimal('0')


class TradeManager:
    """Manages trading operations and positions"""
    
    def __init__(self, settings, mode: str = 'live'):
        """Initialize trade manager COM BACKUP MANAGER"""
        
        self.settings = settings
        self.mode = mode
        self.logger = logging.getLogger(f'TradingBot.TradeManager.{mode}')
        
        # Validate configuration
        if mode == 'testnet':
            settings.validate_for_testnet()
            settings.sync_with_testnet()
        else:
            settings.validate_for_live_trading()
        
        # Initialize components
        self.logger.info("Initializing Trade Manager...")
        
        # Database
        self.db_manager = DatabaseManager(settings.DATABASE_URL)
        
        # Backup manager
        self.backup_manager = BackupManager(settings)
        
        # Exchange
        testnet = (mode == 'testnet')
        api_key, api_secret = settings.get_api_credentials(testnet)
        self.exchange = BinanceExchange(api_key, api_secret, testnet)
        
        # Risk manager
        self.risk_manager = RiskManager(settings)
        
        # Strategy
        self.strategy = StrategyFactory.create_strategy(settings.STRATEGY_MODE)
        
        # Multi-timeframe analyzer
        self.mtf_analyzer = MultiTimeframeAnalyzer(
            primary_timeframe=settings.PRIMARY_TIMEFRAME,
            entry_timeframe=settings.ENTRY_TIMEFRAME,
            strategy=self.strategy,
            require_alignment=settings.REQUIRE_MTF_ALIGNMENT
        )
        
        # State
        self.running = False
        self.open_trades: Dict[str, TestnetTrade] = {}
        self.last_signal_time: Dict[str, datetime] = {}
        self.last_backup_time = datetime.utcnow()
        self.last_recon_time = datetime.utcnow()
        
        # ✅ SINCRONIZAÇÃO: Rastreamento de capital esperado
        self.expected_equity: Optional[Decimal] = None
        self.last_known_equity: Optional[Decimal] = None
        
        # Reconcile with exchange on startup
        self._reconcile_state()
        
        # Fazer backup inicial
        self.backup_manager.backup()
        
        self.logger.info(f"✅ Trade Manager initialized in {mode} mode")
    
    def _reconcile_state(self) -> None:
        """Reconcile local database state with exchange"""
        self.logger.info("Reconciling state with exchange...")
        
        try:
            session = self.db_manager.get_session()
            
            # Get open trades from database
            db_open_trades = session.query(Trade).filter(
                Trade.status == 'OPEN',
                Trade.mode == self.mode
            ).all()
            
            # Get open orders from exchange
            exchange_orders = self.exchange.get_open_orders()
            exchange_order_ids = {
                str(order['orderId']) for order in exchange_orders
            }
            
            # Check each database trade
            for trade in db_open_trades:
                symbol = trade.symbol
                
                # Check if orders still exist
                trade_orders = session.query(Order).filter(
                    Order.trade_id == trade.id,
                    Order.status.in_(['NEW', 'PARTIALLY_FILLED'])
                ).all()
                
                has_open_orders = any(
                    order.exchange_order_id in exchange_order_ids
                    for order in trade_orders
                )
                
                if not has_open_orders:
                    self.logger.warning(
                        f"Trade {trade.id} for {symbol} has no open orders. "
                        f"Checking position..."
                    )
                    
                    trade.status = 'CLOSED'
                    trade.exit_time = datetime.utcnow()
                    
                    self.logger.info(f"Closed orphaned trade {trade.id}")
            
            # Update account balance
            self._update_balance(session)
            
            session.commit()
            session.close()
            
            self.logger.info("✅ State reconciliation complete")
            
        except Exception as e:
            self.logger.error(f"Reconciliation failed: {e}", exc_info=True)
    
    def _update_balance(self, session: Session) -> None:
        """Update account balance in database"""
        try:
            account = self.exchange.get_account()
            
            for balance_info in account['balances']:
                asset = balance_info['asset']
                free = safe_decimal(balance_info['free'])
                locked = safe_decimal(balance_info['locked'])
                total = free + locked
                
                if total > 0:
                    balance = Balance(
                        asset=asset,
                        free=free,
                        locked=locked,
                        total=total,
                        mode=self.mode,
                        timestamp=datetime.utcnow()
                    )
                    session.add(balance)
            
        except Exception as e:
            self.logger.error(f"Failed to update balance: {e}")
    
    def _get_interval_seconds(self) -> int:
        """
        ✅ CANDLE CLOSING: Converte interval string para segundos
        
        Returns:
            Número de segundos no intervalo
        """
        interval = self.settings.ENTRY_TIMEFRAME
        
        interval_map = {
            '1m': 60,
            '5m': 300,
            '15m': 900,
            '30m': 1800,
            '1h': 3600,
            '4h': 14400,
            '1d': 86400,
        }
        
        return interval_map.get(interval, 3600)
    
    def _get_max_data_age(self) -> int:

        seconds_per_interval = self._get_interval_seconds()
        
        if self.mode == 'testnet':
            # Testnet mais permissivo
            max_age_seconds = seconds_per_interval + 600  # +10min
        else:
            # Live mais rigoroso
            max_age_seconds = seconds_per_interval + 300  # +5min
        
        return max_age_seconds
    
    def _wait_for_candle_close(self) -> None:

        seconds_per_interval = self._get_interval_seconds()
        
        # Calcular segundos até próximo fechamento de candle
        now = datetime.utcnow()
        
        # Quantos segundos já se passaram neste período?
        seconds_into_period = (now.hour * 3600 + now.minute * 60 + now.second) % seconds_per_interval
        
        # Quantos segundos faltam para o próximo candle fechar?
        seconds_until_next = seconds_per_interval - seconds_into_period
        
        # Esperar até 30s ANTES do fechamento
        wait_time = seconds_until_next - 30
        
        # Se faltarem menos de 5 segundos, não espera (muito perto)
        if wait_time > 5:
            self.logger.info(
                f"⏱️ Waiting {wait_time:.0f}s for candle to close "
                f"({seconds_until_next:.0f}s remaining in this candle)"
            )
            time.sleep(wait_time)
        else:
            self.logger.debug(f"Candle closing soon, skipping wait")
    
    def start(self) -> None:
        """Start the trading loop com circuit breaker check mais frequente"""
        self.running = True
        self.logger.info(f"🚀 Starting {self.mode} trading loop...")
        
        notify(
            self.settings,
            f"Trading Bot Started - {self.mode.upper()}",
            f"Strategy: {self.settings.STRATEGY_MODE}\n"
            f"Pairs: {', '.join(self.settings.TRADING_PAIRS)}\n"
            f"Risk per trade: {self.settings.RISK_PER_TRADE * 100}%",
            "INFO"
        )
        
        try:
            last_cb_check = datetime.utcnow()
            
            while self.running:
                try:
                    # Check circuit breaker a cada 10 segundos
                    now = datetime.utcnow()
                    if (now - last_cb_check).seconds > 10:
                        triggered, reason = self.risk_manager.is_circuit_breaker_triggered()
                        if triggered:
                            self.logger.error(f"🚨 CIRCUIT BREAKER (mid-check): {reason}")
                            notify(
                                self.settings,
                                "🚨 Circuit Breaker Triggered (Emergency)",
                                reason,
                                "ERROR"
                            )
                            self.backup_manager.backup()
                            self.stop()
                            break
                        
                        last_cb_check = now
                    
                    # Wait for candle close
                    self._wait_for_candle_close()
                    
                    # Execute trading loop
                    self._trading_loop()
                    
                except Exception as e:
                    self.logger.error(f"Trading loop error: {e}", exc_info=True)
                
                # Pequeno delay
                time.sleep(5)
                
        except KeyboardInterrupt:
            self.logger.info("Received stop signal")
        finally:
            # Fazer backup final
            self.backup_manager.backup()
            self.stop()
    
    def _trading_loop(self) -> None:
        try:
            session = self.db_manager.get_session()
            
            now = datetime.utcnow()
            
            # ✅ NOVO: Reset diário
            was_reset = self.risk_manager.check_and_reset_daily_tracking(now)
            if was_reset:
                self.logger.info("📊 Daily tracking reset for new day")
            
            # ✅ NOVO: Backup periódico
            time_since_backup = (now - self.last_backup_time).total_seconds()
            if time_since_backup > 3600:
                self.logger.info("⏰ Performing periodic backup...")
                self.backup_manager.backup()
                self.last_backup_time = now
            
            # ✅ NOVO: Reconciliação periódica
            time_since_recon = (now - self.last_recon_time).total_seconds()
            if time_since_recon > 3600:
                self.logger.info("🔄 Periodic reconciliation with exchange...")
                self._reconcile_state()
                self.last_recon_time = now
            
            # # ✅ NOVO: Time sync periódica
            # time_since_sync = (now - self.last_time_sync).total_seconds()
            # if time_since_sync > 3600:
            #     self.logger.info("🕐 Syncing time with server...")
            #     self._sync_time_with_server()
            #     self.last_time_sync = now
            
            # ✅ Atualizar equity
            try:
                total_equity = self.exchange.get_total_balance_usdt()
                self.logger.debug(f"Current equity: ${total_equity:.2f}")
                self._track_equity_drift(total_equity)
            except Exception as e:
                self.logger.error(f"Failed to get equity: {e}")
                session.close()
                return
            
            self.risk_manager.update_equity_tracking(total_equity)
            
            # ✅ Check circuit breaker
            triggered, reason = self.risk_manager.is_circuit_breaker_triggered()
            if triggered:
                self.logger.error(f"🚨 CIRCUIT BREAKER TRIGGERED: {reason}")
                notify(self.settings, "🚨 Circuit Breaker", reason, "ERROR")
                self.backup_manager.backup()
                self.stop()
                session.close()
                return
            
            # ✅ Update open trades
            try:
                self._update_open_trades(session)
            except Exception as e:
                self.logger.error(f"Error updating trades: {e}", exc_info=True)
            
            # ✅ Scan for new opportunities
            try:
                self._scan_opportunities(session)
            except Exception as e:
                self.logger.error(f"Error scanning opportunities: {e}", exc_info=True)
            
            session.commit()
            session.close()
            
        except Exception as e:
            self.logger.error(f"Trading loop fatal error: {e}", exc_info=True)
    
    def _track_equity_drift(self, current_equity: Decimal) -> None:
        if self.expected_equity is None:
            self.expected_equity = current_equity
            self.last_known_equity = current_equity
            self.logger.info(f"💰 Initial equity set: ${current_equity:.2f}")
            return
        
        # Calcular diferença
        equity_diff = current_equity - self.last_known_equity
        equity_diff_pct = (equity_diff / self.last_known_equity * 100) if self.last_known_equity > 0 else 0
        
        # Log se houver diferença significativa (> 1%)
        if abs(equity_diff_pct) > 1.0:
            self.logger.warning(
                f"⚠️ Equity change detected: ${current_equity:.2f} "
                f"(was ${self.last_known_equity:.2f}) "
                f"Change: {equity_diff_pct:+.2f}%"
            )
            
            # Se diferença muito grande, possível problema
            if abs(equity_diff_pct) > 5.0:
                self.logger.error(
                    f"🚨 Large equity drift: {equity_diff_pct:+.2f}% "
                    f"Possible issue: deposit/withdrawal or data sync problem"
                )
        
        # Atualizar último conhecimento
        self.last_known_equity = current_equity
    
    def _update_open_trades(self, session: Session) -> None:
        """Atualizar trades abertos E executar partial TPs"""
        
        for symbol, trade in list(self.open_trades.items()):
            try:
                current_price = self.exchange.get_ticker_price(symbol)
                current_time = datetime.utcnow()
                
                # ✅ VERIFICAR E EXECUTAR PARTIAL TPs
                tp_hit = trade.check_partial_tp(
                    Decimal(str(current_price)),
                    current_time,
                    self.settings.TAKER_FEE
                )
                
                if tp_hit:
                    self.logger.info(
                        f"💰 {tp_hit} atingido para {symbol}: "
                        f"Posição parcial será fechada"
                    )
                    
                    # ✅ DETERMINAR QUANTIDADE A FECHAR
                    if tp_hit == 'TP1':
                        qty_to_sell = trade.initial_quantity * Decimal('0.3')
                    elif tp_hit == 'TP2':
                        qty_to_sell = trade.initial_quantity * Decimal('0.4')
                    else:  # TP3
                        qty_to_sell = trade.quantity
                    
                    # ✅ EXECUTAR ORDEM REAL
                    try:
                        exit_side = 'SELL' if trade.side == 'BUY' else 'BUY'
                        
                        self.logger.info(
                            f"📤 Closing partial: {qty_to_sell} {symbol} @ market"
                        )
                        
                        partial_order = self.exchange.create_order(
                            symbol=symbol,
                            side=exit_side,
                            order_type='MARKET',
                            quantity=qty_to_sell,
                            test=False
                        )
                        
                        actual_exit_price = Decimal(str(
                            partial_order.get('avgPrice', current_price)
                        ))
                        partial_order_id = partial_order.get('orderId')
                        
                        self.logger.info(
                            f"✅ Partial exit executed: "
                            f"ID={partial_order_id} | "
                            f"Qty={qty_to_sell} | "
                            f"Price=${actual_exit_price}"
                        )
                        
                        # ✅ SALVAR ORDEM DE SAÍDA PARCIAL NO DB
                        db_trade = session.query(Trade).filter(
                            Trade.exchange_order_id != None,
                            Trade.symbol == symbol,
                            Trade.status == 'OPEN'
                        ).first()
                        
                        if db_trade:
                            exit_order = Order(
                                trade_id=db_trade.id,
                                symbol=symbol,
                                side=exit_side,
                                order_type='MARKET',
                                quantity=qty_to_sell,
                                executed_quantity=qty_to_sell,
                                avg_price=actual_exit_price,
                                status='FILLED',
                                exchange_order_id=str(partial_order_id),
                                mode=self.mode
                            )
                            session.add(exit_order)
                        
                    except BinanceAPIException as e:
                        self.logger.error(
                            f"❌ Failed to execute partial exit: {e.message}"
                        )
                        continue
                    
                    # ✅ SE TOTALMENTE FECHADO VIA TP3
                    if trade.status == 'CLOSED':
                        self.open_trades.pop(symbol)
                        self._save_closed_trade_to_db(session, symbol, trade)
                        
                        self.logger.info(
                            f"✅ Trade completamente fechado via TPs parciais: "
                            f"PnL Total=${trade.pnl:.2f} ({trade.pnl_percent:+.2f}%)"
                        )
                        
                        notify(
                            self.settings,
                            f"✅ Trade Closed - {symbol}",
                            f"Method: Partial Take Profits\n"
                            f"Total PnL: ${trade.pnl:.2f}\n"
                            f"Return: {trade.pnl_percent:+.2f}%",
                            "INFO"
                        )
                    
                    session.commit()
                    continue
                
                # ✅ CHECK STOP LOSS (para quantidade restante)
                if trade.side == 'BUY' and current_price <= float(trade.stop_loss):
                    exit_price = trade.stop_loss
                    self._close_trade(
                        session, symbol, trade, exit_price,
                        current_time, 'STOP_LOSS'
                    )
                    continue
                
                if trade.side == 'SELL' and current_price >= float(trade.stop_loss):
                    exit_price = trade.stop_loss
                    self._close_trade(
                        session, symbol, trade, exit_price,
                        current_time, 'STOP_LOSS'
                    )
                    continue
                
                # ✅ CHECK TAKE PROFIT
                if trade.side == 'BUY' and current_price >= float(trade.take_profit):
                    exit_price = trade.take_profit
                    self._close_trade(
                        session, symbol, trade, exit_price,
                        current_time, 'TAKE_PROFIT'
                    )
                    continue
                
                if trade.side == 'SELL' and current_price <= float(trade.take_profit):
                    exit_price = trade.take_profit
                    self._close_trade(
                        session, symbol, trade, exit_price,
                        current_time, 'TAKE_PROFIT'
                    )
                    continue
            
            except Exception as e:
                self.logger.error(f"Error updating trade {symbol}: {e}", exc_info=True)
    
    def _close_trade(
        self,
        session: Session,
        symbol: str,
        trade: TestnetTrade,
        exit_price: Decimal,
        exit_time: datetime,
        reason: str
    ) -> None:
        """
        ✅ SLIPPAGE CONSISTENTE: Fechar trade com slippage (IGUAL AO BACKTEST)
        """
        
        # ✅ SINCRONIZAÇÃO: Aplicar slippage IGUAL ao backtest
        slippage = exit_price * self.settings.SLIPPAGE_PERCENT
        
        if trade.side == 'BUY':
            # Para compra longa, slippage reduz preço de saída
            slipped_exit_price = exit_price - slippage
            self.logger.debug(
                f"Slippage (BUY): ${exit_price:.2f} → ${slipped_exit_price:.2f} "
                f"(-${slippage:.4f})"
            )
        else:
            # Para venda curta, slippage aumenta preço de saída (piora)
            slipped_exit_price = exit_price + slippage
            self.logger.debug(
                f"Slippage (SELL): ${exit_price:.2f} → ${slipped_exit_price:.2f} "
                f"(+${slippage:.4f})"
            )
        
        # Usar preço com slippage para PnL
        trade.close(
            exit_price=slipped_exit_price,
            exit_time=exit_time,
            reason=reason,
            fee_rate=self.settings.TAKER_FEE
        )
        
        # Atualizar risk manager
        self.risk_manager.update_daily_pnl(trade.pnl)
        current_equity = self.exchange.get_total_balance_usdt()
        self.risk_manager.update_equity_tracking(current_equity)
        
        # Remover de open trades
        self.open_trades.pop(symbol, None)
        
        # Salvar no DB
        self._save_closed_trade_to_db(session, symbol, trade)
        
        pnl_emoji = "✅" if trade.pnl > 0 else "❌"
        self.logger.info(
            f"{pnl_emoji} Trade fechado: {trade.side} {symbol} | "
            f"Motivo: {reason} | "
            f"PnL: ${trade.pnl:.2f} ({trade.pnl_percent:+.2f}%)"
        )
        
        notify(
            self.settings,
            f"{pnl_emoji} Trade Closed - {symbol}",
            f"Side: {trade.side}\n"
            f"Entry: ${trade.entry_price}\n"
            f"Exit: ${slipped_exit_price} (com slippage)\n"
            f"Reason: {reason}\n"
            f"PnL: ${trade.pnl:.2f} ({trade.pnl_percent:+.2f}%)",
            "INFO"
        )
    
    def _save_closed_trade_to_db(self, session: Session, symbol: str, trade: TestnetTrade) -> None:
        """Save closed trade to database"""
        try:
            db_trade = Trade(
                symbol=symbol,
                side=trade.side,
                entry_price=trade.entry_price,
                exit_price=trade.exit_price,
                quantity=trade.initial_quantity,
                stop_loss=trade.stop_loss,
                take_profit=trade.take_profit,
                status='CLOSED',
                entry_time=trade.entry_time,
                exit_time=trade.exit_time,
                pnl=trade.pnl,
                pnl_percent=trade.pnl_percent,
                fees=trade.fees,
                strategy=self.settings.STRATEGY_MODE,
                timeframe=self.settings.ENTRY_TIMEFRAME,
                notes=trade.exit_reason,
                mode=self.mode
            )
            session.add(db_trade)
            session.flush()
            
            # Save partial exits if any
            for partial in trade.partial_exits:
                order = Order(
                    trade_id=db_trade.id,
                    symbol=symbol,
                    side='SELL' if trade.side == 'BUY' else 'BUY',
                    order_type='MARKET',
                    quantity=partial['quantity'],
                    executed_quantity=partial['quantity'],
                    status='FILLED',
                    avg_price=partial['price'],
                    mode=self.mode
                )
                session.add(order)
            
            session.commit()
            
        except Exception as e:
            self.logger.error(f"Failed to save trade to DB: {e}")
            session.rollback()
    
    def _scan_opportunities(self, session: Session) -> None:

        can_trade, reason = self.risk_manager.can_open_trade(len(self.open_trades))
        
        if not can_trade:
            self.logger.debug(f"Cannot open new trades: {reason}")
            return
        
        for symbol in self.settings.TRADING_PAIRS:
            try:
                if symbol in self.open_trades:
                    self.logger.debug(f"Skipping {symbol}: already have open trade")
                    continue
                try:
                    self.logger.debug(f"Fetching data for {symbol}...")
                    
                    # Buscar dados com limit (SEM end_time para testnet)
                    primary_df = self.exchange.get_klines(
                        symbol,
                        self.settings.PRIMARY_TIMEFRAME,
                        limit=500
                    )
                    
                    entry_df = self.exchange.get_klines(
                        symbol,
                        self.settings.ENTRY_TIMEFRAME,
                        limit=500
                    )
                    
                except ValueError as e:
                    self.logger.warning(f"❌ Failed to fetch data for {symbol}: {e}")
                    continue
                except Exception as e:
                    self.logger.error(f"Unexpected error fetching data for {symbol}: {e}", exc_info=True)
                    continue
                
                # ✅ VALIDAÇÃO: DataFrames não vazios
                if primary_df.empty or entry_df.empty:
                    self.logger.warning(
                        f"❌ Empty DataFrame for {symbol}: "
                        f"primary={len(primary_df)}, entry={len(entry_df)}"
                    )
                    continue
                
                # ✅ VALIDAÇÃO: Warmup mínimo
                MIN_WARMUP_CANDLES = 200
                if len(entry_df) < MIN_WARMUP_CANDLES:
                    self.logger.debug(
                        f"⚠️ {symbol}: Insufficient warmup "
                        f"({len(entry_df)}/{MIN_WARMUP_CANDLES})"
                    )
                    continue
                
                # ✅ DATA FRESHNESS: Validação robusta
                latest_entry_time = entry_df.index[-1]
                age_seconds = (datetime.utcnow() - latest_entry_time.replace(tzinfo=None)).total_seconds()
                max_age = self._get_max_data_age()
                
                if age_seconds > max_age:
                    self.logger.warning(
                        f"⚠️ Stale data for {symbol}: latest candle is {age_seconds:.0f}s old "
                        f"(max: {max_age}s). Skipping this symbol."
                    )
                    continue
                
                # ✅ DATA FRESHNESS: Validação robusta
                latest_entry_time = entry_df.index[-1]
                age_seconds = (datetime.utcnow() - latest_entry_time.replace(tzinfo=None)).total_seconds()
                
                # Máximo definido por timeframe (1 candle + 5min)
                max_age = self._get_max_data_age()
                
                if age_seconds > max_age:
                    self.logger.warning(
                        f"⚠️ Stale data for {symbol}: latest candle is {age_seconds:.0f}s old "
                        f"(max: {max_age}s). Skipping this symbol."
                    )
                    continue  # ✅ REJEIT A, não continua!
                
                # Multi-timeframe signal analysis
                signal, strength, metadata = self.mtf_analyzer.analyze(
                    primary_df,
                    entry_df
                )
                
                # ✅ LOG DETALHADO de todo sinal (mesmo HOLD)
                self.logger.info(
                    f"📊 {symbol}: Signal={signal:5s} | Strength={strength:.2f} | "
                    f"Primary={metadata.get('primary_signal', 'N/A'):5s} | "
                    f"Aligned={metadata.get('aligned', False)} | "
                    f"Age={age_seconds:.0f}s"
                )
                
                # ✅ SINCRONIZAÇÃO: MESMO threshold que backtest (0.40)
                if signal in ['BUY', 'SELL'] and strength > 0.40:
                    self.logger.info(
                        f"✅ TRADE SIGNAL for {symbol}: {signal} (strength={strength:.2f})"
                    )
                    self._execute_trade(
                        session, symbol, signal, strength, entry_df
                    )
                else:
                    # Log quando sinal é rejeitado
                    if signal in ['BUY', 'SELL']:
                        self.logger.debug(
                            f"⚠️ Signal {signal} for {symbol} rejected: "
                            f"strength {strength:.2f} below threshold 0.40"
                        )
            
            except Exception as e:
                self.logger.error(f"Error scanning {symbol}: {e}", exc_info=True)

    def _execute_trade(
        self,
        session: Session,
        symbol: str,
        signal: str,
        strength: float,
        df: pd.DataFrame
    ) -> None:
        """Executar novo trade COM ordem real no Binance"""
        
        try:
            # Calcular stops e quantidade
            filters = self.exchange.get_symbol_filters(symbol)
            current_price = self.exchange.get_ticker_price(symbol)
            
            stop_loss = self.risk_manager.calculate_stop_loss(
                entry_price=current_price,
                side=signal,
                atr=self.mtf_analyzer.get_atr(df),
                use_atr=True
            )
            
            take_profit = self.risk_manager.calculate_take_profit(
                entry_price=current_price,
                side=signal
            )
            
            total_capital = self.exchange.get_total_balance_usdt()
            
            quantity = self.risk_manager.calculate_dynamic_position_size(
                capital=total_capital,
                entry_price=current_price,
                stop_loss_price=stop_loss,
                symbol_filters=filters,
                signal_strength=strength
            )
            
            if not quantity:
                self.logger.warning(f"Position size too small for {symbol}")
                return
            
            # ✅ EXECUTAR ORDEM REAL NO TESTNET/LIVE
            self.logger.info(
                f"📤 Executing {signal} order: {quantity} {symbol} @ market"
            )
            
            try:
                order_response = self.exchange.create_order(
                    symbol=symbol,
                    side=signal,
                    order_type='MARKET',
                    quantity=quantity,
                    test=False  # ✅ REAL
                )
                
                exchange_order_id = order_response.get('orderId')
                executed_qty = Decimal(str(order_response.get('executedQty', 0)))
                avg_price = Decimal(str(order_response.get('avgPrice', current_price)))
                
                if not exchange_order_id:
                    self.logger.error(f"No order ID returned for {symbol}")
                    return
                
                self.logger.info(
                    f"✅ Order executed: ID={exchange_order_id} | "
                    f"Qty={executed_qty} | Avg=${avg_price}"
                )
                
                if executed_qty < quantity:
                    self.logger.warning(
                        f"⚠️ Partial execution: Expected {quantity}, got {executed_qty}"
                    )
                
                actual_entry_price = avg_price
                
            except BinanceAPIException as e:
                self.logger.error(
                    f"❌ Order execution failed: {e.status_code} - {e.message}"
                )
                notify(
                    self.settings,
                    f"❌ Order Failed - {symbol}",
                    f"Status: {e.status_code}\nMessage: {e.message}\n"
                    f"Quantity: {quantity}\nPrice: ${current_price}",
                    "ERROR"
                )
                return
            
            except TimeoutError as e:
                self.logger.error(f"⏱️ Order timeout: {e}")
                return
            
            # ✅ CRIAR TRADE LOCAL SÓ APÓS CONFIRMAÇÃO
            trade = TestnetTrade(
                symbol=symbol,
                side=signal,
                entry_price=actual_entry_price,
                quantity=executed_qty,
                entry_time=datetime.utcnow(),
                stop_loss=stop_loss,
                take_profit=take_profit
            )
            
            self.open_trades[symbol] = trade
            
            # ✅ SALVAR NO DATABASE COM ORDER ID
            db_trade = Trade(
                symbol=symbol,
                side=signal,
                entry_price=actual_entry_price,
                quantity=executed_qty,
                stop_loss=stop_loss,
                take_profit=take_profit,
                status='OPEN',
                entry_time=datetime.utcnow(),
                exchange_order_id=str(exchange_order_id),
                strategy=self.settings.STRATEGY_MODE,
                timeframe=self.settings.ENTRY_TIMEFRAME,
                signal_strength=strength,
                mode=self.mode
            )
            session.add(db_trade)
            session.commit()
            
            notify(
                self.settings,
                f"🎯 New Trade Opened - {symbol}",
                f"Order ID: {exchange_order_id}\n"
                f"Side: {signal}\n"
                f"Entry: ${actual_entry_price}\n"
                f"Quantity: {executed_qty}\n"
                f"Stop Loss: ${stop_loss}\n"
                f"Take Profit: ${take_profit}\n"
                f"Signal Strength: {strength:.2f}",
                "INFO"
            )
            
            self.logger.info(
                f"✅ Trade recorded: {symbol} {signal} @ ${actual_entry_price} × {executed_qty}"
            )
            
        except Exception as e:
            self.logger.error(f"Unexpected error in _execute_trade: {e}", exc_info=True)
            session.rollback()
    
    def stop(self) -> None:
        """Stop the trading loop"""
        self.logger.info("Stopping trading loop...")
        self.running = False
        
        try:
            self.exchange.close()
            self.db_manager.close()
        except:
            pass
        
        notify(
            self.settings,
            f"Trading Bot Stopped - {self.mode.upper()}",
            "Bot has been shut down",
            "INFO"
        )
        
        self.logger.info("✅ Trade Manager stopped")