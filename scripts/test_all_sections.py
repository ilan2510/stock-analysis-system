"""
Test script — verifies all 14 data sections work for a given ticker.
Tests Finnhub API + yfinance data availability.
Usage: python test_all_sections.py [TICKER]
"""
import yfinance as yf
import urllib.request
import json
import os
import sys
import math
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

TICKER = sys.argv[1] if len(sys.argv) > 1 else "NFLX"
API_KEY = os.environ.get('FINNHUB_API_KEY', '')
if not API_KEY:
    print("ERROR: Set FINNHUB_API_KEY environment variable.")
    sys.exit(1)

t = yf.Ticker(TICKER)

def fetch(url):
    try:
        req = urllib.request.urlopen(url, timeout=10)
        return json.loads(req.read())
    except Exception as e:
        print(f"  ERROR: {e}")
        return None

def fmt(val, prefix='', suffix='', dec=2):
    if val is None: return 'N/A'
    return f"{prefix}{val:,.{dec}f}{suffix}"

# ============================================================
print("=" * 70)
print(f"  TESTING ALL DATA SECTIONS FOR ${TICKER}")
print("=" * 70)

# ── SECTION 1: VALUATION (Finnhub API) ──
print("\n>>> SECTION 1: VALUATION (source: Finnhub API)")
print("-" * 50)
url = f'https://finnhub.io/api/v1/stock/metric?symbol={TICKER}&metric=all&token={API_KEY}'
data = fetch(url)
if data:
    m = data.get('metric', {})
    pe = m.get('peBasicExclExtraTTM')
    eps_g = m.get('epsGrowthTTMYoy')
    peg = round(pe / eps_g, 2) if (pe and eps_g and eps_g > 0) else None
    print(f"  52W Range:     ${m.get('52WeekLow'):.2f} - ${m.get('52WeekHigh'):.2f}")
    print(f"  P/E (TTM):     {fmt(pe, dec=1)}")
    print(f"  P/B:           {fmt(m.get('pbAnnual'), dec=1)}")
    print(f"  P/S:           {fmt(m.get('psAnnual'), dec=1)}")
    print(f"  EPS Growth:    {fmt(eps_g, suffix='%', dec=1)}")
    print(f"  PEG:           {fmt(peg, dec=2)}")

# ── SECTION 2: PROFITABILITY (Finnhub API) ──
print("\n>>> SECTION 2: PROFITABILITY & MARGINS (source: Finnhub API)")
print("-" * 50)
if data:
    m = data.get('metric', {})
    print(f"  Gross Margin:  {fmt(m.get('grossMarginTTM'), suffix='%', dec=1)}")
    print(f"  Net Margin:    {fmt(m.get('netProfitMarginTTM'), suffix='%', dec=1)}")
    print(f"  ROE:           {fmt(m.get('roeTTM'), suffix='%', dec=1)}")
    print(f"  ROA:           {fmt(m.get('roaTTM'), suffix='%', dec=1)}")
    print(f"  ROIC:          {fmt(m.get('roicTTM'), suffix='%', dec=1)}")

# ── SECTION 3: CASH FLOW (yfinance) ──
print("\n>>> SECTION 3: CASH FLOW (source: yfinance)")
print("-" * 50)
try:
    cf = t.cashflow
    if cf is not None and not cf.empty:
        latest = cf.iloc[:, 0]
        ocf = latest.get('Operating Cash Flow')
        capex = latest.get('Capital Expenditure')
        fcf = latest.get('Free Cash Flow')
        ni = None
        try:
            ic = t.income_stmt
            if ic is not None and not ic.empty:
                ni = ic.iloc[:, 0].get('Net Income')
        except: pass

        print(f"  Operating Cash Flow:  {fmt(ocf, prefix='$', dec=0)}")
        print(f"  CapEx:                {fmt(capex, prefix='$', dec=0)}")
        print(f"  Free Cash Flow:       {fmt(fcf, prefix='$', dec=0)}")
        if fcf and ni and ni != 0:
            print(f"  FCF Conversion:       {fcf/ni:.2f}  (>=0.8 good, <0.8 red flag)")
except Exception as e:
    print(f"  ERROR: {e}")

# ── SECTION 4: BALANCE SHEET (yfinance) ──
print("\n>>> SECTION 4: BALANCE SHEET (source: yfinance)")
print("-" * 50)
try:
    bs = t.balance_sheet
    if bs is not None and not bs.empty:
        latest = bs.iloc[:, 0]
        total_debt = latest.get('Total Debt') or 0
        equity = latest.get('Common Stock Equity') or latest.get('Stockholders Equity') or 0
        cash = latest.get('Cash And Cash Equivalents') or 0
        ltd = latest.get('Long Term Debt') or 0
        leases = latest.get('Long Term Capital Lease Obligation') or 0

        de = total_debt / equity if equity else None
        print(f"  Total Debt:     {fmt(total_debt, prefix='$', dec=0)}")
        print(f"  Long Term Debt: {fmt(ltd, prefix='$', dec=0)}")
        print(f"  Capital Leases: {fmt(leases, prefix='$', dec=0)}")
        print(f"  Equity:         {fmt(equity, prefix='$', dec=0)}")
        print(f"  Cash:           {fmt(cash, prefix='$', dec=0)}")
        print(f"  D/E Ratio:      {fmt(de, dec=3)}")
