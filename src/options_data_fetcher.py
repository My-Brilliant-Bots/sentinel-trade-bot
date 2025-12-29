from typing import Dict, List
from datetime import datetime, timedelta
import yfinance as yf
import pandas as pd
import logging


class OptionsDataFetcher:
    """Fetch and format options data optimized for LLM consumption"""
    
    def get_options_for_llm(
        self,
        symbol: str,
        current_price: float,
        max_dte: int = 45,
        strike_range_pct: float = 0.10,
        max_expirations: int = 2
    ) -> str:
        """
        Get options data formatted for LLM to determine strategy
        
        Args:
            symbol: Stock ticker
            current_price: Current stock price
            max_dte: Maximum days to expiration
            strike_range_pct: % range around current price to include
            max_expirations: Number of expiration dates to include
        
        Returns:
            Formatted string for LLM to analyze and recommend strategy
        """
        # Get historical volatility
        historical_volatility = self._get_historical_volatility(symbol)
        
        options_data = self.get_options_data(
            symbol=symbol,
            current_price=current_price,
            max_dte=max_dte,
            strike_range_pct=strike_range_pct,
            max_expirations=max_expirations
        )
        
        if "error" in options_data:
            return f"Error: {options_data['error']}"
        
        return self._format_balanced_options(
            symbol, 
            current_price, 
            options_data,
            historical_volatility
        )

    def _get_historical_volatility(self, symbol: str, period: str = "1mo") -> float:
        """
        Calculate historical volatility (HV) from recent price data
        
        Args:
            symbol: Stock ticker
            period: Lookback period (default 1 month)
        
        Returns:
            Annualized historical volatility as decimal (e.g., 0.25 = 25%)
        """
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period)
            
            if hist.empty or len(hist) < 2:
                return None
            
            # Calculate daily returns
            hist['returns'] = hist['Close'].pct_change()
            
            # Calculate standard deviation of returns
            daily_volatility = hist['returns'].std()
            
            # Annualize (assuming 252 trading days per year)
            annual_volatility = daily_volatility * (252 ** 0.5)
            
            return annual_volatility
            
        except Exception as e:
            logging.warning(f"Error calculating historical volatility for {symbol}: {e}")
            return None

    def get_options_data(
        self, 
        symbol: str, 
        current_price: float,
        max_dte: int = 60,
        strike_range_pct: float = 0.15,
        max_expirations: int = 3
    ) -> Dict:
        """
        Fetch FILTERED options data optimized for LLM analysis
        
        Args:
            symbol: Stock ticker symbol
            current_price: Current stock price (for filtering strikes)
            max_dte: Maximum days to expiration
            strike_range_pct: % range around current price to include
            max_expirations: Number of expiration dates to include
        
        Returns:
            Dictionary with FILTERED options data
        """
        try:
            logging.debug(f"Fetching options for {symbol} at ${current_price:.2f}")
            
            ticker = yf.Ticker(symbol)
            
            # Check if options are available
            if not ticker.options:
                return {"error": "No options available for this symbol", "symbol": symbol}
            
            today = datetime.today()
            cutoff_date = today + timedelta(days=max_dte)
            
            # Calculate strike range
            min_strike = current_price * (1 - strike_range_pct)
            max_strike = current_price * (1 + strike_range_pct)
            
            options_data = {}
            expirations_added = 0
            
            for exp_date in ticker.options:
                if expirations_added >= max_expirations:
                    break
                
                exp_datetime = datetime.strptime(exp_date, '%Y-%m-%d')
                
                if today <= exp_datetime <= cutoff_date:
                    try:
                        option_chain = ticker.option_chain(exp_date)
                        
                        # Filter strikes within range
                        filtered_calls = self._filter_strikes(
                            option_chain.calls, 
                            min_strike, 
                            max_strike,
                            'call'
                        )
                        
                        filtered_puts = self._filter_strikes(
                            option_chain.puts,
                            min_strike,
                            max_strike,
                            'put'
                        )
                        
                        # Only include if we have valid options
                        if filtered_calls or filtered_puts:
                            options_data[exp_date] = {
                                'calls': filtered_calls,
                                'puts': filtered_puts,
                                'days_to_expiration': (exp_datetime - today).days
                            }
                            expirations_added += 1
                    except Exception as e:
                        logging.warning(f"Error fetching option chain for {exp_date}: {e}")
                        continue
            
            logging.debug(
                f"Fetched {expirations_added} expirations with "
                f"{sum(len(v['calls']) + len(v['puts']) for v in options_data.values())} total options"
            )
            
            return options_data
            
        except Exception as e:
            logging.error(f"Error fetching options for {symbol}: {e}")
            return {"error": str(e), "symbol": symbol}
    
    def _filter_strikes(
        self, 
        options_df: pd.DataFrame, 
        min_strike: float, 
        max_strike: float,
        option_type: str
    ) -> List[Dict]:
        """
        Filter options to only include relevant strikes
        
        Args:
            options_df: DataFrame of options
            min_strike: Minimum strike to include
            max_strike: Maximum strike to include
            option_type: 'call' or 'put'
        
        Returns:
            List of filtered option dictionaries
        """
        if options_df.empty:
            return []
        
        # Filter by strike range
        filtered = options_df[
            (options_df['strike'] >= min_strike) & 
            (options_df['strike'] <= max_strike)
        ]
        
        # Further filter by liquidity (volume > 0 or openInterest > 10)
        filtered = filtered[
            (filtered['volume'] > 0) | 
            (filtered['openInterest'] > 10)
        ]
        
        # Sort by strike
        filtered = filtered.sort_values('strike')
        
        # Process and return
        return self._process_options(filtered, option_type)
    
    def _process_options(
        self, 
        options_df: pd.DataFrame, 
        option_type: str
    ) -> List[Dict]:
        """
        Convert options DataFrame to list of dictionaries
        
        Args:
            options_df: DataFrame of options
            option_type: 'call' or 'put'
        
        Returns:
            List of option dictionaries with key metrics including ALL Greeks
        """
        if options_df.empty:
            return []
        
        options_list = []
        
        for _, row in options_df.iterrows():
            option_dict = {
                'strike': float(row['strike']),
                'lastPrice': float(row.get('lastPrice', 0)),
                'bid': float(row.get('bid', 0)),
                'ask': float(row.get('ask', 0)),
                'volume': int(row.get('volume', 0)),
                'openInterest': int(row.get('openInterest', 0)),
                'impliedVolatility': float(row.get('impliedVolatility', 0)) if pd.notna(row.get('impliedVolatility')) else None,
                'delta': float(row.get('delta', 0)) if pd.notna(row.get('delta')) else None,
                'gamma': float(row.get('gamma', 0)) if pd.notna(row.get('gamma')) else None,
                'theta': float(row.get('theta', 0)) if pd.notna(row.get('theta')) else None,
                'vega': float(row.get('vega', 0)) if pd.notna(row.get('vega')) else None,
                'rho': float(row.get('rho', 0)) if pd.notna(row.get('rho')) else None,
                'type': option_type
            }
            
            options_list.append(option_dict)
        
        return options_list
      
    def _format_balanced_options(
          self, 
          symbol: str, 
          price: float, 
          data: Dict,
          historical_volatility: float = None) -> str:

        """Structured format optimized for LLM parsing"""
        
        if not data:
            return f"No options data available for {symbol}"
        
        output = f"Stock: {symbol}, Price: ${price:.2f}"
        if historical_volatility:
            output += f", HV30d: {historical_volatility*100:.1f}%"
        output += "\n\n"
        
        for exp_date, exp_data in sorted(data.items()):
            dte = exp_data['days_to_expiration']
            
            output += f"--- {exp_date} ({dte} DTE) ---\n\n"
            
            # Calls
            top_calls = sorted(
                exp_data['calls'],
                key=lambda x: x.get('volume', 0) + x.get('openInterest', 0) / 10,
                reverse=True
            )[:5]
            
            if top_calls:
                output += "Top 5 Calls by Volume:\n"
                for i, c in enumerate(top_calls, 1):
                    output += f"{i}. Strike ${c['strike']:.0f} "
                    output += f"({self._get_moneyness(c['strike'], price, True)}): "
                    output += f"Premium ${c['lastPrice']:.2f}, "
                    
                    greeks = []
                    if c.get('delta'): greeks.append(f"Δ{c['delta']:.2f}")
                    if c.get('theta'): greeks.append(f"θ{c['theta']:.2f}")
                    if c.get('vega'): greeks.append(f"ν{c['vega']:.1f}")
                    if c.get('impliedVolatility'): 
                        greeks.append(f"IV{c['impliedVolatility']*100:.0f}%")
                    
                    output += ", ".join(greeks)
                    output += f", Vol {c.get('volume', 0)}\n"
                
                output += "\n"
            
            # Puts
            top_puts = sorted(
                exp_data['puts'],
                key=lambda x: x.get('volume', 0) + x.get('openInterest', 0) / 10,
                reverse=True
            )[:5]
            
            if top_puts:
                output += "Top 5 Puts by Volume:\n"
                for i, p in enumerate(top_puts, 1):
                    output += f"{i}. Strike ${p['strike']:.0f} "
                    output += f"({self._get_moneyness(p['strike'], price, False)}): "
                    output += f"Premium ${p['lastPrice']:.2f}, "
                    
                    greeks = []
                    if p.get('delta'): greeks.append(f"Δ{p['delta']:.2f}")
                    if p.get('theta'): greeks.append(f"θ{p['theta']:.2f}")
                    if p.get('vega'): greeks.append(f"ν{p['vega']:.1f}")
                    if p.get('impliedVolatility'): 
                        greeks.append(f"IV{p['impliedVolatility']*100:.0f}%")
                    
                    output += ", ".join(greeks)
                    output += f", Vol {p.get('volume', 0)}\n"
                
                output += "\n"
        
        output += "Greek symbols: Δ=Delta, θ=Theta, ν=Vega, IV=Implied Volatility\n"
        output += "Recommend optimal strategy (call/put/spread) based on Greeks and IV vs HV."
        
        return output


    def _get_moneyness(self, strike: float, price: float, is_call: bool) -> str:
      
          """Determine if option is ITM/ATM/OTM"""
          diff_pct = abs(strike - price) / price
          
          if is_call:
              if strike < price * 0.98:
                  return "ITM"
              elif diff_pct < 0.02:
                  return "ATM"
              else:
                  return "OTM"
          else:
              if strike > price * 1.02:
                  return "ITM"
              elif diff_pct < 0.02:
                  return "ATM"
              else:
                  return "OTM"

# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    fetcher = OptionsDataFetcher()
    
    # Test with a symbol
    symbol = "AAPL"
    current_price = 185.50
    
    # Get formatted options for LLM with all Greeks
    options_text = fetcher.get_options_for_llm(
        symbol=symbol,
        current_price=current_price
    )
    
    print(options_text)