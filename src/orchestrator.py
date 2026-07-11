#!/usr/bin/env python3
"""
Stock Analysis Orchestrator — runs all 4 agents in parallel, combines scores.
Usage: python src/orchestrator.py NFLX
       python src/orchestrator.py SHOP --verbose
"""
from __future__ import annotations

import sys
import os
import re
import json
import time
import subprocess
import concurrent.futures
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from models import AgentResult

import warnings
warnings.filterwarnings('ignore')
import yfinance as yf

# Windows cp1255 fix
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

_args   = [a for a in sys.argv[1:] if not a.startswith('--')]
TICKER  = _args[0].upper().replace('$', '') if _args else 'NFLX'
VERBOSE = '--verbose' in sys.argv or '-v' in sys.argv

SCRIPTS_DIR  = Path(__file__).parent
HISTORY_FILE = SCRIPTS_DIR.parent / 'memory' / 'score_history.json'

# ── Agent definitions (base weights — overridden by adaptive profile) ─────────
AGENTS = [
    {'name': 'Fundamentals', 'script': 'analyzers/fundamental.py'},
    {'name': 'Institutional', 'script': 'analyzers/institutional.py'},
    {'name': 'Analyst',       'script': 'analyzers/analyst.py'},
    {'name': 'Trend',         'script': 'analyzers/trend.py'},
]

# ── Adaptive weight profiles per sector/company type ─────────────────────────
# Why adaptive? A biotech without earnings is judged differently than a mature bank.
WEIGHT_PROFILES = {
    'software':    {'Fundamentals': 0.40, 'Institutional': 0.20, 'Analyst': 0.25, 'Trend': 0.15},
    'semi':        {'Fundamentals': 0.40, 'Institutional': 0.20, 'Analyst': 0.25, 'Trend': 0.15},
    'healthcare':  {'Fundamentals': 0.30, 'Institutional': 0.20, 'Analyst': 0.35, 'Trend': 0.15},
    'bank':        {'Fundamentals': 0.50, 'Institutional': 0.25, 'Analyst': 0.15, 'Trend': 0.10},
    'retail':      {'Fundamentals': 0.45, 'Institutional': 0.20, 'Analyst': 0.20, 'Trend': 0.15},
    'energy':      {'Fundamentals': 0.45, 'Institutional': 0.20, 'Analyst': 0.20, 'Trend': 0.15},
}
DEFAULT_WEIGHTS = {'Fundamentals': 0.45, 'Institutional': 0.20, 'Analyst': 0.20, 'Trend': 0.15}


# ── Macro regime gate — VIX + SPY trend, checked before any single stock ──
# Iron rule: macro first. A great stock score means less in a fear tape.
def fetch_macro() -> dict:
    macro = {'vix': None, 'spy_trend': 'UNKNOWN', 'regime': 'NEUTRAL', 'adj': 0}

    try:
        vix_hist = yf.Ticker('^VIX').history(period='5d')
        if not vix_hist.empty:
            macro['vix'] = float(vix_hist['Close'].iloc[-1])
    except Exception:
        pass

    try:
        spy_hist = yf.Ticker('SPY').history(period='250d')
        if len(spy_hist) >= 200:
            price  = float(spy_hist['Close'].iloc[-1])
            sma50  = float(spy_hist['Close'].rolling(50).mean().iloc[-1])
            sma200 = float(spy_hist['Close'].rolling(200).mean().iloc[-1])
            if price > sma50 > sma200:
                macro['spy_trend'] = 'UPTREND'
            elif price < sma50 < sma200:
                macro['spy_trend'] = 'DOWNTREND'
            else:
                macro['spy_trend'] = 'MIXED'
    except Exception:
        pass

    vix, trend = macro['vix'], macro['spy_trend']
    if trend == 'DOWNTREND' or (vix is not None and vix >= 25):
        macro['regime'], macro['adj'] = 'RISK-OFF', -8
    elif vix is not None and vix >= 20:
        macro['regime'], macro['adj'] = 'CAUTION', -3
    elif trend == 'UPTREND' and vix is not None and vix < 16:
        macro['regime'], macro['adj'] = 'RISK-ON', 5
    else:
        macro['regime'], macro['adj'] = 'NEUTRAL', 0

    return macro


