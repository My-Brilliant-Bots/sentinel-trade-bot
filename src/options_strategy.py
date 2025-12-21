"""
Options strategy for selecting optimal contracts
"""
from typing import Dict, Optional, List
from datetime import datetime
import math

class OptionsStrategy:
    """Select optimal options contracts based on strategy"""
    
    def __init__(self, 
                 strategy_type: str = 'long_call',
                 target_dte_min: int = 30,
                 target_dte_max: int = 45,
                 target_delta_min: float = 0.60,
                 target_delta_max: float = 0.80,
                 max_iv: float = 0.60):
        """
        Initialize options selection parameters
        
        Args:
            strategy_type: Type of options strategy (long_call, cash_secured_put, etc.)
            target_dte_min: Minimum days to expiration
            target_dte_max: Maximum days to expiration
            target_delta_min: Minimum acceptable delta
            target_delta_max: Maximum acceptable delta
            max_iv: Maximum implied volatility (avoid overpaying)
        """
        self.strategy_type = strategy_type
        self.target_dte_min = target_dte_min
        self.target_dte_max = target_dte_max
        self.target_delta_min = target_delta_min
        self.target_delta_max = target_delta_max
        self.max_iv = max_iv
    
    def recommend_option(self, stock_data: Dict, options_data: Dict) -> Optional[Dict]:
        """
        Recommend best option contract based on strategy
        
        Args:
            stock_data: Stock data including current price
            options_data: Options chain data
        
        Returns:
            Recommended option contract details or None
        """
        if "error" in options_data:
            return None
        
        if self.strategy_type == 'long_call':
            return self._select_long_call(stock_data, options_data)
        elif self.strategy_type == 'cash_secured_put':
            return self._select_cash_secured_put(stock_data, options_data)
        elif self.strategy_type == 'bull_call_spread':
            return self._select_bull_call_spread(stock_data, options_data)
        else:
            print(f"Strategy type {self.strategy_type} not implemented")
            return None
    
    def _select_long_call(self, stock_data: Dict, options_data: Dict) -> Optional[Dict]:
        """
        Select optimal long call option
        Look for ATM or slightly OTM calls with good delta and reasonable IV
        """
        current_price = stock_data['price']
        symbol = stock_data['symbol']
        
        candidates = []
        
        for exp_date, exp_data in options_data.items():
            dte = exp_data['days_to_expiration']
            
            # Filter by DTE
            if not (self.target_dte_min <= dte <= self.target_dte_max):
                continue
            
            for call in exp_data['calls']:
                strike = call['strike']
                last_price = call['last_price']
                bid = call['bid']
                ask = call['ask']
                iv = call['implied_volatility']
                volume = call['volume']
                open_interest = call['open_interest']
                
                # Skip if missing critical data
                if None in [last_price, bid, ask, iv]:
                    continue
                
                # Calculate moneyness (how close to ATM)
                moneyness = (strike - current_price) / current_price
                
                # We want ATM to slightly OTM (0% to 5% OTM)
                if not (-0.02 <= moneyness <= 0.05):
                    continue
                
                # Estimate delta (rough approximation)
                # For ATM calls, delta ≈ 0.5, OTM calls have lower delta
                estimated_delta = self._calculate_black_scholes_delta(S=current_price, 
                K=strike, 
                dte=dte, sigma=iv, option_type='call')
                
                # Check delta range
                if not (self.target_delta_min <= estimated_delta <= self.target_delta_max):
                    continue
                
                # Check IV not too high
                if iv > self.max_iv:
                    continue
                
                # Check liquidity (need some volume or open interest)
                if volume == 0 and open_interest < 100:
                    continue
                
                # Calculate bid-ask spread (want tight spreads)
                spread_pct = (ask - bid) / ((ask + bid) / 2) if (ask + bid) > 0 else 1.0
                
                # Calculate cost per contract
                cost_per_contract = last_price * 100
                
                # Breakeven price
                breakeven = strike + last_price
                
                # Required price move %
                required_move_pct = (breakeven - current_price) / current_price * 100
                
                # Score this option
                score = self._score_long_call(
                    moneyness, estimated_delta, iv, spread_pct, 
                    volume, open_interest, dte
                )
                
                candidates.append({
                    'symbol': symbol,
                    'strategy': 'LONG_CALL',
                    'expiration': exp_date,
                    'dte': dte,
                    'strike': strike,
                    'option_type': 'call',
                    'premium': last_price,
                    'bid': bid,
                    'ask': ask,
                    'estimated_delta': round(estimated_delta, 2),
                    'implied_volatility': round(iv, 4),
                    'volume': volume,
                    'open_interest': open_interest,
                    'cost_per_contract': cost_per_contract,
                    'breakeven': round(breakeven, 2),
                    'required_move_pct': round(required_move_pct, 2),
                    'bid_ask_spread_pct': round(spread_pct * 100, 2),
                    'moneyness_pct': round(moneyness * 100, 2),
                    'score': score,
                    'max_loss': cost_per_contract,
                    'max_loss_description': 'Premium paid (occurs if stock below strike at expiration)'
                })
        
        if not candidates:
            return None
        
        # Return best candidate
        candidates.sort(key=lambda x: x['score'], reverse=True)
        best = candidates[0]
        
        # Add recommendation rationale
        best['recommendation_rationale'] = self._generate_call_rationale(best, stock_data)
        
        return best
    
    def _select_cash_secured_put(self, stock_data: Dict, options_data: Dict) -> Optional[Dict]:
        """
        Select optimal cash-secured put (sell puts to acquire stock at discount)
        Look for OTM puts with good premium/risk ratio
        """
        current_price = stock_data['price']
        symbol = stock_data['symbol']
        
        candidates = []
        
        for exp_date, exp_data in options_data.items():
            dte = exp_data['days_to_expiration']
            
            if not (self.target_dte_min <= dte <= self.target_dte_max):
                continue
            
            for put in exp_data['puts']:
                strike = put['strike']
                last_price = put['last_price']
                bid = put['bid']
                ask = put['ask']
                iv = put['implied_volatility']
                
                if None in [last_price, bid, ask, iv]:
                    continue
                
                # Want OTM puts (strike below current price)
                # Target 5-10% below current price
                moneyness = (strike - current_price) / current_price
                
                if not (-0.15 <= moneyness <= -0.03):
                    continue
                
                # Premium collected per contract
                premium_collected = bid * 100
                
                # Effective entry price if assigned
                effective_entry = strike - bid
                discount_pct = (current_price - effective_entry) / current_price * 100
                
                # Return on capital (premium / strike price)
                return_on_capital = (bid / strike) * 100
                
                # Annualized return
                annualized_return = return_on_capital * (365 / dte)
                
                candidates.append({
                    'symbol': symbol,
                    'strategy': 'CASH_SECURED_PUT',
                    'expiration': exp_date,
                    'dte': dte,
                    'strike': strike,
                    'option_type': 'put',
                    'premium_collected': premium_collected,
                    'bid': bid,
                    'ask': ask,
                    'implied_volatility': round(iv, 4),
                    'effective_entry_price': round(effective_entry, 2),
                    'discount_vs_current_pct': round(discount_pct, 2),
                    'return_on_capital_pct': round(return_on_capital, 2),
                    'annualized_return_pct': round(annualized_return, 2),
                    'capital_required': strike * 100,
                    'max_profit': premium_collected,
                    'max_loss_description': f'Stock drops to zero: ${strike * 100 - premium_collected}'
                })
        
        if not candidates:
            return None
        
        # Sort by annualized return
        candidates.sort(key=lambda x: x['annualized_return_pct'], reverse=True)
        best = candidates[0]
        
        best['recommendation_rationale'] = f"""
Selling this put allows you to potentially acquire {symbol} at ${best['effective_entry_price']} 
({best['discount_vs_current_pct']}% below current price) while collecting ${best['premium_collected']} in premium.
If the stock stays above ${best['strike']}, you keep the premium ({best['return_on_capital_pct']}% return in {best['dte']} days).
Annualized return: {best['annualized_return_pct']}%
        """.strip()
        
        return best
    
    def _score_long_call(self, moneyness, delta, iv, spread_pct, 
                         volume, open_interest, dte) -> float:
        """Score a long call option (higher is better)"""
        score = 50
        
        # Prefer ATM to slightly OTM
        if -0.01 <= moneyness <= 0.02:
            score += 20
        
        # Prefer higher delta (more sensitive to stock movement)
        if delta >= 0.70:
            score += 15
        elif delta >= 0.60:
            score += 10
        
        # Prefer lower IV (cheaper options)
        if iv < 0.40:
            score += 15
        elif iv < 0.50:
            score += 10
        
        # Prefer tight spreads
        if spread_pct < 0.05:
            score += 10
        elif spread_pct < 0.10:
            score += 5
        
        # Prefer good liquidity
        if volume > 100 or open_interest > 500:
            score += 10
        elif volume > 50 or open_interest > 200:
            score += 5
        
        # Prefer moderate DTE (sweet spot 30-45 days)
        if 30 <= dte <= 45:
            score += 10
        
        return score
    
    def _generate_call_rationale(self, option: Dict, stock_data: Dict) -> str:
        """Generate human-readable rationale for call recommendation"""
        return f"""
This {option['dte']}-day call option offers good value with:
- Strike ${option['strike']} ({option['moneyness_pct']:.1f}% from current price)
- Estimated delta of {option['estimated_delta']} (good sensitivity to stock movement)
- Moderate IV of {option['implied_volatility']:.2%} (not overpaying for volatility)
- Cost: ${option['cost_per_contract']:.2f} per contract
- Breakeven: ${option['breakeven']} (requires {option['required_move_pct']:.1f}% move)
- Max loss limited to premium paid: ${option['max_loss']:.2f}

The option provides leveraged upside exposure while limiting downside risk to the premium paid.
        """.strip()

    def _calculate_black_scholes_delta(self, S, K, dte, sigma, option_type='call', r=0.045):
        """
        Calculate accurate Delta using Black-Scholes formula
        
        Args:
            S: Current stock price
            K: Strike price
            dte: Days to expiration
            sigma: Implied Volatility (decimal, e.g., 0.45)
            option_type: 'call' or 'put'
            r: Risk-free interest rate (default 4.5%)
        """
        if dte <= 0: return 0.0
        
        # Convert time to years
        t = dte / 365.0
        
        # Avoid division by zero
        if sigma == 0 or t == 0: return 0.0

        # Calculate d1
        # d1 represents the moneyness of the option standardized by volatility
        d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * t) / (sigma * math.sqrt(t))
        
        # Calculate CDF of Normal Distribution using Error Function (math.erf)
        # This mimics scipy.stats.norm.cdf(d1) without needing scipy
        cdf_d1 = 0.5 * (1.0 + math.erf(d1 / math.sqrt(2.0)))
        
        if option_type == 'call':
            return cdf_d1
        elif option_type == 'put':
            return cdf_d1 - 1.0
        else:
            return 0.0
