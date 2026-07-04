#!/usr/bin/env python3
"""
Analyst Ratings Analyzer - Agent 3
Architecture: CODE fetches + analyzes -> AI just summarizes.
"""
from __future__ import annotations

import sys
import math
import time
import concurrent.futures
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

from models import AnalystAction

# Windows cp1255 fix
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import yfinance as yf

_args   = [a for a in sys.argv[1:] if not a.startswith('--')]
TICKER  = _args[0].upper().replace('$', '') if _args else 'NFLX'
VERBOSE = '--verbose' in sys.argv or '-v' in sys.argv

# ── Tier 1 firms — their calls move stocks ───────────────────────
TIER_1 = [
    'goldman', 'morgan stanley', 'jpmorgan', 'jp morgan', 'j.p. morgan',
    'bank of america', 'b of a', 'bofa', 'citigroup', 'citi',
    'ubs', 'barclays', 'deutsche bank', 'credit suisse', 'hsbc',
    'jefferies', 'wells fargo', 'rbc capital',
]

def is_tier1(firm: str) -> bool:    return any(t in firm.lower() for t in TIER_1)

def safe_float(val, default: float = 0.0) -> float:
    if val is None: return default
    try:
        f = float(val)
        return default if math.isnan(f) else f
    except (TypeError, ValueError):
        return default


# ══════════════════════════════════════════════════════════════════
#  PARALLEL FETCH — all 5 yfinance calls simultaneously
# ══════════════════════════════════════════════════════════════════
_t0 = time.time()
print(f"Fetching data for ${TICKER}...", end=' ', flush=True)

with concurrent.futures.ThreadPoolExecutor(max_workers=5) as _ex:
    _f1 = _ex.submit(lambda: yf.Ticker(TICKER).info or {})
    _f2 = _ex.submit(lambda: yf.Ticker(TICKER).recommendations_summary)
    _f3 = _ex.submit(lambda: yf.Ticker(TICKER).analyst_price_targets)
    _f4 = _ex.submit(lambda: yf.Ticker(TICKER).upgrades_downgrades)
    _f5 = _ex.submit(lambda: yf.Ticker(TICKER).eps_trend)
    info         = _f1.result()
    rec_summary  = _f2.result()
    targets      = _f3.result()
    upgrades     = _f4.result()
    eps_trend_df = _f5.result()

print(f"{time.time() - _t0:.1f}s")

current_price = safe_float(info.get('currentPrice') or info.get('regularMarketPrice'), 0)


# ══════════════════════════════════════════════════════════════════
#  PROCESS DATA
# ══════════════════════════════════════════════════════════════════

# ── Consensus ─────────────────────────────────────────────────────
strong_buy = buy = hold = sell = strong_sell = 0
total_analysts = 0

if rec_summary is not None and not rec_summary.empty:
    latest      = rec_summary.iloc[0]
    strong_buy  = int(latest.get('strongBuy', 0))
    buy         = int(latest.get('buy', 0))
    hold        = int(latest.get('hold', 0))
    sell        = int(latest.get('sell', 0))
    strong_sell = int(latest.get('strongSell', 0))
    total_analysts = strong_buy + buy + hold + sell + strong_sell

buy_ratio = sell_ratio = 0.0
if total_analysts > 0:
    buy_ratio  = (strong_buy + buy) / total_analysts
    sell_ratio = (sell + strong_sell) / total_analysts
    if buy_ratio >= 0.7:     consensus = "STRONG BUY"
    elif buy_ratio >= 0.5:   consensus = "MODERATE BUY"
    elif sell_ratio >= 0.5:  consensus = "SELL"
    elif sell_ratio >= 0.3:  consensus = "MODERATE SELL"
    else:                    consensus = "HOLD"
else:
    consensus = "NO DATA"

# ── Price targets ─────────────────────────────────────────────────
pt_low = pt_high = pt_mean = pt_median = upside = upside_median = spread_ratio = 0.0

if targets:
    pt_low    = safe_float(targets.get('low'))
    pt_high   = safe_float(targets.get('high'))
    pt_mean   = safe_float(targets.get('mean'))
    pt_median = safe_float(targets.get('median'))
    if current_price > 0 and pt_mean > 0:
        upside        = (pt_mean - current_price) / current_price * 100
        upside_median = (pt_median - current_price) / current_price * 100
    if pt_low > 0:
        spread_ratio = pt_high / pt_low

# ── Recent analyst actions (90 days) ──────────────────────────────
cutoff = datetime.now() - timedelta(days=90)

upgrades_count = downgrades_count = pt_raises = pt_lowers = pt_maintains = initiations = 0
recent_actions: list[AnalystAction] = []