def load_history() -> dict:
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_history(history: dict, ticker: str, score: int, signal: str) -> None:
    entry = {'date': datetime.now().strftime('%Y-%m-%d'), 'score': score, 'signal': signal}
    if ticker not in history:
        history[ticker] = []
    # Avoid duplicate same-day entries — replace if same date
    if history[ticker] and history[ticker][-1]['date'] == entry['date']:
        history[ticker][-1] = entry
    else:
        history[ticker].append(entry)
    history[ticker] = history[ticker][-20:]  # keep last 20 runs
    try:
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(HISTORY_FILE, 'w') as f:
            json.dump(history, f, indent=2)
    except Exception:
        pass


def run_agent(agent: dict, ticker: str, verbose: bool) -> AgentResult:
    script_path = SCRIPTS_DIR / agent['script']
    cmd = [sys.executable, str(script_path), ticker]
    if verbose:
        cmd.append('--verbose')

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30,
            encoding='utf-8', errors='replace'
        )
        output = result.stdout or ''
        stderr = result.stderr or ''
    except subprocess.TimeoutExpired:
        return AgentResult(name=agent['name'], script=agent['script'],
                           output='', score=None, signal='TIMEOUT',
                           error='Timed out after 30s')
    except Exception as e:
        return AgentResult(name=agent['name'], script=agent['script'],
                           output='', score=None, signal='ERROR',
                           error=str(e))

    score = None
    signal = 'UNKNOWN'
    marker = re.search(r'@@RESULT@@(\{.*\})', output)
    if marker:
        try:
            parsed = json.loads(marker.group(1))
            score  = int(parsed['score'])
            signal = parsed['signal']
        except (json.JSONDecodeError, KeyError, ValueError, TypeError):
            marker = None
    if not marker:
        match = re.search(r'SCORE:\s+(\d+)/100\s+(\w+)', output)
        if match:
            score  = int(match.group(1))
            signal = match.group(2)

    return AgentResult(
        name=agent['name'], script=agent['script'],
        output=output, score=score, signal=signal,
        error=stderr if result.returncode != 0 else None,
    )


def extract_field(output: str, pattern: str, default: str = '') -> str:
    m = re.search(pattern, output)
    return m.group(1).strip() if m else default


