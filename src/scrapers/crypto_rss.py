# -*- coding: utf-8 -*-
"""Crypto RSS scraper — unified scraper for 9 crypto news feeds.

Each source is configured with its RSS feed URL. The single RSSScraper class
handles all 9 sources via feedparser + httpx.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

import feedparser
import httpx

from .base import BaseScraper
from .models import NewsItem, NewsSource, clean_html, truncate_content

logger = logging.getLogger(__name__)

# -- RSS feed URL registry --

RSS_FEEDS: Dict[NewsSource, str] = {
    NewsSource.COINDESK:        "https://www.coindesk.com/arc/outboundfeeds/rss/",
    NewsSource.COINTELEGRAPH:   "https://cointelegraph.com/rss",
    NewsSource.THEBLOCK:        "https://www.theblock.co/rss.xml",
    NewsSource.DECRYPT:         "https://decrypt.co/feed",
    NewsSource.CRYPTOSLATE:     "https://cryptoslate.com/feed/",
    NewsSource.NEWS_BTC:        "https://www.newsbtc.com/feed/",
    NewsSource.BE_IN_CRYPTO:    "https://beincrypto.com/feed/",
    NewsSource.CRYPTO_BRIEFING: "https://cryptobriefing.com/feed/",
    NewsSource.U_TODAY:         "https://u.today/rss",
}

# Per-source display labels (for logging / UI)
SOURCE_LABELS: Dict[NewsSource, str] = {
    NewsSource.COINDESK:        "CoinDesk",
    NewsSource.COINTELEGRAPH:   "CoinTelegraph",
    NewsSource.THEBLOCK:        "The Block",
    NewsSource.DECRYPT:         "Decrypt",
    NewsSource.CRYPTOSLATE:     "CryptoSlate",
    NewsSource.NEWS_BTC:        "NewsBTC",
    NewsSource.BE_IN_CRYPTO:    "BeInCrypto",
    NewsSource.CRYPTO_BRIEFING: "Crypto Briefing",
    NewsSource.U_TODAY:         "U.Today",
}


class RSSScraper(BaseScraper):
    """Scraper for a single crypto RSS/Atom feed.

    Uses feedparser for RSS/Atom parsing and httpx for HTTP transport.
    Each instance is bound to one NewsSource.
    """

    def __init__(
        self,
        source: NewsSource,
        client: Optional[httpx.Client] = None,
        max_items: int = 20,
        request_delay: float = 0.5,
    ):
        super().__init__(client=client, max_items=max_items, request_delay=request_delay)
        self._source = source

    @property
    def domain(self) -> str:
        return "crypto"

    def source(self) -> NewsSource:
        return self._source

    def fetch(self) -> List[Dict[str, Any]]:
        url = RSS_FEEDS.get(self._source)
        if not url:
            logger.warning("No RSS feed URL configured for %s", self._source.value)
            return []

        try:
            resp = self._client.get(url)
            resp.raise_for_status()
            feed = feedparser.parse(resp.text)
            entries = feed.entries

            if not entries:
                logger.warning("%s: feed returned 0 entries", self._source.value)
                return []

            # Limit per-source
            entries = entries[:self._max_items]

            # Convert FeedParserDict to plain dicts
            result = []
            for entry in entries:
                raw = {
                    "title": entry.get("title", ""),
                    "link": entry.get("link", ""),
                    "published": entry.get("published", ""),
                    "published_parsed": getattr(entry, "published_parsed", None),
                    "updated_parsed": getattr(entry, "updated_parsed", None),
                    "summary": entry.get("summary", ""),
                    "content": _extract_entry_content(entry),
                    "author": entry.get("author", ""),
                }
                result.append(raw)

            logger.debug("%s: fetched %d entries", self._source.value, len(result))
            return result

        except httpx.HTTPError as e:
            logger.error("%s: HTTP error: %s", self._source.value, e)
            return []
        except Exception as e:
            logger.error("%s: fetch error: %s", self._source.value, e, exc_info=True)
            return []

    def parse(self, raw: Dict[str, Any]) -> Optional[NewsItem]:
        title = raw.get("title", "").strip()
        if not title:
            return None

        # Extract content from various RSS fields
        content = raw.get("content", "")
        if not content:
            content = raw.get("summary", "")
        content = clean_html(content)
        content = truncate_content(content, max_chars=2000)
        if not content:
            content = title  # fallback

        # Parse publication time
        published_at = _parse_rss_time(raw)

        # Compute stable ID
        item_id = self._compute_id(self._source.value, title)

        return NewsItem(
            id=item_id,
            source=self._source,
            title=title,
            content=content,
            url=raw.get("link") or None,
            published_at=published_at,
            domain=self.domain,
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_crypto_scrapers(
    enabled_sources: Optional[List[NewsSource]] = None,
    max_per_source: int = 20,
    request_delay: float = 0.5,
    client: Optional[httpx.Client] = None,
) -> List[RSSScraper]:
    """Create RSSScraper instances for enabled crypto sources.

    Args:
        enabled_sources: List of sources to enable. None = all 9.
        max_per_source: Max items per source.
        request_delay: Seconds between HTTP requests.
        client: Shared httpx.Client or None.

    Returns:
        List of RSSScraper instances.
    """
    if enabled_sources is None:
        enabled_sources = list(NewsSource)
        # Filter to only crypto RSS sources
        enabled_sources = [s for s in enabled_sources if s.value in {
            "coindesk", "cointelegraph", "theblock", "decrypt", "cryptoslate",
            "newsbtc", "beincrypto", "cryptobriefing", "utoday",
        }]

    scrapers = []
    for source in enabled_sources:
        if source in RSS_FEEDS:
            scrapers.append(RSSScraper(
                source=source,
                client=client,
                max_items=max_per_source,
                request_delay=request_delay,
            ))
        else:
            logger.warning("Skipping %s: no RSS URL configured", source.value)

    return scrapers


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_entry_content(entry) -> str:
    """Best-effort content extraction from feedparser entry.

    RSS feeds store content in various fields: content, summary, description,
    subtitle. Some use lists of dicts with 'value' sub-keys.
    """
    # Try 'content' first (Atom)
    content_attr = getattr(entry, "content", None)
    if content_attr:
        if isinstance(content_attr, list) and len(content_attr) > 0:
            first = content_attr[0]
            if isinstance(first, dict):
                return first.get("value", str(first))
        return str(content_attr)

    # Try HTML content
    for attr in ("summary", "description", "subtitle"):
        val = getattr(entry, attr, None)
        if val:
            if isinstance(val, str):
                return val
            if isinstance(val, list) and len(val) > 0:
                first = val[0]
                if isinstance(first, dict):
                    return first.get("value", str(first))
                return str(first)

    return ""


def _parse_rss_time(raw: Dict[str, Any]) -> Optional[datetime]:
    """Extract publication time from an RSS entry dict."""
    # Prefer structured parsed time tuples
    for key in ("published_parsed", "updated_parsed"):
        tp = raw.get(key)
        if tp and isinstance(tp, (tuple, list)) and len(tp) >= 6:
            try:
                return datetime(*tp[:6])
            except (ValueError, TypeError, OverflowError):
                continue

    # Fall back to string parsing
    for key in ("published", "updated"):
        ts = raw.get(key)
        if ts:
            parsed = BaseScraper._parse_time(ts)
            if parsed:
                return parsed

    return None
