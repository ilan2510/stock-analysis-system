import urllib.request
import json
import sys
import os
import math
from datetime import datetime, timedelta

try:
    import yfinance as yf
    YF_AVAILABLE = True
except ImportError:
    YF_AVAILABLE = False
    print("WARNING: yfinance not installed. Balance sheet / cash flow / reported EPS will use Finnhub fallback.")

API_KEY = os.environ.get('FINNHUB_API_KEY', '')
if not API_KEY:
    print("ERROR: Set FINNHUB_API_KEY environment variable.")
    print("  export FINNHUB_API_KEY=your_key_here")
    sys.exit(1)

NEWS_DAYS_BACK = 60

# ── Sector Benchmarks (Damodaran, January 2026) ───────────────────────────────
# Every metric is judged vs its sector median — not generic thresholds
SECTOR_BENCHMARKS = {
    'healthcare': {'fwd_pe': 42.33, 'peg': 2.74, 'ev_ebitda': 20,   'op_margin': 15.08, 'roic': 22.27, 'roe': 11.26},
    'software':   {'fwd_pe': 34.13, 'peg': 1.65, 'ev_ebitda': 24,   'op_margin': 32.62, 'roic': 50.17, 'roe': 29.62},
    'semi':       {'fwd_pe': 37.29, 'peg': 2.13, 'ev_ebitda': 35,   'op_margin': 34.66, 'roic': 41.83, 'roe': 31.36},
    'retail':     {'fwd_pe': 23.97, 'peg': 2.86, 'ev_ebitda': 17,   'op_margin':  5.87, 'roic': 20.60, 'roe': 26.05},
    'bank':       {'fwd_pe': 12.02, 'peg': 0.97, 'ev_ebitda': None, 'op_margin':  None, 'roic':  None, 'roe': 11.31},
    'energy':     {'fwd_pe': 16.14, 'peg': 2.59, 'ev_ebitda':  5.5, 'op_margin': 24.03, 'roic': 13.79, 'roe': 12.21},
    'utility':    {'fwd_pe': 18.13, 'peg': 2.96, 'ev_ebitda': 14,   'op_margin': 20.24, 'roic':  5.99, 'roe': 10.42},
    'market':     {'fwd_pe': 27.66, 'peg': 1.90, 'ev_ebitda': 17,   'op_margin': 11.88, 'roic':  9.76, 'roe': 17.21},
}


def fetch(url):
    try:
        req = urllib.request.urlopen(url, timeout=10)
        return json.loads(req.read())
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None


def get_field(d, *keys, default=None):
    """Try multiple field name variations — handles API inconsistencies."""
    for k in keys:
        v = d.get(k)
        if v is not None:
            return v
    return default


def get_fundamentals(ticker):
    """Key ratios from Finnhub metrics endpoint."""
    url  = f'https://finnhub.io/api/v1/stock/metric?symbol={ticker}&metric=all&token={API_KEY}'
    data = fetch(url)
    if not data:
        return {}
    m = data.get('metric', {})
    return {
        '52w_high':           m.get('52WeekHigh'),
        '52w_low':            m.get('52WeekLow'),
        'pe_ttm':             m.get('peBasicExclExtraTTM'),
        'pb_annual':          m.get('pbAnnual'),
        'ps_annual':          m.get('psAnnual'),
        'revenue_growth_yoy': m.get('revenueGrowthTTMYoy'),
        'eps_growth_ttm':     m.get('epsGrowthTTMYoy'),
        'eps_growth_3y':      m.get('epsGrowth3Y'),
        'net_margin':         m.get('netProfitMarginTTM'),
        'gross_margin':       m.get('grossMarginTTM'),
        'current_ratio':      m.get('currentRatioAnnual'),
        'debt_to_equity':     m.get('totalDebt/totalEquityAnnual'),
        'roe':                m.get('roeTTM'),
        'roa':                m.get('roaTTM'),
        'roic':               m.get('roicTTM'),
        'beta':               m.get('beta'),
        'market_cap':         m.get('marketCapitalization'),
    }


