"""
Configuration settings for the trading bot
Loads from .env file and provides validation
Perfis de estratégia integrados (Scalping e Swing)
"""

import os
from pathlib import Path
from typing import List, Optional, Tuple, Dict
from decimal import Decimal
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from datetime import datetime

hoje = datetime.now()

# Load environment variables
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)


# ============================================================================
# STRATEGY PROFILES - Integrados aqui
# ============================================================================

SCALPING_PROFILE = {
    'PRIMARY_TIMEFRAME': '15m',
    'ENTRY_TIMEFRAME': '5m',
    'STRATEGY_MODE': 'scalping_ensemble',
    'REQUIRE_MTF_ALIGNMENT': False,
    'TRADING_PAIRS': ["BTCUSDT", "ETHUSDT", "BNBUSDT", "ADAUSDT"],
    'RISK_PER_TRADE': Decimal("0.008"),
    'MAX_OPEN_TRADES': 5,
    'MAX_DRAWDOWN_PERCENT': Decimal("0.12"),
    'MAX_DAILY_LOSS_PERCENT': Decimal("0.025"),
    'MIN_POSITION_SIZE_USD': Decimal("5.0"),
    'MAX_POSITION_SIZE_USD': Decimal("500.0"),
    'STOP_LOSS_PERCENT': Decimal("0.018"),
    'TAKE_PROFIT_PERCENT': Decimal("0.035"),
    'USE_TRAILING_STOP': True,
    'TRAILING_STOP_ATR_MULTIPLIER': Decimal("1.0"),
    'USE_PARTIAL_TAKE_PROFIT': True,
    'TP1_PERCENT': 0.6,
    'TP1_QUANTITY': 0.25,
    'TP2_PERCENT': 0.8,
    'TP2_QUANTITY': 0.35,
    'TP3_QUANTITY': 0.4,
    'USE_DYNAMIC_POSITION_SIZING': True,
    'RISK_MULTIPLIER_VERY_STRONG': 1.3,
    'RISK_MULTIPLIER_STRONG': 1.1,
    'RISK_MULTIPLIER_MEDIUM': 1.0,
    'RISK_MULTIPLIER_WEAK': 0.8,
}

SWING_PROFILE = {
    'PRIMARY_TIMEFRAME': '4h',
    'ENTRY_TIMEFRAME': '1h',
    'STRATEGY_MODE': 'ensemble_aggressive',
    'REQUIRE_MTF_ALIGNMENT': False,
    'TRADING_PAIRS': ["BTCUSDT", "ETHUSDT", "SOLUSDT", "ADAUSDT"],
    'RISK_PER_TRADE': Decimal("0.015"),
    'MAX_OPEN_TRADES': 6,
    'MAX_DRAWDOWN_PERCENT': Decimal("0.18"),
    'MAX_DAILY_LOSS_PERCENT': Decimal("0.035"),
    'MIN_POSITION_SIZE_USD': Decimal("10.0"),
    'MAX_POSITION_SIZE_USD': Decimal("10000.0"),
    'STOP_LOSS_PERCENT': Decimal("0.025"),
    'TAKE_PROFIT_PERCENT': Decimal("0.04"),
    'USE_TRAILING_STOP': True,
    'TRAILING_STOP_ATR_MULTIPLIER': Decimal("2.0"),
    'USE_PARTIAL_TAKE_PROFIT': True,
    'TP1_PERCENT': 0.5,
    'TP1_QUANTITY': 0.3,
    'TP2_PERCENT': 0.75,
    'TP2_QUANTITY': 0.4,
    'TP3_QUANTITY': 0.3,
    'USE_DYNAMIC_POSITION_SIZING': True,
    'RISK_MULTIPLIER_VERY_STRONG': 1.5,
    'RISK_MULTIPLIER_STRONG': 1.25,
    'RISK_MULTIPLIER_MEDIUM': 1.0,
    'RISK_MULTIPLIER_WEAK': 0.75,
}

STRATEGY_PROFILES = {
    'scalping': SCALPING_PROFILE,
    'swing': SWING_PROFILE
}

DEFAULT_PROFILE = 'swing'


