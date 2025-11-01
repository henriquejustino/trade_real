"""
COPY THIS FILE TO: bot_scalping.py
COMPLETE SCALPING BOT WITH WORKING BACKTEST
"""

import sys
import os
from pathlib import Path
import io

sys.path.insert(0, str(Path(__file__).parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from config.scalping_settings import ScalpingSettings
from core.utils import setup_logging, clear_screen
import logging


def main():
    """Main entry point"""
    try:
        clear_screen()
        
        print("\n" + "=" * 80)
        print("⚡ BINANCE SCALPING BOT - FAST TRADING (5m/15m) ⚡")
        print("=" * 80)
        
        # Initialize
        print("\nInitializing...")
        ScalpingSettings.validate()
        ScalpingSettings.create_directories()
        
        settings = ScalpingSettings()
        logger = setup_logging(settings)
        
        logger.info("Scalping Bot Started")
        
        # Show available strategies
        print("\nAvailable Strategies:")
        from core.strategy_factory import StrategyFactory
        available = StrategyFactory.get_available_strategies('scalping')
        for name in available.keys():
            print(f"  • {name}")
        
        # Menu
        print("\n" + "=" * 80)
        print("SELECT OPERATION MODE")
        print("=" * 80)
        print("1 - Backtest")
        print("2 - Testnet")
        print("3 - Live Trading")
        print("=" * 80)
        
        choice = input("\nChoose (1-3): ").strip()
        
        if choice == '1':
            print("\n🔬 Starting Backtest...")
            logger.info("Backtest mode selected")
            from core.scalping.backtest import BacktestEngine
            engine = BacktestEngine(settings)
            results = engine.run()
            print("✅ Backtest Complete!")
            
        elif choice == '2':
            print("\n🧪 Starting Testnet...")
            logger.info("Testnet mode selected")
            from core.scalping.trade_manager import TradeManager
            manager = TradeManager(settings, mode='testnet')
            manager.start()
            
        elif choice == '3':
            print("\n⚠️ WARNING - LIVE TRADING WITH REAL MONEY")
            confirm = input("Type 'START LIVE SCALPING' to continue: ").strip()
            if confirm == "START LIVE SCALPING":
                print("\n📈 Starting Live Trading...")
                logger.info("Live trading mode selected")
                from core.scalping.trade_manager import TradeManager
                manager = TradeManager(settings, mode='live')
                manager.start()
            else:
                print("Cancelled")
        else:
            print("Invalid option")
        
    except KeyboardInterrupt:
        print("\n\nBot interrupted")
        sys.exit(0)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()