"""
Standalone technical analysis script — template version.
Edit TICKER variable and run. Outputs: 13 indicators, 5-gate pipeline,
ATR stop loss, chart patterns, backtest, probability calibration.
"""
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import math
import sys
import warnings
warnings.filterwarnings('ignore')

TICKER = sys.argv[1] if len(sys.argv) > 1 else "AXON"
t = yf.Ticker(TICKER)
df = t.history(period="1y", interval="1d")
df = df.dropna()
df.index = pd.to_datetime(df.index)

# 13 INDICATORS
df['RSI'] = ta.rsi(df['Close'], length=14)
stoch = ta.stoch(df['High'], df['Low'], df['Close'], k=14, d=3, smooth_k=3)
df['STOCH_K'] = stoch['STOCHk_14_3_3']
df['STOCH_D'] = stoch['STOCHd_14_3_3']
bb = ta.bbands(df['Close'], length=20, std=2)
df['BB_UPPER'] = bb['BBU_20_2.0_2.0']
df['BB_MID']   = bb['BBM_20_2.0_2.0']
df['BB_LOWER'] = bb['BBL_20_2.0_2.0']
df['WILLR'] = ta.willr(df['High'], df['Low'], df['Close'], length=14)
df['ATR'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)
don = ta.donchian(df['High'], df['Low'], lower_length=20, upper_length=20)
df['DON_UPPER'] = don['DCU_20_20']
df['DON_LOWER'] = don['DCL_20_20']
df['SMA20']  = ta.sma(df['Close'], length=20)
df['SMA50']  = ta.sma(df['Close'], length=50)
df['SMA200'] = ta.sma(df['Close'], length=200)
df['EMA9'] = ta.ema(df['Close'], length=9)
macd = ta.macd(df['Close'], fast=12, slow=26, signal=9)
df['MACD']        = macd['MACD_12_26_9']
df['MACD_SIGNAL'] = macd['MACDs_12_26_9']
df['MACD_HIST']   = macd['MACDh_12_26_9']
df['VOL_AVG20'] = df['Volume'].rolling(20).mean()
df['VOL_RATIO'] = df['Volume'] / df['VOL_AVG20']

latest = df.iloc[-1]
prev   = df.iloc[-2]
price  = latest['Close']

print(f"=== 13 INDICATORS: {TICKER} ===")
print(f"Price:      ${price:.2f}")
print(f"RSI:        {latest['RSI']:.1f}")
print(f"STOCH K/D:  {latest['STOCH_K']:.1f} / {latest['STOCH_D']:.1f}")
print(f"BB:         upper={latest['BB_UPPER']:.2f}, mid={latest['BB_MID']:.2f}, lower={latest['BB_LOWER']:.2f}")
print(f"Williams%R: {latest['WILLR']:.1f}")
print(f"ATR(14):    {latest['ATR']:.2f}")
print(f"SMA20:      {latest['SMA20']:.2f}")
print(f"SMA50:      {latest['SMA50']:.2f}")
print(f"SMA200:     {latest['SMA200']:.2f}")
print(f"EMA9:       {latest['EMA9']:.2f}")
print(f"MACD hist:  {latest['MACD_HIST']:.3f} (prev: {prev['MACD_HIST']:.3f})")
print(f"Volume:     {latest['VOL_RATIO']:.2f}x avg")

# 5-GATE PIPELINE
gates = {}
gate1_bull = (price > latest['SMA50']) and (price > latest['SMA200']) and (latest['SMA50'] > latest['SMA200'])
gate1_bear = (price < latest['SMA50']) or (price < latest['SMA200'])
gates['TREND'] = 'PASS' if gate1_bull else ('FAIL' if gate1_bear else 'NEUTRAL')

ema9_slope  = latest['EMA9'] - df.iloc[-4]['EMA9']
macd_rising = latest['MACD_HIST'] > prev['MACD_HIST']
gate2_bull  = (ema9_slope > 0) and (latest['MACD_HIST'] > 0) and macd_rising
gate2_bear  = (ema9_slope < 0) and (latest['MACD_HIST'] < 0)
gates['GRADIENT'] = 'PASS' if gate2_bull else ('FAIL' if gate2_bear else 'NEUTRAL')

conf_signals = [
    40 <= latest['RSI'] <= 70,
    latest['STOCH_K'] > 20 and latest['STOCH_K'] > latest['STOCH_D'],
    price > latest['BB_MID'],
    latest['WILLR'] > -80
]
conf_bear = [latest['RSI'] > 75, latest['STOCH_K'] < 20, price < latest['BB_LOWER'], latest['WILLR'] < -90]
gate3_bull = sum(conf_signals) >= 3
gate3_bear = sum(conf_bear) >= 2
gates['CONFLUENCE'] = 'PASS' if gate3_bull else ('FAIL' if gate3_bear else 'NEUTRAL')

