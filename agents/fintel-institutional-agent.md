---
name: fintel-institutional-agent
description: Institutional ownership agent. Runs Python script, reads pre-analyzed output, writes a short summary with key highlights. TRIGGER when user gives a ticker and wants institutional ownership data, or called by the orchestrator.
---

# Institutional Ownership Agent

## Step 1: Run the script

```bash
cd "C:/MTA Computer science/Ilan ultimate claude" && python scripts/institutional_analyzer.py [TICKER]
```

Replace `[TICKER]` with the actual ticker symbol.

## Step 2: Read the output

The script outputs ALL data pre-analyzed:
- Top 10 holders with direction (ADDING/REDUCING/NEW POSITION)
- Smart money tags (BIG 3 / NOTABLE)
- Summary stats (institutional %, insider %, float %)
- Short interest with month-over-month change
- Trend analysis (STRONGLY INCREASING / INCREASING / MIXED / DECREASING)
- Key highlights (auto-generated, labeled POSITIVE / NEGATIVE / CAUTION)
- Score (0-100), Signal (BULLISH/NEUTRAL/BEARISH), Confidence

## Step 3: Write a SHORT summary

Take the KEY HIGHLIGHTS section from the script output and present each one as a bullet point. Add the score and signal at the end.

Do NOT add information the script didn't provide.
Do NOT search the web.
Do NOT re-analyze the data -- the script already did it.

Just present the highlights clearly. That's it.
