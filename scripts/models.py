from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Fundamentals:
    w52_high: float | None = None
    w52_low: float | None = None
    pe_ttm: float | None = None
    pb_annual: float | None = None
    ps_annual: float | None = None
    revenue_growth_yoy: float | None = None
    eps_growth_ttm: float | None = None
    eps_growth_3y: float | None = None
    net_margin: float | None = None
    gross_margin: float | None = None
    current_ratio: float | None = None
    debt_to_equity: float | None = None
    roe: float | None = None
    roa: float | None = None
    roic: float | None = None
    beta: float | None = None
    market_cap: float | None = None


@dataclass
class BalanceSheet:
    long_term_debt: float = 0.0
    short_term_debt: float = 0.0
    capital_leases: float = 0.0
    total_financial_debt: float = 0.0
    total_equity: float = 0.0
    total_liabilities: float = 0.0
    cash: float = 0.0
    shares: float | None = None
    de_ratio_actual: float | None = None
    de_prior: float | None = None
    source: str = 'unknown'


@dataclass
class CashFlow:
    ocf: float | None = None
    capex: float | None = None
    fcf: float | None = None
    ocf_prior: float | None = None
    source: str = 'unknown'


@dataclass
class IncomeStatement:
    revenue: float | None = None
    revenue_prior: float | None = None
    ebit: float | None = None
    ebitda: float | None = None
    net_income: float | None = None
    interest_exp: float | None = None
    gross_profit: float | None = None
    gp_prior: float | None = None
    shares_now: float | None = None
    shares_prior: float | None = None
    source: str = 'unknown'


@dataclass
class DerivedMetrics:
    peg: float | None = None
    fcf: float | None = None
    fcf_margin: float | None = None
    fcf_conversion: float | None = None
    net_debt: float = 0.0
    net_debt_ebitda: float | None = None
    interest_coverage: float | None = None
    piotroski_score: int = 0
    piotroski_max: int = 0
    piotroski_details: list[str] = field(default_factory=list)
    roic_computed: float | None = None
    gm_now_pct: float | None = None
    gm_trend: float | None = None
    rule_of_40: float | None = None
    da: float | None = None
    capex_da_ratio: float | None = None
    ev: float | None = None
    ev_ebitda: float | None = None
    buyback_yield: float | None = None
    dividend_yield: float = 0.0
    total_shareholder_yield: float = 0.0


@dataclass
class ScoringResult:
    score: int
    details: list[str]


@dataclass
class EarningsRecord:
    period: str
    actual: float | None
    estimate: float | None
    surprise_pct: float | None
    beat: bool | None
    source: str


@dataclass
class NewsItem:
    headline: str | None
    date: int | None


@dataclass
class InsiderTransaction:
    name: str | None
    action: str
    shares: int | None
    price: float | None
    date: str | None
    code: str | None


@dataclass
class Catalyst:
    date: str | None = None
    eps_estimate: float | None = None
    revenue_est: float | None = None


@dataclass
class QuarterlyRevenue:
    quarters: list[dict] = field(default_factory=list)
    qoq_growth: list[float] = field(default_factory=list)
    trend: str = ''


@dataclass
class MoatAnalysis:
    type: str = 'UNCLEAR'
    durability: str = 'MEDIUM'
    signals: list[str] = field(default_factory=list)
    warning: str = ''


@dataclass
class ScenarioAnalysis:
    bull: int = 0
    base: int = 0
    bear: int = 0
    ev: int = 0
    upside: int = 0
    downside: int = 0
    bull_sig: str = ''
    base_sig: str = ''
    bear_sig: str = ''
    ev_sig: str = ''


# ── Agent 2: Institutional ────────────────────────────────────────────────────
@dataclass
class HolderRecord:
    name: str
    pct: float
    shares: int
    change: float
    direction: str
    tag: str
    is_big3: bool
    is_notable: bool
    is_activist: bool


# ── Agent 3: Analyst ──────────────────────────────────────────────────────────
@dataclass
class AnalystAction:
    date: str
    firm: str
    grade_str: str
    pt_str: str
    action: str
    pt_action: str
    current_pt: float
    prior_pt: float
    to_grade: str
    from_grade: str
    is_tier1: bool


# ── Agent 5: Trend ────────────────────────────────────────────────────────────
@dataclass
class SectorData:
    name: str
    ret_1w: float = 0.0
    ret_1m: float = 0.0
    ret_3m: float = 0.0


# ── Orchestrator ──────────────────────────────────────────────────────────────
@dataclass
class AgentResult:
    name: str
    script: str
    output: str = ''
    score: int | None = None
    signal: str = 'UNKNOWN'
    error: str | None = None