def _yf_val(series, *keys):
    """Get first non-NaN value from a pandas Series by trying multiple key names."""
    for k in keys:
        if k in series.index:
            v = series[k]
            try:
                if not math.isnan(float(v)):
                    return float(v)
            except (TypeError, ValueError):
                pass
    return None


def get_balance_sheet(ticker):
    """
    Balance sheet via yfinance — includes capital leases, correct D/E.
    Falls back to Finnhub if yfinance unavailable.
    """
    if YF_AVAILABLE:
        try:
            t  = yf.Ticker(ticker)
            bs = t.balance_sheet
            if bs is not None and not bs.empty:
                latest = bs.iloc[:, 0]
                prior  = bs.iloc[:, 1] if bs.shape[1] > 1 else None

                ltd    = _yf_val(latest, 'Long Term Debt') or 0
                leases = _yf_val(latest, 'Long Term Capital Lease Obligation',
                                         'Capital Lease Obligations') or 0
                std    = _yf_val(latest, 'Current Debt And Capital Lease Obligation',
                                         'Current Capital Lease Obligation') or 0
                # Use yfinance's pre-computed Total Debt for accuracy
                total_debt = _yf_val(latest, 'Total Debt') or (ltd + leases + std)
                equity = _yf_val(latest, 'Common Stock Equity', 'Stockholders Equity') or 0
                liab   = _yf_val(latest, 'Total Liabilities Net Minority Interest') or 0
                cash   = _yf_val(latest, 'Cash And Cash Equivalents',
                                          'Cash Cash Equivalents And Short Term Investments') or 0
                shares = _yf_val(latest, 'Ordinary Shares Number', 'Share Issued')

                de_ratio = round(total_debt / equity, 3) if equity else None

                de_prior = None
                if prior is not None:
                    td_pr = _yf_val(prior, 'Total Debt') or 0
                    eq_pr = _yf_val(prior, 'Common Stock Equity', 'Stockholders Equity') or 1
                    de_prior = round(td_pr / eq_pr, 3)

                return {
                    'long_term_debt':       ltd,
                    'short_term_debt':      std,
                    'capital_leases':       leases,
                    'total_financial_debt': total_debt,
                    'total_equity':         equity,
                    'total_liabilities':    liab,
                    'cash':                 cash,
                    'shares':               shares,
                    'de_ratio_actual':      de_ratio,
                    'de_prior':             de_prior,
                    'source':               'yfinance',
                }
        except Exception as e:
            print(f"yfinance balance sheet error: {e} — falling back to Finnhub")

    # Finnhub fallback
    url  = f'https://finnhub.io/api/v1/stock/financials?symbol={ticker}&statement=bs&freq=annual&token={API_KEY}'
    data = fetch(url)
    if not data or not data.get('financials'):
        return {}
    fs     = data['financials']
    latest = fs[0]
    prior  = fs[1] if len(fs) > 1 else {}
    ltd    = get_field(latest, 'longTermDebt', default=0) or 0
    std    = get_field(latest, 'shortLongTermDebt', default=0) or 0
    leases = get_field(latest, 'capitalLeaseObligations', default=0) or 0
    equity = get_field(latest, 'totalStockholderEquity', 'totalEquity', default=0) or 0
    liab   = get_field(latest, 'totalLiab', default=0) or 0
    cash   = get_field(latest, 'cash', 'cashAndCashEquivalents', default=0) or 0
    total_debt = ltd + std + leases
    ltd_pr = get_field(prior, 'longTermDebt', default=0) or 0
    eq_pr  = get_field(prior, 'totalStockholderEquity', default=1) or 1
    return {
        'long_term_debt':       ltd,
        'short_term_debt':      std,
        'capital_leases':       leases,
        'total_financial_debt': total_debt,
        'total_equity':         equity,
        'total_liabilities':    liab,
        'cash':                 cash,
        'de_ratio_actual':      round(total_debt / equity, 3) if equity else None,
        'de_prior':             round(ltd_pr / eq_pr, 3),
        'source':               'finnhub',
    }


