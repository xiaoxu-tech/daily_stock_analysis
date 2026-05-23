# -*- coding: utf-8 -*-
"""第一财经 (Yicai) news scraper — HTML list + detail page fetching."""

from __future__ import annotations

import logging
import re
from typing import Optional, List, Dict, Any

import httpx
from bs4 import BeautifulSoup

from src.scrapers.base import BaseScraper
from src.scrapers.models import NewsItem, NewsSource, clean_html

logger = logging.getLogger(__name__)

LIST_URL = "https://www.yicai.com/news/"
DETAIL_URL = "https://www.yicai.com/news/{id}.html"


class YicaiScraper(BaseScraper):
    """第一财经新闻抓取器（HTML-based）"""

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
        return NewsSource.YICAI

    def fetch(self) -> List[Dict[str, Any]]:
        resp = self._client.get(LIST_URL)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        seen_ids: set = set()
        articles: List[Dict[str, Any]] = []

        for link in soup.select("a[href*='/news/']"):
            href = link.get("href", "")
            title = link.get_text(strip=True)
            if not title or len(title) < 10:
                continue

            match = re.search(r"/news/(\d+)\.html", href)
            art_id = match.group(1) if match else ""

            if art_id and art_id not in seen_ids:
                seen_ids.add(art_id)
                full_url = href if href.startswith("http") else f"https://www.yicai.com{href}"
                articles.append({"id": art_id, "title": title, "url": full_url})

        return articles[: self._max_items]

    def parse(self, raw: Dict[str, Any]) -> Optional[NewsItem]:
        art_id = raw.get("id", "")
        if not art_id:
            return None

        try:
            detail_url = DETAIL_URL.format(id=art_id)
            resp = self._client.get(detail_url)
            resp.encoding = resp.apparent_encoding or "utf-8"
            soup = BeautifulSoup(resp.text, "lxml")

            content = ""
            for sel in (".m-text", ".article-content", ".detail-content", "article"):
                div = soup.select_one(sel)
                if div:
                    content = div.get_text(separator="\n", strip=True)
                    break

            return NewsItem(
                id=art_id,
                source=NewsSource.YICAI,
                title=raw["title"],
                content=clean_html(content or raw["title"])[:2000],
                url=raw.get("url"),
                domain=self.domain,
            )
        except Exception as e:
            logger.debug("[第一财经] 详情 %s 失败: %s", art_id, e)
            return NewsItem(
                id=art_id,
                source=NewsSource.YICAI,
                title=raw["title"],
                content=raw["title"],
                url=raw.get("url"),
                domain=self.domain,
            )
