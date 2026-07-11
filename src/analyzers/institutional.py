#!/usr/bin/env python3
"""
Institutional Ownership Analyzer - Agent 2
Architecture: CODE fetches + analyzes -> AI just summarizes.
"""
from __future__ import annotations
import sys
import json
import math
import time
import concurrent.futures
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from models import HolderRecord

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

# ── Smart money lists ─────────────────────────────────────────────────────────
BIG_3 = ['blackrock', 'vanguard', 'state street']
NOTABLE_FUNDS = [
    'fidelity', 'fil ltd', 'fmr',
    'capital group', 'capital international', 'capital world', 'capital research',
    't. rowe', 't.rowe', 'price associates',
    'wellington', 'geode',
    'jpmorgan', 'jp morgan', 'goldman sachs', 'morgan stanley',
    'citadel', 'renaissance', 'bridgewater', 'two sigma',
    'marshall wace', 'millennium', 'ark invest', 'berkshire',
    'invesco', 'schwab', 'northern trust', 'susquehanna',
    'jane street', 'point72', 'tiger global', 'coatue',
    'd.e. shaw', 'de shaw', 'soros', 'druckenmiller',
    'baillie gifford', 'lone pine', 'viking global', 'appaloosa',
    'elliott management', 'third point', 'pershing square'
]
ACTIVIST_FUNDS = [
    'elliott', 'third point', 'pershing square', 'icahn', 'carl icahn',
    'starboard', 'valueact', 'trian', 'jana partners', 'engine no. 1',
    'nelson peltz', 'dan loeb', 'bill ackman'
]

def is_big3(name: str) -> bool:     return any(b in name.lower() for b in BIG_3)
def is_notable(name: str) -> bool:  return any(f in name.lower() for f in NOTABLE_FUNDS)
def is_activist(name: str) -> bool: return any(a in name.lower() for a in ACTIVIST_FUNDS)

def safe_pct(val) -> float:
    if val is None: return 0.0
    try:
        f = float(val)
        return 0.0 if math.isnan(f) else f
    except (TypeError, ValueError):
        return 0.0


# ══════════════════════════════════════════════════════════════════════════════
#  PARALLEL FETCH — all 3 yfinance calls simultaneously
# ══════════════════════════════════════════════════════════════════════════════
_t0 = time.time()
print(f"Fetching data for ${TICKER}...", end=' ', flush=True)

with concurrent.futures.ThreadPoolExecutor(max_workers=3) as _ex:
    _fi = _ex.submit(lambda: yf.Ticker(TICKER).institutional_holders)
    _fm = _ex.submit(lambda: yf.Ticker(TICKER).major_holders)
    _fo = _ex.submit(lambda: yf.Ticker(TICKER).info or {})
    inst  = _fi.result()
    major = _fm.result()
    info  = _fo.result()

print(f"{time.time() - _t0:.1f}s")


# ══════════════════════════════════════════════════════════════════════════════
#  PROCESS DATA
# ══════════════════════════════════════════════════════════════════════════════

# ── Holders ───────────────────────────────────────────────────────────────────
holders: list[HolderRecord] = []
if inst is not None and not inst.empty:
    for _, row in inst.iterrows():
        name   = str(row.get('Holder', 'N/A')).strip()
        pct    = safe_pct(row.get('pctHeld', 0))
        shares = int(row.get('Shares', 0)) if row.get('Shares') else 0
        change = safe_pct(row.get('pctChange', 0))

        if change > 0.9:     direction = "NEW POSITION"
        elif change > 0.5:   direction = "MAJOR ADD"
        elif change > 0:     direction = "ADDING"
        elif change < -0.25: direction = "MAJOR CUT"
        elif change < 0:     direction = "REDUCING"
        else:                direction = "UNCHANGED"

        _big3     = is_big3(name)
        _activist = is_activist(name)
        _notable  = is_notable(name)
        tag = "BIG 3" if _big3 else ("ACTIVIST" if _activist else ("NOTABLE" if _notable else ""))
        holders.append(HolderRecord(
            name=name, pct=pct, shares=shares,
            change=change, direction=direction, tag=tag,
            is_big3=_big3, is_notable=_notable, is_activist=_activist,
        ))

# ── Ownership stats ───────────────────────────────────────────────────────────
inst_pct = inst_float_pct = insider_pct = 0.0
inst_count = 0
if major is not None and not major.empty:
    for idx, row in major.iterrows():
        val = row['Value']
        if idx == 'insidersPercentHeld':            insider_pct    = safe_pct(val) * 100
        elif idx == 'institutionsPercentHeld':      inst_pct       = safe_pct(val) * 100
        elif idx == 'institutionsFloatPercentHeld': inst_float_pct = safe_pct(val) * 100
        elif idx == 'institutionsCount':            inst_count     = int(val) if val else 0

# ── Short interest ────────────────────────────────────────────────────────────
short_pct         = safe_pct(info.get('shortPercentOfFloat', 0)) * 100
short_ratio       = safe_pct(info.get('shortRatio', 0))
shares_short      = info.get('sharesShort', 0) or 0
shares_short_prev = info.get('sharesShortPriorMonth', 0) or 0
short_mom = 0.0
if shares_short_prev > 0 and shares_short > 0:
    short_mom = (shares_short - shares_short_prev) / shares_short_prev * 100

