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
    option_contract: Optional[str] = None
    strategy: str
    reasoning: str

# --- INSTANTIATE YOUR EXISTING CLASSES ---
fetcher = StockDataFetcher()
# We use the strategy class just to calculate raw indicators, not for the final decision
tech_calc = TradingStrategy() 
risk_mgr = RiskManager(account_size=100000)
opt_strat = OptionsStrategy()

# --- DEFINE TOOLS FOR THE AGENTS ---

def get_market_data_tool(symbol: str) -> str:
    """Fetches price, RSI, volume, and trend data for a symbol."""
    data = fetcher.get_stock_data(symbol)
    if "error" in data:
        return f"Error: {data['error']}"
    
    # We use your existing strategy class to get the raw numbers
    # Assuming your strategy class has a method to get raw indicators
    # If not, we just return the raw data dict
    return str(data) 

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
    

    opt_data = fetcher.get_options_data(symbol)
    # Mocking the stock_data input for the recommendation
    stock_data_mock = {'price': underlying_price} 
    
    rec = opt_strat.recommend_option(stock_data_mock, opt_data)
    if rec:
        return f"RECOMMENDATION: {rec['strategy']} | Strike: {rec['strike']} | Exp: {rec['expiration']}"
    return "No suitable options found."

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
    1. Call get_market_data_tool for the requested symbol.
    2. Analyze RSI, Volume, and Trend.
    3. If the setup looks bullish, propose a trade with:
       - Entry Price (current price)
       - Stop Loss (logical technical level)
       - Take Profit
    4. If the setup is weak, output "PASS" with a reason why the setup is weak
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
    1. If the Risk Manager approves a trade, call get_options_chain_tool.
    2. Recommend the specific contract to buy.
    3. Summarize the final execution plan.
    """
)
# Configure the Finalizer Agent
data_clerk = AssistantAgent(
    name="Data_Clerk",
    model_client=model_client,
    system_message="""
    You are a data entry specialist. 
    Review the conversation between the Analyst and Risk Manager.
    Extract the final trade details and output them strictly as a JSON object 
    matching the schema: {symbol, entry_price, stop_loss, take_profit, confidence_score, shares, option_contract, strategy,reasoning}. 
    If no trade was approved, update the reasonng field with No Trade recoommended
    Do not output as markdown. Output as json string
    with no ```json ```. return pure json
    """
)

# Create the team
trading_team = RoundRobinGroupChat(
    participants=[analyst, risk_agent, options_agent,data_clerk],
    max_turns=4 # Limits the conversation to one round of "Analyst -> Risk -> Options"
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

        result = await trading_team.run(task=f"Analyze {symbol}")
        
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