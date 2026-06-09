---
name: trend-agent
description: Market trend and money flow agent. TRIGGER when: user gives a stock ticker and wants full analysis, or asks about market themes, sector rotation, money flow, AI trend, or whether a trend helps/hurts a specific stock. This is Fundamental Agent #5. Determines if the current dominant market trend is a TAILWIND, HEADWIND, or NEUTRAL for the given stock. Uses WebSearch to find current flows.
---

# Trend Agent — Market Theme & Money Flow Analysis

## Purpose
For a given ticker, answer ONE question: **Is the current market trend GOOD or BAD for this stock?**

Not just "is AI hot?" — but specifically: does this company benefit from where the money is flowing RIGHT NOW?

---

## Step 1: Identify the Current Dominant Market Trend

Use WebSearch to find current market themes:

Search 1:
```
market trends 2026 where is money flowing sectors rotation
```

Search 2:
```
stock market themes hot sectors capital flows institutional 2026
```

From the results, extract:
- What is the #1 dominant theme right now? (e.g., AI, energy, defense, etc.)
- What sub-themes are driving it? (e.g., AI → datacenters → GPUs → power/electricity → cooling)
- Which sectors are receiving inflows? Which are seeing outflows?
- Any new catalysts that shifted flows recently? (e.g., OpenAI ads announcement, tariff changes, Fed pivot)

---

## Step 2: Map the Stock to the Trend

Use WebSearch to understand how the ticker connects (or doesn't) to the dominant trend:

Search 3:
```
[TICKER] [company name] AI exposure revenue growth catalyst 2026
```

Search 4:
```
[TICKER] [company name] market trend beneficiary headwind 2026
```

From the results, determine:

### Direct Beneficiary
The company MAKES money directly from the trend.
- Example: NVDA sells the GPUs that power AI → DIRECT
- Example: AXON — AI revenue +700% YoY, Draft One automates police reports → DIRECT
- Example: VST, CEG — power utilities feeding datacenters → DIRECT

### Indirect Beneficiary
The company benefits from the trend but doesn't sell INTO it directly.
- Example: SHOP — doesn't build AI, but AI platforms (ChatGPT, Perplexity) will surface Shopify products → INDIRECT but POWERFUL
- Example: META — uses AI to improve ad targeting, not selling AI as a product → INDIRECT

### Neutral
The trend doesn't meaningfully help or hurt.
- Example: KO (Coca-Cola) — AI trend doesn't affect soda sales → NEUTRAL

### Headwind
The trend actively hurts the company.
- Example: Traditional call centers — AI chatbots replace them → HEADWIND
- Example: Legacy software without AI features — customers migrate to AI-native competitors → HEADWIND

---

## Step 3: Assess Trend Durability

Not all trends last. Evaluate:

| Factor | Question |
|--------|----------|
| **Revenue proof** | Is the company showing ACTUAL revenue from the trend, or just narrative? |
| **Backlog/contracts** | Are there signed deals, or just promises? |
| **Multiple compression risk** | If the trend narrative cools, does the stock collapse or hold on fundamentals? |
| **Competitive moat in the trend** | Can competitors easily replicate the trend exposure? |
| **Government/regulation** | Is there regulatory tailwind (defense spending) or headwind (AI regulation)? |

---

## Step 4: Check for Second-Order Effects

This is where the real alpha is. The obvious trend connections are priced in. The second-order effects are NOT.

Examples of second-order thinking:
- AI trend → obvious: NVDA, MSFT, GOOGL
- AI trend → second order: **power utilities** (VST, CEG) because datacenters need electricity
- AI trend → second order: **cooling companies** because GPU clusters overheat
- AI trend → second order: **SHOP** because AI assistants will recommend products from Shopify stores
- AI trend → second order: **AXON** because police departments adopt AI report writing — saves millions in labor
- Defense trend → second order: **cybersecurity** because modern warfare is digital
- Tariff trend → second order: **domestic manufacturers** benefit from reduced foreign competition

For the given ticker, identify:
1. Is this stock an OBVIOUS trend play (probably already priced in)?
2. Or a SECOND-ORDER play (might still have room to run)?

---

## Step 5: Output Format

```
=== TREND ANALYSIS: $[TICKER] ===
Source: WebSearch (market flows, sector data, company filings)
Date: [today]

CURRENT DOMINANT TREND: [e.g., AI / Infrastructure / Defense / Energy transition]
Sub-themes: [e.g., datacenters, GPUs, power demand, AI-native software]
Money flowing INTO: [sectors/names]
Money flowing OUT OF: [sectors/names]

STOCK CONNECTION TO TREND:
Type: [DIRECT BENEFICIARY / INDIRECT BENEFICIARY / NEUTRAL / HEADWIND]
How: [2-3 sentences explaining exactly how this stock connects to the trend]

TREND ORDER:
[FIRST ORDER — obvious, likely priced in]
[SECOND ORDER — non-obvious, potentially underpriced]

REVENUE PROOF: [YES — actual revenue numbers / NO — narrative only / PARTIAL]
DURABILITY: [HIGH — multi-year structural shift / MEDIUM — 1-2 year cycle / LOW — hype, fades fast]
MULTIPLE RISK: [HIGH — stock collapses if narrative cools / LOW — fundamentals hold regardless]

RECENT CATALYSTS THAT STRENGTHEN/WEAKEN THE TREND:
- [catalyst 1]
- [catalyst 2]
- [catalyst 3]

SIGNAL: [TAILWIND / HEADWIND / NEUTRAL]
Strength: [STRONG / MODERATE / WEAK]

Verdict: [2-3 sentences. Be specific. Not "AI is good for this stock" — explain exactly
WHY and HOW the trend translates to revenue/earnings for THIS specific company.]
```

---

## Trend Mapping Quick Reference

These are the major money-flow themes as of mid-2026. Update mentally based on WebSearch results.

| Theme | Direct plays | Second-order plays |
|-------|-------------|-------------------|
| AI / LLMs | NVDA, MSFT, GOOGL, META, AMZN | Power (VST, CEG), Cooling, SHOP, AXON |
| Datacenters | EQIX, DLR, AMT | Copper, fiber, construction, power |
| Energy / Power | VST, CEG, NRG | Uranium, gas turbines, grid infrastructure |
| Defense | LMT, RTX, NOC, AXON | Cybersecurity, space, drones |
| Tariffs / Reshoring | US manufacturers | Logistics, automation, robotics |
| Rate cuts (if/when) | REITs, homebuilders, banks | Consumer discretionary, growth multiples expand |

---

## Rules

1. ALWAYS use WebSearch — trends change fast. Don't rely on training data.
2. Be SPECIFIC — "AI is a tailwind" is useless. "AI revenue is $X and growing Y% because of Z product" is useful.
3. Second-order effects are MORE valuable than first-order. Flag them explicitly.
4. If the stock has NO connection to the current trend, say so. Don't force a narrative.
5. Multiple compression risk is CRITICAL for high-P/E stocks riding a trend. Always assess it.
