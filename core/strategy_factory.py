"""
COPY THIS FILE TO: core/strategy_factory.py
REPLACE the old one completely!
"""

import logging
from typing import Dict, Any


SCALPING_STRATEGIES = {
    'scalping_ensemble': 'ScalpingEnsembleStrategy',
    'scalping_mean_reversion': 'ScalpingMeanReversionStrategy',
    'scalping_breakout': 'ScalpingBreakoutStrategy',
    'scalping_momentum': 'ScalpingMomentumStrategy',
}

SWING_STRATEGIES = {
    'ensemble': 'EnsembleStrategy',
    'ensemble_aggressive': 'EnsembleStrategy',
    'mean_reversion': 'MeanReversionStrategy',
    'breakout': 'BreakoutStrategy',
    'trend_following': 'TrendFollowingStrategy',
}

MODE_MAP = {
    'scalping': SCALPING_STRATEGIES,
    'swing': SWING_STRATEGIES,
}


class StrategyFactory:
    """Factory for creating trading strategies based on mode"""
    
    logger = logging.getLogger('TradingBot.StrategyFactory')
    
    @staticmethod
    def get_available_strategies(mode: str) -> Dict[str, str]:
        """Get available strategies for a mode"""
        if mode not in MODE_MAP:
            raise ValueError(f"Unknown mode: {mode}. Available: {', '.join(MODE_MAP.keys())}")
        return MODE_MAP[mode].copy()
    
    @staticmethod
    def validate_strategy_for_mode(strategy_name: str, mode: str) -> bool:
        """Validate if strategy exists for given mode"""
        if mode not in MODE_MAP:
            raise ValueError(f"Unknown mode: {mode}. Available: {', '.join(MODE_MAP.keys())}")
        
        available = MODE_MAP[mode]
        
        if strategy_name not in available:
            available_list = ', '.join(available.keys())
            raise ValueError(
                f"Strategy '{strategy_name}' not available for {mode} mode.\n"
                f"Available: {available_list}"
            )
        
        return True
    
    @staticmethod
    def create_strategy(strategy_name: str, mode: str = 'swing', **kwargs):
        """Create a strategy instance for a specific mode"""
        logger = logging.getLogger('TradingBot.StrategyFactory')
        
        if mode not in MODE_MAP:
            raise ValueError(f"Unknown mode: {mode}. Available: {', '.join(MODE_MAP.keys())}")
        
        StrategyFactory.validate_strategy_for_mode(strategy_name, mode)
        
        logger.info(f"Creating strategy: {strategy_name} (mode: {mode})")
        
        try:
            if mode == 'scalping':
                from core.scalping.strategy import (
                    ScalpingEnsembleStrategy,
                    ScalpingMeanReversionStrategy,
                    ScalpingBreakoutStrategy,
                    ScalpingMomentumStrategy,
                )
                
                strategies = {
                    'scalping_ensemble': ScalpingEnsembleStrategy,
                    'scalping_mean_reversion': ScalpingMeanReversionStrategy,
                    'scalping_breakout': ScalpingBreakoutStrategy,
                    'scalping_momentum': ScalpingMomentumStrategy,
                }
            
            elif mode == 'swing':
                from core.swing.strategy import (
                    EnsembleStrategy,
                    MeanReversionStrategy,
                    BreakoutStrategy,
                    TrendFollowingStrategy,
                )
                
                strategies = {
                    'ensemble': EnsembleStrategy,
                    'ensemble_aggressive': EnsembleStrategy,
                    'mean_reversion': MeanReversionStrategy,
                    'breakout': BreakoutStrategy,
                    'trend_following': TrendFollowingStrategy,
                }
            
            strategy_class = strategies[strategy_name]
            
            if strategy_name == 'ensemble_aggressive':
                instance = strategy_class(aggressive=True, **kwargs)
            else:
                instance = strategy_class(**kwargs)
            
            logger.info(f"Strategy created: {strategy_name}")
            return instance
        
        except ImportError as e:
            logger.error(f"Failed to import strategy: {e}", exc_info=True)
            raise ImportError(f"Could not import strategy for {strategy_name}. Check core/{mode}/strategy.py") from e
        except Exception as e:
            logger.error(f"Failed to create strategy: {e}", exc_info=True)
            raise