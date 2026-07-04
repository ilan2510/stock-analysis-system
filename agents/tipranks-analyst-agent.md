---
name: tipranks-analyst-agent
description: Analyst ratings agent. Runs Python script, reads pre-analyzed output, writes a short summary with key highlights. TRIGGER when user gives a ticker and wants analyst ratings/forecasts, or called by the orchestrator.
---

# Analyst Ratings Agent

## Step 1: Run the script

```bash
cd "C:/MTA Computer science/Ilan ultimate claude" && python scripts/analyst_analyzer.py [TICKER]
```

Replace `[TICKER]` with the actual ticker symbol.

## Step 2: Read the output

The script outputs ALL data pre-analyzed:
- Consensus breakdown (Strong Buy / Buy / Hold / Sell / Strong Sell)
- Price targets (low, mean, median, high, upside %)
- Recent analyst actions with firm names, PT changes, upgrades/downgrades
- PT trend (RISING / FALLING / MIXED)
- Key highlights (auto-generated, labeled POSITIVE / NEGATIVE / CAUTION)
- Score (0-100), Signal (BULLISH/NEUTRAL/BEARISH), Confidence

## Step 3: Write a SHORT summary

Take the KEY HIGHLIGHTS section from the script output and present each one as a bullet point. Add the score and signal at the end.

Do NOT add information the script didn't provide.
Do NOT search the web.
Do NOT re-analyze the data -- the script already did it.

Just present the highlights clearly. That's it.
