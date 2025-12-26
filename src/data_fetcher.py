"""
Data fetcher module using yfinance for fast, reliable data retrieval
No rate limits, much faster than Alpha Vantage
"""
import sys
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas_ta as ta
import requests

class StockDataFetcher:
    """Handles all stock data retrieval operations"""
    
    def __init__(self):
        self.cache = {}
    
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
            print(f"Fetch options for {symbol}")

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
            
            
            return options_data
        except Exception as e:
            print(f"Error fetching options for {symbol}: {e}")
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
                
                print(f"Volume ratio for {symbol} is {volume_ratio}")
                # Only include stocks with significant activity
                if volume_ratio > 0.7:  # 50% above average volume
                    trending.append({
                        'symbol': symbol,
                        'volume_ratio': volume_ratio,
                        'price_change_pct': price_change_5d,
                        'score': volume_ratio * abs(price_change_5d)  # Combined score
                    })
            except Exception as e:
                print(f"Error analyzing {symbol}: {e}")
                continue
        
        # Sort by combined score
        trending.sort(key=lambda x: x['score'], reverse=True)
        return [t['symbol'] for t in trending]
    
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
