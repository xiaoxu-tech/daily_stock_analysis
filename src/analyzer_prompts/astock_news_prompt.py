# -*- coding: utf-8 -*-
"""LLM prompt templates for A-share news analysis.

Used by the analyzer pipeline to process scraped Chinese financial news
through an LLM, identifying affected sectors, stocks, and sentiment.
"""

# ── Batch news analysis prompt (Chinese) ──

ANALYSIS_PROMPT = """你是一位专业的A股市场分析师。请分析以下财经新闻，判断它们可能影响的板块（行业板块/概念板块）和个股。

{capital_flow_context}
每条新闻的格式为：
[新闻ID: {{id}}]
来源: {{source}}
标题: {{title}}
内容: {{content}}

---
{news_items}
---

请按以下 JSON 格式返回分析结果（只返回 JSON，不要包含其他文字）：
{{
  "analysis": [
    {{
      "news_id": "<新闻ID，必须与上面给定的ID一致>",
      "affected_sectors": ["板块名1", "板块名2"],
      "affected_stocks": ["股票代码或名称1", "股票代码或名称2"],
      "sentiment": "利好" 或 "利空" 或 "中性",
      "reasoning": "简要分析理由（30字以内）"
    }}
  ]
}}
"""


# ── Market summary prompt (Chinese) ──

SUMMARIZE_PROMPT = """你是一位A股市场分析师。以下是今日重要财经新闻及AI分析结果：

{capital_flow_summary}
{analysis_summary}

请生成一份结构化的市场简报，包含以下内容（使用 Markdown 格式）：

## 今日市场情绪
整体判断：偏多 / 偏空 / 中性

## 重点板块
按影响力从高到低排列，说明每个板块的核心驱动因素

## 重点个股
被多次提及或影响较大的个股，说明原因

## 风险提示
需要关注的利空因素

请保持简洁，突出重点。注意：不要使用emoji符号。"""