def get_cash_flow(ticker):
    """Cash flow via yfinance — OCF, CapEx, FCF. Falls back to Finnhub."""
    if YF_AVAILABLE:
        try:
            t  = yf.Ticker(ticker)
            cf = t.cashflow
            if cf is not None and not cf.empty:
                latest    = cf.iloc[:, 0]
                prior_col = cf.iloc[:, 1] if cf.shape[1] > 1 else None

                ocf   = _yf_val(latest, 'Operating Cash Flow')
                capex = _yf_val(latest, 'Capital Expenditure')
                fcf   = _yf_val(latest, 'Free Cash Flow')

                if capex and capex > 0:
                    capex = -capex
                if fcf is None and ocf is not None and capex is not None:
                    fcf = ocf + capex

                ocf_prior = _yf_val(prior_col, 'Operating Cash Flow') if prior_col is not None else None

                return {'ocf': ocf, 'capex': capex, 'fcf': fcf,
                        'ocf_prior': ocf_prior, 'source': 'yfinance'}
        except Exception as e:
            print(f"yfinance cash flow error: {e} — falling back to Finnhub")

    # Finnhub fallback
    url  = f'https://finnhub.io/api/v1/stock/financials?symbol={ticker}&statement=cf&freq=annual&token={API_KEY}'
    data = fetch(url)
    if not data or not data.get('financials'):
        return {}
    fs    = data['financials']
    latest = fs[0]
    prior  = fs[1] if len(fs) > 1 else {}
    ocf   = get_field(latest, 'totalCashFromOperatingActivities', 'operatingCashflow')
    capex = get_field(latest, 'capitalExpenditures', 'capitalExpenditure')
    fcf   = get_field(latest, 'freeCashFlow')
    if capex and capex > 0:
        capex = -capex
    if fcf is None and ocf and capex:
        fcf = ocf + capex
    return {'ocf': ocf, 'capex': capex, 'fcf': fcf,
            'ocf_prior': get_field(prior, 'totalCashFromOperatingActivities'), 'source': 'finnhub'}


def get_income_stmt(ticker):
    """Income statement via yfinance — revenue, EBIT, EBITDA, interest. Falls back to Finnhub."""
    if YF_AVAILABLE:
        try:
            t  = yf.Ticker(ticker)
            ic = t.income_stmt
            if ic is not None and not ic.empty:
                latest = ic.iloc[:, 0]
                prior  = ic.iloc[:, 1] if ic.shape[1] > 1 else None

                interest = _yf_val(latest, 'Interest Expense Non Operating', 'Interest Expense')

                return {
                    'revenue':       _yf_val(latest, 'Total Revenue'),
                    'revenue_prior': _yf_val(prior,  'Total Revenue') if prior is not None else None,
                    'ebit':          _yf_val(latest, 'EBIT', 'Operating Income'),
                    'ebitda':        _yf_val(latest, 'EBITDA', 'Normalized EBITDA'),
                    'net_income':    _yf_val(latest, 'Net Income', 'Net Income Common Stockholders'),
                    'interest_exp':  abs(interest) if interest else None,
                    'gross_profit':  _yf_val(latest, 'Gross Profit'),
                    'gp_prior':      _yf_val(prior,  'Gross Profit') if prior is not None else None,
                    'shares_now':    _yf_val(latest, 'Diluted Average Shares', 'Basic Average Shares'),
                    'shares_prior':  _yf_val(prior,  'Diluted Average Shares') if prior is not None else None,
                    'source':        'yfinance',
                }
        except Exception as e:
            print(f"yfinance income stmt error: {e} — falling back to Finnhub")

    # Finnhub fallback
    url  = f'https://finnhub.io/api/v1/stock/financials?symbol={ticker}&statement=ic&freq=annual&token={API_KEY}'
    data = fetch(url)
    if not data or not data.get('financials'):
        return {}
    fs    = data['financials']
    latest = fs[0]
    prior  = fs[1] if len(fs) > 1 else {}
    interest = get_field(latest, 'interestExpense')
    return {
        'revenue':       get_field(latest, 'totalRevenue', 'revenue'),
        'revenue_prior': get_field(prior,  'totalRevenue', 'revenue'),
        'ebit':          get_field(latest, 'ebit', 'operatingIncome'),
        'ebitda':        get_field(latest, 'ebitda'),
        'net_income':    get_field(latest, 'netIncome'),
        'interest_exp':  abs(interest) if interest else None,
        'gross_profit':  get_field(latest, 'grossProfit'),
        'gp_prior':      get_field(prior,  'grossProfit'),
        'shares_now':    get_field(latest, 'commonStockSharesOutstanding'),
        'shares_prior':  get_field(prior,  'commonStockSharesOutstanding'),
        'source':        'finnhub',
    }


