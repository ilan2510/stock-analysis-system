import urllib.request
import json
import sys
import math
import time
import concurrent.futures
from datetime import datetime, timedelta

# Windows cp1255 fix — force UTF-8 output so em-dashes and arrows print correctly
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

try:
    import yfinance as yf
    YF_AVAILABLE = True
except ImportError:
    YF_AVAILABLE = False
    print("WARNING: yfinance not installed. Balance sheet / cash flow / reported EPS will use Finnhub fallback.")

API_KEY = 'd86mf5hr01qgiu4625sgd86mf5hr01qgiu4625t0'
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

# ── yfinance sector -> benchmark key ──────────────────────────────────────────
SECTOR_MAP = {
    'Healthcare': 'healthcare',
    'Financial Services': 'bank',
    'Consumer Cyclical': 'retail',
    'Consumer Defensive': 'retail',
    'Energy': 'energy',
    'Utilities': 'utility',
    'Industrials': 'market',
    'Communication Services': 'market',
    'Real Estate': 'market',
    'Basic Materials': 'market',
}


def detect_sector(info):
    """Map yfinance sector/industry to benchmark key."""
    sector = info.get('sector', '')
    industry = (info.get('industry', '') or '').lower()
    if sector == 'Technology':
        if 'semiconductor' in industry or 'chip' in industry:
            return 'semi'
        return 'software'
    return SECTOR_MAP.get(sector, 'market')


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


def get_quarterly_revenue(ticker):
    """Last 4Q sequential revenue growth — detects ACCELERATING / DECELERATING / STABLE."""
    if not YF_AVAILABLE:
        return {}
    try:
        t  = yf.Ticker(ticker)
        qi = t.quarterly_income_stmt
        if qi is None or qi.empty:
            return {}

        rev_key = next((k for k in ['Total Revenue', 'Revenue', 'Net Revenue'] if k in qi.index), None)
        if not rev_key:
            return {}

        quarters = []
        for date, val in qi.loc[rev_key].items():
            try:
                v = float(val)
                if not math.isnan(v) and v > 0:
                    quarters.append({'date': str(date)[:7], 'revenue': v})
            except (TypeError, ValueError):
                pass

        quarters.sort(key=lambda x: x['date'])   # oldest → newest
        quarters = quarters[-5:]                  # keep 5 to compute 4 growth rates

        if len(quarters) < 3:
            return {'quarters': quarters}

        growth = [
            round((quarters[i]['revenue'] - quarters[i-1]['revenue']) / quarters[i-1]['revenue'] * 100, 1)
            for i in range(1, len(quarters))
            if quarters[i-1]['revenue'] > 0
        ]

        trend = 'STABLE'
        if len(growth) >= 2:
            delta = growth[-1] - growth[0]
            if delta > 2:
                trend = 'ACCELERATING'
            elif delta < -2:
                trend = 'DECELERATING'

        return {'quarters': quarters[-4:], 'qoq_growth': growth[-3:], 'trend': trend}
    except Exception:
        return {}


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
    equity      = balance_sheet.get('total_equity', 0) or 0
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

    # 1. ROA > 0
    if roa is not None:
        if roa > 0:
            score += 1; details.append('ROA > 0 [PASS]')
        else:
            details.append('ROA < 0 [FAIL]')

    # 2. OCF > 0
    if ocf is not None:
        if ocf > 0:
            score += 1; details.append('OCF > 0 [PASS]')
        else:
            details.append('OCF < 0 [FAIL]')

    # 3. OCF > Net Income (accrual quality — most important)
    if ocf is not None and net_income is not None:
        if ocf > net_income:
            score += 1; details.append('OCF > Net Income — quality earnings [PASS]')
        else:
            details.append('OCF < Net Income — accrual risk [WARN]')

    # 4. Debt ratio falling vs prior year
    if de_actual is not None and de_prior is not None:
        if de_actual <= de_prior:
            score += 1; details.append('Debt ratio flat or falling [PASS]')
        else:
            details.append('Debt ratio rising [WARN]')

    # 5. Current ratio (proxy for improving — use level as health check)
    if cur_ratio is not None:
        if cur_ratio >= 1.5:
            score += 1; details.append(f'Current ratio {cur_ratio} — healthy [PASS]')
        elif cur_ratio >= 1.0:
            details.append(f'Current ratio {cur_ratio} — adequate [NEUTRAL]')
        else:
            details.append(f'Current ratio {cur_ratio} — stressed [FAIL]')

    # 6. No meaningful share dilution
    if shares_now is not None and shares_prev is not None and shares_prev > 0:
        if shares_now <= shares_prev * 1.01:
            score += 1; details.append('No meaningful dilution [PASS]')
        else:
            details.append('Share count increasing — dilution [WARN]')

    # 7. Gross margin improving YoY
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

    # ── ROIC from scratch (fallback when Finnhub roicTTM is None) ─────────
    # NOPAT / Invested Capital — never N/A if we have EBIT + equity
    if ebit and ebit > 0 and net_income is not None and equity > 0:
        # effective tax rate from EBIT vs net income (capped 0-40%)
        tax_rate = max(0.0, min(0.40, 1.0 - (net_income / ebit)))
        nopat = ebit * (1 - tax_rate)
        invested_capital = equity + total_debt - cash
        if invested_capital > 0:
            d['roic_computed'] = round((nopat / invested_capital) * 100, 1)

    # ── Gross margin trend YoY ────────────────────────────────────────────
    if gp_now and gp_prev and revenue and revenue_pr and revenue_pr > 0:
        gm_now_pct  = (gp_now / revenue) * 100
        gm_prev_pct = (gp_prev / revenue_pr) * 100
        d['gm_now_pct'] = round(gm_now_pct, 1)
        d['gm_trend']   = round(gm_now_pct - gm_prev_pct, 1)

    # ── Rule of 40 (revenue growth + FCF margin) ─────────────────────────
    rev_g = fundamentals.get('revenue_growth_yoy')
    fcf_mg = d.get('fcf_margin')
    if rev_g is not None and fcf_mg is not None:
        d['rule_of_40'] = round(rev_g + fcf_mg, 1)

    # ── D&A + CapEx/D&A ratio (Buffett: maintenance vs growth capex) ──────
    # D&A = EBITDA - EBIT (no separate line needed)
    if ebitda and ebit and ebitda > ebit:
        da = ebitda - ebit
        d['da'] = round(da)
        capex_abs = abs(cash_flow.get('capex', 0) or 0)
        if capex_abs > 0 and da > 0:
            # <1 = harvesting (low capex need) | 1-2 = maintaining | >2 = heavy growth investment
            d['capex_da_ratio'] = round(capex_abs / da, 2)

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

                    # Clean NaN
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


