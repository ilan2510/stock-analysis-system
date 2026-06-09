import yfinance as yf
import sys
import warnings
warnings.filterwarnings('ignore')

# ticker from command line or default
TICKER = sys.argv[1] if len(sys.argv) > 1 else "NFLX"
t = yf.Ticker(TICKER)

print(f"{'='*60}")
print(f"  INSTITUTIONAL OWNERSHIP: ${TICKER}")
print(f"{'='*60}")

# --- TOP 10 INSTITUTIONAL HOLDERS ---
print(f"\n>>> TOP 10 INSTITUTIONAL HOLDERS")
print("-" * 50)
try:
    inst = t.institutional_holders
    if inst is not None and not inst.empty:
        for _, row in inst.iterrows():
            name = row.get('Holder', 'N/A')
            pct = row.get('pctHeld', 0) * 100
            shares = row.get('Shares', 0)
            change = row.get('pctChange', 0) * 100
            direction = "+" if change > 0 else ""
            print(f"  {name:45s} | {pct:5.2f}% | {shares:>15,} shares | change: {direction}{change:.1f}%")
    else:
        print("  No institutional holder data available")
except Exception as e:
    print(f"  ERROR: {e}")

# --- MAJOR HOLDERS SUMMARY ---
print(f"\n>>> MAJOR HOLDERS SUMMARY")
print("-" * 50)
try:
    major = t.major_holders
    if major is not None and not major.empty:
        labels = {
            'insidersPercentHeld': 'Insiders % Held',
            'institutionsPercentHeld': 'Institutions % Held',
            'institutionsFloatPercentHeld': 'Institutions % of Float',
            'institutionsCount': 'Number of Institutions'
        }
        for idx, row in major.iterrows():
            label = labels.get(idx, idx)
            val = row['Value']
            if 'Percent' in idx or 'percent' in idx:
                print(f"  {label:30s} {val*100:.2f}%")
            else:
                print(f"  {label:30s} {int(val):,}")
    else:
        print("  No major holders data available")
except Exception as e:
    print(f"  ERROR: {e}")

# --- SHORT INTEREST ---
print(f"\n>>> SHORT INTEREST")
print("-" * 50)
try:
    info = t.info
    short_pct = info.get('shortPercentOfFloat', None)
    short_ratio = info.get('shortRatio', None)
    shares_short = info.get('sharesShort', None)
    shares_short_prev = info.get('sharesShortPriorMonth', None)

    if short_pct is not None:
        print(f"  Short % of Float:  {short_pct*100:.2f}%")
    else:
        print(f"  Short % of Float:  N/A")

    if short_ratio is not None:
        print(f"  Short Ratio:       {short_ratio} days to cover")
    else:
        print(f"  Short Ratio:       N/A")

    if shares_short is not None:
        print(f"  Shares Short:      {shares_short:,}")
    else:
        print(f"  Shares Short:      N/A")

    if shares_short_prev is not None and shares_short is not None:
        change = (shares_short - shares_short_prev) / shares_short_prev * 100
        direction = "+" if change > 0 else ""
        print(f"  Short Change MoM:  {direction}{change:.1f}%")
    else:
        print(f"  Short Change MoM:  N/A")

    # insider vs institution split
    insider_pct = info.get('heldPercentInsiders', None)
    inst_pct = info.get('heldPercentInstitutions', None)
    if insider_pct is not None:
        print(f"  Insider % Held:    {insider_pct*100:.2f}%")
    if inst_pct is not None:
        print(f"  Institution % Held:{inst_pct*100:.2f}%")
except Exception as e:
    print(f"  ERROR: {e}")

print(f"\n{'='*60}")
print(f"  END INSTITUTIONAL DATA")
print(f"{'='*60}")
