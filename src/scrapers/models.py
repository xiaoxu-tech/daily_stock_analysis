# -*- coding: utf-8 -*-
"""Unified news data models for crypto and A-share news ingestion.

Supports both crypto (9 RSS sources, enriched AI analysis) and A-share
(6 Chinese news sources, capital flow context) news items through a single
dataclass with optional fields for each domain.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class NewsSource(str, Enum):
    """Unified news source enumeration across crypto and A-share domains."""

    # Crypto RSS sources (9)
    COINDESK = "coindesk"
    COINTELEGRAPH = "cointelegraph"
    THEBLOCK = "theblock"
    DECRYPT = "decrypt"
    CRYPTOSLATE = "cryptoslate"
    NEWS_BTC = "newsbtc"
    BE_IN_CRYPTO = "beincrypto"
    CRYPTO_BRIEFING = "cryptobriefing"
    U_TODAY = "utoday"

    # A-share Chinese sources (6)
    WALLSTREETCN = "wallstreetcn"
    EASTMONEY = "eastmoney"
    STCN = "stcn"
    YICAI = "yicai"
    JIEMIAN = "jiemian"
    YAHOO_CHINA = "yahoo_china"


class SentimentLabel(str, Enum):
    """Sentiment classification labels (7-level for crypto)."""
    STRONG_BULLISH = "strong_bullish"
    BULLISH = "bullish"
    SLIGHTLY_BULLISH = "slightly_bullish"
    NEUTRAL = "neutral"
    SLIGHTLY_BEARISH = "slightly_bearish"
    BEARISH = "bearish"
    STRONG_BEARISH = "strong_bearish"


class ASentiment(str, Enum):
    """A-share simplified sentiment (3-level)."""
    BULLISH = "利好"
    BEARISH = "利空"
    NEUTRAL = "中性"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class NewsItem:
    """Unified news item for both crypto and A-share domains.

    The first block of fields is populated by scrapers (always present).
    The AI analysis block is optional and filled by the analyzer pipeline.

    For crypto: mentioned_coins, affected_sectors (crypto sectors), sentiment_score 0-1.
    For A-share: affected_stocks (A-share codes), affected_sectors (Chinese sectors),
                 sentiment uses Chinese labels (利好/利空/中性).
    """

    # -- scraper-populated fields --
    id: str                      # MD5 hash or source-specific unique ID
    source: NewsSource           # which outlet
    title: str                   # headline
    content: str                 # article body (HTML stripped, truncated)
    url: Optional[str] = None
    published_at: Optional[datetime] = None
    crawled_at: datetime = field(default_factory=datetime.now)

    # -- unified AI analysis fields --
    mentioned_coins: List[str] = field(default_factory=list)    # crypto tickers
    affected_sectors: List[str] = field(default_factory=list)   # sector names
    affected_stocks: List[str] = field(default_factory=list)    # A-share stock codes/names
    sentiment: Optional[str] = None          # label string (enum value or Chinese)
    sentiment_score: Optional[float] = None  # 0.0-1.0 for crypto, None for A-share
    event_type: Optional[str] = None         # regulation/hack/adoption/partnership/macro/etc.
    reasoning: Optional[str] = None          # brief analysis (≤30 chars)
    relevance_score: Optional[float] = None  # 0.0-1.0
    concept_coins: List[Dict[str, Any]] = field(default_factory=list)

    # -- domain tag --
    domain: str = "crypto"  # "crypto" | "astock"

    # -- helper methods --

    def dedup_key(self) -> str:
        """Generate a fuzzy-dedup fingerprint from title + first 100 chars of content."""
        def _norm(s: str) -> str:
            return s.strip().lower().replace(" ", "")[:50]
        return f"{_norm(self.title)}|{_norm(self.content[:100])}"

    def compute_id(self) -> str:
        """Compute a stable MD5-based ID from source + title."""
        raw = f"{self.source.value}:{self.title}"
        return hashlib.md5(raw.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for DB storage (JSON-serializes list fields)."""
        import json
        return {
            "id": self.id or self.compute_id(),
            "source": self.source.value,
            "title": self.title,
            "content": self.content,
            "url": self.url,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "crawled_at": self.crawled_at.isoformat() if self.crawled_at else None,
            "mentioned_coins": json.dumps(self.mentioned_coins, ensure_ascii=False) if self.mentioned_coins else "[]",
            "affected_sectors": json.dumps(self.affected_sectors, ensure_ascii=False) if self.affected_sectors else "[]",
            "affected_stocks": json.dumps(self.affected_stocks, ensure_ascii=False) if self.affected_stocks else "[]",
            "sentiment": self.sentiment,
            "sentiment_score": self.sentiment_score,
            "event_type": self.event_type,
            "reasoning": self.reasoning,
            "relevance_score": self.relevance_score,
            "concept_coins": json.dumps(self.concept_coins, ensure_ascii=False) if self.concept_coins else "[]",
            "domain": self.domain,
        }

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "NewsItem":
        """Reconstruct from a SQLAlchemy row or dict."""
        import json
        def _json_list(val, default=None):
            if val is None:
                return default if default is not None else []
            if isinstance(val, list):
                return val
            try:
                return json.loads(val)
            except (json.JSONDecodeError, TypeError):
                return default if default is not None else []

        return cls(
            id=row.get("id") or "",
            source=NewsSource(row["source"]) if isinstance(row.get("source"), str) else row.get("source"),
            title=row.get("title") or "",
            content=row.get("content") or "",
            url=row.get("url"),
            published_at=_parse_datetime(row.get("published_at")),
            crawled_at=_parse_datetime(row.get("crawled_at")) or datetime.now(),
            mentioned_coins=_json_list(row.get("mentioned_coins")),
            affected_sectors=_json_list(row.get("affected_sectors")),
            affected_stocks=_json_list(row.get("affected_stocks")),
            sentiment=row.get("sentiment"),
            sentiment_score=row.get("sentiment_score"),
            event_type=row.get("event_type"),
            reasoning=row.get("reasoning"),
            relevance_score=row.get("relevance_score"),
            concept_coins=_json_list(row.get("concept_coins"), default=[]),
            domain=row.get("domain", "crypto"),
        )


