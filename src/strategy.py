"""
Trading strategy implementation with entry/exit signals
Implements improved RSI-2 mean reversion strategy
"""
from typing import Dict, Optional, List
from datetime import datetime

class TradingStrategy:
    """Implements the below two trading strategies:
     RSI-2 mean reversion
     Momentum Trend Following strategy (buying the strength)
     RSI-MACD Recovery Strategy
     """
    
    def __init__(self, 
                 rsi_oversold: float = 15,
                 rsi_overbought: float = 65,
                 min_volume_ratio: float = 1.2,
                 require_uptrend: bool = True,
                 macd_fast: int = 12,
                 macd_slow: int = 26,
                 macd_signal: int = 9
                 ):
        """
        Initialize strategy parameters
        
        Args:
            rsi_oversold: RSI-2 threshold for oversold (entry signal)
            rsi_overbought: RSI-2 threshold for overbought (exit signal)
            min_volume_ratio: Minimum volume ratio (current/average)
            require_uptrend: Require price > 200-day SMA
        """
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.min_volume_ratio = min_volume_ratio
        self.require_uptrend = require_uptrend
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
    

    def generate_signal(self, stock_data: Dict) -> Optional[Dict]:

         # 1. Check RSI-MACD Recovery (The "Safe" Entry: Confirms the bottom is in. High win rate.)
        rsi_macd_recovery_signal = self._generate_rsi_macd_recovery_signal(stock_data) 
        if rsi_macd_recovery_signal:
            return rsi_macd_recovery_signal

         # 2. If no reversion, check Momentum (The "Profit Maker": Catches the middle of a big move. Higher reward.)
        momentum_signal = self._generate_momentum_signal(stock_data)
        if momentum_signal:
            return momentum_signal

        # 3. Check Mean Reversion (The "Scalp": Quick 2-5 day flips. High frequency.)
        reversion_signal = self._check_mean_reversion(stock_data) # Rename your old logic to this
        if reversion_signal:
            return reversion_signal
            
       
            
        return None
    
    def _check_mean_reversion(self, stock_data: Dict) -> Optional[Dict]:
        """
        Generate buy signal based on strategy criteria
        
        Args:
            stock_data: Dictionary containing stock data and indicators
        
        Returns:
            Signal dictionary with entry/exit parameters, or None if no signal
        """
        # Handle error case
        if "error" in stock_data:
            return None
        
        # Extract values
        symbol = stock_data['symbol']
        price = stock_data['price']
        sma_200 = stock_data.get('sma_200')
        rsi_2 = stock_data.get('rsi_2')
        rsi_14 = stock_data.get('rsi_14')
        atr_14 = stock_data.get('atr_14')
        volume_ratio = stock_data.get('volume_ratio', 1.0)
        
        # Check for missing data
        if None in [sma_200, rsi_2, atr_14]:
            print(f"Missing indicator data for {symbol}")
            return None
        
        # Strategy filters
        in_uptrend = price > sma_200
        is_oversold = rsi_2 < self.rsi_oversold
        has_volume = volume_ratio >= self.min_volume_ratio
        not_extremely_oversold_14 = rsi_14 > 25  # Avoid falling knives
        
        # Buy signal criteria
        buy_signal = is_oversold and has_volume and not_extremely_oversold_14
        
        if self.require_uptrend:
            buy_signal = buy_signal and in_uptrend
        
        if not buy_signal:
            return None
        
        # Calculate position parameters
        stop_loss = self._calculate_stop_loss(price, atr_14, stock_data['history'])
        take_profit_targets = self._calculate_take_profit(price, stop_loss, atr_14)
        confidence = self._calculate_confidence(stock_data)
        
        return {
            'symbol': symbol,
            'signal_type': 'BUY',
            "strategy": "RSI-2 Mean Reversion",
            'timestamp': datetime.now().isoformat(),
            'entry_price': price,
            'stop_loss': stop_loss,
            'take_profit_1': take_profit_targets[0],  # First target (50% of position)
            'take_profit_2': take_profit_targets[1],  # Second target (remaining 50%)
            'risk_reward_ratio': (take_profit_targets[0] - price) / (price - stop_loss),
            'confidence_score': confidence,
            'indicators': {
                'rsi_2': rsi_2,
                'rsi_14': rsi_14,
                'price_vs_sma_200': (price - sma_200) / sma_200 * 100,
                'volume_ratio': volume_ratio,
                'atr_14': atr_14
            },
            'exit_criteria': {
                'rsi_2_above': self.rsi_overbought,
                'stop_loss_hit': stop_loss,
                'take_profit_1_hit': take_profit_targets[0],
                'take_profit_2_hit': take_profit_targets[1],
                'days_in_trade_max': 10  # Exit after 10 days regardless
            }
        }
    
    def _calculate_stop_loss(self, price: float, atr: float, history) -> float:
        """
        Calculate stop loss using ATR-based method
        Also considers recent swing lows
        
        Args:
            price: Current stock price
            atr: 14-day Average True Range
            history: Price history dataframe
        
        Returns:
            Stop loss price level
        """
        # Method 1: ATR-based (2x ATR below entry)
        atr_stop = price - (2 * atr)
        
        # Method 2: Recent swing low (last 20 days)
        if len(history) >= 20:
            recent_low = history['Low'].iloc[-20:].min()
            swing_stop = recent_low * 0.99  # 1% below swing low
        else:
            swing_stop = price * 0.95
        
        # Use whichever is closer (less risky)
        return max(atr_stop, swing_stop)
    
    def _calculate_take_profit(self, price: float, stop_loss: float, atr: float) -> List[float]:
        """
        Calculate take profit targets based on risk/reward
        
        Args:
            price: Entry price
            stop_loss: Stop loss level
            atr: 14-day Average True Range
        
        Returns:
            List of take profit levels [target1, target2]
        """
        risk = price - stop_loss
        
        # First target: 2:1 risk/reward
        tp1 = price + (risk * 2)
        
        # Second target: 3:1 risk/reward
        tp2 = price + (risk * 3)
        
        return [round(tp1, 2), round(tp2, 2)]
    
    def _calculate_confidence(self, stock_data: Dict) -> float:
        """
        Calculate confidence score (0-100) based on multiple factors
        
        Args:
            stock_data: Dictionary containing stock data
        
        Returns:
            Confidence score between 0 and 100
        """
        score = 50  # Base score
        
        rsi_2 = stock_data.get('rsi_2')
        rsi_14 = stock_data.get('rsi_14')
        price = stock_data['price']
        sma_50 = stock_data.get('sma_50')
        sma_200 = stock_data.get('sma_200')
        volume_ratio = stock_data.get('volume_ratio', 1.0)
        
        # More oversold on RSI-2 = higher confidence
        if rsi_2 < 10:
            score += 20
        elif rsi_2 < 15:
            score += 10
        
        # Strong uptrend (price > both SMAs)
        if sma_50 and sma_200 and price > sma_50 > sma_200:
            score += 15
        
        # High volume confirmation
        if volume_ratio > 2.0:
            score += 10
        elif volume_ratio > 1.5:
            score += 5
        
        # RSI-14 not too oversold (avoid falling knives)
        if rsi_14 and 30 < rsi_14 < 50:
            score += 5
        
        return min(score, 100)
    
    def check_exit_signal(self, current_data: Dict, entry_signal: Dict, days_in_trade: int) -> Optional[str]:
        """
        Check if any exit criteria are met
        
        Args:
            current_data: Current stock data
            entry_signal: Original entry signal data
            days_in_trade: Number of days since entry
        
        Returns:
            Exit reason string if should exit, None otherwise
        """
        current_price = current_data['price']
        current_rsi_2 = current_data.get('rsi_2')
        
        # Stop loss hit
        if current_price <= entry_signal['stop_loss']:
            return f"STOP_LOSS_HIT at {current_price}"
        
        # Take profit targets
        if current_price >= entry_signal['take_profit_2']:
            return f"TAKE_PROFIT_2_HIT at {current_price}"
        elif current_price >= entry_signal['take_profit_1']:
            return f"TAKE_PROFIT_1_HIT at {current_price} (consider scaling out 50%)"
        
        # RSI overbought exit
        if current_rsi_2 and current_rsi_2 > self.rsi_overbought:
            return f"RSI_OVERBOUGHT at {current_rsi_2}"
        
        # Time-based exit
        if days_in_trade >= entry_signal['exit_criteria']['days_in_trade_max']:
            return f"MAX_DAYS_IN_TRADE ({days_in_trade} days)"
        
        return None

    def _generate_momentum_signal(self, stock_data: Dict) -> Optional[Dict]:
        """
        Generate BUY signal based on MACD Momentum (Trend Following)
        Best for: Catching the 'meat' of a 30-day move.
        """
        symbol = stock_data['symbol']
        price = stock_data['price']
        sma_50 = stock_data.get('sma_50')
        macd_line = stock_data.get('macd_line')
        macd_signal_line = stock_data.get('macd_signal_line')
        atr_14 = stock_data.get('atr_14')
        volume_ratio = stock_data.get('volume_ratio', 1.0)
        
        # Data Integrity Check
        if None in [sma_50, macd_line, macd_signal_line, atr_14]:
            return None

        # --- CRITERIA 1: Trend Filter ---
        # We only buy if the medium-term trend is already UP
        in_uptrend = price > sma_50
        
        # --- CRITERIA 2: Momentum Trigger (MACD Crossover) ---
        # We want the MACD to be slightly above the Signal line (fresh cross)
        # Check if cross happened recently (e.g., gap is small but positive)
        macd_gap = macd_line - macd_signal_line
        fresh_crossover = 0 < macd_gap < (price * 0.005) # Gap is positive but small (<0.5% of price)
        
        # --- CRITERIA 3: Volume Confirmation ---
        # Breakouts need volume
        strong_volume = volume_ratio > 1.0
        
        if in_uptrend and fresh_crossover and strong_volume:
            
            # STOP LOSS: Wider than mean reversion.
            # We use 3x ATR Trailing stop concept (initially fixed)
            stop_loss = price - (3 * atr_14)
            
            # TAKE PROFIT: Trend following needs room to run.
            # We look for a 1:3 or 1:4 Risk/Reward
            risk = price - stop_loss
            tp1 = price + (risk * 2)
            tp2 = price + (risk * 4) # Let winners run
            
            return {
                'symbol': symbol,
                'signal_type': 'BUY_MOMENTUM',
                'strategy': 'MACD_TREND',
                'timestamp': datetime.now().isoformat(),
                'entry_price': price,
                'stop_loss': round(stop_loss, 2),
                'take_profit_1': round(tp1, 2),
                'take_profit_2': round(tp2, 2),
                'confidence_score': self._calculate_momentum_confidence(stock_data),
                'reasoning': 'Price > SMA50 and Bullish MACD Crossover detected',
                'exit_criteria': {
                    'macd_cross_under': True, # Exit if MACD crosses back down
                    'stop_loss_hit': stop_loss
                }
            }
        return None

    def _calculate_momentum_confidence(self, stock_data) -> float:
        """Score the strength of the trend"""
        score = 60
        # If MACD is crossing while BELOW zero line, it's a stronger reversal signal
        if stock_data.get('macd_line') < 0:
            score += 15
        # If volume is massive
        if stock_data.get('volume_ratio') > 1.5:
            score += 15
        return min(score, 100)

    def _generate_rsi_macd_recovery_signal(self, stock_data: Dict) -> Optional[Dict]:
        """
        Generates a signal when an oversold stock shows momentum recovery.
        Best for: Safer entries than pure RSI mean reversion.
        """
        symbol = stock_data['symbol']
        price = stock_data['price']
        rsi_14 = stock_data.get('rsi_14')
        macd_hist = stock_data.get('macd_hist')     # Histogram value
        prev_macd_hist = stock_data.get('prev_macd_hist') # Yesterday's Histogram
        atr_14 = stock_data.get('atr_14')
        
        # Data check
        if None in [rsi_14, macd_hist, prev_macd_hist]:
            return None

        # --- CONDITION 1: The Alert (Oversold) ---
        # We use RSI 14 (standard) instead of RSI 2 (extreme) for this longer swing
        # We are lenient (RSI < 40) because we require MACD confirmation
        is_cheap = rsi_14 < 40

        # --- CONDITION 2: The Trigger (Momentum Shift) ---
        # We don't necessarily need a full crossover. 
        # We just need the Histogram to start ticking UP (getting less negative).
        # This gets us in slightly before the crossover.
        momentum_improving = (macd_hist > prev_macd_hist) and (macd_hist < 0)
        
        # --- CONDITION 3: Divergence (Optional but Powerful) ---
        # (Simplified check: Price is down, but Momentum is up)
        # This would require more historical data analysis
        
        if is_cheap and momentum_improving:
            
            # Stop Loss: Recent Low or Volatility based
            stop_loss = price - (2 * atr_14)
            
            return {
                'symbol': symbol,
                'signal_type': 'BUY_RECOVERY',
                'strategy': 'RSI_MACD_HYBRID',
                'timestamp': datetime.now().isoformat(),
                'entry_price': price,
                'stop_loss': round(stop_loss, 2),
                'take_profit_1': round(price + (price - stop_loss) * 2, 2),
                'confidence_score': self._score_recovery(rsi_14, macd_hist),
                'reasoning': f'Stock is oversold (RSI: {rsi_14:.1f}) and momentum is recovering.',
                'indicators': {
                    'rsi': rsi_14,
                    'macd_hist': macd_hist
                }
            }
        return None

    def _score_recovery(self, rsi, macd_hist) -> float:
        """Rate the quality of the recovery setup"""
        score = 60
        # The deeper the oversold, the better the bounce potential
        if rsi < 30: score += 20
        # If MACD is very close to crossing zero, that's bullish
        if -0.1 < macd_hist < 0: score += 10
        return score