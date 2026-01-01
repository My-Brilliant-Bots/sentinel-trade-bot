import sqlite3
import yfinance as yf
import math
from datetime import datetime
from scipy.stats import norm
from typing import List, Optional, Dict, Any
from ai_client_model_registry import TradeSignal

class TradeDatabase:
    """
    Manages a SQLite database for tracking stock and option trades.

    This class handles schema initialization, signal persistence with 
    deterministic OCC symbol generation, and real-time portfolio tracking 
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
        
        Creates the 'trades' table with columns for trade metadata, 
        option-specific details (OCC symbols), and risk metrics (Greeks).
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL, 
                    entry_price REAL, 
                    target_exit_price REAL, 
                    actual_exit_price REAL,
                    stop_loss REAL, 
                    take_profit REAL, 
                    confidence_score REAL, 
                    shares INTEGER, 
                    market_research TEXT,
                    stock_recommendation_strategy TEXT, 
                    stock_recommendation_reasoning TEXT,
                    option_recommendation_strategy TEXT, 
                    option_recommendation_reasoning TEXT,
                    option_strike REAL, 
                    option_expiration_date TEXT, 
                    option_type TEXT, 
                    option_contract TEXT, 
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    closed_at TIMESTAMP,
                    status TEXT DEFAULT 'OPEN',
                    implied_volatility REAL, 
                    historical_volatility REAL,
                    delta REAL, gamma REAL, theta REAL, vega REAL, rho REAL
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
        date_obj = datetime.strptime(expiry.replace("-", ""), "%Y%m%d")
        date_str = date_obj.strftime("%y%m%d")
        type_char = opt_type[0].upper()
        strike_int = int(strike * 1000)
        strike_str = f"{strike_int:08d}"
        return f"{ticker}{date_str}{type_char}{strike_str}"

    def save_signal(self, signal: TradeSignal):
        """
        Persists a new trade signal into the database.

        If the signal is an option trade, it automatically generates the 
        standardized OCC 'option_contract' name.

        Args:
            signal (TradeSignal): A Pydantic model instance containing trade details.

        Returns:
            None

        Raises:
            sqlite3.Error: If the database insertion fails.
            ValueError: If the signal data is malformed.
            
        Example:
            >>> db.save_signal(my_long_call_signal)
        """
        data = signal.model_dump()
        
        # Determine if this is an option trade to generate OCC symbol
        if data.get('option_recommendation_strategy') != "NO TRADE" and data.get('option_strike'):
            data['option_contract'] = self._generate_occ_symbol(
                data['symbol'], 
                data['option_expiration_date'], 
                data['option_type'], 
                data['option_strike']
            )

        clean_data = {k: v for k, v in data.items() if v is not None}
        columns = ', '.join(clean_data.keys())
        placeholders = ', '.join([':' + k for k in clean_data.keys()])
        
        sql = f"INSERT INTO trades ({columns}) VALUES ({placeholders})"
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(sql, clean_data)

    def close_trade_by_attributes(self, symbol: str, actual_exit_price: float, 
                                 target_exit_price: float, option_expiry: str = None, 
                                 option_type: str = None, option_strike: float = None):
        """
        Updates an open trade to 'CLOSED' status based on stock or option attributes.

        If option attributes (expiry, type, strike) are provided, it will 
        specifically target the option contract. Otherwise, it targets stock trades.

        Args:
            symbol (str): The stock ticker.
            actual_exit_price (float): The price at which the trade was filled.
            target_exit_price (float): The original intended exit price for comparison.
            option_expiry (str, optional): Expiration 'YYYY-MM-DD'.
            option_type (str, optional): 'call' or 'put'.
            option_strike (float, optional): Strike price.

        Returns:
            None
            
        Example:
            >>> db.close_trade_by_attributes("TSLA", 250.0, 255.0)
        """
        occ_symbol = None
        if all([option_expiry, option_type, option_strike]):
            occ_symbol = self._generate_occ_symbol(symbol, option_expiry, option_type, option_strike)

        with sqlite3.connect(self.db_path) as conn:
            sql = """
                UPDATE trades 
                SET actual_exit_price = ?, target_exit_price = ?, status = 'CLOSED', closed_at = CURRENT_TIMESTAMP 
                WHERE symbol = ? AND status = 'OPEN'
            """
            if occ_symbol:
                sql += " AND option_contract = ?"
                params = (actual_exit_price, target_exit_price, symbol, occ_symbol)
            else:
                sql += " AND option_contract IS NULL"
                params = (actual_exit_price, target_exit_price, symbol)
            conn.execute(sql, params)

    def get_live_portfolio_status(self):
        """
        Generates a comprehensive financial status report with a Portfolio Summary.
        
        Outputs a detailed trade-by-trade table followed by an aggregate summary 
        of realized vs. unrealized gains to assist Agent decision-making.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 1. Fetch live market data for open trades
            cursor.execute("SELECT * FROM trades WHERE status = 'OPEN'")
            open_trades = cursor.fetchall()
            
            live_data = {}
            for trade in open_trades:
                symbol = trade['symbol']
                try:
                    ticker_obj = yf.Ticker(symbol)
                    if trade['option_contract']:
                        occ_symbol = trade['option_contract']
                        chain = ticker_obj.option_chain(trade['option_expiration_date'])
                        df = chain.calls if trade['option_type'].lower() == 'call' else chain.puts
                        contract_data = df[df['contractSymbol'] == occ_symbol]
                        if not contract_data.empty:
                            live_data[occ_symbol] = {'price': contract_data['lastPrice'].values[0]}
                    else:
                        live_data[symbol] = {'price': ticker_obj.fast_info['last_price']}
                except Exception:
                    continue

            # 2. Fetch all trades for the report
            cursor.execute("SELECT * FROM trades ORDER BY status DESC, created_at DESC")
            rows = cursor.fetchall()
            
            header = (f"{'Asset Identifier':<22} | {'Type':<4} | {'Status':<7} | {'Opened':<10} | {'Closed':<10} | "
                      f"{'Entry':<8} | {'Current':<8} | {'Qty':<4} | {'Total Cost':<10} | {'Curr Value':<10} | {'Total P/L':<9} | {'PnL %'}")
            print("\n" + header)
            print("-" * len(header))
            
            # Summary Tracking Variables
            total_invested = 0
            current_equity = 0
            realized_pnl = 0
            unrealized_pnl = 0

            for row in rows:
                is_opt = row['option_contract'] is not None
                asset_id = row['option_contract'] if is_opt else row['symbol']
                asset_type = "OPT" if is_opt else "STK"
                multiplier = 100 if is_opt else 1
                
                # Pricing & Financials
                qty = row['shares']
                entry_p = row['entry_price']
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
                pnl_pct = ((current_p - entry_p) / entry_p) * 100 if entry_p != 0 else 0
                
                print(f"{asset_id:<22} | {asset_type:<4} | {row['status']:<7} | {row['created_at'][:10]:<10} | "
                      f"{ (row['closed_at'][:10] if row['closed_at'] else 'Active'):<10} | {entry_p:>8.2f} | "
                      f"{current_p:>8.2f} | {qty:>4} | {total_cost:>10.2f} | {curr_val:>10.2f} | {total_pnl:>9.2f} | {pnl_pct:>7.2f}%")

            # 3. Portfolio Summary Block
            print("-" * len(header))
            print(f"{'PORTFOLIO SUMMARY':^135}")
            print("-" * len(header))
            print(f"Total Invested (Open): ${total_invested:,.2f}  |  Current Equity: ${current_equity:,.2f}")
            print(f"Unrealized P/L:        ${unrealized_pnl:,.2f}  |  Realized P/L:   ${realized_pnl:,.2f}")
            print(f"Total Net P/L:         ${(unrealized_pnl + realized_pnl):,.2f}")
            print("-" * len(header))