# ══════════════════════════════════════════════════════════════════════════════
#  4-PILLAR SCORING ENGINE (auto-scores — AI just reads the result)
# ══════════════════════════════════════════════════════════════════════════════

def score_quality(fundamentals, derived, bench):
    """Quality pillar (35%) — durability, margins, balance sheet."""
    score = 50
    details = []

    roic = fundamentals.get('roic')
    if roic is None:
        roic = derived.get('roic_computed')  # computed from scratch: NOPAT / Invested Capital
    b_roic = bench.get('roic')
    if roic is not None and b_roic is not None:
        if roic > b_roic * 1.2:
            score += 12; details.append(f"ROIC {roic:.1f}% >> sector {b_roic:.1f}% [+12]")
        elif roic > b_roic:
            score += 6; details.append(f"ROIC {roic:.1f}% > sector {b_roic:.1f}% [+6]")
        elif roic > b_roic * 0.7:
            score -= 3; details.append(f"ROIC {roic:.1f}% near sector {b_roic:.1f}% [-3]")
        else:
            score -= 10; details.append(f"ROIC {roic:.1f}% << sector {b_roic:.1f}% [-10]")
    elif roic is not None:
        if roic > 15:
            score += 5; details.append(f"ROIC {roic:.1f}% (no sector bench) [+5]")

    p_score = derived.get('piotroski_score', 0)
    p_max = derived.get('piotroski_max', 0)
    if p_max > 0:
        pct = p_score / p_max
        if pct >= 0.75:
            score += 10; details.append(f"Piotroski {p_score}/{p_max} STRONG [+10]")
        elif pct >= 0.5:
            score += 3; details.append(f"Piotroski {p_score}/{p_max} ADEQUATE [+3]")
        else:
            score -= 10; details.append(f"Piotroski {p_score}/{p_max} WEAK [-10]")

    fconv = derived.get('fcf_conversion')
    if fconv is not None:
        if fconv >= 1.0:
            score += 10; details.append(f"FCF Conversion {fconv:.2f} — quality earnings [+10]")
        elif fconv >= 0.8:
            score += 3; details.append(f"FCF Conversion {fconv:.2f} — acceptable [+3]")
        else:
            score -= 12; details.append(f"FCF Conversion {fconv:.2f} — ACCRUAL RISK [-12]")

    gm = fundamentals.get('gross_margin')
    b_om = bench.get('op_margin')
    if gm is not None and b_om is not None:
        if gm > b_om * 1.2:
            score += 5; details.append(f"Gross Margin {gm:.1f}% > sector op margin {b_om:.1f}% [+5]")
        elif gm < b_om * 0.5:
            score -= 5; details.append(f"Gross Margin {gm:.1f}% << sector op margin {b_om:.1f}% [-5]")

    # Gross margin trend YoY — is the moat expanding or eroding?
    gm_trend = derived.get('gm_trend')
    gm_now   = derived.get('gm_now_pct')
    if gm_trend is not None:
        if gm_trend > 2:
            score += 5; details.append(f"Gross margin expanding +{gm_trend:.1f}pp YoY [{gm_now:.1f}%] [+5]")
        elif gm_trend > 0:
            score += 2; details.append(f"Gross margin slightly improving +{gm_trend:.1f}pp YoY [+2]")
        elif gm_trend < -3:
            score -= 7; details.append(f"Gross margin contracting {gm_trend:.1f}pp YoY — competitive pressure [-7]")
        elif gm_trend < -1:
            score -= 3; details.append(f"Gross margin declining {gm_trend:.1f}pp YoY [-3]")

    nd = derived.get('net_debt_ebitda')
    if nd is not None:
        if nd < 0:
            score += 8; details.append(f"Net Cash position [+8]")
        elif nd < 2:
            score += 5; details.append(f"Net Debt/EBITDA {nd:.1f} — excellent [+5]")
        elif nd < 4:
            score += 2; details.append(f"Net Debt/EBITDA {nd:.1f} — healthy [+2]")
        elif nd < 5:
            score -= 3; details.append(f"Net Debt/EBITDA {nd:.1f} — caution [-3]")
        else:
            score -= 10; details.append(f"Net Debt/EBITDA {nd:.1f} — RISKY [-10]")

    ic = derived.get('interest_coverage')
    if ic is not None:
        if ic > 5:
            score += 5; details.append(f"Interest Coverage {ic:.1f}x — strong [+5]")
        elif ic > 3:
            score += 2; details.append(f"Interest Coverage {ic:.1f}x — healthy [+2]")
        elif ic > 1.5:
            score -= 3; details.append(f"Interest Coverage {ic:.1f}x — vulnerable [-3]")
        else:
            score -= 8; details.append(f"Interest Coverage {ic:.1f}x — DISTRESS [-8]")

    return {'score': max(0, min(100, round(score))), 'details': details}


