#!/usr/bin/env python3
"""
Trend & Sector Analyzer - Agent 5
Architecture: CODE fetches + analyzes -> AI adds narrative via WebSearch.
"""

import sys
import math
import time
import concurrent.futures
import warnings
warnings.filterwarnings('ignore')

# Windows cp1255 fix
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

try:
    import yfinance as yf
    YF_AVAILABLE = True
except ImportError:
    YF_AVAILABLE = False
    print("WARNING: yfinance not installed.")
    sys.exit(1)

_args   = [a for a in sys.argv[1:] if not a.startswith('--')]
TICKER  = _args[0].upper().replace('$', '') if _args else 'NFLX'
VERBOSE = '--verbose' in sys.argv or '-v' in sys.argv

# ── Sector ETF mapping ───────────────────────────────────────────
SECTOR_ETFS = {
    'XLK': 'Technology', 'XLF': 'Financials', 'XLE': 'Energy',
    'XLV': 'Healthcare', 'XLI': 'Industrials', 'XLC': 'Communication',
    'XLRE': 'Real Estate', 'XLB': 'Materials', 'XLY': 'Consumer Disc',
    'XLP': 'Consumer Staples', 'XLU': 'Utilities'
}

SECTOR_TO_ETF = {
    'Technology': 'XLK', 'Financial Services': 'XLF', 'Energy': 'XLE',
    'Healthcare': 'XLV', 'Industrials': 'XLI', 'Communication Services': 'XLC',
    'Real Estate': 'XLRE', 'Basic Materials': 'XLB', 'Consumer Cyclical': 'XLY',
    'Consumer Defensive': 'XLP', 'Utilities': 'XLU'
}

OFFENSIVE = {'XLK', 'XLY', 'XLC', 'XLF'}
DEFENSIVE = {'XLP', 'XLU', 'XLV', 'XLRE'}


def safe_float(val, default=0.0):
    if val is None: return default
    try:
        f = float(val)
        return default if math.isnan(f) else f
    except (TypeError, ValueError):
        return default


def calc_return(hist, days):
    if hist is None or hist.empty or len(hist) < 2:
        return 0.0
    try:
        end_price = float(hist['Close'].iloc[-1])
        idx = min(days, len(hist) - 1)
        start_price = float(hist['Close'].iloc[-idx])
        if start_price == 0:
            return 0.0
        return (end_price - start_price) / start_price * 100
    except Exception:
        return 0.0


def get_ticker_hist(batch, ticker):
    try:
        df = batch[ticker]
        if hasattr(df, 'empty') and not df.empty and 'Close' in df.columns:
            return df.dropna(subset=['Close'])
    except (KeyError, TypeError):
        pass
    return None


# ══════════════════════════════════════════════════════════════════
#  PARALLEL FETCH — info + batch download simultaneously
# ══════════════════════════════════════════════════════════════════
_t0 = time.time()
print(f"Fetching data for ${TICKER}...", end=' ', flush=True)

all_tickers = list(SECTOR_ETFS.keys()) + ['SPY', '^VIX', TICKER]
all_tickers = list(dict.fromkeys(all_tickers))

with concurrent.futures.ThreadPoolExecutor(max_workers=2) as _ex:
    _f_info  = _ex.submit(lambda: yf.Ticker(TICKER).info or {})
    _f_batch = _ex.submit(lambda: yf.download(
        all_tickers, period='6mo', interval='1d',
        progress=False, group_by='ticker'))
    info      = _f_info.result()
    batch_raw = _f_batch.result()

print(f"{time.time() - _t0:.1f}s")

stock_sector   = info.get('sector', 'Unknown')
stock_industry = info.get('industry', 'Unknown')
stock_name     = info.get('shortName', TICKER)
stock_etf      = SECTOR_TO_ETF.get(stock_sector, None)


# ══════════════════════════════════════════════════════════════════
#  PROCESS DATA
# ══════════════════════════════════════════════════════════════════

# ── SPY ──────────────────────────────────────────────────────────
spy_hist = get_ticker_hist(batch_raw, 'SPY')
spy_1w = calc_return(spy_hist, 5)
spy_1m = calc_return(spy_hist, 21)
spy_3m = calc_return(spy_hist, 63)

# ── VIX ──────────────────────────────────────────────────────────
vix_hist = get_ticker_hist(batch_raw, '^VIX')
vix_current = vix_change = 0.0
if vix_hist is not None and not vix_hist.empty:
    vix_close = vix_hist['Close'].dropna()
    if len(vix_close) >= 2:
        vix_current = safe_float(vix_close.iloc[-1])
        vix_1m_ago  = safe_float(vix_close.iloc[-min(21, len(vix_close) - 1)])
        if vix_1m_ago > 0:
            vix_change = (vix_current - vix_1m_ago) / vix_1m_ago * 100