def build_story(results: list[AgentResult], ticker: str, final_score: int,
                final_signal: str, weight_profile: dict, bench_key: str) -> list[str]:
    fund_out  = next((r.output for r in results if r.name == 'Fundamentals'), '')
    inst_out  = next((r.output for r in results if r.name == 'Institutional'), '')
    anlst_out = next((r.output for r in results if r.name == 'Analyst'), '')
    trend_out = next((r.output for r in results if r.name == 'Trend'), '')

    # ── Extract data points ───────────────────────────────────────
    quality_match = re.search(r'Quality\s+(\d+)/100', fund_out)
    quality = int(quality_match.group(1)) if quality_match else None

    roic      = extract_field(fund_out, r'ROIC\s+\*?([\d.]+%)')
    fcf       = extract_field(fund_out, r'FCF\s+(\$[\d.]+[BM])')
    gm_trend  = extract_field(fund_out, r'GM\s+[\d.]+%\s+\(([^)]+)\)')
    peg       = extract_field(fund_out, r'PEG\s+([\d.]+)')
    red_flags = extract_field(fund_out, r'RED FLAGS:\s+(.+)')
    moat      = extract_field(fund_out, r'MOAT:\s+(\S+\s+MOAT)')

    inst_trend_match = re.search(r'TREND:\s+(\d+)/(\d+)\s+ADDING\s+\|\s+(\d+)/\d+\s+REDUCING', inst_out)
    inst_adding  = int(inst_trend_match.group(1)) if inst_trend_match else 0
    inst_total   = int(inst_trend_match.group(2)) if inst_trend_match else 0
    inst_reducing = int(inst_trend_match.group(3)) if inst_trend_match else 0

    short_info   = extract_field(inst_out, r'SHORT:\s+([^|]+)')
    consensus    = extract_field(anlst_out, r'CONSENSUS:.*?(\S+\s+\S+)\s+\(\d+%\)')
    upside       = extract_field(anlst_out, r'Mean\s+\$[\d,]+\s+\(([^)]+)\)')
    divergence   = extract_field(anlst_out, r'DIVERGENCE:\s+\[!\]\s+(.+)')
    pt_direction = extract_field(anlst_out, r'PT TREND:.*?\|\s+(\S+)')

    # EPS revision direction (new)
    rev_dir_match = re.search(r'REVISIONS:.*?\|\s+(RISING|FALLING|TICKING UP|TICKING DOWN|STABLE)', anlst_out)
    rev_dir = rev_dir_match.group(1) if rev_dir_match else ''

    sector_rank  = extract_field(trend_out, r'#(\d+)/11')
    sector_name  = extract_field(trend_out, r'SECTOR:\s+([^#]+?)\s+#')
    rotation     = extract_field(trend_out, r'ROTATION:.*?\|\s+(\S+(?:\s+\S+)?)\s*$')
    alpha_quality = extract_field(trend_out, r'STOCK:.*?\|\s+(.+)')

    # ── Sentence 1: Company quality ──────────────────────────────
    if quality and quality >= 80:
        s1 = f"${ticker} is a high-quality company"
        details = []
        if roic: details.append(f"ROIC {roic}")
        if fcf:  details.append(f"FCF {fcf}")
        if moat: details.append(moat.lower())
        if details: s1 += f" ({', '.join(details)})"
    elif quality and quality >= 60:
        s1 = f"${ticker} has solid fundamentals"
        if roic: s1 += f" (ROIC {roic})"
    else:
        s1 = f"${ticker} has mixed fundamentals"
        if roic: s1 += f" (ROIC {roic})"

    try:
        peg_val = float(peg) if peg else None
        if peg_val and peg_val < 0.5:      s1 += ", trading at a deep discount on PEG"
        elif peg_val and peg_val < 1.0:    s1 += ", attractively valued on PEG"
        elif peg_val and peg_val > 3.0:    s1 += ", but valuation is stretched"
    except ValueError:
        pass

    if gm_trend and '+' in gm_trend:     s1 += ", with margins improving"
    elif gm_trend and '-' in gm_trend:   s1 += ", but margins are compressing"
    s1 += '.'

    # ── Sentence 2: Smart money + analyst + EPS revisions ────────
    s2_parts = []
    if inst_adding > inst_reducing:
        s2_parts.append(f"smart money is accumulating ({inst_adding}/{inst_total} adding)")
    elif inst_reducing > inst_adding:
        s2_parts.append(f"smart money is distributing ({inst_reducing}/{inst_total} reducing)")
    else:
        s2_parts.append("smart money is mixed")

    if 'STRONG BUY' in consensus.upper():
        if divergence:
            s2_parts.append(f"analysts rate Strong Buy but {pt_direction.lower() if pt_direction else 'cutting'} price targets")
        else:
            s2_parts.append(f"analysts rate Strong Buy with {upside} upside" if upside else "analysts rate Strong Buy")
    elif 'BUY' in consensus.upper():
        s2_parts.append(f"analysts lean Buy ({upside} upside)" if upside else "analysts lean Buy")
    elif 'SELL' in consensus.upper():
        s2_parts.append("analysts are bearish")

    if rev_dir in ('RISING', 'TICKING UP'):
        s2_parts.append("EPS estimates being revised higher")
    elif rev_dir in ('FALLING', 'TICKING DOWN'):
        s2_parts.append("EPS estimates being cut — watch this")

    s2 = ', and '.join(s2_parts) + '.' if s2_parts else ''

    # ── Sentence 3: Environment ───────────────────────────────────
    s3_parts = []
    if sector_rank:
        rank = int(sector_rank)
        if rank <= 3:
            s3_parts.append(f"{sector_name.strip()} sector is leading (#{rank}/11)")
        elif rank >= 9:
            s3_parts.append(f"the environment is fighting it — {sector_name.strip()} sector ranks #{rank}/11")
        else:
            s3_parts.append(f"{sector_name.strip()} sector sits mid-pack (#{rank}/11)")

    if 'RISK-OFF' in rotation:
        s3_parts.append("money is rotating into defensives")
    elif 'RISK-ON' in rotation:
        s3_parts.append("money is flowing into offensive sectors")

    if short_info:
        sp_match = re.search(r'([\d.]+)%', short_info)
        if sp_match:
            sp = float(sp_match.group(1))
            if sp > 15:   s3_parts.append(f"shorts are heavily positioned ({sp:.1f}%)")
            elif sp > 8:  s3_parts.append(f"short interest is elevated ({sp:.1f}%)")

    s3 = ('However, ' + ', and '.join(s3_parts) + '.') if s3_parts else ''

    # ── Sentence 4: Verdict ───────────────────────────────────────
    if final_signal == 'BULLISH':
        if final_score >= 80:
            s4 = f"The {final_score} score reflects strong conviction across all dimensions."
        else:
            s4 = f"The {final_score} score leans bullish — fundamentals outweigh the headwinds."
    elif final_signal == 'BEARISH':
        if final_score <= 30:
            s4 = f"The {final_score} score is a clear warning — multiple red flags across agents."
        else:
            s4 = f"The {final_score} score leans bearish — the risks outweigh the positives right now."
    else:
        if red_flags and red_flags.strip() not in ('None', ''):
            s4 = f"The {final_score} score sits on the fence — quality is there but watch for: {red_flags.split('.')[0].strip()}."
        elif divergence:
            s4 = f"The {final_score} score sits on the fence — the divergence between analyst words and actions deserves attention."
        else:
            s4 = f"The {final_score} score sits on the fence — not enough conviction in either direction yet."

    # ── Combine + wrap at 75 chars ────────────────────────────────
    story = s1
    if s2: story += ' ' + (s2[0].upper() + s2[1:])
    if s3: story += ' ' + s3
    story += ' ' + s4

    words = story.split()
    lines, current = [], ''
    for w in words:
        if len(current) + len(w) + 1 > 75:
            lines.append(current)
            current = w
        else:
            current = (current + ' ' + w).strip()
    if current:
        lines.append(current)
    return lines


