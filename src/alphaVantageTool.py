import os
import requests
import time

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

        # Get options data (requires a premium Alpha Vantage API key)
        print(f"Fetch options data for {symbol}")
        options_url = f"https://www.alphavantage.co/query?function=HISTORICAL_OPTIONS&symbol={symbol}&apikey={ALPHA_VANTAGE_API_KEY}"
        options_response = requests.get(options_url).json()
        print("Sleep for 12 secs")
        time.sleep(12)  # Respect rate limits

        current_price = float(price_response[GLOBAL_QUOTE_KEY]['05. price']) if 'Global Quote' in price_response and '05. price' in price_response[GLOBAL_QUOTE_KEY] else None
        sma_200_data = sma_response.get('Technical Analysis: SMA')
        sma_200 = float(sma_200_data[list(sma_200_data.keys())[0]]['SMA']) if sma_200_data else None
        rsi_2_data = rsi_response.get('Technical Analysis: RSI')
        rsi_2 = float(rsi_2_data[list(rsi_2_data.keys())[0]]['RSI']) if rsi_2_data else None
        options_data_result = options_response.get('optionsData') # Assuming 'optionsData' is the key for options

        print(f"Alpha Vantage API response for {symbol}: price={current_price}, sma_200={sma_200}, rsi_2={rsi_2}, options_data={options_data_result}")
        return {
            "symbol": symbol,
            "price": current_price,
            "sma_200": sma_200,
            "rsi_2": rsi_2,
            "options_data": options_data_result
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
