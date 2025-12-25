import asyncio
import os
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.messages import TextMessage
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.models.ollama import OllamaChatCompletionClient
from autogen_core.models import ModelInfo
from dotenv import load_dotenv

# Import your existing modules
from data_fetcher import StockDataFetcher
from strategy import TradingStrategy
from risk_manager import RiskManager
from options_strategy import OptionsStrategy

from notificattionTool import send_email, send_sms_text

from pydantic import BaseModel
from typing import Optional, List
import json

load_dotenv()

class TradeSignal(BaseModel):
    symbol: str
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence_score: float
    shares: int
    
    # Stock recommendation fields
    stock_recommendation_strategy: str  # e.g., "BUY", "SELL", "HOLD", "NO TRADE"
    stock_recommendation_reasoning: str  # Explanation for stock recommendation
    
    # Option recommendation fields
    option_recommendation_strategy: str  # e.g., "Buy Long Call", "Buy Long Put", "Covered Call", "NO TRADE"
    option_recommendation_reasoning: str  # Explanation for option recommendation
    
    # Option contract details (required if option_recommendation_strategy is not "NO TRADE")
    option_strike: Optional[float] = None  # Strike price of the option (e.g., 60.0)
    option_expiration_date: Optional[str] = None  # Expiration date in format "YYYY-MM-DD" or "Month DD, YYYY" (e.g., "2025-01-17" or "January 17, 2025")
    option_type: Optional[str] = None  # "call" or "put"
    option_contract: Optional[str] = None  # Formatted contract string (e.g., "NKE 60 CALL 2025-01-17" or "NKE $60 Put Jan 17, 2025")

# --- INSTANTIATE YOUR EXISTING CLASSES ---
fetcher = StockDataFetcher()
# We use the strategy class just to calculate raw indicators, not for the final decision
tech_calc = TradingStrategy() 
risk_mgr = RiskManager(account_size=100000)
opt_strat = OptionsStrategy()

# --- DEFINE TOOLS FOR THE AGENTS ---

def get_market_data_tool(symbol: str) -> str:
    """Fetches price, RSI, volume, and trend data for a symbol."""

    print(f"Fetch market data for {symbol}")
    data = fetcher.get_stock_data(symbol)
    if "error" in data:
        return f"Error: {data['error']}"
    
    # Format the response in a clear, structured way that's easy for the LLM to parse
    price = data.get('price', 'N/A')
    rsi_2 = data.get('rsi_2', 'N/A')
    rsi_14 = data.get('rsi_14', 'N/A')
    sma_50 = data.get('sma_50', 'N/A')
    sma_200 = data.get('sma_200', 'N/A')
    volume_ratio = data.get('volume_ratio', 'N/A')
    atr_14 = data.get('atr_14', 'N/A')
    
    response = f"""Stock Data for {symbol}:
CURRENT PRICE: ${price:.2f}
RSI-2: {rsi_2:.2f if rsi_2 != 'N/A' else 'N/A'}
RSI-14: {rsi_14:.2f if rsi_14 != 'N/A' else 'N/A'}
SMA-50: ${sma_50:.2f if sma_50 != 'N/A' else 'N/A'}
SMA-200: ${sma_200:.2f if sma_200 != 'N/A' else 'N/A'}
Volume Ratio: {volume_ratio:.2f if volume_ratio != 'N/A' else 'N/A'}
ATR-14: ${atr_14:.2f if atr_14 != 'N/A' else 'N/A'}

IMPORTANT: Use the CURRENT PRICE value (${price:.2f}) as the entry_price in your trade recommendation.
"""
    return response 

def check_risk_tool(entry_price: float, stop_loss: float) -> str:
    """Calculates position size and validates risk parameters."""
    # Create a dummy signal dict to match your RiskManager's expected input
    signal = {'entry_price': entry_price, 'stop_loss': stop_loss}
    
    position = risk_mgr.calculate_position_size(signal)
    risk_check = risk_mgr.check_portfolio_risk(position['total_risk_dollars'])
    
    if not risk_check['approved']:
        return f"RISK REJECTED: {risk_check['message']}"
    
    return f"RISK APPROVED: Buy {position['recommended_shares']} shares. Total Risk: ${position['total_risk_dollars']:.2f}"

