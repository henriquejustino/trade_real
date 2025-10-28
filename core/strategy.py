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
        rsi_oversold: float = 35,  # 35 ao invés de 30 (mais sinais)
        rsi_overbought: float = 65  # 65 ao invés de 70 (mais sinais)
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

        # Proximity: se preço chega perto da banda (1% dentro) ou RSI próximo do oversold
        prox_buy = close <= bb_lower * 1.01 or rsi < self.rsi_oversold
        prox_sell = close >= bb_upper * 0.99 or rsi > self.rsi_overbought

        # Confirmation: candle fechou com+ (simples confirmação)
        confirm_buy = close > prev_close
        confirm_sell = close < prev_close

        if prox_buy:
            base_strength = min(1.0, (self.rsi_oversold - rsi) / 20 if rsi < self.rsi_oversold else 0.25)
            # aumenta se houver confirmação de candle
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
        lookback_period: int = 15,  # 15 ao invés de 20 (mais sinais)
        volume_threshold: float = 1.3  # 1.3 ao invés de 1.5 (mais permissivo)
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

        # Allow micro-breakout (close slightly above or equal to dc_upper) and slightly relaxed volume
        breakout_ok = (close > dc_upper * 0.999) and (volume_ratio > self.volume_threshold * 0.85)
        breakdown_ok = (close < dc_lower * 1.001) and (volume_ratio > self.volume_threshold * 0.85)

        # require movement at least some fraction of ATR to reduce whipsaw
        if breakout_ok and not pd.isna(atr):
            if (close - dc_upper) >= 0.25 * atr:
                breakout_pct = (close - dc_upper) / dc_upper
                strength = min(1.0, 0.5 + min(0.5, breakout_pct * 50))
                return 'BUY', strength
            # retest filter: if prev_close closed above dc_upper, prefer that
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
        trend_strength = min(1.0, adx / 50) if adx > 18 else 0.5
        
        # Allow cross even if close slightly below trend EMA (capture early trend)
        trend_floor = ema_trend * 0.995  # 0.5% abaixo ainda OK

        if (ema_fast > ema_slow and prev_ema_fast <= prev_ema_slow and
            close > trend_floor and macd > macd_signal):
            return 'BUY', trend_strength
        
        # Sell signal: bearish cross below trend line
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

        # Ajustes de pesos (default e agressivo)
        if aggressive:
            self.weights = weights or {
                'mean_reversion': 0.15,
                'breakout': 0.5,
                'trend_following': 0.35
            }
            # limiar padrão (full) e limiar baixo (para entradas parciais)
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

        # Normalize weights
        total_weight = sum(self.weights.values())
        self.weights = {k: v / total_weight for k, v in self.weights.items()}

        # Minimum bars needed: reduzido para não travar (antes era 200)
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

        self.logger.debug(f"Buy score: {buy_score:.3f}, Sell score: {sell_score:.3f}, Threshold: {self.threshold:.3f}, Low: {getattr(self,'threshold_low',None)}")

        # regra 1: full entry quando score > threshold
        if buy_score > sell_score and buy_score >= self.threshold:
            return 'BUY', buy_score
        if sell_score > buy_score and sell_score >= self.threshold:
            return 'SELL', sell_score

        # regra 2: parcial se score >= threshold_low AND pelo menos 2 estratégias votaram a favor
        if buy_score > sell_score and buy_score >= self.threshold_low and votes['buy'] >= 2:
            # devolve sinal com força reduzida para indicar entrada parcial
            return 'BUY', buy_score * 0.9
        if sell_score > buy_score and sell_score >= self.threshold_low and votes['sell'] >= 2:
            return 'SELL', sell_score * 0.9

        # regra 3: se apenas uma estratégia forte (breakout forte), permitir se strength alta
        # pega caso em que breakout faz a diferença mas os outros estão HOLD
        breakout_sig, breakout_str = signals.get('breakout', ('HOLD', 0.0))
        if breakout_sig in ['BUY','SELL'] and breakout_str > 0.85:
            return breakout_sig, breakout_str * self.weights.get('breakout', 0.4)

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
            # NOVO: Ensemble Ultra com indicadores mais sensíveis
            'ensemble_ultra': lambda **kw: EnsembleStrategy(
                aggressive=True,
                weights={'mean_reversion': 0.15, 'breakout': 0.6, 'trend_following': 0.25},
                **kw
            ),
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
        require_alignment: bool = True  # Novo parâmetro
    ):
        """
        Initialize multi-timeframe analyzer
        
        Args:
            primary_timeframe: Primary trend timeframe (e.g., '4h')
            entry_timeframe: Entry signal timeframe (e.g., '1h')
            strategy: Strategy to use for analysis
            require_alignment: Se True, exige alinhamento perfeito (conservador)
                              Se False, permite trades mesmo sem alinhamento (agressivo)
        """
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
        
        # Modo AGRESSIVO (require_alignment = False)
        else:
            # Prioriza sinal do entry timeframe, mas considera o primary
            if entry_signal in ['BUY', 'SELL']:
                # Se entry tem sinal, usar ele
                # Boost strength se alinhado com primary
                if entry_signal == primary_signal:
                    combined_strength = (primary_strength * 0.6 + entry_strength * 0.4)
                    self.logger.info(
                        f"Aligned signals (aggressive): {entry_signal} "
                        f"(Primary: {primary_strength:.2f}, Entry: {entry_strength:.2f})"
                    )
                else:
                    # Usa entry mesmo sem alinhamento, mas com strength reduzida
                    combined_strength = entry_strength * 0.7  # Penalidade de 30%
                    self.logger.info(
                        f"Non-aligned signal (aggressive): Entry={entry_signal}({entry_strength:.2f}), "
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
                    f"Using primary signal (aggressive): {primary_signal} ({primary_strength:.2f})"
                )
                return primary_signal, primary_strength * 0.8, {  # Penalidade por usar só primary
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