# Simple create model
@dataclass
class NewsItemCreate:
    """Input model for creating news items (before ID computation)."""
    source: str
    title: str
    content: str
    url: Optional[str] = None
    published_at: Optional[datetime] = None
    domain: str = "crypto"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_datetime(val: Any) -> Optional[datetime]:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    if isinstance(val, str):
        # Try ISO format
        try:
            return datetime.fromisoformat(val)
        except (ValueError, TypeError):
            pass
        # Try common date formats
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y%m%d"):
            try:
                return datetime.strptime(val[:19] if " " in val else val[:10], fmt)
            except (ValueError, TypeError):
                continue
    return None


_HTML_TAG = re.compile(r"<[^>]*>")
_HTML_ENTITY = re.compile(r"&[a-z]+;")
_WHITESPACE = re.compile(r"\s+")


def clean_html(text: str) -> str:
    """Strip HTML tags and entities, collapse whitespace."""
    text = _HTML_TAG.sub(" ", text)
    text = _HTML_ENTITY.sub(" ", text)
    text = _WHITESPACE.sub(" ", text)
    return text.strip()


def truncate_content(text: str, max_chars: int = 2000) -> str:
    """Truncate text to max_chars, preferring sentence boundaries."""
    clean = clean_html(text)
    if len(clean) <= max_chars:
        return clean
    truncated = clean[:max_chars]
    # try to cut at last period or newline
    cut = max(truncated.rfind("。"), truncated.rfind("."), truncated.rfind("\n"))
    if cut > max_chars * 0.7:
        return truncated[:cut + 1]
    return truncated


def extract_news_source_value(source: str) -> Optional[NewsSource]:
    """Map a raw source identifier string to a NewsSource enum member.

    Handles partial matches (e.g. 'wallstreetcn' in 'wallstreetcn_scraper').
    """
    source_lower = source.lower().strip()
    for member in NewsSource:
        if member.value in source_lower or source_lower in member.value:
            return member
    return None