def score_value(fundamentals, derived, stock_info, bench):
    """Value pillar (30%) — what you pay vs what you get."""
    score = 50
    details = []

    peg = derived.get('peg')
    b_peg = bench.get('peg')
    if peg is not None and peg > 0 and b_peg is not None:
        if peg < b_peg * 0.6:
            score += 15; details.append(f"PEG {peg:.2f} << sector {b_peg:.2f} — undervalued [+15]")
        elif peg < b_peg * 0.85:
            score += 8; details.append(f"PEG {peg:.2f} < sector {b_peg:.2f} — cheap [+8]")
        elif peg < b_peg * 1.15:
            score += 3; details.append(f"PEG {peg:.2f} ~ sector {b_peg:.2f} — fair [+3]")
        elif peg < b_peg * 1.5:
            score -= 5; details.append(f"PEG {peg:.2f} > sector {b_peg:.2f} — stretched [-5]")
        else:
            score -= 12; details.append(f"PEG {peg:.2f} >> sector {b_peg:.2f} — expensive [-12]")
    elif peg is not None and peg <= 0:
        score -= 5; details.append(f"PEG negative — growth concern [-5]")

    fwd_pe = stock_info.get('forwardPE') if stock_info else None
    pe = fwd_pe if fwd_pe else fundamentals.get('pe_ttm')
    b_pe = bench.get('fwd_pe')
    pe_label = "Fwd P/E" if fwd_pe else "P/E TTM"
    if pe is not None and pe > 0 and b_pe is not None:
        if pe < b_pe * 0.7:
            score += 10; details.append(f"{pe_label} {pe:.1f} << sector {b_pe:.1f} — cheap [+10]")
        elif pe < b_pe:
            score += 5; details.append(f"{pe_label} {pe:.1f} < sector {b_pe:.1f} — below peers [+5]")
        elif pe < b_pe * 1.3:
            details.append(f"{pe_label} {pe:.1f} ~ sector {b_pe:.1f} — in line [0]")
        else:
            score -= 8; details.append(f"{pe_label} {pe:.1f} > sector {b_pe:.1f} — premium [-8]")

    fcf = derived.get('fcf')
    mcap = stock_info.get('marketCap') if stock_info else None
    if not mcap:
        mcap_m = fundamentals.get('market_cap')
        mcap = mcap_m * 1_000_000 if mcap_m else None
    if fcf and mcap and mcap > 0:
        fy = (fcf / mcap) * 100
        if fy > 8:
            score += 10; details.append(f"FCF Yield {fy:.1f}% — very attractive [+10]")
        elif fy > 5:
            score += 7; details.append(f"FCF Yield {fy:.1f}% — attractive [+7]")
        elif fy > 3:
            score += 3; details.append(f"FCF Yield {fy:.1f}% — fair [+3]")
        elif fy > 0:
            details.append(f"FCF Yield {fy:.1f}% — low [0]")
        else:
            score -= 5; details.append(f"FCF Yield {fy:.1f}% — negative [-5]")

    # EV/EBITDA — most reliable cross-sector valuation (debt-adjusted)
    ev_ebitda = derived.get('ev_ebitda')
    b_ev = bench.get('ev_ebitda')
    if ev_ebitda is not None and b_ev is not None:
        if ev_ebitda < b_ev * 0.6:
            score += 10; details.append(f"EV/EBITDA {ev_ebitda:.1f}x << sector {b_ev:.1f}x — deeply cheap [+10]")
        elif ev_ebitda < b_ev * 0.85:
            score += 6; details.append(f"EV/EBITDA {ev_ebitda:.1f}x < sector {b_ev:.1f}x — cheap [+6]")
        elif ev_ebitda < b_ev * 1.2:
            score += 2; details.append(f"EV/EBITDA {ev_ebitda:.1f}x ~ sector {b_ev:.1f}x — fair [+2]")
        elif ev_ebitda < b_ev * 1.6:
            score -= 5; details.append(f"EV/EBITDA {ev_ebitda:.1f}x > sector {b_ev:.1f}x — stretched [-5]")
        else:
            score -= 10; details.append(f"EV/EBITDA {ev_ebitda:.1f}x >> sector {b_ev:.1f}x — expensive [-10]")
    elif ev_ebitda is not None:
        if ev_ebitda < 10:
            score += 5; details.append(f"EV/EBITDA {ev_ebitda:.1f}x — absolute value [+5]")
        elif ev_ebitda > 40:
            score -= 5; details.append(f"EV/EBITDA {ev_ebitda:.1f}x — very high multiple [-5]")

    return {'score': max(0, min(100, round(score))), 'details': details}