# ── Trend ─────────────────────────────────────────────────────────────────────
total      = len(holders)
increasing = sum(1 for h in holders if h.change > 0)
decreasing = sum(1 for h in holders if h.change < 0)
unchanged  = sum(1 for h in holders if h.change == 0)

big3_total    = sum(1 for h in holders if h.is_big3)
big3_adding   = sum(1 for h in holders if h.is_big3 and h.change > 0)
big3_reducing = sum(1 for h in holders if h.is_big3 and h.change < 0)
big3_new      = sum(1 for h in holders if h.is_big3 and h.change > 0.9)

ratio = increasing / total if total > 0 else 0
if ratio >= 0.7:   trend = "STRONGLY INCREASING"
elif ratio >= 0.5: trend = "INCREASING"
elif ratio >= 0.3: trend = "MIXED"
elif total > 0:    trend = "DECREASING"
else:              trend = "NO DATA"

# ── Concentration risk — top 3 holders ────────────────────────────────────────
sorted_h   = sorted(holders, key=lambda x: x.pct, reverse=True)
top3_pct   = sum(h.pct for h in sorted_h[:3]) * 100 if len(sorted_h) >= 3 else 0
conc_label = "HIGH" if top3_pct > 25 else ("MODERATE" if top3_pct > 15 else "LOW")

# ── 13F filing date — how stale is this data? ────────────────────────────────
filing_date = None
if inst is not None and not inst.empty and 'Date Reported' in inst.columns:
    try:
        filing_date = str(inst['Date Reported'].max())[:10]
    except Exception:
        pass

# ── Weighted flow — dollar-weighted direction of smart money ──────────────────
total_weight  = sum(h.pct for h in holders) or 0.01
weighted_flow = sum(h.change * h.pct for h in holders) / total_weight
flow_label    = "NET INFLOW" if weighted_flow > 0.05 else ("NET OUTFLOW" if weighted_flow < -0.05 else "BALANCED")

# ── Activist detection ────────────────────────────────────────────────────────
activists = [h for h in holders if h.is_activist]


# ══════════════════════════════════════════════════════════════════════════════
#  VERBOSE OUTPUT (--verbose only)
# ══════════════════════════════════════════════════════════════════════════════
if VERBOSE:
    sep = '=' * 65
    print(f"\n{sep}")
    print(f"  INSTITUTIONAL ANALYSIS: ${TICKER} [VERBOSE]")
    print(f"{sep}")

    print(f"\n--- TOP {total} HOLDERS ---")
    for h in holders:
        sign    = "+" if h.change > 0 else ""
        icon    = "[+]" if h.change > 0 else ("[-]" if h.change < 0 else "[=]")
        tag_str = f" [{h.tag}]" if h.tag else ""
        print(f"  {icon} {h.name:42s} {h.pct*100:5.2f}% | {h.shares:>12,} | {sign}{h.change*100:.1f}% {h.direction}{tag_str}")

    print(f"\n--- OWNERSHIP STATS ---")
    print(f"  Insider % Held:          {insider_pct:.2f}%")
    print(f"  Institutions % Held:     {inst_pct:.2f}%")
    print(f"  Institutions % of Float: {inst_float_pct:.2f}%")
    print(f"  Number of Institutions:  {inst_count:,}")

    print(f"\n--- SHORT INTEREST ---")
    print(f"  Short % of Float:  {short_pct:.2f}%")
    print(f"  Days to Cover:     {short_ratio:.2f}")
    print(f"  Shares Short:      {shares_short:,}")
    if short_mom:
        sign = "+" if short_mom > 0 else ""
        print(f"  Short Change MoM:  {sign}{short_mom:.1f}%")

    print(f"\n--- TREND ---")
    print(f"  Top {total} Direction: {increasing} ADDING | {decreasing} REDUCING | {unchanged} UNCHANGED")
    if big3_total > 0:
        print(f"  Big 3: {big3_total} found | {big3_adding} adding | {big3_reducing} reducing | {big3_new} new")
    print(f"  Trend: {trend}")


# ══════════════════════════════════════════════════════════════════════════════
#  SCORING (computed in code)
# ══════════════════════════════════════════════════════════════════════════════
score = 50.0

# 1. Direction of top holders (-20 to +20)
if total > 0:
    score += (ratio - 0.5) * 40

# 2. Smart money signals — weighted by fund reputation
for h in holders:
    if h.is_big3:
        if h.change > 0.9:     score += 6
        elif h.change > 0:     score += 4
        elif h.change < 0:     score -= 6
    elif h.is_notable:
        if h.change > 0.5:     score += 3
        elif h.change > 0:     score += 1
        elif h.change < -0.03: score -= 2

# 3. Short interest level
if short_pct > 30:    score -= 8
elif short_pct > 20:  score -= 5
elif short_pct > 10:  score -= 3
elif short_pct < 3:   score += 5
elif short_pct < 5:   score += 3