if __name__ == "__main__":
    import os
    
    # 1. Reset the database for a clean test run
    if os.path.exists("trading_bot.db"):
        os.remove("trading_bot.db")
        
    db = TradeDatabase("trading_bot.db")

    # 2. Sample 1: A Stock Trade (NVDA)
    # Includes all mandatory fields to satisfy the TradeSignal BaseModel
    nvda_signal = TradeSignal(
        symbol="NVDA",
        entry_price=125.00,
        stop_loss=115.00,
        take_profit=160.00,
        confidence_score=0.88,
        shares=10,
        market_research="Strong data center growth projected in next quarter.",
        stock_recommendation_strategy="BUY",
        stock_recommendation_reasoning="Bouncing off 50-day moving average.",
        option_recommendation_strategy="NO TRADE",
        option_recommendation_reasoning="N/A"
    )

    # 3. Sample 2: An Option Trade (AAPL)
    # Uses a real-world strike and future expiration date
    aapl_signal = TradeSignal(
        symbol="AAPL",
        entry_price=8.50,
        stop_loss=4.00,
        take_profit=20.00,
        confidence_score=0.75,
        shares=3,
        market_research="Anticipating volatility expansion before product event.",
        stock_recommendation_strategy="NO TRADE",
        stock_recommendation_reasoning="N/A",
        option_recommendation_strategy="Buy Long Call",
        option_recommendation_reasoning="High Delta/Gamma setup",
        option_strike=230.0,
        option_expiration_date="2026-06-19",  # Standard monthly expiry
        option_type="call",
        implied_volatility=0.22,
        delta=0.60
    )

    # 4. Save signals (The save_signal method will auto-generate the OCC symbol for AAPL)
    print("Saving signals to database...")
    db.save_signal(nvda_signal)
    db.save_signal(aapl_signal)

    # 5. Show Live Status (fetches real-time price and IV from yfinance)
    print("\n--- Initial Portfolio Status ---")
    db.get_live_portfolio_status()

    # 6. Test Closing Logic
    # We close the NVDA stock trade at a profit
    print("\nClosing NVDA position...")
    db.close_trade_by_attributes(
        symbol="NVDA",
        actual_exit_price=135.50,
        target_exit_price=135.00
    )

    # 7. Final Report
    print("\n--- Final Portfolio Status (1 Closed, 1 Open) ---")
    db.get_live_portfolio_status()