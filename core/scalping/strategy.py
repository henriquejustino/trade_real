"""
Scalping trading strategies (5m/15m timeframes)
Fast strategies for quick entries and exits
COPY THIS FILE TO: core/scalping/strategy.py
"""

import logging
from typing import Tuple
from decimal import Decimal
import pandas as pd
import numpy as np
import ta


class ScalpingMeanReversionStrategy:
    """Mean reversion strategy optimized for scalping (5m/15m)"""
    
    def __init__(
        self,
        bb_period: int = 14,
        bb_std: float = 2.0,
        rsi_period: int = 7,
        rsi_oversold: float = 45,
        rsi_overbought: float = 55
    ):
        self.name = "ScalpingMeanReversion"
        self.logger = logging.getLogger(f'TradingBot.Strategy.{self.name}')
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
    
    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add indicators for scalping"""
        df = df.copy()
        
        # Bollinger Bands (shorter period)
        bb = ta.volatility.BollingerBands(
            close=df['close'],
            window=self.bb_period,
            window_dev=self.bb_std
        )
        df['bb_upper'] = bb.bollinger_hband()
        df['bb_middle'] = bb.bollinger_mavg()
        df['bb_lower'] = bb.bollinger_lband()
        df['bb_width'] = bb.bollinger_wband()
        
        # Fast RSI
        df['rsi'] = ta.momentum.RSIIndicator(
            close=df['close'],
            window=self.rsi_period
        ).rsi()
        
        # Stochastic for additional confirmation
        stoch = ta.momentum.StochasticOscillator(
            high=df['high'],
            low=df['low'],
            close=df['close'],
            window=7,
            smooth_window=3
        )
        df['stoch_k'] = stoch.stoch()
        df['stoch_d'] = stoch.stoch_signal()
        
        return df
    
    def generate_signal(self, df: pd.DataFrame) -> Tuple[str, float]:
        """Generate scalping signal"""
        if len(df) < self.bb_period:
            return 'HOLD', 0.0
        
        df = self.add_indicators(df)
        
        close = df['close'].iloc[-1]
        prev_close = df['close'].iloc[-2]
        bb_upper = df['bb_upper'].iloc[-1]
        bb_lower = df['bb_lower'].iloc[-1]
        rsi = df['rsi'].iloc[-1]
        stoch_k = df['stoch_k'].iloc[-1]
        
        if pd.isna(rsi) or pd.isna(stoch_k):
            return 'HOLD', 0.0
        
        # BUY Signal
        if close <= bb_lower * 1.05 and rsi < self.rsi_oversold and stoch_k < 30:
            strength = min(1.0, 0.3 + (self.rsi_oversold - rsi) / 30 + (20 - stoch_k) / 20 * 0.2)
            if close > prev_close:
                strength = min(1.0, strength + 0.15)
            return 'BUY', strength
        
        # SELL Signal
        if close >= bb_upper * 0.98 and rsi > self.rsi_overbought and stoch_k > 80:
            strength = min(1.0, 0.3 + (rsi - self.rsi_overbought) / 30 + (stoch_k - 80) / 20 * 0.2)
            if close < prev_close:
                strength = min(1.0, strength + 0.15)
            return 'SELL', strength
        
        return 'HOLD', 0.0


class ScalpingBreakoutStrategy:
    """Micro-breakout strategy for scalping (5m/15m)"""
    
    def __init__(
        self,
        lookback_period: int = 8,
        volume_threshold: float = 0.9
    ):
        self.name = "ScalpingBreakout"
        self.logger = logging.getLogger(f'TradingBot.Strategy.{self.name}')
        self.lookback_period = lookback_period
        self.volume_threshold = volume_threshold
    
    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add indicators for breakout scalping"""
        df = df.copy()
        
        # Tight Donchian Channels
        df['dc_upper'] = df['high'].rolling(window=self.lookback_period).max()
        df['dc_lower'] = df['low'].rolling(window=self.lookback_period).min()
        
        # Volume analysis
        df['volume_ma'] = df['volume'].rolling(window=15).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma']
        
        # Volatility (fast ATR)
        df['atr'] = ta.volatility.AverageTrueRange(
            high=df['high'],
            low=df['low'],
            close=df['close'],
            window=7
        ).average_true_range()
        
        # Momentum for confirmation
        df['momentum'] = df['close'] - df['close'].shift(3)
        
        return df
    
    def generate_signal(self, df: pd.DataFrame) -> Tuple[str, float]:
        """Generate breakout signal for scalping"""
        if len(df) < self.lookback_period + 2:
            return 'HOLD', 0.0
        
        df = self.add_indicators(df)
        
        close = df['close'].iloc[-1]
        prev_close = df['close'].iloc[-2]
        dc_upper = df['dc_upper'].iloc[-2]
        dc_lower = df['dc_lower'].iloc[-2]
        volume_ratio = df['volume_ratio'].iloc[-1]
        atr = df['atr'].iloc[-1]
        momentum = df['momentum'].iloc[-1]
        
        if pd.isna(dc_upper) or pd.isna(volume_ratio) or pd.isna(atr):
            return 'HOLD', 0.0
        
        # Upside breakout
        if close > dc_upper * 0.998 and volume_ratio > self.volume_threshold * 0.8 and momentum > 0:
            breakout_size = close - dc_upper
            strength = min(0.9, 0.4 + (volume_ratio / self.volume_threshold) * 0.3 + min(0.2, breakout_size / (atr or 1)))
            return 'BUY', strength
        
        # Downside breakdown
        if close < dc_lower and volume_ratio > self.volume_threshold and momentum < 0:
            breakdown_size = dc_lower - close
            strength = min(0.9, 0.4 + (volume_ratio / self.volume_threshold) * 0.3 + min(0.2, breakdown_size / (atr or 1)))
            return 'SELL', strength
        
        return 'HOLD', 0.0