def score_growth(fundamentals, derived=None, bench_key=None):
    """Growth pillar (25%) — is the business accelerating?"""
    score = 50
    details = []

    rev_g = fundamentals.get('revenue_growth_yoy')
    if rev_g is not None:
        if rev_g > 30:
            score += 15; details.append(f"Revenue Growth {rev_g:.1f}% — explosive [+15]")
        elif rev_g > 20:
            score += 12; details.append(f"Revenue Growth {rev_g:.1f}% — strong [+12]")
        elif rev_g > 8:
            score += 6; details.append(f"Revenue Growth {rev_g:.1f}% — solid [+6]")
        elif rev_g > 0:
            details.append(f"Revenue Growth {rev_g:.1f}% — slow [0]")
        elif rev_g > -5:
            score -= 5; details.append(f"Revenue Growth {rev_g:.1f}% — slight decline [-5]")
        else:
            score -= 12; details.append(f"Revenue Growth {rev_g:.1f}% — declining [-12]")
    else:
        score -= 5; details.append("Revenue Growth N/A [-5]")

    eps_g = fundamentals.get('eps_growth_ttm')
    if eps_g is not None:
        if eps_g > 30:
            score += 12; details.append(f"EPS Growth TTM {eps_g:.1f}% — strong [+12]")
        elif eps_g > 15:
            score += 8; details.append(f"EPS Growth TTM {eps_g:.1f}% — good [+8]")
        elif eps_g > 0:
            score += 3; details.append(f"EPS Growth TTM {eps_g:.1f}% — positive [+3]")
        elif eps_g > -10:
            score -= 5; details.append(f"EPS Growth TTM {eps_g:.1f}% — declining [-5]")
        else:
            score -= 10; details.append(f"EPS Growth TTM {eps_g:.1f}% — sharp decline [-10]")
    else:
        score -= 3; details.append("EPS Growth N/A [-3]")

    eps_3y = fundamentals.get('eps_growth_3y')
    if eps_3y is not None:
        if eps_3y > 15:
            score += 5; details.append(f"EPS Growth 3Y {eps_3y:.1f}% — consistent [+5]")
        elif eps_3y > 0:
            score += 3; details.append(f"EPS Growth 3Y {eps_3y:.1f}% — positive [+3]")
        else:
            score -= 3; details.append(f"EPS Growth 3Y {eps_3y:.1f}% — weak [-3]")

    # ── Acceleration signals ──────────────────────────────────────────────
    if derived:
        eps_g_val  = fundamentals.get('eps_growth_ttm')
        eps_3y_val = fundamentals.get('eps_growth_3y')
        gm_trend   = derived.get('gm_trend')

        # EPS acceleration vs 3Y average
        if eps_g_val and eps_3y_val and eps_3y_val > 0:
            if eps_g_val > eps_3y_val * 1.3:
                score += 5; details.append(f"EPS accelerating: TTM {eps_g_val:.0f}% vs 3Y avg {eps_3y_val:.0f}% [+5]")
            elif eps_g_val < eps_3y_val * 0.7 and eps_g_val < eps_3y_val - 10:
                score -= 5; details.append(f"EPS decelerating: TTM {eps_g_val:.0f}% vs 3Y avg {eps_3y_val:.0f}% [-5]")

        # Operating leverage: revenue growing + margin expanding = compounding moat
        if rev_g and rev_g > 5 and gm_trend and gm_trend > 1:
            score += 5; details.append(f"Operating leverage: revenue +{rev_g:.0f}% + margin expansion +{gm_trend:.1f}pp [+5]")

        # Rule of 40 (software/semi only)
        if bench_key in ('software', 'semi'):
            r40 = derived.get('rule_of_40')
            if r40 is not None:
                if r40 >= 60:
                    score += 10; details.append(f"Rule of 40: {r40:.0f} — EXCELLENT (world-class) [+10]")
                elif r40 >= 40:
                    score += 6; details.append(f"Rule of 40: {r40:.0f} — strong [+6]")
                elif r40 >= 25:
                    score += 2; details.append(f"Rule of 40: {r40:.0f} — acceptable [+2]")
                else:
                    score -= 8; details.append(f"Rule of 40: {r40:.0f} — WEAK for {bench_key} [-8]")

    return {'score': max(0, min(100, round(score))), 'details': details}


def score_sentiment(insiders, earnings, stock_info):
    """Sentiment pillar (10%) — what smart money and market are doing."""
    score = 50
    details = []

    buys = sum(1 for t in insiders if t['action'] == 'BUY')
    sells = sum(1 for t in insiders if t['action'] == 'SELL')
    net = buys - sells
    if buys >= 3 and net > 0:
        score += 18; details.append(f"Cluster insider buying ({buys} buys) — very bullish [+18]")
    elif net > 0:
        score += 10; details.append(f"Net insider buying ({buys}B/{sells}S) — bullish [+10]")
    elif buys == 0 and sells == 0:
        details.append("No insider transactions [0]")
    elif net == 0:
        details.append(f"Balanced insider activity ({buys}B/{sells}S) [0]")
    elif sells > 3:
        score -= 8; details.append(f"Heavy insider selling ({sells} sells) — bearish [-8]")
    else:
        score -= 3; details.append(f"Net insider selling ({buys}B/{sells}S) [-3]")

    short_pct = 0
    if stock_info:
        si = stock_info.get('shortPercentOfFloat')
        if si is not None:
            try:
                short_pct = float(si) * 100
            except (TypeError, ValueError):
                short_pct = 0
    if short_pct > 0.1:
        if short_pct > 30:
            score -= 12; details.append(f"Short Interest {short_pct:.1f}% — extreme [-12]")
        elif short_pct > 20:
            score -= 8; details.append(f"Short Interest {short_pct:.1f}% — very high [-8]")
        elif short_pct > 10:
            score -= 4; details.append(f"Short Interest {short_pct:.1f}% — elevated [-4]")
        elif short_pct > 5:
            score -= 2; details.append(f"Short Interest {short_pct:.1f}% — moderate [-2]")
        elif short_pct < 3:
            score += 5; details.append(f"Short Interest {short_pct:.1f}% — very low [+5]")
        else:
            score += 3; details.append(f"Short Interest {short_pct:.1f}% — normal [+3]")

    beat_count = sum(1 for e in earnings if e.get('beat'))
    total_q = len(earnings) if earnings else 0
    if total_q > 0:
        if beat_count == total_q:
            score += 8; details.append(f"Earnings {beat_count}/{total_q} beats — perfect [+8]")
        elif beat_count >= total_q * 0.75:
            score += 5; details.append(f"Earnings {beat_count}/{total_q} beats — strong [+5]")
        elif beat_count >= total_q * 0.5:
            details.append(f"Earnings {beat_count}/{total_q} beats — mixed [0]")
        else:
            score -= 5; details.append(f"Earnings {beat_count}/{total_q} beats — weak [-5]")

    return {'score': max(0, min(100, round(score))), 'details': details}


def check_red_flags(fundamentals, derived, insiders, stock_info):
    """Auto-check all red flags. Returns list of triggered flags."""
    flags = []

    fconv = derived.get('fcf_conversion')
    if fconv is not None and fconv < 0.8:
        flags.append(f"FCF Conversion {fconv:.2f} < 0.8 — earnings not backed by cash")

    nd = derived.get('net_debt_ebitda')
    if nd is not None and nd > 5:
        flags.append(f"Net Debt/EBITDA {nd:.1f} > 5 — dangerous leverage")

    ic = derived.get('interest_coverage')
    if ic is not None and ic < 1.5:
        flags.append(f"Interest Coverage {ic:.1f}x < 1.5 — distress risk")

    rev_g = fundamentals.get('revenue_growth_yoy')
    net_m = fundamentals.get('net_margin')
    if rev_g is not None and rev_g < 0 and net_m is not None and net_m < 5:
        flags.append(f"Revenue declining ({rev_g:.1f}%) + low margins ({net_m:.1f}%)")

    eps_g = fundamentals.get('eps_growth_ttm')
    if rev_g is not None and eps_g is not None and rev_g > 0 and eps_g > rev_g * 3:
        flags.append(f"EPS growth ({eps_g:.0f}%) >>> revenue ({rev_g:.0f}%) — buyback engineering?")

    sells = [t for t in insiders if t['action'] == 'SELL']
    if len(sells) >= 4:
        flags.append(f"{len(sells)} insider sells — broad-based selling")

    for d in derived.get('piotroski_details', []):
        if 'OCF < Net Income' in d and 'WARN' in d:
            flags.append("OCF < Net Income — accrual quality risk")
            break

    if stock_info:
        si = stock_info.get('shortPercentOfFloat')
        if si is not None:
            try:
                sp = float(si) * 100
                if sp > 20:
                    flags.append(f"Short interest {sp:.1f}% — heavy short pressure")
            except (TypeError, ValueError):
                pass

    return flags


