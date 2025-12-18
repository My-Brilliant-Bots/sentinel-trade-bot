# sentinel-trade-bot 🤖📈

An automated financial analysis system built with **Microsoft AutoGen**. This project leverages multi-agent collaboration to scan the S&P 500 for high-probability mean-reversion setups using **Alpha Vantage** data, providing instant alerts via email and SMS.

## 🚀 Overview
The system employs a dual-agent architecture to automate complex financial workflows:
1.  **AlphaVantage_Analyst (AssistantAgent):** An LLM-powered agent that writes and optimizes Python code to fetch technical indicators (RSI and SMA) while managing API rate limits and connection errors.
2.  **Executor (UserProxyAgent):** A local agent that executes the generated code, processes dataframes, and interacts with local messaging tools.



## 📊 The Strategy: "RSI(2) Mean Reversion"
The bot scans for stocks meeting the following criteria:
* **Trend Filter:** Price must be above the **200-day Simple Moving Average (SMA)** to ensure the asset is in a long-term uptrend.
* **Momentum Trigger:** The **2-period RSI** must be below **10**, identifying stocks that are significantly oversold in the short term.
* **Notification:** Once identified, the system generates an HTML report via `emailTool.py` and sends a mobile alert.

## 🛠️ Features
- **Autonomous Orchestration:** Fully autonomous coding and execution via AutoGen.
- **Alpha Vantage Integration:** Uses specialized technical indicator endpoints to reduce computational overhead.
- **Multi-Channel Alerting:** Integrated with a custom `emailTool.py` supporting **Resend (SMTP)** and **Pushover (SMS)**.
- **Rate-Limit Protection:** Intelligent retry mechanisms for both OpenAI and Alpha Vantage (5 calls/min) APIs.
- **High-Performance Env:** Managed via **uv** for lightning-fast dependency resolution and virtual environments.

## 📦 Installation

This project uses **uv** for dependency management. If you don't have it, install it via `curl -LsSf https://astral.sh/uv/install.sh | sh`.

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/your-username/sentinel-trade-bot.git](https://github.com/your-username/sentinel-trade-bot.git)
   cd sentinel-trade-bot