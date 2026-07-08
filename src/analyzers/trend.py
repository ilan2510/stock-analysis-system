#!/usr/bin/env python3
"""
Trend & Sector Analyzer - Agent 5 v4
3-pillar scoring: Macro 30% / Theme 40% / Stock Position 30%
+ Trend Phase detection + Peer Relative Strength
Blended returns: 1W 20% / 1M 40% / 3M monthly-normalized 40%
Architecture: CODE fetches + analyzes -> AI summarizes
"""
from __future__ import annotations
import sys, math, time, statistics
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from models import SectorData

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

try:
    import yfinance as yf
except ImportError:
    print("WARNING: yfinance not installed."); sys.exit(1)

_args   = [a for a in sys.argv[1:] if not a.startswith('--')]
TICKER  = _args[0].upper().replace('$', '') if _args else 'NFLX'
VERBOSE = '--verbose' in sys.argv or '-v' in sys.argv

# ═══ MAPS ════════════════════════════════════════════════════════
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

# Industry -> thematic ETF (precise benchmark vs SPDR broad sector)
INDUSTRY_ETF = {
    'Semiconductors': 'SMH', 'Semiconductor Equipment & Materials': 'SMH',
    'Semiconductor Equipment': 'SMH',
    'Software—Application': 'IGV', 'Software - Application': 'IGV',
    'Software—Infrastructure': 'IGV', 'Software - Infrastructure': 'IGV',
    'Information Technology Services': 'IGV',
    'Internet Content & Information': 'FDN', 'Internet Retail': 'FDN',
    'Software—Security': 'CIBR',
    'Financial Services': 'FINX', 'Consumer Finance': 'FINX', 'Credit Services': 'FINX',
    'Banks—Regional': 'KBE', 'Banks—Diversified': 'KBE',
    'Banks - Regional': 'KBE', 'Banks - Diversified': 'KBE',
    'Biotechnology': 'XBI',
    'Drug Manufacturers—General': 'IBB', 'Drug Manufacturers - General': 'IBB',
    'Drug Manufacturers—Specialty & Generic': 'IBB',
    'Aerospace & Defense': 'ITA',
    'Oil & Gas E&P': 'XOP', 'Oil & Gas Integrated': 'XOP',
    'Oil & Gas Refining & Marketing': 'XOP', 'Oil & Gas Equipment & Services': 'XOP',
    'Insurance—Diversified': 'KIE', 'Insurance—Life': 'KIE', 'Insurance - Diversified': 'KIE',
    'REIT—Diversified': 'VNQ', 'REIT—Retail': 'VNQ', 'REIT—Industrial': 'VNQ',
    'Telecom Services': 'IYZ', 'Solar': 'TAN',
}

# Industry -> peer tickers (for relative strength)
INDUSTRY_PEERS = {
    'Semiconductors':                 ['NVDA', 'INTC', 'AVGO', 'QCOM'],
    'Semiconductor Equipment':        ['AMAT', 'LRCX', 'KLAC', 'ASML'],
    'Software—Application':           ['MSFT', 'CRM', 'NOW', 'ADBE'],
    'Software - Application':         ['MSFT', 'CRM', 'NOW', 'ADBE'],
    'Software—Infrastructure':        ['MSFT', 'ORCL', 'IBM', 'SNOW'],
    'Software - Infrastructure':      ['MSFT', 'ORCL', 'IBM', 'SNOW'],
    'Software—Security':              ['CRWD', 'PANW', 'ZS', 'S'],
    'Internet Content & Information': ['GOOGL', 'META', 'SNAP', 'PINS'],
    'Financial Services':             ['SQ', 'PYPL', 'SOFI', 'AFRM'],
    'Consumer Finance':               ['SQ', 'PYPL', 'SOFI', 'AFRM'],
    'Credit Services':                ['V', 'MA', 'AXP'],
    'Banks—Regional':                 ['JPM', 'BAC', 'WFC', 'C'],
    'Banks—Diversified':              ['JPM', 'BAC', 'WFC', 'C'],
    'Banks - Regional':               ['JPM', 'BAC', 'WFC', 'C'],
    'Banks - Diversified':            ['JPM', 'BAC', 'WFC', 'C'],
    'Biotechnology':                  ['MRNA', 'BNTX', 'REGN', 'VRTX'],
    'Drug Manufacturers—General':     ['JNJ', 'PFE', 'ABBV', 'LLY'],
    'Drug Manufacturers - General':   ['JNJ', 'PFE', 'ABBV', 'LLY'],
    'Aerospace & Defense':            ['RTX', 'LMT', 'NOC', 'GD'],
    'Oil & Gas E&P':                  ['XOM', 'CVX', 'COP', 'OXY'],
    'Oil & Gas Integrated':           ['XOM', 'CVX', 'BP'],
}

