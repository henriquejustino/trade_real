"""
Risk management module
Position sizing, stop loss, take profit, and risk control
"""

import logging
from typing import Optional, Tuple
from decimal import Decimal
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from core.utils import calculate_quantity, round_down


class RiskManager:
    """Risk management system for position sizing and control"""
    
    def __init__(self, settings):
        """
        Initialize risk manager
        
        Args:
            settings: Settings object with risk parameters
        """
        self.settings = settings
        self.logger = logging.getLogger('TradingBot.RiskManager')
        
        # Risk parameters
        self.risk_per_trade = settings.RISK_PER_TRADE
        self.max_open_trades = settings.MAX_OPEN_TRADES
        self.max_drawdown = settings.MAX_DRAWDOWN_PERCENT
        self.max_daily_loss = settings.MAX_DAILY_LOSS_PERCENT
        
        # Tracking
        self.daily_pnl = Decimal('0')
        self.daily_start_equity = None
        self.peak_equity = Decimal('0')
        self.current_drawdown = Decimal('0')
        
        self.logger.info("Risk Manager initialized")
    
    def calculate_position_size(
        self,
        capital: Decimal,
        entry_price: Decimal,
        stop_loss_price: Decimal,
        symbol_filters: dict
    ) -> Optional[Decimal]:
        """
        Calculate position size based on risk parameters
        
        Args:
            capital: Available capital
            entry_price: Entry price
            stop_loss_price: Stop loss price
            symbol_filters: Symbol filters from exchange
            
        Returns:
            Position size (quantity) or None if too small
        """
        # Calculate stop loss distance
        stop_loss_distance = abs(entry_price - stop_loss_price) / entry_price
        
        if stop_loss_distance == 0:
            self.logger.warning("Stop loss distance is zero")
            return None
        
        # Calculate position size
        quantity = calculate_quantity(
            capital=capital,
            price=entry_price,
            risk_percent=self.risk_per_trade,
            stop_loss_percent=Decimal(str(stop_loss_distance)),
            step_size=symbol_filters['stepSize'],
            min_qty=symbol_filters['minQty'],
            min_notional=symbol_filters['minNotional']
        )
        
        if quantity is None:
            self.logger.warning("Position size too small after applying filters")
            return None
        
        # Enforce position size limits
        position_value = quantity * entry_price
        
        if position_value < self.settings.MIN_POSITION_SIZE_USD:
            self.logger.warning(
                f"Position value ${position_value} below minimum "
                f"${self.settings.MIN_POSITION_SIZE_USD}"
            )
            return None
        
        if position_value > self.settings.MAX_POSITION_SIZE_USD:
            # Scale down to max
            max_quantity = self.settings.MAX_POSITION_SIZE_USD / entry_price
            quantity = round_down(
                Decimal(str(max_quantity)),
                symbol_filters['stepSize']
            )
            
            self.logger.info(
                f"Position scaled down to max size: {quantity}"
            )
        
        return quantity
    
    def calculate_stop_loss(
        self,
        entry_price: Decimal,
        side: str,
        atr: Optional[Decimal] = None,
        use_atr: bool = False
    ) -> Decimal:
        """
        Calculate stop loss price
        
        Args:
            entry_price: Entry price
            side: BUY or SELL
            atr: Average True Range value
            use_atr: Whether to use ATR-based stop
            
        Returns:
            Stop loss price
        """
        if use_atr and atr:
            # ATR-based stop loss
            multiplier = self.settings.TRAILING_STOP_ATR_MULTIPLIER
            stop_distance = atr * multiplier
        else:
            # Percentage-based stop loss
            stop_distance = entry_price * self.settings.STOP_LOSS_PERCENT
        
        if side == 'BUY':
            stop_loss = entry_price - stop_distance
        else:  # SELL
            stop_loss = entry_price + stop_distance
        
        return max(stop_loss, Decimal('0'))
    
    def calculate_take_profit(
        self,
        entry_price: Decimal,
        side: str,
        risk_reward_ratio: Optional[Decimal] = None
    ) -> Decimal:
        """
        Calculate take profit price
        
        Args:
            entry_price: Entry price
            side: BUY or SELL
            risk_reward_ratio: Risk-reward ratio (default from settings)
            
        Returns:
            Take profit price
        """
        if risk_reward_ratio:
            # Use custom risk-reward ratio
            stop_distance = entry_price * self.settings.STOP_LOSS_PERCENT
            profit_distance = stop_distance * risk_reward_ratio
        else:
            # Use configured take profit percentage
            profit_distance = entry_price * self.settings.TAKE_PROFIT_PERCENT
        
        if side == 'BUY':
            take_profit = entry_price + profit_distance
        else:  # SELL
            take_profit = entry_price - profit_distance
        
        return take_profit
    
    def update_trailing_stop(
        self,
        current_price: Decimal,
        entry_price: Decimal,
        current_stop: Decimal,
        side: str,
        atr: Optional[Decimal] = None
    ) -> Decimal:
        """
        Update trailing stop loss
        
        Args:
            current_price: Current market price
            entry_price: Entry price
            current_stop: Current stop loss price
            side: BUY or SELL
            atr: Average True Range value
            
        Returns:
            Updated stop loss price
        """
        if not self.settings.USE_TRAILING_STOP:
            return current_stop
        
        if atr:
            trail_distance = atr * self.settings.TRAILING_STOP_ATR_MULTIPLIER
        else:
            trail_distance = current_price * self.settings.STOP_LOSS_PERCENT
        
        if side == 'BUY':
            # For long positions, only move stop up
            new_stop = current_price - trail_distance
            return max(new_stop, current_stop)
        else:
            # For short positions, only move stop down
            new_stop = current_price + trail_distance
            return min(new_stop, current_stop)
    
    def can_open_trade(self, open_trades_count: int) -> Tuple[bool, str]:
        """
        Check if new trade can be opened
        
        Args:
            open_trades_count: Number of currently open trades
            
        Returns:
            Tuple of (can_trade, reason)
        """
        # Check max open trades
        if open_trades_count >= self.max_open_trades:
            return False, f"Max open trades reached ({self.max_open_trades})"
        
        # Check daily loss limit
        if self.daily_start_equity and self.daily_start_equity > 0:
            daily_loss_pct = abs(self.daily_pnl) / self.daily_start_equity
            
            if self.daily_pnl < 0 and daily_loss_pct > self.max_daily_loss:
                return False, f"Daily loss limit exceeded ({daily_loss_pct:.2%})"
        
        # Check drawdown limit
        if self.current_drawdown > self.max_drawdown:
            return False, f"Max drawdown exceeded ({self.current_drawdown:.2%})"
        
        return True, "OK"
    
    def update_equity_tracking(self, current_equity: Decimal) -> None:
        """
        Update equity tracking for drawdown calculation
        
        Args:
            current_equity: Current account equity
        """
        # Initialize daily start equity if needed
        if self.daily_start_equity is None:
            self.daily_start_equity = current_equity
        
        # Update peak equity
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity
        
        # Calculate current drawdown
        if self.peak_equity > 0:
            self.current_drawdown = (
                self.peak_equity - current_equity
            ) / self.peak_equity
        
        # Log if significant drawdown
        if self.current_drawdown > Decimal('0.05'):  # 5%
            self.logger.warning(
                f"Current drawdown: {self.current_drawdown:.2%} "
                f"(Peak: ${self.peak_equity}, Current: ${current_equity})"
            )
    
    def update_daily_pnl(self, pnl: Decimal) -> None:
        """
        Update daily PnL tracking
        
        Args:
            pnl: PnL to add to daily total
        """
        self.daily_pnl += pnl
        
        self.logger.info(f"Daily PnL updated: ${self.daily_pnl}")
    
    def reset_daily_tracking(self) -> None:
        """Reset daily tracking (call at start of new day)"""
        self.daily_pnl = Decimal('0')
        self.daily_start_equity = None
        
        self.logger.info("Daily tracking reset")
    
    def is_circuit_breaker_triggered(self) -> Tuple[bool, str]:
        """
        Check if circuit breaker should halt trading
        
        Returns:
            Tuple of (is_triggered, reason)
        """
        # Check drawdown
        if self.current_drawdown > self.max_drawdown:
            return True, f"Drawdown {self.current_drawdown:.2%} exceeds limit"
        
        # Check daily loss
        if self.daily_start_equity and self.daily_start_equity > 0:
            daily_loss_pct = abs(self.daily_pnl) / self.daily_start_equity
            
            if self.daily_pnl < 0 and daily_loss_pct > self.max_daily_loss:
                return True, f"Daily loss {daily_loss_pct:.2%} exceeds limit"
        
        return False, ""
    
    def calculate_risk_metrics(
        self,
        entry_price: Decimal,
        stop_loss: Decimal,
        take_profit: Decimal,
        quantity: Decimal,
        side: str
    ) -> dict:
        """
        Calculate risk metrics for a trade
        
        Args:
            entry_price: Entry price
            stop_loss: Stop loss price
            take_profit: Take profit price
            quantity: Position quantity
            side: BUY or SELL
            
        Returns:
            Dictionary with risk metrics
        """
        # Calculate potential loss
        if side == 'BUY':
            potential_loss = (entry_price - stop_loss) * quantity
            potential_profit = (take_profit - entry_price) * quantity
        else:
            potential_loss = (stop_loss - entry_price) * quantity
            potential_profit = (entry_price - take_profit) * quantity
        
        # Risk-reward ratio
        risk_reward = (
            potential_profit / potential_loss
            if potential_loss > 0 else Decimal('0')
        )
        
        return {
            'potential_loss': potential_loss,
            'potential_profit': potential_profit,
            'risk_reward_ratio': risk_reward,
            'stop_loss_pct': abs((stop_loss - entry_price) / entry_price),
            'take_profit_pct': abs((take_profit - entry_price) / entry_price),
        }
    
    def validate_trade_risk(
        self,
        risk_metrics: dict,
        min_risk_reward: Decimal = Decimal('1.5')
    ) -> Tuple[bool, str]:
        """
        Validate if trade meets risk criteria
        
        Args:
            risk_metrics: Risk metrics from calculate_risk_metrics
            min_risk_reward: Minimum acceptable risk-reward ratio
            
        Returns:
            Tuple of (is_valid, reason)
        """
        rr_ratio = risk_metrics['risk_reward_ratio']
        
        if rr_ratio < min_risk_reward:
            return False, f"Risk-reward ratio {rr_ratio:.2f} below minimum {min_risk_reward}"
        
        return True, "OK"
    
    def calculate_dynamic_position_size(
        self,
        capital: Decimal,
        entry_price: Decimal,
        stop_loss_price: Decimal,
        symbol_filters: dict,
        signal_strength: float  # NOVO PARÂMETRO!
    ) -> Optional[Decimal]:
        """
        Calculate position size dynamically based on signal strength
        
        Args:
            capital: Available capital
            entry_price: Entry price
            stop_loss_price: Stop loss price
            symbol_filters: Symbol filters from exchange
            signal_strength: Signal strength (0.0 to 1.0)
            
        Returns:
            Position size (quantity) or None if too small
        """
        # DYNAMIC RISK based on signal strength
        if signal_strength >= 0.8:
            # Very strong signal - risk 3%
            risk_multiplier = Decimal("1.5")  # 2% * 1.5 = 3%
            self.logger.info(f"💪 Sinal FORTE ({signal_strength:.2f}) - Usando 3% de risco")
        elif signal_strength >= 0.6:
            # Strong signal - risk 2.5%
            risk_multiplier = Decimal("1.25")  # 2% * 1.25 = 2.5%
            self.logger.info(f"👍 sinal BOM ({signal_strength:.2f}) - Usando risco de 2,5%")
        elif signal_strength >= 0.4:
            # Medium signal - risk 2%
            risk_multiplier = Decimal("1.0")  # 2% * 1.0 = 2%
            self.logger.info(f"✋ Sinal MÉDIO ({signal_strength:.2f}) - Usando 2% de risco")
        else:
            # Weak signal - risk 1.5%
            risk_multiplier = Decimal("0.75")  # 2% * 0.75 = 1.5%
            self.logger.info(f"⚠️ Sinal FRACO ({signal_strength:.2f}) - Usando risco de 1,5%")
        
        # Calculate dynamic risk
        dynamic_risk = self.risk_per_trade * risk_multiplier
        
        # Calculate stop loss distance
        stop_loss_distance = abs(entry_price - stop_loss_price) / entry_price
        
        if stop_loss_distance == 0:
            self.logger.warning("A distância do stop loss é zero")
            return None
        
        # Calculate position size with dynamic risk
        risk_amount = capital * dynamic_risk
        position_size_usd = risk_amount / stop_loss_distance
        quantity = position_size_usd / entry_price
        
        # Round down to step size
        from core.utils import round_down
        quantity = round_down(Decimal(str(quantity)), symbol_filters['stepSize'])
        
        # Check minimum quantity
        if quantity < symbol_filters['minQty']:
            return None
        
        # Check minimum notional
        notional = quantity * entry_price
        if notional < symbol_filters['minNotional']:
            return None
        
        # Enforce position size limits
        position_value = quantity * entry_price
        
        if position_value < self.settings.MIN_POSITION_SIZE_USD:
            self.logger.warning(
                f"Valor da posição ${position_value} abaixo do mínimo "
                f"${self.settings.MIN_POSITION_SIZE_USD}"
            )
            return None
        
        if position_value > self.settings.MAX_POSITION_SIZE_USD:
            # Scale down to max
            max_quantity = self.settings.MAX_POSITION_SIZE_USD / entry_price
            quantity = round_down(
                Decimal(str(max_quantity)),
                symbol_filters['stepSize']
            )
            self.logger.info(f"Posição reduzida ao tamanho máximo: {quantity}")
        
        return quantity