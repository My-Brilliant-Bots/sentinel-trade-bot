import asyncio
import os
from dotenv import load_dotenv

# New 0.4 Imports
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_core.tools import FunctionTool

# Import your local tools
from notificattionTool import send_email, send_sms_text
from alphaVantageTool import get_stock_data, get_sp500_symbols 
from stockAnalysiAgents import run_analysis

if __name__ == "__main__":
    load_dotenv()
    asyncio.run(run_analysis())