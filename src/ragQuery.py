from datetime import datetime
import logging
import os
from re import S

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken
import numpy as np
import requests

from ai_client_model_registry import ModelClientRegistry
from data_fetcher import StockDataFetcher
from logging_config import get_logger
from options_data_fetcher import OptionsDataFetcher
from prompts import optimize_for_llm
from trade_database import TradeDatabase

logger = get_logger(__name__)

# Embedding Generation (using Ollama)
def get_embeddings_ollama(text):
    """Gets embeddings from Ollama using the embeddings API endpoint."""
    url = "http://localhost:11434/api/embeddings"
    headers = {"Content-Type": "application/json"}
    data = {
        "model": os.environ.get("LLM_MODEL"),  # Use the correct model name
        "prompt": text
    }
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        return np.array(response.json()["embedding"])
    except requests.exceptions.RequestException as e:
        logger.error(f"Error calling Ollama API: {e}")
        return None

def get_options_chain_tool(symbol: str) -> str:
    """Finds the best option contract for the symbol.
     
    """
    
    logger.debug(f"Check option recommendations for {symbol}")

    fetcher = StockDataFetcher()
    opt_data = fetcher.get_options_data(symbol)
    
    return opt_data

def get_market_data(symbol: str) -> str:
    """
        Fetches price, RSI, volume, and trend data for a symbol.
        for e.g : get_market_data(TSLA)
    
    """

    logger.debug(f"Fetch market data for {symbol}")

    fetcher = StockDataFetcher()
    data = fetcher.get_enhanced_stock_data(symbol,'1y',60)
    # data = fetcher.get_stock_data(symbol)
    if "error" in data:
        #return f"Error: {data['error']}"
        raise ValueError({data['error']})
    
    
    return data 
    
async def augment_query_with_context(symbol:str,query:str):
    stock_details = get_market_data(symbol)

    current_price = stock_details['price']

    options_fetcher = OptionsDataFetcher()

    options_text = options_fetcher.get_options_for_llm(
        symbol=symbol,
        current_price=current_price,
        max_dte=60,
        max_exps=6
    )
    trade_database = TradeDatabase()
    live_portfolio = trade_database.get_live_portfolio_status()


    knowledge_base = f"""
      ### Stock Details 
      Stock details for {symbol}: {stock_details}
      
      ### Options Details
      Option details for {symbol}: {options_text}

      ### Live Portfolio
      {live_portfolio}

    """
    
    augmented_prompt = f"""
# TASK: Stock Analysis & Trading Strategy Recommendation

## CONTEXT & KNOWLEDGE BASE
{knowledge_base}

## USER QUERY
{query}

### INSTRUCTIONS
Based on the data provided, analyze the stock and recommend entry/exit points using **only one** of the following Momentum Strategies:
1. **Connors RSI 2**
2. **RSI Divergence**
3. **50-Crossover Signals**

### OUTPUT REQUIREMENTS
- Provide a concise answer for both **Stock** and **Option** recommendations.
- If the information provided is outdated or unclear, you **must** explicitly mention this in your response.
- Format your response using clear headers and bullet points.
"""

    logger.debug("**** Final Prompt")
    logger.debug("")
    logger.debug(augmented_prompt)
    logger.debug("")

    prompt_agent = AssistantAgent(
        name="Report_Agent",
        model_client=ModelClientRegistry.get_or_email_model_client(),
        reflect_on_tool_use=True,
        max_tool_iterations=3,
        system_message=optimize_for_llm
    )

    logger.debug("Optimizing augemeted query prompt")
    message = TextMessage(
        content=f"""Optimize this prompt for an LLM agent  : {augmented_prompt}
        """, 
        source="user"
    )

    response:TextMessage = await prompt_agent.on_messages(messages=[message], cancellation_token=CancellationToken())
    logger.debug(response.chat_message.content)
    return response.chat_message.content
