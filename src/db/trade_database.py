import sqlite3
from datetime import datetime

class TradeDatabase:
    def __init__(self, db_path="trading_bot.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            # Create the table using the schema above
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT, entry_price REAL, stop_loss REAL, take_profit REAL,
                    confidence_score REAL, shares INTEGER, market_research TEXT,
                    stock_recommendation_strategy TEXT, stock_recommendation_reasoning TEXT,
                    option_recommendation_strategy TEXT, option_recommendation_reasoning TEXT,
                    option_strike REAL, option_expiration_date TEXT, option_type TEXT,
                    option_contract TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'PENDING'
                )
            """)

    def save_signal(self, signal: TradeSignal):
        # 1. Convert Pydantic model to a dictionary
        data = signal.model_dump()
        
        # 2. Extract keys and values for dynamic insertion
        columns = ', '.join(data.keys())
        placeholders = ', '.join([':' + k for k in data.keys()])
        
        sql = f"INSERT INTO trades ({columns}) VALUES ({placeholders})"
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(sql, data)
            print(f"✅ Trade signal for {signal.symbol} saved to database.")

# --- Usage Example ---
db = TradeDatabase()
# Assuming 'signal' is an instance of your TradeSignal class
db.save_signal(signal)