# VIX level
if vix_current < 15:     vix_label = "LOW"
elif vix_current < 20:   vix_label = "NORMAL"
elif vix_current < 25:   vix_label = "ELEVATED"
elif vix_current < 30:   vix_label = "HIGH"
else:                    vix_label = "EXTREME"

# VIX direction — level tells you WHERE fear is, direction tells you WHERE it's GOING
if vix_change > 15:      vix_dir = "SPIKING"
elif vix_change > 5:     vix_dir = "RISING"
elif vix_change < -15:   vix_dir = "COLLAPSING"
elif vix_change < -5:    vix_dir = "FALLING"
else:                    vix_dir = "STABLE"

# Market regime
if spy_1m > 2 and vix_current < 20:     regime = "RISK-ON"
elif spy_1m < -2 or vix_current > 25:   regime = "RISK-OFF"
else:                                    regime = "NEUTRAL"

# ── Sector performance ───────────────────────────────────────────
sector_data = {}
for etf, name in SECTOR_ETFS.items():
    hist = get_ticker_hist(batch_raw, etf)
    sector_data[etf] = {
        'name': name,
        '1w': calc_return(hist, 5),
        '1m': calc_return(hist, 21),
        '3m': calc_return(hist, 63),
    }

ranked   = sorted(sector_data.items(), key=lambda x: x[1]['1m'], reverse=True)
leaders  = ranked[:3]
laggards = ranked[-3:]

stock_sector_rank = 0
for i, (etf, d) in enumerate(ranked, 1):
    if etf == stock_etf:
        stock_sector_rank = i

# ── Stock vs sector ──────────────────────────────────────────────
stock_hist = get_ticker_hist(batch_raw, TICKER)
stock_1w = calc_return(stock_hist, 5)
stock_1m = calc_return(stock_hist, 21)
stock_3m = calc_return(stock_hist, 63)

sd = sector_data.get(stock_etf, {'1w': 0, '1m': 0, '3m': 0, 'name': 'Unknown'})
sector_vs_spy    = sd['1m'] - spy_1m
stock_vs_sector  = stock_1m - sd['1m']

# ── Rotation ─────────────────────────────────────────────────────
off_avg = def_avg = 0.0
off_count = def_count = 0
for etf, d in sector_data.items():
    if etf in OFFENSIVE:
        off_avg += d['1m'];  off_count += 1
    elif etf in DEFENSIVE:
        def_avg += d['1m'];  def_count += 1
if off_count > 0: off_avg /= off_count
if def_count > 0: def_avg /= def_count

rotation_spread = off_avg - def_avg
if rotation_spread > 3:     rotation = "RISK-ON"
elif rotation_spread < -3:  rotation = "RISK-OFF"
else:                       rotation = "BALANCED"

# ── Momentum ─────────────────────────────────────────────────────
accelerating = []
decelerating = []
for etf, d in ranked:
    weekly_pace = d['1w'] * 4
    diff = weekly_pace - d['1m']
    if diff > 2:    accelerating.append((etf, d['name'], diff))
    elif diff < -2: decelerating.append((etf, d['name'], diff))

stock_sector_accel = False
stock_sector_decel = False
if stock_etf:
    stock_sector_accel = any(etf == stock_etf for etf, _, _ in accelerating)
    stock_sector_decel = any(etf == stock_etf for etf, _, _ in decelerating)

# ── NEW: Market breadth — how many sectors beating SPY? ──────────
breadth_count = sum(1 for _, d in sector_data.items() if d['1m'] > spy_1m)
if breadth_count >= 8:     breadth_label = "BROAD"
elif breadth_count >= 5:   breadth_label = "HEALTHY"
elif breadth_count >= 3:   breadth_label = "NARROW"
else:                      breadth_label = "VERY NARROW"

# ── NEW: Multi-timeframe alignment for stock's sector ────────────
if stock_etf and stock_etf in sector_data:
    s = sector_data[stock_etf]
    dirs = []
    for tf in [s['1w'], s['1m'], s['3m']]:
        dirs.append('UP' if tf > 1 else ('DN' if tf < -1 else 'FLAT'))
    tf_str = '/'.join(dirs)

    if all(d == 'UP' for d in dirs):
        alignment = "ALL UP"
        alignment_label = "STRONG UPTREND"
    elif all(d == 'DN' for d in dirs):
        alignment = "ALL DOWN"
        alignment_label = "STRONG DOWNTREND"
    elif dirs[0] == 'UP' and dirs[1] == 'DN':
        alignment = "REVERSING UP"
        alignment_label = "POSSIBLE RECOVERY"
    elif dirs[0] == 'DN' and dirs[1] == 'UP':
        alignment = "REVERSING DOWN"
        alignment_label = "LOSING MOMENTUM"
    else:
        alignment = "MIXED"
        alignment_label = "NO CLEAR TREND"
