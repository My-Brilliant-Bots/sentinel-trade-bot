import asyncio
import json
import logging
import os
from typing import Optional

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_core.models import ModelInfo
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_core.tools import FunctionTool
from openai import RateLimitError
from pydantic import BaseModel

from logging_config import get_logger
from prompts import (
   options_strategist_system_prompt,
   senior_analyst_review_prompt,
   technical_analyst_prompt,
)
from ragQuery import augment_query_with_context
from search_tool import SearchTool
from data_fetcher import StockDataFetcher
from pydantic import BaseModel

logging = get_logger(__name__)


class TradeSignal(BaseModel):
    symbol: str
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence_score: float
    shares: int
    market_research: Optional[str] = None
    
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

class StockRecommendAgent:

  
  def create_openai_client(self,api_key_name:str,model_name:str, api_type=None):
    
    # 1. Define base configs for specific providers
    api_configs = {
        "cerebras": {
            "base_url": "https://api.cerebras.ai/v1", 
            "api_type": "cerebras"
        },
        "ollama": {
            "base_url": "http://localhost:11434/v1", 
            "api_type": "ollama"
        },
        "ollama_docker": {
            "base_url": "http://localhost:11434/v1", 
            "api_type": "ollama"
        },
        "openrouter": {
            "base_url": "https://openrouter.ai/api/v1", 
            "default_headers": {
                "HTTP-Referer": "http://localhost:3000", # Required for OpenRouter rankings
                "X-Title": "StockAnalysisBot",           # Name of your bot
                "transforms": json.dumps([])             # Disables OpenRouter's auto-compression
            }
        },
        "groq": {
            "api_type": "groq",
            "base_url": "https://api.groq.com/openai/v1"
        },
    }

    # 2. Start with common arguments used by EVERY client
    client_args = {
        "model": os.environ.get(model_name),
        "response_format": TradeSignal,
        "model_info": ModelInfo(
            vision=True, 
            function_calling=True, 
            json_output=True, 
            family="unknown",
            structured_output=True
        )
    }

    # 3. Add provider-specific settings (base_url, etc.)
    provider_settings = api_configs.get(api_type, {})
    client_args.update(provider_settings)

    logging.debug(f"LLM Provider Settings : {client_args}")

    # 4. Logic for API Key: Skip only for Ollama
    if api_type == "ollama":
        client_args["api_key"] = "not-required" # Local servers often ignore this
    else:
        # Require key from environment for all others
        client_args["api_key"] = os.environ.get(api_key_name)

    return OpenAIChatCompletionClient(**client_args)


  def create_trading_team(self):
    
    research_tool = FunctionTool(
      self.deep_market_research, 
      strict=True,
      description="Provides a comprehensive 3-tier market report for any stock ticker.")

    cerebras_model_client=self.create_openai_client("CEREBRAS_API_KEY", "CAREBRAS_LLM_MODEL", "cerebras")
    open_router_finance_model_client=self.create_openai_client("OPENROUTER_API_KEY", "OPENROUTER_FINANCE_LLM_MODEL", "openrouter")
    open_router_general_purpose_model_client=self.create_openai_client("OPENROUTER_API_KEY", "OPENROUTER_LLM_MODEL", "openrouter")
    groq_model_client=self.create_openai_client("GROQ_API_KEY", "GROQ_LLM_MODEL", "groq")

    market_researcher = AssistantAgent(
      name="Market_Researcher",
      model_client=open_router_general_purpose_model_client,
      tools=[research_tool],
      reflect_on_tool_use=True,
      system_message="""You provide the foundational facts for the trading team.
      When a ticker is provided, run the deep_market_research tool.
      Summarize the findings into: 
      1. Direct Ticker News 
      2. Sector/Commodity Health 
      3. Macro Sentiment."""
    )

    # Technical_Analyst_1 & Technical_Analyst_1 use two different LLM models hosted on different providers
    # to analyse the same stock
    analyst_1 = AssistantAgent(
      name="Technical_Analyst_1",
      model_client=cerebras_model_client,
      reflect_on_tool_use=True,
      system_message=technical_analyst_prompt
    )

    analyst_2 = AssistantAgent(
      name="Technical_Analyst_2",
      model_client=groq_model_client,
      reflect_on_tool_use=True,
      system_message=technical_analyst_prompt
    )

    # Options_Strategist_1 & Options_Strategist_2 use two different LLM models hosted on different providers
    # to analyse the same stock
    options_agent_1 = AssistantAgent(
        name="Options_Strategist_1",
        model_client=cerebras_model_client,
        reflect_on_tool_use=True,
        system_message=options_strategist_system_prompt
    )

    options_agent_2 = AssistantAgent(
        name="Options_Strategist_2",
        model_client=groq_model_client,
        reflect_on_tool_use=True,
        system_message=options_strategist_system_prompt
    )

    # Senior_Analyst uses a third LLM to review the results from the first two LLMs
    senior_analyst = AssistantAgent(
        name="Senior_Analyst",
        model_client=open_router_finance_model_client,
        system_message=senior_analyst_review_prompt
    )
    
    """Create a fresh trading team instance with reset conversation history."""
    return RoundRobinGroupChat(
        participants=[market_researcher,analyst_1, options_agent_1, analyst_2, options_agent_2,senior_analyst],
        max_turns=6)

  async def recommend_trades( self,symbol_to_analyze, skip_execution:bool=True ):
    # Create a fresh team instance to reset conversation history
    trading_team = self.create_trading_team()
    
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

    response = f"""
    {{
      "symbol": "{symbol_to_analyze}",
      "entry_price": 0,
      "stop_loss": 0,
      "take_profit": 0,
      "confidence_score": 0,
      "shares": 0,
      "stock_recommendation_strategy": "NO TRADE",
      "stock_recommendation_reasoning": "NO TRADE",
      "option_recommendation_strategy": "NO TRADE",
      "option_recommendation_reasoning": "NO TRADE",
      "option_strike": 0,
      "option_expiration_date": "N/A",
      "option_type": "N/A",
      "option_contract": "NO TRADE"
    }}
    """

    if (skip_execution):
      logging.debug("Skipping LLM calls. Returning canned response")
      return response

    logging.debug("Trading Team Start")
    
    try:
      result = await trading_team.run(task=augemented_query)
      logging.debug("Trading Team End")
      
      # Get the last message content (from the Senior_Analyst) - should be a JSON array
      response = result.messages[-1].content
      logging.debug(f"\nFinal message from Senior_Analyst:\n{response}\n")
    
      return response
    except RateLimitError as rateLimitError :
      logging.error(f"An error occurred: Rate Limit Exceeded: {rateLimitError}")
      return response
    except Exception as e:
      logging.error(f"An unexpected error occurred: {e}")
      return response
  
  def deep_market_research(self,symbol: str) -> str:
    """
    Performs a 3-tier web search to gather market context for a stock.

    Args:
        symbol (str): The stock ticker symbol (e.g., 'FCX', 'NVDA').
    """

    # Initialize your SearchTool class instance inside or globally
    # Using the searcher we built with Tenacity retries
    searcher = SearchTool(max_results=3) 
    
    # Generate the queries 
    data_fetcher = StockDataFetcher()
    print(f"Symbol to search is {symbol}")
    queries = data_fetcher.generate_search_queries(symbol=symbol)
    
    results = []
    
    for q in queries:
        try:
            # Executes with your built-in retry logic
            data = searcher.search(q)
            results.append(f"### Query: {q}\n{data}")
        except Exception as e:
            results.append(f"### Query: {q}\nError fetching data: {str(e)}")

    # Return as formatted string, NOT as Pydantic model
    report = f"""
      MARKET RESEARCH REPORT FOR {symbol}
      {'='*80}

      {chr(10).join(results)}

      {'='*80}
      End of Market Research Report
      """
    
    return report

def test_tool():
      agent = StockRecommendAgent()
      tool = agent.deep_market_research
      result = tool("AAPL")
      print(f"Tool output: {result}...")  # Check for valid structure
      # Try parsing as JSON if you convert it later


if __name__ == "__main__":
    test_tool()
  
       
  