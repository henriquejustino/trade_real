"""
Trading strategy implementations
Mean Reversion, Breakout, Trend Following, and Ensemble strategies
"""

import logging
from typing import Optional, Dict, Tuple
from decimal import Decimal
import pandas as pd
import numpy as np
import ta


class BaseStrategy:
    """Base class for all trading strategies"""
    
    def __init__(self, name: str):
        """
        Initialize base strategy
        
        Args:
            name: Strategy name
        """
        self.name = name
        self.logger = logging.getLogger(f'TradingBot.Strategy.{name}')
    
    def generate_signal(self, df: pd.DataFrame) -> Tuple[str, float]:
        """
        Generate trading signal from data
        
        Args:
            df: DataFrame with OHLCV data and indicators
            
        Returns:
            Tuple of (signal, strength) where signal is 'BUY', 'SELL', or 'HOLD'
            and strength is 0.0 to 1.0
        """
        raise NotImplementedError("Subclasses must implement generate_signal")
    
    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add technical indicators to DataFrame
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            DataFrame with added indicators
        """
        raise NotImplementedError("Subclasses must implement add_indicators")


class MeanReversionStrategy(BaseStrategy):
    """Mean reversion strategy using Bollinger Bands and RSI"""
    
    def __init__(
        self,
        bb_period: int = 20,
        bb_std: float = 2.0,
        rsi_period: int = 14,
        rsi_oversold: float = 30,
        rsi_overbought: float = 70
    ):
        super().__init__("MeanReversion")
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
    
    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add Bollinger Bands and RSI"""
        df = df.copy()
        
        # Bollinger Bands
        bb = ta.volatility.BollingerBands(
            close=df['close'],
            window=self.bb_period,
            window_dev=self.bb_std
        )
        df['bb_upper'] = bb.bollinger_hband()
        df['bb_middle'] = bb.bollinger_mavg()
        df['bb_lower'] = bb.bollinger_lband()
        df['bb_width'] = bb.bollinger_wband()
        
        # RSI
        df['rsi'] = ta.momentum.RSIIndicator(
            close=df['close'],
            window=self.rsi_period
        ).rsi()
        
        return df
    
    def generate_signal(self, df: pd.DataFrame) -> Tuple[str, float]:
        """
        Generate mean reversion signal
        
        Buy when price touches lower band and RSI is oversold
        Sell when price touches upper band and RSI is overbought
        """
        if len(df) < self.bb_period:
            return 'HOLD', 0.0
        
        df = self.add_indicators(df)
        
        # Get latest values
        close = df['close'].iloc[-1]
        bb_upper = df['bb_upper'].iloc[-1]
        bb_lower = df['bb_lower'].iloc[-1]
        bb_middle = df['bb_middle'].iloc[-1]
        rsi = df['rsi'].iloc[-1]
        
        # Check for NaN
        if pd.isna(rsi) or pd.isna(bb_lower):
            return 'HOLD', 0.0
        
        # Buy signal: price at lower band + RSI oversold
        if close <= bb_lower and rsi < self.rsi_oversold:
            # Strength based on how oversold
            strength = min(1.0, (self.rsi_oversold - rsi) / 20)
            return 'BUY', strength
        
        # Sell signal: price at upper band + RSI overbought
        if close >= bb_upper and rsi > self.rsi_overbought:
            # Strength based on how overbought
            strength = min(1.0, (rsi - self.rsi_overbought) / 20)
            return 'SELL', strength
        
        return 'HOLD', 0.0


