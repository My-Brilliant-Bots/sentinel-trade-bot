"""
Risk management module for position sizing and portfolio risk
"""
from typing import Dict, List

class RiskManager:
    """Manages position sizing and portfolio-level risk"""
    
    def __init__(self, 
                 account_size: float = 100000,
                 max_risk_per_trade_pct: float = 2.0,
                 max_portfolio_risk_pct: float = 6.0,
                 max_positions: int = 5):
        """
        Initialize risk management parameters
        
        Args:
            account_size: Total account value in dollars
            max_risk_per_trade_pct: Max % of account to risk per trade
            max_portfolio_risk_pct: Max % of account at risk across all positions
            max_positions: Maximum number of concurrent positions
        """
        self.account_size = account_size
        self.max_risk_per_trade = account_size * (max_risk_per_trade_pct / 100)
        self.max_portfolio_risk = account_size * (max_portfolio_risk_pct / 100)
        self.max_positions = max_positions
        self.current_positions = []
    
    def calculate_position_size(self, signal: Dict) -> Dict:
        """
        Calculate appropriate position size for a stock trade
        
        Args:
            signal: Trading signal with entry price and stop loss
        
        Returns:
            Dictionary with position sizing details
        """
        entry_price = signal['entry_price']
        stop_loss = signal['stop_loss']
        
        # Risk per share
        risk_per_share = entry_price - stop_loss
        
        if risk_per_share <= 0:
            return {"error": "Invalid stop loss - must be below entry price"}
        
        # Calculate shares based on max risk
        max_shares = int(self.max_risk_per_trade / risk_per_share)
        
        # Don't let position exceed certain % of account (e.g., 25%)
        max_position_value = self.account_size * 0.25
        max_shares_by_value = int(max_position_value / entry_price)
        
        # Use lesser of the two
        recommended_shares = min(max_shares, max_shares_by_value)
        
        # Calculate actual position metrics
        position_value = recommended_shares * entry_price
        total_risk = recommended_shares * risk_per_share
        risk_pct = (total_risk / self.account_size) * 100
        
        # Calculate potential profit at each target
        profit_at_tp1 = recommended_shares * (signal['take_profit_1'] - entry_price)
        profit_at_tp2 = recommended_shares * (signal['take_profit_2'] - entry_price)
        
        return {
            'symbol': signal['symbol'],
            'recommended_shares': recommended_shares,
            'position_value': round(position_value, 2),
            'total_risk_dollars': round(total_risk, 2),
            'risk_percentage': round(risk_pct, 2),
            'entry_price': entry_price,
            'stop_loss': stop_loss,
            'take_profit_1': signal['take_profit_1'],
            'take_profit_2': signal['take_profit_2'],
            'potential_profit_tp1': round(profit_at_tp1, 2),
            'potential_profit_tp2': round(profit_at_tp2, 2),
            'risk_reward_ratio_tp1': round(profit_at_tp1 / total_risk, 2),
            'risk_reward_ratio_tp2': round(profit_at_tp2 / total_risk, 2),
            'max_loss_dollars': round(total_risk, 2),
            'max_loss_percentage': round(risk_pct, 2)
        }
    
    def calculate_options_position_size(self, option: Dict) -> Dict:
        """
        Calculate appropriate number of options contracts
        
        Args:
            option: Options recommendation with cost per contract
        
        Returns:
            Dictionary with options position sizing details
        """
        cost_per_contract = option['cost_per_contract']
        
        # For options, max risk per trade still applies
        # Since we can lose 100% of premium, the position size is limited by max risk
        max_contracts = int(self.max_risk_per_trade / cost_per_contract)
        
        # Also limit by percentage of account (e.g., no more than 5% in one options position)
        max_contracts_by_pct = int((self.account_size * 0.05) / cost_per_contract)
        
        recommended_contracts = min(max_contracts, max_contracts_by_pct)
        recommended_contracts = max(1, recommended_contracts)  # At least 1 contract
        
        total_cost = recommended_contracts * cost_per_contract
        risk_pct = (total_cost / self.account_size) * 100
        
        # For long calls, max loss = premium paid
        max_loss = total_cost
        
        # Potential profit if stock reaches certain levels
        # This is simplified - actual profit depends on time decay and IV changes
        strike = option['strike']
        current_price = option.get('current_stock_price', strike)  # Approximate
        
        # Estimate profit if stock moves 10%, 20%
        intrinsic_value_10pct = max(0, (current_price * 1.10) - strike) * 100
        intrinsic_value_20pct = max(0, (current_price * 1.20) - strike) * 100
        
        profit_10pct = (intrinsic_value_10pct - cost_per_contract) * recommended_contracts
        profit_20pct = (intrinsic_value_20pct - cost_per_contract) * recommended_contracts
        
        return {
            'symbol': option['symbol'],
            'strategy': option['strategy'],
            'recommended_contracts': recommended_contracts,
            'cost_per_contract': cost_per_contract,
            'total_cost': round(total_cost, 2),
            'risk_percentage': round(risk_pct, 2),
            'max_loss': round(max_loss, 2),
            'expiration': option['expiration'],
            'strike': strike,
            'estimated_profit_10pct_move': round(profit_10pct, 2),
            'estimated_profit_20pct_move': round(profit_20pct, 2),
            'breakeven': option.get('breakeven'),
            'notes': f'Max loss limited to premium paid: ${max_loss:.2f}'
        }
    
    def check_portfolio_risk(self, new_position_risk: float) -> Dict:
        """
        Check if adding a new position would exceed portfolio risk limits
        
        Args:
            new_position_risk: Dollar amount at risk for new position
        
        Returns:
            Dictionary with approval status and current risk metrics
        """
        current_risk = sum([pos.get('risk', 0) for pos in self.current_positions])
        total_risk = current_risk + new_position_risk
        
        approved = (
            len(self.current_positions) < self.max_positions and
            total_risk <= self.max_portfolio_risk
        )
        
        return {
            'approved': approved,
            'current_positions': len(self.current_positions),
            'max_positions': self.max_positions,
            'current_risk_dollars': round(current_risk, 2),
            'new_position_risk': round(new_position_risk, 2),
            'total_risk_dollars': round(total_risk, 2),
            'max_portfolio_risk': round(self.max_portfolio_risk, 2),
            'risk_utilization_pct': round((total_risk / self.max_portfolio_risk) * 100, 1),
            'message': self._get_risk_message(approved, len(self.current_positions), total_risk)
        }
    
    def _get_risk_message(self, approved: bool, num_positions: int, total_risk: float) -> str:
        """Generate human-readable risk message"""
        if not approved:
            if num_positions >= self.max_positions:
                return f"REJECTED: Already at maximum positions ({self.max_positions})"
            else:
                return f"REJECTED: Portfolio risk would exceed limit (${total_risk:.2f} > ${self.max_portfolio_risk:.2f})"
        else:
            return f"APPROVED: Within risk limits ({num_positions + 1}/{self.max_positions} positions, ${total_risk:.2f}/${self.max_portfolio_risk:.2f} at risk)"
    
    def add_position(self, position: Dict):
        """Add a position to tracking"""
        self.current_positions.append(position)
    
    def remove_position(self, symbol: str):
        """Remove a position from tracking"""
        self.current_positions = [p for p in self.current_positions if p['symbol'] != symbol]
    
    def get_portfolio_summary(self) -> Dict:
        """Get current portfolio risk summary"""
        total_risk = sum([pos.get('risk', 0) for pos in self.current_positions])
        total_value = sum([pos.get('value', 0) for pos in self.current_positions])
        
        return {
            'account_size': self.account_size,
            'num_positions': len(self.current_positions),
            'max_positions': self.max_positions,
            'total_position_value': round(total_value, 2),
            'total_risk_dollars': round(total_risk, 2),
            'total_risk_pct': round((total_risk / self.account_size) * 100, 2),
            'max_risk_per_trade': round(self.max_risk_per_trade, 2),
            'max_portfolio_risk': round(self.max_portfolio_risk, 2),
            'available_risk': round(self.max_portfolio_risk - total_risk, 2),
            'positions': self.current_positions
        }