import sqlite3
import yfinance as yf
from datetime import datetime
from typing import List, Optional
from ai_client_model_registry import TradeSignal

class TradeDatabase:
    def __init__(self, db_path="trading_bot.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT, entry_price REAL, 
                    target_exit_price REAL, actual_exit_price REAL, -- Renamed for clarity
                    stop_loss REAL, take_profit REAL, confidence_score REAL, 
                    shares INTEGER, market_research TEXT,
                    stock_recommendation_strategy TEXT, stock_recommendation_reasoning TEXT,
                    option_recommendation_strategy TEXT, option_recommendation_reasoning TEXT,
                    option_strike REAL, option_expiration_date TEXT, 
                    option_type TEXT, option_contract TEXT, 
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    closed_at TIMESTAMP,
                    status TEXT DEFAULT 'OPEN',
                    implied_volatility REAL, historical_volatility REAL,
                    delta REAL, gamma REAL, theta REAL, vega REAL, rho REAL
                )
            """)

    def save_signal(self, signal: TradeSignal):
        data = signal.model_dump()
        # Filter out None values to let DB defaults work
        clean_data = {k: v for k, v in data.items() if v is not None}
        columns = ', '.join(clean_data.keys())
        placeholders = ', '.join([':' + k for k in clean_data.keys()])
        
        sql = f"INSERT INTO trades ({columns}) VALUES ({placeholders})"
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(sql, clean_data)

    def close_trade_by_attributes(self, symbol: str, actual_exit_price: float, target_exit_price: float, option_contract: str = None):
        with sqlite3.connect(self.db_path) as conn:
            # We add "closed_at = CURRENT_TIMESTAMP" to the SET clause
            sql = """
                UPDATE trades 
                SET actual_exit_price = ?, 
                    target_exit_price = ?, 
                    status = 'CLOSED',
                    closed_at = CURRENT_TIMESTAMP 
                WHERE symbol = ? AND status = 'OPEN'
            """
            if option_contract:
                sql += " AND option_contract = ?"
                params = (actual_exit_price, target_exit_price, symbol, option_contract)
            else:
                sql += " AND option_contract IS NULL"
                params = (actual_exit_price, target_exit_price, symbol)
                
            conn.execute(sql, params)

    def get_live_portfolio_status(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 1. Fetch live prices for open positions
            cursor.execute("SELECT DISTINCT symbol FROM trades WHERE status = 'OPEN'")
            open_symbols = [row['symbol'] for row in cursor.fetchall()]
            
            live_prices = {}
            if open_symbols:
                data = yf.download(open_symbols, period="1d", interval="1m", progress=False)
                if not data.empty:
                    last_prices = data['Close'].iloc[-1]
                    live_prices = last_prices.to_dict() if len(open_symbols) > 1 else {open_symbols[0]: float(last_prices)}

            # 2. Fetch all columns to provide full context to the Agent
            cursor.execute("SELECT * FROM trades ORDER BY created_at DESC")
            rows = cursor.fetchall()
            
            # Header with date and price columns
            header = f"{'Asset Identifier':<25} | {'Opened':<12} | {'Closed':<12} | {'Entry':<8} | {'Exit':<8} | {'PnL %'}"
            print(header)
            print("-" * len(header))
            
            for row in rows:
                is_option = row['option_contract'] is not None
                asset_id = row['option_contract'] if is_option else row['symbol']
                
                # Format Dates (created_at is automatic, we'll use it as Opened)
                open_date = row['created_at'][:10] # YYYY-MM-DD
                
                # For closed trades, we can derive the close date or add a 'closed_at' column.
                # If you haven't added a 'closed_at' column yet, it will show as N/A for now.
                close_date = row['closed_at'][:10] if row['closed_at'] else "Active"
                
                entry = row['entry_price']
                multiplier = 100 if is_option else 1
                
                # Determine current price for PnL calculation
                current = row['actual_exit_price'] if row['status'] == 'CLOSED' else live_prices.get(row['symbol'], entry)
                exit_display = f"{row['actual_exit_price']:>8.2f}" if row['actual_exit_price'] else f"{'Live':>8}"
                
                pnl_pct = ((current - entry) / entry) * 100 if entry != 0 else 0
                
                print(f"{asset_id:<25} | {open_date:<12} | {close_date:<12} | {entry:>8.2f} | {exit_display} | {pnl_pct:>7.2f}%") 



if __name__ == "__main__":
    # 1. Initialize the database
    db = TradeDatabase("test_trading.db")
    
    # 2. Define sample TradeSignals
    # Note: market_research is a required string based on your Pydantic model
    
    # SAMPLE 1: An Open Stock Trade (NVDA)
    nvda_stock = TradeSignal(
        symbol="NVDA",
        entry_price=120.50,
        stop_loss=110.00,
        take_profit=150.00,
        confidence_score=0.85,
        shares=10,
        market_research="Strong AI demand and upcoming earnings catalyst.",
        stock_recommendation_strategy="BUY",
        stock_recommendation_reasoning="Bullish momentum",
        option_recommendation_strategy="NO TRADE",
        option_recommendation_reasoning="N/A"
    )

    # SAMPLE 2: An Open Option Trade (AAPL Call)
    aapl_call = TradeSignal(
        symbol="AAPL",
        entry_price=5.20,
        stop_loss=2.50,
        take_profit=12.00,
        confidence_score=0.70,
        shares=2, # 2 contracts = 200 shares equivalent
        market_research="Anticipating product launch breakout.",
        stock_recommendation_strategy="NO TRADE",
        stock_recommendation_reasoning="N/A",
        option_recommendation_strategy="Buy Long Call",
        option_recommendation_reasoning="High Delta play",
        option_strike=220.0,
        option_expiration_date="2025-06-20",
        option_type="call",
        option_contract="AAPL 220 CALL 2025-06-20",
        implied_volatility=0.28,
        delta=0.65
    )

    # SAMPLE 3: A Closed Stock Trade (TSLA)
    tsla_stock = TradeSignal(
        symbol="TSLA",
        entry_price=250.00,
        stop_loss=230.00,
        take_profit=280.00,
        confidence_score=0.60,
        shares=5,
        market_research="Technical bounce play.",
        stock_recommendation_strategy="BUY",
        stock_recommendation_reasoning="Oversold on RSI",
        option_recommendation_strategy="NO TRADE",
        option_recommendation_reasoning="N/A"
    )

    # 3. Save signals to the DB
    db.save_signal(nvda_stock)
    db.save_signal(aapl_call)
    db.save_signal(tsla_stock)

    # 4. Manually close the TSLA trade to test "Realized P&L" logic
    # We exit at $265.00 (Actual) even though our Target was $265.50
    db.close_trade_by_attributes(
        symbol="TSLA", 
        actual_exit_price=265.00, 
        target_exit_price=265.50
    )

    # 5. Run the Status Report
    print("\n--- TEST: LIVE PORTFOLIO STATUS ---")
    db.get_live_portfolio_status()