class BreakoutStrategy(BaseStrategy):
    """Breakout strategy using Donchian Channels and volume"""
    
    def __init__(
        self,
        lookback_period: int = 20,
        volume_threshold: float = 1.5
    ):
        super().__init__("Breakout")
        self.lookback_period = lookback_period
        self.volume_threshold = volume_threshold
    
    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add Donchian Channels and volume indicators"""
        df = df.copy()
        
        # Donchian Channels
        df['dc_upper'] = df['high'].rolling(window=self.lookback_period).max()
        df['dc_lower'] = df['low'].rolling(window=self.lookback_period).min()
        df['dc_middle'] = (df['dc_upper'] + df['dc_lower']) / 2
        
        # Volume indicators
        df['volume_ma'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma']
        
        # ATR for volatility
        df['atr'] = ta.volatility.AverageTrueRange(
            high=df['high'],
            low=df['low'],
            close=df['close'],
            window=14
        ).average_true_range()
        
        return df
    
    def generate_signal(self, df: pd.DataFrame) -> Tuple[str, float]:
        """
        Generate breakout signal
        
        Buy on upside breakout with high volume
        Sell on downside breakout with high volume
        """
        if len(df) < self.lookback_period:
            return 'HOLD', 0.0
        
        df = self.add_indicators(df)
        
        # Get latest values
        close = df['close'].iloc[-1]
        prev_close = df['close'].iloc[-2]
        dc_upper = df['dc_upper'].iloc[-2]  # Previous candle's high
        dc_lower = df['dc_lower'].iloc[-2]  # Previous candle's low
        volume_ratio = df['volume_ratio'].iloc[-1]
        
        if pd.isna(dc_upper) or pd.isna(volume_ratio):
            return 'HOLD', 0.0
        
        # Buy signal: breakout above upper channel with volume
        if close > dc_upper and volume_ratio > self.volume_threshold:
            # Strength based on volume and breakout magnitude
            breakout_pct = (close - dc_upper) / dc_upper
            strength = min(1.0, (volume_ratio / self.volume_threshold) * 0.5 + 0.5)
            return 'BUY', strength
        
        # Sell signal: breakdown below lower channel with volume
        if close < dc_lower and volume_ratio > self.volume_threshold:
            # Strength based on volume and breakdown magnitude
            breakdown_pct = (dc_lower - close) / dc_lower
            strength = min(1.0, (volume_ratio / self.volume_threshold) * 0.5 + 0.5)
            return 'SELL', strength
        
        return 'HOLD', 0.0


class TrendFollowingStrategy(BaseStrategy):
    """Trend following strategy using EMA crossover and MACD"""
    
    def __init__(
        self,
        fast_ema: int = 12,
        slow_ema: int = 26,
        signal_ema: int = 9,
        trend_ema: int = 200
    ):
        super().__init__("TrendFollowing")
        self.fast_ema = fast_ema
        self.slow_ema = slow_ema
        self.signal_ema = signal_ema
        self.trend_ema = trend_ema
    
    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add EMA and MACD indicators"""
        df = df.copy()
        
        # EMAs
        df['ema_fast'] = ta.trend.EMAIndicator(
            close=df['close'],
            window=self.fast_ema
        ).ema_indicator()
        
        df['ema_slow'] = ta.trend.EMAIndicator(
            close=df['close'],
            window=self.slow_ema
        ).ema_indicator()
        
        df['ema_trend'] = ta.trend.EMAIndicator(
            close=df['close'],
            window=self.trend_ema
        ).ema_indicator()
        
        # MACD
        macd = ta.trend.MACD(
            close=df['close'],
            window_fast=self.fast_ema,
            window_slow=self.slow_ema,
            window_sign=self.signal_ema
        )
        df['macd'] = macd.macd()
        df['macd_signal'] = macd.macd_signal()
        df['macd_diff'] = macd.macd_diff()
        
        # ADX for trend strength
        adx = ta.trend.ADXIndicator(
            high=df['high'],
            low=df['low'],
            close=df['close'],
            window=14
        )
        df['adx'] = adx.adx()
        
        return df
    
    def generate_signal(self, df: pd.DataFrame) -> Tuple[str, float]:
        """
        Generate trend following signal
        
        Buy on bullish EMA cross above trend line with MACD confirmation
        Sell on bearish EMA cross below trend line with MACD confirmation
        """
        if len(df) < self.trend_ema:
            return 'HOLD', 0.0
        
        df = self.add_indicators(df)
        
        # Get latest values
        close = df['close'].iloc[-1]
        ema_fast = df['ema_fast'].iloc[-1]
        ema_slow = df['ema_slow'].iloc[-1]
        ema_trend = df['ema_trend'].iloc[-1]
        macd = df['macd'].iloc[-1]
        macd_signal = df['macd_signal'].iloc[-1]
        adx = df['adx'].iloc[-1]
        
        # Previous values
        prev_ema_fast = df['ema_fast'].iloc[-2]
        prev_ema_slow = df['ema_slow'].iloc[-2]
        
        if pd.isna(ema_fast) or pd.isna(adx):
            return 'HOLD', 0.0
        
        # Check trend strength (ADX > 25 indicates strong trend)
        trend_strength = min(1.0, adx / 50) if adx > 25 else 0.5
        
        # Buy signal: bullish cross above trend line
        if (ema_fast > ema_slow and prev_ema_fast <= prev_ema_slow and
            close > ema_trend and macd > macd_signal):
            return 'BUY', trend_strength
        
        # Sell signal: bearish cross below trend line
        if (ema_fast < ema_slow and prev_ema_fast >= prev_ema_slow and
            close < ema_trend and macd < macd_signal):
            return 'SELL', trend_strength
        
        return 'HOLD', 0.0


