from decimal import Decimal
from pathlib import Path
from datetime import datetime


class SwingSettings:
    """Configurações EXCLUSIVAS para swing"""
    
    MODE = 'swing'
    MODE_DISPLAY = '📈 SWING (1h/4h)'
    
    PRIMARY_TIMEFRAME = '4h'
    ENTRY_TIMEFRAME = '1h'
    CANDLE_WAIT_BUFFER = 5
    
    TRADING_PAIRS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "ADAUSDT"]
    
    STRATEGY_MODE = 'ensemble_aggressive'
    REQUIRE_MTF_ALIGNMENT = False
    
    SIGNAL_THRESHOLD = 0.48
    SIGNAL_THRESHOLD_LOW = 0.30
    MIN_SIGNAL_BARS = 50
    
    RISK_PER_TRADE = Decimal("0.015")
    MAX_OPEN_TRADES = 6
    MAX_DRAWDOWN_PERCENT = Decimal("0.18")
    MAX_DAILY_LOSS_PERCENT = Decimal("0.035")
    
    MIN_POSITION_SIZE_USD = Decimal("10.0")
    MAX_POSITION_SIZE_USD = Decimal("10000.0")
    
    USE_DYNAMIC_POSITION_SIZING = True
    RISK_MULTIPLIER_VERY_STRONG = Decimal("1.5")
    RISK_MULTIPLIER_STRONG = Decimal("1.25")
    RISK_MULTIPLIER_MEDIUM = Decimal("1.0")
    RISK_MULTIPLIER_WEAK = Decimal("0.75")
    
    STOP_LOSS_PERCENT = Decimal("0.025")
    TAKE_PROFIT_PERCENT = Decimal("0.04")
    USE_TRAILING_STOP = True
    TRAILING_STOP_ATR_MULTIPLIER = Decimal("2.0")
    
    USE_PARTIAL_TAKE_PROFIT = True
    TP1_PERCENT = 0.5
    TP1_QUANTITY = 0.3
    TP2_PERCENT = 0.75
    TP2_QUANTITY = 0.4
    TP3_QUANTITY = 0.3
    
    MAKER_FEE = Decimal("0.001")
    TAKER_FEE = Decimal("0.001")
    SLIPPAGE_PERCENT = Decimal("0.001")
    
    hoje = datetime.now()
    BACKTEST_START_DATE = f"{hoje.year}-01-01"
    BACKTEST_END_DATE = hoje.strftime("%Y-10-31")
    BACKTEST_INITIAL_CAPITAL = Decimal("10000.0")
    
    DATA_DIR = Path("data/swing")
    REPORTS_DIR = Path("reports/swing")
    LOGS_DIR = Path("reports/logs/swing")
    DATABASE_URL = "sqlite:///db/swing_state.db"
    
    LOG_LEVEL = "INFO"
    LOG_TO_FILE = True
    LOG_ROTATION_DAYS = 7
    LOG_BACKUP_COUNT = 30
    
    MAX_REQUESTS_PER_MINUTE = 1200
    RATE_LIMIT_BUFFER = 0.8
    
    MAX_RETRIES = 5
    RETRY_DELAY_SECONDS = 1.0
    RETRY_BACKOFF_MULTIPLIER = 2.0
    
    TESTNET_MODE = False
    DRY_RUN = False
    
    BACKUP_ENABLED = True
    BACKUP_INTERVAL_HOURS = 4
    BACKUP_KEEP_COUNT = 7
    
    BINANCE_BASE_URL = "https://api.binance.com"
    TESTNET_BASE_URL = "https://testnet.binance.vision"
    
    TELEGRAM_ENABLED = False
    TELEGRAM_BOT_TOKEN = ""
    TELEGRAM_CHAT_ID = ""
    
    SLACK_ENABLED = False
    SLACK_WEBHOOK_URL = ""
    
    @classmethod
    def validate(cls) -> bool:
        """Valida configuração"""
        if cls.PRIMARY_TIMEFRAME == cls.ENTRY_TIMEFRAME:
            raise ValueError("Timeframes devem ser diferentes")
        if not (0 < cls.RISK_PER_TRADE <= Decimal("0.1")):
            raise ValueError("RISK_PER_TRADE inválido")
        total_qty = cls.TP1_QUANTITY + cls.TP2_QUANTITY + cls.TP3_QUANTITY
        if abs(total_qty - 1.0) > 0.01:
            raise ValueError(f"Quantidades de TP devem somar 1.0, obtido {total_qty}")
        return True
    
    @classmethod
    def create_directories(cls) -> None:
        """Cria diretórios necessários"""
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        cls.LOGS_DIR.mkdir(parents=True, exist_ok=True)
        Path("db").mkdir(parents=True, exist_ok=True)