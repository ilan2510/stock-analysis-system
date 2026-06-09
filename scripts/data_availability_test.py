"""
Quick test — checks what yfinance data is available for agents 2, 3, 4, 5.
Usage: python data_availability_test.py [TICKER]
"""
import yfinance as yf
import sys
import warnings
warnings.filterwarnings('ignore')

TICKER = sys.argv[1] if len(sys.argv) > 1 else "NFLX"
t = yf.Ticker(TICKER)

# === AGENT 2: INSTITUTIONAL (replaces Fintel WebSearch) ===
print("=" * 60)
print("AGENT 2 DATA — INSTITUTIONAL OWNERSHIP")
print("=" * 60)
try:
    inst = t.institutional_holders
    if inst is not None and not inst.empty:
        print(f"\nTop 10 Institutional Holders:")
        print(inst.to_string())
    else:
        print("No institutional data")
except Exception as e:
    print(f"Error: {e}")

try:
    major = t.major_holders
    if major is not None and not major.empty:
        print(f"\nMajor Holders Summary:")
        print(major.to_string())
    else:
        print("No major holders data")
except Exception as e:
    print(f"Error: {e}")

# === AGENT 3: ANALYSTS (replaces TipRanks WebSearch) ===
print("\n" + "=" * 60)
print("AGENT 3 DATA — ANALYST RECOMMENDATIONS")
print("=" * 60)
try:
    rec = t.recommendations
    if rec is not None and not rec.empty:
        print(f"\nRecent Analyst Recommendations (last 10):")
        print(rec.tail(10).to_string())
    else:
        print("No recommendations data")
except Exception as e:
    print(f"Error: {e}")

try:
    rec_sum = t.recommendations_summary
    if rec_sum is not None and not rec_sum.empty:
        print(f"\nRecommendations Summary:")
        print(rec_sum.to_string())
    else:
        print("No summary data")
except Exception as e:
    print(f"Error: {e}")

try:
    targets = t.analyst_price_targets
    if targets is not None:
        print(f"\nAnalyst Price Targets:")
        print(f"  Current: ${targets.get('current', 'N/A')}")
        print(f"  Low:     ${targets.get('low', 'N/A')}")
        print(f"  High:    ${targets.get('high', 'N/A')}")
        print(f"  Mean:    ${targets.get('mean', 'N/A')}")
        print(f"  Median:  ${targets.get('median', 'N/A')}")
    else:
        print("No price targets")
except Exception as e:
    print(f"Error: {e}")

# === AGENT 4: SENTIMENT (news from yfinance) ===
print("\n" + "=" * 60)
print("AGENT 4 DATA — NEWS & SENTIMENT")
print("=" * 60)
try:
    news = t.news
    if news:
        print(f"\nRecent News ({len(news)} items, showing first 5):")
        for n in news[:5]:
            title = n.get('title', 'N/A')
            publisher = n.get('publisher', 'N/A')
            print(f"  - [{publisher}] {title}")
    else:
        print("No news data")
except Exception as e:
    print(f"Error: {e}")

# === AGENT 5: TREND (sector performance data) ===
print("\n" + "=" * 60)
print("AGENT 5 DATA — SECTOR PERFORMANCE (for trend)")
print("=" * 60)
sectors = {
    'XLK': 'Technology', 'XLF': 'Financials', 'XLE': 'Energy',
    'XLV': 'Healthcare', 'XLI': 'Industrials', 'XLC': 'Communication',
    'XLRE': 'Real Estate', 'XLB': 'Materials', 'XLY': 'Consumer Disc',
    'XLP': 'Consumer Staples', 'XLU': 'Utilities', 'SPY': '--- S&P 500 ---'
}
print(f"\nSector ETF Performance (1 month):")
for etf, name in sectors.items():
    try:
        data = yf.Ticker(etf).history(period="1mo")
        if not data.empty:
            ret = (data['Close'].iloc[-1] - data['Close'].iloc[0]) / data['Close'].iloc[0] * 100
            direction = "+" if ret > 0 else ""
            print(f"  {name:20s} ({etf}): {direction}{ret:.1f}%")
    except:
        print(f"  {name:20s} ({etf}): ERROR")

# === EXTRA: bonus yfinance data ===
print("\n" + "=" * 60)
print("BONUS — OTHER DATA AVAILABLE VIA CODE")
print("=" * 60)
info = t.info
print(f"  Market Cap:        ${info.get('marketCap', 0)/1e9:.1f}B")
print(f"  Forward P/E:       {info.get('forwardPE', 'N/A')}")
print(f"  Trailing P/E:      {info.get('trailingPE', 'N/A')}")
print(f"  PEG Ratio:         {info.get('pegRatio', 'N/A')}")
print(f"  Short % of Float:  {info.get('shortPercentOfFloat', 0)*100:.2f}%")
print(f"  Short Ratio:       {info.get('shortRatio', 'N/A')} days")
print(f"  52W High:          ${info.get('fiftyTwoWeekHigh', 'N/A')}")
print(f"  52W Low:           ${info.get('fiftyTwoWeekLow', 'N/A')}")
print(f"  Beta:              {info.get('beta', 'N/A')}")
print(f"  Insider % Held:    {info.get('heldPercentInsiders', 0)*100:.2f}%")
print(f"  Institution % Held:{info.get('heldPercentInstitutions', 0)*100:.2f}%")
