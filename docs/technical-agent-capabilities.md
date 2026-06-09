# Technical Agent Capabilities

Agent #6 in the stock analysis system.
Runs AFTER the 5 fundamental agents.
Source logic: gracefullight/stock-checker (TypeScript/Bun), reimplemented in Python.

## 13 Technical Indicators

| # | Indicator | What it tells you |
|---|-----------|------------------|
| 1 | RSI(14) | Overbought >70, Oversold <30 |
| 2 | Stochastic K/D (14,3,3) | Momentum crossovers |
| 3 | Bollinger Bands (20,2) | Price relative to volatility envelope |
| 4 | Williams %R(14) | Overbought/oversold oscillator |
| 5 | ATR(14) | Average True Range — volatility measure |
| 6 | Donchian Channel(20) | 20-day high/low channel |
| 7 | SMA20 | Short-term trend |
| 8 | SMA50 | Medium-term trend |
| 9 | SMA200 | Long-term trend |
| 10 | EMA9 | Fast momentum direction |
| 11 | MACD(12,26,9) | Trend + momentum |
| 12 | Volume vs 20-day avg | Is today's volume unusual? |
| 13 | Volume trend | Is volume confirming the move? |

## 5-Gate Pipeline

| Gate | BUY (PASS) | FAIL |
|------|-----------|------|
| TREND | Price > SMA50 > SMA200 | Price < SMA50 or SMA200 |
| GRADIENT | EMA9 up + MACD hist positive + rising | EMA9 down + MACD negative |
| CONFLUENCE | 3/4 indicators bullish | 2+ bearish |
| REVERSAL | No big red reversal candle | Red candle > 1.5x avg range |
| ENSEMBLE | 4-5 pass = BUY | 2+ fail = SELL |

## ATR Stop Loss

- **Stop Loss** = Entry - 1.5x ATR
- **Trailing** activates at Entry + 0.5x ATR
- **Target 1** = Entry + 2.0x ATR (R/R 1.33:1)
- **Target 2** = Entry + 3.0x ATR (R/R 2.00:1)

## Chart Patterns (10)

Bullish: Double Bottom, Bullish Flag, Ascending Triangle, Falling Wedge, Island Reversal
Bearish: Double Top, Bearish Flag, Descending Triangle, Rising Wedge, Island Reversal

## Backtesting

Strategy: RSI crosses above 35 + MACD histogram positive + price above SMA50 = BUY
Exit: RSI > 70 OR price < SMA50

## Probability Calibration

Sigmoid-based conversion from 9 technical inputs into BUY/SELL/HOLD probabilities with confidence levels.
