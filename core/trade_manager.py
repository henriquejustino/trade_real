"""
Trade Manager - Orchestrates live/testnet trading operations
Handles order execution, position management, and reconciliation
"""

import logging
import time
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


class TradeManager:
    """Manages trading operations and positions"""
    
    def __init__(self, settings, mode: str = 'live'):
        """
        Initialize trade manager
        
        Args:
            settings: Settings object
            mode: Operation mode ('live' or 'testnet')
        """
        self.settings = settings
        self.mode = mode
        self.logger = logging.getLogger(f'TradingBot.TradeManager.{mode}')
        
        # Validate configuration
        if mode == 'testnet':
            settings.validate_for_testnet()
        else:
            settings.validate_for_live_trading()
        
        # Initialize components
        self.logger.info("Initializing Trade Manager...")
        
        # Database
        self.db_manager = DatabaseManager(settings.DATABASE_URL)
        
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
        self.open_trades: Dict[str, Trade] = {}
        self.last_signal_time: Dict[str, datetime] = {}
        
        # Reconcile with exchange on startup
        self._reconcile_state()
        
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
        """Start the trading loop"""
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
            while self.running:
                self._trading_loop()
                time.sleep(60)  # Check every minute
                
        except KeyboardInterrupt:
            self.logger.info("Received stop signal")
        finally:
            self.stop()
    
    def _trading_loop(self) -> None:
        """Main trading loop iteration"""
        try:
            session = self.db_manager.get_session()
            
            # Update equity tracking
            total_equity = self.exchange.get_total_balance_usdt()
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
                self.stop()
                return
            
            # Update open trades
            self._update_open_trades(session)
            
            # Check for new opportunities
            self._scan_opportunities(session)
            
            session.commit()
            session.close()
            
        except Exception as e:
            self.logger.error(f"Trading loop error: {e}", exc_info=True)
    
    def _update_open_trades(self, session: Session) -> None:
        """Update status of open trades"""
        open_trades = session.query(Trade).filter(
            Trade.status == 'OPEN',
            Trade.mode == self.mode
        ).all()
        
        for trade in open_trades:
            try:
                # Get current price
                current_price = self.exchange.get_ticker_price(trade.symbol)
                
                # Check stop loss
                if trade.stop_loss:
                    if (trade.side == 'BUY' and current_price <= trade.stop_loss) or \
                       (trade.side == 'SELL' and current_price >= trade.stop_loss):
                        self.logger.info(
                            f"Stop loss hit for {trade.symbol}: "
                            f"Current ${current_price}, SL ${trade.stop_loss}"
                        )
                        self._close_trade(session, trade, current_price, 'STOP_LOSS')
                        continue
                
                # Check take profit
                if trade.take_profit:
                    if (trade.side == 'BUY' and current_price >= trade.take_profit) or \
                       (trade.side == 'SELL' and current_price <= trade.take_profit):
                        self.logger.info(
                            f"Take profit hit for {trade.symbol}: "
                            f"Current ${current_price}, TP ${trade.take_profit}"
                        )
                        self._close_trade(session, trade, current_price, 'TAKE_PROFIT')
                        continue
                
                # Update trailing stop if enabled
                if self.settings.USE_TRAILING_STOP and trade.trailing_stop:
                    # Get ATR for trailing calculation
                    df = self.exchange.get_klines(
                        trade.symbol,
                        self.settings.ENTRY_TIMEFRAME,
                        limit=50
                    )
                    atr = self.mtf_analyzer.get_atr(df)
                    
                    new_stop = self.risk_manager.update_trailing_stop(
                        current_price=current_price,
                        entry_price=trade.entry_price,
                        current_stop=trade.stop_loss,
                        side=trade.side,
                        atr=atr
                    )
                    
                    if new_stop != trade.stop_loss:
                        self.logger.info(
                            f"Trailing stop updated for {trade.symbol}: "
                            f"${trade.stop_loss} -> ${new_stop}"
                        )
                        trade.stop_loss = new_stop
                
            except Exception as e:
                self.logger.error(
                    f"Error updating trade {trade.id}: {e}",
                    exc_info=True
                )
    
    def _scan_opportunities(self, session: Session) -> None:
        """Scan for new trading opportunities"""
        # Check if we can open new trades
        open_count = session.query(Trade).filter(
            Trade.status == 'OPEN',
            Trade.mode == self.mode
        ).count()
        
        can_trade, reason = self.risk_manager.can_open_trade(open_count)
        
        if not can_trade:
            self.logger.debug(f"Cannot open new trades: {reason}")
            return
        
        # Scan each trading pair
        for symbol in self.settings.TRADING_PAIRS:
            try:
                # Skip if already have open trade on this pair
                existing_trade = session.query(Trade).filter(
                    Trade.symbol == symbol,
                    Trade.status == 'OPEN',
                    Trade.mode == self.mode
                ).first()
                if existing_trade:
                    continue
                
                # Avoid excessive signal frequency (2 min cooldown)
                last_signal = self.last_signal_time.get(symbol)
                if last_signal and (datetime.utcnow() - last_signal).seconds < 120:
                    continue
                
                # Fetch data for both timeframes
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
                
                # Multi-timeframe signal analysis
                signal, strength, metadata = self.mtf_analyzer.analyze(
                    primary_df,
                    entry_df
                )
                
                # Only act if BUY or SELL
                if signal in ['BUY', 'SELL']:
                    # Define tipo de execução com base na força do sinal
                    exec_type = (
                        'FULL' if strength >= 0.55 
                        else 'PARTIAL' if strength >= 0.40 
                        else 'SKIP'
                    )

                    if exec_type != 'SKIP':
                        self.logger.info(
                            f"✅ Signal detected: {symbol} | {signal} | "
                            f"Strength={strength:.2f} | Exec={exec_type}"
                        )
                        self._execute_trade(
                            session, symbol, signal, strength, entry_df, exec_type=exec_type
                        )
                        self.last_signal_time[symbol] = datetime.utcnow()
                    else:
                        self.logger.debug(
                            f"⚪ Ignored weak signal for {symbol}: "
                            f"{signal} (strength={strength:.2f})"
                        )
            
            except Exception as e:
                self.logger.error(f"Error scanning {symbol}: {e}", exc_info=True)

    
    def _execute_trade(self, session, symbol, signal, strength, df, exec_type: str = 'FULL') -> None:
        """Execute a new trade"""
        try:
            # Get current price and filters
            current_price = self.exchange.get_ticker_price(symbol)
            filters = self.exchange.get_symbol_filters(symbol)
            
            # Get total capital
            total_capital = self.exchange.get_total_balance_usdt()
            
            # Calculate stop loss and take profit
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
            
            # Calculate position size
            quantity = self.risk_manager.calculate_dynamic_position_size(
            capital=total_capital,
            entry_price=current_price,
            stop_loss_price=stop_loss,
            symbol_filters=filters,
            signal_strength=strength
            )

            # Se for execução parcial, reduz posição pela metade
            if exec_type == 'PARTIAL':
                quantity = (Decimal(str(quantity)) * Decimal("0.5")).quantize(Decimal('0.00000001'))
                self.logger.info(f"⚠ Execução parcial ativada — quantidade reduzida para {quantity}")
            
            if not quantity:
                self.logger.warning(f"Position size too small for {symbol}")
                return
            
            # Calculate risk metrics
            risk_metrics = self.risk_manager.calculate_risk_metrics(
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                quantity=quantity,
                side=side
            )
            
            # Validate trade
            is_valid, reason = self.risk_manager.validate_trade_risk(risk_metrics)
            if not is_valid:
                self.logger.warning(f"Trade validation failed: {reason}")
                return
            
            # Place order
            self.logger.info(
                f"Placing {side} order: {quantity} {symbol} @ ${current_price}"
            )
            
            order_response = self.exchange.create_order(
                symbol=symbol,
                side=side,
                order_type='MARKET',
                quantity=quantity,
                test=(self.mode == 'testnet')
            )
            
            # Create trade record
            trade = Trade(
                symbol=symbol,
                side=side,
                entry_price=current_price,
                quantity=quantity,
                stop_loss=stop_loss,
                take_profit=take_profit,
                trailing_stop=stop_loss if self.settings.USE_TRAILING_STOP else None,
                status='OPEN',
                strategy=self.settings.STRATEGY_MODE,
                timeframe=self.settings.ENTRY_TIMEFRAME,
                signal_strength=strength,
                risk_amount=risk_metrics['potential_loss'],
                risk_reward_ratio=float(risk_metrics['risk_reward_ratio']),
                mode=self.mode
            )
            
            session.add(trade)
            session.flush()  # Get trade ID
            
            # Create order record
            order = Order(
                trade_id=trade.id,
                exchange_order_id=str(order_response.get('orderId', '')),
                client_order_id=order_response.get('clientOrderId', ''),
                symbol=symbol,
                side=side,
                order_type='MARKET',
                quantity=quantity,
                executed_quantity=safe_decimal(order_response.get('executedQty', quantity)),
                status=order_response.get('status', 'FILLED'),
                avg_price=safe_decimal(order_response.get('price', current_price)),
                mode=self.mode
            )
            
            session.add(order)
            session.commit()
            
            # Send notification
            notify(
                self.settings,
                f"🎯 New Trade Opened - {symbol} ({exec_type})",
                f"Side: {side}\n"
                f"Entry: ${current_price}\n"
                f"Quantity: {quantity}\n"
                f"Stop Loss: ${stop_loss}\n"
                f"Take Profit: ${take_profit}\n"
                f"Risk/Reward: {risk_metrics['risk_reward_ratio']:.2f}",
                "INFO"
            )
            
            self.logger.info(f"✅ Trade opened: {trade.id} for {symbol}")
            
        except Exception as e:
            self.logger.error(f"Failed to execute trade: {e}", exc_info=True)
            session.rollback()
    
    def _close_trade(
        self,
        session: Session,
        trade: Trade,
        exit_price: Decimal,
        reason: str
    ) -> None:
        """Close an existing trade"""
        try:
            self.logger.info(f"Closing trade {trade.id} for {trade.symbol}: {reason}")
            
            # Place closing order
            close_side = 'SELL' if trade.side == 'BUY' else 'BUY'
            
            order_response = self.exchange.create_order(
                symbol=trade.symbol,
                side=close_side,
                order_type='MARKET',
                quantity=trade.quantity,
                test=(self.mode == 'testnet')
            )
            
            # Calculate PnL
            if trade.side == 'BUY':
                pnl = (exit_price - trade.entry_price) * trade.quantity
            else:
                pnl = (trade.entry_price - exit_price) * trade.quantity
            
            # Subtract fees
            commission = self.exchange.calculate_commission(
                trade.quantity,
                exit_price
            )
            pnl -= commission
            
            pnl_percent = float((pnl / (trade.entry_price * trade.quantity)) * 100)
            
            # Update trade
            trade.exit_price = exit_price
            trade.exit_time = datetime.utcnow()
            trade.status = 'CLOSED'
            trade.pnl = pnl
            trade.pnl_percent = pnl_percent
            trade.fees += commission
            trade.notes = reason
            
            # Update risk manager
            self.risk_manager.update_daily_pnl(pnl)
            
            # Create order record
            order = Order(
                trade_id=trade.id,
                exchange_order_id=str(order_response.get('orderId', '')),
                client_order_id=order_response.get('clientOrderId', ''),
                symbol=trade.symbol,
                side=close_side,
                order_type='MARKET',
                quantity=trade.quantity,
                executed_quantity=trade.quantity,
                status='FILLED',
                avg_price=exit_price,
                mode=self.mode
            )
            
            session.add(order)
            session.commit()
            
            # Send notification
            pnl_emoji = "💰" if pnl > 0 else "📉"
            notify(
                self.settings,
                f"{pnl_emoji} Trade Closed - {trade.symbol}",
                f"Reason: {reason}\n"
                f"Entry: ${trade.entry_price}\n"
                f"Exit: ${exit_price}\n"
                f"PnL: ${pnl:.2f} ({pnl_percent:+.2f}%)\n"
                f"Duration: {(trade.exit_time - trade.entry_time)}",
                "INFO"
            )
            
            self.logger.info(
                f"✅ Trade closed: {trade.id} | PnL: ${pnl:.2f} ({pnl_percent:+.2f}%)"
            )
            
        except Exception as e:
            self.logger.error(f"Failed to close trade: {e}", exc_info=True)
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