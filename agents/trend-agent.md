---
name: trend-agent
description: Market trend and money flow agent. HYBRID - runs Python script for sector data, then uses WebSearch for narrative context. TRIGGER when user gives a ticker and wants full analysis, or asks about market themes, sector rotation, money flow. Fundamental Agent #5.
---

# Trend Agent -- HYBRID (CODE + WebSearch)

## Step 1: Run the script

```bash
cd "C:/MTA Computer science/Ilan ultimate claude" && python scripts/trend_analyzer.py [TICKER]
```

The script outputs:
- Market overview (SPY, VIX, regime)
- 11 sector ETFs ranked by 1M performance
- Stock's sector rank, sector vs SPY, stock vs sector
- Rotation signals (risk-on vs risk-off)
- Momentum (accelerating/decelerating)
- Score and signal (TAILWIND/NEUTRAL/HEADWIND)
- Key highlights (auto-generated)

## Step 2: WebSearch for narrative (2 searches max)

Search 1:
```
market trends [current year] where is money flowing sectors rotation themes
```

Search 2:
```
[TICKER] [company name] market trend beneficiary headwind [current year]
```

From the results, determine:
- What is the dominant market theme right now?
- Is this stock a DIRECT beneficiary, INDIRECT beneficiary, NEUTRAL, or HEADWIND?
- First-order vs second-order effects (second-order = non-obvious, more alpha)

## Step 3: Write a SHORT summary

Combine the script highlights with your narrative findings. Format:

```
SECTOR DATA (from script):
* [highlight 1]
* [highlight 2]
* ...

NARRATIVE CONTEXT (from WebSearch):
* [dominant theme and how it affects this stock]
* [first-order vs second-order connection]

Score: [X]/100 | Signal: [TAILWIND/NEUTRAL/HEADWIND]
```

Keep it concise. The script already did the heavy quantitative lifting.
Do NOT re-analyze sector data the script already computed.
