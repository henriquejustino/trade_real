# 🤖 Professional Binance Trading Bot

A production-ready, multi-strategy cryptocurrency trading bot for Binance with backtesting, testnet simulation, and live trading capabilities.

## ✨ Features

- **🎯 Multiple Trading Modes**
  - Backtest mode with historical data analysis
  - Testnet mode for risk-free testing
  - Live trading with real capital

- **📊 Advanced Strategies**
  - Mean Reversion (Bollinger Bands + RSI)
  - Breakout (Donchian Channels + Volume)
  - Trend Following (EMA crossover + MACD)
  - Ensemble (weighted combination of all strategies)

- **🛡️ Risk Management**
  - Position sizing based on account risk
  - ATR-based trailing stops
  - Circuit breaker for drawdown protection
  - Daily loss limits

- **📈 Multi-Timeframe Analysis**
  - Top-down trend analysis
  - Multiple pairs concurrent trading
  - Configurable timeframes

- **💾 Persistent State**
  - SQLite/PostgreSQL database
  - Automatic reconciliation with exchange
  - Complete trade history

- **🔔 Notifications**
  - Telegram alerts
  - Slack webhooks
  - Detailed logging

- **🐳 Docker Support**
  - Fully containerized
  - Easy deployment
  - Consistent environments

## 📋 Requirements

- Python 3.11+
- Binance account with API keys
- (Optional) PostgreSQL database

## 🚀 Quick Start

### 1. Clone Repository

```bash
git clone <repository-url>
cd binance_trading_bot
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

Copy the example environment file and add your API keys:

```bash
cp config/.env.example .env
```

Edit `.env` and add your credentials:

```env
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here
TESTNET_API_KEY=your_testnet_key_here
TESTNET_API_SECRET=your_testnet_secret_here
```

### 4. Run the Bot

```bash
python bot_main.py
```

You'll see an interactive menu:

```
==============================
     BINANCE TRADING BOT
==============================
Select operation mode:
1 - Backtest
2 - Testnet
3 - Live
==============================
Choose an option: _
```

## 🔧 Configuration

Edit `config/settings.py` or set environment variables to customize:

### Trading Parameters

```python
TRADING_PAIRS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
PRIMARY_TIMEFRAME = "4h"
ENTRY_TIMEFRAME = "1h"
STRATEGY_MODE = "ensemble"  # or mean_reversion, breakout, trend_following
```

### Risk Management

```python
RISK_PER_TRADE = 0.02  # 2% of capital per trade
MAX_OPEN_TRADES = 4
MAX_DRAWDOWN_PERCENT = 0.15  # 15% circuit breaker
STOP_LOSS_PERCENT = 0.02  # 2% stop loss
TAKE_PROFIT_PERCENT = 0.04  # 4% take profit
```

### Backtesting

```python
BACKTEST_START_DATE = "2024-01-01"
BACKTEST_END_DATE = "2024-12-31"
BACKTEST_INITIAL_CAPITAL = 10000
```

## 📊 Operation Modes

### 1. Backtest Mode

Simulate strategy performance using historical data:

- Loads OHLCV data from Binance or CSV files
- Simulates fees, slippage, and market impact
- Generates comprehensive performance reports
- Exports results to CSV, HTML, and PDF

**Output:**
- Equity curve charts
- Performance metrics (Sharpe ratio, win rate, max drawdown)
- Trade-by-trade analysis
- Reports saved in `reports/` directory

### 2. Testnet Mode

Practice trading with fake money on Binance Testnet:

- Connects to https://testnet.binance.vision
- Places test orders without real capital
- Full reconciliation with database
- Real-time notifications

**Setup:**
1. Get testnet API keys from https://testnet.binance.vision/
2. Add keys to `.env` file
3. Select option "2" when running bot

### 3. Live Mode

Trade with real capital on Binance:

- Requires confirmation before starting
- Places real market orders
- Tracks fills and reconciles positions
- Circuit breaker protection
- Comprehensive logging and alerts

**⚠️ WARNING:** Live mode uses real money. Start with small amounts and test thoroughly in testnet first!

## 🗄️ Database Schema

The bot maintains persistent state in SQLite (or PostgreSQL):

### Tables

- **trades**: Complete trade records with entry/exit and PnL
- **orders**: Individual order details and execution
- **fills**: Granular fill information
- **balances**: Account balance snapshots
- **performance**: Daily/weekly/monthly performance metrics
- **config**: Runtime configuration storage

### Auto Reconciliation

On startup, the bot:
1. Loads local database state
2. Fetches current positions from Binance
3. Reconciles any differences
4. Updates database to match exchange

## 📈 Strategy Details

### Mean Reversion
- **Indicators**: Bollinger Bands (20, 2σ), RSI (14)
- **Entry**: Price touches lower band + RSI < 30 (buy) or upper band + RSI > 70 (sell)
- **Best For**: Ranging markets with clear support/resistance

### Breakout
- **Indicators**: Donchian Channels (20), Volume
- **Entry**: Price breaks 20-period high/low with volume > 1.5x average
- **Best For**: Volatile markets with strong directional moves

### Trend Following
- **Indicators**: EMA (12/26/200), MACD, ADX
- **Entry**: EMA crossover above 200 EMA with MACD confirmation
- **Best For**: Strong trending markets

### Ensemble
- **Method**: Weighted voting from all strategies
- **Weights**: Mean Reversion (30%), Breakout (30%), Trend Following (40%)
- **Best For**: All market conditions (most robust)

## 🔔 Notifications

### Telegram Setup

1. Create a bot with [@BotFather](https://t.me/botfather)
2. Get your chat ID from [@userinfobot](https://t.me/userinfobot)
3. Add to `.env`:

```env
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### Slack Setup

