# sentinel-trade-bot 🤖📈

## 🌟 About

An automated financial analysis system built with **Microsoft AutoGen**. This project leverages multi-agent collaboration to scan for high-probability mean-reversion setups using **Alpha Vantage** data, providing instant alerts via email and SMS. The bot focuses on identifying significantly oversold stocks in a long-term uptrend, generating detailed reports, and notifying users.

### 📊 The Strategy: "RSI(2) Mean Reversion"
The bot scans for stocks meeting the following criteria:
* **Trend Filter:** Price must be above the **200-day Simple Moving Average (SMA)** to ensure the asset is in a long-term uptrend.
* **Momentum Trigger:** The **2-period RSI** must be below **10**, identifying stocks that are significantly oversold in the short term.
* **Notification:** Once identified, the system generates an HTML report via `emailTool.py` and sends a mobile alert.

### 🛠️ Features
- **Autonomous Orchestration:** Fully autonomous coding and execution via AutoGen.
- **Alpha Vantage Integration:** Uses specialized technical indicator endpoints to reduce computational overhead.
- **Multi-Channel Alerting:** Integrated with a custom `emailTool.py` supporting **Resend (SMTP)** and **Pushover (SMS)**.
- **Rate-Limit Protection:** Intelligent retry mechanisms for both OpenAI and Alpha Vantage (5 calls/min) APIs.
- **High-Performance Env:** Managed via **uv** for lightning-fast dependency resolution and virtual environments.

## 🚀 Architecture
The system employs a multi-agent architecture to automate complex financial workflows:

1.  **StockAnalyst (AssistantAgent):** An LLM-powered agent that orchestrates the analysis. It utilizes the `MultimodalWebSurfer` to identify trending S&P 500 stocks, then fetches detailed stock and options data using `alphaVantageTool.py`. It applies a mean-reversion strategy to identify buy candidates, generates HTML reports, and leverages `notificattionTool.py` for alerts.

2.  **WebSurfer (MultimodalWebSurfer):** This agent is used by the `StockAnalyst` to browse financial websites (e.g., TradingView) to find trending stocks.

3.  **Local Tools (`alphaVantageTool.py`, `notificattionTool.py`):** These Python scripts provide the core functionalities:
    -   `alphaVantageTool.py`: Handles fetching real-time stock prices, 200-day Simple Moving Average (SMA), 2-period Relative Strength Index (RSI) from Alpha Vantage, and options data from yfinance. It includes intelligent retry mechanisms and rate-limit protection.
    -   `notificattionTool.py`: Manages multi-channel alerting, sending detailed HTML reports via email (Resend SMTP) and concise notifications via SMS (Pushover).

The agents communicate within a `RoundRobinGroupChat` to collaboratively achieve the financial analysis and alerting goals.

## 📦 Installation

This project uses **uv** for dependency management. If you don't have it, install it via `curl -LsSf https://astral.sh/uv/install.sh | sh`.

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/My-Brilliant-Bots/sentinel-trade-bot.git](https://github.com/My-Brilliant-Bots/sentinel-trade-bot.git)
   cd sentinel-trade-bot
2.  **Install dependencies:**
    ```bash
    uv pip install -r requirements.txt
    ```
3.  **Set up Environment Variables:**
    Create a `.env` file in the project root with the following:
    ```
    OPENAI_API_KEY="YOUR_OPENAI_API_KEY"
    ALPHA_VANTAGE_API_KEY="YOUR_ALPHA_VANTAGE_API_KEY"
    RESEND_SERVER="smtp.resend.com"
    RESEND_USER="resend"
    RESEND_API_KEY="YOUR_RESEND_API_KEY"
    FROM_EMAIL="your_verified_resend_email@example.com"
    TO_EMAIL="recipient_email@example.com"
    PUSHOVER_USER="YOUR_PUSHOVER_USER_KEY"
    PUSHOVER_TOKEN="YOUR_PUSHOVER_API_TOKEN"
    PUSHOVER_URL="https://api.pushover.net/1/messages.json"
    ```

## 🚀 Quick Start

To run the Sentinel Trade Bot, ensure your environment variables are set up and then execute the `main.py` script:

```bash
python src/main.py
```

The bot will perform the analysis, and if any buy candidates are found, you will receive an email with a detailed report and an SMS notification.