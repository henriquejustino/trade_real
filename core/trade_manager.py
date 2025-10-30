"""
Trade Manager - Orchestrates live/testnet trading operations
Handles order execution, position management, and reconciliation
SINCRONIZADO COM BACKTEST - Mesmos parametros e lógica
"""

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
        
        # 🔴 ADICIONE ISTO: Backup manager
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
        self.last_backup_time: datetime = datetime.utcnow()
        
        # Reconcile with exchange on startup
        self._reconcile_state()
        
        # 🔴 FAZER BACKUP INICIAL
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
                    # No open orders - check if we should close trade
                    self.logger.warning(
                        f"Trade {trade.id} for {symbol} has no open orders. "
                        f"Checking position..."
                    )
                    
                    # In a real implementation, check actual position
                    # For now, just mark as closed
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
                    # 🔴 ADICIONE ISTO: Check circuit breaker a cada 10 segundos
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
                    
                    # Wait for candle
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
            # 🔴 FAZER BACKUP FINAL
            self.backup_manager.backup()
            self.stop()
    
    def _wait_for_candle_close(self) -> None:
        """
        Aguarda o fechamento do candle atual
        Garante que você analisa candles COMPLETOS, não em progresso
        
        Exemplo com timeframe 1h:
        - Se são 13:30 (meio da hora), espera até 13:59:30
        - Aí dorme 30 segundos
        - Acorda em 14:00 com candle de 13:00-14:00 FECHADO
        """
        interval = self.settings.ENTRY_TIMEFRAME
        
        # Mapeamento interval → minutos
        interval_map = {
            '1m': 1,
            '5m': 5,
            '15m': 15,
            '30m': 30,
            '1h': 60,
            '4h': 240,
            '1d': 1440,
        }
        
        minutes = interval_map.get(interval, 60)
        
        # Calcular segundos até próximo fechamento de candle
        now = datetime.utcnow()
        
        # Quantos segundos já se passaram neste período?
        # Exemplo: em timeframe 1h, se são 13:45, se passaram 45min * 60s = 2700s
        seconds_into_period = (now.hour * 3600 + now.minute * 60 + now.second) % (minutes * 60)
        
        # Quantos segundos faltam para o próximo candle fechar?
        seconds_until_next = (minutes * 60) - seconds_into_period
        
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

    def _calculate_sleep_time(self) -> float:
        """
        Calcula sleep time baseado no timeframe da entrada
        Garante que não perde candles
        """
        interval = self.settings.ENTRY_TIMEFRAME
        
        # Mapeamento interval → minutos
        interval_map = {
            '1m': 1,
            '5m': 5,
            '15m': 15,
            '30m': 30,
            '1h': 60,
            '4h': 240,
            '1d': 1440,
        }
        
        minutes = interval_map.get(interval, 60)
        
        # Sleep = (interval - 5 segundos de buffer) convertido para segundos
        # Exemplo: 1h = 60min → sleep 55min = 3300s
        sleep_seconds = (minutes * 60) - 5
        
        # Mínimo 10s, máximo 60s para não ficar muito tempo sem checar
        sleep_seconds = max(10, min(sleep_seconds, 60))
        
        return sleep_seconds
    
    def _trading_loop(self) -> None:
        """Main trading loop com backup periódico"""
        try:
            session = self.db_manager.get_session()
            
            # 🔴 ADICIONE ISTO: Fazer backup a cada 1 hora
            now = datetime.utcnow()
            time_since_backup = (now - self.last_backup_time).total_seconds()
            
            if time_since_backup > 3600:  # 1 hora = 3600 segundos
                self.logger.info("⏰ Horário de backup periódico...")
                self.backup_manager.backup()
                self.last_backup_time = now
            
            # Wait for candle
            self._wait_for_candle_close()
            
            # Update equity tracking
            try:
                total_equity = self.exchange.get_total_balance_usdt()
                self.logger.debug(f"Current equity: ${total_equity:.2f}")
            except Exception as e:
                self.logger.error(f"Failed to get equity: {e}")
                session.close()
                return
            
            self.risk_manager.update_equity_tracking(total_equity)
            
            # Check circuit breaker
            triggered, reason = self.risk_manager.is_circuit_breaker_triggered()
            if triggered:
                self.logger.error(f"🚨 CIRCUIT BREAKER TRIGGERED: {reason}")
                notify(
                    self.settings,
                    "🚨 Circuit Breaker Triggered",
                    reason,
                    "ERROR"
                )
                # 🔴 FAZER BACKUP ANTES DE PARAR!
                self.backup_manager.backup()
                self.stop()
                session.close()
                return
            
            # Update open trades
            try:
                self._update_open_trades(session)
            except Exception as e:
                self.logger.error(f"Error updating trades: {e}", exc_info=True)
            
            # Check for new opportunities
            try:
                self._scan_opportunities(session)
            except Exception as e:
                self.logger.error(f"Error scanning opportunities: {e}", exc_info=True)
            
            session.commit()
            session.close()
            
        except Exception as e:
            self.logger.error(f"Trading loop fatal error: {e}", exc_info=True)
    
    def _update_open_trades(self, session: Session) -> None:
        """Update status of open trades - IGUAL AO BACKTEST"""
        for symbol, trade in list(self.open_trades.items()):
            try:
                # Get current price
                current_price = self.exchange.get_ticker_price(symbol)
                current_time = datetime.utcnow()
                
                # CHECK PARTIAL TAKE PROFITS FIRST! (IGUAL BACKTEST)
                tp_hit = trade.check_partial_tp(
                    Decimal(str(current_price)),
                    current_time,
                    self.settings.TAKER_FEE
                )
                
                if tp_hit:
                    self.logger.info(
                        f"  💰 {tp_hit} acerto para {symbol}: Posição parcial fechada"
                    )
                    
                    # If fully closed via TP3, remove from open trades
                    if trade.status == 'CLOSED':
                        self.open_trades.pop(symbol)
                        self.logger.info(
                            f"  ✅ Totalmente fechado via TPs parciais | "
                            f"Total PnL: ${trade.pnl:.2f} ({trade.pnl_percent:+.2f}%)"
                        )
                        # Salvar no banco de dados
                        self._save_closed_trade_to_db(session, symbol, trade)
                    continue
                
                # Check stop loss (para quantidade restante)
                if trade.side == 'BUY' and current_price <= float(trade.stop_loss):
                    exit_price = trade.stop_loss
                    self._close_trade(session, symbol, trade, exit_price, current_time, 'STOP_LOSS')
                    continue
                
                if trade.side == 'SELL' and current_price >= float(trade.stop_loss):
                    exit_price = trade.stop_loss
                    self._close_trade(session, symbol, trade, exit_price, current_time, 'STOP_LOSS')
                    continue
                
                # Check take profit
                if trade.side == 'BUY' and current_price >= float(trade.take_profit):
                    exit_price = trade.take_profit
                    self._close_trade(session, symbol, trade, exit_price, current_time, 'TAKE_PROFIT')
                    continue
                
                if trade.side == 'SELL' and current_price <= float(trade.take_profit):
                    exit_price = trade.take_profit
                    self._close_trade(session, symbol, trade, exit_price, current_time, 'TAKE_PROFIT')
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
        """Close trade - IGUAL AO BACKTEST"""
        
        # Apply slippage
        slippage = exit_price * self.settings.SLIPPAGE_PERCENT
        if trade.side == 'BUY':
            exit_price -= slippage
        else:
            exit_price += slippage
        
        # Close trade
        trade.close(
            exit_price=exit_price,
            exit_time=exit_time,
            reason=reason,
            fee_rate=self.settings.TAKER_FEE
        )
        
        # Update risk manager
        self.risk_manager.update_daily_pnl(trade.pnl)
        self.risk_manager.update_equity_tracking(self.exchange.get_total_balance_usdt())
        
        # Remove from open trades
        self.open_trades.pop(symbol, None)
        
        # Save to database
        self._save_closed_trade_to_db(session, symbol, trade)
        
        pnl_emoji = "✅" if trade.pnl > 0 else "❌"
        self.logger.info(
            f"  {pnl_emoji} Closed {trade.side} trade: {reason} | "
            f"PnL: ${trade.pnl:.2f} ({trade.pnl_percent:+.2f}%)"
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
        """Scan for new trading opportunities com validação robusta"""
        
        can_trade, reason = self.risk_manager.can_open_trade(len(self.open_trades))
        
        if not can_trade:
            self.logger.debug(f"Cannot open new trades: {reason}")
            return
        
        for symbol in self.settings.TRADING_PAIRS:
            try:
                if symbol in self.open_trades:
                    self.logger.debug(f"Skipping {symbol}: already have open trade")
                    continue
                
                # Avoid excessive signal frequency (2 min cooldown)
                last_signal = self.last_signal_time.get(symbol)
                if last_signal and (datetime.utcnow() - last_signal).seconds < 120:
                    self.logger.debug(f"Skipping {symbol}: in cooldown period")
                    continue
                
                try:
                    self.logger.debug(f"Fetching data for {symbol}...")
                    
                    # 🔴 SEM end_time (testnet não suporta)
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
                
                # 🔴 VALIDAÇÃO: DataFrames não vazios
                if primary_df.empty or entry_df.empty:
                    self.logger.warning(
                        f"❌ Empty DataFrame for {symbol}: "
                        f"primary={len(primary_df)}, entry={len(entry_df)}"
                    )
                    continue
                
                # 🔴 VALIDAÇÃO: Timestamps recentes (relaxado para testnet)
                latest_entry_time = entry_df.index[-1]
                age_seconds = (datetime.utcnow() - latest_entry_time.replace(tzinfo=None)).total_seconds()
                
                # Aceita dados até 1h atrasados (testnet é assim)
                max_age = 3600
                
                if age_seconds > max_age:
                    self.logger.warning(
                        f"⚠️ Stale data for {symbol}: latest candle is {age_seconds:.0f}s old"
                    )
                
                # Multi-timeframe signal analysis
                signal, strength, metadata = self.mtf_analyzer.analyze(
                    primary_df,
                    entry_df
                )
                
                # 🔴 LOG DETALHADO de todo sinal (mesmo HOLD)
                self.logger.info(
                    f"📊 {symbol}: Signal={signal:5s} | Strength={strength:.2f} | "
                    f"Primary={metadata.get('primary_signal', 'N/A'):5s} | "
                    f"Aligned={metadata.get('aligned', False)} | "
                    f"Age={age_seconds:.0f}s"
                )
                
                # 🔴 THRESHOLD: Aceita sinais acima de 0.35 (reduzido para testnet)
                if signal in ['BUY', 'SELL'] and strength > 0.35:
                    self.logger.info(
                        f"✅ TRADE SIGNAL for {symbol}: {signal} (strength={strength:.2f})"
                    )
                    self._execute_trade(
                        session, symbol, signal, strength, entry_df
                    )
                    self.last_signal_time[symbol] = datetime.utcnow()
                else:
                    # Log quando sinal é rejeitado
                    if signal in ['BUY', 'SELL']:
                        self.logger.debug(
                            f"⚠️ Signal {signal} for {symbol} rejected: "
                            f"strength {strength:.2f} below threshold 0.48"
                        )
            
            except Exception as e:
                self.logger.error(f"Error scanning {symbol}: {e}", exc_info=True)

    def _get_max_data_age(self) -> int:
        """
        Calcula idade máxima aceitável dos dados em segundos
        baseado no timeframe
        """
        interval = self.settings.ENTRY_TIMEFRAME
        
        # Mapeamento interval → minutos
        interval_map = {
            '1m': 1,
            '5m': 5,
            '15m': 15,
            '30m': 30,
            '1h': 60,
            '4h': 240,
            '1d': 1440,
        }
        
        minutes = interval_map.get(interval, 60)
        
        # Dados podem estar atrasados por até 1 candle inteiro + 5min buffer
        # Exemplo: timeframe 1h → max age = 60min + 5min = 3900s
        max_age_seconds = (minutes * 60) + 300  # +5min buffer
        
        return max_age_seconds
    
    def _execute_trade(
        self,
        session: Session,
        symbol: str,
        signal: str,
        strength: float,
        df: pd.DataFrame
    ) -> None:
        """Execute a new trade - IGUAL AO BACKTEST"""
        try:
            # Get current price and filters
            current_price = self.exchange.get_ticker_price(symbol)
            filters = self.exchange.get_symbol_filters(symbol)
            
            # Get total capital
            total_capital = self.exchange.get_total_balance_usdt()
            
            # Calculate stops - IGUAL AO BACKTEST
            atr = self.mtf_analyzer.get_atr(df)
            
            side = signal  # 'BUY' or 'SELL'
            
            stop_loss = self.risk_manager.calculate_stop_loss(
                entry_price=current_price,
                side=side,
                atr=atr,
                use_atr=bool(atr > 0)
            )
            
            take_profit = self.risk_manager.calculate_take_profit(
                entry_price=current_price,
                side=side
            )
            
            # Calculate position size - IGUAL AO BACKTEST
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
            
            # Create testnet trade object
            trade = TestnetTrade(
                symbol=symbol,
                side=side,
                entry_price=current_price,
                quantity=quantity,
                entry_time=datetime.utcnow(),
                stop_loss=stop_loss,
                take_profit=take_profit
            )
            
            self.open_trades[symbol] = trade
            
            # Save to database
            db_trade = Trade(
                symbol=symbol,
                side=side,
                entry_price=current_price,
                quantity=quantity,
                stop_loss=stop_loss,
                take_profit=take_profit,
                status='OPEN',
                strategy=self.settings.STRATEGY_MODE,
                timeframe=self.settings.ENTRY_TIMEFRAME,
                signal_strength=strength,
                mode=self.mode
            )
            session.add(db_trade)
            session.commit()
            
            # Send notification
            notify(
                self.settings,
                f"🎯 New Trade Opened - {symbol}",
                f"Side: {side}\n"
                f"Entry: ${current_price}\n"
                f"Quantity: {quantity}\n"
                f"Stop Loss: ${stop_loss}\n"
                f"Take Profit: ${take_profit}\n"
                f"Signal Strength: {strength:.2f}",
                "INFO"
            )
            
            self.logger.info(
                f"✅ Trade opened: {symbol} {side} @ ${current_price} | "
                f"SL: ${stop_loss}, TP: ${take_profit}"
            )
            
        except Exception as e:
            self.logger.error(f"Failed to execute trade: {e}", exc_info=True)
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