import asyncio
import os
from pyexpat import model
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

from stock_recommend_agent import StockRecommendAgent

from pydantic import BaseModel
from typing import Optional, List
import json

load_dotenv()

async def run_agentic_analysis():
    print("--- STARTING AGENTIC ANALYSIS ---")

    fetcher = StockDataFetcher()
    sp500 = fetcher.get_sp500_symbols()
    trending_symbols = fetcher.get_trending_stocks(sp500, top_n=3)
    
    print(f"Analyzing symbols: {trending_symbols}")
    
    all_signals_for_report = []
    # Prepare symbols list (limit to 5 for now)
    
    symbols_to_analyze = trending_symbols[:5]

    recommendation_agent = StockRecommendAgent("GEMINI_API_KEY","LLM_MODEL")

    for i, symbol in enumerate(symbols_to_analyze):
        stock_recommendation = await recommendation_agent.run_agentic_analysis_stock(symbol)
        clean_json = stock_recommendation.replace("```json", "").replace("```", "").strip()
        all_signals_for_report.append(clean_json)
        if i < len(symbols_to_analyze) - 1:  # Don't wait after last symbol
            print("Waiting 10 seconds to avoid rate limit...")
            await asyncio.sleep(61) 
    
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

if __name__ == "__main__":
    asyncio.run(run_agentic_analysis())