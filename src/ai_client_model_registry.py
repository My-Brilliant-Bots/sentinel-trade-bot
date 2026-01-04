import json
import os
from typing import Optional

from autogen_core.models import ModelInfo
from autogen_ext.models.openai import OpenAIChatCompletionClient


from pydantic import BaseModel

from logging_config import get_logger

logger = get_logger(__name__)

class StockSignal(BaseModel):
    symbol: str
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence_score: float
    shares: int
    market_research: str
    
    # Stock recommendation fields
    stock_recommendation_strategy: str  # e.g., "BUY", "SELL", "HOLD", "NO TRADE"
    stock_recommendation_reasoning: str  # Explanation for stock recommendation
    
    

class OptionSignal(BaseModel):
    stop_loss: float
    take_profit: float
    confidence_score: float
    market_research: str
    
    # Option recommendation fields
    option_recommendation_strategy: str  # e.g., "Buy Long Call", "Buy Long Put", "Covered Call", "NO TRADE"
    option_recommendation_reasoning: str  # Explanation for option recommendation
    
    option_strike: float  # Strike price of the option (e.g., 60.0)
    option_expiration_date: str # Expiration date in format "YYYY-MM-DD" or "Month DD, YYYY" (e.g., "2025-01-17" or "January 17, 2025")
    option_type: str  # "call" or "put"
    option_contract: str  # Formatted contract string (e.g., "NKE 60 CALL 2025-01-17" or "NKE $60 Put Jan 17, 2025")
    option_entry_price : float # Market price of the option
    option_target_exit_price : float 
    option_actual_exit_price : float
    num_of_contracts : int # Number of option contracts to buy

    #Volatility Fields
    implied_volatility: float    # IV at time of entry (e.g., 0.35 for 35%)
    historical_volatility: float  # HV (e.g., 20-day or 30-day realized)
    
    # The Greeks
    delta: float  # Sensitivity to underlying price
    gamma: float # Sensitivity of Delta to underlying price
    theta: float # Time decay (daily)
    vega: float   # Sensitivity to IV changes
    rho: float   # Sensitivity to interest rates

class TradeSignal(BaseModel):
    stock_signal: StockSignal
    option_signal: OptionSignal

class ModelClientRegistry:
    # Singleton storage
    _instances = {}

    @classmethod
    def _get_model_client(cls, key, api_key_env, model_env, provider_type):
        """Internal helper to manage the singleton logic."""
        if key not in cls._instances:
            # Reusing your provided factory logic
            cls._instances[key] = cls.create_openai_client(
                api_key_name=api_key_env,
                model_name=model_env,
                api_type=provider_type
            )
       
        return cls._instances[key]

    @staticmethod
    def create_openai_client(api_key_name, model_name, api_type):
        
        # 1. Define base configs for specific providers
        api_configs = {
            "cerebras": {
                "base_url": "https://api.cerebras.ai/v1", 
                 "response_format": StockSignal,
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
                "response_format": OptionSignal,
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

        logger.debug(f"LLM Provider Settings : {client_args}")

        # 4. Logic for API Key: Skip only for Ollama
        if api_type == "ollama":
            client_args["api_key"] = "not-required" # Local servers often ignore this
        else:
            # Require key from environment for all others
            client_args["api_key"] = os.environ.get(api_key_name)

        return OpenAIChatCompletionClient(**client_args)

    @classmethod
    def get_cerebras_client(cls):
        return cls._get_model_client("cerebras", "CEREBRAS_API_KEY", "CAREBRAS_LLM_MODEL", "cerebras")

    @classmethod
    def get_groq_client(cls):
        return cls._get_model_client("groq", "GROQ_API_KEY", "GROQ_LLM_MODEL", "groq")

    @classmethod
    def get_or_finance_client(cls):
        return cls._get_model_client("or_finance", "OPENROUTER_API_KEY", "OPENROUTER_FINANCE_LLM_MODEL", "openrouter")

    @classmethod
    def get_or_general_client(cls):
        return cls._get_model_client("or_general", "OPENROUTER_API_KEY", "OPENROUTER_LLM_MODEL", "openrouter")

    @classmethod
    def get_or_email_model_client(cls):

        model_client = OpenAIChatCompletionClient(
        model=os.environ.get("OPENROUTER_LLM_MODEL"),
        base_url= "https://openrouter.ai/api/v1", 
        api_key=os.environ.get("OPENROUTER_API_KEY"),
        default_headers ={
            "HTTP-Referer": "http://localhost:3000", # Required for OpenRouter rankings
            "X-Title": "StockAnalysisBot",           # Name of your bot
            "transforms": json.dumps([])             # Disables OpenRouter's auto-compression
        },
        model_info=ModelInfo(vision=True, function_calling=True, json_output=False, family="unknown", structured_output=False),)

        return model_client