# 4. Short momentum — rising = bears accumulating pressure
if short_mom > 20:    score -= 5
elif short_mom > 10:  score -= 3
elif short_mom < -20: score += 5
elif short_mom < -10: score += 3

# 5. Institutional ownership level
if 40 <= inst_pct <= 70: score += 3
elif inst_pct > 70:      score += 1
elif inst_pct < 25:      score -= 3

# 5b. Insider ownership — skin in the game (Buffett signal)
mcap = info.get('marketCap', 0) or 0
is_small_mid = mcap < 20_000_000_000  # < $20B
if insider_pct > 10:      score += 6  # founder/owner-operator
elif insider_pct > 5:     score += 4  # strong alignment
elif insider_pct > 1:     score += 2  # adequate
elif is_small_mid and insider_pct < 0.5: score -= 3  # no skin in the game

# 6. Magnitude bonus — very large position changes = conviction
for h in holders:
    if h.change > 2:     score += 2
    elif h.change > 0.9: score += 1
    if h.change < -0.5:  score -= 2

# 7. Activist presence
for h in activists:
    if h.change > 0.9:   score += 8
    elif h.change > 0:   score += 5
    elif h.change < 0:   score -= 4

# 8. Concentration risk
if top3_pct > 30:   score -= 4
elif top3_pct > 25: score -= 2

# 9. Short squeeze potential — high SI + hard to cover + institutions accumulating
squeeze_flag = False
if short_pct > 15 and short_ratio > 5 and ratio >= 0.5:
    squeeze_flag = True
    score += 6

score      = max(0, min(100, round(score)))
signal     = "BULLISH" if score >= 70 else ("NEUTRAL" if score >= 45 else "BEARISH")
confidence = ("HIGH"        if (score >= 80 or score <= 20) else
              "MEDIUM-HIGH" if (score >= 70 or score <= 30) else "MEDIUM")


# ══════════════════════════════════════════════════════════════════════════════
#  COMPACT OUTPUT — all signal, no noise
# ══════════════════════════════════════════════════════════════════════════════
sep = '=' * 65
print(f"\n{sep}")
print(f"  INSTITUTIONAL ANALYSIS: ${TICKER}")
print(f"{sep}")

# Ownership + concentration + 13F date
filing_str = f" | 13F: {filing_date}" if filing_date else ""
print(f"  OWNERSHIP:  Inst {inst_float_pct:.1f}% float | Insider {insider_pct:.1f}% | {inst_count:,} funds | Top3 {top3_pct:.0f}% ({conc_label}){filing_str}")

# Big 3
b3 = [h for h in holders if h.is_big3]
if b3:
    b3_parts = []
    for h in b3:
        icon  = "[+]" if h.change > 0 else "[-]"
        label = "NEW" if h.direction == "NEW POSITION" else f"{h.change*100:+.1f}%"
        b3_parts.append(f"{icon} {h.name.split()[0]} {label} ({h.pct*100:.1f}%)")
    print(f"  BIG 3:      {' | '.join(b3_parts)}")

# Notable funds — only significant movers
notable_sig = [h for h in holders if h.is_notable and not h.is_big3 and abs(h.change) > 0.03][:5]
if notable_sig:
    n_parts = []
    for h in notable_sig:
        label = "NEW" if h.direction == "NEW POSITION" else f"{h.change*100:+.0f}%"
        n_parts.append(f"{h.name.split()[0]} {label}")
    print(f"  NOTABLE:    {' | '.join(n_parts)}")

# Activist
if activists:
    for h in activists:
        icon  = "[!]" if h.change > 0 else "[X]"
        label = "NEW POSITION — CATALYST" if h.direction == "NEW POSITION" else h.direction
        print(f"  ACTIVIST:   {icon} {h.name} {label} ({h.pct*100:.1f}%)")

# Insider ownership
insider_lbl = ("owner-operator" if insider_pct > 10 else
               "strong" if insider_pct > 5 else
               "adequate" if insider_pct > 1 else "low")
print(f"  INSIDERS:   {insider_pct:.1f}% held ({insider_lbl})")

# Short interest
mom_str = ""
if short_mom:
    mom_label = "RISING" if short_mom > 10 else ("FALLING" if short_mom < -10 else "stable")
    mom_str   = f" | MoM {short_mom:+.1f}% ({mom_label})"
squeeze_str = " | ** SHORT SQUEEZE POTENTIAL **" if squeeze_flag else ""
print(f"  SHORT:      {short_pct:.1f}% float | DTC {short_ratio:.1f}d{mom_str}{squeeze_str}")

# Trend + weighted flow
print(f"  TREND:      {increasing}/{total} ADDING | {decreasing}/{total} REDUCING | {trend} | Flow: {flow_label}")

print()
print(f"{sep}")
print(f"  SCORE:  {score}/100  {signal}  |  Confidence: {confidence}")
print(f"{sep}")
print(f"@@RESULT@@{json.dumps({'score': score, 'signal': signal, 'confidence': confidence})}")
