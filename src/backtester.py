"""
Backtesting module to test strategy on historical data
"""
import pandas as pd
import pandas_ta as ta
from datetime import datetime, timedelta
from typing import Dict, List
import yfinance as yf

class Backtester:
    """Backtest trading strategy on historical data"""
    
    def __init__(self, 
                 initial_capital: float = 100000,
                 rsi_oversold: float = 15,
                 rsi_overbought: float = 65,
                 position_size_pct: float = 10):
        """
        Initialize backtester
        
        Args:
            initial_capital: Starting capital for backtest
            rsi_oversold: RSI-2 entry threshold
            rsi_overbought: RSI-2 exit threshold
            position_size_pct: % of capital per position
        """
        self.initial_capital = initial_capital
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.position_size_pct = position_size_pct
    
    def run_backtest(self, symbols: List[str], start_date: str, end_date: str) -> Dict:
        """
        Run backtest on list of symbols
        
        Args:
            symbols: List of stock symbols to test
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
        
        Returns:
            Dictionary with backtest results and statistics
        """
        all_trades = []
        
        for symbol in symbols:
            try:
                trades = self._backtest_symbol(symbol, start_date, end_date)
                all_trades.extend(trades)
            except Exception as e:
                print(f"Error backtesting {symbol}: {e}")
                continue
        
        # Calculate statistics
        stats = self._calculate_statistics(all_trades)
        
        return {
            'trades': all_trades,
            'statistics': stats,
            'start_date': start_date,
            'end_date': end_date,
            'symbols_tested': symbols,
            'initial_capital': self.initial_capital
        }
    
    def _backtest_symbol(self, symbol: str, start_date: str, end_date: str) -> List[Dict]:
        """Backtest strategy on a single symbol"""
        # Download historical data
        ticker = yf.Ticker(symbol)
        hist = ticker.history(start=start_date, end=end_date)
        
        if len(hist) < 250:  # Need enough data for 200-day SMA
            return []
        
        # Calculate indicators
        hist['SMA_200'] = hist['Close'].rolling(window=200).mean()
        hist['RSI_2'] = ta.rsi(hist['Close'], length=2)
        hist['ATR_14'] = ta.atr(hist['High'], hist['Low'], hist['Close'], length=14)
        
        # Remove NaN values
        hist = hist.dropna()
        
        trades = []
        position = None
        
        for i in range(len(hist)):
            date = hist.index[i]
            row = hist.iloc[i]
            
            if position is None:
                # Check for entry signal
                in_uptrend = row['Close'] > row['SMA_200']
                is_oversold = row['RSI_2'] < self.rsi_oversold
                
                if in_uptrend and is_oversold:
                    # Enter position
                    entry_price = row['Close']
                    stop_loss = entry_price - (2 * row['ATR_14'])
                    
                    # Calculate position size
                    risk_per_share = entry_price - stop_loss
                    position_value = self.initial_capital * (self.position_size_pct / 100)
                    shares = int(position_value / entry_price)
                    
                    position = {
                        'symbol': symbol,
                        'entry_date': date,
                        'entry_price': entry_price,
                        'shares': shares,
                        'stop_loss': stop_loss,
                        'entry_index': i
                    }
            else:
                # Check for exit signal
                exit_reason = None
                exit_price = row['Close']
                
                # Stop loss
                if row['Low'] <= position['stop_loss']:
                    exit_reason = 'STOP_LOSS'
                    exit_price = position['stop_loss']
                
                # RSI overbought
                elif row['RSI_2'] > self.rsi_overbought:
                    exit_reason = 'RSI_OVERBOUGHT'
                
                # Max holding period (10 days)
                elif i - position['entry_index'] >= 10:
                    exit_reason = 'MAX_DAYS'
                
                if exit_reason:
                    # Exit position
                    profit = (exit_price - position['entry_price']) * position['shares']
                    profit_pct = ((exit_price - position['entry_price']) / position['entry_price']) * 100
                    
                    trades.append({
                        'symbol': symbol,
                        'entry_date': position['entry_date'].strftime('%Y-%m-%d'),
                        'exit_date': date.strftime('%Y-%m-%d'),
                        'entry_price': round(position['entry_price'], 2),
                        'exit_price': round(exit_price, 2),
                        'shares': position['shares'],
                        'profit_loss': round(profit, 2),
                        'profit_loss_pct': round(profit_pct, 2),
                        'exit_reason': exit_reason,
                        'days_held': (date - position['entry_date']).days
                    })
                    
                    position = None
        
        return trades
    
    def _calculate_statistics(self, trades: List[Dict]) -> Dict:
        """Calculate backtest statistics"""
        if not trades:
            return {
                'total_trades': 0,
                'error': 'No trades generated'
            }
        
        total_trades = len(trades)
        winning_trades = [t for t in trades if t['profit_loss'] > 0]
        losing_trades = [t for t in trades if t['profit_loss'] <= 0]
        
        num_winners = len(winning_trades)
        num_losers = len(losing_trades)
        
        win_rate = (num_winners / total_trades * 100) if total_trades > 0 else 0
        
        total_profit = sum(t['profit_loss'] for t in trades)
        avg_profit = total_profit / total_trades if total_trades > 0 else 0
        
        avg_winner = sum(t['profit_loss'] for t in winning_trades) / num_winners if num_winners > 0 else 0
        avg_loser = sum(t['profit_loss'] for t in losing_trades) / num_losers if num_losers > 0 else 0
        
        profit_factor = abs(sum(t['profit_loss'] for t in winning_trades) / sum(t['profit_loss'] for t in losing_trades)) if losing_trades and sum(t['profit_loss'] for t in losing_trades) != 0 else 0
        
        avg_days_held = sum(t['days_held'] for t in trades) / total_trades if total_trades > 0 else 0
        
        # Calculate max consecutive wins/losses
        consecutive_wins = self._max_consecutive(trades, True)
        consecutive_losses = self._max_consecutive(trades, False)
        
        # Calculate max drawdown
        cumulative_pnl = []
        running_total = 0
        for trade in trades:
            running_total += trade['profit_loss']
            cumulative_pnl.append(running_total)
        
        max_drawdown = self._calculate_max_drawdown(cumulative_pnl)
        
        return {
            'total_trades': total_trades,
            'winning_trades': num_winners,
            'losing_trades': num_losers,
            'win_rate_pct': round(win_rate, 2),
            'total_profit_loss': round(total_profit, 2),
            'avg_profit_per_trade': round(avg_profit, 2),
            'avg_winner': round(avg_winner, 2),
            'avg_loser': round(avg_loser, 2),
            'profit_factor': round(profit_factor, 2),
            'avg_days_held': round(avg_days_held, 1),
            'max_consecutive_wins': consecutive_wins,
            'max_consecutive_losses': consecutive_losses,
            'max_drawdown': round(max_drawdown, 2),
            'return_on_capital_pct': round((total_profit / self.initial_capital) * 100, 2)
        }
    
    def _max_consecutive(self, trades: List[Dict], winners: bool) -> int:
        """Calculate max consecutive wins or losses"""
        max_consecutive = 0
        current_consecutive = 0
        
        for trade in trades:
            is_winner = trade['profit_loss'] > 0
            
            if is_winner == winners:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0
        
        return max_consecutive
    
    def _calculate_max_drawdown(self, cumulative_pnl: List[float]) -> float:
        """Calculate maximum drawdown from cumulative P&L"""
        if not cumulative_pnl:
            return 0
        
        peak = cumulative_pnl[0]
        max_dd = 0
        
        for value in cumulative_pnl:
            if value > peak:
                peak = value
            dd = peak - value
            if dd > max_dd:
                max_dd = dd
        
        return max_dd
    
    def generate_report(self, backtest_results: Dict) -> str:
        """Generate human-readable backtest report"""
        stats = backtest_results['statistics']
        
        report = f"""
========================================
BACKTEST REPORT
========================================
Period: {backtest_results['start_date']} to {backtest_results['end_date']}
Symbols: {', '.join(backtest_results['symbols_tested'])}
Initial Capital: ${backtest_results['initial_capital']:,.2f}

PERFORMANCE SUMMARY
========================================
Total Trades: {stats['total_trades']}
Winning Trades: {stats['winning_trades']}
Losing Trades: {stats['losing_trades']}
Win Rate: {stats['win_rate_pct']:.2f}%

Total P&L: ${stats['total_profit_loss']:,.2f}
Return on Capital: {stats['return_on_capital_pct']:.2f}%
Average P&L per Trade: ${stats['avg_profit_per_trade']:,.2f}

Average Winner: ${stats['avg_winner']:,.2f}
Average Loser: ${stats['avg_loser']:,.2f}
Profit Factor: {stats['profit_factor']:.2f}

TRADE METRICS
========================================
Average Days Held: {stats['avg_days_held']:.1f}
Max Consecutive Wins: {stats['max_consecutive_wins']}
Max Consecutive Losses: {stats['max_consecutive_losses']}
Max Drawdown: ${stats['max_drawdown']:,.2f}

RECENT TRADES (Last 5)
========================================
"""
        
        # Add last 5 trades
        for trade in backtest_results['trades'][-5:]:
            report += f"\n{trade['symbol']}: {trade['entry_date']} -> {trade['exit_date']}"
            report += f"\n  Entry: ${trade['entry_price']} | Exit: ${trade['exit_price']}"
            report += f"\n  P&L: ${trade['profit_loss']:.2f} ({trade['profit_loss_pct']:.2f}%)"
            report += f"\n  Reason: {trade['exit_reason']} | Days: {trade['days_held']}\n"
        
        return report