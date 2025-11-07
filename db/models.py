"""
Database models for persistent state management
SQLAlchemy ORM models for trades, orders, and performance tracking
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, DateTime,
    Boolean, Text, ForeignKey, Index, Numeric
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker, Session
from sqlalchemy.pool import StaticPool

Base = declarative_base()


class Trade(Base):
    """Trade record model"""
    __tablename__ = 'trades'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Trade identification
    symbol = Column(String(20), nullable=False, index=True)
    side = Column(String(10), nullable=False)  # BUY or SELL
    trade_type = Column(String(20), default='SPOT')  # SPOT, MARGIN, FUTURES
    
    # Trade details
    entry_price = Column(Numeric(20, 8), nullable=False)
    exit_price = Column(Numeric(20, 8), nullable=True)
    quantity = Column(Numeric(20, 8), nullable=False)
    
    # Stop loss and take profit
    stop_loss = Column(Numeric(20, 8), nullable=True)
    take_profit = Column(Numeric(20, 8), nullable=True)
    trailing_stop = Column(Numeric(20, 8), nullable=True)
    
    # Status and timing
    status = Column(String(20), default='OPEN', index=True)  # OPEN, CLOSED, CANCELLED
    entry_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    exit_time = Column(DateTime, nullable=True)
    
    # Performance metrics
    pnl = Column(Numeric(20, 8), default=0)
    pnl_percent = Column(Float, default=0.0)
    fees = Column(Numeric(20, 8), default=0)
    
    # Risk metrics
    risk_amount = Column(Numeric(20, 8), nullable=True)
    risk_reward_ratio = Column(Float, nullable=True)
    
    # Strategy information
    strategy = Column(String(50), nullable=True)
    timeframe = Column(String(10), nullable=True)
    signal_strength = Column(Float, nullable=True)
    
    # Notes and metadata
    notes = Column(Text, nullable=True)
    exchange_order_id = Column(String(50), unique=True, nullable=True, index=True)
    client_order_id = Column(String(50), unique=True, nullable=True, index=True)
    actual_entry_price = Column(Numeric(20, 8), nullable=True)
    actual_quantity = Column(Numeric(20, 8), nullable=True)
    partial_exits = Column(Text, nullable=True)  # JSON
    actual_fees = Column(Numeric(20, 8), nullable=True)
    reconciled_at = Column(DateTime, nullable=True)
    trade_metadata = Column(Text, nullable=True)  # JSON string (renamed from 'metadata')
    
    # Mode
    mode = Column(String(20), default='live')  # live, testnet, backtest
    
    # Relationships
    orders = relationship("Order", back_populates="trade", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_trade_symbol_status', 'symbol', 'status'),
        Index('idx_entry_time', 'entry_time'),
        Index('idx_mode', 'mode'),
    )
    
    def __repr__(self):
        return (
            f"<Trade(id={self.id}, symbol={self.symbol}, side={self.side}, "
            f"status={self.status}, pnl={self.pnl})>"
        )


class Order(Base):
    """Order record model"""
    __tablename__ = 'orders'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Order identification
    trade_id = Column(Integer, ForeignKey('trades.id'), nullable=True)
    exchange_order_id = Column(String(50), unique=True, index=True)
    client_order_id = Column(String(50), unique=True, index=True)
    
    # Order details
    symbol = Column(String(20), nullable=False, index=True)
    side = Column(String(10), nullable=False)  # BUY or SELL
    order_type = Column(String(20), nullable=False)  # MARKET, LIMIT, STOP_LOSS, etc.
    
    # Pricing and quantity
    price = Column(Numeric(20, 8), nullable=True)
    stop_price = Column(Numeric(20, 8), nullable=True)
    quantity = Column(Numeric(20, 8), nullable=False)
    executed_quantity = Column(Numeric(20, 8), default=0)
    
    # Status
    status = Column(String(20), default='NEW', index=True)  # NEW, FILLED, CANCELLED, etc.
    time_in_force = Column(String(10), default='GTC')  # GTC, IOC, FOK
    
    # Timing
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Execution details
    avg_price = Column(Numeric(20, 8), nullable=True)
    commission = Column(Numeric(20, 8), default=0)
    commission_asset = Column(String(10), default='USDT')
    
    # Mode
    mode = Column(String(20), default='live')
    
    # Relationships
    trade = relationship("Trade", back_populates="orders")
    fills = relationship("Fill", back_populates="order", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_order_symbol_status', 'symbol', 'status'),
        Index('idx_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return (
            f"<Order(id={self.id}, symbol={self.symbol}, side={self.side}, "
            f"status={self.status}, quantity={self.quantity})>"
        )


class Fill(Base):
    """Fill (execution) record model"""
    __tablename__ = 'fills'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Fill identification
    order_id = Column(Integer, ForeignKey('orders.id'), nullable=False)
    exchange_fill_id = Column(String(50), index=True)
    
    # Fill details
    price = Column(Numeric(20, 8), nullable=False)
    quantity = Column(Numeric(20, 8), nullable=False)
    commission = Column(Numeric(20, 8), default=0)
    commission_asset = Column(String(10), default='USDT')
    
    # Timing
    filled_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    order = relationship("Order", back_populates="fills")
    
    def __repr__(self):
        return (
            f"<Fill(id={self.id}, price={self.price}, "
            f"quantity={self.quantity})>"
        )


class Balance(Base):
    """Account balance snapshot model"""
    __tablename__ = 'balances'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Balance details
    asset = Column(String(10), nullable=False, index=True)
    free = Column(Numeric(20, 8), nullable=False)
    locked = Column(Numeric(20, 8), default=0)
    total = Column(Numeric(20, 8), nullable=False)
    
    # USD value (if applicable)
    usd_value = Column(Numeric(20, 2), nullable=True)
    
    # Timing
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Mode
    mode = Column(String(20), default='live')
    
    __table_args__ = (
        Index('idx_asset_timestamp', 'asset', 'timestamp'),
    )
    
    def __repr__(self):
        return f"<Balance(asset={self.asset}, total={self.total}, timestamp={self.timestamp})>"


class Performance(Base):
    """Performance metrics snapshot model"""
    __tablename__ = 'performance'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Period identification
    date = Column(DateTime, nullable=False, index=True)
    period = Column(String(20), default='daily')  # daily, weekly, monthly
    
    # Equity metrics
    starting_equity = Column(Numeric(20, 2), nullable=False)
    ending_equity = Column(Numeric(20, 2), nullable=False)
    peak_equity = Column(Numeric(20, 2), nullable=False)
    
    # Performance metrics
    total_pnl = Column(Numeric(20, 2), default=0)
    total_pnl_percent = Column(Float, default=0.0)
    
    # Trade statistics
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    win_rate = Column(Float, default=0.0)
    
    # Risk metrics
    sharpe_ratio = Column(Float, nullable=True)
    sortino_ratio = Column(Float, nullable=True)
    max_drawdown = Column(Float, default=0.0)
    max_drawdown_duration = Column(Integer, default=0)  # in periods
    
    # Profit metrics
    profit_factor = Column(Float, nullable=True)
    avg_win = Column(Numeric(20, 2), default=0)
    avg_loss = Column(Numeric(20, 2), default=0)
    largest_win = Column(Numeric(20, 2), default=0)
    largest_loss = Column(Numeric(20, 2), default=0)
    
    # Mode
    mode = Column(String(20), default='live')
    
    __table_args__ = (
        Index('idx_date_period', 'date', 'period'),
    )
    
    def __repr__(self):
        return (
            f"<Performance(date={self.date}, total_pnl={self.total_pnl}, "
            f"win_rate={self.win_rate})>"
        )


class Config(Base):
    """Configuration storage model"""
    __tablename__ = 'config'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=True)
    value_type = Column(String(20), default='string')  # string, int, float, bool, json
    
    description = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<Config(key={self.key}, value={self.value})>"


class DatabaseManager:
    """Database manager for handling connections and sessions"""
    
    def __init__(self, database_url: str):
        """
        Initialize database manager
        
        Args:
            database_url: SQLAlchemy database URL
        """
        # Special handling for SQLite
        if database_url.startswith('sqlite'):
            self.engine = create_engine(
                database_url,
                connect_args={'check_same_thread': False},
                poolclass=StaticPool,
                echo=False
            )
        else:
            self.engine = create_engine(database_url, echo=False)
        
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )
        
        # Create all tables
        Base.metadata.create_all(bind=self.engine)
    
    def get_session(self) -> Session:
        """Get a new database session"""
        return self.SessionLocal()
    
    def close(self) -> None:
        """Close the database connection"""
        self.engine.dispose()


def init_database(database_url: str) -> DatabaseManager:
    """
    Initialize database and return manager
    
    Args:
        database_url: SQLAlchemy database URL
        
    Returns:
        DatabaseManager instance
    """
    return DatabaseManager(database_url)