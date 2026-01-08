import json
import sqlite3
import yfinance as yf
import re
from datetime import datetime
from typing import Optional

from logging_config import get_logger
from ai_client_model_registry import StockSignal, TradeSignal, OptionSignal

logger = get_logger(__name__)

class TradeDatabase:
    """
    Manages a SQLite database for tracking stock and option trades separately.

    This class handles schema initialization with separate tables for stock
    and option trades, signal persistence, and real-time portfolio tracking
    using yfinance for market data and Greeks.

    Attributes:
        db_path (str): The filesystem path to the SQLite database file.
    """

    def __init__(self, db_path: str = "trading_bot.db"):
        """
        Initializes the TradeDatabase with a specific database file.

        Args:
            db_path (str): Path to the .db file. Defaults to "trading_bot.db".
        """
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """
        Initializes the database schema if it does not already exist.
        
        Creates separate 'stock_trades' and 'option_trades' tables.
        """
        with sqlite3.connect(self.db_path) as conn:
            # Stock trades table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS stock_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    signal_id TEXT,
                    symbol TEXT NOT NULL, 
                    entry_price REAL NOT NULL, 
                    target_exit_price REAL,
                    actual_exit_price REAL,
                    stop_loss REAL NOT NULL, 
                    take_profit REAL NOT NULL, 
                    confidence_score REAL NOT NULL, 
                    shares INTEGER NOT NULL, 
                    market_research TEXT,
                    stock_recommendation_strategy TEXT NOT NULL, 
                    stock_recommendation_reasoning TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    closed_at TIMESTAMP,
                    status TEXT DEFAULT 'OPEN'
                )
            """)
            
            # Option trades table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS option_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    signal_id TEXT,
                    symbol TEXT NOT NULL,
                    target_exit_price REAL,
                    actual_exit_price REAL,
                    stop_loss REAL NOT NULL, 
                    take_profit REAL NOT NULL, 
                    confidence_score REAL NOT NULL, 
                    market_research TEXT,
                    option_recommendation_strategy TEXT NOT NULL, 
                    option_recommendation_reasoning TEXT,
                    option_strike REAL NOT NULL, 
                    option_expiration_date TEXT NOT NULL, 
                    option_type TEXT NOT NULL, 
                    option_contract TEXT NOT NULL, 
                    option_entry_price REAL NOT NULL, 
                    num_of_contracts INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    closed_at TIMESTAMP,
                    status TEXT DEFAULT 'OPEN',
                    implied_volatility REAL, 
                    historical_volatility REAL,
                    delta REAL, 
                    gamma REAL, 
                    theta REAL, 
                    vega REAL, 
                    rho REAL
                )
            """)

    def _generate_occ_symbol(self, symbol: str, expiry: str, opt_type: str, strike: float) -> str:
        """
        Generates a deterministic OCC (Options Clearing Corporation) symbol.

        Args:
            symbol (str): Underlying stock ticker (e.g., 'AAPL').
            expiry (str): Expiration date in 'YYYY-MM-DD' format.
            opt_type (str): Either 'call' or 'put'.
            strike (float): The strike price (e.g., 150.0).

        Returns:
            str: Standardized OCC symbol (e.g., 'AAPL260117C00150000').
        """
        ticker = symbol.upper().strip().ljust(6).replace(" ", "")
        
        # Extract YYYY-MM-DD
        match = re.search(r"\d{4}-\d{2}-\d{2}", expiry)
        if not match:
            raise ValueError(f"No valid date found in: {expiry}")
        date_part = match.group()
        dt = datetime.strptime(date_part, "%Y-%m-%d")
        date_str = dt.strftime("%y%m%d")

        type_char = opt_type[0].upper()
        strike_int = int(strike * 1000)
        strike_str = f"{strike_int:08d}"
        return f"{ticker}{date_str}{type_char}{strike_str}"

    def save_signal(self, signal_as_string: str):
        """
        Persists a new trade signal into the database as separate stock and option rows.

        Args:
            signal_as_string (str): A JSON string representation of a TradeSignal object.

        Returns:
            None

        Raises:
            sqlite3.Error: If the database insertion fails.
            json.JSONDecodeError: If the JSON string is malformed.
            ValidationError: If the data doesn't match TradeSignal schema.
            
        Example:
            >>> db.save_signal('{"stock_signal": {...}, "option_signal": {...}}')
        """
        try:
            logger.debug("Called save_signal method")
            
            # Parse JSON string to dictionary
            signal_dict = json.loads(signal_as_string)
            logger.debug(f"Converted to json: {signal_dict}")
            
            # Convert dictionary to TradeSignal object
            trade_signal = TradeSignal(**signal_dict)
            logger.debug("Successfully validated TradeSignal")
            
            # Generate a unique signal_id to link stock and option trades
            signal_id = f"{trade_signal.stock_signal.symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            with sqlite3.connect(self.db_path) as conn:
                # Save stock signal if it's a valid trade
                if trade_signal.stock_signal.stock_recommendation_strategy != "NO TRADE":
                    stock_data = {
                        'signal_id': signal_id,
                        'symbol': trade_signal.stock_signal.symbol,
                        'entry_price': trade_signal.stock_signal.entry_price,
                        'stop_loss': trade_signal.stock_signal.stop_loss,
                        'take_profit': trade_signal.stock_signal.take_profit,
                        'confidence_score': trade_signal.stock_signal.confidence_score,
                        'shares': trade_signal.stock_signal.shares,
                        'market_research': trade_signal.stock_signal.market_research,
                        'stock_recommendation_strategy': trade_signal.stock_signal.stock_recommendation_strategy,
                        'stock_recommendation_reasoning': trade_signal.stock_signal.stock_recommendation_reasoning
                    }
                    
                    columns = ', '.join(stock_data.keys())
                    placeholders = ', '.join([':' + k for k in stock_data.keys()])
                    sql = f"INSERT INTO stock_trades ({columns}) VALUES ({placeholders})"
                    conn.execute(sql, stock_data)
                    logger.debug(f"Saved stock trade for {signal_id}")
                
                # Save option signal if it's a valid trade
                if trade_signal.option_signal.option_recommendation_strategy != "NO TRADE":
                    # Generate OCC symbol
                    occ_symbol = self._generate_occ_symbol(
                        trade_signal.stock_signal.symbol,
                        trade_signal.option_signal.option_expiration_date,
                        trade_signal.option_signal.option_type,
                        trade_signal.option_signal.option_strike
                    )
                    
                    option_data = {
                        'signal_id': signal_id,
                        'symbol': trade_signal.stock_signal.symbol,
                        'stop_loss': trade_signal.option_signal.stop_loss,
                        'take_profit': trade_signal.option_signal.take_profit,
                        'confidence_score': trade_signal.option_signal.confidence_score,
                        'market_research': trade_signal.option_signal.market_research,
                        'option_recommendation_strategy': trade_signal.option_signal.option_recommendation_strategy,
                        'option_recommendation_reasoning': trade_signal.option_signal.option_recommendation_reasoning,
                        'option_strike': trade_signal.option_signal.option_strike,
                        'option_expiration_date': trade_signal.option_signal.option_expiration_date,
                        'option_type': trade_signal.option_signal.option_type,
                        'option_contract': occ_symbol,
                        'option_entry_price': trade_signal.option_signal.option_entry_price,
                        'num_of_contracts': trade_signal.option_signal.num_of_contracts,
                        'implied_volatility': trade_signal.option_signal.implied_volatility,
                        'historical_volatility': trade_signal.option_signal.historical_volatility,
                        'delta': trade_signal.option_signal.delta,
                        'gamma': trade_signal.option_signal.gamma,
                        'theta': trade_signal.option_signal.theta,
                        'vega': trade_signal.option_signal.vega,
                        'rho': trade_signal.option_signal.rho
                    }
                    
                    columns = ', '.join(option_data.keys())
                    placeholders = ', '.join([':' + k for k in option_data.keys()])
                    sql = f"INSERT INTO option_trades ({columns}) VALUES ({placeholders})"
                    conn.execute(sql, option_data)
                    logger.debug(f"Saved option trade for {signal_id}")
            
            logger.debug("Completed save_signal method")
            logger.debug("Portfolio summary report")
            logger.debug(self.get_live_portfolio_status())
            
        except json.JSONDecodeError as ex:
            logger.error(f"Invalid JSON string: {ex}")
            raise
        except Exception as ex:
            logger.error(f"Error saving to database: {ex}")
            raise

    def close_stock_trade(self, symbol: str, actual_exit_price: float, target_exit_price: Optional[float] = None):
        """
        Closes an open stock trade.

        Args:
            symbol (str): The stock ticker.
            actual_exit_price (float): The price at which the trade was filled.
            target_exit_price (float, optional): The original intended exit price.
        """
        with sqlite3.connect(self.db_path) as conn:
            sql = """
                UPDATE stock_trades 
                SET actual_exit_price = ?, target_exit_price = COALESCE(?, target_exit_price), 
                    status = 'CLOSED', closed_at = CURRENT_TIMESTAMP 
                WHERE symbol = ? AND status = 'OPEN'
            """
            conn.execute(sql, (actual_exit_price, target_exit_price, symbol))
            logger.debug(f"Closed stock trade for {symbol}")

    def close_option_trade(self, symbol: str, option_expiry: str, option_type: str, 
                          option_strike: float, actual_exit_price: float, 
                          target_exit_price: Optional[float] = None):
        """
        Closes an open option trade.

        Args:
            symbol (str): The underlying stock ticker.
            option_expiry (str): Expiration date 'YYYY-MM-DD'.
            option_type (str): 'call' or 'put'.
            option_strike (float): Strike price.
            actual_exit_price (float): The price at which the option was filled.
            target_exit_price (float, optional): The original intended exit price.
        """
        occ_symbol = self._generate_occ_symbol(symbol, option_expiry, option_type, option_strike)
        
        with sqlite3.connect(self.db_path) as conn:
            sql = """
                UPDATE option_trades 
                SET actual_exit_price = ?, target_exit_price = COALESCE(?, target_exit_price),
                    status = 'CLOSED', closed_at = CURRENT_TIMESTAMP 
                WHERE option_contract = ? AND status = 'OPEN'
            """
            conn.execute(sql, (actual_exit_price, target_exit_price, occ_symbol))
            logger.debug(f"Closed option trade {occ_symbol}")

    def get_live_portfolio_status(self) -> str:
        """
        Generates a comprehensive financial status report with Portfolio Summary
        and RETURNS it as a formatted string instead of printing to console.
        """
        output_lines = []

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Fetch live market data for open trades
            live_data = {}

            # Open stock trades
            cursor.execute("SELECT * FROM stock_trades WHERE status = 'OPEN'")
            open_stocks = cursor.fetchall()
            for trade in open_stocks:
                symbol = trade['symbol']
                try:
                    ticker_obj = yf.Ticker(symbol)
                    live_data[symbol] = {'price': ticker_obj.fast_info['last_price']}
                except Exception:
                    continue

            # Open option trades
            cursor.execute("SELECT * FROM option_trades WHERE status = 'OPEN'")
            open_options = cursor.fetchall()
            for trade in open_options:
                try:
                    ticker_obj = yf.Ticker(trade['symbol'])
                    occ_symbol = trade['option_contract']
                    chain = ticker_obj.option_chain(trade['option_expiration_date'])
                    df = chain.calls if trade['option_type'].lower() == 'call' else chain.puts
                    contract_data = df[df['contractSymbol'] == occ_symbol]
                    if not contract_data.empty:
                        live_data[occ_symbol] = {
                            'price': contract_data['lastPrice'].values[0]
                        }
                except Exception:
                    continue

            # Unified trade query
            cursor.execute("""
                SELECT 
                    'STOCK' as trade_type,
                    id,
                    signal_id,
                    symbol,
                    status,
                    created_at,
                    closed_at,
                    entry_price,
                    actual_exit_price,
                    shares as quantity,
                    NULL as option_contract,
                    NULL as option_entry_price,
                    NULL as num_of_contracts,
                    NULL as option_type
                FROM stock_trades

                UNION ALL

                SELECT 
                    'OPTION' as trade_type,
                    id,
                    signal_id,
                    symbol,
                    status,
                    created_at,
                    closed_at,
                    NULL as entry_price,
                    actual_exit_price,
                    NULL as quantity,
                    option_contract,
                    option_entry_price,
                    num_of_contracts,
                    option_type
                FROM option_trades

                ORDER BY status DESC, created_at DESC
            """)

            rows = cursor.fetchall()

            header = (
                f"{'Asset Identifier':<22} | {'Type':<6} | {'Status':<7} | "
                f"{'Opened':<10} | {'Closed':<10} | {'Entry':<8} | {'Current':<8} | "
                f"{'Qty':<4} | {'Total Cost':<10} | {'Curr Value':<10} | "
                f"{'Total P/L':<9} | {'PnL %'}"
            )

            separator = "-" * len(header)

            output_lines.append(header)
            output_lines.append(separator)

            total_invested = 0.0
            current_equity = 0.0
            realized_pnl = 0.0
            unrealized_pnl = 0.0

            for row in rows:
                is_stock = row['trade_type'] == 'STOCK'

                if is_stock:
                    asset_id = row['symbol']
                    asset_type = "STOCK"
                    multiplier = 1
                    qty = row['quantity']
                    entry_p = row['entry_price']
                else:
                    asset_id = row['option_contract']
                    asset_type = "OPTION"
                    multiplier = 100
                    qty = row['num_of_contracts']
                    entry_p = row['option_entry_price']

                total_cost = entry_p * qty * multiplier

                if row['status'] == 'CLOSED':
                    current_p = row['actual_exit_price']
                    realized_pnl += (current_p - entry_p) * qty * multiplier
                else:
                    current_p = live_data.get(asset_id, {}).get('price', entry_p)
                    total_invested += total_cost
                    current_equity += current_p * qty * multiplier
                    unrealized_pnl += (current_p - entry_p) * qty * multiplier

                curr_val = current_p * qty * multiplier
                total_pnl = curr_val - total_cost
                pnl_pct = ((current_p - entry_p) / entry_p) * 100 if entry_p else 0

                output_lines.append(
                    f"{asset_id:<22} | {asset_type:<6} | {row['status']:<7} | "
                    f"{row['created_at'][:10]:<10} | "
                    f"{(row['closed_at'][:10] if row['closed_at'] else 'Active'):<10} | "
                    f"{entry_p:>8.2f} | {current_p:>8.2f} | {qty:>4} | "
                    f"{total_cost:>10.2f} | {curr_val:>10.2f} | "
                    f"{total_pnl:>9.2f} | {pnl_pct:>7.2f}%"
                )

            # Portfolio summary
            output_lines.append(separator)
            output_lines.append(f"{'PORTFOLIO SUMMARY':^{len(header)}}")
            output_lines.append(separator)
            output_lines.append(
                f"Total Invested (Open): ${total_invested:,.2f}  |  "
                f"Current Equity: ${current_equity:,.2f}"
            )
            output_lines.append(
                f"Unrealized P/L:        ${unrealized_pnl:,.2f}  |  "
                f"Realized P/L:   ${realized_pnl:,.2f}"
            )
            output_lines.append(
                f"Total Net P/L:         ${(unrealized_pnl + realized_pnl):,.2f}"
            )
            output_lines.append(separator)

        portfolio = "\n".join(output_lines)
        logger.debug(portfolio)
        return portfolio


if __name__ == "__main__":
    import os
    
    # Reset the database
    if os.path.exists("trading_bot.db"):
        os.remove("trading_bot.db")

    db = TradeDatabase()

    # print and check that the portfolio has been cleared    
    db.get_live_portfolio_status()