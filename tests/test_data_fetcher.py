"""
Test cases for StockDataFetcher.get_stock_data method
Uses real API calls to yfinance (no mocking)
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os
import time

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from data_fetcher import StockDataFetcher


class TestStockDataFetcherGetStockData:
    """Test suite for StockDataFetcher.get_stock_data method using real API calls"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.fetcher = StockDataFetcher()
        # Use well-known, stable stocks for testing
        self.test_symbols = ["AAPL", "MSFT", "GOOGL"]
        # Add small delay between API calls to avoid rate limiting
        time.sleep(0.5)
    
    
    def test_get_stock_data_success(self):
        """Test successful retrieval of stock data with real API call"""
        symbol = "NKE"  # Apple - reliable stock with good data
        
        # Execute - real API call
        result = self.fetcher.get_stock_data(symbol)
        
        # Assertions
        assert result is not None, "Result should not be None"
        assert "error" not in result, f"Should not have error: {result.get('error', 'N/A')}"
        assert result["symbol"] == symbol
        assert "price" in result
        assert isinstance(result["price"], float)
        assert result["price"] > 0, f"Price should be positive, got {result['price']}"
        
        # Check required fields
        required_fields = [
            "symbol", "price", "prev_close", "volume", "volume_ratio",
            "sma_50", "sma_200", "rsi_2", "rsi_14", "atr_14",
            "macd_line", "macd_signal_line", "macd_hist", "prev_macd_hist",
            "market_cap", "sector", "industry"
        ]
        for field in required_fields:
            assert field in result, f"Missing field: {field}"
        
        # Verify data types
        assert isinstance(result["price"], float)
        assert isinstance(result["volume"], float)
        assert isinstance(result["volume_ratio"], float)
        assert result["volume_ratio"] >= 0
        
        # Verify price is reasonable (AAPL typically $100-$200 range)
        assert 50 < result["price"] < 500, f"Price seems unreasonable: {result['price']}"
        
    
    def test_get_stock_data_invalid_symbol(self):
        """Test handling of invalid stock symbol"""
        invalid_symbol = "INVALID_SYMBOL_XYZ123"
        
        # Execute - real API call with invalid symbol
        result = self.fetcher.get_stock_data(invalid_symbol)
        
        # Assertions - should return error for invalid symbol
        assert result is not None
        assert "error" in result
        assert result["symbol"] == invalid_symbol
        assert "error" in result["error"] or "No data available" in result["error"]
    
    
    def test_get_stock_data_insufficient_data_short_period(self):
        """Test handling with short period that may not have enough data for SMA-200"""
        symbol = "AAPL"
        
        # Execute with short period
        result = self.fetcher.get_stock_data(symbol, period="5d")
        
        # Assertions - should still return data
        assert result is not None
        # With only 5 days, SMA-200 will be None, but other indicators should work
        assert result["symbol"] == symbol
        # SMA-200 should be None due to insufficient data for short period
        assert result["sma_200"] is None or pd.isna(result["sma_200"])
        # But price and basic data should be available
        assert result["price"] > 0
    
   
    def test_get_stock_data_multiple_symbols(self):
        """Test retrieving data for multiple different symbols"""
        symbols = ["AAPL", "MSFT", "GOOGL"]
        
        for symbol in symbols:
            # Execute - real API call
            result = self.fetcher.get_stock_data(symbol)
            
            # Assertions
            assert result is not None, f"Result should not be None for {symbol}"
            assert result["symbol"] == symbol
            assert "price" in result
            assert result["price"] > 0, f"Price should be positive for {symbol}"
            
            # Add small delay to avoid rate limiting
            time.sleep(0.5)
    
    
    def test_get_stock_data_different_periods(self):
        """Test get_stock_data with different period parameters using real API"""
        symbol = "MSFT"
        
        # Test different periods
        periods = ["1mo", "3mo", "6mo", "1y"]
        
        for period in periods:
            # Execute - real API call
            result = self.fetcher.get_stock_data(symbol, period=period)
            
            assert result is not None, f"Result should not be None for period {period}"
            assert result["symbol"] == symbol
            assert "price" in result
            assert result["price"] > 0
            
            # Verify history DataFrame has data
            assert isinstance(result["history"], pd.DataFrame)
            assert len(result["history"]) > 0, f"History should have data for period {period}"
            
            # Add delay between calls
            time.sleep(0.5)
    
    
    def test_get_stock_data_nan_handling(self):
        """Test proper handling of NaN values in indicators with real data"""
        symbol = "AAPL"
        
        # Execute - real API call
        result = self.fetcher.get_stock_data(symbol)
        
        # Assertions - should handle NaN gracefully
        assert result is not None
        assert "error" not in result
        
        # Check that None values are used for NaN indicators, or valid floats
        if result.get("sma_50") is not None:
            assert isinstance(result["sma_50"], float)
            assert not np.isnan(result["sma_50"])
        
        if result.get("rsi_2") is not None:
            assert isinstance(result["rsi_2"], float)
            assert not np.isnan(result["rsi_2"])
            # RSI should be between 0 and 100
            assert 0 <= result["rsi_2"] <= 100
    
    
    def test_get_stock_data_price_and_prev_close(self):
        """Test that price and prev_close are properly set with real data"""
        symbol = "AAPL"
        
        # Execute - real API call
        result = self.fetcher.get_stock_data(symbol)
        
        # Assertions
        assert result is not None
        assert "error" not in result
        assert "price" in result
        assert "prev_close" in result
        
        # Both should be positive floats
        assert isinstance(result["price"], float)
        assert isinstance(result["prev_close"], float)
        assert result["price"] > 0
        assert result["prev_close"] > 0
        
        # Price and prev_close should be close (within reasonable range)
        # They might be the same if only one day of data, or different if multiple days
        price_diff = abs(result["price"] - result["prev_close"])
        assert price_diff < result["price"] * 0.1, "Price and prev_close should be close"
    
    
    def test_get_stock_data_volume_ratio_calculation(self):
        """Test volume ratio calculation with real data"""
        symbol = "AAPL"
        
        # Execute - real API call
        result = self.fetcher.get_stock_data(symbol)
        
        # Assertions
        assert result is not None
        assert "error" not in result
        assert "volume_ratio" in result
        assert isinstance(result["volume_ratio"], float)
        assert result["volume_ratio"] > 0, "Volume ratio should be positive"
        
        # Volume ratio should be reasonable (typically between 0.1 and 10 for normal trading)
        assert 0.01 < result["volume_ratio"] < 100, f"Volume ratio seems unreasonable: {result['volume_ratio']}"
    
    
    def test_get_stock_data_macd_calculation(self):
        """Test that MACD indicators are calculated and included with real data"""
        symbol = "AAPL"
        
        # Execute - real API call
        result = self.fetcher.get_stock_data(symbol)
        
        # Assertions - MACD fields should be present
        assert result is not None
        assert "error" not in result
        assert "macd_line" in result
        assert "macd_signal_line" in result
        assert "macd_hist" in result
        assert "prev_macd_hist" in result
        
        # Values can be None if insufficient data, or float if calculated
        # With 1y period, we should have enough data for MACD
        if result["macd_line"] is not None:
            assert isinstance(result["macd_line"], float)
            assert not np.isnan(result["macd_line"])
        
        if result["macd_hist"] is not None:
            assert isinstance(result["macd_hist"], float)
            assert not np.isnan(result["macd_hist"])
    
    
    def test_get_stock_data_info_handling(self):
        """Test handling of ticker.info fields with real data"""
        symbol = "AAPL"
        
        # Execute - real API call
        result = self.fetcher.get_stock_data(symbol)
        
        # Assertions - should handle info fields gracefully
        assert result is not None
        assert "error" not in result
        assert "market_cap" in result
        assert "sector" in result
        assert "industry" in result
        assert "info" in result
        
        # For AAPL, these should typically have values
        # But we allow None in case API doesn't return them
        if result["sector"] is not None:
            assert isinstance(result["sector"], str)
            assert len(result["sector"]) > 0
        
        if result["industry"] is not None:
            assert isinstance(result["industry"], str)
            assert len(result["industry"]) > 0
    
    
    def test_get_stock_data_technical_indicators(self):
        """Test that all technical indicators are calculated correctly"""
        symbol = "MSFT"
        
        # Execute - real API call
        result = self.fetcher.get_stock_data(symbol)
        
        # Assertions
        assert result is not None
        assert "error" not in result
        
        # Check RSI values (should be between 0 and 100 if calculated)
        if result.get("rsi_2") is not None:
            assert 0 <= result["rsi_2"] <= 100, f"RSI-2 should be 0-100, got {result['rsi_2']}"
        
        if result.get("rsi_14") is not None:
            assert 0 <= result["rsi_14"] <= 100, f"RSI-14 should be 0-100, got {result['rsi_14']}"
        
        # Check ATR (should be positive if calculated)
        if result.get("atr_14") is not None:
            assert result["atr_14"] > 0, f"ATR should be positive, got {result['atr_14']}"
        
        # Check SMA values (should be positive if calculated)
        if result.get("sma_50") is not None:
            assert result["sma_50"] > 0, f"SMA-50 should be positive, got {result['sma_50']}"
        
        if result.get("sma_200") is not None:
            assert result["sma_200"] > 0, f"SMA-200 should be positive, got {result['sma_200']}"
    
    
    def test_get_stock_data_history_dataframe(self):
        """Test that history DataFrame contains expected columns"""
        symbol = "GOOGL"
        
        # Execute - real API call
        result = self.fetcher.get_stock_data(symbol)
        
        # Assertions
        assert result is not None
        assert "error" not in result
        assert "history" in result
        assert isinstance(result["history"], pd.DataFrame)
        
        # Check that history has expected columns
        expected_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
        for col in expected_columns:
            assert col in result["history"].columns, f"Missing column {col} in history"
        
        # History should have multiple rows for 1y period
        assert len(result["history"]) > 50, "History should have sufficient data points"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

