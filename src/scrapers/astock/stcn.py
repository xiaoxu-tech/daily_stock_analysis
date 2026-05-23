# -*- coding: utf-8 -*-
"""证券时报 (STCN) news scraper — HTML list + detail page fetching.

Parses the server-rendered news list, then fetches each article detail page
to extract full content and publication time.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime
from typing import Optional, List, Dict, Any

import httpx
from bs4 import BeautifulSoup

from src.scrapers.base import BaseScraper
from src.scrapers.models import NewsItem, NewsSource, clean_html

logger = logging.getLogger(__name__)

LIST_URL = "https://www.stcn.com/article/list/xw.html"
DETAIL_URL = "https://www.stcn.com/article/detail/{id}.html"


class STCNScraper(BaseScraper):
    """证券时报新闻抓取器（HTML-based）"""

    def __init__(
        self,
        client: Optional[httpx.Client] = None,
        max_items: int = 20,
        request_delay: float = 0.5,
    ):
        super().__init__(client=client, max_items=max_items, request_delay=request_delay)

    @property
    def domain(self) -> str:
        return "astock"

    def source(self) -> NewsSource:
        return NewsSource.STCN

    def fetch(self) -> List[Dict[str, Any]]:
        resp = self._client.get(LIST_URL)
        resp.raise_for_status()
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        articles: List[Dict[str, Any]] = []
        seen_ids: set = set()

        for link in soup.select("a[href*='/article/detail/']"):
            href = link.get("href", "")
            title = link.get_text(strip=True)
            if not title:
                continue

            match = re.search(r"/article/detail/(\d+)\.html", href)
            art_id = match.group(1) if match else ""

            if art_id and art_id not in seen_ids:
                seen_ids.add(art_id)
                articles.append({
                    "id": art_id,
                    "title": title,
                    "url": href if href.startswith("http") else f"https://www.stcn.com{href}",
                })

        return articles[: self._max_items]

    def parse(self, raw: Dict[str, Any]) -> Optional[NewsItem]:
        art_id = raw.get("id", "")
        if not art_id:
            return None

        try:
            detail_url = DETAIL_URL.format(id=art_id)
            resp = self._client.get(detail_url)
            resp.raise_for_status()
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "lxml")

            content = self._extract_content(soup)
            pub_time = self._extract_time(soup)
            time.sleep(self._request_delay)

            return NewsItem(
                id=art_id,
                source=NewsSource.STCN,
                title=raw["title"],
                content=clean_html(content or raw["title"])[:2000],
                url=raw.get("url"),
                published_at=_parse_chinese_time(pub_time) if pub_time else None,
                domain=self.domain,
            )
        except Exception as e:
            logger.warning("[证券时报] 详情页 %s 抓取失败: %s", art_id, e)
            return NewsItem(
                id=art_id,
                source=NewsSource.STCN,
                title=raw["title"],
                content=raw["title"],
                url=raw.get("url"),
                domain=self.domain,
            )

    def _extract_content(self, soup: BeautifulSoup) -> Optional[str]:
        selectors = [".article-content", ".detail-content", ".text", "article", ".main-content"]
        for sel in selectors:
            div = soup.select_one(sel)
            if div:
                return div.get_text(separator="\n", strip=True)
        return None

    def _extract_time(self, soup: BeautifulSoup) -> Optional[str]:
        selectors = [".time", ".date", ".article-info time", "time", ".publish-time"]
        for sel in selectors:
            elem = soup.select_one(sel)
            if elem:
                return elem.get_text(strip=True)
        return None


def _parse_chinese_time(s: str) -> Optional[datetime]:
    """Parse Chinese date format like '2025-01-15 14:30:00'."""
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except ValueError:
            continue
    return None