if upgrades is not None and not upgrades.empty:
    for date_idx, row in upgrades.iterrows():
        try:
            if hasattr(date_idx, 'to_pydatetime'):
                action_date = date_idx.to_pydatetime().replace(tzinfo=None)
            else:
                action_date = datetime.strptime(str(date_idx)[:19], '%Y-%m-%d %H:%M:%S')
        except Exception:
            continue

        if action_date < cutoff:
            continue

        firm       = row.get('Firm', 'Unknown')
        to_grade   = row.get('ToGrade', '')
        from_grade = row.get('FromGrade', '')
        action     = row.get('Action', '')
        pt_action  = row.get('priceTargetAction', '')
        current_pt = safe_float(row.get('currentPriceTarget'))
        prior_pt   = safe_float(row.get('priorPriceTarget'))

        if action == 'up':     upgrades_count += 1
        elif action == 'down': downgrades_count += 1
        elif action == 'init': initiations += 1

        if pt_action == 'Raises':      pt_raises += 1
        elif pt_action == 'Lowers':    pt_lowers += 1
        elif pt_action == 'Maintains': pt_maintains += 1

        grade_str = to_grade
        if action == 'up':   grade_str = f"{from_grade}->{to_grade} (UPGRADE)"
        elif action == 'down': grade_str = f"{from_grade}->{to_grade} (DOWNGRADE)"
        elif action == 'init': grade_str = f"{to_grade} (NEW COVERAGE)"

        pt_str = ""
        if current_pt > 0:
            if prior_pt > 0 and prior_pt != current_pt:
                pt_str = f" | PT: ${current_pt:.0f} (was ${prior_pt:.0f})"
            else:
                pt_str = f" | PT: ${current_pt:.0f}"

        recent_actions.append(AnalystAction(
            date=action_date.strftime('%Y-%m-%d'),
            firm=firm,
            grade_str=grade_str,
            pt_str=pt_str,
            action=action,
            pt_action=pt_action,
            current_pt=current_pt,
            prior_pt=prior_pt,
            to_grade=to_grade,
            from_grade=from_grade,
            is_tier1=is_tier1(firm),
        ))

# ── PT trend ──────────────────────────────────────────────────────
pt_direction = "STABLE"
if pt_raises + pt_lowers > 0:
    raise_ratio = pt_raises / (pt_raises + pt_lowers)
    if raise_ratio >= 0.7:   pt_direction = "RISING"
    elif raise_ratio <= 0.3: pt_direction = "FALLING"
    else:                    pt_direction = "MIXED"

upgrade_direction = "STABLE"
if upgrades_count + downgrades_count > 0:
    up_ratio = upgrades_count / (upgrades_count + downgrades_count)
    if up_ratio >= 0.7:   upgrade_direction = "IMPROVING"
    elif up_ratio <= 0.3: upgrade_direction = "DETERIORATING"
    else:                 upgrade_direction = "MIXED"

# ── Weighted PT change magnitude ──────────────────────────────────
pt_changes_pct = []
for a in recent_actions:
    if a.prior_pt > 0 and a.current_pt > 0 and a.current_pt != a.prior_pt:
        pt_changes_pct.append((a.current_pt - a.prior_pt) / a.prior_pt * 100)
avg_pt_change = sum(pt_changes_pct) / len(pt_changes_pct) if pt_changes_pct else 0

# ── Consensus vs PT divergence ────────────────────────────────────
divergence = None
if buy_ratio >= 0.7 and pt_direction == "FALLING":
    divergence = "STRONG BUY consensus but PTs FALLING — analysts losing conviction quietly"
elif buy_ratio >= 0.5 and pt_direction == "FALLING":
    divergence = "BUY-leaning consensus but PTs FALLING — conviction weakening"
elif sell_ratio >= 0.4 and pt_direction == "RISING":
    divergence = "SELL-heavy consensus but PTs RISING — potential reversal brewing"

# ── Tier 1 highlights ─────────────────────────────────────────────
tier1_upgrades = [a for a in recent_actions if a.is_tier1 and a.action in ('up', 'down')]
tier1_pt_moves = sorted(
    [a for a in recent_actions if a.is_tier1 and a.prior_pt > 0 and a.current_pt > 0 and a.current_pt != a.prior_pt],
    key=lambda a: abs(a.current_pt - a.prior_pt) / a.prior_pt,
    reverse=True
)
tier1_show = tier1_upgrades[:2] + [a for a in tier1_pt_moves if a not in tier1_upgrades][:3]