class EnsembleStrategy(BaseStrategy):
    """Ensemble strategy combining multiple strategies with weighted voting"""
    
    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None
    ):
        super().__init__("Ensemble")
        
        # Initialize sub-strategies
        self.strategies = {
            'mean_reversion': MeanReversionStrategy(),
            'breakout': BreakoutStrategy(),
            'trend_following': TrendFollowingStrategy()
        }
        
        # Default weights
        self.weights = weights or {
            'mean_reversion': 0.3,
            'breakout': 0.3,
            'trend_following': 0.4
        }
        
        # Normalize weights
        total_weight = sum(self.weights.values())
        self.weights = {k: v / total_weight for k, v in self.weights.items()}
    
    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add all indicators from sub-strategies"""
        df = df.copy()
        
        for strategy in self.strategies.values():
            df = strategy.add_indicators(df)
        
        return df
    
    def generate_signal(self, df: pd.DataFrame) -> Tuple[str, float]:
        """
        Generate ensemble signal by weighted voting
        
        Returns strongest consensus signal
        """
        if len(df) < 200:  # Need enough data for trend following
            return 'HOLD', 0.0
        
        # Get signals from all strategies
        signals = {}
        for name, strategy in self.strategies.items():
            signal, strength = strategy.generate_signal(df)
            signals[name] = (signal, strength)
            self.logger.debug(f"{name}: {signal} ({strength:.2f})")
        
        # Calculate weighted votes
        buy_score = 0.0
        sell_score = 0.0
        
        for name, (signal, strength) in signals.items():
            weight = self.weights[name]
            weighted_strength = strength * weight
            
            if signal == 'BUY':
                buy_score += weighted_strength
            elif signal == 'SELL':
                sell_score += weighted_strength
        
        # Determine final signal
        threshold = 0.3  # Require at least 30% weighted agreement (reduzido de 40%)
        
        if buy_score > sell_score and buy_score > threshold:
            return 'BUY', buy_score
        elif sell_score > buy_score and sell_score > threshold:
            return 'SELL', sell_score
        else:
            return 'HOLD', 0.0


class StrategyFactory:
    """Factory for creating strategy instances"""
    
    @staticmethod
    def create_strategy(strategy_name: str, **kwargs) -> BaseStrategy:
        """
        Create strategy instance by name
        
        Args:
            strategy_name: Name of strategy to create
            **kwargs: Additional parameters for strategy
            
        Returns:
            Strategy instance
        """
        strategies = {
            'mean_reversion': MeanReversionStrategy,
            'breakout': BreakoutStrategy,
            'trend_following': TrendFollowingStrategy,
            'ensemble': EnsembleStrategy
        }
        
        strategy_class = strategies.get(strategy_name.lower())
        
        if not strategy_class:
            raise ValueError(
                f"Unknown strategy: {strategy_name}. "
                f"Available: {list(strategies.keys())}"
            )
        
        return strategy_class(**kwargs)


class MultiTimeframeAnalyzer:
    """Analyze signals across multiple timeframes"""
    
    def __init__(
        self,
        primary_timeframe: str,
        entry_timeframe: str,
        strategy: BaseStrategy
    ):
        """
        Initialize multi-timeframe analyzer
        
        Args:
            primary_timeframe: Primary trend timeframe (e.g., '4h')
            entry_timeframe: Entry signal timeframe (e.g., '1h')
            strategy: Strategy to use for analysis
        """
        self.primary_timeframe = primary_timeframe
        self.entry_timeframe = entry_timeframe
        self.strategy = strategy
        self.logger = logging.getLogger('TradingBot.MultiTimeframe')
    
    def analyze(
        self,
        primary_df: pd.DataFrame,
        entry_df: pd.DataFrame
    ) -> Tuple[str, float, Dict[str, any]]:
        """
        Analyze signals across timeframes
        
        Args:
            primary_df: OHLCV data for primary timeframe
            entry_df: OHLCV data for entry timeframe
            
        Returns:
            Tuple of (signal, strength, metadata)
        """
        # Get primary trend
        primary_signal, primary_strength = self.strategy.generate_signal(primary_df)
        
        # Get entry signal
        entry_signal, entry_strength = self.strategy.generate_signal(entry_df)
        
        # Only take trades aligned with primary trend
        if primary_signal == 'HOLD':
            return 'HOLD', 0.0, {
                'primary_signal': primary_signal,
                'entry_signal': entry_signal,
                'reason': 'No primary trend'
            }
        
        if entry_signal == primary_signal:
            # Signals aligned - combine strengths
            combined_strength = (primary_strength * 0.6 + entry_strength * 0.4)
            
            self.logger.info(
                f"Aligned signals: {primary_signal} "
                f"(Primary: {primary_strength:.2f}, Entry: {entry_strength:.2f})"
            )
            
            return entry_signal, combined_strength, {
                'primary_signal': primary_signal,
                'primary_strength': primary_strength,
                'entry_signal': entry_signal,
                'entry_strength': entry_strength,
                'aligned': True
            }
        else:
            # Signals not aligned - wait
            return 'HOLD', 0.0, {
                'primary_signal': primary_signal,
                'entry_signal': entry_signal,
                'reason': 'Signals not aligned'
            }
    
    def get_atr(self, df: pd.DataFrame, period: int = 14) -> Decimal:
        """
        Get Average True Range from DataFrame
        
        Args:
            df: OHLCV DataFrame
            period: ATR period
            
        Returns:
            ATR value as Decimal
        """
        atr = ta.volatility.AverageTrueRange(
            high=df['high'],
            low=df['low'],
            close=df['close'],
            window=period
        ).average_true_range()
        
        if len(atr) > 0 and not pd.isna(atr.iloc[-1]):
            return Decimal(str(atr.iloc[-1]))
        else:
            return Decimal('0')