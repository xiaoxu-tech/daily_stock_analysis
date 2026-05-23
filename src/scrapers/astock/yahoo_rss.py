# -*- coding: utf-8 -*-
"""Yahoo Finance China RSS scraper — uses RSS feeds for A-share related news.

Fetches from Yahoo Finance RSS feeds keyed on Shanghai Composite (000001.SS)
and CSI 300 (000300.SS) to get China-related financial headlines.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from typing import Optional, List, Dict, Any

import httpx

from src.scrapers.base import BaseScraper
from src.scrapers.models import NewsItem, NewsSource

logger = logging.getLogger(__name__)

FEED_URLS = [
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s=000001.SS&region=CN&lang=zh-CN",
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s=000300.SS&region=US&lang=en-US",
]


class YahooChinaScraper(BaseScraper):
    """Yahoo Finance 中国财经 RSS 抓取器"""

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
        return NewsSource.YAHOO_CHINA

    def fetch(self) -> List[Dict[str, Any]]:
        articles: List[Dict[str, Any]] = []
        for feed_url in FEED_URLS:
            try:
                resp = self._client.get(feed_url)
                resp.raise_for_status()
                root = ET.fromstring(resp.text)
                channel = root.find("channel")
                if channel is not None:
                    for item in channel.findall("item"):
                        title = item.findtext("title", "")
                        link = item.findtext("link", "")
                        description = item.findtext("description", "")
                        pub_date = item.findtext("pubDate", "")

                        if title and link:
                            articles.append({
                                "id": link,
                                "title": _clean_text(title),
                                "content": _clean_text(description),
                                "url": link,
                                "pub_date": pub_date,
                            })
            except Exception as e:
                logger.warning("[Yahoo] RSS %s 失败: %s",
                              feed_url.split("?")[-1][:30] if "?" in feed_url else feed_url[:30], e)

        logger.info("[Yahoo] RSS 获取 %d 篇", len(articles))
        return articles[: self._max_items]

    def parse(self, raw: Dict[str, Any]) -> Optional[NewsItem]:
        title = raw.get("title", "")
        if not title:
            return None

        return NewsItem(
            id=raw.get("id", title),
            source=NewsSource.YAHOO_CHINA,
            title=title,
            content=raw.get("content", title)[:2000],
            url=raw.get("url"),
            published_at=self._parse_time(raw.get("pub_date")),
            domain=self.domain,
        )


def _clean_text(text: str) -> str:
    """Clean HTML entities and tags from text."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&quot;", '"').replace("&apos;", "'")
    text = text.replace("\xa0", " ").replace(" ", " ")
    return text.strip()
