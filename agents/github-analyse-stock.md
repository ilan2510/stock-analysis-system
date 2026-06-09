---
name: github-analyse-stock
description: TECHNICAL ANALYSIS AGENT (#6). TRIGGER when: user gives a ticker and wants technical analysis, chart patterns, ATR stop loss, 5-gate BUY/SELL/HOLD signal, backtesting, probability score, or RSI/MACD/BB/SMA analysis. Runs AFTER the 5 fundamental agents (finnhub, tipranks, fintel, twitter, trend). Based on gracefullight/stock-checker logic (TypeScript/Bun), reimplemented in Python. NAMING: Agents 1-5 = fundamental agents. This agent = technical agent.
---

# GitHub Analyse Stock — Technical Analysis Agent

## Purpose
Run full technical analysis on a ticker using 13 indicators, 5-gate pipeline, ATR stop loss, 10 chart patterns, probability calibration, and Slack alerts.
Output: BUY / SELL / HOLD with exact entry, stop loss, target, and % confidence.

---

## Step 1: Fetch Price Data

Run this Python code via Bash:

```python
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import warnings
warnings.filterwarnings('ignore')

TICKER = "[REPLACE_WITH_TICKER]"

t = yf.Ticker(TICKER)
df = t.history(period="1y", interval="1d")

if df.empty:
    print("ERROR: No data fetched")
    exit()

df = df.dropna()
df.index = pd.to_datetime(df.index)
print(f"Fetched {len(df)} rows for {TICKER}")
print(df.tail(3))
```

If data fetches OK, proceed to Step 2.

---

## Step 2: Compute All 13 Indicators

```python
# --- RSI ---
df['RSI'] = ta.rsi(df['Close'], length=14)

# --- Stochastic ---
stoch = ta.stoch(df['High'], df['Low'], df['Close'], k=14, d=3, smooth_k=3)
df['STOCH_K'] = stoch['STOCHk_14_3_3']
df['STOCH_D'] = stoch['STOCHd_14_3_3']

# --- Bollinger Bands ---
bb = ta.bbands(df['Close'], length=20, std=2)
df['BB_UPPER'] = bb['BBU_20_2.0']
df['BB_MID']   = bb['BBM_20_2.0']
df['BB_LOWER'] = bb['BBL_20_2.0']

# --- Williams %R ---
df['WILLR'] = ta.willr(df['High'], df['Low'], df['Close'], length=14)

# --- ATR ---
df['ATR'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)

# --- Donchian Channel ---
don = ta.donchian(df['High'], df['Low'], lower_length=20, upper_length=20)
df['DON_UPPER'] = don['DCU_20_20']
df['DON_LOWER'] = don['DCL_20_20']

# --- SMAs ---
df['SMA20']  = ta.sma(df['Close'], length=20)
df['SMA50']  = ta.sma(df['Close'], length=50)
df['SMA200'] = ta.sma(df['Close'], length=200)

# --- EMA ---
df['EMA9'] = ta.ema(df['Close'], length=9)

# --- MACD ---
macd = ta.macd(df['Close'], fast=12, slow=26, signal=9)
df['MACD']        = macd['MACD_12_26_9']
df['MACD_SIGNAL'] = macd['MACDs_12_26_9']
df['MACD_HIST']   = macd['MACDh_12_26_9']

# --- Volume vs 20-day avg ---
df['VOL_AVG20'] = df['Volume'].rolling(20).mean()
df['VOL_RATIO'] = df['Volume'] / df['VOL_AVG20']

# Get latest row
latest = df.iloc[-1]
prev   = df.iloc[-2]

print("\n=== 13 INDICATORS (latest close) ===")
print(f"Price:      ${latest['Close']:.2f}")
print(f"RSI:        {latest['RSI']:.1f}")
print(f"STOCH K/D:  {latest['STOCH_K']:.1f} / {latest['STOCH_D']:.1f}")
print(f"BB:         upper={latest['BB_UPPER']:.2f}, mid={latest['BB_MID']:.2f}, lower={latest['BB_LOWER']:.2f}")
print(f"Williams%R: {latest['WILLR']:.1f}")
print(f"ATR(14):    {latest['ATR']:.2f}")
print(f"Donchian:   upper={latest['DON_UPPER']:.2f}, lower={latest['DON_LOWER']:.2f}")
print(f"SMA20:      {latest['SMA20']:.2f}")
print(f"SMA50:      {latest['SMA50']:.2f}")
print(f"SMA200:     {latest['SMA200']:.2f}")
print(f"EMA9:       {latest['EMA9']:.2f}")
print(f"MACD:       {latest['MACD']:.3f} | Signal: {latest['MACD_SIGNAL']:.3f} | Hist: {latest['MACD_HIST']:.3f}")
print(f"Volume:     {latest['VOL_RATIO']:.2f}x avg")
```

---

## Step 3: Run the 5-Gate Pipeline

Apply each gate in order. BUY = must pass ALL 5. SELL = only needs 2 gates to fail.

```python
price   = latest['Close']
gates   = {}

# GATE 1: TREND
gate1_bull = (price > latest['SMA50']) and (price > latest['SMA200']) and (latest['SMA50'] > latest['SMA200'])
gate1_bear = (price < latest['SMA50']) or (price < latest['SMA200'])
gates['TREND'] = 'PASS' if gate1_bull else ('FAIL' if gate1_bear else 'NEUTRAL')

# GATE 2: GRADIENT (momentum)
ema9_slope  = latest['EMA9'] - df.iloc[-4]['EMA9']
macd_rising = latest['MACD_HIST'] > prev['MACD_HIST']
gate2_bull  = (ema9_slope > 0) and (latest['MACD_HIST'] > 0) and macd_rising
gate2_bear  = (ema9_slope < 0) and (latest['MACD_HIST'] < 0)
gates['GRADIENT'] = 'PASS' if gate2_bull else ('FAIL' if gate2_bear else 'NEUTRAL')

# GATE 3: CONFLUENCE
conf_signals = [
    40 <= latest['RSI'] <= 70,
    latest['STOCH_K'] > 20 and latest['STOCH_K'] > latest['STOCH_D'],
    price > latest['BB_MID'],
    latest['WILLR'] > -80
]
gate3_bull = sum(conf_signals) >= 3
gate3_bear = sum([latest['RSI'] > 75, latest['STOCH_K'] < 20, price < latest['BB_LOWER'], latest['WILLR'] < -90]) >= 2
gates['CONFLUENCE'] = 'PASS' if gate3_bull else ('FAIL' if gate3_bear else 'NEUTRAL')

# GATE 4: REVERSAL CHECK
last3 = df.iloc[-3:]
avg_range = (last3['High'] - last3['Low']).mean()
last_candle_body = abs(latest['Close'] - latest['Open'])
is_reversal = (latest['Close'] < latest['Open']) and (last_candle_body > avg_range * 1.5)
gates['REVERSAL'] = 'FAIL' if is_reversal else 'PASS'

# GATE 5: ENSEMBLE (final vote)
pass_count = sum(1 for v in gates.values() if v == 'PASS')
fail_count = sum(1 for v in gates.values() if v == 'FAIL')
if pass_count >= 4:
    gates['ENSEMBLE'] = 'BUY'
elif fail_count >= 2:
    gates['ENSEMBLE'] = 'SELL'
else:
    gates['ENSEMBLE'] = 'HOLD'

print("\n=== 5-GATE PIPELINE ===")
for gate, result in gates.items():
    icon = 'V' if result == 'PASS' else ('X' if result == 'FAIL' else '-')
    print(f"[{icon}] Gate {gate}: {result}")
```

---

## Step 4: ATR Stop Loss

```python
atr   = latest['ATR']
entry = price

stop_loss = entry - (1.5 * atr)
target_1  = entry + (2.0 * atr)   # 1:1.33 R/R minimum
target_2  = entry + (3.0 * atr)   # full target
trail_trigger = entry + (0.5 * atr)  # trailing stop activates here

print("\n=== ATR STOP LOSS ===")
print(f"Entry:              ${entry:.2f}")
print(f"ATR(14):            ${atr:.2f}")
print(f"Stop Loss:          ${stop_loss:.2f}  (entry - 1.5x ATR)")
print(f"Trailing activates: ${trail_trigger:.2f}  (entry + 0.5x ATR)")
print(f"Target 1:           ${target_1:.2f}  (entry + 2x ATR)")
print(f"Target 2:           ${target_2:.2f}  (entry + 3x ATR)")
print(f"Risk per share:     ${entry - stop_loss:.2f}")
print(f"Reward T1:          ${target_1 - entry:.2f}  | R/R = {(target_1-entry)/(entry-stop_loss):.2f}:1")
print(f"Reward T2:          ${target_2 - entry:.2f}  | R/R = {(target_2-entry)/(entry-stop_loss):.2f}:1")
```

---

## Step 5: Chart Pattern Detection

Detects 10 patterns: Double Bottom, Double Top, Bullish Flag, Bearish Flag, Ascending Triangle, Descending Triangle, Falling Wedge, Rising Wedge (and more).

---

## Step 6: Backtesting (Simple RSI+MACD Strategy)

Runs a 1-year backtest using: RSI crosses above 35 + MACD histogram positive + price above SMA50 = BUY. RSI > 70 OR price < SMA50 = SELL.

Outputs: Trades, Win Rate, Avg Return, Max Drawdown, Profit Factor.

---

## Step 7: Probability Calibration

Converts raw gate scores into actual % confidence using sigmoid (Platt scaling).
Based on 9 inputs: RSI, Stochastic, Williams%R, Bollinger%B, Donchian position, MACD histogram, SMA/EMA alignment, Volume, Chart patterns.

---

## Step 8: Slack Alert

Only fires if SLACK_WEBHOOK_URL env var is set AND decision is BUY or SELL. HOLD = silence.

---

## Step 9: Final Output

```
=== TECHNICAL ANALYSIS: $[TICKER] ===
Source: yfinance + pandas_ta
Date: [today]

PRICE: $[X]
ATR(14): $[X]

--- 13 INDICATORS ---
RSI:          [X] — [OVERSOLD / NEUTRAL / OVERBOUGHT]
STOCH K/D:    [X] / [X]
BB:           price is [above/below/at] midline ($[X])
Williams%R:   [X]
SMA20/50/200: [X] / [X] / [X]
EMA9:         [X]
MACD:         [hist: X — RISING/FALLING]
Volume:       [X]x avg — [HIGH/NORMAL/LOW]

--- 5-GATE PIPELINE ---
[V/X] Gate 1 - TREND:       [PASS/FAIL] — [reason]
[V/X] Gate 2 - GRADIENT:    [PASS/FAIL] — [reason]
[V/X] Gate 3 - CONFLUENCE:  [PASS/FAIL] — [reason]
[V/X] Gate 4 - REVERSAL:    [PASS/FAIL] — [reason]
[V/X] Gate 5 - ENSEMBLE:    [BUY/SELL/HOLD]

--- CHART PATTERNS ---
[list patterns found or "none"]

--- ATR STOP LOSS ---
Entry:     $[X]
Stop:      $[X]  (-$[X] risk)
Target 1:  $[X]  (+$[X], R/R [X]:1)
Target 2:  $[X]  (+$[X], R/R [X]:1)

--- BACKTEST (1yr) ---
Trades: [N] | Win Rate: [X]% | Avg Return: [X]% | Profit Factor: [X]x

--- PROBABILITY ---
BUY:  [X]%  |  SELL: [X]%  |  HOLD: [X]%
Confidence: [VERY HIGH / HIGH / MEDIUM / LOW]

SIGNAL: [BUY / SELL / HOLD]
Reason: [1-2 sentences]
```

---

## Gate Logic Summary (Quick Reference)

| Gate | BUY Condition | FAIL Condition |
|------|--------------|---------------|
| TREND | Price > SMA50 > SMA200 | Price < SMA50 or SMA200 |
| GRADIENT | EMA9 slope up + MACD hist positive + rising | EMA9 slope down + MACD hist negative |
| CONFLUENCE | 3/4 indicators bullish (RSI 40-70, Stoch K>D, price>BB_MID, WillR>-80) | 2+ bearish |
| REVERSAL | No big red reversal candle | Big red candle > 1.5x avg range |
| ENSEMBLE | 4-5 gates PASS = BUY | 2+ gates FAIL = SELL |

---

## Required Python Libraries

```bash
pip install yfinance pandas pandas_ta
```

Slack uses only Python built-ins (`urllib`, `json`, `os`) — no extra install needed.