else:
    tf_str = "N/A"
    alignment = "N/A"
    alignment_label = "NO DATA"

# ── NEW: Alpha quality — beating a strong sector vs a weak one ───
if stock_vs_sector > 5:
    if sd['1m'] > 2:
        alpha_quality = "REAL ALPHA (beating STRONG sector)"
    elif sd['1m'] < -2:
        alpha_quality = "RELATIVE ALPHA (less bad than WEAK sector)"
    else:
        alpha_quality = "ALPHA (beating flat sector)"
elif stock_vs_sector < -5:
    if sd['1m'] > 2:
        alpha_quality = "LAGGING (can't keep up with STRONG sector)"
    elif sd['1m'] < -2:
        alpha_quality = "DOUBLE DRAG (weak in WEAK sector)"
    else:
        alpha_quality = "UNDERPERFORMING (behind flat sector)"
else:
    alpha_quality = "IN LINE WITH SECTOR"


# ══════════════════════════════════════════════════════════════════
#  VERBOSE OUTPUT (--verbose only)
# ══════════════════════════════════════════════════════════════════
if VERBOSE:
    sep = '=' * 65
    print(f"\n{sep}")
    print(f"  TREND & SECTOR ANALYSIS: ${TICKER} ({stock_name}) [VERBOSE]")
    print(f"  Sector: {stock_sector} | Industry: {stock_industry}")
    print(f"{sep}")

    print(f"\n--- MARKET OVERVIEW ---")
    print(f"  SPY:     1W {spy_1w:+.1f}% | 1M {spy_1m:+.1f}% | 3M {spy_3m:+.1f}%")
    print(f"  VIX:     {vix_current:.1f} ({vix_label}, {vix_dir}) | 1M change: {vix_change:+.1f}%")
    print(f"  Regime:  {regime} | Breadth: {breadth_count}/11 > SPY ({breadth_label})")

    print(f"\n--- SECTOR PERFORMANCE (ranked by 1M) ---")
    print(f"  {'Rank':4s} {'Sector':20s} {'ETF':5s} {'1W':>8s} {'1M':>8s} {'3M':>8s}")
    print(f"  {'-'*4} {'-'*20} {'-'*5} {'-'*8} {'-'*8} {'-'*8}")
    for i, (etf, d) in enumerate(ranked, 1):
        marker = " <-- " if etf == stock_etf else ""
        print(f"  {i:4d} {d['name']:20s} {etf:5s} {d['1w']:+7.1f}% {d['1m']:+7.1f}% {d['3m']:+7.1f}%{marker}")
    print(f"  {'---':4s} {'--- S&P 500 ---':20s} {'SPY':5s} {spy_1w:+7.1f}% {spy_1m:+7.1f}% {spy_3m:+7.1f}%")

    print(f"\n--- STOCK SECTOR CONTEXT ---")
    print(f"  Sector Rank:     #{stock_sector_rank}/11")
    print(f"  Sector 1M:       {sd['1m']:+.1f}% (vs SPY: {sector_vs_spy:+.1f}%)")
    print(f"  Stock 1M:        {stock_1m:+.1f}% (vs sector: {stock_vs_sector:+.1f}%)")
    print(f"  Alpha Quality:   {alpha_quality}")
    print(f"  TF Alignment:    1W/1M/3M: {tf_str} ({alignment_label})")

    print(f"\n--- ROTATION ---")
    print(f"  Offensive avg 1M: {off_avg:+.1f}% | Defensive avg 1M: {def_avg:+.1f}%")
    print(f"  Spread: {rotation_spread:+.1f}% | {rotation}")
    if accelerating:
        print(f"  Accelerating: {', '.join(f'{name} ({etf})' for etf, name, _ in accelerating)}")
    if decelerating:
        print(f"  Decelerating: {', '.join(f'{name} ({etf})' for etf, name, _ in decelerating)}")


# ══════════════════════════════════════════════════════════════════
#  SCORING
# ══════════════════════════════════════════════════════════════════
score = 50.0

# 1. Sector rank (-15 to +15)
if stock_sector_rank > 0:
    score += (6 - stock_sector_rank) * 3

