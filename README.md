# sentinel-trade-bot 🤖📈

## 🌟 About

An automated financial analysis system built with **Microsoft AutoGen**. This project leverages multi-agent collaboration to scan for high-probability mean-reversion setups using **yfinance** data, providing instant alerts via email and SMS. The bot focuses on identifying significantly oversold stocks in a long-term uptrend, generating detailed reports, and notifying users.

### 📊 Trading Strategies

The bot implements **three complementary trading strategies** that are evaluated in priority order:

#### 1. **RSI-MACD Recovery Strategy** (Priority 1 - "The Safe Entry")
* **Best For:** Safer entries with high win rate, catching momentum recovery
* **Entry Criteria:**
  - RSI-14 < 40 (oversold condition)
  - MACD Histogram improving (turning up from negative)
  - Momentum shift detected before full MACD crossover
* **Stop Loss:** 2x ATR below entry price
* **Take Profit:** 2:1 risk/reward ratio
* **Use Case:** Identifies stocks that are oversold but showing early signs of momentum recovery

#### 2. **Momentum Trend Following Strategy** (Priority 2 - "The Profit Maker")
* **Best For:** Catching the middle of big moves, higher reward potential
* **Entry Criteria:**
  - Price > SMA-50 (medium-term uptrend)
  - MACD line crosses above Signal line (fresh bullish crossover)
  - Volume confirmation (volume ratio > 1.0)
* **Stop Loss:** 3x ATR below entry (wider than mean reversion)
* **Take Profit:** 2:1 and 4:1 risk/reward targets (lets winners run)
* **Use Case:** Captures sustained trends and momentum breakouts

#### 3. **RSI-2 Mean Reversion Strategy** (Priority 3 - "The Scalp")
* **Best For:** Quick 2-5 day flips, high frequency trades
* **Entry Criteria:**
  - RSI-2 < 15 (significantly oversold)
  - Price > SMA-200 (long-term uptrend filter)
  - Volume ratio ≥ 1.2 (volume confirmation)
  - RSI-14 > 25 (avoids falling knives)
* **Stop Loss:** Maximum of (2x ATR) or (1% below recent 20-day low)
* **Take Profit:** 2:1 and 3:1 risk/reward targets
* **Exit Criteria:** RSI-2 > 65, stop loss hit, or 10-day maximum hold period
* **Use Case:** Quick mean reversion trades in trending stocks

**Strategy Selection:** The system evaluates strategies in priority order and returns the first matching signal. This ensures safer entries are preferred over riskier ones.

#### Strategy Configuration Parameters

The `TradingStrategy` class accepts the following configurable parameters:

- **`rsi_oversold`** (default: 15): RSI-2 threshold for oversold entry signals
- **`rsi_overbought`** (default: 65): RSI-2 threshold for overbought exit signals
- **`min_volume_ratio`** (default: 1.2): Minimum volume ratio (current/average) for entry confirmation
- **`require_uptrend`** (default: True): Require price > 200-day SMA for mean reversion entries
- **`macd_fast`** (default: 12): Fast period for MACD calculation
- **`macd_slow`** (default: 26): Slow period for MACD calculation
- **`macd_signal`** (default: 9): Signal period for MACD calculation

#### Risk Management Features

- **Dynamic Stop Loss:** Uses ATR-based stops (2-3x ATR) combined with recent swing lows
- **Take Profit Targets:** Two-tier profit taking (50% at TP1, 50% at TP2) with risk/reward ratios of 2:1 and 3-4:1
- **Confidence Scoring:** Multi-factor scoring system (0-100) based on:
  - RSI oversold depth
  - Trend strength (price vs SMAs)
  - Volume confirmation
  - MACD momentum signals
- **Exit Criteria:** Multiple exit triggers including stop loss, take profit targets, RSI overbought conditions, and maximum hold period (10 days)

### 🛠️ Features
- **Multi-Agent Architecture:** Uses AutoGen's RoundRobinGroupChat with specialized agents for technical analysis, risk management, and options strategy.
- **yfinance Integration:** Fast, reliable data retrieval without rate limits using yfinance.
- **Multi-Channel Alerting:** Integrated with `notificattionTool.py` supporting **Resend (SMTP)** and **Pushover (SMS)**.
- **Risk Management:** Built-in position sizing and portfolio risk management.
- **Options Strategy:** Automated options contract selection and recommendations.
- **High-Performance Env:** Managed via **uv** for lightning-fast dependency resolution and virtual environments.

## 🚀 Architecture
The system employs a multi-agent architecture to automate complex financial workflows:

### Active Components

1. **Main Entry Point (`main.py`):** Orchestrates the entire analysis pipeline using AutoGen agents.

2. **Agent Team (RoundRobinGroupChat):**
   - **Technical_Analyst:** Analyzes stock data and proposes trades based on technical indicators.
   - **Risk_Manager:** Validates trades against account size and risk parameters.
   - **Options_Strategist:** Recommends optimal options contracts for approved trades.
   - **Data_Clerk:** Extracts and formats final trade signals as JSON.