1. Create an incoming webhook in your Slack workspace
2. Add to `.env`:

```env
SLACK_ENABLED=true
SLACK_WEBHOOK_URL=your_webhook_url
```

## 🐳 Docker Deployment

### Build and Run

```bash
docker-compose up -d
```

### View Logs

```bash
docker-compose logs -f trading-bot
```

### Stop Bot

```bash
docker-compose down
```

### Using PostgreSQL

Uncomment the PostgreSQL service in `docker-compose.yml` and update `DATABASE_URL`:

```env
DATABASE_URL=postgresql://trader:password@postgres:5432/trading_bot
```

## 🧪 Testing

Run unit tests:

```bash
pytest tests/ -v
```

Run with coverage:

```bash
pytest tests/ --cov=core --cov-report=html
```

## 📁 Project Structure

```
binance_trading_bot/
├── core/
│   ├── exchange.py          # Binance API integration
│   ├── risk.py              # Risk management
│   ├── strategy.py          # Trading strategies
│   ├── trade_manager.py     # Order and position management
│   ├── backtest.py          # Backtesting engine
│   └── utils.py             # Utility functions
├── db/
│   ├── models.py            # Database models
│   └── state.db             # SQLite database
├── config/
│   ├── settings.py          # Configuration
│   └── .env.example         # Environment template
├── data/                    # Historical data storage
├── reports/                 # Backtest reports and logs
├── tests/                   # Unit tests
├── bot_main.py              # Main entry point
├── requirements.txt         # Python dependencies
├── Dockerfile               # Docker configuration
├── docker-compose.yml       # Docker Compose setup
└── README.md                # This file
```

## ⚠️ Important Notes

### Security

- **Never commit `.env` file** to version control
- API secrets are never logged or printed
- Use IP restrictions on Binance API keys
- Start with read-only keys for testing

### Best Practices

1. **Always backtest first** before live trading
2. **Test on testnet** to verify behavior
3. **Start with small capital** in live mode
4. **Monitor daily** and adjust as needed
5. **Keep API keys secure** and rotate regularly

### Limitations

- Designed for spot trading only (not margin/futures)
- Requires stable internet connection
- Subject to Binance API rate limits
- Past performance doesn't guarantee future results

## 📞 Support

For issues or questions:

1. Check the logs in `reports/logs/`
2. Review Binance API status
3. Verify your configuration in `.env`
4. Check database integrity

## 📜 License

This project is for educational purposes. Use at your own risk. The authors are not responsible for any financial losses.

## 🗺️ Roadmap

See [ROADMAP.md](ROADMAP.md) for planned features and improvements.

## 📝 Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history and updates.

---

**⚡ Happy Trading! Remember: Never risk more than you can afford to lose.**