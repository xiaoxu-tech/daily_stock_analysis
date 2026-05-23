# -*- coding: utf-8 -*-
"""Abstract base class for all news scrapers.

Defines the template method pattern for multi-source news scraping:
    fetch() → parse(raw) → (optional) compute_id()
"""

from __future__ import annotations

import hashlib
import logging
import re
from abc import ABC, abstractmethod
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Optional, List, Dict, Any

import httpx

from .models import NewsItem, NewsSource, clean_html, truncate_content

logger = logging.getLogger(__name__)

# Browser-like headers to avoid 403 blocks
_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
}


class BaseScraper(ABC):
    """Abstract base for all news scrapers (crypto RSS + A-share HTML/API).

    Subclasses implement:
        source()  → NewsSource enum member
        fetch()   → list of raw dicts
        parse(raw) → Optional[NewsItem]

    The template method scrape() orchestrates fetch → parse → ID compute.
    """

    def __init__(
        self,
        client: Optional[httpx.Client] = None,
        max_items: int = 20,
        request_delay: float = 0.5,
    ):
        """Initialize the scraper.

        Args:
            client: Shared httpx.Client or None (creates a new one).
            max_items: Max items to fetch per scrape run.
            request_delay: Seconds between HTTP requests (rate limiting).
        """
        self._client = client or httpx.Client(
            headers=_DEFAULT_HEADERS,
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
        )
        self._max_items = max_items
        self._request_delay = request_delay

    # -- subclasses must implement --

    @abstractmethod
    def source(self) -> NewsSource:
        """Return the NewsSource enum for this scraper."""
        ...

    @abstractmethod
    def fetch(self) -> List[Dict[str, Any]]:
        """Fetch raw data items from the source.

        Returns:
            List of raw dicts, each containing at minimum 'title' and 'content'.
        """
        ...

    @abstractmethod
    def parse(self, raw: Dict[str, Any]) -> Optional[NewsItem]:
        """Convert a single raw dict into a NewsItem.

        Args:
            raw: One dict from the list returned by fetch().

        Returns:
            A NewsItem or None if this item should be skipped.
        """
        ...

    # -- domain hint (override if needed) --

    @property
    def domain(self) -> str:
        """Return 'crypto' or 'astock' for this scraper's domain."""
        return "crypto"

    # -- template method --

    def scrape(self) -> List[NewsItem]:
        """Fetch and parse all items from this source.

        Returns:
            List of NewsItem objects (may be empty on failure).
        """
        source_name = self.source().value
        try:
            logger.info("Scraping %s ...", source_name)
            raw_items = self.fetch()
            logger.debug("%s: fetched %d raw items", source_name, len(raw_items))
        except httpx.HTTPError as e:
            logger.error("%s: HTTP error during fetch: %s", source_name, e)
            return []
        except Exception as e:
            logger.error("%s: unexpected fetch error: %s", source_name, e, exc_info=True)
            return []

        results: List[NewsItem] = []
        for i, raw in enumerate(raw_items):
            if len(results) >= self._max_items:
                break
            try:
                item = self.parse(raw)
                if item is None:
                    continue
                # Ensure ID is set
                if not item.id:
                    item.id = item.compute_id()
                item.domain = self.domain
                results.append(item)
            except Exception as e:
                logger.warning("%s: parse error for item %d: %s",
                              source_name, i, e, exc_info=True)
                continue

        logger.info("%s: parsed %d valid items (skipped %d)",
                    source_name, len(results), len(raw_items) - len(results))
        return results

    # -- utility helpers for subclasses --

    @staticmethod
    def _parse_time(ts: Any) -> Optional[datetime]:
        """Best-effort datetime parsing from various formats.

        Handles: Unix timestamps (int/float), ISO 8601 strings, RFC 2822,
        and common Chinese date formats.
        """
        if ts is None:
            return None
        if isinstance(ts, datetime):
            return ts
        # Unix timestamp
        if isinstance(ts, (int, float)):
            try:
                return datetime.fromtimestamp(ts)
            except (OSError, ValueError):
                return datetime.fromtimestamp(ts / 1000) if ts > 1e10 else None
        if isinstance(ts, str):
            ts_str = ts.strip()
            if not ts_str:
                return None
            # RFC 2822
            try:
                return parsedate_to_datetime(ts_str)
            except (ValueError, TypeError):
                pass
            # ISO 8601 variants
            for sep in ("T", " "):
                try:
                    return datetime.fromisoformat(ts_str[:19].replace(sep, "T"))
                except (ValueError, TypeError):
                    continue
            # Chinese format: 2024年01月15日 14:30
            cn_match = re.match(
                r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日?\s*(\d{1,2}:\d{2}(?::\d{2})?)?",
                ts_str,
            )
            if cn_match:
                y, m, d = int(cn_match.group(1)), int(cn_match.group(2)), int(cn_match.group(3))
                hms = cn_match.group(4) or "00:00:00"
                parts = hms.split(":")
                h, mi = int(parts[0]), int(parts[1])
                s = int(parts[2]) if len(parts) > 2 else 0
                try:
                    return datetime(y, m, d, h, mi, s)
                except ValueError:
                    pass
            # Common date-only
            for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y"):
                try:
                    return datetime.strptime(ts_str[:10], fmt)
                except ValueError:
                    continue
        return None

    @staticmethod
    def _compute_id(source: str, title: str) -> str:
        """Compute stable MD5 ID from source + title."""
        raw = f"{source}:{title}"
        return hashlib.md5(raw.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _clean_and_truncate(text: str, max_chars: int = 2000) -> str:
        """Strip HTML and truncate to max_chars."""
        return truncate_content(text, max_chars)

    @staticmethod
    def _extract_html_text(html: str) -> str:
        """Strip HTML tags and return clean text."""
        return clean_html(html)

    def close(self):
        """Close the HTTP client."""
        if self._client is not None:
            self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
