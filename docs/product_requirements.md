# Product Requirements Document (PRD) V5: AI Swing Trading System

## Executive Summary
This document is the rigorous engineering blueprint for an institutional-grade, long-only AI Swing Trading System. It mathematically codifies the expert human intuition from the `trading_system_specs.md` (the absolute Source of Truth) into boolean constraints, agent Input/Output contracts, and precise execution triggers. 

**Core Architectural Principle: CODE fetches, AI thinks.**
All data (APIs, web scraping, mathematical calculations) MUST be pulled by Python scripts. The AI agents are strictly reasoning engines; they only interpret the provided context and make decisions. They do not execute fetch commands themselves.

---

## 1. System Rollout & Architecture
*   **Phase 1 (Copilot):** Autonomous advisor mode. Evaluates entries at 21:30 ILS. Evaluates exits at 23:00 ILS. Paper trading only.
*   **Phase 2 (Autonomous):** Triggers when Phase 1 achieves: ≥50 completed trades, Win Rate ≥55%, and Average R:R ≥1.2. Executes directly via Brokerage API.
*   **Timeframes:** 
    *   **Weekly Chart:** Used strictly for identifying historical Support/Resistance (S/R) zones.
    *   **Daily Chart:** Used strictly for Entry/Exit execution.
*   **The "Two-Touch" Rule:** The mathematical engine SHALL NOT validate any S/R line unless it detects ≥2 distinct price touches (wicks or bodies) in history.
*   **Manipulation Tolerance (Liquidity Sweeps):** `IF (price drops below valid S/R_line) AND (price recovers and closes above S/R_line within 3 daily candles) THEN pattern remains valid`.

## 2. Pipeline 1: The Screener (Data Ingestion)
The Python Screener filters the universe of stocks. A ticker MUST PASS ALL 7 filters to proceed to the Agent Pipeline.
1.  `market_cap >= 300,000,000`
2.  `price >= 10.00`
3.  `asset_class == 'US_EQUITY' AND is_etf == FALSE` (Exception: IGV allowed).
4.  `avg_daily_volume_20d >= 250,000`
5.  `beta > 1.0`
6.  `price <= (52_week_high * 0.85)` (Must be at least 15% below the 52-week high).
7.  `(analyst_consensus >= 'HOLD') AND (price > SMA_200)`

*Note: A permanent, hardcoded watchlist (TSLA, SHOP, NFLX, IREN, OKLO, TEM, GOOGL, AFRM, HOOD) bypasses this screener entirely and is evaluated daily.*

## 3. Boolean Hard Constraints (Disqualification)
Before Agent 6 evaluates technicals, the system SHALL REJECT any ticker triggering these conditions:
1.  **Earnings Blackout:** `IF days_to_next_earnings <= 3 THEN Reject`.
2.  **Open Position Earnings Exit:** `IF days_to_next_earnings == 1 AND has_open_position THEN Force_Close_Position`. (We do not hold through earnings).
3.  **Market Regime Filter:** `IF SPY_SMA_44_slope < 0 THEN (IF Ticker_SMA_44_slope <= 0 THEN Reject) AND (Agent_6_Activation_Threshold = 80)`. (Slope = `SMA44_today - SMA44_10_days_ago`).
4.  **Extended Breakout:** `IF current_swing_leg_performance > 30% AND has_pullback == FALSE THEN Reject`.
5.  **Portfolio Exposure Cap:** `IF open_positions >= 5 THEN Reject_New_Entries`.

## 4. The Agent Pipeline (Input/Output Contracts)

### Error Handling / Failover
If any agent fails to fetch data or time out, it defaults to a neutral stance to prevent pipeline collapse: Agents 1-4 return `50`; Agent 5 returns `NEUTRAL (1.0x)`.

### Agents 1-4: The Fundamental Scoring Engine
These agents run in parallel. Their outputs are weighted to produce a final Base Score (0-100).
*   **Agent 1 (Fundamentals - 35% Weight):** 
    *   *Inputs:* Valuation, Profitability, Cash Flow, Balance Sheet, Growth, Piotroski F-Score, Earnings, News, Insiders, Next Catalyst.
    *   *Output:* Score (0-100).
*   **Agent 2 (Institutional - 30% Weight):** 
    *   *Inputs:* Institutional Ownership, Insider Transactions.
    *   *Output:* Score (0-100).
*   **Agent 3 (Analyst Consensus - 25% Weight):** 
    *   *Inputs:* Analyst Ratings, Price Targets vs Current Price.
    *   *Output:* Score (0-100).
*   **Agent 4 (Narrative/Sentiment - 10% Weight):** 
    *   *Pipeline:* Queries the Twitter API daily (prior to 21:30) for a hardcoded whitelist of top financial accounts PLUS global cashtag searches. Finnhub News is appended. 
    *   *Output:* LLM-evaluated Sentiment Score (0-100).