last3 = df.iloc[-3:]
avg_range = (last3['High'] - last3['Low']).mean()
last_candle_body = abs(latest['Close'] - latest['Open'])
is_reversal = (latest['Close'] < latest['Open']) and (last_candle_body > avg_range * 1.5)
gates['REVERSAL'] = 'FAIL' if is_reversal else 'PASS'

pass_count = sum(1 for v in gates.values() if v == 'PASS')
fail_count = sum(1 for v in gates.values() if v == 'FAIL')
if pass_count >= 4:
    gates['ENSEMBLE'] = 'BUY'
elif fail_count >= 2:
    gates['ENSEMBLE'] = 'SELL'
else:
    gates['ENSEMBLE'] = 'HOLD'

print(f"\n=== 5-GATE PIPELINE ===")
for gate, result in gates.items():
    icon = 'V' if result == 'PASS' else ('X' if result == 'FAIL' else '-')
    print(f"[{icon}] {gate}: {result}")

# ATR STOP LOSS
atr = latest['ATR']
entry = price
stop_loss = entry - (1.5 * atr)
target_1  = entry + (2.0 * atr)
target_2  = entry + (3.0 * atr)
trail     = entry + (0.5 * atr)
print(f"\n=== ATR STOP LOSS ===")
print(f"Entry:     ${entry:.2f}")
print(f"ATR(14):   ${atr:.2f}")
print(f"Stop:      ${stop_loss:.2f}  (risk: ${entry-stop_loss:.2f})")
print(f"Trail at:  ${trail:.2f}")
print(f"Target 1:  ${target_1:.2f}  R/R {(target_1-entry)/(entry-stop_loss):.2f}:1")
print(f"Target 2:  ${target_2:.2f}  R/R {(target_2-entry)/(entry-stop_loss):.2f}:1")

# CHART PATTERNS
patterns = []
window = df.iloc[-30:]
w_l = window['Low'].values
min1_idx = w_l.argmin()
if 5 < min1_idx < len(w_l)-5:
    if abs(w_l[:min1_idx].min() - w_l[min1_idx+1:].min()) / w_l[:min1_idx].min() < 0.03:
        patterns.append("DOUBLE BOTTOM (bullish)")
w_h = window['High'].values
max1_idx = w_h.argmax()
if 5 < max1_idx < len(w_h)-5:
    if abs(w_h[:max1_idx].max() - w_h[max1_idx+1:].max()) / w_h[:max1_idx].max() < 0.03:
        patterns.append("DOUBLE TOP (bearish)")
last20 = df.iloc[-20:]
last5  = df.iloc[-5:]
uptrend_20   = (last20['Close'].iloc[-1] - last20['Close'].iloc[0]) / last20['Close'].iloc[0]
consol_5     = last5['Close'].std() / last5['Close'].mean()
downtrend_20 = (last20['Close'].iloc[0] - last20['Close'].iloc[-1]) / last20['Close'].iloc[0]
if uptrend_20 > 0.05 and consol_5 < 0.01:
    patterns.append("BULLISH FLAG")
if downtrend_20 > 0.05 and consol_5 < 0.01:
    patterns.append("BEARISH FLAG")
last15 = df.iloc[-15:]
if (last15['High'].std()/last15['High'].mean()) < 0.01 and (last15['Low'].iloc[-1]-last15['Low'].iloc[0])/last15['Low'].iloc[0] > 0.02:
    patterns.append("ASCENDING TRIANGLE (bullish)")
if (last15['Low'].std()/last15['Low'].mean()) < 0.01 and (last15['High'].iloc[-1]-last15['High'].iloc[0])/last15['High'].iloc[0] < -0.02:
    patterns.append("DESCENDING TRIANGLE (bearish)")
h_slope = (df.iloc[-1]['High']-df.iloc[-20]['High'])/df.iloc[-20]['High']
l_slope = (df.iloc[-1]['Low']-df.iloc[-20]['Low'])/df.iloc[-20]['Low']
if h_slope < -0.03 and l_slope < -0.01 and h_slope < l_slope:
    patterns.append("FALLING WEDGE (bullish)")
if h_slope > 0.01 and l_slope > 0.03 and l_slope > h_slope:
    patterns.append("RISING WEDGE (bearish)")
print(f"\n=== CHART PATTERNS ===")
for p in (patterns if patterns else ["None detected"]):
    print(f"  - {p}")

