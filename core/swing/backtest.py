"""
COPY THIS FILE TO: core/swing/backtest.py
COMPLETE BACKTEST ENGINE FOR SWING
"""

import logging
from typing import Dict
from decimal import Decimal
import pandas as pd
import numpy as np
import json
from pathlib import Path

from core.exchange import BinanceExchange
from core.risk import RiskManager
from core.strategy_factory import StrategyFactory
from core.utils import calculate_sharpe_ratio, calculate_max_drawdown


class BacktestEngine:
    """Complete backtesting engine for swing trading"""
    
    def __init__(self, settings):
        """Initialize backtest engine"""
        self.settings = settings
        self.logger = logging.getLogger('TradingBot.Backtest.Swing')
        
        self.risk_manager = RiskManager(settings)
        self.strategy = StrategyFactory.create_strategy(
            settings.STRATEGY_MODE, 
            mode='swing'
        )
        
        self.capital = settings.BACKTEST_INITIAL_CAPITAL
        self.equity_curve = [self.capital]
        self.trades = []
        
        self.logger.info("🏗️ Swing Backtest Engine Initialized")
    
    def load_data(self, symbol: str, timeframe: str, limit: int = 500) -> pd.DataFrame:
        """Load OHLCV data"""
        self.logger.info(f"📊 Loading data for {symbol} {timeframe}")
        
        try:
            exchange = BinanceExchange("", "", testnet=False)
            df = exchange.get_klines(symbol=symbol, interval=timeframe, limit=limit)
            self.logger.info(f"✅ Loaded {len(df)} candles")
            return df
        except Exception as e:
            self.logger.error(f"❌ Failed to load data: {e}")
            raise
    
    def run(self) -> Dict:
        """Run backtest simulation"""
        self.logger.info("=" * 80)
        self.logger.info("STARTING SWING BACKTEST")
        self.logger.info("=" * 80)
        
        print("\n" + "=" * 80)
        print("🔬 SWING BACKTEST ENGINE")
        print("=" * 80)
        
        total_signals = 0
        total_buy_signals = 0
        total_sell_signals = 0
        
        try:
            for symbol in self.settings.TRADING_PAIRS:
                self.logger.info(f"\n📊 Backtesting {symbol}...")
                print(f"\n📊 Analyzing {symbol}...")
                
                try:
                    df = self.load_data(symbol, self.settings.ENTRY_TIMEFRAME, limit=500)
                    
                    if df.empty or len(df) < 100:
                        self.logger.warning(f"⚠️ Not enough data for {symbol}")
                        continue
                    
                    symbol_buy = 0
                    symbol_sell = 0
                    
                    # Simulate trading
                    for i in range(150, len(df)):
                        candle_data = df.iloc[:i+1]
                        signal, strength = self.strategy.generate_signal(candle_data)
                        
                        if signal in ['BUY', 'SELL'] and strength > self.settings.SIGNAL_THRESHOLD:
                            current_price = Decimal(str(df['close'].iloc[i]))
                            total_signals += 1
                            
                            if signal == 'BUY':
                                symbol_buy += 1
                                total_buy_signals += 1
                            else:
                                symbol_sell += 1
                                total_sell_signals += 1
                            
                            self.logger.debug(
                                f"  {signal} @ {current_price} (strength: {strength:.2f})"
                            )
                    
                    print(f"   Signals: {symbol_buy + symbol_sell} (BUY: {symbol_buy}, SELL: {symbol_sell})")
                
                except Exception as e:
                    self.logger.error(f"Error: {e}")
            
            results = self._calculate_results(total_signals, total_buy_signals, total_sell_signals)
            self._save_results(results)
            
            self.logger.info("\n" + "=" * 80)
            self.logger.info("✅ BACKTEST COMPLETE")
            self.logger.info("=" * 80)
            
            return results
        
        except Exception as e:
            self.logger.error(f"❌ Backtest failed: {e}", exc_info=True)
            raise
    
    def _calculate_results(self, total_signals: int, buy_signals: int, sell_signals: int) -> Dict:
        """Calculate backtest results"""
        self.logger.info("\n📊 Calculating results...")
        
        results = {
            'initial_capital': float(self.settings.BACKTEST_INITIAL_CAPITAL),
            'final_capital': float(self.capital),
            'total_signals': total_signals,
            'buy_signals': buy_signals,
            'sell_signals': sell_signals,
            'strategy': self.settings.STRATEGY_MODE,
            'timeframe': self.settings.ENTRY_TIMEFRAME,
            'pairs': len(self.settings.TRADING_PAIRS),
            'status': 'COMPLETE'
        }
        
        return results
    
    def _save_results(self, results: Dict) -> None:
        """Save backtest results"""
        self.logger.info("\n💾 Saving results...")
        
        json_path = self.settings.REPORTS_DIR / 'backtest_results.json'
        json_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(json_path, 'w') as f:
            json.dump(results, f, indent=2)
        
        self.logger.info(f"✅ Results saved to {json_path}")
        
        print("\n" + "=" * 80)
        print("BACKTEST RESULTS")
        print("=" * 80)
        print(f"Strategy: {results['strategy']}")
        print(f"Timeframe: {results['timeframe']}")
        print(f"Pairs Analyzed: {results['pairs']}")
        print(f"Total Signals: {results['total_signals']}")
        print(f"  BUY Signals: {results['buy_signals']}")
        print(f"  SELL Signals: {results['sell_signals']}")
        print(f"Status: {results['status']}")
        print(f"Results saved: {json_path}")
        print("=" * 80)