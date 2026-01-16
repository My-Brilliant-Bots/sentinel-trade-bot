import asyncio
import logging

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.teams import SelectorGroupChat
from autogen_agentchat.conditions import TextMentionTermination, MaxMessageTermination
from autogen_core import CancellationToken
from autogen_core.tools import FunctionTool
from openai import RateLimitError


from ai_client_model_registry import ModelClientRegistry
from data_fetcher import StockDataFetcher
from logging_config import get_logger
from prompts import (
   options_strategist_system_prompt,
   portfolio_data_manager_system_prompt,
   senior_analyst_review_prompt,
   technical_analyst_prompt,
   market_researcher_prompt,
   mock_response_prompt
)
from ragQuery import augment_query_with_context
from search_tool import SearchTool
from trade_database import TradeDatabase

logger = get_logger(__name__)


class StockRecommendAgent:

  def create_trading_team(self):
    db = TradeDatabase()

    research_tool = FunctionTool(
      self.deep_market_research, 
      strict=True,
      description="Provides a comprehensive 3-tier market report for any stock ticker.")
    stock_data = StockDataFetcher()

    stock_tool = FunctionTool(
      stock_data.get_enhanced_stock_data, 
      strict=True,
      description="Provides stock data for any stock ticker.")
    
    option_tool = FunctionTool(
      stock_data.get_options_data, 
      strict=True,
      description="Provides option data for any stock ticker.")

    cerebras_model_client=ModelClientRegistry.get_cerebras_client()
    open_router_finance_model_client=ModelClientRegistry.get_or_finance_client()
    open_router_general_purpose_model_client=ModelClientRegistry.get_or_general_client()
    groq_model_client=ModelClientRegistry.get_groq_client()

    market_researcher = AssistantAgent(
      name="Market_Researcher",
      description="Conducts deep market research using web search to provide context for stock analysis.",
      model_client=open_router_general_purpose_model_client,
      tools=[research_tool,stock_tool,option_tool],
      reflect_on_tool_use=True,
      system_message=market_researcher_prompt
    )

    # Technical_Analyst_1 & Technical_Analyst_1 use two different LLM models hosted on different providers
    # to analyse the same stock
    analyst_1 = AssistantAgent(
      name="Technical_Analyst_1",
      description="Performs technical analysis on stocks using market data and research reports.Recommends trades based on established momentum strategies.",
      model_client=open_router_general_purpose_model_client,
      reflect_on_tool_use=True,
      system_message=technical_analyst_prompt
    )

    analyst_2 = AssistantAgent(
      name="Technical_Analyst_2",
      description="Performs technical analysis on stocks using market data and research reports.Recommends trades based on established momentum strategies.",
      model_client=open_router_general_purpose_model_client,
      reflect_on_tool_use=True,
      system_message=technical_analyst_prompt
    )

    # Options_Strategist_1 & Options_Strategist_2 use two different LLM models hosted on different providers
    # to analyse the same stock
    options_agent_1 = AssistantAgent(
        name="Options_Strategist_1",
        description="Specializes in options trading strategies based on market data and research reports.",
        model_client=open_router_general_purpose_model_client,
        reflect_on_tool_use=True,
        system_message=options_strategist_system_prompt
    )

    options_agent_2 = AssistantAgent(
        name="Options_Strategist_2",
        description="Specializes in options trading strategies based on market data and research reports.",
        model_client=open_router_general_purpose_model_client,
        reflect_on_tool_use=True,
        system_message=options_strategist_system_prompt
    )

    # Senior_Analyst uses a third LLM to review the results from the first two LLMs
    senior_analyst = AssistantAgent(
        name="Senior_Analyst",
        description="Reviews and consolidates trade recommendations from multiple analysts to produce final trade suggestions.One stock recommendation and one option recommendation per stock.",
        model_client=open_router_general_purpose_model_client,
        reflect_on_tool_use=True,
        system_message=senior_analyst_review_prompt
    )
    """
    portfolio_data_manager = AssistantAgent(
          name="Portfolio_Data_Manager",
          model_client=ModelClientRegistry.get_or_email_model_client(),
          tools=[db.save_signal,db.close_option_trade,db.close_stock_trade],
          max_tool_iterations=1,
          reflect_on_tool_use=True,
          system_message=portfolio_data_manager_system_prompt
      )
    """

    """Create a fresh trading team instance with reset conversation history.
    return RoundRobinGroupChat(
        participants=[market_researcher,
          analyst_1, 
          options_agent_1, 
          analyst_2, 
          options_agent_2,
          senior_analyst,
          #portfolio_data_manager
        ],
        max_turns=6)
    """
    
    # Selector prompt
    # Selector prompt
    selector_prompt = """
  You are orchestrating a trading analysis workflow. Select the next agent strategically.

AVAILABLE AGENTS:
- Market_Researcher: Gathers fundamental market data, news, and context (SPEAK FIRST)
- Technical_Analyst_1: Provides stock recommendations using technical analysis
- Technical_Analyst_2: Provides stock recommendations using technical analysis (independent view)
- Options_Strategist_1: Recommends options strategies and contract details
- Options_Strategist_2: Recommends options strategies and contract details (independent view)
- Senior_Analyst: Reviews all 4 analyst recommendations and makes final decision (SPEAK LAST)

WORKFLOW STAGES:
1. **Research Phase**: Market_Researcher provides fundamental context
2. **Analysis Phase**: Both Technical Analysts AND both Options Strategists provide independent recommendations
3. **Review Phase**: Senior_Analyst synthesizes all 4 recommendations into final decision

SELECTION RULES:
1. Start with Market_Researcher (if not spoken yet)
2. After research, select analysts in any order until all 4 have spoken:
   - Technical_Analyst_1 and Technical_Analyst_2 (both must speak)
   - Options_Strategist_1 and Options_Strategist_2 (both must speak)
3. Ensure each analyst speaks EXACTLY ONCE
4. Only select Senior_Analyst AFTER all 4 analysts have provided recommendations
5. After Senior_Analyst speaks, return "TERMINATE"

IMPORTANT:
- Do NOT allow analysts to speak multiple times
- Do NOT select Senior_Analyst until all 4 analysts have contributed
- Track which agents have already spoken

Based on the conversation history, who should speak next? If workflow is complete, return "TERMINATE".
"""

    trading_team = SelectorGroupChat(
      participants=[
        market_researcher,      # Speaks first
        analyst_1,              # Technical analyst 1
        analyst_2,              # Technical analyst 2
        options_agent_1,        # Options strategist 1
        options_agent_2,        # Options strategist 2
        senior_analyst          # Speaks last, synthesizes everything
    ],
    model_client=open_router_general_purpose_model_client,
    selector_prompt=selector_prompt,
    termination_condition=TextMentionTermination("TERMINATE") | MaxMessageTermination(10),
    allow_repeated_speaker=False  # Prevents same agent from speaking consecutively
   ) 
   
    return trading_team



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
    
    augemented_query = await augment_query_with_context(symbol_to_analyze,task)

    if (skip_execution):
      logger.debug("Skipping LLM calls. Returning canned response")
      return  mock_response_prompt


    logger.debug("Trading Team Start")
    
    try:
      result = await trading_team.run(task=augemented_query)
      logger.debug("Trading Team End")
      
      # Get the last message content (from the Senior_Analyst) - should be a JSON array
      response = result.messages[-1].content
      logger.debug(f"\nFinal message from Senior_Analyst:\n{response}\n")

      return response
    except RateLimitError as rateLimitError :
      logger.error(f"An error occurred: Rate Limit Exceeded: {rateLimitError}")
      return response
    except Exception as e:
      logger.error(f"An unexpected error occurred: {e}")
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

    logger.debug(f"Market Research contents is {results}")

    # Return as formatted string, NOT as Pydantic model
    report = f"""
      MARKET RESEARCH REPORT FOR {symbol}
      {'='*80}

      {chr(10).join(results)}

      {'='*80}
      End of Market Research Report
      """
    
    return report

async def test_tool():
      agent = StockRecommendAgent()
      research_tool = FunctionTool(
      agent.deep_market_research, 
      strict=True,
      description="Provides a comprehensive 3-tier market report for any stock ticker.")

      open_router_general_purpose_model_client=ModelClientRegistry.get_or_general_client()
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
      
      message = TextMessage(
        content="""
        Research this stock . Symbol=AAPL
        """, 
        source="user"
      )

      response: TextMessage = await market_researcher.on_messages(messages=[message], cancellation_token=CancellationToken())
      logger.debug(response.chat_message.content)

if __name__ == "__main__":
    asyncio.run(test_tool())
  
       
  