"""
Binance exchange integration using python-binance
Handles API calls, order management, and data fetching with retry logic
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from decimal import Decimal
from datetime import datetime, timedelta
import time
import pandas as pd
from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceRequestException
from core.utils import (
    retry_with_backoff, RateLimiter, round_down,
    format_quantity, format_price, validate_symbol_filters
)


class BinanceExchange:
    """Binance exchange API wrapper with error handling"""
    
    def __init__(self, api_key: str, api_secret: str, testnet: bool = False):
        """
        Initialize Binance client
        
        Args:
            api_key: Binance API key
            api_secret: Binance API secret
            api_secret: Binance API secret
            testnet: Whether to use testnet
        """
        self.logger = logging.getLogger('TradingBot.Exchange')
        self.testnet = testnet
        
        try:
            if testnet:
                self.client = Client(
                    api_key,
                    api_secret,
                    testnet=True
                )
                self.logger.info("✅ Connected to Binance Testnet")
            else:
                self.client = Client(api_key, api_secret)
                self.logger.info("✅ Connected to Binance Live")
            
            # Rate limiter
            self.rate_limiter = RateLimiter(max_requests=1200, time_window=60)
            
            # Cache exchange info
            self._exchange_info = None
            self._symbol_info_cache = {}
            self._load_exchange_info()
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Binance client: {e}")
            raise
    
    def _load_exchange_info(self) -> None:
        """Load and cache exchange information"""
        try:
            self._exchange_info = self.get_exchange_info()
            
            # Cache symbol info for quick access
            for symbol_info in self._exchange_info['symbols']:
                symbol = symbol_info['symbol']
                self._symbol_info_cache[symbol] = symbol_info
            
            self.logger.info(f"Loaded exchange info for {len(self._symbol_info_cache)} symbols")
            
        except Exception as e:
            self.logger.error(f"Failed to load exchange info: {e}")
            raise
    
    @retry_with_backoff(max_retries=3, exceptions=(BinanceRequestException,))
    def get_exchange_info(self) -> Dict[str, Any]:
        """
        Get exchange information
        
        Returns:
            Exchange info dictionary
        """
        self.rate_limiter.wait_if_needed()
        return self.client.get_exchange_info()
    
    def get_symbol_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get symbol information from cache
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Symbol info dictionary or None
        """
        return self._symbol_info_cache.get(symbol)
    
    def get_symbol_filters(self, symbol: str) -> Dict[str, Any]:
        """
        Get symbol filters (LOT_SIZE, PRICE_FILTER, MIN_NOTIONAL)
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Dictionary with filter values
        """
        symbol_info = self.get_symbol_info(symbol)
        
        if not symbol_info:
            raise ValueError(f"Symbol {symbol} not found")
        
        filters = {f['filterType']: f for f in symbol_info['filters']}
        
        # Extract key filter values
        lot_size = filters.get('LOT_SIZE', {})
        price_filter = filters.get('PRICE_FILTER', {})
        min_notional = filters.get('MIN_NOTIONAL') or filters.get('NOTIONAL', {})
        
        return {
            'stepSize': Decimal(str(lot_size.get('stepSize', '0.00000001'))),
            'minQty': Decimal(str(lot_size.get('minQty', '0.00000001'))),
            'maxQty': Decimal(str(lot_size.get('maxQty', '9000000000'))),
            'tickSize': Decimal(str(price_filter.get('tickSize', '0.00000001'))),
            'minPrice': Decimal(str(price_filter.get('minPrice', '0.00000001'))),
            'maxPrice': Decimal(str(price_filter.get('maxPrice', '1000000'))),
            'minNotional': Decimal(str(min_notional.get('minNotional', '10'))),
        }
    
    @retry_with_backoff(max_retries=3, exceptions=(BinanceRequestException,))
    def get_account(self) -> Dict[str, Any]:
        """
        Get account information
        
        Returns:
            Account info dictionary
        """
        self.rate_limiter.wait_if_needed()
        return self.client.get_account()
    
    @retry_with_backoff(max_retries=3, exceptions=(BinanceRequestException,))
    def get_asset_balance(self, asset: str) -> Dict[str, str]:
        """
        Get balance for specific asset
        
        Args:
            asset: Asset symbol (e.g., 'USDT', 'BTC')
            
        Returns:
            Balance dictionary with 'free', 'locked', 'total'
        """
        self.rate_limiter.wait_if_needed()
        return self.client.get_asset_balance(asset=asset)
    
    @retry_with_backoff(max_retries=3, exceptions=(BinanceRequestException,))
    def get_ticker_price(self, symbol: str) -> Decimal:
        """
        Get current ticker price
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Current price as Decimal
        """
        self.rate_limiter.wait_if_needed()
        ticker = self.client.get_symbol_ticker(symbol=symbol)
        return Decimal(str(ticker['price']))
    
    @retry_with_backoff(max_retries=3, exceptions=(BinanceRequestException,))
    def get_klines(
        self,
        symbol: str,
        interval: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000
    ) -> pd.DataFrame:
        """
        Get historical klines/candlestick data com validação robusta
        
        Args:
            symbol: Trading pair symbol
            interval: Kline interval (1m, 5m, 15m, 1h, 4h, 1d, etc.)
            start_time: Start time
            end_time: End time
            limit: Number of klines to retrieve (max 1000)
            
        Returns:
            DataFrame with OHLCV data
            
        Raises:
            ValueError: Se dados estão inválidos ou insuficientes
        """
        self.rate_limiter.wait_if_needed()
        
        # Convert datetime to timestamp
        kwargs = {'symbol': symbol, 'interval': interval, 'limit': limit}
        
        if start_time:
            kwargs['startTime'] = int(start_time.timestamp() * 1000)
        
        if end_time:
            kwargs['endTime'] = int(end_time.timestamp() * 1000)
        
        klines = self.client.get_klines(**kwargs)
        
        # 🔴 VALIDAÇÃO 1: Verifica se retornou dados
        if not klines or len(klines) == 0:
            raise ValueError(
                f"No kline data returned for {symbol} {interval}. "
                f"Possible causes: symbol invalid, date range empty, or API issue."
            )
        
        # Convert to DataFrame
        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])
        
        # 🔴 VALIDAÇÃO 2: Verifica se tem coluna de timestamp
        if 'timestamp' not in df.columns:
            raise ValueError(f"Missing 'timestamp' column in kline data for {symbol}")
        
        # Convert types
        try:
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df['close_time'] = pd.to_datetime(df['close_time'], unit='ms')
            
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
        except Exception as e:
            raise ValueError(f"Failed to convert kline data types for {symbol}: {e}")
        
        # 🔴 VALIDAÇÃO 3: Verifica se tem NaN após conversão
        if df[['open', 'high', 'low', 'close', 'volume']].isna().any().any():
            nan_count = df[['open', 'high', 'low', 'close', 'volume']].isna().sum().sum()
            self.logger.warning(
                f"⚠️ {symbol} {interval}: {nan_count} NaN values found after conversion. "
                f"Dropping NaN rows..."
            )
            df = df.dropna(subset=['open', 'high', 'low', 'close', 'volume'])
            
            if len(df) < 10:
                raise ValueError(
                    f"Too many NaN values in kline data for {symbol} {interval}. "
                    f"Only {len(df)} valid candles remain."
                )
        
        # 🔴 VALIDAÇÃO 4: Verifica se tem candles suficientes após limpeza
        if len(df) < 20:
            raise ValueError(
                f"Insufficient kline data for {symbol} {interval}: "
                f"only {len(df)} candles (minimum 20 required)"
            )
        
        # 🔴 VALIDAÇÃO 5: Verifica se timestamps estão em ordem e sem gaps excessivos
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        time_diffs = df['timestamp'].diff().dt.total_seconds()
        expected_interval_seconds = self._interval_to_seconds(interval)
        
        # Tolerância de 10% para gaps (testnet pode ser inconsistente)
        max_gap = expected_interval_seconds * 1.1
        
        large_gaps = time_diffs[time_diffs > max_gap]
        if len(large_gaps) > 0 and len(large_gaps) > len(df) * 0.1:  # Se >10% tem gaps
            self.logger.warning(
                f"⚠️ {symbol} {interval}: {len(large_gaps)} large gaps detected. "
                f"Data may be inconsistent. Continuing anyway..."
            )
        
        # Reset index to timestamp e retorna
        df.set_index('timestamp', inplace=True)
        result_df = df[['open', 'high', 'low', 'close', 'volume']].copy()
        
        # 🔴 VALIDAÇÃO 6: Log de sucesso com info
        self.logger.debug(
            f"✓ Loaded {len(result_df)} candles for {symbol} {interval} "
            f"[{result_df.index[0]} → {result_df.index[-1]}]"
        )
        
        return result_df
    
    def _interval_to_seconds(self, interval: str) -> int:
        """Converte interval string para segundos"""
        multipliers = {
            'm': 60,
            'h': 3600,
            'd': 86400,
            'w': 604800
        }
        
        number = int(interval[:-1])
        unit = interval[-1]
        
        return number * multipliers.get(unit, 3600)
    
    def create_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Decimal,
        price: Optional[Decimal] = None,
        stop_price: Optional[Decimal] = None,
        time_in_force: str = 'GTC',
        test: bool = False
    ) -> Dict[str, Any]:
        """
        Create an order COM TIMEOUT
        
        Args:
            symbol: Trading pair symbol
            side: BUY or SELL
            order_type: MARKET, LIMIT, STOP_LOSS, etc.
            quantity: Order quantity
            price: Limit price (for LIMIT orders)
            stop_price: Stop price (for STOP orders)
            time_in_force: Time in force (GTC, IOC, FOK)
            test: Whether to use test order endpoint
            
        Returns:
            Order response dictionary
            
        Raises:
            TimeoutError: Se ordem demora mais de 30s
            ValueError: Se validação falhar
        """
        import signal
        
        # Get symbol filters
        filters = self.get_symbol_filters(symbol)
        symbol_info = self.get_symbol_info(symbol)
        
        # Format quantity
        quantity_str = format_quantity(quantity, filters['stepSize'])
        
        # Validate quantity
        if Decimal(quantity_str) < filters['minQty']:
            raise ValueError(
                f"Quantity {quantity_str} below minimum {filters['minQty']}"
            )
        
        # Build order parameters
        params = {
            'symbol': symbol,
            'side': side,
            'type': order_type,
            'quantity': quantity_str,
        }
        
        # Add price for LIMIT orders
        if order_type in ['LIMIT', 'STOP_LOSS_LIMIT', 'TAKE_PROFIT_LIMIT']:
            if price is None:
                raise ValueError(f"Price required for {order_type} order")
            
            price_str = format_price(price, filters['tickSize'])
            params['price'] = price_str
            params['timeInForce'] = time_in_force
        
        # Add stop price for STOP orders
        if order_type in ['STOP_LOSS', 'STOP_LOSS_LIMIT', 'TAKE_PROFIT', 'TAKE_PROFIT_LIMIT']:
            if stop_price is None:
                raise ValueError(f"Stop price required for {order_type} order")
            
            stop_price_str = format_price(stop_price, filters['tickSize'])
            params['stopPrice'] = stop_price_str
        
        # Validate against filters
        validate_price = price or stop_price or self.get_ticker_price(symbol)
        is_valid, error_msg = validate_symbol_filters(
            symbol_info,
            Decimal(quantity_str),
            validate_price
        )
        
        if not is_valid:
            raise ValueError(f"Order validation failed: {error_msg}")
        
        # 🔴 CORREÇÃO: Adicionar timeout de 30 segundos
        def timeout_handler(signum, frame):
            raise TimeoutError(f"Order creation timeout after 30s for {symbol}")
        
        # Create order COM TIMEOUT
        self.rate_limiter.wait_if_needed()
        
        try:
            # Configurar signal de timeout (Linux/Mac)
            if hasattr(signal, 'SIGALRM'):
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(30)  # 30 segundos de timeout
            
            try:
                if test or self.testnet:
                    response = self.client.create_test_order(**params)
                    
                    if not response:
                        response = {
                            'symbol': symbol,
                            'orderId': int(time.time() * 1000),
                            'clientOrderId': f"test_{int(time.time() * 1000)}",
                            'transactTime': int(time.time() * 1000),
                            'price': params.get('price', '0'),
                            'origQty': params['quantity'],
                            'executedQty': params['quantity'] if order_type == 'MARKET' else '0',
                            'status': 'FILLED' if order_type == 'MARKET' else 'NEW',
                            'type': order_type,
                            'side': side,
                        }
                else:
                    response = self.client.create_order(**params)
                
                # Cancelar timeout se sucesso
                if hasattr(signal, 'SIGALRM'):
                    signal.alarm(0)
                
                self.logger.info(
                    f"Order created: {side} {quantity_str} {symbol} @ "
                    f"{params.get('price', 'MARKET')}"
                )
                
                return response
                
            except TimeoutError as e:
                self.logger.error(f"🚨 ORDER TIMEOUT: {e}")
                raise
            
            except BinanceAPIException as e:
                self.logger.error(f"Order creation failed: {e}")
                raise
                
        finally:
            # Garantir que cancel timeout
            if hasattr(signal, 'SIGALRM'):
                signal.alarm(0)
    
    @retry_with_backoff(max_retries=3, exceptions=(BinanceRequestException,))
    def cancel_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """
        Cancel an open order
        
        Args:
            symbol: Trading pair symbol
            order_id: Order ID to cancel
            
        Returns:
            Cancel response dictionary
        """
        self.rate_limiter.wait_if_needed()
        
        response = self.client.cancel_order(symbol=symbol, orderId=order_id)
        
        self.logger.info(f"Order cancelled: {order_id} for {symbol}")
        
        return response
    
    @retry_with_backoff(max_retries=3, exceptions=(BinanceRequestException,))
    def get_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """
        Get order status
        
        Args:
            symbol: Trading pair symbol
            order_id: Order ID
            
        Returns:
            Order status dictionary
        """
        self.rate_limiter.wait_if_needed()
        return self.client.get_order(symbol=symbol, orderId=order_id)
    
    @retry_with_backoff(max_retries=3, exceptions=(BinanceRequestException,))
    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all open orders
        
        Args:
            symbol: Trading pair symbol (optional, gets all if None)
            
        Returns:
            List of open orders
        """
        self.rate_limiter.wait_if_needed()
        
        if symbol:
            return self.client.get_open_orders(symbol=symbol)
        else:
            return self.client.get_open_orders()
    
    @retry_with_backoff(max_retries=3, exceptions=(BinanceRequestException,))
    def get_all_orders(
        self,
        symbol: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 500
    ) -> List[Dict[str, Any]]:
        """
        Get all orders (open and closed)
        
        Args:
            symbol: Trading pair symbol
            start_time: Start time
            end_time: End time
            limit: Number of orders to retrieve (max 1000)
            
        Returns:
            List of orders
        """
        self.rate_limiter.wait_if_needed()
        
        kwargs = {'symbol': symbol, 'limit': limit}
        
        if start_time:
            kwargs['startTime'] = int(start_time.timestamp() * 1000)
        
        if end_time:
            kwargs['endTime'] = int(end_time.timestamp() * 1000)
        
        return self.client.get_all_orders(**kwargs)
    
    @retry_with_backoff(max_retries=3, exceptions=(BinanceRequestException,))
    def get_my_trades(
        self,
        symbol: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 500
    ) -> List[Dict[str, Any]]:
        """
        Get trade history
        
        Args:
            symbol: Trading pair symbol
            start_time: Start time
            end_time: End time
            limit: Number of trades to retrieve (max 1000)
            
        Returns:
            List of trades
        """
        self.rate_limiter.wait_if_needed()
        
        kwargs = {'symbol': symbol, 'limit': limit}
        
        if start_time:
            kwargs['startTime'] = int(start_time.timestamp() * 1000)
        
        if end_time:
            kwargs['endTime'] = int(end_time.timestamp() * 1000)
        
        return self.client.get_my_trades(**kwargs)
    
    def calculate_commission(
        self,
        quantity: Decimal,
        price: Decimal,
        is_maker: bool = False
    ) -> Decimal:
        """
        Calculate trading commission
        
        Args:
            quantity: Trade quantity
            price: Trade price
            is_maker: Whether order is maker (default False = taker)
            
        Returns:
            Commission amount in quote asset
        """
        notional = quantity * price
        fee_rate = Decimal('0.001')  # 0.1% default
        
        commission = notional * fee_rate
        
        return commission
    
    def get_total_balance_usdt(self) -> Decimal:
        """
        Get total account balance in USDT
        
        Returns:
            Total balance in USDT
        """
        try:
            account = self.get_account()
            total_usdt = Decimal('0')
            
            for balance in account['balances']:
                asset = balance['asset']
                free = Decimal(balance['free'])
                locked = Decimal(balance['locked'])
                total = free + locked
                
                if total > 0:
                    if asset == 'USDT':
                        total_usdt += total
                    else:
                        # Try to get USD value
                        try:
                            symbol = f"{asset}USDT"
                            price = self.get_ticker_price(symbol)
                            total_usdt += total * price
                        except:
                            # Skip assets without USDT pair
                            pass
            
            return total_usdt
            
        except Exception as e:
            self.logger.error(f"Failed to calculate total balance: {e}")
            return Decimal('0')
    
    def ping(self) -> bool:
        """
        Test connectivity to the API
        
        Returns:
            True if connected, False otherwise
        """
        try:
            self.client.ping()
            return True
        except:
            return False
    
    def get_server_time(self) -> datetime:
        """
        Get server time
        
        Returns:
            Server datetime
        """
        response = self.client.get_server_time()
        return datetime.fromtimestamp(response['serverTime'] / 1000)
    
    def sync_time(self) -> None:
        """Synchronize local time with server time"""
        try:
            server_time = self.get_server_time()
            local_time = datetime.now()
            time_diff = (server_time - local_time).total_seconds()
            
            if abs(time_diff) > 1:
                self.logger.warning(
                    f"Time difference with server: {time_diff:.2f}s"
                )
        except Exception as e:
            self.logger.error(f"Failed to sync time: {e}")
    
    def close(self) -> None:
        """Close the client connection"""
        try:
            self.client.close_connection()
            self.logger.info("Exchange connection closed")
        except:
            pass