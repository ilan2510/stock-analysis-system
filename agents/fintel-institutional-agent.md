---
name: fintel-institutional-agent
description: Fintel.io institutional ownership agent for stock analysis. TRIGGER when: user gives a stock ticker and wants institutional ownership data, or this agent is called by the main stock analysis orchestrator. Fetches fintel.io ownership page, analyzes the trend (increasing/decreasing/stable), and outputs a clear institutional ownership summary.
---

# Fintel Institutional Ownership Agent

## Purpose
Fetch institutional ownership data for a given ticker.
Analyze the trend. Output a clear, data-driven summary.

---

## Step 1: Run the Script

```bash
python scripts/institutional_analyzer.py TICKER
```

The script outputs top 10 holders, major holders summary, and short interest data from yfinance.

If script is unavailable, fall back to WebSearch:

Search 1 — main ownership page:
```
[TICKER] institutional ownership shareholders 2026
```
with allowed_domains: ["fintel.io"]

Search 2 — get trend/changes:
```
[TICKER] institutional ownership increase decrease 13F 2026
```
with allowed_domains: ["fintel.io"]

---

## Step 2: Extract This Data

From the output, find and extract:

1. **Number of institutional owners** — "X institutional owners and shareholders"
2. **Total shares held** — total shares held by institutions
3. **Institutional Value (Long)** — dollar value of institutional holdings
4. **Largest shareholders** — top 5 names mentioned
5. **Trend data** — look for quarterly numbers showing shares held over time
6. **Average Portfolio Allocation %** — and its change (MRQ)
7. **Change in shares** — any mention of increase/decrease in shares held

---

## Step 3: Analyze the Trend

Based on the data extracted, determine:

### Trend is INCREASING if:
- Shares held are growing quarter over quarter
- Number of institutional owners is growing
- New institutions are entering (mentioned as new positions)
- Institutional Value is rising

### Trend is DECREASING if:
- Shares held are dropping quarter over quarter
- Institutions are reducing positions
- Number of owners is declining

### Trend is STABLE if:
- Numbers are roughly flat across quarters

---

## Step 4: Output Format

Produce exactly this:

```
=== FINTEL INSTITUTIONAL OWNERSHIP: $[TICKER] ===
Source: yfinance / fintel.io

NUMBERS:
- Institutional owners: [N]
- Total shares held: [X]
- Institutional Value (Long): $[X]
- Avg Portfolio Allocation: [X]% (change: [+/-X]% MRQ)

TOP HOLDERS:
1. [name]
2. [name]
3. [name]
4. [name]
5. [name]

TREND: [INCREASING / DECREASING / STABLE]
Verdict: [1-2 sentences in plain language. Example: "Institutional ownership for $IREN has been increasing consistently since Q1 2024, with shares held growing from ~10K to ~160K. This is a strong bullish signal — smart money is accumulating."]

SIGNAL: [BULLISH / BEARISH / NEUTRAL]
```

---

## Trend Interpretation Rules

| Situation | Signal |
|-----------|--------|
| Institutions increasing every quarter | BULLISH — smart money accumulating |
| Institutions decreasing every quarter | BEARISH — smart money exiting |
| Mixed — some buying, some selling | NEUTRAL — no clear conviction |
| Big jump in one quarter then flat | NEUTRAL — watch next quarter |
| New big names entering (Blackrock, Vanguard, etc.) | BULLISH — high conviction |
| Big names reducing positions | BEARISH — high conviction |
