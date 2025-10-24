"""
Backtesting engine for strategy simulation
Candle-by-candle execution with realistic fees and slippage
"""

import logging
from typing import List, Dict, Optional, Tuple
from decimal import Decimal
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path
import json

from core.exchange import BinanceExchange
from core.risk import RiskManager
from core.strategy import StrategyFactory, MultiTimeframeAnalyzer
from core.utils import (
    calculate_sharpe_ratio, calculate_sortino_ratio,
    calculate_max_drawdown, format_percentage, safe_decimal
)


class BacktestTrade:
    """Represents a trade in backtest with partial take profit support"""
    
    def __init__(
        self,
        symbol: str,
        side: str,
        entry_price: Decimal,
        quantity: Decimal,
        entry_time: datetime,
        stop_loss: Decimal,
        take_profit: Decimal
    ):
        self.symbol = symbol
        self.side = side
        self.entry_price = entry_price
        self.initial_quantity = quantity  # Guarda quantidade inicial
        self.quantity = quantity  # Quantidade atual
        self.entry_time = entry_time
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        
        # Take Profit Parcial (3 níveis)
        distance = abs(take_profit - entry_price)
        if side == 'BUY':
            self.tp1 = entry_price + (distance * Decimal('0.5'))  # 50% do caminho
            self.tp2 = entry_price + (distance * Decimal('0.75'))  # 75% do caminho
            self.tp3 = take_profit  # 100%
        else:  # SELL
            self.tp1 = entry_price - (distance * Decimal('0.5'))
            self.tp2 = entry_price - (distance * Decimal('0.75'))
            self.tp3 = take_profit
        
        self.tp1_hit = False
        self.tp2_hit = False
        self.tp3_hit = False
        
        self.exit_price: Optional[Decimal] = None
        self.exit_time: Optional[datetime] = None
        self.pnl: Decimal = Decimal('0')
        self.pnl_percent: float = 0.0
        self.fees: Decimal = Decimal('0')
        self.status: str = 'OPEN'
        self.exit_reason: str = ''
        self.partial_exits: List[Dict] = []  # Histórico de saídas parciais
    
    def check_partial_tp(
        self,
        current_price: Decimal,
        current_time: datetime,
        fee_rate: Decimal
    ) -> Optional[str]:
        """
        Check and execute partial take profits
        Returns: 'TP1', 'TP2', 'TP3', or None
        """
        if self.quantity <= 0:
            return None
        
        hit_tp = None
        quantity_to_close = Decimal('0')
        
        # Check TP1 (30% position)
        if not self.tp1_hit:
            if (self.side == 'BUY' and current_price >= self.tp1) or \
               (self.side == 'SELL' and current_price <= self.tp1):
                self.tp1_hit = True
                quantity_to_close = self.initial_quantity * Decimal('0.3')
                hit_tp = 'TP1'
        
        # Check TP2 (40% position)
        elif not self.tp2_hit:
            if (self.side == 'BUY' and current_price >= self.tp2) or \
               (self.side == 'SELL' and current_price <= self.tp2):
                self.tp2_hit = True
                quantity_to_close = self.initial_quantity * Decimal('0.4')
                hit_tp = 'TP2'
        
        # Check TP3 (30% remaining)
        elif not self.tp3_hit:
            if (self.side == 'BUY' and current_price >= self.tp3) or \
               (self.side == 'SELL' and current_price <= self.tp3):
                self.tp3_hit = True
                quantity_to_close = self.quantity  # Resto
                hit_tp = 'TP3'
        
        if hit_tp and quantity_to_close > 0:
            # Calculate partial PnL
            if self.side == 'BUY':
                partial_pnl = (current_price - self.entry_price) * quantity_to_close
            else:
                partial_pnl = (self.entry_price - current_price) * quantity_to_close
            
            # Calculate partial fees
            entry_value = self.entry_price * quantity_to_close
            exit_value = current_price * quantity_to_close
            partial_fees = (entry_value + exit_value) * fee_rate
            
            # Net partial PnL
            partial_pnl -= partial_fees
            
            # Update totals
            self.pnl += partial_pnl
            self.fees += partial_fees
            self.quantity -= quantity_to_close
            
            # Record partial exit
            self.partial_exits.append({
                'time': current_time,
                'price': current_price,
                'quantity': quantity_to_close,
                'pnl': partial_pnl,
                'level': hit_tp
            })
            
            # If all closed, mark as complete
            if self.quantity <= Decimal('0.0001'):
                self.status = 'CLOSED'
                self.exit_price = current_price
                self.exit_time = current_time
                self.exit_reason = 'TAKE_PROFIT_FULL'
                
                # Calculate final PnL percentage
                total_entry_value = self.entry_price * self.initial_quantity
                self.pnl_percent = float((self.pnl / total_entry_value) * 100)
            
            return hit_tp
        
        return None
    
    def close(
        self,
        exit_price: Decimal,
        exit_time: datetime,
        reason: str,
        fee_rate: Decimal
    ) -> None:
        """Close remaining position (stop loss or manual exit)"""
        if self.quantity <= 0:
            return
        
        self.exit_price = exit_price
        self.exit_time = exit_time
        self.exit_reason = reason
        self.status = 'CLOSED'
        
        # Calculate PnL for remaining quantity
        if self.side == 'BUY':
            remaining_pnl = (exit_price - self.entry_price) * self.quantity
        else:
            remaining_pnl = (self.entry_price - exit_price) * self.quantity
        
        # Calculate fees for remaining
        entry_value = self.entry_price * self.quantity
        exit_value = exit_price * self.quantity
        remaining_fees = (entry_value + exit_value) * fee_rate
        
        # Add to totals
        self.pnl += remaining_pnl - remaining_fees
        self.fees += remaining_fees
        
        # Calculate final PnL percentage
        total_entry_value = self.entry_price * self.initial_quantity
        self.pnl_percent = float((self.pnl / total_entry_value) * 100)
        
        self.quantity = Decimal('0')


