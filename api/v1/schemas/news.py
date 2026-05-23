# -*- coding: utf-8 -*-
"""News API schemas — unified news feed (crypto + A-share)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# News Item
# ---------------------------------------------------------------------------

class NewsItem(BaseModel):
    """Unified news article from any source."""
    id: Optional[int] = Field(None, description="数据库 ID")
    news_id: str = Field(..., description="唯一标识(来源+URL哈希)")
    source: str = Field(..., description="新闻来源, 如 coindesk / eastmoney")
    source_type: str = Field(..., description="crypto / astock")
    title: str = Field(..., description="标题")
    url: Optional[str] = Field(None, description="原文链接")
    summary: Optional[str] = Field(None, description="摘要/前200字")
    content: Optional[str] = Field(None, description="正文(可能已截断)")
    published_at: Optional[str] = Field(None, description="发布时间")
    scraped_at: Optional[str] = Field(None, description="抓取时间")

    # Crypto-specific
    mentioned_coins: Optional[List[str]] = Field(None, description="提及的币种")
    sentiment_score: Optional[float] = Field(None, description="AI 情绪分数 0-1")
    sentiment_label: Optional[str] = Field(None, description="情绪标签")
    event_type: Optional[str] = Field(None, description="事件类型(如 regulation/partnership/hack)")
    ai_analysis: Optional[str] = Field(None, description="AI 分析摘要")

    # A-stock-specific
    affected_stocks: Optional[List[str]] = Field(None, description="受影响的股票代码")
    a_sentiment: Optional[str] = Field(None, description="A股情绪")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "id": 1,
            "news_id": "coindesk_abc123",
            "source": "CoinDesk",
            "source_type": "crypto",
            "title": "Bitcoin Surges Past $68,000 on ETF Inflow Data",
            "url": "https://coindesk.com/...",
            "summary": "BTC rallied 5% in the last 24 hours...",
            "published_at": "2025-01-15T08:30:00Z",
            "scraped_at": "2025-01-15T09:00:00Z",
            "mentioned_coins": ["BTC", "ETH"],
            "sentiment_score": 0.72,
            "sentiment_label": "bullish",
            "event_type": "market",
        }
    })


class NewsListResponse(BaseModel):
    """Paginated news feed."""
    items: List[NewsItem] = Field(default_factory=list)
    total: int
    page: int
    page_size: int


class NewsDetailResponse(BaseModel):
    """Full news article with AI analysis."""
    item: NewsItem
    related_news: List[NewsItem] = Field(default_factory=list, description="相关新闻")


# ---------------------------------------------------------------------------
# News Source
# ---------------------------------------------------------------------------

class NewsSource(BaseModel):
    """Available news source info."""
    source: str = Field(..., description="来源标识")
    source_type: str = Field(..., description="crypto / astock")
    description: Optional[str] = Field(None, description="来源描述")
    article_count: Optional[int] = Field(None, description="最近文章数")
    last_fetch: Optional[str] = Field(None, description="最后抓取时间")


class NewsSourceListResponse(BaseModel):
    """List of available news sources."""
    sources: List[NewsSource] = Field(default_factory=list)
    total_sources: int


# ---------------------------------------------------------------------------
# News Stats
# ---------------------------------------------------------------------------

class NewsStats(BaseModel):
    """Aggregated news statistics."""
    total_articles: int
    articles_24h: int
    articles_7d: int
    by_source: Dict[str, int] = Field(default_factory=dict)
    by_sentiment: Dict[str, int] = Field(default_factory=dict)
    top_coins: Dict[str, int] = Field(default_factory=dict, description="提及最多的币种")
    top_stocks: Dict[str, int] = Field(default_factory=dict, description="提及最多股票")


# ---------------------------------------------------------------------------
# Scrape trigger
# ---------------------------------------------------------------------------

class ScrapeRequest(BaseModel):
    """Request to trigger news scraping."""
    source_type: str = Field(..., description="crypto / astock / both")
    max_articles: int = Field(20, ge=1, le=200, description="每源最大文章数")
    analyze: bool = Field(True, description="是否随后进行 AI 分析")


class ScrapeResponse(BaseModel):
    """Result of a scrape run."""
    status: str = Field("ok", description="ok / partial / error")
    source_type: str
    sources_scraped: int
    total_fetched: int
    new_articles: int
    duplicates_skipped: int
    errors: List[str] = Field(default_factory=list)
    elapsed_seconds: Optional[float] = None