def compute_derived(fundamentals, balance_sheet, cash_flow, income_stmt):
    """
    Computes all derived metrics:
      PEG | FCF | FCF Margin | FCF Conversion
      Net Debt/EBITDA | Interest Coverage
      Piotroski F-Score (up to 7 of 9 tests from available data)
    """
    d = {}

    pe          = fundamentals.get('pe_ttm')
    eps_growth  = fundamentals.get('eps_growth_ttm')
    roa         = fundamentals.get('roa')
    cur_ratio   = fundamentals.get('current_ratio')

    ocf         = cash_flow.get('ocf')
    fcf         = cash_flow.get('fcf')

    revenue     = income_stmt.get('revenue')
    revenue_pr  = income_stmt.get('revenue_prior')
    ebit        = income_stmt.get('ebit')
    ebitda      = income_stmt.get('ebitda')
    net_income  = income_stmt.get('net_income')
    interest    = income_stmt.get('interest_exp')
    gp_now      = income_stmt.get('gross_profit')
    gp_prev     = income_stmt.get('gp_prior')
    shares_now  = income_stmt.get('shares_now')
    shares_prev = income_stmt.get('shares_prior')

    total_debt  = balance_sheet.get('total_financial_debt', 0) or 0
    cash        = balance_sheet.get('cash', 0) or 0
    de_actual   = balance_sheet.get('de_ratio_actual')
    de_prior    = balance_sheet.get('de_prior')

    # ── PEG ──────────────────────────────────────────────────────────────
    if pe and eps_growth and eps_growth > 0:
        d['peg'] = round(pe / eps_growth, 2)
    else:
        d['peg'] = None

    # ── FCF Metrics ───────────────────────────────────────────────────────
    d['fcf'] = fcf
    d['fcf_margin']     = round((fcf / revenue) * 100, 1)   if (fcf and revenue)     else None
    d['fcf_conversion'] = round(fcf / net_income, 2)         if (fcf and net_income)  else None

    # ── Net Debt / EBITDA ─────────────────────────────────────────────────
    net_debt = total_debt - cash
    d['net_debt']       = net_debt
    d['net_debt_ebitda']= round(net_debt / ebitda, 2) if (ebitda and ebitda > 0) else None

    # ── Interest Coverage ─────────────────────────────────────────────────
    d['interest_coverage'] = round(ebit / interest, 1) if (ebit and interest and interest > 0) else None

    # ── Piotroski F-Score (up to 7 of 9 tests) ───────────────────────────
    score   = 0
    details = []

    if roa is not None:
        if roa > 0:
            score += 1; details.append('ROA > 0 [PASS]')
        else:
            details.append('ROA < 0 [FAIL]')

    if ocf is not None:
        if ocf > 0:
            score += 1; details.append('OCF > 0 [PASS]')
        else:
            details.append('OCF < 0 [FAIL]')

    if ocf is not None and net_income is not None:
        if ocf > net_income:
            score += 1; details.append('OCF > Net Income — quality earnings [PASS]')
        else:
            details.append('OCF < Net Income — accrual risk [WARN]')

    if de_actual is not None and de_prior is not None:
        if de_actual <= de_prior:
            score += 1; details.append('Debt ratio flat or falling [PASS]')
        else:
            details.append('Debt ratio rising [WARN]')

    if cur_ratio is not None:
        if cur_ratio >= 1.5:
            score += 1; details.append(f'Current ratio {cur_ratio} — healthy [PASS]')
        elif cur_ratio >= 1.0:
            details.append(f'Current ratio {cur_ratio} — adequate [NEUTRAL]')
        else:
            details.append(f'Current ratio {cur_ratio} — stressed [FAIL]')

    if shares_now is not None and shares_prev is not None and shares_prev > 0:
        if shares_now <= shares_prev * 1.01:
            score += 1; details.append('No meaningful dilution [PASS]')
        else:
            details.append('Share count increasing — dilution [WARN]')

    if gp_now and gp_prev and revenue and revenue_pr and revenue_pr > 0:
        gm_now  = gp_now  / revenue
        gm_prev = gp_prev / revenue_pr
        if gm_now > gm_prev:
            score += 1; details.append('Gross margin improving [PASS]')
        else:
            details.append('Gross margin flat or declining [WARN]')

    d['piotroski_score']   = score
    d['piotroski_max']     = len(details)
    d['piotroski_details'] = details

    return d


