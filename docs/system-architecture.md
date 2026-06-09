# System Architecture

## Core Principle: CODE fetches, AI thinks

All data is pulled by Python scripts (APIs, calculations). The AI agents only think, interpret, and decide.

```
PYTHON CODE (the hands)              AI AGENT (the brain)
─────────────────────                 ──────────────────
Finnhub API → ratios, news           Reads the numbers
yfinance → financials, holders       Compares to benchmarks
yfinance → analyst ratings, PT       Decides: good or bad?
yfinance → sector ETFs               Identifies patterns
pandas_ta → 13 indicators            Writes final analysis
All the math. Zero thinking.          All the thinking. Zero fetch.
```

## Agent Pipeline

```
User gives ticker
        |
        v
[Agent 1] finnhub-fundamentals  → Quality/Value/Growth score (35/30/25/10%)
[Agent 2] fintel-institutional   → Smart money buying or selling?
[Agent 3] tipranks-analyst       → Analyst consensus + price targets
[Agent 4] twitter-sentiment      → Social sentiment + data quality
[Agent 5] trend-agent            → TAILWIND / HEADWIND / NEUTRAL
        |
        v  (all 5 run in parallel)
[Agent 6] github-analyse-stock   → Technical confirmation (runs LAST)
        |
        v
FINAL: BULLISH (70+) | NEUTRAL (45-69) | BEARISH (<45)
       + exact entry, stop loss, target from ATR
```

## Data Sources

| Source | What it provides | Cost |
|--------|-----------------|------|
| Finnhub API | Ratios, news, insiders, earnings calendar | Free tier |
| yfinance | Financials, institutional holders, analyst data, sector ETFs | Free |
| Twitter API | Social sentiment (7 days) | Free tier |
| WebSearch | Market trends, North Star metrics, narrative | Free |

## 14 Verified Data Sections

| # | Section | Source |
|---|---------|--------|
| 1 | Valuation | Finnhub |
| 2 | Profitability | Finnhub |
| 3 | Cash Flow | yfinance |
| 4 | Balance Sheet | yfinance |
| 5 | Growth | Finnhub |
| 6 | Piotroski F-Score | Calculated |
| 7 | Earnings | yfinance |
| 8 | News | Finnhub |
| 9 | Insiders | Finnhub |
| 10 | Next Catalyst | Finnhub |
| A2 | Institutional Ownership | yfinance |
| A3 | Analyst Ratings | yfinance |
| A5 | Sector ETF Performance | yfinance |
| B | Bonus (.info) | yfinance |
