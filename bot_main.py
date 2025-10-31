import sys
import os
from pathlib import Path
import io

sys.path.insert(0, str(Path(__file__).parent))

from core.backtest import BacktestEngine
from core.trade_manager import TradeManager
from config.settings import Settings
from core.utils import setup_logging, clear_screen
import logging

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def display_operation_menu() -> str:
    """Display the operation mode menu"""
    print("=" * 50)
    print("     BINANCE TRADING BOT")
    print("=" * 50)
    print("Selecione o modo de operação:")
    print("1 - Backtest")
    print("2 - Testnet")
    print("3 - Trading ao Vivo")
    print("=" * 50)
    
    while True:
        choice = input("Escolha uma opção (1-3): ").strip()
        if choice in ['1', '2', '3']:
            return choice
        print("❌ Opção inválida. Digite 1, 2 ou 3.")

def display_trading_mode_menu() -> str:
    """Display the trading mode menu (scalping vs swing)"""
    print("\n" + "=" * 50)
    print("     SELECIONE O MODO DE TRADING")
    print("=" * 50)
    print("1 - Scalping (timeframes 5m/15m)")
    print("2 - Swing Trading (timeframes 1h/4h)")
    print("=" * 50)
    
    while True:
        choice = input("Escolha o modo de trading (1-2): ").strip()
        if choice in ['1', '2']:
            return choice
        print("❌ Opção inválida. Digite 1 ou 2.")

def get_user_operation_choice() -> str:
    """Get and validate user input for operation mode"""
    while True:
        try:
            choice = input("Escolha uma opção: ").strip()
            if choice in ['1', '2', '3']:
                return choice
            else:
                print("❌ Opção inválida. Digite 1, 2 ou 3.")
        except KeyboardInterrupt:
            print("\n\n👋 Encerrando...")
            sys.exit(0)
        except EOFError:
            print("\n\n❌ Entrada inválida detectada.")
            sys.exit(1)

def get_user_trading_choice() -> str:
    """Get and validate user input for trading mode"""
    while True:
        try:
            choice = input("Escolha o modo de trading: ").strip()
            if choice in ['1', '2']:
                return choice
            else:
                print("❌ Opção inválida. Digite 1 ou 2.")
        except KeyboardInterrupt:
            print("\n\n👋 Encerrando...")
            sys.exit(0)
        except EOFError:
            print("\n\n❌ Entrada inválida detectada.")
            sys.exit(1)

def run_backtest(settings: Settings, logger: logging.Logger, trading_mode: str) -> None:
    """Run backtest mode"""
    logger.info("=" * 60)
    logger.info(f"INICIANDO BACKTEST - MODO {trading_mode.upper()}")
    logger.info("=" * 60)
    
    print("\n🔬 Inicializando Backtest Engine...")
    print(f"📊 Modo: {trading_mode.upper()}")
    print(f"📈 Pares: {', '.join(settings.TRADING_PAIRS)}")
    print(f"⏱️  Timeframes: {settings.PRIMARY_TIMEFRAME} (primária), {settings.ENTRY_TIMEFRAME} (entrada)")
    
    try:
        engine = BacktestEngine(settings)
        results = engine.run()
        
        print("\n✅ Backtest concluído com sucesso!")
        print(f"📊 Relatórios gerados em: {settings.REPORTS_DIR}")
        
        if results:
            print(f"\n📈 Resumo dos Resultados:")
            print(f"   Total de Trades: {results.get('total_trades', 0)}")
            print(f"   Taxa de Acerto: {results.get('win_rate', 0):.2f}%")
            print(f"   PnL Total: ${results.get('total_pnl', 0):,.2f}")
            print(f"   Retorno: {results.get('total_pnl_percent', 0):.2f}%")
        
    except Exception as e:
        logger.error(f"Backtest falhou: {e}", exc_info=True)
        print(f"\n❌ Backtest falhou: {e}")
        sys.exit(1)