THEMATIC_ETFS = list(set(INDUSTRY_ETF.values()))


# ═══ HELPERS ═════════════════════════════════════════════════════
def safe_float(val, default=0.0):
    if val is None: return default
    try:
        f = float(val); return default if math.isnan(f) else f
    except: return default

def calc_ret(hist, days):
    if hist is None or hist.empty or len(hist) < 2: return 0.0
    try:
        ep = float(hist['Close'].iloc[-1])
        sp = float(hist['Close'].iloc[-min(days, len(hist)-1)])
        return 0.0 if sp == 0 else (ep - sp) / sp * 100
    except: return 0.0

def get_hist(batch, t):
    try:
        df = batch[t]
        if hasattr(df, 'empty') and not df.empty and 'Close' in df.columns:
            return df.dropna(subset=['Close'])
    except: pass
    return None

def blend(r1w, r1m, r3m):
    """Weighted blend — 1W 20% / 1M 40% / 3M at monthly pace 40%."""
    return r1w * 0.2 + r1m * 0.4 + (r3m / 3.0) * 0.4

def trend_phase(s1w, s1m, s3m, spy_3m):
    """Where is the stock in its trend cycle? — most important trader signal."""
    alpha_3m = s3m - spy_3m
    strong   = s3m > 20 or alpha_3m > 15   # big 3M run vs market
    weak     = s3m < -10 or alpha_3m < -15  # seriously lagging

    # Relative TOPPING: retracement as % of the 3M gain, not fixed threshold
    # 5% drop after 138% gain = 3.5% retrace (nothing). 5% drop after 20% gain = 25% retrace (real).
    retrace_pct = abs(s1m) / s3m * 100 if s3m > 5 and s1m < 0 else 0

    if strong and s1m > 1 and s1w > 0:  return "MOMENTUM",            "all TFs up — strong continuation"
    if strong and retrace_pct > 20:     return "TOPPING",             "retracing >20% of 3M gain — reduce exposure"
    if strong:                          return "PULLBACK IN UPTREND", "3M run intact, short dip — potential buy"
    if not weak and s1m > 5:            return "BREAKOUT",            "momentum accelerating — new trend forming"
    if weak and s1m > 3:                return "RECOVERY",            "bouncing from weakness — watch for follow-through"
    if weak:                            return "DOWNTREND",           "all TFs weak — avoid"
    return                               "CONSOLIDATING",             "mixed signals — no directional edge"


# ═══ FETCH ═══════════════════════════════════════════════════════
_t0 = time.time()
print(f"Fetching ${TICKER}...", end=' ', flush=True)

# Step 1: info first (fast) — need industry to build peer list for one-shot batch
info           = yf.Ticker(TICKER).info or {}
stock_sector   = info.get('sector', 'Unknown')
stock_industry = info.get('industry', 'Unknown')
stock_name     = info.get('shortName', TICKER)
stock_etf      = SECTOR_TO_ETF.get(stock_sector)
thematic_etf   = INDUSTRY_ETF.get(stock_industry)
peers          = [p for p in INDUSTRY_PEERS.get(stock_industry, []) if p != TICKER][:4]

# Step 2: one batch — sector ETFs + thematic ETFs + peers + SPY + VIX + stock
all_tickers = list(dict.fromkeys(
    list(SECTOR_ETFS.keys()) + THEMATIC_ETFS + peers + ['SPY', '^VIX', TICKER]
))
batch = yf.download(all_tickers, period='6mo', interval='1d',
                    progress=False, group_by='ticker')
print(f"{time.time()-_t0:.1f}s")


# ═══ PROCESS ═════════════════════════════════════════════════════

# ── SPY ──────────────────────────────────────────────────────────
spy_h = get_hist(batch, 'SPY')
spy_1w, spy_1m, spy_3m = calc_ret(spy_h,5), calc_ret(spy_h,21), calc_ret(spy_h,63)
spy_blend = blend(spy_1w, spy_1m, spy_3m)