class Settings(BaseSettings):
    """Application settings with validation"""
    
    # API Configuration
    BINANCE_API_KEY: str = Field(default="", env="BINANCE_API_KEY")
    BINANCE_API_SECRET: str = Field(default="", env="BINANCE_API_SECRET")
    TESTNET_API_KEY: str = Field(default="", env="TESTNET_API_KEY")
    TESTNET_API_SECRET: str = Field(default="", env="TESTNET_API_SECRET")
    
    # URLs
    BINANCE_BASE_URL: str = "https://api.binance.com"
    TESTNET_BASE_URL: str = "https://testnet.binance.vision"
    
    # Trading Pairs
    TRADING_PAIRS: List[str] = Field(
        default=["BTCUSDT", "ETHUSDT", "SOLUSDT", "ADAUSDT"]
    )
    
    # Timeframes
    PRIMARY_TIMEFRAME: str = "4h"
    ENTRY_TIMEFRAME: str = "1h"
    ADDITIONAL_TIMEFRAMES: List[str] = ["15m", "5m"]

    # Gerenciamento de backups
    BACKUP_ENABLED: bool = True
    BACKUP_INTERVAL_HOURS: int = 4
    BACKUP_KEEP_COUNT: int = 5

    STRATEGY_MODE: str = "ensemble_aggressive"
    REQUIRE_MTF_ALIGNMENT: bool = True
    
    # Risk Management
    RISK_PER_TRADE: Decimal = Decimal("0.015")
    MAX_OPEN_TRADES: int = 6
    MAX_DRAWDOWN_PERCENT: Decimal = Decimal("0.18")
    MAX_DAILY_LOSS_PERCENT: Decimal = Decimal("0.035")
    
    # Position Sizing
    MIN_POSITION_SIZE_USD: Decimal = Decimal("10.0")
    MAX_POSITION_SIZE_USD: Decimal = Decimal("10000.0")
    
    # Stop Loss / Take Profit
    STOP_LOSS_PERCENT: Decimal = Decimal("0.025")
    TAKE_PROFIT_PERCENT: Decimal = Decimal("0.04")
    USE_TRAILING_STOP: bool = True
    TRAILING_STOP_ATR_MULTIPLIER: Decimal = Decimal("2.0")

    # Take Profit Parcial
    USE_PARTIAL_TAKE_PROFIT: bool = True
    TP1_PERCENT: float = 0.5
    TP1_QUANTITY: float = 0.3
    TP2_PERCENT: float = 0.75
    TP2_QUANTITY: float = 0.4
    TP3_QUANTITY: float = 0.3

    # Position Sizing Dinâmico
    USE_DYNAMIC_POSITION_SIZING: bool = True
    RISK_MULTIPLIER_VERY_STRONG: float = 1.5
    RISK_MULTIPLIER_STRONG: float = 1.25
    RISK_MULTIPLIER_MEDIUM: float = 1.0
    RISK_MULTIPLIER_WEAK: float = 0.75
    
    # Fees and Slippage
    MAKER_FEE: Decimal = Decimal("0.001")
    TAKER_FEE: Decimal = Decimal("0.001")
    SLIPPAGE_PERCENT: Decimal = Decimal("0.001")
    
    # Database
    DATABASE_URL: str = Field(
        default="sqlite:///db/state.db",
        env="DATABASE_URL"
    )
    
    # Backtest Configuration
    BACKTEST_START_DATE: str = f"{hoje.year}-01-01"
    BACKTEST_END_DATE: str = hoje.strftime("%Y-10-21")
    BACKTEST_INITIAL_CAPITAL: Decimal = Decimal("10000.0")
    
    # Data Sources
    DATA_DIR: Path = Path("data")
    REPORTS_DIR: Path = Path("reports")
    LOGS_DIR: Path = Path("reports/logs")
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_TO_FILE: bool = True
    LOG_ROTATION_DAYS: int = 7
    LOG_BACKUP_COUNT: int = 30
    
    # Notifications
    TELEGRAM_ENABLED: bool = Field(default=False, env="TELEGRAM_ENABLED")
    TELEGRAM_BOT_TOKEN: str = Field(default="", env="TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID: str = Field(default="", env="TELEGRAM_CHAT_ID")
    
    SLACK_ENABLED: bool = Field(default=False, env="SLACK_ENABLED")
    SLACK_WEBHOOK_URL: str = Field(default="", env="SLACK_WEBHOOK_URL")
    
    # API Rate Limiting
    MAX_REQUESTS_PER_MINUTE: int = 1200
    RATE_LIMIT_BUFFER: float = 0.8
    
    # Retry Configuration
    MAX_RETRIES: int = 5
    RETRY_DELAY_SECONDS: float = 1.0
    RETRY_BACKOFF_MULTIPLIER: float = 2.0
    
    # Mode Control
    TESTNET_MODE: bool = False
    DRY_RUN: bool = False
    
    # Performance
    USE_ASYNC: bool = True
    MAX_WORKERS: int = 4
    
    # Monitoring
    ENABLE_WEB_DASHBOARD: bool = False
    DASHBOARD_PORT: int = 8080
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
    
    @field_validator("BINANCE_API_KEY", "BINANCE_API_SECRET")
    @classmethod
    def validate_live_api_keys(cls, v):
        """Validate that live API keys are present when needed"""
        return v
    
    @field_validator("TRADING_PAIRS")
    @classmethod
    def validate_trading_pairs(cls, v):
        """Ensure all pairs end with USDT"""
        validated = []
        for pair in v:
            if not pair.endswith("USDT"):
                raise ValueError(f"Trading pair {pair} must end with USDT")
            validated.append(pair.upper())
        return validated
    
    @field_validator("RISK_PER_TRADE")
    @classmethod
    def validate_risk_per_trade(cls, v):
        """Ensure risk per trade is reasonable"""
        if v <= 0 or v > Decimal("0.1"):
            raise ValueError("RISK_PER_TRADE must be between 0 and 0.1 (10%)")
        return v
    
    @field_validator("MAX_DRAWDOWN_PERCENT")
    @classmethod
    def validate_max_drawdown(cls, v):
        """Ensure max drawdown is reasonable"""
        if v <= 0 or v > Decimal("0.5"):
            raise ValueError("MAX_DRAWDOWN_PERCENT must be between 0 and 0.5 (50%)")
        return v
    
    def _validate_partial_tp_config(self) -> None:
        """Validate partial take profit configuration"""
        if self.USE_PARTIAL_TAKE_PROFIT:
            total = self.TP1_QUANTITY + self.TP2_QUANTITY + self.TP3_QUANTITY
            if abs(total - 1.0) > 0.01:
                raise ValueError(
                    f"As quantidades parciais de TP devem somar 1,0 (100%), obtido {total}"
                )
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._create_directories()
        self._validate_partial_tp_config()
    
    def _create_directories(self) -> None:
        """Create necessary directories if they don't exist"""
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        self.LOGS_DIR.mkdir(parents=True, exist_ok=True)
        
        db_dir = Path("db")
        db_dir.mkdir(parents=True, exist_ok=True)
    
    def load_profile(self, profile_name: str) -> None:

        if profile_name not in STRATEGY_PROFILES:
            raise ValueError(f"Perfil desconhecido: {profile_name}. Use 'scalping' ou 'swing'")
        
        profile = STRATEGY_PROFILES[profile_name]
        
        # Aplica todas as configurações do perfil
        self.PRIMARY_TIMEFRAME = profile['PRIMARY_TIMEFRAME']
        self.ENTRY_TIMEFRAME = profile['ENTRY_TIMEFRAME']
        self.STRATEGY_MODE = profile['STRATEGY_MODE']
        self.REQUIRE_MTF_ALIGNMENT = profile['REQUIRE_MTF_ALIGNMENT']
        self.TRADING_PAIRS = profile['TRADING_PAIRS']
        self.RISK_PER_TRADE = profile['RISK_PER_TRADE']
        self.MAX_OPEN_TRADES = profile['MAX_OPEN_TRADES']
        self.MAX_DRAWDOWN_PERCENT = profile['MAX_DRAWDOWN_PERCENT']
        self.MAX_DAILY_LOSS_PERCENT = profile['MAX_DAILY_LOSS_PERCENT']
        self.MIN_POSITION_SIZE_USD = profile['MIN_POSITION_SIZE_USD']
        self.MAX_POSITION_SIZE_USD = profile['MAX_POSITION_SIZE_USD']
        self.STOP_LOSS_PERCENT = profile['STOP_LOSS_PERCENT']
        self.TAKE_PROFIT_PERCENT = profile['TAKE_PROFIT_PERCENT']
        self.USE_TRAILING_STOP = profile['USE_TRAILING_STOP']
        self.TRAILING_STOP_ATR_MULTIPLIER = profile['TRAILING_STOP_ATR_MULTIPLIER']
        self.USE_PARTIAL_TAKE_PROFIT = profile.get('USE_PARTIAL_TAKE_PROFIT', True)
        self.TP1_PERCENT = profile.get('TP1_PERCENT', 0.5)
        self.TP1_QUANTITY = profile.get('TP1_QUANTITY', 0.3)
        self.TP2_PERCENT = profile.get('TP2_PERCENT', 0.75)
        self.TP2_QUANTITY = profile.get('TP2_QUANTITY', 0.4)
        self.TP3_QUANTITY = profile.get('TP3_QUANTITY', 0.3)
        self.USE_DYNAMIC_POSITION_SIZING = profile.get('USE_DYNAMIC_POSITION_SIZING', True)
        self.RISK_MULTIPLIER_VERY_STRONG = profile.get('RISK_MULTIPLIER_VERY_STRONG', 1.5)
        self.RISK_MULTIPLIER_STRONG = profile.get('RISK_MULTIPLIER_STRONG', 1.25)
        self.RISK_MULTIPLIER_MEDIUM = profile.get('RISK_MULTIPLIER_MEDIUM', 1.0)
        self.RISK_MULTIPLIER_WEAK = profile.get('RISK_MULTIPLIER_WEAK', 0.75)
    
    def get_api_credentials(self, testnet: bool = False) -> Tuple[str, str]:
        """Get appropriate API credentials based on mode"""
        if testnet:
            if not self.TESTNET_API_KEY or not self.TESTNET_API_SECRET:
                raise ValueError(
                    "Testnet API keys not configured. "
                    "Set TESTNET_API_KEY and TESTNET_API_SECRET in .env file"
                )
            return self.TESTNET_API_KEY, self.TESTNET_API_SECRET
        else:
            if not self.BINANCE_API_KEY or not self.BINANCE_API_SECRET:
                raise ValueError(
                    "Binance API keys not configured. "
                    "Set BINANCE_API_KEY and BINANCE_API_SECRET in .env file"
                )
            return self.BINANCE_API_KEY, self.BINANCE_API_SECRET
    
    def get_base_url(self, testnet: bool = False) -> str:
        """Get appropriate base URL based on mode"""
        return self.TESTNET_BASE_URL if testnet else self.BINANCE_BASE_URL
    
    def validate_for_live_trading(self) -> None:
        """Validate configuration for live trading"""
        errors = []
        
        if not self.BINANCE_API_KEY or len(self.BINANCE_API_KEY) < 10:
            errors.append("Invalid or missing BINANCE_API_KEY")
        
        if not self.BINANCE_API_SECRET or len(self.BINANCE_API_SECRET) < 10:
            errors.append("Invalid or missing BINANCE_API_SECRET")
        
        if not self.TRADING_PAIRS:
            errors.append("No trading pairs configured")
        
        if self.RISK_PER_TRADE <= 0:
            errors.append("RISK_PER_TRADE must be positive")
        
        if errors:
            raise ValueError(
                "Configuration validation failed:\n" + 
                "\n".join(f"  - {e}" for e in errors)
            )
    
    def validate_for_testnet(self) -> None:
        """Validate configuration for testnet trading"""
        errors = []
        
        if not self.TESTNET_API_KEY or len(self.TESTNET_API_KEY) < 10:
            errors.append("Invalid or missing TESTNET_API_KEY")
        
        if not self.TESTNET_API_SECRET or len(self.TESTNET_API_SECRET) < 10:
            errors.append("Invalid or missing TESTNET_API_SECRET")
        
        if not self.TRADING_PAIRS:
            errors.append("No trading pairs configured")
        
        if errors:
            raise ValueError(
                "Testnet configuration validation failed:\n" + 
                "\n".join(f"  - {e}" for e in errors)
            )
        
    def sync_with_testnet(self) -> None:
        """
        Sincroniza o relógio local com o testnet
        Chamado uma vez na inicialização
        """
        from core.exchange import BinanceExchange
        import logging
        
        logger = logging.getLogger('TradingBot')
        
        try:
            api_key, api_secret = self.get_api_credentials(testnet=True)
            exchange = BinanceExchange(api_key, api_secret, testnet=True)
            
            server_time = exchange.get_server_time()
            local_time = datetime.utcnow()
            
            time_diff = (server_time - local_time).total_seconds()
            
            if abs(time_diff) > 60:
                logger.warning(
                    f"⚠️ Time sync: Server time {time_diff:.0f}s ahead of local time"
                )
                logger.warning(
                    f"   Server: {server_time}"
                )
                logger.warning(
                    f"   Local:  {local_time}"
                )
                logger.warning(
                    f"   Consider syncing your system clock!"
                )
            else:
                logger.info("✓ Time is synced with testnet")
                
        except Exception as e:
            logger.warning(f"Could not sync time with testnet: {e}")