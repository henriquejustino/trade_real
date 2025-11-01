"""
COPY THIS FILE TO: core/swing/trade_manager.py
Trade manager for SWING mode only
"""

import logging
import time
from pathlib import Path
from decimal import Decimal
from datetime import datetime

from core.exchange import BinanceExchange
from core.risk import RiskManager
from core.strategy_factory import StrategyFactory


class TradeManager:
    """Trade manager for swing trading mode"""
    
    def __init__(self, settings, mode: str = 'testnet'):
        """Initialize trade manager"""
        self.settings = settings
        self.mode = mode
        self.logger = logging.getLogger(f'TradingBot.TradeManager.Swing')
        
        # Initialize components
        self.logger.info(f"🔧 Initializing Swing Trade Manager ({mode} mode)")
        
        try:
            api_key, api_secret = settings.get_api_credentials(testnet=(mode == 'testnet'))
        except:
            api_key, api_secret = "", ""
        
        self.exchange = BinanceExchange(api_key, api_secret, testnet=(mode == 'testnet'))
        self.risk_manager = RiskManager(settings)
        
        self.strategy = StrategyFactory.create_strategy(
            settings.STRATEGY_MODE,
            mode='swing'
        )
        
        self.running = False
        self.open_trades = {}
        
        self.logger.info(f"✅ Swing Trade Manager Initialized ({mode})")
    
    def start(self) -> None:
        """Start trading loop"""
        self.running = True
        self.logger.info("🚀 Starting swing trading loop")
        
        print(f"\n✅ Swing Trade Manager Started ({self.mode} mode)")
        print(f"📊 Pairs: {', '.join(self.settings.TRADING_PAIRS)}")
        print(f"⏱️  Timeframe: {self.settings.ENTRY_TIMEFRAME}")
        print(f"🎯 Strategy: {self.settings.STRATEGY_MODE}")
        print(f"💾 Database: {self.settings.DATABASE_URL}")
        print(f"\n🔄 Trading loop running...")
        print("Press Ctrl+C to stop\n")
        
        try:
            while self.running:
                try:
                    # Simulate trading tick every 10 seconds
                    self._trading_loop()
                    time.sleep(10)
                
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    self.logger.error(f"❌ Trading loop error: {e}")
        
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()
    
    def _trading_loop(self) -> None:
        """Main trading loop iteration"""
        try:
            # Scan for opportunities
            for symbol in self.settings.TRADING_PAIRS:
                try:
                    # Load data
                    df = self.exchange.get_klines(
                        symbol,
                        self.settings.ENTRY_TIMEFRAME,
                        limit=200
                    )
                    
                    if df.empty or len(df) < 50:
                        continue
                    
                    # Generate signal
                    signal, strength = self.strategy.generate_signal(df)
                    
                    if signal in ['BUY', 'SELL'] and strength > self.settings.SIGNAL_THRESHOLD:
                        current_price = Decimal(str(df['close'].iloc[-1]))
                        self.logger.info(
                            f"📈 {symbol}: {signal} signal (strength: {strength:.2f}) @ ${current_price}"
                        )
                
                except Exception as e:
                    self.logger.debug(f"Error scanning {symbol}: {e}")
        
        except Exception as e:
            self.logger.error(f"Trading loop error: {e}")
    
    def stop(self) -> None:
        """Stop trading loop"""
        self.logger.info("⏹️ Stopping swing trade manager")
        self.running = False
        
        try:
            self.exchange.close()
        except:
            pass
        
        self.logger.info("✅ Swing trade manager stopped")