class ScalpingMomentumStrategy:
    """Fast momentum strategy using MACD and moving averages for scalping"""
    
    def __init__(
        self,
        fast_ema: int = 7,
        slow_ema: int = 14,
        signal_ema: int = 5
    ):
        self.name = "ScalpingMomentum"
        self.logger = logging.getLogger(f'TradingBot.Strategy.{self.name}')
        self.fast_ema = fast_ema
        self.slow_ema = slow_ema
        self.signal_ema = signal_ema
    
    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add momentum indicators"""
        df = df.copy()
        
        # Fast EMAs
        df['ema_fast'] = ta.trend.EMAIndicator(close=df['close'], window=self.fast_ema).ema_indicator()
        df['ema_slow'] = ta.trend.EMAIndicator(close=df['close'], window=self.slow_ema).ema_indicator()
        
        # MACD (very fast)
        macd = ta.trend.MACD(close=df['close'], window_fast=self.fast_ema, window_slow=self.slow_ema, window_sign=self.signal_ema)
        df['macd'] = macd.macd()
        df['macd_signal'] = macd.macd_signal()
        
        # Price velocity
        df['velocity'] = df['close'].pct_change() * 100
        
        return df
    
    def generate_signal(self, df: pd.DataFrame) -> Tuple[str, float]:
        """Generate momentum signal"""
        if len(df) < max(self.fast_ema, self.slow_ema) + 2:
            return 'HOLD', 0.0
        
        df = self.add_indicators(df)
        
        ema_fast = df['ema_fast'].iloc[-1]
        ema_slow = df['ema_slow'].iloc[-1]
        prev_ema_fast = df['ema_fast'].iloc[-2]
        prev_ema_slow = df['ema_slow'].iloc[-2]
        macd = df['macd'].iloc[-1]
        macd_signal = df['macd_signal'].iloc[-1]
        velocity = df['velocity'].iloc[-1]
        
        if pd.isna(ema_fast) or pd.isna(macd):
            return 'HOLD', 0.0
        
        # Golden cross: EMA 7 crosses above EMA 14
        if prev_ema_fast <= prev_ema_slow and ema_fast > ema_slow and macd > macd_signal:
            strength = min(1.0, 0.5 + abs(velocity) / 50)
            return 'BUY', strength
        
        # Death cross: EMA 7 crosses below EMA 14
        if prev_ema_fast >= prev_ema_slow and ema_fast < ema_slow and macd < macd_signal:
            strength = min(1.0, 0.5 + abs(velocity) / 50)
            return 'SELL', strength
        
        return 'HOLD', 0.0


class ScalpingEnsembleStrategy:
    """Ensemble combining all three scalping strategies"""
    
    def __init__(self):
        self.name = "ScalpingEnsemble"
        self.logger = logging.getLogger(f'TradingBot.Strategy.{self.name}')
        
        self.strategies = {
            'mean_reversion': ScalpingMeanReversionStrategy(),
            'breakout': ScalpingBreakoutStrategy(),
            'momentum': ScalpingMomentumStrategy()
        }
        
        self.weights = {'mean_reversion': 0.35, 'breakout': 0.25, 'momentum': 0.40}
        self.threshold = 0.20
        self.threshold_low = 0.12
        self.min_bars = 20
    
    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add all indicators"""
        df = df.copy()
        for strategy in self.strategies.values():
            df = strategy.add_indicators(df)
        return df
    
    def generate_signal(self, df: pd.DataFrame) -> Tuple[str, float]:
        """Generate ensemble signal"""
        if len(df) < self.min_bars:
            return 'HOLD', 0.0
        
        signals = {}
        for name, strategy in self.strategies.items():
            signal, strength = strategy.generate_signal(df)
            signals[name] = (signal, strength)
        
        buy_score = 0.0
        sell_score = 0.0
        votes = {'buy': 0, 'sell': 0}
        
        for name, (signal, strength) in signals.items():
            weight = self.weights[name]
            weighted_strength = strength * weight
            
            if signal == 'BUY':
                buy_score += weighted_strength
                votes['buy'] += 1
            elif signal == 'SELL':
                sell_score += weighted_strength
                votes['sell'] += 1
        
        if buy_score > sell_score and buy_score >= self.threshold:
            return 'BUY', buy_score
        
        if sell_score > buy_score and sell_score >= self.threshold:
            return 'SELL', sell_score
        
        if buy_score > sell_score and buy_score >= self.threshold_low and votes['buy'] >= 2:
            return 'BUY', buy_score * 0.85
        
        if sell_score > buy_score and sell_score >= self.threshold_low and votes['sell'] >= 2:
            return 'SELL', sell_score * 0.85
        
        return 'HOLD', 0.0