# ── VIX ──────────────────────────────────────────────────────────
vix_h = get_hist(batch, '^VIX')
vix_cur = vix_chg = 0.0
if vix_h is not None and not vix_h.empty:
    vc = vix_h['Close'].dropna()
    if len(vc) >= 2:
        vix_cur = safe_float(vc.iloc[-1])
        v1m     = safe_float(vc.iloc[-min(21, len(vc)-1)])
        vix_chg = (vix_cur - v1m) / v1m * 100 if v1m > 0 else 0.0

vix_lbl = ("LOW" if vix_cur < 15 else "NORMAL" if vix_cur < 20 else
           "ELEVATED" if vix_cur < 25 else "HIGH" if vix_cur < 30 else "EXTREME")
vix_dir = ("SPIKING"   if vix_chg > 15 else "RISING"    if vix_chg > 5 else
           "COLLAPSING" if vix_chg < -15 else "FALLING"  if vix_chg < -5 else "STABLE")
regime  = ("RISK-ON"  if spy_1m > 2 and vix_cur < 20 else
           "RISK-OFF" if spy_1m < -2 or vix_cur > 25 else "NEUTRAL")

# ── Broad sectors ─────────────────────────────────────────────────
sector_data: dict[str, SectorData] = {}
for etf, name in SECTOR_ETFS.items():
    h = get_hist(batch, etf)
    sector_data[etf] = SectorData(name=name,
        ret_1w=calc_ret(h,5), ret_1m=calc_ret(h,21), ret_3m=calc_ret(h,63))

ranked  = sorted(sector_data.items(), key=lambda x: x[1].ret_1m, reverse=True)
leaders = ranked[:3]
sd      = sector_data.get(stock_etf, SectorData(name='Unknown'))
stock_sector_rank = next((i+1 for i,(e,_) in enumerate(ranked) if e == stock_etf), 0)

off_avg = sum(d.ret_1m for e,d in sector_data.items() if e in OFFENSIVE) / len(OFFENSIVE)
def_avg = sum(d.ret_1m for e,d in sector_data.items() if e in DEFENSIVE) / len(DEFENSIVE)
rot_spread = off_avg - def_avg
rotation   = "RISK-ON" if rot_spread > 3 else "RISK-OFF" if rot_spread < -3 else "BALANCED"
breadth    = sum(1 for _,d in sector_data.items() if d.ret_1m > spy_1m)
breadth_lbl = ("BROAD" if breadth >= 8 else "HEALTHY" if breadth >= 5 else
               "NARROW" if breadth >= 3 else "VERY NARROW")

# ── Thematic ETF ──────────────────────────────────────────────────
th_1w = th_1m = th_3m = 0.0
if thematic_etf:
    th_h = get_hist(batch, thematic_etf)
    th_1w, th_1m, th_3m = calc_ret(th_h,5), calc_ret(th_h,21), calc_ret(th_h,63)

# Use thematic if available, else broad sector
ref_1w  = th_1w  if thematic_etf else sd.ret_1w
ref_1m  = th_1m  if thematic_etf else sd.ret_1m
ref_3m  = th_3m  if thematic_etf else sd.ret_3m
ref_lbl = thematic_etf if thematic_etf else (stock_etf or 'sector')
th_blend_vs_spy = blend(ref_1w, ref_1m, ref_3m) - spy_blend

# Theme acceleration: is the weekly pace faster or slower than the monthly?
# Positive = theme recovering/accelerating. Negative = theme still rolling over.
th_weekly_pace = ref_1w * 4  # annualize weekly to monthly comparison
th_accel = th_weekly_pace - ref_1m
th_accel_lbl = ("RECOVERING" if th_accel > 3 and ref_1m < 0 else
                "ACCELERATING" if th_accel > 3 else
                "ROLLING OVER" if th_accel < -3 else "STEADY")

# ── Stock ──────────────────────────────────────────────────────────
stk_h = get_hist(batch, TICKER)
s1w, s1m, s3m = calc_ret(stk_h,5), calc_ret(stk_h,21), calc_ret(stk_h,63)
stk_blend_vs_spy = blend(s1w, s1m, s3m) - spy_blend

# ── Peer relative strength (1M) ───────────────────────────────────
peer_rets = []
for p in peers:
    r = calc_ret(get_hist(batch, p), 21)
    if get_hist(batch, p) is not None:
        peer_rets.append((p, r))