### The "Disrupted Model" Kill Switch
Agents 1 and 4 parse news/analyst text for existential threats. 
*   **LLM Prompt:** *"Based on the following news articles from the last 30 days about {TICKER}, is the company's core business model facing an existential threat from a competing technology or market shift? Answer TRUE or FALSE with a brief justification."*
*   If `TRUE`, the system overrides the score and REJECTS the ticker.

### Agent 5 (Macro Trend)
*   *Input:* yfinance Sector ETFs.
*   *Output Multipliers:* `TAILWIND` (1.1x), `NEUTRAL` (1.0x), or `HEADWIND` (0.8x) applied to the Base Score.

### Agent 6 (Technical Execution)
**Activation:** Triggers ONLY IF the final Base Score (after Agent 5 multiplier) is `>= 70`.
*   *Task:* Map the price action to the Chart Pattern Taxonomy (Section 5) and trigger Vision AI.
*   *RSI Preference:* `RSI(14) < 50` acts as a bonus confidence multiplier internally, not a hard gate.

## 5. Chart Pattern Taxonomy & Entry Triggers (Agent 6)
**Execution Philosophy:** All intraday signals before 21:30 ILS MUST be ignored to avoid institutional manipulation.

### Pattern Group 1: The "Detached Breakout"
*   **Execution Trigger (at 21:30):** The Daily candle (body AND wicks) MUST close completely above the resistance line.
*   **Volume Requirement:** `breakout_volume >= (avg_volume_20d * 0.8)`.
*   **Specific Patterns:**
    *   *Ascending Triangle / Cup & Handle:* Breakout above horizontal resistance. **Requirement:** SMA 44 and SMA 200 MUST be below the current price to act as a safety net.
    *   *Descending Triangle:* Breakout above the descending trendline. **Requirement:** SMA 44 and SMA 200 MUST be below current price.
    *   *Down Channel:* Breakout above the upper channel line.

### Pattern Group 2: The "V-Shape Retest"
*   **Execution Trigger (at 21:30):** Price hits S/R line and forms a sharp 'V' reversal candle (long lower wick).
*   **Specific Patterns:**
    *   *Up Channel:* Retest on the lower ascending channel line.
    *   *Fibonacci Pullback:* IF the prior swing leg was `>= 30%` (a massive rally), the 'V' reversal MUST occur between the `0.5` and `0.618` retracement levels. **Grading:** A 0.5 retest is ideal and scores higher; 0.618 is the absolute lower boundary.
*   **Confluence Bonus:** If the S/R line, the SMA 44, and the Fib 0.618 level converge at the exact same price, Agent 6 flags this as a "High-Priority Confluence Setup."

### Vision AI Validation (Final Gate)
*   **Model:** Gemini Pro Vision (or equivalent).
*   **Input:** A Python-generated (Matplotlib/Plotly) clean chart image + JSON context (pattern type, current OHLCV).
*   **Output Contract:** Must return strictly `VALID_PATTERN` or `INVALID_PATTERN` with a brief justification.
*   **S/R Naturalness Check:** Vision AI must confirm that programmatic S/R lines "look natural to the human eye" and are not forced through noise.

## 6. Mathematical Risk & Trade Management

### Position Sizing & SL (Hard Orders)
*   **Size:** 10% portfolio max per trade. `IF (TP_distance / SL_distance) < 1.0 THEN Reject`.
*   **Stop Loss (Detached Breakouts):** `SL = Low_of_candle_immediately_preceding_breakout_candle`.
*   **Stop Loss (V-Shape Retest):** `SL = Entry - (1.5 * ATR_14)` calculated from the absolute low of the 'V'.
*   **Execution:** SL is NEVER mental. It must be submitted to the brokerage atomically (OCO order) alongside the entry order.

### Dynamic Take Profit (TP) State Machine
*   **Target Selection Priority:** `TP = MIN(Volume_Gap, SMA_200, Historical_SR, Avg_3_Legs)`. (The system always selects the *nearest* logical resistance).
*   **Mid-Trade SMA 44 Resistance Gate:** When price approaches a falling SMA 44 from below, apply the same 50% candle-body test used at TP. If the candle closes >50% above it, SMA 44 resistance is invalidated and the trade continues. If <50%, SMA 44 becomes the de facto exit point.
*   **Evaluation (23:00 ILS Scheduled Process):** When price hits TP, the system waits for the Daily Close.
    *   `IF candle_body_above_TP < 50%`: Close 100% of position.
    *   `IF candle_body_above_TP >= 50%`: Close 50% of position, hold 50% as "Runner", and trail the SL to the exact partial-exit price point.

## 7. System Infrastructure (State & UX)
*   **State & Memory Database:** SQLite/PostgreSQL tracking: Ticker, Timestamp, Current State (e.g., `WAITING_FOR_SMA_44_RETEST`), and Base Score history. Ensures continuous context-aware analysis across days.
*   **UX/UI Components:**
    *   *Alerts:* Discord/Telegram Bot pushing actionable setups at 21:30, and TP/SL alerts at 23:00.
    *   *Dashboard:* A React/Next.js frontend displaying the permanent watchlist, trade journal, portfolio exposure, and deep-dive analysis views.
