import asyncio
import os
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.messages import TextMessage
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.models.ollama import OllamaChatCompletionClient
from autogen_core.models import ModelInfo
from autogen_core import CancellationToken
from dotenv import load_dotenv
from numba.parfors.array_analysis import SymbolicEquivSet

# Import your existing modules
from data_fetcher import StockDataFetcher
from strategy import TradingStrategy
from risk_manager import RiskManager
from options_strategy import OptionsStrategy
from ragQuery import augment_query_with_context

from notificattionTool import send_email, send_sms_text
from prompts import technical_analyst_prompt, risk_manager_system_prompt, options_strategist_system_prompt, data_clerk_system_prompt, report_agent_system_prompt

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
risk_mgr = RiskManager(account_size=100000)

def check_risk_tool(entry_price: float, stop_loss: float) -> str:
    """Calculates position size and validates risk parameters."""
    # Create a dummy signal dict to match your RiskManager's expected input
    signal = {'entry_price': entry_price, 'stop_loss': stop_loss}
    
    position = risk_mgr.calculate_position_size(signal)
    risk_mgr.check_portfolio_risk(position['total_risk_dollars'])
    
    return f"RISK APPROVED: Buy {position['recommended_shares']} shares. Total Risk: ${position['total_risk_dollars']:.2f}"


# Configure the LLM
model_client = OpenAIChatCompletionClient(
    model=os.environ.get("LLM_MODEL") ,
    response_format=TradeSignal,
    model_info=ModelInfo(vision=True, function_calling=True, json_output=True, family="unknown", structured_output=True),)

# 1. The Analyst: Reads the data and proposes a trade
analyst = AssistantAgent(
    name="Technical_Analyst",
    model_client=model_client,
    reflect_on_tool_use=True,
    system_message=technical_analyst_prompt
)

# 2. The Risk Manager: Validates the trade against account size
risk_agent = AssistantAgent(
    name="Risk_Manager",
    model_client=model_client,
    reflect_on_tool_use=True,
    system_message=risk_manager_system_prompt
)

# 3. The Options Strategist: Finds a derivative play
options_agent = AssistantAgent(
    name="Options_Strategist",
    model_client=model_client,
    reflect_on_tool_use=True,
    system_message=options_strategist_system_prompt
)

# Configure the Finalizer Agent
data_clerk = AssistantAgent(
    name="Data_Clerk",
    model_client=model_client,
    system_message=data_clerk_system_prompt
)

# Team will be created fresh for each symbol analysis to reset conversation history
def create_trading_team():
    """Create a fresh trading team instance with reset conversation history."""
    return RoundRobinGroupChat(
        participants=[analyst, options_agent, data_clerk],
        max_turns=3
    )

async def run_agentic_analysis():
    print("--- STARTING AGENTIC ANALYSIS ---")
    sp500 = fetcher.get_sp500_symbols()
    trending_symbols = fetcher.get_trending_stocks(sp500, top_n=3)
    
    print(f"Analyzing symbols: {trending_symbols}")
    
    all_signals_for_report = []
    # Prepare symbols list (limit to 5 for now)
    
    symbols_to_analyze = trending_symbols[:5]

    for symbol in symbols_to_analyze:
        stock_recommendation = await run_agentic_analysis_stock(symbol)
        clean_json = stock_recommendation.replace("```json", "").replace("```", "").strip()
        all_signals_for_report.append(clean_json)
    
    print(f"Stock Recommendations are {all_signals_for_report}")

    # Re-initilize the model
    model_client = OllamaChatCompletionClient(
    model="llama3.2",
    model_info=ModelInfo(vision=True, function_calling=True, json_output=True, family="unknown", structured_output=True),)

    report_agent = AssistantAgent(
    name="Report_Agent",
    model_client=model_client,
    tools=[send_email, send_sms_text],
    reflect_on_tool_use=True,
    system_message=report_agent_system_prompt)
    
    message = TextMessage(content=f"Please send an email with these stock and option recommendattions : {all_signals_for_report}", source="user")

    await report_agent.on_messages(messages=[message], cancellation_token=CancellationToken())

    return all_signals_for_report

async def run_agentic_analysis_stock( symbol_to_analyze ):
    # Create a fresh team instance to reset conversation history
    trading_team = create_trading_team()
    
    task = f"""Analyze and recommend suitable trades for the following stock symbol: {symbol_to_analyze}.

        Please provide:
        - Current entry price (use actual price from market data)
        - Stop loss and take profit levels
        - Stock recommendation strategy and reasoning
        - Option recommendation strategy and reasoning
        - Option strike price, expiration date, and type (call/put)
        - Option contract formatted string

        Process ALL symbols and provide recommendations for each one.
    """

    augemented_query = augment_query_with_context(symbol_to_analyze,task)

    result = await trading_team.run(task=augemented_query)
    
    # Print all messages for debugging
    for i, message in enumerate(result.messages):
        print(f"[{i+1}] {message.source}: {message.content}")
    
    # Get the last message content (from the Data_Clerk) - should be a JSON array
    final_msg = result.messages[-1].content
    print(f"\nFinal message from Data_Clerk:\n{final_msg}\n")
    
   
    return final_msg

if __name__ == "__main__":
    asyncio.run(run_agentic_analysis())