# -*- coding: utf-8 -*-
"""东方财富 (EastMoney) news scraper — HTML list + detail page fetching.

Parses the finance news list page, then fetches each article's detail page
to extract full content using BeautifulSoup.
"""

from __future__ import annotations

import logging
import time
from typing import Optional, List, Dict, Any

import httpx
from bs4 import BeautifulSoup

from src.scrapers.base import BaseScraper
from src.scrapers.models import NewsItem, NewsSource, clean_html

logger = logging.getLogger(__name__)

LIST_URL = "https://finance.eastmoney.com/a/czqyw.html"


class EastMoneyScraper(BaseScraper):
    """东方财富财经新闻抓取器（HTML-based）"""

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
        return NewsSource.EASTMONEY

    def fetch(self) -> List[Dict[str, Any]]:
        resp = self._client.get(LIST_URL)
        resp.raise_for_status()
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")

        articles: List[Dict[str, Any]] = []
        seen_titles: set = set()

        for link in soup.select("a[href*='finance.eastmoney.com/a/']"):
            href = link.get("href", "")
            title = link.get_text(strip=True)

            if not title or len(title) < 10 or title in seen_titles:
                continue
            seen_titles.add(title)

            full_url = href if href.startswith("http") else f"https:{href}"
            art_id = href.split("/")[-1].replace(".html", "") if "/" in href else ""

            if art_id:
                articles.append({"id": art_id, "title": title, "url": full_url})

        logger.info("[东方财富] HTML页面找到 %d 篇文章", len(articles))
        return articles[: self._max_items]

    def parse(self, raw: Dict[str, Any]) -> Optional[NewsItem]:
        title = raw.get("title", "")
        if not title:
            return None

        content = title  # fallback
        art_id = raw.get("id", "")
        if art_id:
            try:
                detail_url = f"https://finance.eastmoney.com/a/{art_id}.html"
                resp = self._client.get(detail_url)
                resp.encoding = "utf-8"
                soup = BeautifulSoup(resp.text, "lxml")
                for sel in (".Body_text", ".article-content", ".detail-content", ".text"):
                    div = soup.select_one(sel)
                    if div:
                        content = div.get_text(separator="\n", strip=True)
                        break
                time.sleep(self._request_delay)
            except Exception as e:
                logger.debug("[东方财富] 详情页 %s 抓取失败: %s", art_id, e)

        return NewsItem(
            id=art_id,
            source=NewsSource.EASTMONEY,
            title=title,
            content=clean_html(content)[:2000],
            url=raw.get("url"),
            domain=self.domain,
        )
