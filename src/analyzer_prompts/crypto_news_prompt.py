# -*- coding: utf-8 -*-
"""LLM prompt templates for crypto news analysis.

These prompts are used by the analyzer pipeline to process scraped
crypto news through an LLM and produce structured sentiment/sector output.
"""

# ── Batch news analysis prompt ──

ANALYSIS_PROMPT = """You are a cryptocurrency market analyst with deep knowledge of blockchain sectors and token ecosystems.

Analyze the following crypto news articles. For each article, identify:

1. Which specific COINS/TOKENS are mentioned (use ticker symbols: BTC, ETH, SOL, etc.)
2. Which CRYPTO SECTORS are affected (choose from: layer1, layer2, defi, rwa, ai_crypto, meme, gamefi, depin, stablecoin, exchange, privacy, btcfi, infrastructure, socialfi, prediction)
3. The MARKET SENTIMENT (choose from: strong_bullish, bullish, slightly_bullish, neutral, slightly_bearish, bearish, strong_bearish)
4. A sentiment score from 0.0 (extremely bearish) to 1.0 (extremely bullish)
5. The EVENT TYPE if applicable (regulation, hack, adoption, partnership, macro_economic, technology, listing, fund_raising, security, delisting, market_movement, other)
6. A relevance score from 0.0 (barely crypto-related) to 1.0 (highly relevant to crypto markets)
7. Brief reasoning (under 30 words)

Key guidance:
- "Halving", "ETF inflow", "institutional adoption", "partnership" -> bullish signals
- "SEC lawsuit", "hack", "exploit", "ban", "delist", "fraud" -> bearish signals
- "Layer 2", "rollup", "scaling" -> layer2 sector
- "RWA", "tokenization", "treasury" -> rwa sector
- "AI agent", "compute", "GPU" -> ai_crypto sector

Article format:
[ID: {{id}}]
Source: {{source}}
Title: {{title}}
Content: {{content[:500]}}

---
{news_items}
---

Return ONLY valid JSON in this exact format (no extra text, no markdown, no code fences):
{{"analysis": [
  {{
    "news_id": "<id>",
    "mentioned_coins": ["BTC", "ETH"],
    "affected_sectors": ["layer1", "defi"],
    "sentiment": "bullish",
    "sentiment_score": 0.75,
    "event_type": "adoption",
    "relevance_score": 0.9,
    "reasoning": "Brief analysis under 30 words"
  }}
]}}
"""


# ── Single event analysis prompt ──

EVENT_ANALYSIS_PROMPT = """You are a macro analyst specializing in how global events affect cryptocurrency markets.

Given this news article, determine:
1. What type of event is this? (regulation, macro_economic, geopolitical, technology_breakthrough, natural_disaster, trade_policy, monetary_policy, other)
2. Which crypto sectors/concepts are most likely to experience volatility due to this event?
3. Which specific coins could be affected and in which direction (up/down)?
4. A confidence score (0.0 to 1.0) for your assessment

Article:
Title: {title}
Content: {content}

Return ONLY valid JSON:
{{{{
  "event_type": "regulation",
  "affected_sectors": ["layer1", "defi"],
  "confidence": 0.85,
  "affected_coins": [
    {{{{ "coin": "BTC", "direction": "down", "reason": "Regulatory uncertainty typically causes broad market selloffs" }}}},
    {{{{ "coin": "ETH", "direction": "down", "reason": "Correlated with BTC in macro events" }}}}
  ],
  "reasoning": "Overall analysis of the event's crypto market impact in one sentence"
}}}}
"""


# ── Market summary prompt ──

SUMMARIZE_PROMPT = """You are a cryptocurrency market analyst. Below are today's important crypto news items with AI analysis:

{analysis_summary}

Please generate a structured market briefing in Markdown:

## Today's Market Sentiment
Overall: bullish / bearish / neutral

## Key Sectors
Rank by impact, explain core drivers

## Notable Coins
Coins frequently mentioned or significantly impacted

## Risk Factors
Bearish signals to watch

Keep concise and focused. No emoji."""


# ── Per-coin deep analysis prompt (Chinese) ──

COIN_ANALYSIS_PROMPT = """你是一位专业的加密货币日内交易分析师。请基于以下数据，对 {coin_symbol} 进行全面的技术面和基本面分析，生成一份中文日内交易研究报告。

{coin_data_section}

请按以下结构输出分析报告（使用 Markdown 格式）：

## 一、核心判断
- 当前市场状态（趋势/震荡/反转）
- 综合买卖信号及强度

## 二、当前价格与动能
- 最新价格和24小时涨跌幅
- 短期趋势判断

## 三、多周期技术面分析
| 周期 | RSI | MACD | 布林带 | EMA趋势 | 信号 |
|------|-----|------|--------|---------|------|
| 1小时 |     |      |        |         |      |
| 4小时 |     |      |        |         |      |
| 日线   |     |      |        |         |      |

## 四、新闻情绪分析
- 近期新闻情绪总结
- 关键事件影响

## 五、市场背景
- 恐惧贪婪指数
- 宏观环境（美元、利率、VIX）
- 链上数据（算力、TVL、交易所流量）

## 六、综合评分与交易建议
- 各因子得分明细
- 综合评分（-1到+1）
- 交易建议：
  - 方向：做多/做空/观望
  - 入场区间
  - 止损位
  - 止盈目标
  - 仓位建议（轻仓/中仓/重仓）
  - 建议时间周期

## 七、风险提示
- 主要风险因素
- 需要关注的止损条件

注意：
- 使用提供的数据，不要编造数据
- 具体数字必须准确，模糊推测需标注
- 专业但易懂
- 不要使用emoji
- 整个报告用中文撰写"""