# ══════════════════════════════════════════════════════════════════
#  LOAD HISTORY
# ══════════════════════════════════════════════════════════════════
history    = load_history()
prev_runs  = history.get(TICKER, [])
prev_entry = None
# Find last run that isn't today
today = datetime.now().strftime('%Y-%m-%d')
for run in reversed(prev_runs):
    if run['date'] != today:
        prev_entry = run
        break


# ══════════════════════════════════════════════════════════════════
#  MACRO FIRST — VIX + SPY trend, before we even look at the stock
# ══════════════════════════════════════════════════════════════════
macro = fetch_macro()
vix_str = f"{macro['vix']:.1f}" if macro['vix'] is not None else "N/A"
print(f"MACRO:  VIX {vix_str} | SPY {macro['spy_trend']} -> {macro['regime']} "
      f"(adj {macro['adj']:+d})\n")


# ══════════════════════════════════════════════════════════════════
#  RUN ALL AGENTS IN PARALLEL
# ══════════════════════════════════════════════════════════════════
_t0 = time.time()
print(f"Running 4 agents on ${TICKER}...", flush=True)

with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
    futures = {ex.submit(run_agent, agent, TICKER, VERBOSE): agent for agent in AGENTS}
    results: list[AgentResult] = []
    for future in concurrent.futures.as_completed(futures):
        results.append(future.result())

agent_order = {a['script']: i for i, a in enumerate(AGENTS)}
results.sort(key=lambda r: agent_order.get(r.script, 99))

elapsed = time.time() - _t0
print(f"All agents done in {elapsed:.1f}s\n")


# ══════════════════════════════════════════════════════════════════
#  VERBOSE: show each agent's full output
# ══════════════════════════════════════════════════════════════════
if VERBOSE:
    for r in results:
        if r.output:
            print(r.output)
            print()


# ══════════════════════════════════════════════════════════════════
#  ADAPTIVE WEIGHTS — detect company type from Agent 1 output
# ══════════════════════════════════════════════════════════════════
fund_output = next((r.output for r in results if r.name == 'Fundamentals'), '')
bench_match = re.search(r'Benchmark:\s*(\w+)', fund_output)
bench_key   = bench_match.group(1).lower() if bench_match else 'market'
weight_profile = WEIGHT_PROFILES.get(bench_key, DEFAULT_WEIGHTS)


# ══════════════════════════════════════════════════════════════════
#  COMBINE SCORES — weighted average with adaptive weights
# ══════════════════════════════════════════════════════════════════
scored = [r for r in results if r.score is not None]
failed = [r for r in results if r.score is None]

if scored:
    total_weight   = sum(weight_profile.get(r.name, 0.20) for r in scored)
    weighted_score = sum(r.score * weight_profile.get(r.name, 0.20) for r in scored) / total_weight
    raw_score      = round(weighted_score)
else:
    raw_score = 0

# Apply macro regime adjustment — a good stock still scores worse in a bad tape
final_score = max(0, min(100, raw_score + macro['adj']))

# Final signal
if final_score >= 65:   final_signal = "BULLISH"
elif final_score >= 40: final_signal = "NEUTRAL"
else:                   final_signal = "BEARISH"

