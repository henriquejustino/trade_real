"""
Configuration settings for the trading bot
Loads from .env file and provides validation
"""

import os
from pathlib import Path
from typing import List, Optional, Tuple
from decimal import Decimal
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from datetime import datetime

hoje = datetime.now()


# Load environment variables
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)


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
        default=["BTCUSDT", "ETHUSDT", "SOLUSDT", "ADAUSDT"]  # 4 pares = 4x mais oportunidades!
    )
    
    # Timeframes
    PRIMARY_TIMEFRAME: str = "4h"  # Main trend detection
    ENTRY_TIMEFRAME: str = "1h"    # Entry signals
    ADDITIONAL_TIMEFRAMES: List[str] = ["15m", "5m"]

    # # TESTEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE
    # PRIMARY_TIMEFRAME: str = "15m"  # Main trend detection
    # ENTRY_TIMEFRAME: str = "5m"    # Entry signals
    # ADDITIONAL_TIMEFRAMES: List[str] = ["5m", "1m"]
    
    # Strategy Configuration
    # STRATEGY_MODE: str = "ensemble_ultra"
    # REQUIRE_MTF_ALIGNMENT: bool = False

    STRATEGY_MODE: str = "ensemble_aggressive"  # ensemble, ensemble_aggressive, mean_reversion, breakout, trend_following, ensemble_ultra
    REQUIRE_MTF_ALIGNMENT: bool = True  # True = conservador (exige alinhamento), False = agressivo
    
    # Risk Management
    RISK_PER_TRADE: Decimal = Decimal("0.015")  # 1.2% of equity per trade
    MAX_OPEN_TRADES: int = 6
    MAX_DRAWDOWN_PERCENT: Decimal = Decimal("0.18")  # 15% circuit breaker
    MAX_DAILY_LOSS_PERCENT: Decimal = Decimal("0.035")  # 3.5% daily loss limit
    
    # Position Sizing
    MIN_POSITION_SIZE_USD: Decimal = Decimal("10.0")
    MAX_POSITION_SIZE_USD: Decimal = Decimal("10000.0")
    
    # Stop Loss / Take Profit
    STOP_LOSS_PERCENT: Decimal = Decimal("0.025")
    TAKE_PROFIT_PERCENT: Decimal = Decimal("0.04")
    USE_TRAILING_STOP: bool = True
    TRAILING_STOP_ATR_MULTIPLIER: Decimal = Decimal("2.0")

    # 🆕 TAKE PROFIT PARCIAL (Melhor Profit Factor!)
    USE_PARTIAL_TAKE_PROFIT: bool = True
    # Formato: (% do caminho até TP, % da posição a fechar)
    # Exemplo: (0.5, 0.3) = Quando chegar 50% do TP, fecha 30% da posição
    TP1_PERCENT: float = 0.5   # 50% do caminho
    TP1_QUANTITY: float = 0.3  # Fecha 30%
    TP2_PERCENT: float = 0.75  # 75% do caminho
    TP2_QUANTITY: float = 0.4  # Fecha 40%
    TP3_QUANTITY: float = 0.3  # Fecha 30% restante

    # 🆕 POSITION SIZING DINÂMICO (Maior Retorno!)
    USE_DYNAMIC_POSITION_SIZING: bool = True
    # Multiplicadores de risco baseados na força do sinal
    RISK_MULTIPLIER_VERY_STRONG: float = 1.5   # Signal >= 0.8 → 3% risk
    RISK_MULTIPLIER_STRONG: float = 1.25       # Signal >= 0.6 → 2.5% risk
    RISK_MULTIPLIER_MEDIUM: float = 1.0        # Signal >= 0.4 → 2% risk
    RISK_MULTIPLIER_WEAK: float = 0.75         # Signal < 0.4 → 1.5% risk
    
    # Fees and Slippage
    MAKER_FEE: Decimal = Decimal("0.001")  # 0.1%
    TAKER_FEE: Decimal = Decimal("0.001")  # 0.1%
    SLIPPAGE_PERCENT: Decimal = Decimal("0.001")  # 0.1%
    
    # Database
    DATABASE_URL: str = Field(
        default="sqlite:///db/state.db",
        env="DATABASE_URL"
    )
    
    # Backtest Configuration
    # BACKTEST_START_DATE: str = "2024-01-01"
    # BACKTEST_END_DATE: str = "2024-10-22"
    BACKTEST_START_DATE: str = f"{hoje.year}-01-01"
    BACKTEST_END_DATE: str = hoje.strftime("%Y-%m-%d")

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
    RATE_LIMIT_BUFFER: float = 0.8  # Use 80% of limit
    
    # Retry Configuration
    MAX_RETRIES: int = 5
    RETRY_DELAY_SECONDS: float = 1.0
    RETRY_BACKOFF_MULTIPLIER: float = 2.0
    
    # Mode Control
    TESTNET_MODE: bool = False
    DRY_RUN: bool = False  # Simulate trades without execution
    
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
        # Keys are optional at init, validated when live mode starts
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
            if abs(total - 1.0) > 0.01:  # Tolerância de 1%
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
        
        # Create db directory
        db_dir = Path("db")
        db_dir.mkdir(parents=True, exist_ok=True)
    
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
            
            if abs(time_diff) > 60:  # Mais de 1 minuto de diferença
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