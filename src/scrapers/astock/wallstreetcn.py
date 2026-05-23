# -*- coding: utf-8 -*-
"""华尔街见闻 (WallStreetCN) scraper — uses public REST API.

Fetches from 3 channels: global live, A-stock live, and articles.
No detail page fetch needed — content comes directly from API response.
"""

from __future__ import annotations

import logging
from typing import Optional, List, Dict, Any

import httpx

from src.scrapers.base import BaseScraper
from src.scrapers.models import NewsItem, NewsSource, truncate_content

logger = logging.getLogger(__name__)

BASE_URL = "https://api-prod.wallstreetcn.com/apiv1/content"


class WallStreetCNScraper(BaseScraper):
    """华尔街见闻文章/快讯抓取器（API-based）"""

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
        return NewsSource.WALLSTREETCN

    def fetch(self) -> List[Dict[str, Any]]:
        seen: set = set()
        merged: List[Dict[str, Any]] = []

        channels = [
            ("lives", "global-channel"),
            ("lives", "a-stock-channel"),
            ("articles", "shares"),
        ]

        for endpoint, channel in channels:
            try:
                items = self._fetch_channel(endpoint, channel)
                for item in items:
                    item_id = item.get("id")
                    if item_id and item_id not in seen:
                        seen.add(item_id)
                        merged.append(item)
            except Exception as e:
                logger.warning("[华尔街见闻] 频道 %s/%s 请求失败: %s", endpoint, channel, e)

        return merged[: self._max_items]

    def _fetch_channel(self, endpoint: str, channel: str) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"limit": self._max_items}
        if endpoint == "lives":
            params["channel"] = channel
            params["cursor"] = "0"
        else:
            params["category"] = channel

        url = f"{BASE_URL}/{endpoint}"
        resp = self._client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") == 20000:
            return data.get("data", {}).get("items", [])
        return []

    def parse(self, raw: Dict[str, Any]) -> Optional[NewsItem]:
        title = raw.get("title") or ""
        content = raw.get("content_text") or raw.get("content_short") or ""

        if not title and content:
            title = content[:60]
        if not title:
            return None

        item_id = str(raw.get("id", ""))
        return NewsItem(
            id=item_id,
            source=NewsSource.WALLSTREETCN,
            title=title.strip(),
            content=truncate_content(content.strip(), 2000),
            url=f"https://wallstreetcn.com/articles/{item_id}" if item_id else None,
            published_at=self._parse_time(raw.get("display_time")),
            domain=self.domain,
        )