# Confidence — agent agreement
if scored:
    signals        = [r.signal for r in scored]
    bullish_count  = sum(1 for s in signals if s in ('BULLISH', 'TAILWIND'))
    bearish_count  = sum(1 for s in signals if s in ('BEARISH', 'HEADWIND'))

    if bullish_count == len(scored) or bearish_count == len(scored):
        agreement, confidence = "UNANIMOUS", "HIGH"
    elif bullish_count >= 3 or bearish_count >= 3:
        agreement, confidence = "STRONG", "MEDIUM-HIGH"
    elif bullish_count >= 2 or bearish_count >= 2:
        agreement, confidence = "MAJORITY", "MEDIUM"
    else:
        agreement, confidence = "SPLIT", "LOW"
else:
    agreement, confidence = "NO DATA", "NONE"

# Conflict detection
conflicts = []
if scored:
    score_list = [(r.name, r.score, r.signal) for r in scored]
    max_s = max(s for _, s, _ in score_list)
    min_s = min(s for _, s, _ in score_list)
    if max_s - min_s > 30:
        high = next(name for name, s, _ in score_list if s == max_s)
        low  = next(name for name, s, _ in score_list if s == min_s)
        conflicts.append(f"{high} ({max_s}) vs {low} ({min_s}) — {max_s - min_s}pt spread")

# Earnings-date risk flag — don't get run over the day before a print
earnings_flag = None
earn_match = re.search(r'Next earnings\s+(\d{4}-\d{2}-\d{2})', fund_output, re.IGNORECASE)
if earn_match:
    try:
        earn_date  = datetime.strptime(earn_match.group(1), '%Y-%m-%d')
        days_until = (earn_date - datetime.now()).days
        if 0 <= days_until <= 7:
            earnings_flag = f"EARNINGS in {days_until}d ({earn_match.group(1)}) — HIGH RISK, don't open fresh size into it"
        elif 8 <= days_until <= 14:
            earnings_flag = f"EARNINGS in {days_until}d ({earn_match.group(1)}) — reduce size going in"
    except ValueError:
        pass

# Score delta vs previous run
score_delta = None
if prev_entry:
    score_delta = final_score - prev_entry['score']

# Save to history
save_history(history, TICKER, final_score, final_signal)


# ══════════════════════════════════════════════════════════════════
#  COMPACT OUTPUT
# ══════════════════════════════════════════════════════════════════
sep = '=' * 65

print(sep)
print(f"  COMBINED ANALYSIS: ${TICKER}")
print(sep)

# Weight profile info
wf = weight_profile
print(f"  Profile: {bench_key.upper()} | Fund {int(wf['Fundamentals']*100)}% / Inst {int(wf['Institutional']*100)}% / Anlst {int(wf['Analyst']*100)}% / Trend {int(wf['Trend']*100)}%")
print()

# Per-agent scores
for r in results:
    if r.score is not None:
        w = int(weight_profile.get(r.name, 0.20) * 100)
        print(f"  {r.name:14s}  {r.score:3d}/100  {r.signal:10s}  (weight {w}%)")
    else:
        err = r.error or 'unknown error'
        print(f"  {r.name:14s}  FAILED — {err}")

if conflicts:
    print(f"\n  CONFLICT:    {conflicts[0]}")

if macro['adj'] != 0:
    print(f"\n  MACRO ADJ:   {raw_score} -> {final_score} ({macro['regime']}, {macro['adj']:+d})")

if earnings_flag:
    print(f"\n  EARNINGS:    [!] {earnings_flag}")

if failed:
    print(f"\n  WARNING:     {len(failed)} agent(s) failed: {', '.join(r.name for r in failed)}")

# The Story
story_lines = build_story(results, TICKER, final_score, final_signal, weight_profile, bench_key)
print(f"\n  THE STORY:")
for line in story_lines:
    print(f"  {line}")

# Score history delta
delta_str = ''
if score_delta is not None:
    sign      = '+' if score_delta > 0 else ''
    trend_arr = ' (improving)' if score_delta > 3 else (' (deteriorating)' if score_delta < -3 else ' (stable)')
    delta_str = f"  |  vs {prev_entry['date']}: {sign}{score_delta}{trend_arr}"

print()
print(sep)
print(f"  FINAL SCORE:  {final_score}/100  {final_signal}  |  Confidence: {confidence} ({agreement}){delta_str}")
print(sep)
