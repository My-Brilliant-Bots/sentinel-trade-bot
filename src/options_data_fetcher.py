import logging
import numpy as np
import yfinance as yf
from scipy.stats import norm
from datetime import datetime, timedelta

from logging_config import get_logger

logger = get_logger(__name__)

class OptionsAnalytics:
    @staticmethod
    def calculate_greeks(S, K, t, r, sigma, is_call=True):
        if t <= 0 or sigma <= 0:
            return {"delta": 0, "gamma": 0, "theta": 0, "vega": 0, "pop": 0, "pot": 0, "rr": "N/A"}
        
        # Core Black-Scholes variables
        d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * t) / (sigma * np.sqrt(t))
        d2 = d1 - sigma * np.sqrt(t)
        
        # Greeks
        delta = norm.cdf(d1) if is_call else norm.cdf(d1) - 1
        gamma = norm.pdf(d1) / (S * sigma * np.sqrt(t))
        vega = (S * norm.pdf(d1) * np.sqrt(t)) / 100 # Per 1% IV move
        
        # Theta (Daily Decay)
        term1 = -(S * norm.pdf(d1) * sigma) / (2 * np.sqrt(t))
        term2 = r * K * np.exp(-r * t) * (norm.cdf(d2) if is_call else -norm.cdf(-d2))
        theta = (term1 - term2) / 365
        
        # Probabilities (using 0.04 risk-free rate for drift)
        pop = norm.cdf(d2) if is_call else norm.cdf(-d2)
        pot = 2 * (1 - norm.cdf(abs(d2)))
        
        return {
            "delta": round(delta, 2),
            "gamma": round(gamma, 4),
            "theta": round(theta, 3),
            "vega": round(vega, 3),
            "pop": round(pop * 100, 1),
            "pot": round(min(pot * 100, 100), 1)
        }

class OptionsDataFetcher:
    def get_options_for_llm(self, symbol: str, current_price: float, max_dte: int = 5, max_exps: int = 2):
        
        logger.debug(f"Fetching options for {symbol}")
        
        ticker = yf.Ticker(symbol)
        # Calculate Historical Volatility for the header
        hist = ticker.history(period="1mo")
        hv = (hist['Close'].pct_change().std() * np.sqrt(252)) * 100
        
        output = f"Option details for {symbol}: Stock: {symbol}, Price: ${current_price:.2f}, HV30d: {hv:.1f}%\n"
        
        today = datetime.now()
        valid_exps = [e for e in ticker.options if (datetime.strptime(e, "%Y-%m-%d") - today).days <= max_dte][:max_exps]

        for exp in valid_exps:
            
            chain = ticker.option_chain(exp)
            dte = (datetime.strptime(exp, "%Y-%m-%d") - today).days
            t = max(dte, 1) / 365.0
            
            output += f"\n--- {exp} ({dte} DTE) ---\n"
            
            for label, data, is_call in [("Calls", chain.calls, True), ("Puts", chain.puts, False)]:
                
                output += f"\nTop 5 {label} by Volume:\n"
                # Filter for liquidity and proximity to price
                mask = (data['strike'] >= current_price * 0.90) & (data['strike'] <= current_price * 1.10)
                df = data[mask].sort_values('volume', ascending=False).head(5)
                
                for i, (_, row) in enumerate(df.iterrows(), 1):
                   
                    try:
                        g = OptionsAnalytics.calculate_greeks(current_price, row['strike'], t, 0.043, row['impliedVolatility'], is_call)
                        
                        # 1. LEGACY PART: Keeps "Strike $XXX (ATM): Premium $X, IVX%, Vol X"
                        # 2. NEW PART: Appends "Δ X, Γ X, Θ X, ν X, PoP X%"
                        output += (f"{i}. Strike ${row['strike']:.0f} ({'ATM' if abs(row['strike']-current_price)/current_price < 0.02 else 'OTM'}): "
                                f"Premium ${row['lastPrice']:.2f}, IV{int(row['impliedVolatility']*100)}%, Vol {int(row['volume'])}, "
                                f"Delta {g['delta']}, Gamma {g['gamma']}, Theta {g['theta']}, Vega {g['vega']}, PoP {g['pop']}%\n")
                    except Exception as e:
                        logger.error(e)
        return output

if __name__ == "__main__":
    fetcher = OptionsDataFetcher()
    print(fetcher.get_options_for_llm("AAPL", 240.50,max_dte=60,max_exps=6))