def generate_highlights(q, v, g, s, total, red_flags, fundamentals, derived, bench_key, insiders, earnings):
    """Auto-generate key highlights from scoring results."""
    highlights = []
    bench = SECTOR_BENCHMARKS.get(bench_key, {})

    pillars = [('Quality', q), ('Value', v), ('Growth', g), ('Sentiment', s)]
    best = max(pillars, key=lambda x: x[1])
    worst = min(pillars, key=lambda x: x[1])
    if best[1] >= 70:
        highlights.append(f"  * {best[0]} score {best[1]}/100 -- POSITIVE (strongest pillar)")
    if worst[1] < 40:
        highlights.append(f"  * {worst[0]} score {worst[1]}/100 -- NEGATIVE (weakest pillar)")

    peg = derived.get('peg')
    b_peg = bench.get('peg')
    if peg and b_peg and peg > 0 and peg < b_peg * 0.7:
        highlights.append(f"  * PEG {peg:.2f} vs sector {b_peg:.2f} -- POSITIVE (value opportunity)")
    elif peg and b_peg and peg > b_peg * 1.5:
        highlights.append(f"  * PEG {peg:.2f} vs sector {b_peg:.2f} -- NEGATIVE (overvalued vs growth)")

    roic = fundamentals.get('roic')
    if roic and roic > 20:
        highlights.append(f"  * ROIC {roic:.1f}% -- POSITIVE (moat signal, value creation)")

    fconv = derived.get('fcf_conversion')
    if fconv is not None and fconv >= 1.2:
        highlights.append(f"  * FCF Conversion {fconv:.2f} -- POSITIVE (high quality earnings)")
    elif fconv is not None and fconv < 0.8:
        highlights.append(f"  * FCF Conversion {fconv:.2f} -- NEGATIVE (earnings quality concern)")

    if earnings:
        beats = sum(1 for e in earnings if e.get('beat'))
        if beats == len(earnings) and len(earnings) >= 3:
            highlights.append(f"  * Earnings {beats}/{len(earnings)} beats -- POSITIVE (perfect streak)")
        elif beats == 0 and len(earnings) >= 3:
            highlights.append(f"  * Earnings 0/{len(earnings)} beats -- NEGATIVE (consistent misses)")

    buys = sum(1 for t in insiders if t['action'] == 'BUY')
    sells_count = sum(1 for t in insiders if t['action'] == 'SELL')
    if buys >= 3:
        highlights.append(f"  * {buys} insider buys (cluster) -- POSITIVE (high conviction)")
    elif sells_count >= 4:
        highlights.append(f"  * {sells_count} insider sells -- NEGATIVE (broad selling)")

    nd = derived.get('net_debt_ebitda')
    if nd is not None and nd < 0:
        highlights.append(f"  * Net cash position -- POSITIVE (fortress balance sheet)")
    elif nd is not None and nd > 5:
        highlights.append(f"  * Net Debt/EBITDA {nd:.1f} -- NEGATIVE (high leverage)")

    for flag in red_flags[:2]:
        highlights.append(f"  * RED FLAG: {flag}")

    return highlights


def classify_moat(fundamentals, derived, bench_key):
    """
    Classify moat type from financial fingerprint — Buffett framework.
    No judgment required: pure financial signature detection.
    """
    roic      = fundamentals.get('roic') or derived.get('roic_computed')
    gm        = fundamentals.get('gross_margin')
    fcf_mg    = derived.get('fcf_margin')
    gm_trend  = derived.get('gm_trend')
    capex_da  = derived.get('capex_da_ratio')

    moat_type  = "UNCLEAR"
    durability = "MEDIUM"
    signals    = []
    warning    = ""

    if roic is not None and gm is not None:
        if roic > 20 and gm > 40:
            if capex_da is not None and capex_da < 0.6:
                moat_type = "ASSET-LIGHT COMPOUNDER"
                signals.append(f"ROIC {roic:.1f}% + gross margin {gm:.1f}% + CapEx/D&A {capex_da:.2f}x (minimal reinvestment)")
            elif bench_key == 'software':
                moat_type = "SWITCHING COST MOAT"
                signals.append(f"ROIC {roic:.1f}% + high gross margin {gm:.1f}% (SaaS fingerprint)")
            else:
                moat_type = "BRAND / INTANGIBLE MOAT"
                signals.append(f"ROIC {roic:.1f}% + high gross margin {gm:.1f}%")
        elif roic > 15 and gm < 30:
            moat_type = "COST ADVANTAGE / SCALE"
            signals.append(f"ROIC {roic:.1f}% despite low gross margin {gm:.1f}% — scale efficiency")
        elif roic > 15 and capex_da is not None and capex_da > 2:
            moat_type = "CAPITAL-INTENSIVE COMPOUNDER"
            signals.append(f"ROIC {roic:.1f}% with heavy reinvestment (CapEx/D&A {capex_da:.1f}x)")
        elif roic < 8:
            moat_type = "NO CLEAR MOAT"
            signals.append(f"ROIC {roic:.1f}% — likely below cost of capital")
        else:
            moat_type = "NARROW MOAT"
            signals.append(f"ROIC {roic:.1f}% — modest competitive advantage")
    elif roic is not None:
        if roic > 20:
            moat_type = "MOAT LIKELY (gross margin N/A)"
        elif roic < 8:
            moat_type = "NO CLEAR MOAT"

    # Durability — is the moat widening or eroding?
    if gm_trend is not None and gm_trend > 1 and roic and roic > 15:
        durability = "HIGH (moat expanding)"
    elif gm_trend is not None and gm_trend < -2:
        durability = "LOW (margins eroding — moat under pressure)"
    elif roic is not None and roic > 30:
        durability = "HIGH (sustained ROIC far above cost of capital)"
    elif roic is not None and roic > 15:
        durability = "MEDIUM-HIGH"

    # Buffett warning: high-change industries erode moats
    if bench_key == 'semi':
        warning = "[!] Semiconductor — moat requires constant R&D spend to defend"
    elif bench_key == 'software' and (roic is None or roic < 20):
        warning = "[!] Software — watch NRR and churn; narrow moats disappear fast"

    # CapEx/D&A context
    if capex_da is not None:
        if capex_da < 0.5:
            signals.append("Capital-light: CapEx << D&A — Buffett's ideal (cash machine)")
        elif capex_da < 1.2:
            signals.append(f"Maintenance mode: CapEx ~ D&A ({capex_da:.2f}x)")
        elif capex_da < 2.5:
            signals.append(f"Growth investment: CapEx > D&A ({capex_da:.2f}x) — expect future FCF expansion")
        else:
            signals.append(f"Heavy capex ({capex_da:.2f}x D&A) — verify returns justify reinvestment")

    return {'type': moat_type, 'durability': durability, 'signals': signals, 'warning': warning}


