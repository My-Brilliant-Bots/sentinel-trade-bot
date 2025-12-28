from re import S
import requests
import numpy as np
from datetime import datetime
import os
from data_fetcher import StockDataFetcher
from options_strategy import OptionsStrategy
import logging

from logging_config import get_logger

logging = get_logger(__name__)

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
        logging.error(f"Error calling Ollama API: {e}")
        return None

def get_options_chain_tool(symbol: str) -> str:
    """Finds the best option contract for the symbol.
     
    """
    
    logging.debug(f"Check option recommendations for {symbol}")

    fetcher = StockDataFetcher()
    opt_data = fetcher.get_options_data(symbol)
    
    return opt_data

def get_market_data(symbol: str) -> str:
    """
        Fetches price, RSI, volume, and trend data for a symbol.
        for e.g : get_market_data(TSLA)
    
    """

    logging.debug(f"Fetch market data for {symbol}")

    fetcher = StockDataFetcher()
    data = fetcher.get_enhanced_stock_data(symbol,'1y',60)
    # data = fetcher.get_stock_data(symbol)
    if "error" in data:
        #return f"Error: {data['error']}"
        raise ValueError({data['error']})
    
    
    return data 
    
def augment_query_with_context(symbol:str,query:str):
    stock_details = get_market_data(symbol)
    option_details = get_options_chain_tool(symbol)

    knowledge_base = f"""
      Stock details for {symbol}: {stock_details}

      Option details for {symbol}: {option_details}

    """
    
    augmented_prompt = f"""
    Answer the question and recommend entry/exit points using either 
    1. Connors RSI 2, or
    2. RSI Divergence or 
    3. 50-Crossover signals, 
    
    Choose the appropiate Momentum Strategy based on the data provided in {knowledge_base} .
    Question: {query}

    Provide a concise answer about the stock and option recommendations. If the information appears outdated or unclear, mention that in your response."""

    return augmented_prompt
