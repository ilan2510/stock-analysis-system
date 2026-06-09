import yfinance as yf
import pandas as pd
import pandas_ta as ta
import math
import warnings
warnings.filterwarnings('ignore')

TICKERS = ["BE", "CEG", "GEV", "CLS", "META"]

for TICKER in TICKERS:
    try:
        t = yf.Ticker(TICKER)
        df = t.history(period="1y", interval="1d")
        df = df.dropna()
        df.index = pd.to_datetime(df.index)

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

        # GATE 1: TREND
        gate1 = (price > latest['SMA50']) and (price > latest['SMA200']) and (latest['SMA50'] > latest['SMA200'])
        # GATE 2: GRADIENT
        ema9_slope  = latest['EMA9'] - df.iloc[-4]['EMA9']
        macd_rising = latest['MACD_HIST'] > prev['MACD_HIST']
        gate2 = (ema9_slope > 0) and (latest['MACD_HIST'] > 0) and macd_rising
        # GATE 3: CONFLUENCE
        conf = [
            40 <= latest['RSI'] <= 70,
            latest['STOCH_K'] > 20 and latest['STOCH_K'] > latest['STOCH_D'],
            price > latest['BB_MID'],
            latest['WILLR'] > -80
        ]
        gate3 = sum(conf) >= 3
        # GATE 4: REVERSAL
        last3 = df.iloc[-3:]
        avg_range = (last3['High'] - last3['Low']).mean()
        last_body = abs(latest['Close'] - latest['Open'])
        is_reversal = (latest['Close'] < latest['Open']) and (last_body > avg_range * 1.5)
        gate4 = not is_reversal

        gates_pass = sum([gate1, gate2, gate3, gate4])
        gates_fail = sum([not gate1, not gate2, not gate3, not gate4])
        if gates_pass >= 4:
            ensemble = "BUY"
        elif gates_fail >= 2:
            ensemble = "SELL"
        else:
            ensemble = "HOLD"

        g1 = "PASS" if gate1 else "FAIL"
        g2 = "PASS" if gate2 else "FAIL"
        g3 = "PASS" if gate3 else "FAIL"
        g4 = "PASS" if gate4 else "FAIL"

        print(f"\n{'='*50}")
        print(f"{TICKER} | ${price:.2f} | RSI:{latest['RSI']:.1f} | MACD_H:{latest['MACD_HIST']:.3f}")
        print(f"  SMA50=${latest['SMA50']:.2f} | SMA200=${latest['SMA200']:.2f} | EMA9=${latest['EMA9']:.2f}")
        print(f"  TREND:{g1} | GRADIENT:{g2} | CONFLUENCE:{g3} | REVERSAL:{g4}")
        print(f"  >>> ENSEMBLE: {ensemble} ({gates_pass}/4 pass) <<<")
    except Exception as e:
        print(f"\n{TICKER}: ERROR - {e}")