def run_scenario_engine(q_score, v_score, g_score, s_score, base_total):
    """
    ARK + Ackman scenario analysis: Bull / Base / Bear + Expected Value.
    Bull: growth accelerates, moat strengthening
    Bear: growth disappoints, multiple compresses, competitive pressure
    """
    # BULL: business executes well — growth +15, quality strengthens +5
    bull_q = min(100, q_score + 5)
    bull_g = min(100, g_score + 15)
    bull_total = max(0, min(100, round(bull_q * 0.35 + v_score * 0.30 + bull_g * 0.25 + s_score * 0.10)))

    # BEAR: growth disappoints -20, multiple compresses -15, competitive pressure -10 quality
    bear_q = max(0, q_score - 10)
    bear_v = max(0, v_score - 15)
    bear_g = max(0, g_score - 20)
    bear_total = max(0, min(100, round(bear_q * 0.35 + bear_v * 0.30 + bear_g * 0.25 + s_score * 0.10)))

    # Expected Value — equal probability tails (25/50/25)
    ev = round(0.25 * bull_total + 0.50 * base_total + 0.25 * bear_total)

    def sig(score):
        return "BULLISH" if score >= 70 else ("NEUTRAL" if score >= 45 else "BEARISH")

    return {
        'bull':    bull_total,
        'base':    base_total,
        'bear':    bear_total,
        'ev':      ev,
        'upside':  bull_total - base_total,
        'downside': bear_total - base_total,
        'bull_sig': sig(bull_total),
        'base_sig': sig(base_total),
        'bear_sig': sig(bear_total),
        'ev_sig':  sig(ev),
    }


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

    print(sep)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python finnhub_stock_analyzer.py <TICKER> [--verbose]")
        print("Example: python finnhub_stock_analyzer.py NFLX")
        sys.exit(1)

    _args  = [a for a in sys.argv[1:] if not a.startswith('--')]
    ticker = _args[0].upper().replace('$', '') if _args else 'NFLX'
    VERBOSE = '--verbose' in sys.argv or '-v' in sys.argv

    _t0 = time.time()
    print(f"Fetching data for ${ticker}...", end=' ', flush=True)

    def _get_info():
        try:
            return (yf.Ticker(ticker).info or {}) if YF_AVAILABLE else {}
        except Exception:
            return {}

    # ── parallel fetch — all API calls run simultaneously ─────────────────
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as _ex:
        _ff = _ex.submit(get_fundamentals,      ticker)
        _fb = _ex.submit(get_balance_sheet,     ticker)
        _fc = _ex.submit(get_cash_flow,         ticker)
        _fi = _ex.submit(get_income_stmt,       ticker)
        _fe = _ex.submit(get_earnings,          ticker)
        _fn = _ex.submit(get_news,              ticker)
        _fk = _ex.submit(get_insiders,          ticker)
        _ft = _ex.submit(get_next_catalyst,     ticker)
        _fq = _ex.submit(get_quarterly_revenue, ticker)
        _fo = _ex.submit(_get_info)
        fundamentals  = _ff.result()
        balance_sheet = _fb.result()
        cash_flow     = _fc.result()
        income_stmt   = _fi.result()
        earnings      = _fe.result()
        news          = _fn.result()
        insiders      = _fk.result()
        catalyst      = _ft.result()
        quarterly_rev = _fq.result()
        stock_info    = _fo.result()

    print(f"{time.time() - _t0:.1f}s")
    derived = compute_derived(fundamentals, balance_sheet, cash_flow, income_stmt)

    # ── compute EV/EBITDA (requires market cap from stock_info) ───────────
    mcap = stock_info.get('marketCap')
    if not mcap:
        mcap_m = fundamentals.get('market_cap')
        mcap = mcap_m * 1_000_000 if mcap_m else None
    net_debt_ev = derived.get('net_debt', 0) or 0
    ebitda_ev   = income_stmt.get('ebitda')
    if mcap and ebitda_ev and ebitda_ev > 0:
        derived['ev']       = mcap + net_debt_ev
        derived['ev_ebitda'] = round((mcap + net_debt_ev) / ebitda_ev, 1)

    # ── buyback yield + total shareholder yield ────────────────────────────
    sn = income_stmt.get('shares_now')
    sp = income_stmt.get('shares_prior')
    if sn and sp and sp > 0 and sn < sp:
        derived['buyback_yield'] = round((sp - sn) / sp * 100, 2)
    div_raw = stock_info.get('dividendYield') or 0
    try:
        derived['dividend_yield'] = round(float(div_raw) * 100, 2)
    except (TypeError, ValueError):
        derived['dividend_yield'] = 0
    derived['total_shareholder_yield'] = round(
        (derived.get('buyback_yield') or 0) + derived['dividend_yield'], 2
    )

    # ── verbose: raw data sections 1-10 (only with --verbose flag) ───────
    if VERBOSE:
        print_results(ticker, fundamentals, balance_sheet, cash_flow,
                      income_stmt, derived, earnings, news, insiders, catalyst)

    # ── sector + benchmarks ───────────────────────────────────────────────
    bench_key = detect_sector(stock_info)
    bench     = SECTOR_BENCHMARKS.get(bench_key, SECTOR_BENCHMARKS['market'])

    # ── 4-pillar scoring ──────────────────────────────────────────────────
    q = score_quality(fundamentals, derived, bench)
    v = score_value(fundamentals, derived, stock_info, bench)
    g = score_growth(fundamentals, derived, bench_key)
    s = score_sentiment(insiders, earnings, stock_info)

    # ── verbose: pillar detail ─────────────────────────────────────────────
    if VERBOSE:
        sep_v = '=' * 65
        print(f"\n=== 4-PILLAR SCORING (VERBOSE) ===")
        for pillar, name in [(q, 'QUALITY (35%)'), (v, 'VALUE (30%)'), (g, 'GROWTH (25%)'), (s, 'SENTIMENT (10%)')]:
            print(f"\n--- {name} ---")
            for detail in pillar['details']:
                print(f"  {detail}")
            print(f"  Score: {pillar['score']}/100")
        if bench_key in ('software', 'semi'):
            r40 = derived.get('rule_of_40')
            if r40 is not None:
                r40g = "EXCELLENT" if r40 >= 60 else ("STRONG" if r40 >= 40 else ("ACCEPTABLE" if r40 >= 25 else "WEAK"))
                print(f"\n--- RULE OF 40 ({bench_key.upper()}) ---")
                print(f"  {fundamentals.get('revenue_growth_yoy', 0) or 0:.1f}% Rev + {derived.get('fcf_margin', 0) or 0:.1f}% FCF = {r40:.0f} — {r40g}")

    # ── red flags ─────────────────────────────────────────────────────────
    red_flags = check_red_flags(fundamentals, derived, insiders, stock_info)

    # ── override rules ────────────────────────────────────────────────────
    q_final = q['score']
    fconv   = derived.get('fcf_conversion')
    if fconv is not None and fconv < 0.8:
        q_final = min(q_final, 40)

    w_q = q_final    * 0.35
    w_v = v['score'] * 0.30
    w_g = g['score'] * 0.25
    w_s = s['score'] * 0.10
    total = round(w_q + w_v + w_g + w_s)

    nd      = derived.get('net_debt_ebitda')
    fcf_val = derived.get('fcf')
    forced_bearish = False
    if len(red_flags) >= 3:
        total = min(total, 40); forced_bearish = True
    if nd is not None and nd > 5 and fcf_val is not None and fcf_val < 0:
        total = min(total, 35); forced_bearish = True

    peg_val      = derived.get('peg')
    b_peg        = bench.get('peg')
    p_score      = derived.get('piotroski_score', 0)
    p_max        = derived.get('piotroski_max', 1)
    insider_buys = sum(1 for t in insiders if t['action'] == 'BUY')
    if (insider_buys >= 3 and p_max > 0 and p_score / p_max >= 0.75
            and peg_val and b_peg and peg_val < b_peg):
        total = min(total + 5, 100)

    total = max(0, min(100, total))
    signal = "BULLISH" if total >= 70 else ("NEUTRAL" if total >= 45 else "BEARISH")
    if forced_bearish:
        signal = "BEARISH"
    confidence = ("HIGH" if (total >= 80 or total <= 20) else
                  "MEDIUM-HIGH" if (total >= 70 or total <= 30) else "MEDIUM")

    # ── moat + scenario ───────────────────────────────────────────────────
    moat      = classify_moat(fundamentals, derived, bench_key)
    scenarios = run_scenario_engine(q_final, v['score'], g['score'], s['score'], total)

    # ══════════════════════════════════════════════════════════════════════
    #  COMPACT OUTPUT — all signal, no noise
    # ══════════════════════════════════════════════════════════════════════
    sep = '=' * 65
    print(f"\n{sep}")
    print(f"  FUNDAMENTAL ANALYSIS: ${ticker}")
    print(f"{sep}")

    # Sector + price + 52W
    yf_sector  = stock_info.get('sector', 'Unknown')
    yf_ind     = stock_info.get('industry', 'Unknown')
    curr_price = stock_info.get('currentPrice') or stock_info.get('regularMarketPrice')
    w52_high   = fundamentals.get('52w_high')
    w52_low    = fundamentals.get('52w_low')
    beta       = fundamentals.get('beta')
    print(f"  Sector:    {yf_sector} | {yf_ind} | Benchmark: {bench_key}")
    if curr_price and w52_high and w52_low and w52_high > w52_low:
        rng = (curr_price - w52_low) / (w52_high - w52_low) * 100
        pos = "near HIGH" if rng > 75 else ("mid-range" if rng > 40 else "near LOW")
        beta_s = f" | Beta {beta:.2f}" if beta else ""
        print(f"  Price:     ${curr_price:.2f} | 52W ${w52_low:.2f}-${w52_high:.2f} | {rng:.0f}% of range ({pos}){beta_s}")

    # Valuation
    pe     = fundamentals.get('pe_ttm')
    fwd_pe = stock_info.get('forwardPE')
    peg    = derived.get('peg')
    pb     = fundamentals.get('pb_annual')
    ps     = fundamentals.get('ps_annual')
    ev_eb  = derived.get('ev_ebitda')
    parts  = []
    if pe:     parts.append(f"P/E {pe:.1f}")
    if fwd_pe: parts.append(f"Fwd P/E {fwd_pe:.1f} (sector {bench.get('fwd_pe','N/A')})")
    if peg:    parts.append(f"PEG {peg:.2f} (sector {bench.get('peg','N/A')})")
    if pb:     parts.append(f"P/B {pb:.1f}")
    if ev_eb:  parts.append(f"EV/EBITDA {ev_eb:.1f}x (sector {bench.get('ev_ebitda','N/A')}x)")
    if mcap:   parts.append(f"MCap ${mcap/1e9:.1f}B")
    print(f"  VALUATION: {' | '.join(parts)}")

    # Quality
    roic_val = fundamentals.get('roic') or derived.get('roic_computed')
    roic_src = '' if fundamentals.get('roic') else '*'
    gm       = fundamentals.get('gross_margin')
    gm_trend = derived.get('gm_trend')
    nm       = fundamentals.get('net_margin')
    fcf      = derived.get('fcf')
    fcf_m    = derived.get('fcf_margin')
    nd_eb    = derived.get('net_debt_ebitda')
    ic_val   = derived.get('interest_coverage')
    capex_da = derived.get('capex_da_ratio')
    p_sc     = derived.get('piotroski_score', 0)
    p_mx     = derived.get('piotroski_max', 0)
    parts    = []
    if roic_val: parts.append(f"ROIC {roic_src}{roic_val:.1f}% (sector {bench.get('roic','N/A')}%)")
    if gm:
        gm_s = f"GM {gm:.1f}%"
        if gm_trend is not None: gm_s += f" ({gm_trend:+.1f}pp YoY)"
        parts.append(gm_s)
    if nm:        parts.append(f"NM {nm:.1f}%")
    if fcf and fcf_m: parts.append(f"FCF ${fcf/1e9:.1f}B ({fcf_m:.1f}%)")
    if fconv:    parts.append(f"FCFConv {fconv:.2f}")
    if nd_eb is not None: parts.append(f"ND/EBITDA {nd_eb:.1f}")
    if ic_val:   parts.append(f"IntCov {ic_val:.1f}x")
    if capex_da: parts.append(f"CapEx/D&A {capex_da:.2f}x")
    if p_mx:     parts.append(f"Piotroski {p_sc}/{p_mx}")
    print(f"  QUALITY:   {' | '.join(parts)}")

    # Growth
    rev_g  = fundamentals.get('revenue_growth_yoy')
    eps_g  = fundamentals.get('eps_growth_ttm')
    eps_3y = fundamentals.get('eps_growth_3y')
    r40    = derived.get('rule_of_40')
    parts  = []
    if rev_g  is not None: parts.append(f"Rev {rev_g:+.1f}% YoY")
    # Quarterly revenue trend (QoQ sequential)
    _qg = (quarterly_rev or {}).get('qoq_growth', [])
    _qt = (quarterly_rev or {}).get('trend', '')
    if _qg:
        parts.append(f"QoQ: {'→'.join(f'{g:+.1f}%' for g in _qg)} ({_qt})")
    if eps_g  is not None: parts.append(f"EPS TTM {eps_g:+.1f}%")
    if eps_3y is not None: parts.append(f"EPS 3Y {eps_3y:+.1f}%")
    if r40 is not None and bench_key in ('software', 'semi'): parts.append(f"Rule40 {r40:.0f}")
    if rev_g and rev_g > 5 and gm_trend and gm_trend > 1: parts.append("OpLev YES")
    print(f"  GROWTH:    {' | '.join(parts)}")

    # Sentiment
    n_buys  = sum(1 for t in insiders if t['action'] == 'BUY')
    n_sells = sum(1 for t in insiders if t['action'] == 'SELL')
    si_raw  = stock_info.get('shortPercentOfFloat')
    beats   = sum(1 for e in earnings if e.get('beat'))
    tot_q   = len(earnings)
    next_e  = (catalyst or {}).get('date')
    parts   = []
    if tot_q:  parts.append(f"Beats {beats}/{tot_q}")
    parts.append(f"Insiders {n_buys}B/{n_sells}S")
    if si_raw: parts.append(f"Short {float(si_raw)*100:.1f}%")
    _bb = derived.get('buyback_yield')
    _dy = derived.get('dividend_yield', 0)
    _ty = derived.get('total_shareholder_yield', 0)
    if _bb:          parts.append(f"Buyback {_bb:.1f}%")
    if _dy:          parts.append(f"Div {_dy:.1f}%")
    if _ty and _ty > 0.3: parts.append(f"TotalYield {_ty:.1f}%")
    if next_e: parts.append(f"Next earnings {next_e}")
    print(f"  SENTIMENT: {' | '.join(parts)}")

    # News (2 headlines)
    if news:
        hl = ' | '.join((n.get('headline') or '')[:55] for n in news[:2])
        print(f"  NEWS:      {hl}")

    print()

    # Moat
    moat_warn = f" | {moat['warning']}" if moat['warning'] else ""
    print(f"  MOAT:      {moat['type']} | Durability: {moat['durability']}{moat_warn}")
    if moat['signals']:
        print(f"             {' | '.join(moat['signals'][:2])}")

    # Scenarios
    asym = "FAVORABLE" if abs(scenarios['upside']) > abs(scenarios['downside']) else "UNFAVORABLE"
    print(f"  SCENARIOS: Bull {scenarios['bull']} {scenarios['bull_sig']} | Base {scenarios['base']} {scenarios['base_sig']} | Bear {scenarios['bear']} {scenarios['bear_sig']} | EV {scenarios['ev']} {scenarios['ev_sig']} | {asym}")

    # Red flags
    if red_flags:
        print(f"  RED FLAGS: {' | '.join(red_flags)}")
    else:
        print(f"  RED FLAGS: None")

    # Pillars
    print(f"  PILLARS:   Quality {q_final}/100 (35%) | Value {v['score']}/100 (30%) | Growth {g['score']}/100 (25%) | Sentiment {s['score']}/100 (10%)")

    print()
    print(f"{sep}")
    forced_s = " [CAPPED — red flags]" if forced_bearish else ""
    print(f"  SCORE:  {total}/100  {signal}{forced_s}  |  EV: {scenarios['ev']}/100  {scenarios['ev_sig']}  |  Confidence: {confidence}")
    print(f"{sep}")
