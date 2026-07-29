# AI Swing Trading Bot — Requirements

## Vision

Give the bot a stock ticker. It reads the chart the way Ilan reads a chart — support/resistance, trend lines, patterns like cup-and-handle and triangles — and only flags a trade when there's a confirmed breakout. Fundamentals (already built, see below) don't decide IF you trade, they decide HOW MUCH you trade. Bot calculates its own stop-loss and take-profit. This is swing trading, not day trading.

Phase 1: bot alerts you both, you execute manually.
Phase 2 (later): bot executes the trade itself.

---

## What already exists — don't rebuild this

The 4 fundamental agents + `orchestrator.py` are done and working. Full detail: [`fundamentals-system-requirements.md`](./fundamentals-system-requirements.md).

**Its job in this bot:** not a gate. A technical breakout is what triggers a trade idea at all. The fundamental score (0-100) then adjusts position size — strong fundamentals, bigger size; weak fundamentals, smaller size or skip.

---

## System flow

```
   Watchlist (manual list)
          │
          ▼
   Technical Signal Engine   ← NEW, not built yet
   (support/resistance, trend lines,
    patterns, breakout confirmation)
          │
     breakout confirmed?
          │ yes
          ▼
   pull fundamental score  ← reuse existing orchestrator
   (sets position size, not a go/no-go)
          │
          ▼
   calculate stop-loss + take-profit  ← rules pending (Ilan teaches)
          │
          ▼
   Slack alert: ticker, pattern, entry, stop, target, size
          │
          ▼
   (Phase 2, later) auto-execute via broker
```

---

## Watchlist

- Size: dynamic, no fixed cap (currently 10-40+ tickers).
- Sourcing — two parts:
  1. **Core known names** Ilan tracks regardless of screen (e.g. TSLA, AMZN, AFRM, HOOD, OKLO).
  2. **Finviz screen, refreshed every 2 weeks** — filters: price ≥ $7, above SMA200, USA-listed only, market cap ≥ $300M, avg volume ≥ 300K, beta ≥ 1 (plus more Ilan may add) — then manual chart review for clean S/R + trend-line behavior before adding.
- Removal: manual — a ticker comes off when it breaks its technical pattern and has nothing interesting going on.
- Update owner: both Ilan and Segev, manual entry.
- **Scope: watchlist curation is a permanent human step, not something the bot automates.** Bot only consumes the list — screening/adding/removing tickers is not in scope for the bot, now or later.

## Data handling

- Fundamental score missing/unavailable at alert time → alert still fires (fundamentals are 20% sizing input, never a gate). Alert should note "fundamental score unavailable — size conservatively."
- No price/candle data returned at all → nothing to alert on, no rule needed (no signal exists).
- Basic sanity check on price data before trusting a breakout signal: reject/flag a candle if it's a wild outlier vs. recent candles (e.g. price gaps way beyond normal range in one bar) — simple check, not a full data-quality pipeline.

## Validation method (Phase 1)

- No formal backtest/win-rate requirement for v1. Validation is visual: Segev builds pattern detection, overlays the detected S/R zones, trend lines, and patterns directly on a live chart.
- Ilan and Segev review together — if what the AI flags matches what Ilan would call by eye, it's trusted. If it doesn't match, rules get adjusted.
- Ownership: Segev leads this build; Ilan is the validator (his eye is the ground truth, since the whole system is modeling how he reads a chart).
- A real backtest/accuracy metric can be added later once the visual matching is solid — not a Phase 1 requirement.

## Requirements — Phase 1 (alert-only)

1. Bot scans a manually maintained watchlist (see Watchlist section above). No full-market scanning yet.
2. Reads daily candles by default. Must also be able to check weekly candles — some setups are only clean on weekly, not daily.
3. Detects: support/resistance levels, trend lines, and chart patterns (cup-and-handle, triangles, and whatever else Ilan defines). **Exact detection rules are not written yet** — needs a dedicated session where Ilan teaches his rules before this gets coded.
4. Only flags a trade on a **confirmed breakout** — exact confirmation criteria also pending that same teaching session.
5. Pulls the fundamental score from the existing orchestrator and uses it to size the position — never as a reason to block a trade on its own.
6. Calculates stop-loss and take-profit automatically for every flagged trade. Method pending — Ilan will teach his actual rules (likely structure-based: stop below the pattern, not a generic % or pure ATR).
7. Sends a Slack alert with: ticker, pattern found, entry, stop, target, suggested size. Does **not** place any real trade in Phase 1.
8. Swing trading only — no intraday/day-trading logic.

## Requirements — Phase 2 (later, not building yet)

9. Auto-execute trades via a broker API, once the alert-only version is proven.
10. Possibly expand from a fixed watchlist to scanning the full market.

---

## Things we still need to decide, together

1. **Team split** — who builds what between the three of us — not decided yet.
2. **Trading rules** — support/resistance, trend lines, pattern criteria, breakout confirmation, stop-loss placement — none of this is written down yet. Needs a dedicated session with Ilan before the Technical Signal Engine gets built.
3. **Position-sizing formula** — how exactly does a 0-100 fundamental score map to position size? Not defined.
4. **Broker choice** for the eventual auto-execute phase.
5. **Scan schedule** — once a day after market close, or something else?
