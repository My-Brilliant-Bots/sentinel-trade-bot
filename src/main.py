import asyncio
import logging
import os
import sys

from dotenv import load_dotenv

from data_fetcher import StockDataFetcher
from logging_config import get_logger
from notificattionTool import send_report
from stock_recommend_agent import StockRecommendAgent

logging = get_logger(__name__)
logging.debug("Checking RSI 2 conditions...") 

load_dotenv()
sys.tracebacklimit = 0

async def run_agentic_analysis():
    logging.debug("--- STARTING AGENTIC ANALYSIS ---")

    fetcher = StockDataFetcher()
    sp500 = fetcher.get_sp500_symbols()
    sp500.append("SPY")
    
    # Ensure this env var is an integer, defaulting to 5 if not set
    max_stocks_to_recommended = int(os.environ.get("MAX_STOCK_RECOMMENDATIONS", 5))
    
    trending_symbols = fetcher.get_trending_stocks(sp500, top_n=max_stocks_to_recommended)
    
    logging.debug(f"Analyzing symbols: {trending_symbols}")
    
    all_signals_for_report = []

    trade_recommendation_agent = StockRecommendAgent()
    
    for i, symbol in enumerate(trending_symbols):

        # Set skip_llm to True while debugging code that does not need LLM interaction.
        skip_llm:bool = False
        logging.debug(f"Start Recommendation for {symbol} ")
        try:
            trade_recommendation = await trade_recommendation_agent.recommend_trades(symbol,skip_llm)
        except Exception as e:
             logging.debug(f"Skip Recommendation for {symbol} because of {e} error")
             continue
        logging.debug(f"End Recommendation for {symbol} ")
       
        # Process the recommendation
        if isinstance(trade_recommendation, str):
            recommendation_json = trade_recommendation.replace("```json", "").replace("```", "").strip()
            logging.debug(f"Recommendation is {recommendation_json}")
            all_signals_for_report.append(recommendation_json)
        

        if i < len(trending_symbols) - 1:  
            logging.debug("Waiting 61 seconds to avoid rate limit...")
            await asyncio.sleep(61) 
    
    await send_report(all_signals_for_report)

    return all_signals_for_report

if __name__ == "__main__":
    asyncio.run(run_agentic_analysis())