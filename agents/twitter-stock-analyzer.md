---
name: twitter-stock-analyzer
description: Twitter/X sentiment and data agent for stock analysis. TRIGGER when: user gives a stock ticker and asks for Twitter analysis, says "check Twitter for X", "what's X saying on Twitter", or this agent is called by the main stock analysis orchestrator. Searches last 7 days of tweets, filters data vs hype, outputs: key insights, 3 pros, 3 cons, sentiment grade 1-100.
---

# Twitter Stock Analyzer Agent

## Purpose
Search Twitter/X for quality tweets about a stock. Filter noise. Extract signal. Output structured analysis.

---

## Step 1: Run the Script

```bash
python scripts/twitter_stock_analyzer.py TICKER
```

If tweepy is not installed, run first:
```bash
pip install tweepy
```

---

## Step 2: Quality Filter — Apply After Getting Results

The script already pre-filters by engagement. You still need to apply content quality judgment.

### GOOD tweet — keep and extract insights:
- Hard numbers: revenue, %, institutional ownership %, contract values, EPS, price targets
- Specific comparison: "5 years ago vs now", "this quarter vs last"
- Credible account: verified, 10K+ followers, known financial account
- High engagement: 500+ likes OR 10K+ impressions
- Clear thesis or conclusion with reasoning
- Insider buying, short interest data, analyst upgrades/downgrades

### BAD tweet — ignore completely:
- Pure sentiment: "moon", "going all in", "can't miss this"
- Basic price chart screenshot with no analysis
- Under 20 likes, under 5 retweets, no substance
- Meme content or jokes
- Price predictions with zero reasoning

---

## Step 3: Output Format

Produce exactly this:

```
=== TWITTER ANALYSIS: $[TICKER] ===
Period: Last 7 days
Quality tweets analyzed: [N]

TOP INSIGHTS FROM TWITTER:
[Bullet list — only facts and data points found in tweets. Numbers, catalysts, institutional moves, analyst calls. No hype. No opinions.]

PROS (3 things Twitter bulls are saying, with data):
1.
2.
3.

CONS (3 things Twitter bears are saying or risks mentioned):
1.
2.
3.

SENTIMENT GRADE: [X]/100
Reasoning: [2-3 sentences — why this grade. Based on data quality of tweets, engagement levels, bull/bear ratio, credibility of accounts.]

DATA QUALITY NOTE: [Was there real fundamental data in the tweets, or mostly sentiment? Flag if thin data.]
```

---

## Grading Scale

| Grade | Meaning |
|-------|---------|
| 80-100 | Strong bullish consensus backed by hard data |
| 60-79 | Moderately bullish, some data, some noise |
| 40-59 | Mixed — bulls and bears roughly equal |
| 20-39 | Mostly bearish, concerns outweigh positives |
| 1-19 | Strong bearish sentiment, major red flags |

**Key rule:** A tweet with 50K impressions saying "moon soon" = worth less than a tweet with 500 impressions showing institutional ownership data. Data always beats volume.

---

## API Limitation
Script searches last 7 days only — Twitter API free plan restriction.
3-month search = Pro plan ($5,000/month). Not worth it.