# BACKTEST
df2 = df.copy()
df2['signal'] = 0
for i in range(1, len(df2)):
    rsi_cross = df2['RSI'].iloc[i] > 35 and df2['RSI'].iloc[i-1] <= 35
    macd_pos  = df2['MACD_HIST'].iloc[i] > 0
    above_sma = df2['Close'].iloc[i] > df2['SMA50'].iloc[i]
    if rsi_cross and macd_pos and above_sma:
        df2.iloc[i, df2.columns.get_loc('signal')] = 1
    if df2['RSI'].iloc[i] > 70 or df2['Close'].iloc[i] < df2['SMA50'].iloc[i]:
        df2.iloc[i, df2.columns.get_loc('signal')] = -1
trades = []
in_trade = False
ep = 0
for i in range(len(df2)):
    if df2['signal'].iloc[i] == 1 and not in_trade:
        in_trade = True
        ep = df2['Close'].iloc[i]
    elif df2['signal'].iloc[i] == -1 and in_trade:
        trades.append((df2['Close'].iloc[i]-ep)/ep)
        in_trade = False
print(f"\n=== BACKTEST (1yr RSI+MACD) ===")
if trades:
    t_s = pd.Series(trades)
    wr  = (t_s>0).mean()*100
    ar  = t_s.mean()*100
    md  = t_s.min()*100
    pf  = t_s[t_s>0].sum()/abs(t_s[t_s<0].sum()) if (t_s<0).any() else float('inf')
    print(f"  Trades: {len(trades)} | Win Rate: {wr:.1f}% | Avg Return: {ar:.2f}% | Profit Factor: {pf:.2f}x | Max DD: {md:.2f}%")
else:
    print("  Not enough signals")

# PROBABILITY
def sigmoid(score, slope=0.008, intercept=-1.2):
    return 1/(1+math.exp(-(slope*score+intercept)))

buy_score = sell_score = 0.0
rsi = latest['RSI']
if rsi < 25: buy_score += 100
elif rsi < 30: buy_score += 80
elif rsi < 40: buy_score += 50
elif rsi > 75: sell_score += 100
elif rsi > 70: sell_score += 80
elif rsi > 60: sell_score += 40

stk = latest['STOCH_K']
if stk < 15: buy_score += 80
elif stk < 25: buy_score += 50
elif stk > 85: sell_score += 80
elif stk > 75: sell_score += 50

wr2 = latest['WILLR']
if wr2 < -85: buy_score += 80
elif wr2 < -70: buy_score += 40
elif wr2 > -15: sell_score += 80
elif wr2 > -30: sell_score += 40

bb_r = latest['BB_UPPER'] - latest['BB_LOWER']
bb_b = (price - latest['BB_LOWER']) / bb_r if bb_r > 0 else 0.5
if bb_b < 0.1: buy_score += 80
elif bb_b < 0.3: buy_score += 40
elif bb_b > 0.9: sell_score += 80
elif bb_b > 0.7: sell_score += 40

don_r = latest['DON_UPPER'] - latest['DON_LOWER']
don_p = (price - latest['DON_LOWER']) / don_r if don_r > 0 else 0.5
if don_p < 0.15: buy_score += 60
elif don_p > 0.85: sell_score += 60

mh = latest['MACD_HIST']
pm = prev['MACD_HIST']
if mh > 0 and mh > pm: buy_score += 70
elif mh < 0 and mh < pm: sell_score += 70

if price > latest['SMA20'] and price > latest['EMA9']: buy_score += 50
elif price < latest['SMA20'] and price < latest['EMA9']: sell_score += 50

vr = latest['VOL_RATIO']
if vr > 1.5 and price > prev['Close']: buy_score += 40
if vr > 1.5 and price < prev['Close']: sell_score += 40

bull_p = sum(1 for p in patterns if 'bullish' in p.lower() or 'bottom' in p.lower())
bear_p = sum(1 for p in patterns if 'bearish' in p.lower() or 'top' in p.lower())
buy_score += bull_p * 50
sell_score += bear_p * 50

bp = sigmoid(buy_score)
sp = sigmoid(sell_score)
hp = max(0, 1 - bp - sp)
tot = bp + sp + hp
buy_pct  = round(bp / tot * 100, 1)
sell_pct = round(sp / tot * 100, 1)
hold_pct = round(hp / tot * 100, 1)
mx = max(buy_pct, sell_pct)
conf = 'VERY HIGH' if mx >= 75 else 'HIGH' if mx >= 60 else 'MEDIUM' if mx >= 40 else 'LOW'

print(f"\n=== PROBABILITY ===")
print(f"  BUY:  {buy_pct}%  |  SELL: {sell_pct}%  |  HOLD: {hold_pct}%")
print(f"  Confidence: {conf}")

decision = gates.get('ENSEMBLE', 'HOLD')
print(f"\n=== FINAL SIGNAL: {decision} ===")
