import asyncio
from datetime import datetime
import json
import logging
from typing import Dict, List

import gradio as gr
import markdown

from logging_config import get_logger
from ragQuery import augment_query_with_context
from stock_recommend_agent import StockRecommendAgent

logging = get_logger(__name__)


class TradingBotUI:
    """Gradio UI for Stock Recommendation Agent with streaming conversation"""
    
    def __init__(self):
        self.agent = StockRecommendAgent()
        self.conversation_history = []
    
    def parse_json_response(self, response: str) -> Dict:
        """Parse JSON response, handling potential markdown wrapping"""
        try:
            # Remove markdown code blocks if present
            cleaned = response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            
            cleaned = cleaned.strip()
            
            # Parse JSON
            data = json.loads(cleaned)
            
            # Handle both single object and array
            if isinstance(data, list):
                return data[0] if data else {}
            return data
            
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse JSON: {e}")
            return {
                "symbol": "ERROR",
                "stock_recommendation_strategy": "PARSE ERROR",
                "stock_recommendation_reasoning": f"Failed to parse response: {str(e)}"
            }
    
    def format_recommendation_card(self, data: Dict) -> str:
        """Format recommendation as HTML card"""
        
        symbol = data.get('symbol', 'N/A')
        entry_price = data.get('entry_price', 0)
        stop_loss = data.get('stop_loss', 0)
        take_profit = data.get('take_profit', 0)
        confidence = data.get('confidence_score', 0)
        
        stock_strategy = data.get('stock_recommendation_strategy', 'N/A')
        stock_reasoning = data.get('stock_recommendation_reasoning', 'N/A')
        
        option_strategy = data.get('option_recommendation_strategy', 'N/A')
        option_reasoning = data.get('option_recommendation_reasoning', 'N/A')
        option_contract = data.get('option_contract', 'N/A')
        
        # Color coding based on recommendation
        if stock_strategy == "BUY":
            card_color = "#d4edda"
            border_color = "#28a745"
        elif stock_strategy == "SELL":
            card_color = "#f8d7da"
            border_color = "#dc3545"
        elif stock_strategy == "NO TRADE":
            card_color = "#fff3cd"
            border_color = "#ffc107"
        else:
            card_color = "#e2e3e5"
            border_color = "#6c757d"
        
        html = f"""
        <div style="border: 3px solid {border_color}; border-radius: 10px; padding: 20px; margin: 10px 0; background-color: {card_color};">
            <h2 style="margin-top: 0; color: {border_color};">📊 {symbol} Trade Recommendation</h2>
            
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin: 15px 0;">
                <div style="background: white; padding: 10px; border-radius: 5px;">
                    <strong>Entry Price:</strong> ${entry_price:.2f}
                </div>
                <div style="background: white; padding: 10px; border-radius: 5px;">
                    <strong>Confidence:</strong> {confidence*100:.0f}%
                </div>
                <div style="background: white; padding: 10px; border-radius: 5px;">
                    <strong>Stop Loss:</strong> ${stop_loss:.2f}
                </div>
                <div style="background: white; padding: 10px; border-radius: 5px;">
                    <strong>Take Profit:</strong> ${take_profit:.2f}
                </div>
            </div>
            
            <div style="background: white; padding: 15px; border-radius: 5px; margin: 15px 0;">
                <h3 style="margin-top: 0; color: #333;">📈 Stock Recommendation</h3>
                <p><strong>Strategy:</strong> <span style="font-size: 18px; font-weight: bold; color: {border_color};">{stock_strategy}</span></p>
                <p><strong>Reasoning:</strong> {stock_reasoning}</p>
            </div>
            
            <div style="background: white; padding: 15px; border-radius: 5px; margin: 15px 0;">
                <h3 style="margin-top: 0; color: #333;">📉 Options Recommendation</h3>
                <p><strong>Strategy:</strong> <span style="font-size: 16px; font-weight: bold;">{option_strategy}</span></p>
                <p><strong>Contract:</strong> {option_contract}</p>
                <p><strong>Reasoning:</strong> {option_reasoning}</p>
            </div>
        </div>
        """
        return html
    
    def format_agent_message(self, agent_name: str, message: str, timestamp: str) -> str:
        """Format individual agent message, converting JSON to tables or Markdown to HTML"""
        
        agent_colors = {
            "Technical_Analyst_1": "#007bff",
            "Technical_Analyst_2": "#17a2b8",
            "Options_Strategist_1": "#28a745",
            "Options_Strategist_2": "#20c997",
            "Senior_Analyst": "#dc3545",
            "User": "#6f42c1" # Added a color for User
        }
        color = agent_colors.get(agent_name, "#6c757d")
        
        emoji_map = {
            "Technical_Analyst_1": "🔍",
            "Technical_Analyst_2": "📊",
            "Options_Strategist_1": "📈",
            "Options_Strategist_2": "💹",
            "Senior_Analyst": "👔",
            "User": "👤" # Added emoji for User
        }
        emoji = emoji_map.get(agent_name, "🤖")

        formatted_content = message
        
        # --- NEW LOGIC FOR USER (MARKDOWN) ---
        if agent_name.lower() == "user":
            # Convert Markdown string to HTML
            formatted_content = markdown.markdown(message)
        else:
            # --- EXISTING LOGIC FOR AGENTS (JSON TO TABLE) ---
            try:
                clean_msg = message.strip()
                if clean_msg.startswith("```json"): clean_msg = clean_msg[7:]
                if clean_msg.startswith("```"): clean_msg = clean_msg[3:]
                if clean_msg.endswith("```"): clean_msg = clean_msg[:-3]
                
                data = json.loads(clean_msg.strip())
                
                if isinstance(data, dict):
                    table_rows = "".join([
                        f"<tr style='border-bottom: 1px solid #eee;'>"
                        f"<td style='padding: 4px 8px; font-weight: bold; color: #555;'>{k.replace('_', ' ').title()}</td>"
                        f"<td style='padding: 4px 8px; color: #333;'>{v}</td></tr>" 
                        for k, v in data.items()
                    ])
                    formatted_content = f"<table style='width: 100%; border-collapse: collapse; font-size: 13px; background: white;'>{table_rows}</table>"
            except (json.JSONDecodeError, AttributeError):
                # Fallback: Treat as Markdown even for agents if it's not valid JSON
                formatted_content = markdown.markdown(message)

        html = f"""
        <div style="border-left: 4px solid {color}; padding: 10px; margin: 10px 0; background: #f8f9fa; border-radius: 5px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <strong style="color: {color}; font-size: 16px;">{emoji} {agent_name}</strong>
                <span style="color: #6c757d; font-size: 12px;">{timestamp}</span>
            </div>
            <div class="message-body" style="color: #333; font-family: sans-serif; font-size: 14px; line-height: 1.5;">
                {formatted_content}
            </div>
        </div>
        """
        return html

    def _wrap_scrollable(self, content: str) -> str:
        """Helper to wrap content in a scrollable div"""
        return f"""
        <div style="max-height: 600px; overflow-y: auto; padding-right: 10px; border: 1px solid #eee; border-radius: 8px;">
            {content}
        </div>
        """

    async def analyze_symbol_streaming(
        self, 
        symbol: str, 
        skip_llm: bool,
        progress=gr.Progress()
    ):
        """Analyze symbol with streaming updates"""
        symbol = symbol.strip().upper()
        self.conversation_history = []
        conversation_content = "<h3>🔄 Analysis Starting...</h3>"
        
        # Initial yield (Conversation HTML, Recommendation HTML, JSON Data)
        yield self._wrap_scrollable(conversation_content), "", {}
        
        try:
            progress(0, desc="Initializing agents...")
            trading_team = self.agent.create_trading_team()
            
            progress(0.1, desc="Preparing analysis task...")
            # Note: Ensure ragQuery and augment_query_with_context are importable
            try:
                
                task = f"""
### Analyze and recommend suitable trades for: {symbol}.
### Provide:
- Current entry price (use actual market data)
- Stop loss and take profit levels
- Stock recommendation strategy and reasoning
- Option recommendation strategy and reasoning
- Option details (strike, expiration, type)
"""
                augmented_query = augment_query_with_context(symbol, task)
            except ImportError:
                augmented_query = f"Analyze {symbol} and provide trading recommendations."

            if skip_llm:
                progress(1.0, desc="Using cached response...")
                mock_response = f"""[{{
                    "symbol": "{symbol}",
                    "entry_price": 150.0,
                    "stop_loss": 145.0,
                    "take_profit": 160.0,
                    "confidence_score": 0.75,
                    "shares": 100,
                    "stock_recommendation_strategy": "BUY",
                    "stock_recommendation_reasoning": "Mock recommendation - LLM calls skipped",
                    "option_recommendation_strategy": "Buy Long Call",
                    "option_recommendation_reasoning": "Mock options recommendation",
                    "option_strike": 155.0,
                    "option_expiration_date": "2025-02-21",
                    "option_type": "call",
                    "option_contract": "{symbol} 155 CALL 2025-02-21"
                }}]"""
                
                conversation_content = "<h3>⚠️ Using Mock Data (LLM Calls Skipped)</h3>"
                data = self.parse_json_response(mock_response)
                recommendation_html = self.format_recommendation_card(data)
                
                yield self._wrap_scrollable(conversation_content), recommendation_html, data
                return
            
            progress(0.2, desc="Running agent analysis...")
            conversation_content = "<h3>💬 Agent Conversation</h3>"
            
            stream = trading_team.run_stream(task=augmented_query)
            
            message_count = 0
            max_messages = 5
            
            async for message in stream:
                message_count += 1
                progress(0.2 + (0.7 * message_count / max_messages), 
                        desc=f"Agent {message_count}/{max_messages} responding...")
                
                timestamp = datetime.now().strftime("%H:%M:%S")
                agent_name = message.source
                content = str(message.content)
                
                agent_html = self.format_agent_message(agent_name, content, timestamp)
                conversation_content += agent_html
                
                yield self._wrap_scrollable(conversation_content), "", {}
            
            progress(0.9, desc="Formatting final recommendation...")
            
            result = await trading_team.run(task=augmented_query)
            final_response = result.messages[-1].content
            
            progress(1.0, desc="Complete!")
            
            data = self.parse_json_response(final_response)
            recommendation_html = self.format_recommendation_card(data)
            
            timestamp = datetime.now().strftime("%H:%M:%S")
            final_agent_html = self.format_agent_message(
                "Senior_Analyst",
                final_response,
                timestamp
            )
            conversation_content += final_agent_html
            
            # Final Yield: Full Conversation, Nice Card, and Raw JSON Data
            yield self._wrap_scrollable(conversation_content), recommendation_html, data
            
        except Exception as e:
            error_html = f"""
            <div style="border: 3px solid #dc3545; border-radius: 10px; padding: 20px; background-color: #f8d7da;">
                <h3 style="color: #dc3545;">❌ Error</h3>
                <p>{str(e)}</p>
            </div>
            """
            yield self._wrap_scrollable(conversation_content), error_html, {"error": str(e)}

    def create_interface_with_tabs(self):
      """Create interface with separate tabs for conversation and results"""
      
      with gr.Blocks(theme=gr.themes.Soft()) as demo:
          gr.Markdown("# 🤖 Multi-Agent Trading Bot")
          
          with gr.Row():
              symbol_input = gr.Textbox(label="Stock Symbol", value="AAPL")
              skip_llm = gr.Checkbox(label="Mock Mode", value=False)
              analyze_btn = gr.Button("Analyze", variant="primary")
          
          with gr.Tabs():
              with gr.Tab("💬 Agent Conversation"):
                  conversation_display = gr.HTML()
              
              with gr.Tab("📊 Recommendation"):
                  recommendation_display = gr.HTML()
              
              with gr.Tab("📄 Raw JSON"):
                  json_output = gr.JSON()
          
          analyze_btn.click(
              fn=self.analyze_symbol_streaming,
              inputs=[symbol_input, skip_llm],
              outputs=[conversation_display, recommendation_display, json_output]
          )
      
      return demo
    
    def launch(self, **kwargs):
        """Launch the Gradio interface"""
        demo = self.create_interface_with_tabs()
        demo.launch(**kwargs)


if __name__ == "__main__":
    ui = TradingBotUI()
    ui.launch(
        share=False,
        server_name="0.0.0.0",
        server_port=7860,
        show_error=True
    )