# ── NEW: EPS estimate revisions — the most predictive analyst signal ─────────
# Stocks follow where earnings estimates go. Rising = demand building; Falling = trouble brewing.
rev_cq_current = rev_cq_30d = None
rev_pct = 0.0
rev_direction = "N/A"

if eps_trend_df is not None and not eps_trend_df.empty:
    try:
        idx  = [str(i).lower() for i in eps_trend_df.index]
        cols = [str(c).lower() for c in eps_trend_df.columns]

        # Find current quarter row (0q) and 30daysAgo column
        cq_pos   = next((i for i, v in enumerate(idx) if '0q' in v), None)
        curr_pos = next((i for i, v in enumerate(cols) if v == 'current'), None)
        d30_pos  = next((i for i, v in enumerate(cols) if '30' in v), None)

        if cq_pos is not None and curr_pos is not None and d30_pos is not None:
            row = eps_trend_df.iloc[cq_pos]
            rev_cq_current = safe_float(row.iloc[curr_pos])
            rev_cq_30d     = safe_float(row.iloc[d30_pos])

            if rev_cq_30d != 0 and rev_cq_current != 0:
                rev_pct = (rev_cq_current - rev_cq_30d) / abs(rev_cq_30d) * 100
                if rev_pct > 5:      rev_direction = "RISING"
                elif rev_pct > 1:    rev_direction = "TICKING UP"
                elif rev_pct < -5:   rev_direction = "FALLING"
                elif rev_pct < -1:   rev_direction = "TICKING DOWN"
                else:                rev_direction = "STABLE"
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════
#  VERBOSE OUTPUT (--verbose only)
# ══════════════════════════════════════════════════════════════════
if VERBOSE:
    sep = '=' * 65
    print(f"\n{sep}")
    print(f"  ANALYST ANALYSIS: ${TICKER} [VERBOSE]")
    print(f"{sep}")

    print(f"\n--- CONSENSUS ---")
    print(f"  Strong Buy: {strong_buy} | Buy: {buy} | Hold: {hold} | Sell: {sell} | Strong Sell: {strong_sell}")
    print(f"  Total: {total_analysts} | Consensus: {consensus} ({buy_ratio*100:.0f}% buy)")

    print(f"\n--- PRICE TARGETS ---")
    print(f"  Current: ${current_price:.2f}")
    print(f"  Low: ${pt_low:.2f} | Mean: ${pt_mean:.2f} | Median: ${pt_median:.2f} | High: ${pt_high:.2f}")
    if upside:        print(f"  Upside (mean): {upside:+.1f}% | Upside (median): {upside_median:+.1f}%")
    if spread_ratio:  print(f"  Spread (H/L): {spread_ratio:.1f}x (${pt_low:.0f} to ${pt_high:.0f})")

    print(f"\n--- RECENT ACTIONS (90 days) ---")
    for a in recent_actions[:12]:
        t1 = " [T1]" if a.is_tier1 else ""
        print(f"  {a.date} | {a.firm:20s} | {a.grade_str}{a.pt_str}{t1}")
    print(f"\n  Upgrades: {upgrades_count} | Downgrades: {downgrades_count} | Initiations: {initiations}")
    print(f"  PT Raises: {pt_raises} | PT Lowers: {pt_lowers} | PT Maintains: {pt_maintains}")

    print(f"\n--- TREND ---")
    print(f"  PT Direction: {pt_direction} | Rating Trend: {upgrade_direction}")
    if avg_pt_change: print(f"  Avg PT Change: {avg_pt_change:+.1f}%")
    if divergence:    print(f"  DIVERGENCE: {divergence}")

    print(f"\n--- EPS ESTIMATE REVISIONS ---")
    if rev_cq_current is not None and rev_cq_30d is not None:
        print(f"  Current Quarter: ${rev_cq_current:.2f} (was ${rev_cq_30d:.2f} 30d ago | {rev_pct:+.1f}% | {rev_direction})")
    else:
        print(f"  No revision data available")


# ══════════════════════════════════════════════════════════════════
#  SCORING
# ══════════════════════════════════════════════════════════════════
score = 50.0

# 1. Consensus strength (-20 to +20)
if total_analysts > 0:
    score += (buy_ratio - 0.5) * 40

# 2. Upside to mean target (-10 to +15)
if upside > 30:      score += 15
elif upside > 20:    score += 10
elif upside > 10:    score += 5
elif upside > 0:     score += 2
elif upside < -10:   score -= 10
elif upside < -5:    score -= 5
elif upside < 0:     score -= 2

# 3. Target spread / uncertainty (0 to -10)
if spread_ratio > 4:   score -= 10
elif spread_ratio > 3: score -= 7
elif spread_ratio > 2: score -= 4

