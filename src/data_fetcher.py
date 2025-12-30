"""
Data fetcher module using yfinance for fast, reliable data retrieval
No rate limits, much faster than Alpha Vantage
"""
from datetime import datetime, timedelta
import logging
import sys
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import pandas_ta as ta
import requests
import yfinance as yf

from logging_config import get_logger

logging = get_logger(__name__)

class StockDataFetcher:
    """Handles all stock data retrieval operations"""
    
    def __init__(self):
        self.cache = {}

    def get_enhanced_stock_data(
    self,
    symbol: str, 
    period: str = "1y", 
    history_window: int = 60  # Days of history to return for LLMs (configurable)
    ) -> Optional[Dict[str, any]]:

        """
        Fetch enhanced stock data with indicators for multiple strategies (Connors RSI 2, RSI Divergence, 50-Crossover)
        and pre-formatted data for LLM recommendations. Includes trimmed history for context.

        Args:
            symbol: Stock ticker (e.g., 'AAPL').
            period: YF period (e.g., '1y').
            history_window: Number of recent days to include in response (e.g., 60 for divergences).

        Returns:
            Dict with latest indicators, strategy signals, history slice, and LLM-friendly prompt. None on error.
        """
        try:
            logging.debug(f"Fetching enhanced data for {symbol}")
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period)

            if hist.empty:
                return {"error": f"No data for {symbol}", "symbol": symbol}

            # Trim to last 'history_window' days for efficiency (tail preserves recency)
            hist = hist.tail(history_window)  # Ensures sufficient data but not full period
            
            # Core Indicators (from original get_stock_data)
            hist['SMA_50'] = hist['Close'].rolling(window=50).mean()
            hist['SMA_200'] = hist['Close'].rolling(window=200, min_periods=1).mean()  # Allow partial if <200 in window
            hist['RSI_2'] = ta.rsi(hist['Close'], length=2)
            hist['RSI_14'] = ta.rsi(hist['Close'], length=14)
            hist['ATR_14'] = ta.atr(hist['High'], hist['Low'], hist['Close'], length=14)
            
            # MACD for momentum
            macd_df = ta.macd(hist['Close'], fast=12, slow=26, signal=9)
            hist = pd.concat([hist, macd_df], axis=1)
            macd_h_col = 'MACDh_12_26_9'  # Histogram
            
            # Volume
            hist['Volume_SMA_20'] = hist['Volume'].rolling(window=20, min_periods=1).mean()
            hist['Volume_Ratio'] = hist['Volume'] / hist['Volume_SMA_20'].replace(0, 1)  # Avoid div by zero

            # Strategy-Specific Calculations
            # 1. 50-Crossover: Cross signal based on price vs SMA-50 (1=buy, -1=sell, 0=neutral)
            hist['Price_vs_SMA50'] = np.where(hist['Close'] > hist['SMA_50'], 1, -1)
            hist['SMA50_Cross'] = hist['Price_vs_SMA50'].diff().fillna(0)  # Change in signal
            
            # 2. Connors RSI 2 (Simplified): RSI-2 + Streak (consec up/down days) + %Rank(Close, 100)
            hist['Streak'] = ((hist['Close'] > hist['Close'].shift(1)).astype(int) * 2 - 1).groupby(
                (hist['Close'] > hist['Close'].shift(1)).astype(int).ne(hist['Close'].shift(1, fill_value=0).astype(int)).cumsum()).cumsum()
            hist['Percent_Rank'] = (hist['Close'].rank(pct=True) * 100).rolling(100, min_periods=10).mean()  # Approx %Rank
            hist['Connors_RSI2'] = (hist['RSI_2'] + hist['Streak'] + hist['Percent_Rank']) / 3  # Normalized avg
            
            # 3. RSI Divergence: Basic detection (manual: compare peaks/valleys in price vs RSI)
            # Note: For simplicity, check if last 5 days show divergence (e.g., price up, RSI down). Use libraries for prod.
            hist['Price_Change'] = hist['Close'].pct_change()
            hist['RSI_Change'] = hist['RSI_14'].pct_change()
            hist['Divergence_Bearish'] = ((hist['Price_Change'] > 0) & (hist['RSI_Change'] < 0)).rolling(5).sum() / 5 >= 0.6  # >60% in 5 days
            hist['Divergence_Bullish'] = ((hist['Price_Change'] < 0) & (hist['RSI_Change'] > 0)).rolling(5).sum() / 5 >= 0.6

            # Latest & Previous
            latest = hist.iloc[-1]
            prev = hist.iloc[-2] if len(hist) > 1 else latest
            info = ticker.info

            # Strategies Summary for LLMs
            strategies = {
                "50_Crossover": {
                    "signal": "Bullish" if latest['SMA50_Cross'] > 0 else "Bearish" if latest['SMA50_Cross'] < 0 else "Neutral",
                    "trend": "Uptrend" if latest['Price_vs_SMA50'] == 1 else "Downtrend",
                    "details": f"Price at {latest['Close']:.2f}, SMA-50 at {latest['SMA_50']:.2f}. Recent cross: {latest['SMA50_Cross']}"
                },
                "Connors_RSI2": {
                    "score": round(latest['Connors_RSI2'], 2) if not pd.isna(latest['Connors_RSI2']) else None,
                    "interpretation": "Oversold (<40)" if latest['Connors_RSI2'] < 40 else "Neutral (40-60)" if latest['Connors_RSI2'] < 60 else "Overbought (>60)",
                    "details": f"RSI-2: {latest['RSI_2']:.2f}, Streak: {latest['Streak']}, %Rank: {latest['Percent_Rank']:.2f}"
                },
                "RSI_Divergence": {
                    "signal": "Bullish" if latest['Divergence_Bullish'] else "Bearish" if latest['Divergence_Bearish'] else "None",
                    "details": f"Over last 5 days, {'bullish' if latest['Divergence_Bullish'] else 'bearish' if latest['Divergence_Bearish'] else 'no'} divergence detected (price vs RSI-14)."
                }
            }

            # LLM Prompt: Structured JSON + Narrative Text
            llm_prompt = {
                "data_type": "enhanced_stock_analysis",
                "description": "Summarized stock information with technical indicators",
                "symbol": symbol,
                "price": float(latest['Close']),
                "prev_price": float(prev['Close']),
                "indicators": {
                    "rsi_2": float(latest['RSI_2']) if not pd.isna(latest['RSI_2']) else None,
                    "rsi_14": float(latest['RSI_14']) if not pd.isna(latest['RSI_14']) else None,
                    "sma_50": float(latest['SMA_50']) if not pd.isna(latest['SMA_50']) else None,
                    "macd_hist": float(latest[macd_h_col]) if not pd.isna(latest[macd_h_col]) else None,
                    "atr_14": float(latest['ATR_14']) if not pd.isna(latest['ATR_14']) else None,
                    "volume_ratio": float(latest['Volume_Ratio']) if not pd.isna(latest['Volume_Ratio']) else 1.0
                },
                "strategies": strategies,
                "history_summary": f"Recent 30-day high: {hist['Close'].tail(30).max():.2f}, low: {hist['Close'].tail(30).min():.2f}. Trend: {'Bullish' if hist['Close'].iloc[-1] > hist['Close'].iloc[-30] else 'Bearish'} over past month.",
                "narrative_text": f"""
                Stock {symbol} currently trades at ${latest['Close']:.2f}, up {((latest['Close']/prev['Close'])-1)*100:.1f}% from previous day.
                RSI-14 is {latest['RSI_14']:.0f}, indicating {'overbought' if latest['RSI_14'] > 70 else 'oversold' if latest['RSI_14'] < 30 else 'neutral'} conditions.
                SMA-50 crossover signals: {strategies['50_Crossover']['signal']} with {strategies['50_Crossover']['trend']} trend.
                Connors RSI-2 score: {strategies['Connors_RSI2']['score']} ({strategies['Connors_RSI2']['interpretation']}).
                RSI Divergence: {strategies['RSI_Divergence']['signal']} if present, suggesting potential reversal.
                Volume is {'elevated' if latest['Volume_Ratio'] > 1.2 else 'low'} at {latest['Volume_Ratio']:.1f}x average.
                MACD histogram: {latest[macd_h_col]:.3f}, indicating {'bullish momentum' if latest[macd_h_col] > 0 else 'bearish momentum'}.
                Market cap: {info.get('marketCap', 'N/A')}, sector: {info.get('sector', 'N/A')}.
                Historical context: Over the last 30 days, average volatility (ATR-14): {hist['ATR_14'].tail(30).mean():.2f}, max close: {hist['Close'].tail(30).max():.2f}.
                """.strip()
            }

            # Main Response: Core data + History DF (pandas DF is JSON-serializable if converted to dict)
            stock_data = {
                "symbol": symbol,
                "price": float(latest['Close']),
                "prev_close": float(prev['Close']),
                "sma_50": float(latest['SMA_50']) if not pd.isna(latest['SMA_50']) else None,
                "rsi_2": float(latest['RSI_2']) if not pd.isna(latest['RSI_2']) else None,
                "rsi_14": float(latest['RSI_14']) if not pd.isna(latest['RSI_14']) else None,
                "connors_rsi2": float(latest['Connors_RSI2']) if not pd.isna(latest['Connors_RSI2']) else None,
                "divergence_bullish": bool(latest['Divergence_Bullish']),
                "sma50_cross_signal": float(latest['SMA50_Cross']),
                "macd_hist": float(latest[macd_h_col]) if not pd.isna(latest[macd_h_col]) else None,
                "atr_14": float(latest['ATR_14']) if not pd.isna(latest['ATR_14']) else None,
                "volume_ratio": float(latest['Volume_Ratio']) if not pd.isna(latest['Volume_Ratio']) else 1.0,
                "market_cap": info.get('marketCap'),
                "sector": info.get('sector'),
                #"history": hist[['Close', 'Open', 'High', 'Low', 'Volume', 'SMA_50', 'RSI_14', macd_h_col]].to_dict('records'),  # JSON-friendly; last 60 days
                "llm_prompt": llm_prompt
            }

            logging.debug(f"Successfully processed {symbol}")
            return stock_data

        except Exception as e:
            logging.error(f"Error for {symbol}: {e}")
            raise e
            

    def get_stock_data(self, symbol: str, period: str = "1y") -> Optional[Dict]:
        """
        Fetch comprehensive stock data including price, indicators, and history.
        Now includes detailed MACD Histogram analysis for momentum shifts.
        """
        try:
            print(f"Fetching stock market data for {symbol}")
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period)

            print(f"Historical (1yr) data for {symbol} is {hist}")
            
            if hist.empty:
                return {"error": f"No data available for {symbol}", "symbol": symbol}
            
            # 1. Calculate Standard Indicators
            hist['SMA_50'] = hist['Close'].rolling(window=50).mean()
            hist['SMA_200'] = hist['Close'].rolling(window=200).mean()
            hist['RSI_2'] = ta.rsi(hist['Close'], length=2)
            hist['RSI_14'] = ta.rsi(hist['Close'], length=14)
            hist['ATR_14'] = ta.atr(hist['High'], hist['Low'], hist['Close'], length=14)
            
            # 2. Calculate MACD (Returns a DF with MACD_12_26_9, MACDh_12_26_9, MACDs_12_26_9)
            macd_df = ta.macd(hist['Close'], fast=12, slow=26, signal=9)
            
            # Merge MACD values into main history for row-based access
            hist = pd.concat([hist, macd_df], axis=1)
            
            # Column names from pandas_ta for MACD
            macd_col = 'MACD_12_26_9'
            macd_s_col = 'MACDs_12_26_9'
            macd_h_col = 'MACDh_12_26_9' # This is the Histogram
            
            # 3. Volume analysis
            hist['Volume_SMA_20'] = hist['Volume'].rolling(window=20).mean()
            hist['Volume_Ratio'] = hist['Volume'] / hist['Volume_SMA_20']
            
            # Get latest and previous values
            latest = hist.iloc[-1]
            # Ensure we have at least 2 rows for 'previous' comparisons
            prev = hist.iloc[-2] if len(hist) > 1 else latest
            
            # Get company info
            info = ticker.info
            
            stock_data = {
                "symbol": symbol,
                "price": float(latest['Close']),
                "prev_close": float(prev['Close']),
                "sma_50": float(latest['SMA_50']) if not pd.isna(latest['SMA_50']) else None,
                "sma_200": float(latest['SMA_200']) if not pd.isna(latest['SMA_200']) else None,
                "rsi_2": float(latest['RSI_2']) if not pd.isna(latest['RSI_2']) else None,
                "rsi_14": float(latest['RSI_14']) if not pd.isna(latest['RSI_14']) else None,
                "atr_14": float(latest['ATR_14']) if not pd.isna(latest['ATR_14']) else None,
                
                # --- NEW MACD DATA ---
                "macd_line": float(latest[macd_col]) if not pd.isna(latest[macd_col]) else None,
                "macd_signal_line": float(latest[macd_s_col]) if not pd.isna(latest[macd_s_col]) else None,
                "macd_hist": float(latest[macd_h_col]) if not pd.isna(latest[macd_h_col]) else None,
                "prev_macd_hist": float(prev[macd_h_col]) if not pd.isna(prev[macd_h_col]) else None,
                # ---------------------

                "volume": float(latest['Volume']),
                "volume_ratio": float(latest['Volume_Ratio']) if not pd.isna(latest['Volume_Ratio']) else 1.0,
                "market_cap": info.get('marketCap'),
                "sector": info.get('sector'),
                "industry": info.get('industry')
                
            }
            
            print("***** Result ")
            print(stock_data)

            return stock_data
        except Exception as e:
            print(f"Error fetching data for {symbol}: {e}")
            return {"error": str(e), "symbol": symbol}
    
    def get_options_data(self, symbol: str, max_dte: int = 60) -> Dict:
        """
        Fetch options data for near-term expirations
        
        Args:
            symbol: Stock ticker symbol
            max_dte: Maximum days to expiration
        
        Returns:
            Dictionary with options data organized by expiration date
        """
        try:
            logging.debug(f"Fetch options for {symbol}")

            ticker = yf.Ticker(symbol)
            today = datetime.today()
            cutoff_date = today + timedelta(days=max_dte)
            
            options_data = {}
            
            for exp_date in ticker.options:
                exp_datetime = datetime.strptime(exp_date, '%Y-%m-%d')
                
                if today <= exp_datetime <= cutoff_date:
                    option_chain = ticker.option_chain(exp_date)
                    
                    options_data[exp_date] = {
                        'calls': self._process_options(option_chain.calls, 'call'),
                        'puts': self._process_options(option_chain.puts, 'put'),
                        'days_to_expiration': (exp_datetime - today).days
                    }
            
            
            
            logging.debug(f"Fetched options for {symbol}")
            return options_data
        except Exception as e:
            logging.error(f"Error fetching options for {symbol}: {e}")
            return {"error": str(e), "symbol": symbol}
    
    def _process_options(self, options_df: pd.DataFrame, option_type: str) -> List[Dict]:
        """Process options dataframe into list of dictionaries"""
        processed = []
        for _, opt in options_df.iterrows():
            processed.append({
                'strike': float(opt['strike']),
                'option_type': option_type,
                'last_price': float(opt['lastPrice']) if 'lastPrice' in opt and not pd.isna(opt['lastPrice']) else None,
                'bid': float(opt['bid']) if 'bid' in opt and not pd.isna(opt['bid']) else None,
                'ask': float(opt['ask']) if 'ask' in opt and not pd.isna(opt['ask']) else None,
                'volume': int(opt['volume']) if 'volume' in opt and not pd.isna(opt['volume']) else 0,
                'open_interest': int(opt['openInterest']) if 'openInterest' in opt and not pd.isna(opt['openInterest']) else 0,
                'implied_volatility': float(opt['impliedVolatility']) if 'impliedVolatility' in opt and not pd.isna(opt['impliedVolatility']) else None,
            })
        return processed
    
    def get_trending_stocks(self, symbols: List[str], top_n: int = 8) -> List[str]:
        """
        Identify trending stocks based on volume and price momentum
        
        Args:
            symbols: List of symbols to analyze
            top_n: Number of top trending stocks to return
        
        Returns:
            List of trending stock symbols
        """
        trending = []
        
        for symbol in symbols:
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="10d")
                
                
                if len(hist) < 5:
                    continue
                
                # Calculate metrics
                avg_volume = hist['Volume'][:-1].mean()  # Exclude today
                today_volume = hist['Volume'].iloc[-1]
                volume_ratio = today_volume / avg_volume if avg_volume > 0 else 0
                
                # Price momentum
                price_change_5d = (hist['Close'].iloc[-1] - hist['Close'].iloc[0]) / hist['Close'].iloc[0] * 100
                
                logging.debug(f"Volume ratio for {symbol} is {volume_ratio}")
                
                # Only include stocks with significant activity
                if volume_ratio > 0.7 or symbol == "SPY":  # 50% above average volume
                    trending.append({
                        'symbol': symbol,
                        'volume_ratio': volume_ratio,
                        'price_change_pct': price_change_5d,
                        'score': volume_ratio * abs(price_change_5d)  # Combined score
                    })
            except Exception as e:
                logging.error(f"Error analyzing {symbol}: {e}")
                continue
        
        # Sort by combined score
        trending.sort(key=lambda x: x['score'], reverse=True)
        return [t['symbol'] for t in trending[:top_n]]
    
    def get_sp500_symbols(self) -> List[str]:
        """
        Get S&P 500 symbols from Wikipedia
        
        Returns:
            List of S&P 500 ticker symbols
        """
        try:
            headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies', headers=headers)
            table = pd.read_html(response.text)
            df = table[0]
            return df['Symbol'].tolist()
        except Exception as e:
            print(f"Error fetching S&P 500 symbols: {e}")
            print("Fallback to a subset")
            # Fallback to a subset
            return ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA',
                    'JPM', 'JNJ', 'V', 'PG', 'MA', 'HD', 'CVX', 'MRK', 'ABBV', 'PEP']

    def generate_search_queries(self,symbol: str) -> List[str]:
        """
        Identifies stock sector and returns a List of 3 targeted search strings.
        """
        # 1. Default fallback values
        sector = "General"
        industry = "General"
        
        try:
            # 2. Fetch Ticker info
            ticker = yf.Ticker(symbol)
            info = ticker.info
            sector = info.get('sector', 'General')
            industry = info.get('industry', 'General')
        except Exception:
            # Fallback if yfinance fetch fails
            pass

        # 3. Sector-to-Driver Map
        sector_drivers = {
            "Technology": "Semiconductor lead times and AI software demand",
            "Financial Services": "US Treasury yield curve and regional bank health",
            "Energy": "WTI Crude Oil prices and OPEC production updates",
            "Basic Materials": "Copper, Gold, and Iron Ore spot prices and China PMI",
            "Healthcare": "FDA drug approval calendar and healthcare policy news",
            "Consumer Cyclical": "Consumer spending data and retail earnings sentiment",
            "Communication Services": "Digital ad spend trends and streaming subscriber growth",
            "Utilities": "Interest rate sensitivity and natural gas storage reports",
            "Consumer Defensive": "Consumer staples inflation and grocery pricing trends"
        }
        
        # Select the driver based on sector
        driver = sector_drivers.get(sector, f"{sector} {industry} industry trends")
        
        # 4. Construct the List
        today = datetime.now().strftime('%Y-%m-%d')
        
        queries = [
            f"{symbol} stock news catalysts and analyst ratings last 24 hours",
            f"Current price trend of {driver} today {today}",
            f"S&P 500 VIX and FOMC market sentiment report for {today}"
        ]
        
        return queries  # Strictly returning a List[str]



