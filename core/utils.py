"""
Utility functions for the trading bot
Logging, formatting, rounding, and helper functions
"""

import os
import sys
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from decimal import Decimal, ROUND_DOWN, ROUND_UP
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import time
from functools import wraps
import requests


def setup_logging(settings) -> logging.Logger:
    """
    Setup logging with rotation and console output
    
    Args:
        settings: Settings object with logging configuration
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger('TradingBot')
    logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
    
    # Remove existing handlers
    logger.handlers = []
    
    # Console handler with color support
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)
    
    # File handler with rotation
    if settings.LOG_TO_FILE:
        log_file = settings.LOGS_DIR / 'trading_bot.log'
        file_handler = TimedRotatingFileHandler(
            filename=log_file,
            when='midnight',
            interval=1,
            backupCount=settings.LOG_BACKUP_COUNT,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)
    
    return logger


def clear_screen() -> None:
    """Clear the terminal screen (cross-platform)"""
    os.system('cls' if os.name == 'nt' else 'clear')


def round_down(value: Decimal, step_size: Decimal) -> Decimal:
    """
    Round down to nearest step size (for Binance quantity/price filters)
    
    Args:
        value: Value to round
        step_size: Step size from exchange info
        
    Returns:
        Rounded value
    """
    if step_size == 0:
        return value
    
    precision = abs(step_size.as_tuple().exponent)
    return Decimal(value).quantize(step_size, rounding=ROUND_DOWN)


def round_up(value: Decimal, step_size: Decimal) -> Decimal:
    """
    Round up to nearest step size
    
    Args:
        value: Value to round
        step_size: Step size from exchange info
        
    Returns:
        Rounded value
    """
    if step_size == 0:
        return value
    
    precision = abs(step_size.as_tuple().exponent)
    return Decimal(value).quantize(step_size, rounding=ROUND_UP)


def format_quantity(quantity: Decimal, step_size: Decimal) -> str:
    """
    Format quantity string according to Binance step size
    
    Args:
        quantity: Quantity to format
        step_size: Step size from exchange info
        
    Returns:
        Formatted quantity string
    """
    rounded = round_down(quantity, step_size)
    
    # Remove trailing zeros
    result = f"{rounded:.8f}".rstrip('0').rstrip('.')
    
    return result


def format_price(price: Decimal, tick_size: Decimal) -> str:
    """
    Format price string according to Binance tick size
    
    Args:
        price: Price to format
        tick_size: Tick size from exchange info
        
    Returns:
        Formatted price string
    """
    rounded = round_down(price, tick_size)
    
    # Remove trailing zeros
    result = f"{rounded:.8f}".rstrip('0').rstrip('.')
    
    return result


def calculate_quantity(
    capital: Decimal,
    price: Decimal,
    risk_percent: Decimal,
    stop_loss_percent: Decimal,
    step_size: Decimal,
    min_qty: Decimal,
    min_notional: Decimal
) -> Optional[Decimal]:
    """
    Calculate position size based on risk management
    
    Args:
        capital: Total available capital
        price: Current asset price
        risk_percent: Risk per trade as decimal (0.02 = 2%)
        stop_loss_percent: Stop loss distance as decimal
        step_size: Exchange step size for quantity
        min_qty: Minimum quantity from exchange
        min_notional: Minimum notional value (quantity * price)
        
    Returns:
        Calculated quantity or None if too small
    """
    # Risk amount in USD
    risk_amount = capital * risk_percent
    
    # Position size based on risk and stop loss
    position_size_usd = risk_amount / stop_loss_percent
    
    # Quantity to buy
    quantity = position_size_usd / price
    
    # Round down to step size
    quantity = round_down(Decimal(str(quantity)), step_size)
    
    # Check minimum quantity
    if quantity < min_qty:
        return None
    
    # Check minimum notional
    notional = quantity * price
    if notional < min_notional:
        return None
    
    return quantity


def retry_with_backoff(
    max_retries: int = 5,
    initial_delay: float = 1.0,
    backoff_multiplier: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    Decorator for retrying functions with exponential backoff
    
    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        backoff_multiplier: Multiplier for exponential backoff
        exceptions: Tuple of exceptions to catch
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        raise
                    
                    logger = logging.getLogger('TradingBot')
                    logger.warning(
                        f"Attempt {attempt + 1}/{max_retries + 1} failed: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    
                    time.sleep(delay)
                    delay *= backoff_multiplier
            
            raise last_exception
        
        return wrapper
    return decorator


def send_telegram_message(
    token: str,
    chat_id: str,
    message: str,
    parse_mode: str = "HTML"
) -> bool:
    """
    Send message via Telegram
    
    Args:
        token: Telegram bot token
        chat_id: Telegram chat ID
        message: Message to send
        parse_mode: Message parse mode
        
    Returns:
        True if successful, False otherwise
    """
    if not token or not chat_id:
        return False
    
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": parse_mode
        }
        
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
        
    except Exception as e:
        logger = logging.getLogger('TradingBot')
        logger.error(f"Failed to send Telegram message: {e}")
        return False


def send_slack_message(webhook_url: str, message: str) -> bool:
    """
    Send message via Slack webhook
    
    Args:
        webhook_url: Slack webhook URL
        message: Message to send
        
    Returns:
        True if successful, False otherwise
    """
    if not webhook_url:
        return False
    
    try:
        payload = {"text": message}
        response = requests.post(webhook_url, json=payload, timeout=10)
        return response.status_code == 200
        
    except Exception as e:
        logger = logging.getLogger('TradingBot')
        logger.error(f"Failed to send Slack message: {e}")
        return False


def notify(settings, title: str, message: str, level: str = "INFO") -> None:
    """
    Send notification via configured channels
    
    Args:
        settings: Settings object with notification config
        title: Notification title
        message: Notification message
        level: Log level (INFO, WARNING, ERROR)
    """
    logger = logging.getLogger('TradingBot')
    
    # Format message
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_message = f"<b>{title}</b>\n{message}\n\n<i>{timestamp}</i>"
    
    # Send to Telegram
    if settings.TELEGRAM_ENABLED:
        send_telegram_message(
            settings.TELEGRAM_BOT_TOKEN,
            settings.TELEGRAM_CHAT_ID,
            full_message
        )
    
    # Send to Slack
    if settings.SLACK_ENABLED:
        slack_message = f"*{title}*\n{message}\n_{timestamp}_"
        send_slack_message(settings.SLACK_WEBHOOK_URL, slack_message)
    
    # Log locally
    log_func = getattr(logger, level.lower(), logger.info)
    log_func(f"{title}: {message}")


def calculate_sharpe_ratio(
    returns: list[float],
    risk_free_rate: float = 0.0,
    periods_per_year: int = 365
) -> float:
    """
    Calculate Sharpe ratio from returns
    
    Args:
        returns: List of period returns
        risk_free_rate: Annual risk-free rate
        periods_per_year: Number of periods per year
        
    Returns:
        Sharpe ratio
    """
    import numpy as np
    
    if not returns or len(returns) < 2:
        return 0.0
    
    returns_array = np.array(returns)
    excess_returns = returns_array - (risk_free_rate / periods_per_year)
    
    if np.std(excess_returns) == 0:
        return 0.0
    
    sharpe = np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(periods_per_year)
    return float(sharpe)


def calculate_sortino_ratio(
    returns: list[float],
    risk_free_rate: float = 0.0,
    periods_per_year: int = 365
) -> float:
    """
    Calculate Sortino ratio (downside deviation only)
    
    Args:
        returns: List of period returns
        risk_free_rate: Annual risk-free rate
        periods_per_year: Number of periods per year
        
    Returns:
        Sortino ratio
    """
    import numpy as np
    
    if not returns or len(returns) < 2:
        return 0.0
    
    returns_array = np.array(returns)
    excess_returns = returns_array - (risk_free_rate / periods_per_year)
    
    # Calculate downside deviation
    downside_returns = excess_returns[excess_returns < 0]
    
    if len(downside_returns) == 0 or np.std(downside_returns) == 0:
        return 0.0
    
    sortino = np.mean(excess_returns) / np.std(downside_returns) * np.sqrt(periods_per_year)
    return float(sortino)


def calculate_max_drawdown(equity_curve: list[float]) -> tuple[float, int, int]:
    """
    Calculate maximum drawdown from equity curve
    
    Args:
        equity_curve: List of equity values
        
    Returns:
        Tuple of (max_drawdown_percent, peak_idx, trough_idx)
    """
    import numpy as np
    
    if not equity_curve or len(equity_curve) < 2:
        return 0.0, 0, 0
    
    equity_array = np.array(equity_curve)
    running_max = np.maximum.accumulate(equity_array)
    drawdown = (equity_array - running_max) / running_max
    
    max_dd_idx = np.argmin(drawdown)
    max_dd = abs(float(drawdown[max_dd_idx]))
    
    # Find the peak before the max drawdown
    peak_idx = np.argmax(equity_array[:max_dd_idx + 1]) if max_dd_idx > 0 else 0
    
    return max_dd, peak_idx, max_dd_idx


def format_decimal(value: Decimal, decimal_places: int = 2) -> str:
    """
    Format decimal for display
    
    Args:
        value: Decimal value
        decimal_places: Number of decimal places
        
    Returns:
        Formatted string
    """
    return f"{value:.{decimal_places}f}"


def format_percentage(value: float, decimal_places: int = 2) -> str:
    """
    Format percentage for display
    
    Args:
        value: Percentage as decimal (0.05 = 5%)
        decimal_places: Number of decimal places
        
    Returns:
        Formatted string with % sign
    """
    return f"{value * 100:.{decimal_places}f}%"


def get_timestamp() -> int:
    """Get current timestamp in milliseconds"""
    return int(time.time() * 1000)


def timestamp_to_datetime(timestamp: int) -> datetime:
    """Convert timestamp in milliseconds to datetime"""
    return datetime.fromtimestamp(timestamp / 1000)


def datetime_to_timestamp(dt: datetime) -> int:
    """Convert datetime to timestamp in milliseconds"""
    return int(dt.timestamp() * 1000)


def validate_symbol_filters(
    symbol_info: Dict[str, Any],
    quantity: Decimal,
    price: Decimal
) -> tuple[bool, str]:
    """
    Validate order against Binance symbol filters
    
    Args:
        symbol_info: Symbol info from exchange
        quantity: Order quantity
        price: Order price
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    filters = {f['filterType']: f for f in symbol_info.get('filters', [])}
    
    # LOT_SIZE filter
    if 'LOT_SIZE' in filters:
        lot_filter = filters['LOT_SIZE']
        min_qty = Decimal(str(lot_filter['minQty']))
        max_qty = Decimal(str(lot_filter['maxQty']))
        step_size = Decimal(str(lot_filter['stepSize']))
        
        if quantity < min_qty:
            return False, f"Quantity {quantity} below minimum {min_qty}"
        
        if quantity > max_qty:
            return False, f"Quantity {quantity} above maximum {max_qty}"
        
        # Check step size compliance
        remainder = (quantity - min_qty) % step_size
        if remainder != 0:
            return False, f"Quantity {quantity} does not comply with step size {step_size}"
    
    # PRICE_FILTER
    if 'PRICE_FILTER' in filters:
        price_filter = filters['PRICE_FILTER']
        min_price = Decimal(str(price_filter['minPrice']))
        max_price = Decimal(str(price_filter['maxPrice']))
        tick_size = Decimal(str(price_filter['tickSize']))
        
        if price < min_price:
            return False, f"Price {price} below minimum {min_price}"
        
        if price > max_price:
            return False, f"Price {price} above maximum {max_price}"
        
        # Check tick size compliance
        remainder = (price - min_price) % tick_size
        if remainder != 0:
            return False, f"Price {price} does not comply with tick size {tick_size}"
    
    # MIN_NOTIONAL filter
    if 'MIN_NOTIONAL' in filters or 'NOTIONAL' in filters:
        notional_filter = filters.get('MIN_NOTIONAL') or filters.get('NOTIONAL')
        min_notional = Decimal(str(notional_filter.get('minNotional', 0)))
        
        notional = quantity * price
        if notional < min_notional:
            return False, f"Notional {notional} below minimum {min_notional}"
    
    return True, ""


