import asyncio
import os
from dotenv import load_dotenv

# AutoGen imports
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_ext.models.ollama import OllamaChatCompletionClient
from autogen_core.models import ModelInfo
from autogen_core import CancellationToken

# Local modules
from data_fetcher import StockDataFetcher
from stock_recommend_agent import StockRecommendAgent
from notificattionTool import send_email, send_sms_text
from prompts import report_agent_system_prompt

load_dotenv()

async def run_agentic_analysis():
    print("--- STARTING AGENTIC ANALYSIS ---")

    fetcher = StockDataFetcher()
    sp500 = fetcher.get_sp500_symbols()
    
    # Ensure this env var is an integer, defaulting to 5 if not set
    max_stocks_to_recommended = int(os.environ.get("MAX_STOCK_RECOMMENDATIONS", 5))
    
    trending_symbols = fetcher.get_trending_stocks(sp500, top_n=max_stocks_to_recommended)
    
    print(f"Analyzing symbols: {trending_symbols}")
    
    all_signals_for_report = []
    
    # Initialize agents
    #model1_recommendation_engine = StockRecommendAgent("GEMINI_API_KEY", "LLM_MODEL_1","ollama")
    model1_recommendation_engine = StockRecommendAgent("CEREBRAS_API_KEY", "LLM_MODEL_2", "ollama_docker")

    for i, symbol in enumerate(trending_symbols):
        # Run recommendations in parallel
        #gemini_stock_recommendation, cerebras_stock_recommendation = await asyncio.gather(
        #    gemini_recommendation_agent.recommend_trades(symbol),
        #    carebras_recommendation_agent.recommend_trades(symbol),
        #    return_exceptions=True
        #)
        print("Gemma Model start")
        model1_stock_recommendation = await model1_recommendation_engine.recommend_trades(symbol)
        print("Gemma Model end")
       

        # Process Gemini result
        if isinstance(model1_stock_recommendation, str):
            gemini_clean_json = model1_stock_recommendation.replace("```json", "").replace("```", "").strip()
            print(f"Gemini Recommendation is {gemini_clean_json}")
            all_signals_for_report.append(gemini_clean_json)
        

        if i < len(trending_symbols) - 1:  
            print("Waiting 61 seconds to avoid rate limit...")
            await asyncio.sleep(61) 
    
    # Re-initialize the model using Ollama for reporting
    model_client = OllamaChatCompletionClient(
        model="llama3.2",
        model_info=ModelInfo(
            vision=True, 
            function_calling=True, 
            json_output=True, 
            family="unknown"
        ),
    )

    report_agent = AssistantAgent(
        name="Report_Agent",
        model_client=model_client,
        tools=[send_email, send_sms_text],
        reflect_on_tool_use=True,
        system_message=report_agent_system_prompt
    )
    
    message = TextMessage(
        content=f"Please send an email with these stock and option recommendations : {all_signals_for_report}", 
        source="user"
    )

    await report_agent.on_messages(messages=[message], cancellation_token=CancellationToken())

    return all_signals_for_report

if __name__ == "__main__":
    asyncio.run(run_agentic_analysis())