def get_options_chain_tool(symbol: str, underlying_price: float) -> str:
    """Finds the best option contract for the symbol."""
    
    print(f"Check option recommendations for {symbol}")

    opt_data = fetcher.get_options_data(symbol)
    # Mocking the stock_data input for the recommendation
    stock_data_mock = {'price': underlying_price, 'symbol': symbol} 
    
    rec = opt_strat.recommend_option(stock_data_mock, opt_data)
    print(f"The recommendation is {rec}")
    
    if not rec:
        return "NO OPTIONS RECOMMENDATION: No suitable options found (no options data returned)."

    # If an error dictionary is returned, surface the human-readable reason
    if 'error' in rec:
        return f"NO OPTIONS RECOMMENDATION: {rec['error']}"

    # Happy path: we have a concrete contract recommendation
    # Format response with all required fields in a structured way
    strike = rec.get('strike', 'N/A')
    expiration = rec.get('expiration', 'N/A')
    option_type = rec.get('option_type', 'call')
    strategy = rec.get('strategy', 'LONG_CALL')
    
    # Determine option type from strategy if not explicitly set
    if 'PUT' in strategy.upper() or 'PUT' in rec.get('strategy', '').upper():
        option_type = 'put'
    elif 'CALL' in strategy.upper() or 'CALL' in rec.get('strategy', '').upper():
        option_type = 'call'
    
    response = f"""Option Recommendation for {symbol}:
STRATEGY: {strategy}
OPTION_TYPE: {option_type}
STRIKE_PRICE: {strike}
EXPIRATION_DATE: {expiration}
DAYS_TO_EXPIRATION: {rec.get('dte', 'N/A')}
PREMIUM: ${rec.get('premium', 'N/A')}
ESTIMATED_DELTA: {rec.get('estimated_delta', 'N/A')}
IMPLIED_VOLATILITY: {rec.get('implied_volatility', 'N/A')}

IMPORTANT: Extract these exact values:
- option_strike: {strike} (use this numeric value)
- option_expiration_date: {expiration} (use this date in YYYY-MM-DD format)
- option_type: {option_type} (use "call" or "put")
- option_contract: Format as "{symbol} {strike} {option_type.upper()} {expiration}" or similar readable format
"""
    return response

# Configure the LLM
model_client = OllamaChatCompletionClient(
    model="llama3.2",
    response_format=TradeSignal,
    model_info=ModelInfo(vision=True, function_calling=True, json_output=True, family="unknown", structured_output=True),)

# 1. The Analyst: Reads the data and proposes a trade
analyst = AssistantAgent(
    name="Technical_Analyst",
    model_client=model_client,
    tools=[get_market_data_tool],
    system_message="""
    You are a conservative Technical Analyst.
    1. Get latest stock market data for the requested symbol.
    2. Extract the CURRENT PRICE from the tool response - this is the actual current stock price.
    3. Analyze RSI, Volume, and Trend from the tool response.
    4. If the setup looks bullish, propose a trade with:
       - Entry Price: MUST use the CURRENT PRICE value from the tool response (do not make up a price)
       - Stop Loss: Calculate based on ATR or technical support levels
       - Take Profit: Calculate based on risk/reward ratio
    5. If the setup is weak, output "PASS" with a reason why the setup is weak
    
    CRITICAL: Always use the exact CURRENT PRICE value shown in the tool response. Never invent or estimate prices.
    """
)

# 2. The Risk Manager: Validates the trade against account size
risk_agent = AssistantAgent(
    name="Risk_Manager",
    model_client=model_client,
    tools=[check_risk_tool],
    system_message="""
    You are the Risk Manager.
    1. If the Analyst says "PASS", you also say "PASS".
    2. If the Analyst proposes a trade, extract the Entry Price and Stop Loss.
    3. Call check_risk_tool.
    4. Output the approved position size or the rejection reason.
    """
)