# 2. Sector vs SPY (-10 to +10)
if sector_vs_spy > 5:      score += 10
elif sector_vs_spy > 2:    score += 5
elif sector_vs_spy < -5:   score -= 10
elif sector_vs_spy < -2:   score -= 5

# 3. Stock vs sector (-8 to +8)
if stock_vs_sector > 10:   score += 8
elif stock_vs_sector > 5:  score += 5
elif stock_vs_sector < -10: score -= 8
elif stock_vs_sector < -5: score -= 5

# 4. Rotation alignment (-5 to +5)
if stock_etf in OFFENSIVE and rotation_spread > 3:     score += 5
elif stock_etf in DEFENSIVE and rotation_spread < -3:  score += 5
elif stock_etf in OFFENSIVE and rotation_spread < -3:  score -= 5
elif stock_etf in DEFENSIVE and rotation_spread > 3:   score -= 5

# 5. Momentum (-5 to +5)
if stock_etf:
    if stock_sector_accel:   score += 5
    elif stock_sector_decel: score -= 5

# 6. VIX level (-5 to +3)
if vix_current < 15:     score += 3
elif vix_current > 25:   score -= 5
elif vix_current > 20:   score -= 2

# 7. NEW: Market breadth (-5 to +5)
if breadth_count >= 8:     score += 5
elif breadth_count >= 5:   score += 2
elif breadth_count <= 2:   score -= 5
elif breadth_count <= 3:   score -= 2

# 8. NEW: Multi-timeframe alignment (-5 to +5)
if alignment == "ALL UP":           score += 5
elif alignment == "ALL DOWN":       score -= 5
elif alignment == "REVERSING UP":   score += 3
elif alignment == "REVERSING DOWN": score -= 3

# 9. NEW: VIX direction (-4 to +4)
if vix_dir == "SPIKING":       score -= 4
elif vix_dir == "RISING":      score -= 2
elif vix_dir == "COLLAPSING":  score += 4
elif vix_dir == "FALLING":     score += 2

# 10. NEW: Alpha quality (-3 to +3)
if "REAL ALPHA" in alpha_quality:        score += 3
elif "RELATIVE ALPHA" in alpha_quality:  score += 1
elif "DOUBLE DRAG" in alpha_quality:     score -= 3
elif "LAGGING" in alpha_quality:         score -= 1

score = max(0, min(100, round(score)))

if score >= 65:   signal = "TAILWIND"
elif score >= 40: signal = "NEUTRAL"
else:             signal = "HEADWIND"

confidence = ("HIGH"        if (score >= 80 or score <= 20) else
              "MEDIUM-HIGH" if (score >= 65 or score <= 35) else "MEDIUM")


# ══════════════════════════════════════════════════════════════════
#  COMPACT OUTPUT
# ══════════════════════════════════════════════════════════════════
sep = '=' * 65
print(f"\n{sep}")
print(f"  TREND & SECTOR ANALYSIS: ${TICKER} ({stock_name})")
print(f"{sep}")

# Line 1: Market snapshot
print(f"  MARKET:     SPY 1W {spy_1w:+.1f}% | 1M {spy_1m:+.1f}% | 3M {spy_3m:+.1f}% | VIX {vix_current:.1f} ({vix_label}, {vix_dir}) | {regime}")

# Line 2: Sector leaders/laggards + breadth
leaders_str  = ', '.join(f"{d['name'].split()[0]} {d['1m']:+.0f}%" for _, d in leaders)
laggards_str = ', '.join(f"{d['name'].split()[0]} {d['1m']:+.0f}%" for _, d in laggards)
print(f"  SECTORS:    Lead: {leaders_str} | Lag: {laggards_str} | Breadth: {breadth_count}/11 ({breadth_label})")

# Line 3: Rotation
print(f"  ROTATION:   Off {off_avg:+.1f}% vs Def {def_avg:+.1f}% | Spread {rotation_spread:+.1f}% | {rotation}")

# Line 4: Stock's sector position + timeframe alignment
mom_str = "ACCEL" if stock_sector_accel else ("DECEL" if stock_sector_decel else "STEADY")
print(f"  SECTOR:     {stock_sector} #{stock_sector_rank}/11 | 1M {sd['1m']:+.1f}% (vs SPY {sector_vs_spy:+.1f}%) | Mom: {mom_str} | TF: {tf_str} ({alignment})")

# Line 5: Stock alpha
print(f"  STOCK:      ${TICKER} 1M {stock_1m:+.1f}% (vs sector {stock_vs_sector:+.1f}%) | {alpha_quality}")

print()
print(f"{sep}")
print(f"  SCORE:  {score}/100  {signal}  |  Confidence: {confidence}")
print(f"{sep}")