def get_earnings(ticker):
    """
    Earnings beats/misses.
    PRIMARY: yfinance earnings_history — uses actual REPORTED EPS + real consensus estimates.
    FALLBACK: Finnhub /stock/earnings (normalized EPS — flags with warning).
    """
    if YF_AVAILABLE:
        try:
            t  = yf.Ticker(ticker)
            eh = t.earnings_history
            if eh is not None and not eh.empty:
                results = []
                for date, row in eh.tail(4).iterrows():
                    actual   = row.get('epsActual')
                    estimate = row.get('epsEstimate')
                    surprise = row.get('surprisePercent')

                    try:
                        actual   = float(actual)   if actual   is not None and not math.isnan(actual)   else None
                        estimate = float(estimate) if estimate is not None and not math.isnan(estimate) else None
                        surprise = float(surprise) if surprise is not None and not math.isnan(surprise) else None
                    except (TypeError, ValueError):
                        actual = estimate = surprise = None

                    beat = (actual > estimate) if (actual is not None and estimate is not None) else None
                    surprise_pct = round(surprise * 100, 2) if surprise is not None else (
                        round(((actual - estimate) / abs(estimate)) * 100, 2)
                        if (actual and estimate and estimate != 0) else None
                    )

                    results.append({
                        'period':       str(date.date()) if hasattr(date, 'date') else str(date),
                        'actual':       round(actual, 4) if actual is not None else None,
                        'estimate':     round(estimate, 4) if estimate is not None else None,
                        'surprise_pct': surprise_pct,
                        'beat':         beat,
                        'source':       'yfinance-reported',
                    })
                return results
        except Exception as e:
            print(f"yfinance earnings error: {e} — falling back to Finnhub")

    # Finnhub fallback (normalized EPS — may diverge from reported)
    url  = f'https://finnhub.io/api/v1/stock/earnings?symbol={ticker}&limit=4&token={API_KEY}'
    data = fetch(url)
    if not data:
        return []
    results = []
    for e in data:
        actual   = e.get('actual')
        estimate = e.get('estimate')
        beat     = actual > estimate if (actual is not None and estimate is not None) else None
        results.append({
            'period':       e.get('period'),
            'actual':       actual,
            'estimate':     estimate,
            'surprise_pct': round(e.get('surprisePercent', 0), 2),
            'beat':         beat,
            'source':       'finnhub-normalized',
        })
    return results


def get_next_catalyst(ticker):
    """Next earnings date from Finnhub earnings calendar."""
    try:
        today = datetime.today()
        end   = (today + timedelta(days=180)).strftime('%Y-%m-%d')
        start = today.strftime('%Y-%m-%d')
        url   = f'https://finnhub.io/api/v1/calendar/earnings?symbol={ticker}&from={start}&to={end}&token={API_KEY}'
        data  = fetch(url)
        if data and data.get('earningsCalendar'):
            events = data['earningsCalendar']
            if events:
                e = events[0]
                return {
                    'date':          e.get('date'),
                    'eps_estimate':  e.get('epsEstimate'),
                    'revenue_est':   e.get('revenueEstimate'),
                }
    except Exception:
        pass
    return {}


def get_news(ticker):
    end   = datetime.today().strftime('%Y-%m-%d')
    start = (datetime.today() - timedelta(days=NEWS_DAYS_BACK)).strftime('%Y-%m-%d')
    url   = f'https://finnhub.io/api/v1/company-news?symbol={ticker}&from={start}&to={end}&token={API_KEY}'
    data  = fetch(url)
    if not data:
        return []
    return [{'headline': n.get('headline'), 'date': n.get('datetime')} for n in data[:10]]


