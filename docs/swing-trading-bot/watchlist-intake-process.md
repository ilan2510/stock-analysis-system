# Watchlist Intake Process — Finviz to Watchlist

## Purpose

How a ticker goes from a Finviz screen to actually earning a spot on the watchlist. This is Ilan's manual chart-read step — the human filter before a ticker gets tracked. **This is not entry/breakout timing.** It only answers "is this worth watching," nothing about when to actually trade it. Entry rules are a separate doc, later.

This stays a manual human step for now (Ilan + Segev) — not something the bot automates yet, per `requirements.md`.

---

## Step 1: Finviz Screen

Search parameters:

- Price ≥ $7
- Above SMA200
- USA-listed only
- Market cap ≥ $300M
- Avg volume ≥ 200K
- Beta ≥ 1

(Plus the core watchlist names Ilan tracks regardless of screen — see `requirements.md`.)

## Step 2: Open the Chart

- Click "Charts" on Finviz. **Daily timeframe only** at this stage.
- Look at price action plus whatever trend lines / support-resistance lines Finviz has already auto-drawn on the chart. Finviz's chart tool detects and overlays these itself (sometimes even labels a named pattern, like "Double Top"). Nothing gets manually drawn at this step — Ilan is reading what Finviz already flagged.

## Step 3: What Makes It a "Yes"

1. **Clear directional price movement** — not chopping sideways for months (e.g. stuck between $50-55 for months = reject).
2. **Real candle bodies** — not mostly long wicks with tiny bodies. Wick-dominant candles read as indecision, not structure.
3. **Finviz has drawn a trend line and/or S/R line, and price is actually respecting it** — candles reacting/bouncing off the line, not just cutting straight through it.
4. A valid S/R line generally needs **at least 2 touches** — not a rigid rule, use judgment (dynamic).

## Step 4: The Weekly Check

If there's clear directional movement (not a straight crash, see Step 5) but Finviz hasn't drawn any clean trend line or S/R on the daily chart, don't reject immediately — pull up the **weekly** chart on TradingView. Some structure only shows up zoomed out.

## Step 5: What Makes It a "No"

- Choppy, range-bound price with no real trend
- Mostly wicks, no real candle bodies
- No structure on daily, and nothing clean on weekly either
- A big straight-down move (e.g. an 80% crash) is not "clear movement" in the good sense — that's a broken chart, not structure.

## Step 6: Patterns Ilan Watches For

- Clear support/resistance levels (doesn't need a named pattern shape — a clean, respected S/R line on its own is enough)
- Cup and handle
- Ascending triangle
- Descending triangle
- Down channel
- Up channel

Common thread across all of them: candles need to actually **respect** the lines forming the pattern, not just loosely resemble the shape.

## Step 7: Volume

Not a factor at this stage beyond the initial Finviz filter (avg volume ≥ 200K). Volume becomes relevant later, at entry — not part of the watchlist decision.

## Hit Rate

Roughly **8 out of every 50** charts opened from a Finviz screen make it onto the watchlist. Dynamic — varies with market conditions.

## Out of Scope

- Entry timing / breakout confirmation criteria — separate doc, pending the dedicated rules session.
- Automating this step — stays manual (Ilan + Segev) for now.