3. **Core Modules:**
   - **`data_fetcher.py` (StockDataFetcher):** Handles all stock data retrieval using yfinance. Fetches price data, technical indicators (RSI-2, RSI-14, SMA-50, SMA-200, MACD, ATR-14), volume analysis, and options chains. Also provides S&P 500 symbol list and trending stock identification.
   - **`strategy.py` (TradingStrategy):** Implements three complementary trading strategies evaluated in priority order:
     - **RSI-MACD Recovery** (Priority 1): Safer entries for oversold stocks showing momentum recovery
     - **Momentum Trend Following** (Priority 2): Captures sustained trends using MACD crossovers
     - **RSI-2 Mean Reversion** (Priority 3): Quick scalping trades on extreme oversold conditions
     - Includes confidence scoring, dynamic stop-loss calculation (ATR-based + swing low), and take-profit target calculation
   - **`risk_manager.py` (RiskManager):** Manages position sizing, stop-loss calculations, and portfolio-level risk limits. Enforces maximum risk per trade (default 2%) and maximum portfolio risk (default 6%).
   - **`options_strategy.py` (OptionsStrategy):** Selects optimal options contracts based on delta (0.60-0.80), DTE (30-45 days), and implied volatility criteria. Supports long call strategies with risk/reward optimization.
   - **`notificattionTool.py`:** Manages multi-channel alerting:
     - Email notifications via Resend SMTP (HTML reports)
     - SMS notifications via Pushover API

### Deprecated Files ⚠️

The following files are **deprecated** and not used in the current implementation:

- **`alphaVantageTool.py`:** Previously used for Alpha Vantage API integration. Replaced by `data_fetcher.py` which uses yfinance for faster, rate-limit-free data retrieval.
- **`stockAnalysiAgents.py`:** Legacy agent implementation using Alpha Vantage tools. Superseded by the current multi-agent architecture in `main.py`.
- **`backtester.py`:** Backtesting module for historical strategy testing. Not currently integrated into the main workflow.
- **`report_generator.py`:** HTML report generation module. Referenced in comments but not currently used in the active codebase.

Please see [High Level Architecture](https://github.com/My-Brilliant-Bots/sentinel-trade-bot/wiki#high-level-architecture) For more details

## 📁 Project Structure

```
src/
├── main.py                    # Main entry point - orchestrates multi-agent analysis
├── data_fetcher.py           # Stock data retrieval using yfinance
├── strategy.py                # Trading strategy implementations (RSI-MACD Recovery, Momentum Trend Following, RSI-2 Mean Reversion)
├── risk_manager.py            # Position sizing and risk management
├── options_strategy.py        # Options contract selection and recommendations
├── notificattionTool.py       # Email (Resend) and SMS (Pushover) notifications
│
├── [DEPRECATED] alphaVantageTool.py    # Legacy Alpha Vantage integration
├── [DEPRECATED] stockAnalysiAgents.py  # Legacy agent implementation
├── [DEPRECATED] backtester.py          # Historical backtesting (not integrated)
└── [DEPRECATED] report_generator.py    # HTML report generation (not integrated)
```

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
    RESEND_SERVER="smtp.resend.com"
    RESEND_USER="resend"
    RESEND_API_KEY="YOUR_RESEND_API_KEY"
    FROM_EMAIL="your_verified_resend_email@example.com"
    TO_EMAIL="recipient_email@example.com"
    PUSHOVER_USER="YOUR_PUSHOVER_USER_KEY"
    PUSHOVER_TOKEN="YOUR_PUSHOVER_API_TOKEN"
    PUSHOVER_URL="https://api.pushover.net/1/messages.json"
    ```
    
    **Note:** `ALPHA_VANTAGE_API_KEY` is no longer required as the system now uses yfinance for data retrieval.

## 🚀 Quick Start

To run the Sentinel Trade Bot, ensure your environment variables are set up and then execute the `main.py` script:

```bash
python src/main.py
```

The bot will:
1. Fetch S&P 500 symbols and identify trending stocks
2. Analyze each stock using technical indicators (RSI, SMA, MACD)
3. Generate trade signals through the multi-agent team
4. Calculate position sizes and risk parameters
5. Recommend options contracts for approved trades
6. Output trade signals as JSON (email/SMS notifications can be added)

## ⚠️ Deprecated Files

The following files are marked as deprecated and are not used in the current implementation:

- **`alphaVantageTool.py`**: Replaced by `data_fetcher.py` (yfinance-based)
- **`stockAnalysiAgents.py`**: Legacy implementation superseded by `main.py`
- **`backtester.py`**: Not integrated into main workflow
- **`report_generator.py`**: Not currently used (referenced in comments only)

These files are kept in the repository for reference but should not be used in new development. Consider removing them in future versions or integrating them if needed.