peer_avg    = statistics.mean(r for _,r in peer_rets) if peer_rets else 0.0
vs_peers    = s1m - peer_avg if peer_rets else 0.0
peer_rs     = ("LEADING" if vs_peers > 8 else "AHEAD"   if vs_peers > 2 else
               "IN LINE" if vs_peers > -2 else "LAGGING") if peer_rets else "N/A"
peer_str    = (f"{vs_peers:+.1f}% vs {'/'.join(p for p,_ in peer_rets[:3])}"
               if peer_rets else "no peers mapped")

# ── Trend phase ───────────────────────────────────────────────────
phase, phase_desc = trend_phase(s1w, s1m, s3m, spy_3m)


# ═══ VERBOSE ═════════════════════════════════════════════════════
if VERBOSE:
    sep = '=' * 65
    print(f"\n{sep}")
    print(f"  TREND ANALYSIS: ${TICKER} ({stock_name}) [VERBOSE]")
    print(f"  Sector: {stock_sector} | Industry: {stock_industry}")
    print(f"  Benchmark: {ref_lbl}{' (thematic)' if thematic_etf else ' (broad sector)'}")
    print(f"  Peers: {', '.join(peers) if peers else 'none mapped'}")
    print(f"{sep}")

    print(f"\n--- MACRO ---")
    print(f"  SPY: 1W {spy_1w:+.1f}% | 1M {spy_1m:+.1f}% | 3M {spy_3m:+.1f}% | blend {spy_blend:+.1f}%")
    print(f"  VIX: {vix_cur:.1f} ({vix_lbl}, {vix_dir}) | 1M chg {vix_chg:+.1f}%")
    print(f"  Regime: {regime} | Breadth: {breadth}/11 ({breadth_lbl}) | Rotation: {rotation} (spread {rot_spread:+.1f}%)")

    print(f"\n--- SECTORS (by 1M) ---")
    for i, (e, d) in enumerate(ranked, 1):
        m = " <--" if e == stock_etf else ""
        print(f"  {i:2d}. {d.name:20s} {e:4s} | 1W {d.ret_1w:+6.1f}% | 1M {d.ret_1m:+6.1f}% | 3M {d.ret_3m:+6.1f}%{m}")

    print(f"\n--- THEME: {ref_lbl} ---")
    print(f"  1W {ref_1w:+.1f}% | 1M {ref_1m:+.1f}% | 3M {ref_3m:+.1f}% | blend vs SPY: {th_blend_vs_spy:+.1f}% | {th_accel_lbl}")

    print(f"\n--- STOCK ---")
    print(f"  ${TICKER}: 1W {s1w:+.1f}% | 1M {s1m:+.1f}% | 3M {s3m:+.1f}% | blend vs SPY: {stk_blend_vs_spy:+.1f}%")
    print(f"  Phase: {phase} — {phase_desc}")
    if peer_rets:
        print(f"  Peers: {' | '.join(f'{p} {r:+.1f}%' for p,r in peer_rets)}")
        print(f"  Peer avg: {peer_avg:+.1f}% | {TICKER} vs peers: {vs_peers:+.1f}% → {peer_rs}")


# ═══ SCORING — 3 PILLARS ═════════════════════════════════════════

# ── Pillar 1: MACRO (30%) — is the market environment supportive?
macro = 50.0

if spy_blend > 3:    macro += 12   # SPY blended trend
elif spy_blend > 1:  macro += 6
elif spy_blend < -3: macro -= 12
elif spy_blend < -1: macro -= 6

if vix_cur < 15:    macro += 10   # VIX level
elif vix_cur < 20:  macro += 5
elif vix_cur > 25:  macro -= 12
elif vix_cur > 20:  macro -= 5

if vix_dir == "COLLAPSING": macro += 8    # VIX direction
elif vix_dir == "FALLING":  macro += 4
elif vix_dir == "RISING":   macro -= 4
elif vix_dir == "SPIKING":  macro -= 8

if breadth >= 8:   macro += 10   # market breadth
elif breadth >= 5: macro += 5
elif breadth <= 2: macro -= 10
elif breadth <= 3: macro -= 5

if rotation == "RISK-ON":  macro += 8   # offensive vs defensive rotation
elif rotation == "RISK-OFF": macro -= 8

macro = max(0, min(100, round(macro)))

# ── Pillar 2: THEME (40%) — is money flowing into this sector/theme?
theme = 50.0

