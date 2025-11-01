import logging
from typing import Optional, Dict, Tuple
from decimal import Decimal
import pandas as pd
import numpy as np
import ta


class MeanReversionStrategy:
    """Mean reversion strategy using Bollinger Bands and RSI for swing"""
    
    def __init__(
        self,
        bb_period: int = 20,
        bb_std: float = 2.0,
        rsi_period: int = 14,
        rsi_oversold: float = 35,
        rsi_overbought: float = 65
    ):
        self.name = "MeanReversion"
        self.logger = logging.getLogger(f'TradingBot.Strategy.{self.name}')
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
    
    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add Bollinger Bands and RSI"""
        df = df.copy()
        
        bb = ta.volatility.BollingerBands(close=df['close'], window=self.bb_period, window_dev=self.bb_std)
        df['bb_upper'] = bb.bollinger_hband()
        df['bb_middle'] = bb.bollinger_mavg()
        df['bb_lower'] = bb.bollinger_lband()
        df['bb_width'] = bb.bollinger_wband()
        
        df['rsi'] = ta.momentum.RSIIndicator(close=df['close'], window=self.rsi_period).rsi()
        
        return df
    
    def generate_signal(self, df: pd.DataFrame) -> Tuple[str, float]:
        if len(df) < self.bb_period:
            return 'HOLD', 0.0

        df = self.add_indicators(df)

        close = df['close'].iloc[-1]
        prev_close = df['close'].iloc[-2]
        bb_upper = df['bb_upper'].iloc[-1]
        bb_lower = df['bb_lower'].iloc[-1]
        rsi = df['rsi'].iloc[-1]

        if pd.isna(rsi) or pd.isna(bb_lower):
            return 'HOLD', 0.0

        prox_buy = close <= bb_lower * 1.01 or rsi < self.rsi_oversold
        prox_sell = close >= bb_upper * 0.99 or rsi > self.rsi_overbought

        confirm_buy = close > prev_close
        confirm_sell = close < prev_close

        if prox_buy:
            base_strength = min(1.0, (self.rsi_oversold - rsi) / 20 if rsi < self.rsi_oversold else 0.25)
            strength = min(1.0, base_strength + (0.2 if confirm_buy else 0.0))
            return 'BUY', strength

        if prox_sell:
            base_strength = min(1.0, (rsi - self.rsi_overbought) / 20 if rsi > self.rsi_overbought else 0.25)
            strength = min(1.0, base_strength + (0.2 if confirm_sell else 0.0))
            return 'SELL', strength

        return 'HOLD', 0.0


class BreakoutStrategy:
    """Breakout strategy using Donchian Channels and volume for swing"""
    
    def __init__(
        self,
        lookback_period: int = 15,
        volume_threshold: float = 1.3
    ):
        self.name = "Breakout"
        self.logger = logging.getLogger(f'TradingBot.Strategy.{self.name}')
        self.lookback_period = lookback_period
        self.volume_threshold = volume_threshold
    
    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add Donchian Channels and volume indicators"""
        df = df.copy()
        
        df['dc_upper'] = df['high'].rolling(window=self.lookback_period).max()
        df['dc_lower'] = df['low'].rolling(window=self.lookback_period).min()
        df['dc_middle'] = (df['dc_upper'] + df['dc_lower']) / 2
        
        df['volume_ma'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma']
        
        df['atr'] = ta.volatility.AverageTrueRange(high=df['high'], low=df['low'], close=df['close'], window=14).average_true_range()
        
        return df
    
    def generate_signal(self, df: pd.DataFrame) -> Tuple[str, float]:
        if len(df) < self.lookback_period + 2:
            return 'HOLD', 0.0

        df = self.add_indicators(df)

        close = df['close'].iloc[-1]
        prev_close = df['close'].iloc[-2]
        dc_upper = df['dc_upper'].iloc[-2]
        dc_lower = df['dc_lower'].iloc[-2]
        volume_ratio = df['volume_ratio'].iloc[-1]
        atr = df['atr'].iloc[-1] if 'atr' in df.columns else np.nan

        if pd.isna(dc_upper) or pd.isna(volume_ratio):
            return 'HOLD', 0.0

        breakout_ok = (close > dc_upper * 0.999) and (volume_ratio > self.volume_threshold * 0.85)
        breakdown_ok = (close < dc_lower * 1.001) and (volume_ratio > self.volume_threshold * 0.85)

        if breakout_ok and not pd.isna(atr):
            if (close - dc_upper) >= 0.25 * atr:
                breakout_pct = (close - dc_upper) / dc_upper
                strength = min(1.0, 0.5 + min(0.5, breakout_pct * 50))
                return 'BUY', strength
            if prev_close > dc_upper:
                return 'BUY', min(1.0, volume_ratio / (self.volume_threshold or 1.0) * 0.6)

        if breakdown_ok and not pd.isna(atr):
            if (dc_lower - close) >= 0.25 * atr:
                breakdown_pct = (dc_lower - close) / dc_lower
                strength = min(1.0, 0.5 + min(0.5, breakdown_pct * 50))
                return 'SELL', strength
            if prev_close < dc_lower:
                return 'SELL', min(1.0, volume_ratio / (self.volume_threshold or 1.0) * 0.6)

        return 'HOLD', 0.0


class TrendFollowingStrategy:
    """Trend following strategy using EMA crossover and MACD for swing"""
    
    def __init__(
        self,
        fast_ema: int = 12,
        slow_ema: int = 26,
        signal_ema: int = 9,
        trend_ema: int = 150
    ):
        self.name = "TrendFollowing"
        self.logger = logging.getLogger(f'TradingBot.Strategy.{self.name}')
        self.fast_ema = fast_ema
        self.slow_ema = slow_ema
        self.signal_ema = signal_ema
        self.trend_ema = trend_ema
    
    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add EMA and MACD indicators"""
        df = df.copy()
        
        df['ema_fast'] = ta.trend.EMAIndicator(close=df['close'], window=self.fast_ema).ema_indicator()
        df['ema_slow'] = ta.trend.EMAIndicator(close=df['close'], window=self.slow_ema).ema_indicator()
        df['ema_trend'] = ta.trend.EMAIndicator(close=df['close'], window=self.trend_ema).ema_indicator()
        
        macd = ta.trend.MACD(close=df['close'], window_fast=self.fast_ema, window_slow=self.slow_ema, window_sign=self.signal_ema)
        df['macd'] = macd.macd()
        df['macd_signal'] = macd.macd_signal()
        df['macd_diff'] = macd.macd_diff()
        
        adx = ta.trend.ADXIndicator(high=df['high'], low=df['low'], close=df['close'], window=14)
        df['adx'] = adx.adx()
        
        return df
    
    def generate_signal(self, df: pd.DataFrame) -> Tuple[str, float]:
        """Generate trend following signal"""
        if len(df) < self.trend_ema:
            return 'HOLD', 0.0
        
        df = self.add_indicators(df)
        
        close = df['close'].iloc[-1]
        ema_fast = df['ema_fast'].iloc[-1]
        ema_slow = df['ema_slow'].iloc[-1]
        ema_trend = df['ema_trend'].iloc[-1]
        macd = df['macd'].iloc[-1]
        macd_signal = df['macd_signal'].iloc[-1]
        adx = df['adx'].iloc[-1]
        
        prev_ema_fast = df['ema_fast'].iloc[-2]
        prev_ema_slow = df['ema_slow'].iloc[-2]
        
        if pd.isna(ema_fast) or pd.isna(adx):
            return 'HOLD', 0.0
        
        trend_strength = min(1.0, adx / 50) if adx > 18 else 0.5
        trend_floor = ema_trend * 0.995

        if (ema_fast > ema_slow and prev_ema_fast <= prev_ema_slow and
            close > trend_floor and macd > macd_signal):
            return 'BUY', trend_strength
        
        if (ema_fast < ema_slow and prev_ema_fast >= prev_ema_slow and
            close < ema_trend and macd < macd_signal):
            return 'SELL', trend_strength
        
        return 'HOLD', 0.0


class EnsembleStrategy:
    """Ensemble combining all swing strategies"""
    
    def __init__(self, weights: Optional[Dict[str, float]] = None, aggressive: bool = False):
        self.name = "Ensemble"
        self.logger = logging.getLogger(f'TradingBot.Strategy.{self.name}')
        
        self.strategies = {
            'mean_reversion': MeanReversionStrategy(),
            'breakout': BreakoutStrategy(),
            'trend_following': TrendFollowingStrategy()
        }

        if aggressive:
            self.weights = weights or {'mean_reversion': 0.15, 'breakout': 0.5, 'trend_following': 0.35}
            self.threshold = 0.24
            self.threshold_low = 0.16
        else:
            self.weights = weights or {'mean_reversion': 0.25, 'breakout': 0.35, 'trend_following': 0.4}
            self.threshold = 0.20
            self.threshold_low = 0.12

        total_weight = sum(self.weights.values())
        self.weights = {k: v / total_weight for k, v in self.weights.items()}

        self.min_bars = max(50, max(s.trend_ema if hasattr(s, 'trend_ema') else 0 for s in self.strategies.values()))

    
    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add all indicators from sub-strategies"""
        df = df.copy()
        
        for strategy in self.strategies.values():
            df = strategy.add_indicators(df)
        
        return df
    
    def generate_signal(self, df: pd.DataFrame) -> Tuple[str, float]:
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
            return 'BUY', buy_score * 0.9
        if sell_score > buy_score and sell_score >= self.threshold_low and votes['sell'] >= 2:
            return 'SELL', sell_score * 0.9

        breakout_sig, breakout_str = signals.get('breakout', ('HOLD', 0.0))
        if breakout_sig in ['BUY','SELL'] and breakout_str > 0.85:
            return breakout_sig, breakout_str * self.weights.get('breakout', 0.4)

        return 'HOLD', 0.0