import sys
import os
from pathlib import Path
import sys
import io

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.backtest import BacktestEngine
from core.trade_manager import TradeManager
from config.settings import Settings
from core.utils import setup_logging, clear_screen
import logging

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def display_menu() -> None:
    """Display the interactive menu"""
    print("=" * 40)
    print("     BINANCE TRADING BOT")
    print("=" * 40)
    print("Select operation mode:")
    print("1 - Backtest")
    print("2 - Testnet")
    print("3 - Live")
    print("=" * 40)


def get_user_choice() -> str:
    """Get and validate user input"""
    while True:
        try:
            choice = input("Choose an option: ").strip()
            if choice in ['1', '2', '3']:
                return choice
            else:
                print("❌ Invalid option. Please enter 1, 2, or 3.")
        except KeyboardInterrupt:
            print("\n\n👋 Exiting...")
            sys.exit(0)
        except EOFError:
            print("\n\n❌ Invalid input detected.")
            sys.exit(1)


def run_backtest(settings: Settings, logger: logging.Logger) -> None:
    """Run backtest mode"""
    logger.info("=" * 60)
    logger.info("STARTING BACKTEST MODE")
    logger.info("=" * 60)
    
    print("\n🔬 Initializing Backtest Engine...")
    
    try:
        engine = BacktestEngine(settings)
        engine.run()
        
        print("\n✅ Backtest completed successfully!")
        print(f"📊 Reports generated in: {settings.REPORTS_DIR}")
        
    except Exception as e:
        logger.error(f"Backtest failed: {e}", exc_info=True)
        print(f"\n❌ Backtest failed: {e}")
        sys.exit(1)


def run_testnet(settings: Settings, logger: logging.Logger) -> None:
    """Run testnet mode"""
    logger.info("=" * 60)
    logger.info("STARTING TESTNET MODE")
    logger.info("=" * 60)
    
    print("\n🧪 Initializing Testnet Trading...")
    print(f"📡 Connecting to: {settings.TESTNET_BASE_URL}")
    
    try:
        settings.TESTNET_MODE = True
        manager = TradeManager(settings, mode='testnet')
        manager.start()
        
    except KeyboardInterrupt:
        print("\n\n⏸️  Desligando o modo testnet...")
        logger.info("Modo testnet interrompido pelo usuário")
        manager.stop()
        
    except Exception as e:
        logger.error(f"Falha no modo Testnet: {e}", exc_info=True)
        print(f"\n❌ Falha no Testnet: {e}")
        sys.exit(1)


def run_live(settings: Settings, logger: logging.Logger) -> None:
    """Run live trading mode"""
    logger.info("=" * 60)
    logger.info("STARTING LIVE TRADING MODE")
    logger.info("=" * 60)
    
    print("\n" + "!" * 60)
    print("⚠️  WARNING: LIVE TRADING MODE - REAL MONEY AT RISK!")
    print("!" * 60)
    
    confirmation = input("\nType 'START LIVE TRADING' to continue: ").strip()
    
    if confirmation != "START LIVE TRADING":
        print("\n❌ Live trading cancelled.")
        logger.warning("Live trading cancelled by user")
        return
    
    print("\n💰 Initializing Live Trading...")
    print(f"📡 Connecting to: {settings.BINANCE_BASE_URL}")
    
    try:
        settings.TESTNET_MODE = False
        manager = TradeManager(settings, mode='live')
        manager.start()
        
    except KeyboardInterrupt:
        print("\n\n⏸️  Shutting down live mode...")
        logger.info("Live mode interrupted by user")
        manager.stop()
        
    except Exception as e:
        logger.error(f"Live mode failed: {e}", exc_info=True)
        print(f"\n❌ Live trading failed: {e}")
        sys.exit(1)


def main() -> None:
    """Main entry point"""
    clear_screen()
    
    try:
        settings = Settings()
        logger = setup_logging(settings)
        
    except Exception as e:
        print(f"\n❌ Initialization failed: {e}")
        print("\n💡 Make sure you have:")
        print("   1. Created a .env file with your API keys")
        print("   2. Installed all requirements: pip install -r requirements.txt")
        sys.exit(1)
    
    # Display menu and get choice
    display_menu()
    choice = get_user_choice()
    
    # Route to appropriate mode
    mode_map = {
        '1': ('Backtest', run_backtest),
        '2': ('Testnet', run_testnet),
        '3': ('Live', run_live)
    }
    
    mode_name, mode_func = mode_map[choice]
    
    clear_screen()
    print(f"\n🚀 Starting {mode_name} Mode...\n")
    logger.info(f"User selected mode: {mode_name}")
    
    # Execute selected mode
    mode_func(settings, logger)


if __name__ == "__main__":
    main()