# 4. Analyst coverage
if total_analysts >= 20:   score += 5
elif total_analysts >= 10: score += 3
elif total_analysts >= 5:  score += 1
elif total_analysts < 3:   score -= 5

# 5. PT trend (-8 to +8)
if pt_direction == "RISING":    score += 8
elif pt_direction == "FALLING": score -= 8
elif pt_direction == "MIXED":   score -= 2

# 6. Upgrade/downgrade momentum (-6 to +6)
if upgrade_direction == "IMPROVING":       score += 6
elif upgrade_direction == "DETERIORATING": score -= 6

# 7. PT change magnitude (-7 to +5)
if avg_pt_change > 10:    score += 5
elif avg_pt_change > 5:   score += 3
elif avg_pt_change < -15: score -= 7
elif avg_pt_change < -10: score -= 5
elif avg_pt_change < -5:  score -= 3

# 8. Tier 1 firm actions (+3 / -3 each)
for a in recent_actions:
    if a.is_tier1:
        if a.action == 'up':   score += 3
        elif a.action == 'down': score -= 3

# 9. Divergence penalty (-6 / +4)
if divergence and "FALLING" in divergence:
    score -= 6
elif divergence and "RISING" in divergence:
    score += 4

# 10. NEW: EPS estimate revisions — the most predictive signal
# Stocks follow estimates. Analysts raising next-quarter EPS = demand building.
if rev_direction == "RISING":        score += 8
elif rev_direction == "TICKING UP":  score += 4
elif rev_direction == "FALLING":     score -= 8
elif rev_direction == "TICKING DOWN": score -= 4

score      = max(0, min(100, round(score)))
signal     = "BULLISH" if score >= 70 else ("NEUTRAL" if score >= 45 else "BEARISH")
confidence = ("HIGH"        if (score >= 80 or score <= 20) else
              "MEDIUM-HIGH" if (score >= 70 or score <= 30) else "MEDIUM")


# ══════════════════════════════════════════════════════════════════
#  COMPACT OUTPUT
# ══════════════════════════════════════════════════════════════════
sep = '=' * 65
print(f"\n{sep}")
print(f"  ANALYST ANALYSIS: ${TICKER}")
print(f"{sep}")

# Consensus
buy_total  = strong_buy + buy
sell_total = sell + strong_sell
print(f"  CONSENSUS:  {buy_total} Buy ({strong_buy} Strong) | {hold} Hold | {sell_total} Sell | {consensus} ({buy_ratio*100:.0f}%)")

# Targets
if pt_mean > 0:
    print(f"  TARGETS:    Mean ${pt_mean:.0f} ({upside:+.1f}%) | Median ${pt_median:.0f} ({upside_median:+.1f}%) | Range ${pt_low:.0f}-${pt_high:.0f} ({spread_ratio:.1f}x spread)")

# PT trend + magnitude
pt_parts = [f"{pt_raises} raises / {pt_lowers} lowers", pt_direction]
if avg_pt_change: pt_parts.append(f"Avg {avg_pt_change:+.1f}%")
print(f"  PT TREND:   {' | '.join(pt_parts)}")

# EPS revisions
if rev_cq_current is not None and rev_cq_30d is not None and rev_cq_30d != 0:
    print(f"  REVISIONS:  CQ EPS ${rev_cq_current:.2f} (was ${rev_cq_30d:.2f} 30d ago, {rev_pct:+.1f}%) | {rev_direction}")

# Actions
print(f"  ACTIONS:    {upgrades_count} upgrades | {downgrades_count} downgrades | {initiations} initiations (90d) | {upgrade_direction}")

# Tier 1 highlights
if tier1_show:
    t1_parts = []
    for a in tier1_show[:4]:
        name = a.firm.split()[0]
        if a.action in ('up', 'down'):
            t1_parts.append(f"{name}: {a.from_grade}->{a.to_grade}{a.pt_str}")
        elif a.current_pt > 0 and a.prior_pt > 0:
            chg = (a.current_pt - a.prior_pt) / a.prior_pt * 100
            t1_parts.append(f"{name}: PT ${a.current_pt:.0f} ({chg:+.0f}%)")
        elif a.current_pt > 0:
            t1_parts.append(f"{name}: {a.to_grade} PT ${a.current_pt:.0f}")
    if t1_parts:
        print(f"  TIER 1:     {' | '.join(t1_parts)}")

# Divergence
if divergence:
    print(f"  DIVERGENCE: [!] {divergence}")

print()
print(f"{sep}")
print(f"  SCORE:  {score}/100  {signal}  |  Confidence: {confidence}")
print(f"{sep}")
