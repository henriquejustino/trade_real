import logging
from typing import Optional, Dict, Tuple
from decimal import Decimal
import pandas as pd
import numpy as np
import ta


class BaseStrategy:
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f'TradingBot.Strategy.{name}')
    
    def generate_signal(self, df: pd.DataFrame) -> Tuple[str, float]:

        raise NotImplementedError("Subclasses must implement generate_signal")
    
    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:

        raise NotImplementedError("Subclasses must implement add_indicators")


class MeanReversionStrategy(BaseStrategy):
    """Mean reversion strategy using Bollinger Bands and RSI"""
    
    def __init__(
        self,
        bb_period: int = 20,
        bb_std: float = 2.0,
        rsi_period: int = 14,
        rsi_oversold: float = 35,
        rsi_overbought: float = 65
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


class BreakoutStrategy(BaseStrategy):
    """Breakout strategy using Donchian Channels and volume"""
    
    def __init__(
        self,
        lookback_period: int = 15,
        volume_threshold: float = 1.3
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


class TrendFollowingStrategy(BaseStrategy):
    """Trend following strategy using EMA crossover and MACD"""
    
    def __init__(
        self,
        fast_ema: int = 12,
        slow_ema: int = 26,
        signal_ema: int = 9,
        trend_ema: int = 150
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


class EnsembleStrategy(BaseStrategy):
    def __init__(self, weights: Optional[Dict[str, float]] = None, aggressive: bool = False):
        super().__init__("Ensemble")
        self.strategies = {
            'mean_reversion': MeanReversionStrategy(),
            'breakout': BreakoutStrategy(),
            'trend_following': TrendFollowingStrategy()
        }

        if aggressive:
            self.weights = weights or {
                'mean_reversion': 0.15,
                'breakout': 0.5,
                'trend_following': 0.35
            }
            self.threshold = 0.24
            self.threshold_low = 0.16
        else:
            self.weights = weights or {
                'mean_reversion': 0.25,
                'breakout': 0.35,
                'trend_following': 0.4
            }
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
            self.logger.debug(f"{name}: {signal} ({strength:.2f})")

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

        self.logger.debug(f"Buy score: {buy_score:.3f}, Sell score: {sell_score:.3f}, Threshold: {self.threshold:.3f}")

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

class ScalpingMeanReversionStrategy:
    """Estratégia de mean reversion rápida para scalping (5m/15m)"""
    
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
        stoch_d = df['stoch_d'].iloc[-1]
        
        if pd.isna(rsi) or pd.isna(stoch_k):
            return 'HOLD', 0.0
        
        # BUY Signal: Touch lower band + RSI oversold + Stoch below 20
        if (close <= bb_lower * 1.05 and 
            rsi < self.rsi_oversold and 
            stoch_k < 30):
            
            strength = min(1.0, 0.3 + 
                          (self.rsi_oversold - rsi) / 30 +
                          (20 - stoch_k) / 20 * 0.2)
            
            if close > prev_close:
                strength = min(1.0, strength + 0.15)
            
            return 'BUY', strength
        
        # SELL Signal: Touch upper band + RSI overbought + Stoch above 80
        if (close >= bb_upper * 0.98 and 
            rsi > self.rsi_overbought and 
            stoch_k > 80):
            
            strength = min(1.0, 0.3 + 
                          (rsi - self.rsi_overbought) / 30 +
                          (stoch_k - 80) / 20 * 0.2)
            
            if close < prev_close:
                strength = min(1.0, strength + 0.15)
            
            return 'SELL', strength
        
        return 'HOLD', 0.0


class ScalpingBreakoutStrategy:
    """Micro-breakout strategy for scalping (5m/15m)"""
    
    def __init__(
        self,
        lookback_period: int = 8,
        volume_threshold: float = 0.9,
        min_breakout_pct: float = 0.001
    ):
        self.name = "ScalpingBreakout"
        self.logger = logging.getLogger(f'TradingBot.Strategy.{self.name}')
        self.lookback_period = lookback_period
        self.volume_threshold = volume_threshold
        self.min_breakout_pct = min_breakout_pct
    
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
        df['momentum_ma'] = df['momentum'].rolling(3).mean()
        
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
        if (close > dc_upper * 0.998 and 
            volume_ratio > self.volume_threshold * 0.8 and
            momentum > 0):
            
            breakout_size = close - dc_upper
            strength = min(0.9, 0.4 + 
                          (volume_ratio / self.volume_threshold) * 0.3 +
                          min(0.2, breakout_size / (atr or 1)))
            
            return 'BUY', strength
        
        # Downside breakdown
        if (close < dc_lower and 
            volume_ratio > self.volume_threshold and
            momentum < 0):
            
            breakdown_size = dc_lower - close
            strength = min(0.9, 0.4 + 
                          (volume_ratio / self.volume_threshold) * 0.3 +
                          min(0.2, breakdown_size / (atr or 1)))
            
            return 'SELL', strength
        
        return 'HOLD', 0.0


class ScalpingMomentumStrategy:
    """Fast momentum strategy using MACD and moving averages"""
    
    def __init__(
        self,
        fast_ema: int = 7,
        slow_ema: int = 14,
        signal_ema: int = 5,
        threshold: float = 0.0
    ):
        self.name = "ScalpingMomentum"
        self.logger = logging.getLogger(f'TradingBot.Strategy.{self.name}')
        self.fast_ema = fast_ema
        self.slow_ema = slow_ema
        self.signal_ema = signal_ema
        self.threshold = threshold
    
    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add momentum indicators"""
        df = df.copy()
        
        # Fast EMAs
        df['ema_fast'] = ta.trend.EMAIndicator(
            close=df['close'],
            window=self.fast_ema
        ).ema_indicator()
        
        df['ema_slow'] = ta.trend.EMAIndicator(
            close=df['close'],
            window=self.slow_ema
        ).ema_indicator()
        
        # MACD (very fast)
        macd = ta.trend.MACD(
            close=df['close'],
            window_fast=self.fast_ema,
            window_slow=self.slow_ema,
            window_sign=self.signal_ema
        )
        df['macd'] = macd.macd()
        df['macd_signal'] = macd.macd_signal()
        df['macd_diff'] = macd.macd_diff()
        
        # Price velocity
        df['velocity'] = df['close'].pct_change() * 100
        df['velocity_ma'] = df['velocity'].rolling(3).mean()
        
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
        prev_macd = df['macd'].iloc[-2]
        prev_macd_signal = df['macd_signal'].iloc[-2]
        
        velocity = df['velocity'].iloc[-1]
        
        if pd.isna(ema_fast) or pd.isna(macd):
            return 'HOLD', 0.0
        
        # Golden cross: EMA 7 crosses above EMA 14
        if (prev_ema_fast <= prev_ema_slow and 
            ema_fast > ema_slow and
            macd > macd_signal):
            
            strength = min(1.0, 0.5 + abs(velocity) / 50)
            return 'BUY', strength
        
        # Death cross: EMA 7 crosses below EMA 14
        if (prev_ema_fast >= prev_ema_slow and 
            ema_fast < ema_slow and
            macd < macd_signal):
            
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
        
        # Weights (momentum gets highest for scalping)
        self.weights = {
            'mean_reversion': 0.35,
            'breakout': 0.25,
            'momentum': 0.40
        }
        
        # Lower thresholds for scalping (more signals)
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
            self.logger.debug(f"{name}: {signal} ({strength:.2f})")
        
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
        
        self.logger.debug(f"Buy: {buy_score:.3f}, Sell: {sell_score:.3f}, Threshold: {self.threshold:.3f}")
        
        # Aggressive entry for scalping
        if buy_score > sell_score and buy_score >= self.threshold:
            return 'BUY', buy_score
        
        if sell_score > buy_score and sell_score >= self.threshold:
            return 'SELL', sell_score
        
        # Partial signals
        if buy_score > sell_score and buy_score >= self.threshold_low and votes['buy'] >= 2:
            return 'BUY', buy_score * 0.85
        
        if sell_score > buy_score and sell_score >= self.threshold_low and votes['sell'] >= 2:
            return 'SELL', sell_score * 0.85
        
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
            'ensemble': EnsembleStrategy,
            'ensemble_aggressive': lambda **kw: EnsembleStrategy(aggressive=True, **kw),
            'scalping_ensemble': lambda **kw: ScalpingEnsembleStrategy(**kw),
            'scalping_ensemble_ultra': lambda **kw: ScalpingEnsembleStrategy(**kw),
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
        strategy: BaseStrategy,
        require_alignment: bool = True
    ):
        self.primary_timeframe = primary_timeframe
        self.entry_timeframe = entry_timeframe
        self.strategy = strategy
        self.require_alignment = require_alignment
        self.logger = logging.getLogger('TradingBot.MultiTimeframe')
    
    def analyze(
        self,
        primary_df: pd.DataFrame,
        entry_df: pd.DataFrame
    ) -> Tuple[str, float, Dict[str, any]]:
        
        if primary_df.empty:
            self.logger.warning("Primary DataFrame is empty!")
            return 'HOLD', 0.0, {'reason': 'Empty primary DataFrame'}
        
        if entry_df.empty:
            self.logger.warning("Entry DataFrame is empty!")
            return 'HOLD', 0.0, {'reason': 'Empty entry DataFrame'}
        
        # 🔴 VALIDAÇÃO: Timestamps sincronizados
        primary_latest = primary_df.index[-1]
        entry_latest = entry_df.index[-1]
        
        time_diff = (primary_latest - entry_latest).total_seconds() / 3600
        
        if time_diff > 2:
            self.logger.warning(
                f"⚠️ Large timestamp difference: primary={primary_latest}, entry={entry_latest}"
            )
        
        # Get primary trend
        try:
            primary_signal, primary_strength = self.strategy.generate_signal(primary_df)
        except Exception as e:
            self.logger.error(f"Error generating primary signal: {e}", exc_info=True)
            return 'HOLD', 0.0, {'reason': f'Primary signal error: {str(e)}'}
        
        # Get entry signal
        try:
            entry_signal, entry_strength = self.strategy.generate_signal(entry_df)
        except Exception as e:
            self.logger.error(f"Error generating entry signal: {e}", exc_info=True)
            return 'HOLD', 0.0, {'reason': f'Entry signal error: {str(e)}'}
        
        # Modo CONSERVADOR (require_alignment = True)
        if self.require_alignment:
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
                    f"✅ Aligned signals: {primary_signal} "
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
        
        # Modo AGRESSIVO (require_alignment = False)
        else:
            # Prioriza sinal do entry timeframe, mas considera o primary
            if entry_signal in ['BUY', 'SELL']:
                if entry_signal == primary_signal:
                    combined_strength = (primary_strength * 0.6 + entry_strength * 0.4)
                    self.logger.info(
                        f"✅ Aligned signals (aggressive): {entry_signal} "
                        f"(Primary: {primary_strength:.2f}, Entry: {entry_strength:.2f})"
                    )
                else:
                    # Usa entry mesmo sem alinhamento, mas com strength reduzida
                    combined_strength = entry_strength * 0.7
                    self.logger.info(
                        f"⚠️ Non-aligned signal (aggressive): Entry={entry_signal}({entry_strength:.2f}), "
                        f"Primary={primary_signal}({primary_strength:.2f}) - Using entry with penalty"
                    )
                
                return entry_signal, combined_strength, {
                    'primary_signal': primary_signal,
                    'primary_strength': primary_strength,
                    'entry_signal': entry_signal,
                    'entry_strength': entry_strength,
                    'aligned': entry_signal == primary_signal,
                    'mode': 'aggressive'
                }
            
            # Se entry não tem sinal, tentar primary
            elif primary_signal in ['BUY', 'SELL']:
                self.logger.info(
                    f"ℹ️ Using primary signal (aggressive): {primary_signal} ({primary_strength:.2f})"
                )
                return primary_signal, primary_strength * 0.8, {
                    'primary_signal': primary_signal,
                    'primary_strength': primary_strength,
                    'entry_signal': entry_signal,
                    'reason': 'Using primary timeframe signal',
                    'mode': 'aggressive'
                }
            
            return 'HOLD', 0.0, {
                'primary_signal': primary_signal,
                'entry_signal': entry_signal,
                'reason': 'No signals in any timeframe'
            }
    
    def get_atr(self, df: pd.DataFrame, period: int = 14) -> Decimal:

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