class BacktestEngine:
    """Backtesting engine with realistic simulation"""
    
    def __init__(self, settings):
        """
        Initialize backtest engine
        
        Args:
            settings: Settings object with backtest configuration
        """
        self.settings = settings
        self.logger = logging.getLogger('TradingBot.Backtest')
        
        # Initialize components
        self.risk_manager = RiskManager(settings)
        self.strategy = StrategyFactory.create_strategy(settings.STRATEGY_MODE)
        self.mtf_analyzer = MultiTimeframeAnalyzer(
            primary_timeframe=settings.PRIMARY_TIMEFRAME,
            entry_timeframe=settings.ENTRY_TIMEFRAME,
            strategy=self.strategy,
            require_alignment=settings.REQUIRE_MTF_ALIGNMENT
        )
        
        # Backtest state
        self.capital = settings.BACKTEST_INITIAL_CAPITAL
        self.equity_curve: List[Decimal] = [self.capital]
        self.trades: List[BacktestTrade] = []
        self.open_trades: Dict[str, BacktestTrade] = {}
        self.daily_returns: List[float] = []
        
        self.logger.info("Backtest engine initialized")
    
    def load_data(
        self,
        symbol: str,
        timeframe: str,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """
        Load historical data for backtesting
        
        Args:
            symbol: Trading pair symbol
            timeframe: Timeframe (e.g., '1h', '4h')
            start_date: Start date string
            end_date: End date string
            
        Returns:
            DataFrame with OHLCV data
        """
        self.logger.info(
            f"Loading data for {symbol} ({timeframe}): {start_date} to {end_date}"
        )
        
        try:
            # Try to load from CSV first
            csv_path = (
                self.settings.DATA_DIR / 
                f"{symbol}_{timeframe}_{start_date}_{end_date}.csv"
            )
            
            if csv_path.exists():
                self.logger.info(f"Loading from CSV: {csv_path}")
                df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
                return df
            
            # Otherwise fetch from exchange
            self.logger.info("Fetching from Binance API...")
            
            # Use a dummy exchange connection (no API keys needed for public data)
            exchange = BinanceExchange("", "", testnet=False)
            
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            
            # Fetch data in chunks
            all_data = []
            current_start = start_dt
            
            while current_start < end_dt:
                chunk_end = min(
                    current_start + timedelta(days=30),
                    end_dt
                )
                
                chunk_df = exchange.get_klines(
                    symbol=symbol,
                    interval=timeframe,
                    start_time=current_start,
                    end_time=chunk_end,
                    limit=1000
                )
                
                all_data.append(chunk_df)
                current_start = chunk_end
                
                self.logger.info(f"Fetched data up to {current_start}")
            
            # Combine all chunks
            df = pd.concat(all_data)
            df = df[~df.index.duplicated(keep='first')]
            df.sort_index(inplace=True)
            
            # Save to CSV for future use
            csv_path.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(csv_path)
            self.logger.info(f"Saved data to {csv_path}")
            
            return df
            
        except Exception as e:
            self.logger.error(f"Failed to load data: {e}", exc_info=True)
            raise
    
    def run(self) -> Dict:
        """
        Run backtest simulation
        
        Returns:
            Dictionary with backtest results
        """
        self.logger.info("=" * 60)
        self.logger.info("STARTING BACKTEST")
        self.logger.info("=" * 60)
        
        results = {}
        
        for symbol in self.settings.TRADING_PAIRS:
            self.logger.info(f"\n📊 Backtesting {symbol}...")
            
            try:
                # Load data for both timeframes
                primary_df = self.load_data(
                    symbol,
                    self.settings.PRIMARY_TIMEFRAME,
                    self.settings.BACKTEST_START_DATE,
                    self.settings.BACKTEST_END_DATE
                )
                
                entry_df = self.load_data(
                    symbol,
                    self.settings.ENTRY_TIMEFRAME,
                    self.settings.BACKTEST_START_DATE,
                    self.settings.BACKTEST_END_DATE
                )
                
                # Run simulation
                self._simulate_trading(symbol, primary_df, entry_df)
                
            except Exception as e:
                self.logger.error(f"Error backtesting {symbol}: {e}", exc_info=True)
        
        # Calculate final results
        results = self._calculate_results()
        
        # Generate reports
        self._generate_reports(results)
        
        self.logger.info("\n" + "=" * 60)
        self.logger.info("BACKTEST COMPLETE")
        self.logger.info("=" * 60)
        
        return results
    
    def _simulate_trading(
        self,
        symbol: str,
        primary_df: pd.DataFrame,
        entry_df: pd.DataFrame
    ) -> None:
        """Simulate trading on historical data"""
        
        # Iterate through each candle
        for i in range(200, len(entry_df)):  # Start after enough history
            current_time = entry_df.index[i]
            current_candle = entry_df.iloc[i]
            
            # Get historical data up to current point
            primary_history = primary_df.loc[:current_time]
            entry_history = entry_df.loc[:current_time]
            
            # Update open trades
            if symbol in self.open_trades:
                self._update_trade(
                    symbol,
                    current_candle['high'],
                    current_candle['low'],
                    current_candle['close'],
                    current_time
                )
            
            # Check for new signals
            if symbol not in self.open_trades:
                signal, strength, metadata = self.mtf_analyzer.analyze(
                    primary_history.tail(500),
                    entry_history.tail(500)
                )
                
                if signal in ['BUY', 'SELL'] and strength > 0.4:  # Reduzido de 0.5 para 0.4 (20% mais permissivo)
                    self._open_trade(
                        symbol,
                        signal,
                        current_candle['close'],
                        current_time,
                        entry_history.tail(100),
                        strength=strength  # 🆕 PASSA A FORÇA!
                    )
            
            # Track equity
            current_equity = self._calculate_current_equity(
                current_candle['close']
            )
            self.equity_curve.append(current_equity)
    
    def _open_trade(
        self,
        symbol: str,
        side: str,
        price: Decimal,
        time: datetime,
        df: pd.DataFrame,
        strength: float = 0.5  # 🆕 ADICIONE ESTE PARÂMETRO

    ) -> None:
        """Open a new trade in backtest"""
        
        # Check if can open trade
        can_trade, reason = self.risk_manager.can_open_trade(
            len(self.open_trades)
        )
        
        if not can_trade:
            return
        
        # Calculate stops
        atr = self.mtf_analyzer.get_atr(df)
        
        stop_loss = self.risk_manager.calculate_stop_loss(
            entry_price=Decimal(str(price)),
            side=side,
            atr=atr,
            use_atr=bool(atr > 0)
        )
        
        take_profit = self.risk_manager.calculate_take_profit(
            entry_price=Decimal(str(price)),
            side=side
        )
        
        # Calculate position size
        # Use simplified filters for backtest
        filters = {
            'stepSize': Decimal('0.00001'),
            'minQty': Decimal('0.001'),
            'minNotional': Decimal('10'),
        }
        
        quantity = self.risk_manager.calculate_dynamic_position_size(
        capital=self.capital,
        entry_price=Decimal(str(price)),
        stop_loss_price=stop_loss,
        symbol_filters=filters,
        signal_strength=strength  # 🆕 USA A FORÇA DO SINAL!
        )
        
        if not quantity:
            return
        
        # Create trade
        trade = BacktestTrade(
            symbol=symbol,
            side=side,
            entry_price=Decimal(str(price)),
            quantity=quantity,
            entry_time=time,
            stop_loss=stop_loss,
            take_profit=take_profit
        )
        
        self.open_trades[symbol] = trade
        
        self.logger.info(
            f"  Aberto {side} trade: {quantity} {symbol} @ ${price} "
            f"(SL: ${stop_loss}, TP: ${take_profit})"
        )
    
    def _update_trade(
        self,
        symbol: str,
        high: float,
        low: float,
        close: float,
        time: datetime
    ) -> None:
        """Update open trade based on current candle"""
        
        trade = self.open_trades[symbol]
        
        # Check PARTIAL TAKE PROFITS first! 🆕
        tp_hit = trade.check_partial_tp(
            Decimal(str(close)),
            time,
            self.settings.TAKER_FEE
        )
        
        if tp_hit:
            self.logger.info(
                f"  💰 {tp_hit} acerto para {symbol}: Posição parcial fechada"
            )
            
            # If fully closed via TP3, remove from open trades
            if trade.status == 'FECHADO':
                self.open_trades.pop(symbol)
                self.capital += trade.pnl
                self.risk_manager.update_daily_pnl(trade.pnl)
                self.risk_manager.update_equity_tracking(self.capital)
                self.trades.append(trade)
                self.logger.info(
                    f"  ✅ Totalmente fechado via TPs parciais | "
                    f"Total PnL: ${trade.pnl:.2f} ({trade.pnl_percent:+.2f}%)"
                )
            return
        
        # Check stop loss (para quantidade restante)
        if trade.side == 'BUY' and low <= float(trade.stop_loss):
            exit_price = trade.stop_loss
            self._close_trade(symbol, exit_price, time, 'STOP_LOSS')
            return
        
        if trade.side == 'SELL' and high >= float(trade.stop_loss):
            exit_price = trade.stop_loss
            self._close_trade(symbol, exit_price, time, 'STOP_LOSS')
            return
        
        # Check take profit
        if trade.side == 'BUY' and high >= float(trade.take_profit):
            exit_price = trade.take_profit
            self._close_trade(symbol, exit_price, time, 'TAKE_PROFIT')
            return
        
        if trade.side == 'SELL' and low <= float(trade.take_profit):
            exit_price = trade.take_profit
            self._close_trade(symbol, exit_price, time, 'TAKE_PROFIT')
            return
    
    def _close_trade(
        self,
        symbol: str,
        exit_price: Decimal,
        exit_time: datetime,
        reason: str
    ) -> None:
        """Close trade in backtest"""
        
        trade = self.open_trades.pop(symbol)
        
        # Apply slippage
        slippage = exit_price * self.settings.SLIPPAGE_PERCENT
        if trade.side == 'BUY':
            exit_price -= slippage
        else:
            exit_price += slippage
        
        # Close trade
        trade.close(
            exit_price=exit_price,
            exit_time=exit_time,
            reason=reason,
            fee_rate=self.settings.TAKER_FEE
        )
        
        # Update capital
        self.capital += trade.pnl
        
        # Update risk manager
        self.risk_manager.update_daily_pnl(trade.pnl)
        self.risk_manager.update_equity_tracking(self.capital)
        
        # Store trade
        self.trades.append(trade)
        
        pnl_emoji = "✅" if trade.pnl > 0 else "❌"
        self.logger.info(
            f"  {pnl_emoji} Closed {trade.side} trade: {reason} | "
            f"PnL: ${trade.pnl:.2f} ({trade.pnl_percent:+.2f}%)"
        )
    
    def _calculate_current_equity(self, current_price: float) -> Decimal:
        """Calculate current total equity including open positions"""
        
        equity = self.capital
        
        for trade in self.open_trades.values():
            # Calculate unrealized PnL
            if trade.side == 'BUY':
                unrealized_pnl = (
                    Decimal(str(current_price)) - trade.entry_price
                ) * trade.quantity
            else:
                unrealized_pnl = (
                    trade.entry_price - Decimal(str(current_price))
                ) * trade.quantity
            
            equity += unrealized_pnl
        
        return equity
    
    def _calculate_results(self) -> Dict:
        """Calculate backtest performance metrics"""
        
        self.logger.info("\n📊 Calculating performance metrics...")
        
        # Basic stats
        total_trades = len(self.trades)
        winning_trades = len([t for t in self.trades if t.pnl > 0])
        losing_trades = len([t for t in self.trades if t.pnl < 0])
        
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        # PnL stats
        total_pnl = sum(t.pnl for t in self.trades)
        total_pnl_percent = (
            (self.capital - self.settings.BACKTEST_INITIAL_CAPITAL) / 
            self.settings.BACKTEST_INITIAL_CAPITAL * 100
        )
        
        wins = [float(t.pnl) for t in self.trades if t.pnl > 0]
        losses = [float(t.pnl) for t in self.trades if t.pnl < 0]
        
        avg_win = np.mean(wins) if wins else 0
        avg_loss = np.mean(losses) if losses else 0
        largest_win = max(wins) if wins else 0
        largest_loss = min(losses) if losses else 0
        
        # Profit factor
        total_wins = sum(wins) if wins else 0
        total_losses = abs(sum(losses)) if losses else 0
        profit_factor = (total_wins / total_losses) if total_losses > 0 else 0
        
        # Risk metrics
        returns = [
            float((self.equity_curve[i] - self.equity_curve[i-1]) / self.equity_curve[i-1])
            for i in range(1, len(self.equity_curve))
        ]
        
        sharpe = calculate_sharpe_ratio(returns)
        sortino = calculate_sortino_ratio(returns)
        
        equity_values = [float(e) for e in self.equity_curve]
        max_dd, peak_idx, trough_idx = calculate_max_drawdown(equity_values)
        
        results = {
            'initial_capital': float(self.settings.BACKTEST_INITIAL_CAPITAL),
            'final_capital': float(self.capital),
            'total_pnl': float(total_pnl),
            'total_pnl_percent': float(total_pnl_percent),
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'largest_win': largest_win,
            'largest_loss': largest_loss,
            'profit_factor': profit_factor,
            'sharpe_ratio': sharpe,
            'sortino_ratio': sortino,
            'max_drawdown': max_dd * 100,
            'equity_curve': equity_values,
        }
        
        return results
    
    def _generate_reports(self, results: Dict) -> None:
        """Generate backtest reports"""
        
        self.logger.info("\n📄 Generating reports...")
        
        # Print summary to console
        self._print_summary(results)
        
        # Generate charts
        self._generate_charts(results)
        
        # Save results to JSON
        self._save_json_report(results)
        
        # Save trades to CSV
        self._save_trades_csv()
        
        self.logger.info(f"\n✅ Reports saved to: {self.settings.REPORTS_DIR}")
    
    def _print_summary(self, results: Dict) -> None:
        """Print results summary"""
        
        print("\n" + "=" * 60)
        print("BACKTEST RESULTS")
        print("=" * 60)
        print(f"Strategy: {self.settings.STRATEGY_MODE}")
        print(f"Pairs: {', '.join(self.settings.TRADING_PAIRS)}")
        print(f"Period: {self.settings.BACKTEST_START_DATE} to {self.settings.BACKTEST_END_DATE}")
        print("-" * 60)
        print(f"Initial Capital: ${results['initial_capital']:,.2f}")
        print(f"Final Capital: ${results['final_capital']:,.2f}")
        print(f"Total PnL: ${results['total_pnl']:,.2f} ({results['total_pnl_percent']:+.2f}%)")
        print("-" * 60)
        print(f"Total Trades: {results['total_trades']}")
        print(f"Winning Trades: {results['winning_trades']}")
        print(f"Losing Trades: {results['losing_trades']}")
        print(f"Win Rate: {results['win_rate']:.2f}%")
        print("-" * 60)
        print(f"Average Win: ${results['avg_win']:,.2f}")
        print(f"Average Loss: ${results['avg_loss']:,.2f}")
        print(f"Largest Win: ${results['largest_win']:,.2f}")
        print(f"Largest Loss: ${results['largest_loss']:,.2f}")
        print(f"Profit Factor: {results['profit_factor']:.2f}")
        print("-" * 60)
        print(f"Sharpe Ratio: {results['sharpe_ratio']:.2f}")
        print(f"Sortino Ratio: {results['sortino_ratio']:.2f}")
        print(f"Max Drawdown: {results['max_drawdown']:.2f}%")
        print("=" * 60)
    
    def _generate_charts(self, results: Dict) -> None:
        """Generate equity curve and other charts"""
        
        fig, axes = plt.subplots(2, 1, figsize=(14, 10))
        
        # Equity curve
        ax1 = axes[0]
        ax1.plot(results['equity_curve'], linewidth=2, color='#2E86AB')
        ax1.axhline(
            y=results['initial_capital'],
            color='gray',
            linestyle='--',
            label='Initial Capital'
        )
        ax1.set_title('Equity Curve', fontsize=14, fontweight='bold')
        ax1.set_xlabel('Trade Number')
        ax1.set_ylabel('Equity ($)')
        ax1.grid(True, alpha=0.3)
        ax1.legend()
        
        # Trade PnL
        ax2 = axes[1]
        trade_pnls = [float(t.pnl) for t in self.trades]
        colors = ['green' if pnl > 0 else 'red' for pnl in trade_pnls]
        ax2.bar(range(len(trade_pnls)), trade_pnls, color=colors, alpha=0.6)
        ax2.axhline(y=0, color='black', linestyle='-', linewidth=0.8)
        ax2.set_title('Trade PnL', fontsize=14, fontweight='bold')
        ax2.set_xlabel('Trade Number')
        ax2.set_ylabel('PnL ($)')
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        chart_path = self.settings.REPORTS_DIR / 'backtest_equity_curve.png'
        plt.savefig(chart_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        self.logger.info(f"  Chart saved: {chart_path}")
    
    def _save_json_report(self, results: Dict) -> None:
        """Save results to JSON file"""
        
        report_path = self.settings.REPORTS_DIR / 'backtest_results.json'
        
        with open(report_path, 'w') as f:
            json.dump(results, f, indent=2)
        
        self.logger.info(f"  JSON report saved: {report_path}")
    
    def _save_trades_csv(self) -> None:
        """Save trade history to CSV"""
        
        trades_data = []
        
        for trade in self.trades:
            trades_data.append({
                'symbol': trade.symbol,
                'side': trade.side,
                'entry_price': float(trade.entry_price),
                'exit_price': float(trade.exit_price) if trade.exit_price else None,
                'quantity': float(trade.quantity),
                'entry_time': trade.entry_time,
                'exit_time': trade.exit_time,
                'pnl': float(trade.pnl),
                'pnl_percent': trade.pnl_percent,
                'fees': float(trade.fees),
                'exit_reason': trade.exit_reason,
            })
        
        df = pd.DataFrame(trades_data)
        
        csv_path = self.settings.REPORTS_DIR / 'backtest_trades.csv'
        df.to_csv(csv_path, index=False)
        
        self.logger.info(f"  Trades CSV saved: {csv_path}")