if th_blend_vs_spy > 8:    theme += 20   # theme blended alpha vs SPY
elif th_blend_vs_spy > 4:  theme += 12
elif th_blend_vs_spy > 1:  theme += 6
elif th_blend_vs_spy < -8: theme -= 20
elif th_blend_vs_spy < -4: theme -= 12
elif th_blend_vs_spy < -1: theme -= 6

if ref_3m > 20:    theme += 18   # 3M trend — is the big theme alive?
elif ref_3m > 5:   theme += 8
elif ref_3m > 0:   theme += 3
elif ref_3m < -10: theme -= 18
elif ref_3m < 0:   theme -= 8

if ref_1m > 2 and ref_3m > 5:    theme += 12   # 1M+3M both positive = healthy theme
elif ref_3m > 5 and ref_1m < 0:  theme += 5    # 3M alive, 1M pullback = still ok
elif ref_1m < -3 and ref_3m < 0: theme -= 12   # both negative = theme in trouble
elif ref_1m < 0 and ref_3m > 0:  theme -= 3    # 1M soft in positive theme

if th_accel_lbl == "RECOVERING":    theme += 8   # theme bouncing back from dip — buy signal
elif th_accel_lbl == "ACCELERATING": theme += 5   # already strong and getting stronger
elif th_accel_lbl == "ROLLING OVER": theme -= 8   # momentum fading — wait

if not thematic_etf: theme = 50 + (theme - 50) * 0.7  # penalty if using broad sector fallback

theme = max(0, min(100, round(theme)))

# ── Pillar 3: STOCK POSITION (30%) — where is this stock in its trend cycle?
stock = 50.0

if stk_blend_vs_spy > 10:    stock += 20   # blended alpha vs SPY (primary momentum signal)
elif stk_blend_vs_spy > 5:   stock += 12
elif stk_blend_vs_spy > 1:   stock += 6
elif stk_blend_vs_spy < -10: stock -= 20
elif stk_blend_vs_spy < -5:  stock -= 12
elif stk_blend_vs_spy < -1:  stock -= 6

if phase == "MOMENTUM":              stock += 15   # trend cycle phase
elif phase == "BREAKOUT":            stock += 12
elif phase == "PULLBACK IN UPTREND": stock += 8    # still bullish — buy the dip
elif phase == "RECOVERY":            stock += 5
elif phase == "TOPPING":             stock -= 10
elif phase == "DOWNTREND":           stock -= 20
# CONSOLIDATING = 0

if peer_rs == "LEADING":  stock += 12   # peer relative strength
elif peer_rs == "AHEAD":  stock += 5
elif peer_rs == "LAGGING": stock -= 12

stock = max(0, min(100, round(stock)))

# ── Final weighted score ──────────────────────────────────────────
final  = max(0, min(100, round(macro * 0.30 + theme * 0.40 + stock * 0.30)))
signal = "TAILWIND" if final >= 65 else "HEADWIND" if final < 40 else "NEUTRAL"
conf   = ("HIGH"        if final >= 80 or final <= 20 else
          "MEDIUM-HIGH" if final >= 65 or final <= 35 else "MEDIUM")


# ═══ COMPACT OUTPUT ══════════════════════════════════════════════
sep = '=' * 65
print(f"\n{sep}")
print(f"  TREND ANALYSIS: ${TICKER} ({stock_name})")
print(f"{sep}")

leaders_str = ' | '.join(f"{d.name.split()[0]} {d.ret_1m:+.0f}%" for _,d in leaders)
print(f"  MACRO:    SPY blend {spy_blend:+.1f}% | VIX {vix_cur:.1f} {vix_lbl} {vix_dir} | Breadth {breadth}/11 | {rotation}  [{macro}/100]")
print(f"  THEME:    {ref_lbl} | 1M {ref_1m:+.1f}% | 3M {ref_3m:+.1f}% | vs SPY {th_blend_vs_spy:+.1f}% | {th_accel_lbl}  [{theme}/100]")
print(f"  STOCK:    ${TICKER} 1W {s1w:+.1f}% | 1M {s1m:+.1f}% | 3M {s3m:+.1f}% | blend vs SPY {stk_blend_vs_spy:+.1f}%")
print(f"  PEERS:    {peer_rs} — {peer_str}  [{stock}/100]")
print(f"  PHASE:    {phase} — {phase_desc}")

print()
print(f"{sep}")
print(f"  SCORE:  {final}/100  {signal}  |  Macro {macro} · Theme {theme} · Stock {stock}  |  {conf}")
print(f"{sep}")