def get_insiders(ticker):
    url  = f'https://finnhub.io/api/v1/stock/insider-transactions?symbol={ticker}&token={API_KEY}'
    data = fetch(url)
    if not data:
        return []
    transactions = []
    for t in data.get('data', [])[:10]:
        code   = t.get('transactionCode')
        action = 'BUY' if code == 'P' else 'SELL' if code == 'S' else 'OTHER'
        transactions.append({
            'name':   t.get('name'),
            'action': action,
            'shares': t.get('change'),
            'price':  t.get('transactionPrice'),
            'date':   t.get('transactionDate'),
            'code':   code,
        })
    return transactions


def fmt(val, suffix='', prefix='', decimals=2, na='N/A'):
    """Clean number formatting — returns N/A if None."""
    if val is None:
        return na
    return f"{prefix}{val:,.{decimals}f}{suffix}"


def print_results(ticker, fundamentals, balance_sheet, cash_flow, income_stmt, derived, earnings, news, insiders, catalyst=None):
    sep = '=' * 65
    print(f"\n{sep}")
    print(f"  FINNHUB FUNDAMENTAL ANALYSIS: ${ticker}")
    print(f"{sep}\n")

    # ── 1. VALUATION ─────────────────────────────────────────────────────
    print("=== 1. VALUATION ===")
    pe     = fundamentals.get('pe_ttm')
    peg    = derived.get('peg')
    eps_g  = fundamentals.get('eps_growth_ttm')

    print(f"52W Range:  {fmt(fundamentals.get('52w_low'))} - {fmt(fundamentals.get('52w_high'))}")
    print(f"P/E (TTM):  {fmt(pe, decimals=1)}")
    print(f"P/B:        {fmt(fundamentals.get('pb_annual'), decimals=1)}  |  P/S: {fmt(fundamentals.get('ps_annual'), decimals=1)}")
    print(f"EPS Growth: {fmt(eps_g, suffix='%', decimals=1)}")

    if peg is not None:
        peg_label = 'undervalued vs growth' if peg < 1.0 else ('fair' if peg < 2.0 else 'stretched')
        print(f"PEG Ratio:  {peg}  -> {peg_label}  (rule: <1 cheap, 1-2 fair, >2 stretched)")
    else:
        print("PEG Ratio:  N/A (negative or missing EPS growth)")

    print()

    # ── 2. PROFITABILITY & MARGINS ────────────────────────────────────────
    print("=== 2. PROFITABILITY & MARGINS ===")
    roic = fundamentals.get('roic')
    print(f"Gross Margin:  {fmt(fundamentals.get('gross_margin'), suffix='%', decimals=1)}")
    print(f"Net Margin:    {fmt(fundamentals.get('net_margin'),   suffix='%', decimals=1)}")
    print(f"ROE:           {fmt(fundamentals.get('roe'),           suffix='%', decimals=1)}")
    print(f"ROA:           {fmt(fundamentals.get('roa'),           suffix='%', decimals=1)}")
    roic_note = '  -> above 10% = moat signal' if (roic and roic > 10) else ''
    print(f"ROIC:          {fmt(roic, suffix='%', decimals=1)}{roic_note}")
    print()

    # ── 3. CASH FLOW — Truth-teller ───────────────────────────────────────
    print("=== 3. CASH FLOW (Truth-teller) ===")
    fconv = derived.get('fcf_conversion')
    print(f"Operating Cash Flow:  {fmt(cash_flow.get('ocf'), prefix='$', decimals=0)}")
    print(f"Free Cash Flow:       {fmt(derived.get('fcf'), prefix='$', decimals=0)}")
    print(f"FCF Margin:           {fmt(derived.get('fcf_margin'), suffix='%', decimals=1)}  (>15% excellent, 5-15% solid)")

    if fconv is not None:
        conv_label = 'quality earnings' if fconv >= 1.0 else ('acceptable' if fconv >= 0.8 else 'ACCRUAL RISK — investigate')
        print(f"FCF Conversion:       {fconv}  -> {conv_label}  (rule: >=1.0 healthy, <0.8 red flag)")
    else:
        print("FCF Conversion:       N/A")
    print()

    # ── 4. BALANCE SHEET HEALTH ───────────────────────────────────────────
    print("=== 4. BALANCE SHEET HEALTH ===")
    de        = balance_sheet.get('de_ratio_actual')
    ltd       = balance_sheet.get('long_term_debt', 0)
    leases    = balance_sheet.get('capital_leases', 0)
    nd_ebitda = derived.get('net_debt_ebitda')
    ic        = derived.get('interest_coverage')

    de_str = f"{de}  (LTD: ${ltd:,.0f} + Leases: ${leases:,.0f})" if de is not None else 'N/A'
    print(f"Debt/Equity (actual): {de_str}")
    print(f"Cash on hand:         {fmt(balance_sheet.get('cash'), prefix='$', decimals=0)}")

    if nd_ebitda is not None:
        nd_label = ('net cash') if nd_ebitda < 0 else ('excellent' if nd_ebitda < 2 else ('healthy' if nd_ebitda < 4 else ('caution' if nd_ebitda < 5 else 'RISKY')))
        print(f"Net Debt/EBITDA:      {nd_ebitda}  -> {nd_label}  (rule: <2 excellent, >5 risky)")
    else:
        print("Net Debt/EBITDA:      N/A")

    if ic is not None:
        ic_label = 'strong' if ic > 5 else ('healthy' if ic > 3 else ('vulnerable' if ic > 1.5 else 'DISTRESS RISK'))
        print(f"Interest Coverage:    {ic}x  -> {ic_label}  (rule: >3 healthy, <1.5 warning)")
    else:
        print("Interest Coverage:    N/A (likely no interest-bearing debt)")

    print(f"Current Ratio:        {fmt(fundamentals.get('current_ratio'), decimals=2)}")
    print()

    # ── 5. GROWTH ─────────────────────────────────────────────────────────
    print("=== 5. GROWTH ===")
    rev_g = fundamentals.get('revenue_growth_yoy')
    print(f"Revenue Growth YoY:   {fmt(rev_g, suffix='%', decimals=1)}  (>8% baseline quality, >20% strong)")
    print(f"EPS Growth TTM:       {fmt(eps_g,  suffix='%', decimals=1)}")
    print(f"EPS Growth 3Y:        {fmt(fundamentals.get('eps_growth_3y'), suffix='%', decimals=1)}")
    print(f"Beta:                 {fmt(fundamentals.get('beta'), decimals=2)}")
    print()

    # ── 6. PIOTROSKI F-SCORE ──────────────────────────────────────────────
    print("=== 6. PIOTROSKI F-SCORE (Quality Filter) ===")
    p_score   = derived.get('piotroski_score', 0)
    p_max     = derived.get('piotroski_max', 0)
    p_details = derived.get('piotroski_details', [])

    if p_max > 0:
        pct = p_score / p_max
        grade = 'STRONG' if pct >= 0.75 else ('ADEQUATE' if pct >= 0.5 else 'WEAK')
        skipped = 9 - p_max
        print(f"Score: {p_score}/{p_max} tested ({skipped} tests skipped — need full historical data)  -> {grade}")
        for line in p_details:
            print(f"  {line}")
    else:
        print("  Could not compute (insufficient data from API)")
    print()

    # ── 7. EARNINGS ───────────────────────────────────────────────────────
    print("=== 7. EARNINGS (last 4 quarters) ===")
    beat_count = 0
    src_label  = ''
    for e in earnings:
        beat_str  = "BEAT" if e.get('beat') else ("MISS" if e.get('beat') is False else "N/A")
        if e.get('beat'):
            beat_count += 1
        src_label = e.get('source', 'unknown')
        print(f"  {e.get('period')} | Actual: {e.get('actual')} | Est: {e.get('estimate')} | Surprise: {e.get('surprise_pct')}% | {beat_str}")
    print(f"Beat streak: {beat_count}/4")
    if 'normalized' in src_label:
        print("  [!] Source: Finnhub normalized EPS — verify manually if numbers look off.")
    else:
        print("  [OK] Source: yfinance reported EPS (actual filed figures)")
    print()

    # ── 8. NEWS ───────────────────────────────────────────────────────────
    print(f"=== 8. RECENT NEWS (last {NEWS_DAYS_BACK} days) ===")
    for n in (news[:5] if news else []):
        print(f"  - {n.get('headline')}")
    if not news:
        print("  No recent news found.")
    print()

    # ── 9. INSIDER ACTIVITY ───────────────────────────────────────────────
    print("=== 9. INSIDER ACTIVITY ===")
    buys  = [t for t in insiders if t['action'] == 'BUY']
    sells = [t for t in insiders if t['action'] == 'SELL']
    print(f"Open-market Buys: {len(buys)} | Sells: {len(sells)}")
    for t in insiders[:5]:
        print(f"  {t.get('date')} | {t.get('name')} | {t.get('action')} | {t.get('shares')} shares @ ${t.get('price')}")
    print()

    # ── CATALYST ──────────────────────────────────────────────────────────
    print("=== 10. NEXT CATALYST ===")
    if catalyst and catalyst.get('date'):
        eps_est = catalyst.get('eps_estimate')
        rev_est = catalyst.get('revenue_est')
        eps_str = f" | EPS est: ${eps_est}" if eps_est else ""
        rev_str = f" | Rev est: ${rev_est:,.0f}" if rev_est else ""
        print(f"  Next Earnings: {catalyst['date']}{eps_str}{rev_str}")
    else:
        print("  No upcoming earnings found in next 6 months (or calendar not available).")
    print()

    # ── SECTOR BENCHMARK TABLE (for agent reference) ──────────────────────
    print("=== SECTOR BENCHMARKS (Damodaran Jan 2026 — agent: use for sector-relative scoring) ===")
    print("  healthcare -> fwd P/E 42.33 | PEG 2.74 | op_margin 15.08% | ROIC 22.27%")
    print("  software   -> fwd P/E 34.13 | PEG 1.65 | op_margin 32.62% | ROIC 50.17%")
    print("  semi       -> fwd P/E 37.29 | PEG 2.13 | op_margin 34.66% | ROIC 41.83%")
    print("  retail     -> fwd P/E 23.97 | PEG 2.86 | op_margin  5.87% | ROIC 20.60%")
    print("  market avg -> fwd P/E 27.66 | PEG 1.90 | op_margin 11.88% | ROIC  9.76%")
    print()
    print(sep)
    print("AGENT INSTRUCTIONS:")
    print("  0. Run Section 0 (Company DNA) FIRST — identify North Star metric, search for latest value,")
    print("     flag price/metric divergences, note next catalyst date from Section 10 above.")
    print("  1. Identify the sector of this stock.")
    print("  2. Compare every metric above to that sector's benchmark — not generic thresholds.")
    print("  3. Score 4 pillars: Quality 35% / Value 30% / Growth 25% / Sentiment 10%")
    print("  4. Identify moat type: Network Effects | Switching Costs | Cost Advantage | Intangibles | Efficient Scale")
    print("  5. Write 2-3 specific growth vectors with real numbers (like the Amazon/TransMedics example style).")
    print("  6. Check red flags: FCF conversion <0.8 | Net Debt/EBITDA >5 | rising debt + falling FCF")
    print("  7. Final output: BULLISH / NEUTRAL / BEARISH with score and reasoning.")
    print(sep)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python finnhub_stock_analyzer.py <TICKER>")
        print("Example: python finnhub_stock_analyzer.py ALGN")
        sys.exit(1)

    ticker = sys.argv[1].upper().replace('$', '')
    print(f"Fetching Finnhub data for ${ticker}...")

    fundamentals  = get_fundamentals(ticker)
    balance_sheet = get_balance_sheet(ticker)
    cash_flow     = get_cash_flow(ticker)
    income_stmt   = get_income_stmt(ticker)
    derived       = compute_derived(fundamentals, balance_sheet, cash_flow, income_stmt)
    earnings      = get_earnings(ticker)
    news          = get_news(ticker)
    insiders      = get_insiders(ticker)
    catalyst      = get_next_catalyst(ticker)

    print_results(ticker, fundamentals, balance_sheet, cash_flow,
                  income_stmt, derived, earnings, news, insiders, catalyst)