except Exception as e:
    print(f"  ERROR: {e}")

# ── SECTION 5: GROWTH (Finnhub API) ──
print("\n>>> SECTION 5: GROWTH (source: Finnhub API)")
print("-" * 50)
if data:
    m = data.get('metric', {})
    print(f"  Revenue Growth YoY:  {fmt(m.get('revenueGrowthTTMYoy'), suffix='%', dec=1)}")
    print(f"  EPS Growth TTM:      {fmt(m.get('epsGrowthTTMYoy'), suffix='%', dec=1)}")
    print(f"  EPS Growth 3Y:       {fmt(m.get('epsGrowth3Y'), suffix='%', dec=1)}")
    print(f"  Beta:                {fmt(m.get('beta'), dec=2)}")

# ── SECTION 6: PIOTROSKI (calculated) ──
print("\n>>> SECTION 6: PIOTROSKI F-SCORE (source: calculated)")
print("-" * 50)
print("  (See finnhub_stock_analyzer.py for full Piotroski calculation)")

# ── SECTION 7: EARNINGS (yfinance) ──
print("\n>>> SECTION 7: EARNINGS — Last 4 Quarters (source: yfinance)")
print("-" * 50)
try:
    eh = t.earnings_history
    if eh is not None and not eh.empty:
        for date, row in eh.tail(4).iterrows():
            actual = row.get('epsActual')
            est = row.get('epsEstimate')
            surp = row.get('surprisePercent')
            try:
                actual = float(actual) if actual is not None and not math.isnan(actual) else None
                est = float(est) if est is not None and not math.isnan(est) else None
                surp = float(surp) if surp is not None and not math.isnan(surp) else None
            except: actual = est = surp = None
            beat = "BEAT" if (actual and est and actual > est) else "MISS" if (actual and est) else "N/A"
            surp_str = f"{surp*100:.2f}%" if surp else "N/A"
            print(f"  {str(date.date()) if hasattr(date,'date') else date} | Actual: {actual} | Est: {est} | Surprise: {surp_str} | {beat}")
except Exception as e:
    print(f"  ERROR: {e}")

# ── SECTION 8: NEWS (Finnhub API) ──
print("\n>>> SECTION 8: NEWS — Last 60 Days (source: Finnhub API)")
print("-" * 50)
end = datetime.today().strftime('%Y-%m-%d')
start = (datetime.today() - timedelta(days=60)).strftime('%Y-%m-%d')
url = f'https://finnhub.io/api/v1/company-news?symbol={TICKER}&from={start}&to={end}&token={API_KEY}'
news = fetch(url)
if news:
    for n in news[:5]:
        print(f"  - [{n.get('source','')}] {n.get('headline','')}")
    print(f"  ... ({len(news)} total articles)")
else:
    print("  No news found")

# ── SECTION 9: INSIDERS (Finnhub API) ──
print("\n>>> SECTION 9: INSIDER ACTIVITY (source: Finnhub API)")
print("-" * 50)
url = f'https://finnhub.io/api/v1/stock/insider-transactions?symbol={TICKER}&token={API_KEY}'
ins = fetch(url)
if ins and ins.get('data'):
    buys = sum(1 for x in ins['data'] if x.get('transactionCode') == 'P')
    sells = sum(1 for x in ins['data'] if x.get('transactionCode') == 'S')
    print(f"  Open-market Buys: {buys} | Sells: {sells}")
    for x in ins['data'][:5]:
        code = x.get('transactionCode')
        action = 'BUY' if code == 'P' else 'SELL' if code == 'S' else 'OTHER'
        print(f"  {x.get('transactionDate')} | {x.get('name')} | {action} | {x.get('change')} shares @ ${x.get('transactionPrice')}")

# ── SECTION 10: NEXT CATALYST (Finnhub API) ──
print("\n>>> SECTION 10: NEXT CATALYST (source: Finnhub API)")
print("-" * 50)
today = datetime.today()
end_cat = (today + timedelta(days=180)).strftime('%Y-%m-%d')
start_cat = today.strftime('%Y-%m-%d')
url = f'https://finnhub.io/api/v1/calendar/earnings?symbol={TICKER}&from={start_cat}&to={end_cat}&token={API_KEY}'
cat = fetch(url)
if cat and cat.get('earningsCalendar'):
    e = cat['earningsCalendar'][0]
    print(f"  Next Earnings: {e.get('date')}")
    print(f"  EPS Estimate:  {e.get('epsEstimate')}")
    print(f"  Revenue Est:   {e.get('revenueEstimate')}")
else:
    print("  No upcoming earnings found")