class RateLimiter:
    """Rate limiter for API requests"""
    
    def __init__(self, max_requests: int, time_window: int = 60):
        """
        Initialize rate limiter
        
        Args:
            max_requests: Maximum requests per time window
            time_window: Time window in seconds
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
    
    def wait_if_needed(self) -> None:
        """Wait if rate limit would be exceeded"""
        now = time.time()
        
        # Remove old requests outside time window
        self.requests = [
            req_time for req_time in self.requests 
            if now - req_time < self.time_window
        ]
        
        # Check if we need to wait
        if len(self.requests) >= self.max_requests:
            oldest_request = min(self.requests)
            wait_time = self.time_window - (now - oldest_request)
            
            if wait_time > 0:
                logger = logging.getLogger('TradingBot')
                logger.warning(f"Rate limit reached. Waiting {wait_time:.2f}s...")
                time.sleep(wait_time)
                
                # Clean up again after waiting
                now = time.time()
                self.requests = [
                    req_time for req_time in self.requests 
                    if now - req_time < self.time_window
                ]
        
        # Record this request
        self.requests.append(time.time())


def safe_decimal(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    """
    Safely convert value to Decimal
    
    Args:
        value: Value to convert
        default: Default value if conversion fails
        
    Returns:
        Decimal value
    """
    try:
        if isinstance(value, Decimal):
            return value
        elif isinstance(value, (int, float)):
            return Decimal(str(value))
        elif isinstance(value, str):
            return Decimal(value)
        else:
            return default
    except:
        return default