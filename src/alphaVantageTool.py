import os
import requests
import time
import yfinance as yf
import yoptions as yo
from datetime import datetime, timedelta

GLOBAL_QUOTE_KEY = "Global Quote"

ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")

def get_stock_data(symbol: str, use_mock_data: bool = False):
    """
    Fetches the symbol's current price, 200 day moving average and RSI
    """
    print(f"\n--- Calling get_stock_data for symbol: {symbol}, mock_data: {use_mock_data} ---")

    if use_mock_data:
        print(f"Returning mock data for {symbol}")
        return {
            "symbol": symbol,
            "price": 150.0 + len(symbol),
            "sma_200": 145.0 + len(symbol),
            "rsi_2": 8.0 - len(symbol)
        }
    
    if not ALPHA_VANTAGE_API_KEY:
        print(f"ERROR: ALPHA_VANTAGE_API_KEY is not set in .env file for symbol {symbol}")
        return {"error": "Alpha Vantage API key not set.", "symbol": symbol}

    try:
        # Get current price
        print(f"Fetch price for {symbol}")
        price_url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={ALPHA_VANTAGE_API_KEY}"
        price_response = requests.get(price_url).json()
        print("Sleep for 12 secs")
        time.sleep(12)  # Respect rate limits

        # Get 200-day SMA
        print(f"Fetch SMA for {symbol}")
        sma_url = f"https://www.alphavantage.co/query?function=SMA&symbol={symbol}&interval=daily&time_period=200&series_type=close&apikey={ALPHA_VANTAGE_API_KEY}"
        sma_response = requests.get(sma_url).json()
        print("Sleep for 12 secs")
        time.sleep(12)  # Respect rate limits

        # Get 2-day RSI
        print(f"Fetch RSI for {symbol}")
        rsi_url = f"https://www.alphavantage.co/query?function=RSI&symbol={symbol}&interval=daily&time_period=2&series_type=close&apikey={ALPHA_VANTAGE_API_KEY}"
        rsi_response = requests.get(rsi_url).json()
        print("Sleep for 12 secs")
        time.sleep(12)  # Respect rate limits

        current_price = float(price_response[GLOBAL_QUOTE_KEY]['05. price']) if 'Global Quote' in price_response and '05. price' in price_response[GLOBAL_QUOTE_KEY] else None
        sma_200_data = sma_response.get('Technical Analysis: SMA')
        sma_200 = float(sma_200_data[list(sma_200_data.keys())[0]]['SMA']) if sma_200_data else None
        rsi_2_data = rsi_response.get('Technical Analysis: RSI')
        rsi_2 = float(rsi_2_data[list(rsi_2_data.keys())[0]]['RSI']) if rsi_2_data else None

        print(f"Alpha Vantage API response for {symbol}: price={current_price}, sma_200={sma_200}, rsi_2={rsi_2}")
        return {
            "symbol": symbol,
            "price": current_price,
            "sma_200": sma_200,
            "rsi_2": rsi_2
        }

    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")
        return {"error": str(e), "symbol": symbol}

def get_sp500_symbols(use_mock_data: bool = False):
    print(f"\n--- Calling get_sp500_symbols, mock_data: {use_mock_data} ---")
    """Returns a list of S&P 500 stock symbols. (Hardcoded for demonstration)"""
    if use_mock_data:
        print("Returning mock S&P 500 symbols.")
        return ["MSFT", "GOOGL"]

    symbols = ["AAPL", "MSFT", "GOOGL", "AMZN"]
    print(f"Retrieved S&P 500 symbols: {symbols}")
    return symbols # Add more as needed