def run_testnet(settings: Settings, logger: logging.Logger, trading_mode: str) -> None:
    """Run testnet mode"""
    logger.info("=" * 60)
    logger.info(f"INICIANDO TESTNET - MODO {trading_mode.upper()}")
    logger.info("=" * 60)
    
    print("\n🧪 Inicializando Trading em Testnet...")
    print(f"📊 Modo: {trading_mode.upper()}")
    print(f"📡 Conectando a: {settings.TESTNET_BASE_URL}")
    print(f"💱 Pares: {', '.join(settings.TRADING_PAIRS)}")
    print(f"⏱️  Timeframes: {settings.PRIMARY_TIMEFRAME} (primária), {settings.ENTRY_TIMEFRAME} (entrada)")
    
    try:
        settings.TESTNET_MODE = True
        manager = TradeManager(settings, mode='testnet')
        manager.start()
        
    except KeyboardInterrupt:
        print("\n\n⏸️  Encerrando testnet...")
        logger.info("Testnet interrompido pelo usuário")
        if 'manager' in locals():
            manager.stop()
        
    except Exception as e:
        logger.error(f"Testnet falhou: {e}", exc_info=True)
        print(f"\n❌ Testnet falhou: {e}")
        sys.exit(1)

def run_live(settings: Settings, logger: logging.Logger, trading_mode: str) -> None:
    """Run live trading mode"""
    logger.info("=" * 60)
    logger.info(f"INICIANDO TRADING AO VIVO - MODO {trading_mode.upper()}")
    logger.info("=" * 60)
    
    print("\n" + "!" * 60)
    print("⚠️  AVISO: MODO TRADING AO VIVO - DINHEIRO REAL EM RISCO!")
    print("!" * 60)
    print(f"\n📊 Modo de Trading: {trading_mode.upper()}")
    print(f"💱 Pares: {', '.join(settings.TRADING_PAIRS)}")
    print(f"⏱️  Timeframes: {settings.PRIMARY_TIMEFRAME} (primária), {settings.ENTRY_TIMEFRAME} (entrada)")
    print(f"🎯 Estratégia: {settings.STRATEGY_MODE}")
    
    confirmation = input("\nDigite 'INICIAR TRADING AO VIVO' para continuar: ").strip()
    
    if confirmation != "INICIAR TRADING AO VIVO":
        print("\n❌ Trading ao vivo cancelado.")
        logger.warning("Trading ao vivo cancelado pelo usuário")
        return
    
    print("\n💰 Inicializando Trading ao Vivo...")
    print(f"📡 Conectando a: {settings.BINANCE_BASE_URL}")
    
    try:
        settings.TESTNET_MODE = False
        manager = TradeManager(settings, mode='live')
        manager.start()
        
    except KeyboardInterrupt:
        print("\n\n⏸️  Encerrando trading ao vivo...")
        logger.info("Trading ao vivo interrompido pelo usuário")
        if 'manager' in locals():
            manager.stop()
        
    except Exception as e:
        logger.error(f"Trading ao vivo falhou: {e}", exc_info=True)
        print(f"\n❌ Trading ao vivo falhou: {e}")
        sys.exit(1)

def main() -> None:
    """Main entry point with dual-mode support"""
    clear_screen()
    
    # Initialize settings and logging
    try:
        settings = Settings()
        logger = setup_logging(settings)
        
    except Exception as e:
        print(f"\n❌ Inicialização falhou: {e}")
        print("\n💡 Certifique-se de:")
        print("   1. Ter criado um arquivo .env com suas API keys")
        print("   2. Ter instalado todos os requirements: pip install -r requirements.txt")
        sys.exit(1)
    
    # Display operation menu and get choice
    display_operation_menu()
    operation_choice = get_user_operation_choice()
    
    # Display trading mode menu and get choice
    display_trading_mode_menu()
    trading_choice = get_user_trading_choice()
    
    # Determine trading mode
    trading_mode = "scalping" if trading_choice == "1" else "swing"
    
    # Load the appropriate profile
    settings.load_profile(trading_mode)
    
    clear_screen()
    
    # Route to appropriate mode
    mode_map = {
        '1': ('Backtest', run_backtest),
        '2': ('Testnet', run_testnet),
        '3': ('Trading ao Vivo', run_live)
    }
    
    mode_name, mode_func = mode_map[operation_choice]
    
    print(f"\n🚀 Iniciando {mode_name} - MODO {trading_mode.upper()}...\n")
    logger.info(f"Usuário selecionou: {mode_name}, modo {trading_mode}")
    
    # Execute selected mode
    mode_func(settings, logger, trading_mode)

if __name__ == "__main__":
    main()