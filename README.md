# Stock Analysis System

A multi-agent stock analysis pipeline that combines fundamental analysis, institutional data, analyst forecasts, social sentiment, market trends, and technical analysis into a single weighted signal.

**Architecture:** CODE fetches all data (Python scripts + APIs). AI agents only think and interpret.

## How It Works

```
Ticker input
     |
     v
  [5 Fundamental Agents — run in parallel]
     |
     |-- Agent 1: Fundamentals    (Finnhub + yfinance)  → 4-pillar score
     |-- Agent 2: Institutional   (yfinance)             → smart money trend
     |-- Agent 3: Analyst         (yfinance/TipRanks)    → consensus + targets
     |-- Agent 4: Twitter         (Twitter API)           → sentiment grade
     |-- Agent 5: Trend           (WebSearch + ETFs)      → TAILWIND/HEADWIND
     |
     v
  [Technical Agent — runs last]
     |
     |-- Agent 6: Technical       (yfinance + pandas_ta)  → 5-gate BUY/SELL/HOLD
     |
     v
  Final Score: BULLISH / NEUTRAL / BEARISH (0-100)
  + entry, stop loss, target, confidence %
```

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set API keys
export FINNHUB_API_KEY=your_key_here
export TWITTER_BEARER_TOKEN=your_token_here       # optional
export SLACK_WEBHOOK_URL=your_webhook_here         # optional

# 3. Run fundamental analysis
python scripts/finnhub_stock_analyzer.py NFLX

# 4. Run technical analysis
python scripts/axon_technical.py NFLX

# 5. Run institutional ownership check
python scripts/institutional_analyzer.py NFLX

# 6. Screen multiple tickers
python scripts/screen_technical.py

# 7. Test all 14 data sections
python scripts/test_all_sections.py NFLX
```

## Project Structure

```
agents/                          # AI agent prompts (for Claude Code)
  finnhub-fundamentals-agent.md  # 4-pillar fundamental scoring
  fintel-institutional-agent.md  # Institutional ownership analysis
  tipranks-analyst-agent.md      # Analyst consensus
  twitter-stock-analyzer.md      # Social sentiment
  trend-agent.md                 # Market trend & money flow
  github-analyse-stock.md        # Technical analysis (13 indicators, 5-gate)

scripts/                         # Python data scripts
  finnhub_stock_analyzer.py      # Main fundamental data (10 sections)
  institutional_analyzer.py      # Institutional ownership (yfinance)
  twitter_stock_analyzer.py      # Twitter sentiment search
  axon_technical.py              # Full technical analysis (standalone)
  screen_technical.py            # Multi-ticker 5-gate screening
  test_all_sections.py           # Verify all 14 data sections work
  data_availability_test.py      # Check yfinance data availability

docs/                            # Documentation
  system-architecture.md         # Pipeline and data flow
  technical-agent-capabilities.md # Technical agent deep-dive
```

## Key Features

| Feature | Details |
|---------|---------|
| Fundamental scoring | 4-pillar: Quality 35%, Value 30%, Growth 25%, Sentiment 10% |
| Sector-relative | All metrics compared to sector medians (Damodaran 2026) |
| North Star tracking | Identifies business-critical KPI and detects price divergences |
| Piotroski F-Score | 7/9 tests automated for quality filtering |
| 13 technical indicators | RSI, MACD, BB, Stochastic, Williams%R, ATR, Donchian, SMAs, EMA, Volume |
| 5-gate pipeline | TREND → GRADIENT → CONFLUENCE → REVERSAL → ENSEMBLE |
| ATR stop loss | Entry, stop (1.5x ATR), trailing, targets (2x/3x ATR) |
| Chart patterns | 10 patterns: double top/bottom, flags, triangles, wedges |
| Backtesting | 1-year RSI+MACD strategy with win rate and profit factor |
| Probability calibration | Sigmoid-based BUY/SELL/HOLD confidence scoring |
| Slack alerts | Optional webhook for BUY/SELL signals |

## Data Sources

| Source | Cost | Used For |
|--------|------|----------|
| [Finnhub](https://finnhub.io) | Free tier | Ratios, news, insiders, earnings calendar |
| [yfinance](https://github.com/ranaroussi/yfinance) | Free | Financials, holders, analysts, sector ETFs |
| [Twitter API](https://developer.twitter.com) | Free tier (7 days) | Social sentiment |
| pandas_ta | Free | Technical indicators |

## Requirements

- Python 3.10+
- Finnhub API key (free at finnhub.io)
- Twitter bearer token (optional, for sentiment agent)
