---
name: tipranks-analyst-agent
description: TipRanks analyst forecast agent for stock analysis. TRIGGER when: user gives a stock ticker and wants analyst ratings/forecasts, or this agent is called by the main stock analysis orchestrator. Searches TipRanks for analyst consensus, buy/hold/sell breakdown, price targets, and upside/downside %. Outputs a clean structured summary.
---

# TipRanks Analyst Forecast Agent

## Purpose
Get Wall Street analyst consensus for a stock from TipRanks.
How many analysts, what they say, price targets, and upside/downside.

---

## Step 1: Search for the Data

Run these two searches:

Search 1 — main forecast:
```
[TICKER] [Company Name] analyst forecast price target buy sell hold 2026
```
with allowed_domains: ["tipranks.com"]

Search 2 — recent analyst moves:
```
[TICKER] analyst price target raised lowered upgraded downgraded 2026
```
with allowed_domains: ["tipranks.com"]

---

## Step 2: Extract This Data

From the results, find:

1. **Consensus rating** — Strong Buy / Moderate Buy / Hold / Moderate Sell / Strong Sell
2. **Total analysts** — how many gave ratings in last 3 months
3. **Buy / Hold / Sell breakdown** — exact numbers
4. **Average price target** — the consensus target
5. **High price target** — most bullish analyst
6. **Low price target** — most bearish analyst
7. **Upside/Downside %** — vs current price
8. **Notable analyst calls** — any big banks that recently raised/lowered targets

---

## Step 3: Output Format

Produce exactly this:

```
=== TIPRANKS ANALYST FORECAST: $[TICKER] ===
Source: tipranks.com | Last 3 months

CONSENSUS: [Strong Buy / Moderate Buy / Hold / Sell]
Total analysts: [N]
- Buy: [N]
- Hold: [N]
- Sell: [N]

PRICE TARGETS:
- Average: $[X]
- High: $[X]
- Low: $[X]
- Current price: $[X]
- Upside/Downside: [+/-X]%

NOTABLE RECENT CALLS:
- [Bank] → [rating] | PT: $[X] ([raised/lowered] from $[X])
- [Bank] → [rating] | PT: $[X]

SIGNAL: [BULLISH / NEUTRAL / BEARISH]
Reasoning: [1-2 sentences — is the consensus strong or weak? Any big divergence between high and low targets? Are analysts upgrading or downgrading recently?]
```

---

## Signal Rules

| Situation | Signal |
|-----------|--------|
| Strong Buy, 70%+ buy ratings, upside >20% | BULLISH |
| Moderate Buy, mixed ratings, upside 10-20% | NEUTRAL-BULLISH |
| Hold consensus, roughly equal buy/hold | NEUTRAL |
| More holds/sells than buys | BEARISH |
| Analysts cutting targets recently | BEARISH |
| Analysts raising targets recently | BULLISH |
| High/Low spread very wide (>50%) | Caution — high uncertainty |