def get_options_data(symbol: str, use_mock_data: bool = False):
    """
    Fetches options data (expiration dates, strike prices, option prices, and Greek values)
    for a given stock symbol for the next two months using `yfinance` and `yoptions`.

    Args:
        symbol (str): The stock ticker symbol.
        use_mock_data (bool): If True, returns mock options data. Defaults to False.

    Returns:
        dict: A dictionary where keys are expiration dates (YYYY-MM-DD format) and values are lists of
              dictionaries, each representing an option contract with the following keys:
              - 'strike': The strike price.
              - 'option_type': 'call' or 'put'.
              - 'last_price': The last traded price of the option.
              - 'bid': The current bid price.
              - 'ask': The current ask price.
              - 'implied_volatility': The implied volatility of the option.
              - 'delta': The option's delta.
              - 'gamma': The option's gamma.
              - 'theta': The option's theta.
              - 'vega': The option's vega.
              - 'rho': The option's rho.
              Example: {
                  "2025-01-17": [
                      {'strike': 100, 'option_type': 'call', 'last_price': 5.0, 'bid': 4.9, 'ask': 5.1, 'implied_volatility': 0.2, 'delta': 0.7, 'gamma': 0.05, 'theta': -0.02, 'vega': 0.15, 'rho': 0.01},
                      {'strike': 105, 'option_type': 'put', 'last_price': 2.0, 'bid': 1.9, 'ask': 2.1, 'implied_volatility': 0.22, 'delta': -0.3, 'gamma': 0.04, 'theta': -0.01, 'vega': 0.12, 'rho': -0.005}
                  ],
                  "2025-02-14": [ ... ]
              }
              If an error occurs, it returns a dictionary with an "error" key.
    """
    print(f"\n--- Calling get_options_data for symbol: {symbol}, mock_data: {use_mock_data} ---")
    if use_mock_data:
        print(f"Returning mock options data for {symbol}")
        return {
            "2025-01-17": [
                {'strike': 100, 'option_type': 'call', 'last_price': 5.0, 'bid': 4.9, 'ask': 5.1, 'implied_volatility': 0.2, 'delta': 0.7, 'gamma': 0.05, 'theta': -0.02, 'vega': 0.15, 'rho': 0.01},
                {'strike': 105, 'option_type': 'put', 'last_price': 2.0, 'bid': 1.9, 'ask': 2.1, 'implied_volatility': 0.22, 'delta': -0.3, 'gamma': 0.04, 'theta': -0.01, 'vega': 0.12, 'rho': -0.005}
            ],
            "2025-02-14": [
                {'strike': 100, 'option_type': 'call', 'last_price': 6.0, 'bid': 5.9, 'ask': 6.1, 'implied_volatility': 0.21, 'delta': 0.75, 'gamma': 0.06, 'theta': -0.03, 'vega': 0.18, 'rho': 0.012},
                {'strike': 110, 'option_type': 'put', 'last_price': 3.0, 'bid': 2.9, 'ask': 3.1, 'implied_volatility': 0.23, 'delta': -0.35, 'gamma': 0.05, 'theta': -0.015, 'vega': 0.14, 'rho': -0.006}
            ]
        }
        
    print(f"Fetch stock options data for {symbol}")
    try:
        ticker = yf.Ticker(symbol)
        today = datetime.today()
        two_months_later = today + timedelta(days=60)

        options_data = {}

        for exp_date in ticker.options:
            exp_datetime = datetime.strptime(exp_date, '%Y-%m-%d')
            if today <= exp_datetime <= two_months_later:
                option_chain = ticker.option_chain(exp_date)
                options = option_chain.calls.append(option_chain.puts, ignore_index=True)
                
                options_data[exp_date] = []

                for _, option in options.iterrows():
                    # Ensure option_type is 'call' or 'put' for yoptions
                    option_type = 'call' if option['optionType'] == 'CALL' else 'put'

                    # Placeholder for dividend_yield and risk_free_rate. These would ideally be dynamic.
                    # For simplicity, using a common risk-free rate and 0 dividend yield.
                    dividend_yield = 0.0
                    risk_free_rate = 0.01  # Example: 1% annual risk-free rate

                    # Fetching underlying stock price to calculate Greeks if not directly available
                    # yfinance ticker.info can provide this.
                    # For simplicity, using option.lastPrice or fetching current price if available.
                    current_stock_price = ticker.info.get('regularMarketPrice')
                    if current_stock_price is None:
                        # Fallback if regularMarketPrice is not immediately available
                        print(f"Warning: Could not fetch regularMarketPrice for {symbol}. Using option.lastPrice as fallback for Greeks calculation.")
                        current_stock_price = option['lastPrice'] if 'lastPrice' in option and option['lastPrice'] is not None else option['bid']
                        if current_stock_price is None:
                            current_stock_price = option['ask']

                    # Implied volatility from yfinance is already available.
                    implied_volatility = option['impliedVolatility']

                    # Calculate Greeks using yoptions
                    # yoptions get_option_greeks expects expiration date as datetime object.
                    greeks = yo.get_option_greeks(
                        stock_price=current_stock_price,
                        strike_price=option['strike'],
                        time_to_expiry=(exp_datetime - today).days / 365.0,
                        interest_rate=risk_free_rate,
                        volatility=implied_volatility,
                        option_type=option_type
                    ).iloc[0]

                    options_data[exp_date].append({
                        'strike': option['strike'],
                        'option_type': option_type,
                        'last_price': option['lastPrice'] if 'lastPrice' in option else None,
                        'bid': option['bid'] if 'bid' in option else None,
                        'ask': option['ask'] if 'ask' in option else None,
                        'implied_volatility': implied_volatility,
                        'delta': greeks['delta'],
                        'gamma': greeks['gamma'],
                        'theta': greeks['theta'],
                        'vega': greeks['vega'],
                        'rho': greeks['rho']
                    })

        print(f"Options data for {symbol}: {options_data}")
        return options_data

    except Exception as e:
        print(f"Error fetching options data for {symbol}: {e}")
        return {"error": str(e), "symbol": symbol}