# 3. The Options Strategist: Finds a derivative play
options_agent = AssistantAgent(
    name="Options_Strategist",
    model_client=model_client,
    tools=[get_options_chain_tool],
    system_message="""
    You are the Derivatives Specialist.
    1. Get latest option chain details for the requested symbol using get_options_chain_tool
    2. Analyze the option recommendations from the tool response
    3. If options are available, provide:
       - option_recommendation_strategy: Valid strategy like "Buy Long Call", "Buy Long Put", "Covered Call", etc.
       - option_recommendation_reasoning: Clear explanation of why this option is recommended
       - option_strike: The exact strike price (numeric value, e.g., 60.0)
       - option_expiration_date: Expiration date in "YYYY-MM-DD" format (e.g., "2025-01-17") or "Month DD, YYYY" format (e.g., "January 17, 2025")
       - option_type: "call" or "put"
       - option_contract: Formatted contract string (e.g., "NKE 60 CALL 2025-01-17" or "NKE $60 Put Jan 17, 2025")
    4. If no options are recommended, set:
       - option_recommendation_strategy: "NO TRADE"
       - option_recommendation_reasoning: Clear reason why no options were recommended (e.g., "No suitable options found: [reason from tool]")
       - All other option fields should be null
    
    IMPORTANT: Always extract the exact strike price and expiration date from the tool response. Do not invent or estimate these values.
    """
)
# Configure the Finalizer Agent
data_clerk = AssistantAgent(
    name="Data_Clerk",
    model_client=model_client,
    system_message="""
    You are a data entry specialist. 
    Review the conversation between the Analyst and Options_Strategist.
    Extract the final trade details and output them strictly as a JSON object matching this schema:
    
    {
        "symbol": "TICKER",
        "entry_price": 0.0,
        "stop_loss": 0.0,
        "take_profit": 0.0,
        "confidence_score": 0.0,
        "shares": 0,
        "stock_recommendation_strategy": "BUY/SELL/HOLD/NO TRADE",
        "stock_recommendation_reasoning": "explanation",
        "option_recommendation_strategy": "Buy Long Call/Buy Long Put/Covered Call/NO TRADE",
        "option_recommendation_reasoning": "explanation",
        "option_strike": 0.0 or null,
        "option_expiration_date": "YYYY-MM-DD" or "Month DD, YYYY" or null,
        "option_type": "call" or "put" or null,
        "option_contract": "formatted string" or null
    }
    
    IMPORTANT RULES:
    1. If option_recommendation_strategy is "NO TRADE", set option_strike, option_expiration_date, option_type, and option_contract to null
    2. If an option is recommended, ALL option fields must be populated:
       - option_strike: numeric strike price (e.g., 60.0)
       - option_expiration_date: date in "YYYY-MM-DD" format (e.g., "2025-01-17") or "Month DD, YYYY" format (e.g., "January 17, 2025")
       - option_type: "call" or "put"
       - option_contract: formatted string like "NKE 60 CALL 2025-01-17" or "NKE $60 Put Jan 17, 2025"
    3. entry_price must be the actual current stock price from the market data tool
    4. If no trade was approved, set stock_recommendation_strategy to "NO TRADE" and provide reasoning
    
    Do not output as markdown. Output as pure JSON string with no ```json ``` wrapper.
    """
)

# Create the team
trading_team = RoundRobinGroupChat(
    participants=[analyst, options_agent,data_clerk],
    max_turns=4 # Limits the conversation to one round of "Analyst  -> Options"
)


async def run_agentic_analysis():
    print("--- STARTING AGENTIC ANALYSIS ---")
    sp500 = fetcher.get_sp500_symbols()
    trending_symbols = fetcher.get_trending_stocks(sp500, top_n=3)
    all_signals_for_report = []
    
    print(f"Analyzing: {trending_symbols}")
    
    for symbol in trending_symbols[:5]:
        # 1. Run the team
        print(f"Analyze {symbol}")

        result = await trading_team.run(task=f"Recommend suitable trades for stock symbol: {symbol}. If the stock is a sell candidate , recommend a PUT option on {symbol}. The PUT Option recommendation should have a valid strike and expiration month+year")
        
        for i, message in enumerate(result.messages):
            print(f"[{i+1}] {message.source}: {message.content}")

        # 2. Get the last message content (from the Data_Clerk)
        final_msg = result.messages[-1].content
        print(f"Final message is {final_msg}")
        
        if "NO_TRADE" not in final_msg:
            try:
                # 3. Clean and parse the JSON string
                # We strip any markdown triple backticks if the LLM included them
                #clean_json = final_msg.replace("```json", "").replace("```", "").strip()
                signal_data = json.loads(final_msg)
                
                all_signals_for_report.append(signal_data)
                print(f"✅ Data captured for {symbol}")
            except Exception as e:
                print(f"❌ Failed to parse data for {symbol}: {e}")

    # 4. Pass to your existing ReportGenerator
    # report_gen.generate_stock_analysis_report(signals=all_signals_for_report, ...)
    return all_signals_for_report

if __name__ == "__main__":
    asyncio.run(run_agentic_analysis())