from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_agentchat.messages import BaseChatMessage, TextMessage
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_core.models import ModelInfo
from autogen_core import CancellationToken

from notificattionTool import send_email, send_sms_text
from alphaVantageTool import get_stock_data, get_sp500_symbols 

USE_MOCK_DATA = True # Set to False to use actual Alpha Vantage API calls

# Wrapper for data about stock symbols
def get_stock_data_wrapper(symbol: str):
  return get_stock_data(symbol, use_mock_data=USE_MOCK_DATA)

# Wrapper for get_sp500_symbols
def get_sp500_symbols_wrapper():
  return get_sp500_symbols(use_mock_data=USE_MOCK_DATA)

async def run_analysis():
  model_client = OpenAIChatCompletionClient(
  model="gpt-4.1",
  model_info=ModelInfo(vision=True, function_calling=True, json_output=True, family="unknown", structured_output=True),)

  stock_analyst_system_message="""
  You are a verbose and strict financial automation bot. You follow these steps to determine if a stock is a good Buy candidate:
  1. You fetch the list of stocks to analyse using the provided get_sp500_symbols_wrapper tool. 
  2. For each stock in the list of stocks from step 1, you fetch stock price, sma (Simple Moving Average), RSI (Relative Strength Indicator) using the provided get_stock_data_wrapper
  3. Once you have price, sma and rsi for each stock, use Price > 200-day SMA and RSI(2) < 10 to determine if the stock is a good Buy candidate. Create a detailed report for each stock and provide a reason why this stock is a good Buy candidate. The report should be in html format. There should be a separate section for each stock that has been analysed
  4. If no stocks matched the criteria, reply with "No Stocks Matched the criteria"
  5. Send an email containing the stocks that are good Buy candidates or email with "No Stocks Matched the criteria"
  6. Finally send a sms text notification that the job has completed
  """

  agent:AssistantAgent = AssistantAgent(
      name="StockAnalyst",
      model_client=model_client,
      system_message=stock_analyst_system_message,
      tools=[get_stock_data_wrapper,
      get_sp500_symbols_wrapper,
      send_email, 
      send_sms_text
      ],
      reflect_on_tool_use=True)

  user_message_str = "Please email me a list of stocks that have a buy signal for today"
  user_message= TextMessage(content=user_message_str, source="user")
  
  team = RoundRobinGroupChat(
    [agent],
    max_turns=10)
  
  result = await team.run(task="Execute all the steps and send an email with the result")
  for message in result.messages:
    print(f"{message.source}:\n{message.content}\n\n")
  