# ── AGENT 2 DATA: INSTITUTIONAL OWNERSHIP (yfinance) ──
print("\n" + "=" * 70)
print(">>> AGENT 2: INSTITUTIONAL OWNERSHIP (source: yfinance)")
print("-" * 50)
try:
    inst = t.institutional_holders
    if inst is not None and not inst.empty:
        print(f"  Top {len(inst)} Institutional Holders:")
        for _, row in inst.iterrows():
            name = row.get('Holder', 'N/A')
            pct = row.get('pctHeld', 0)
            shares = row.get('Shares', 0)
            change = row.get('pctChange', 0)
            chg_str = f"+{change*100:.1f}%" if change > 0 else f"{change*100:.1f}%"
            print(f"    {name:45s} | {pct*100:.2f}% | {shares:>15,} shares | change: {chg_str}")

    major = t.major_holders
    if major is not None and not major.empty:
        print(f"\n  Major Holders Summary:")
        for idx, row in major.iterrows():
            print(f"    {idx}: {row.values[0]}")
except Exception as e:
    print(f"  ERROR: {e}")

# ── AGENT 3 DATA: ANALYST RECOMMENDATIONS (yfinance) ──
print("\n>>> AGENT 3: ANALYST RECOMMENDATIONS (source: yfinance)")
print("-" * 50)
try:
    rec = t.recommendations_summary
    if rec is not None and not rec.empty:
        latest_rec = rec.iloc[0]
        total = latest_rec.get('strongBuy',0) + latest_rec.get('buy',0) + latest_rec.get('hold',0) + latest_rec.get('sell',0) + latest_rec.get('strongSell',0)
        print(f"  Strong Buy:  {latest_rec.get('strongBuy', 0)}")
        print(f"  Buy:         {latest_rec.get('buy', 0)}")
        print(f"  Hold:        {latest_rec.get('hold', 0)}")
        print(f"  Sell:        {latest_rec.get('sell', 0)}")
        print(f"  Strong Sell: {latest_rec.get('strongSell', 0)}")
        print(f"  Total:       {total}")

    targets = t.analyst_price_targets
    if targets:
        print(f"\n  Price Targets:")
        print(f"    Current:  ${targets.get('current', 'N/A')}")
        print(f"    Low:      ${targets.get('low', 'N/A')}")
        print(f"    High:     ${targets.get('high', 'N/A')}")
        print(f"    Mean:     ${targets.get('mean', 'N/A')}")
        print(f"    Median:   ${targets.get('median', 'N/A')}")
        if targets.get('current') and targets.get('mean'):
            upside = (targets['mean'] - targets['current']) / targets['current'] * 100
            print(f"    Upside:   {upside:+.1f}%")
except Exception as e:
    print(f"  ERROR: {e}")

# ── AGENT 5 DATA: SECTOR ETF PERFORMANCE (yfinance) ──
print("\n>>> AGENT 5: SECTOR ETF PERFORMANCE (source: yfinance)")
print("-" * 50)
sectors = {
    'XLK': 'Technology', 'XLF': 'Financials', 'XLE': 'Energy',
    'XLV': 'Healthcare', 'XLI': 'Industrials', 'XLC': 'Communication',
    'XLRE': 'Real Estate', 'XLB': 'Materials', 'XLY': 'Consumer Disc',
    'XLP': 'Consumer Staples', 'XLU': 'Utilities', 'SPY': '--- S&P 500 ---'
}
for etf, name in sectors.items():
    try:
        d = yf.Ticker(etf).history(period="1mo")
        if not d.empty:
            ret = (d['Close'].iloc[-1] - d['Close'].iloc[0]) / d['Close'].iloc[0] * 100
            bar = "+" if ret > 0 else ""
            print(f"  {name:20s} ({etf}): {bar}{ret:.1f}%")
    except:
        print(f"  {name:20s} ({etf}): ERROR")

# ── BONUS: EXTRA DATA FROM yfinance .info ──
print("\n>>> BONUS: EXTRA DATA (source: yfinance .info)")
print("-" * 50)
try:
    info = t.info
    print(f"  Market Cap:        ${info.get('marketCap', 0)/1e9:.1f}B")
    print(f"  Forward P/E:       {info.get('forwardPE', 'N/A')}")
    print(f"  Trailing P/E:      {info.get('trailingPE', 'N/A')}")
    print(f"  PEG Ratio:         {info.get('pegRatio', 'N/A')}")
    print(f"  Short % Float:     {info.get('shortPercentOfFloat', 0)*100:.2f}%")
    print(f"  Short Ratio:       {info.get('shortRatio', 'N/A')} days")
    print(f"  52W High:          ${info.get('fiftyTwoWeekHigh', 'N/A')}")
    print(f"  52W Low:           ${info.get('fiftyTwoWeekLow', 'N/A')}")
    print(f"  Sector:            {info.get('sector', 'N/A')}")
    print(f"  Industry:          {info.get('industry', 'N/A')}")
except Exception as e:
    print(f"  ERROR: {e}")

print("\n" + "=" * 70)
print("  TEST COMPLETE")
print("=" * 70)
