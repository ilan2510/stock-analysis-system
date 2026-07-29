# Stock Analysis Orchestrator — Requirements

Scope: the 4 fundamental agents + `orchestrator.py` only. Not the technical agent, not the screening script — those are separate.

---

## 1. What it does

Give it a ticker, it gives back a single BULLISH / NEUTRAL / BEARISH call with a 0-100 score, built from 4 independent angles (fundamentals, institutional ownership, analyst sentiment, sector/market trend), adjusted for the overall market mood.

Code does all the fetching, scoring, and math — no LLM in the loop for scoring. Same ticker, same day = same score, every time.

---

## 2. How it's built

```
                    orchestrator.py
                          │
        ┌─────────────────┼─────────────────┬─────────────────┐
        ▼                 ▼                 ▼                 ▼
   Fundamentals      Institutional        Analyst            Trend
        │                 │                 │                 │
        └─────────────────┴────────┬────────┴─────────────────┘
                                    ▼
                    weighted score + macro adjustment + story
```

Each agent is its own Python script, run in parallel. The orchestrator doesn't touch agent internals — it just reads what each script prints. Keeps them independent and easy to test on their own.

---

## 3. The 4 agents

| # | Agent | Script | Data source | What it scores |
|---|-------|--------|--------------|-----------------|
| 1 | Fundamentals | `finnhub_stock_analyzer.py` | Finnhub API + yfinance | Quality, Value, Growth, Sentiment. Plus Piotroski score, red flags, moat, bull/base/bear scenarios |
| 2 | Institutional | `institutional_analyzer.py` | yfinance holders data | Smart-money buying vs. selling, insider ownership, short-squeeze signal |
| 3 | Analyst | `analyst_analyzer.py` | yfinance analyst data | Consensus rating, price-target trend, EPS revisions |
| 5 | Trend | `trend_analyzer.py` | yfinance sector ETFs + SPY + VIX | Sector rank, rotation, trend phase, relative strength |

(Numbered 1/2/3/5 to match the file numbering across the wider project — agent #4, Twitter, was removed 2026-07-26 and was never part of the orchestrator anyway.)

**Every agent must print this as its last line:**
```
@@RESULT@@{"score": 74, "signal": "BULLISH", "confidence": "HIGH"}
```
If it can't find that, it's marked FAILED and dropped from the score — doesn't crash the run.

---

## 4. What the orchestrator does

1. **Checks the market mood first** — VIX + SPY trend, before even looking at the stock. Bad tape = score gets knocked down (-8 to -3); good tape = small boost (+5).
2. **Runs all 4 agents in parallel**, 30s timeout each. One agent failing doesn't kill the run.
3. **Weights each agent differently by sector** — a bank gets judged mostly on Fundamentals, a biotech leans more on Analyst since it may not have real earnings yet.
4. **Combines into one 0-100 score** → BULLISH (65+) / NEUTRAL (40-64) / BEARISH (under 40).
5. **Flags when agents disagree** — if the spread between highest and lowest agent score is over 30 points, it says so.
6. **Flags earnings coming up** — warns if earnings are within 7 days (high risk) or 14 days (reduce size).
7. **Remembers past runs** — keeps score history per ticker so you can see if a stock is improving or fading.
8. **Writes a short story** — 4 sentences summarizing the call, built from templates, not an LLM.

---

## 5. Some ground rules

- Full run takes ~4-5 seconds.
- If one agent breaks, the other 3 still work — never a hard crash.
- No randomness anywhere — reproducible results.
- All the recent upgrades used data we already fetch — zero extra API calls/cost.

---

## 6. What we deliberately left out

- No technical analysis (charts/indicators) in here — that's a separate agent, on purpose.
- No options/IV data.
- No auto trade plan (entry/stop/target) — can't do it properly without technicals, so not building a half version.

---

## 7. Questions for you (Segev)

1. The sector weights (step 3 above) are just judgment calls, never backtested — worth checking if they actually hold up?
2. Same for the "30-point disagreement" flag — arbitrary number, never validated.
3. Score history file only lives on my machine right now — should it be somewhere we both see?
4. Zero tests right now — worth adding some?
5. Finnhub API key is hardcoded in the script — want to move it to an env var since this is shared now?

---

## 8. How to run it

```bash
python scripts/orchestrator.py TICKER
python scripts/orchestrator.py TICKER --verbose   # shows each agent's full output
```

Same code also lives in the GitHub repo (`stock-analysis-system`) at `src/orchestrator.py` + `src/analyzers/*.py`.
