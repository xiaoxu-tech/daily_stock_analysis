# -*- coding: utf-8 -*-
"""A-share news ingestion pipeline orchestrator.

Wraps the full A-share news pipeline:
    1. Scrape 6 Chinese news sources + capital flow data
    2. Fuzzy deduplicate news items
    3. Store raw items + capital flow snapshot to DB
    4. Batch analyze via LLM (sectors, stocks, sentiment)
    5. Generate market summary (optional)
"""

from __future__ import annotations

import json
import logging
import re
from typing import Optional, List, Dict, Any

import httpx

from src.scrapers.models import NewsItem, NewsSource
from src.scrapers.astock import (
    WallStreetCNScraper,
    EastMoneyScraper,
    STCNScraper,
    YicaiScraper,
    JiemianScraper,
    YahooChinaScraper,
)
from src.scrapers.capital_flow import EastMoneyCapitalFlowFetcher, CapitalFlowSnapshot
from src.scrapers.dedup import deduplicate
from src.analyzer_prompts.astock_news_prompt import (
    ANALYSIS_PROMPT,
    SUMMARIZE_PROMPT,
)

logger = logging.getLogger(__name__)

BATCH_SIZE = 15


class AstockIngestor:
    """Orchestrate A-share news scraping → dedup → store → analyze → summarize."""

    _SCRAPER_CLASSES = {
        NewsSource.WALLSTREETCN: WallStreetCNScraper,
        NewsSource.EASTMONEY: EastMoneyScraper,
        NewsSource.STCN: STCNScraper,
        NewsSource.YICAI: YicaiScraper,
        NewsSource.JIEMIAN: JiemianScraper,
        NewsSource.YAHOO_CHINA: YahooChinaScraper,
    }

    def __init__(
        self,
        db_manager=None,
        llm_provider=None,
        enabled_sources: Optional[List[NewsSource]] = None,
        max_per_source: int = 10,
        dedup_threshold: float = 0.75,
        request_delay: float = 0.5,
        northbound_days: int = 5,
        sector_top_n: int = 20,
        dragon_top_n: int = 20,
    ):
        self._db = db_manager
        self._llm = llm_provider
        self._enabled_sources = enabled_sources or list(self._SCRAPER_CLASSES.keys())
        self._max_per_source = max_per_source
        self._dedup_threshold = dedup_threshold
        self._request_delay = request_delay
        self._northbound_days = northbound_days
        self._sector_top_n = sector_top_n
        self._dragon_top_n = dragon_top_n

    # ── Pipeline phases ──

    def scrape_news(self) -> List[NewsItem]:
        """Phase 1a: Scrape all enabled A-share news sources."""
        client = httpx.Client(
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
        )

        all_items: List[NewsItem] = []
        try:
            for source in self._enabled_sources:
                scraper_cls = self._SCRAPER_CLASSES.get(source)
                if scraper_cls is None:
                    continue
                try:
                    scraper = scraper_cls(
                        client=client,
                        max_items=self._max_per_source,
                        request_delay=self._request_delay,
                    )
                    items = scraper.scrape()
                    all_items.extend(items)
                    logger.info("Scraped %d items from %s", len(items), source.value)
                except Exception as e:
                    logger.error("Scraper %s failed: %s", source.value, e)
        finally:
            client.close()

        return all_items

    def fetch_capital_flow(self) -> CapitalFlowSnapshot:
        """Phase 1b: Fetch capital flow data from EastMoney."""
        fetcher = EastMoneyCapitalFlowFetcher(
            northbound_days=self._northbound_days,
            sector_top_n=self._sector_top_n,
            dragon_top_n=self._dragon_top_n,
        )
        try:
            snapshot = fetcher.fetch_all()
            logger.info("Capital flow fetched: northbound=%d, sectors=%d, concepts=%d, dragon=%d",
                        len(snapshot.northbound_history),
                        len(snapshot.sector_flows),
                        len(snapshot.concept_flows),
                        len(snapshot.dragon_tiger))
            return snapshot
        finally:
            fetcher.close()

    def dedup(self, items: List[NewsItem]) -> List[NewsItem]:
        """Phase 2: Remove near-duplicates."""
        return deduplicate(items, threshold=self._dedup_threshold)

    def store(self, items: List[NewsItem], cf_snapshot: Optional[CapitalFlowSnapshot] = None) -> int:
        """Phase 3: Store raw items + capital flow to DB."""
        if not self._db:
            return 0

        stored = 0
        for item in items:
            try:
                self._db.save_crypto_news([item.to_dict()])
                stored += 1
            except Exception as e:
                logger.debug("Failed to store item %s: %s", item.id, e)

        # Store capital flow snapshot
        if cf_snapshot and cf_snapshot.has_data:
            try:
                import json as _json
                payload = _json.dumps({
                    "northbound": [nb.__dict__ for nb in cf_snapshot.northbound_history],
                    "sector_flows": [sf.__dict__ for sf in cf_snapshot.sector_flows],
                    "concept_flows": [cf.__dict__ for cf in cf_snapshot.concept_flows],
                    "dragon_tiger": [dt.__dict__ for dt in cf_snapshot.dragon_tiger],
                }, ensure_ascii=False, default=str)
                from datetime import date
                self._db.save_capital_flow_snapshot(
                    snapshot_date=date.today().isoformat(),
                    payload_json=payload,
                )
            except Exception as e:
                logger.warning("Failed to store capital flow snapshot: %s", e)

        logger.info("Stored %d A-share news items", stored)
        return stored

    def analyze(self, items: List[NewsItem],
                cf_snapshot: Optional[CapitalFlowSnapshot] = None) -> List[NewsItem]:
        """Phase 4: Batch LLM analysis."""
        if not self._llm:
            return items
        if not items:
            return items

        # Build capital flow context
        cf_context = ""
        if cf_snapshot and cf_snapshot.has_data:
            cf_context = cf_snapshot.summary_text(
                nb_top=self._northbound_days,
                sector_top=self._sector_top_n,
                dragon_top=self._dragon_top_n,
            ) + "\n"

        all_results: Dict[str, Dict[str, Any]] = {}
        total = len(items)

        for batch_start in range(0, total, BATCH_SIZE):
            batch = items[batch_start:batch_start + BATCH_SIZE]
            batch_end = min(batch_start + len(batch), total)
            logger.info("LLM batch %d-%d / %d", batch_start + 1, batch_end, total)

            news_text = _format_astock_items(batch)
            prompt = ANALYSIS_PROMPT.format(
                capital_flow_context=cf_context,
                news_items=news_text,
            )

            try:
                response = self._llm.chat(
                    system_prompt="你是一位专业的A股市场分析师。只返回JSON格式的结果。",
                    user_prompt=prompt,
                    max_tokens=4096,
                )
                result = _parse_json_response(response)
                for entry in result:
                    if "news_id" in entry:
                        all_results[entry["news_id"]] = entry
                logger.info("Batch %d-%d: %d results", batch_start + 1, batch_end, len(result))
            except Exception as e:
                logger.error("LLM batch %d-%d failed: %s", batch_start + 1, batch_end, e)

        # Apply results
        for item in items:
            result = all_results.get(item.id)
            if result:
                item.affected_sectors = result.get("affected_sectors", [])
                item.affected_stocks = result.get("affected_stocks", [])
                item.sentiment = result.get("sentiment")
                item.reasoning = result.get("reasoning")

                if self._db:
                    try:
                        self._db.save_crypto_news([item.to_dict()])
                    except Exception as e:
                        logger.debug("Failed to update analysis for %s: %s", item.id, e)

        analyzed = len(all_results)
        logger.info("AI analysis complete: %d/%d items", analyzed, total)
        return items

    def summarize(self, items: List[NewsItem],
                  cf_snapshot: Optional[CapitalFlowSnapshot] = None) -> Optional[str]:
        """Phase 5: Generate A-share market summary."""
        if not self._llm or not items:
            return None

        cf_summary = ""
        if cf_snapshot and cf_snapshot.has_data:
            cf_summary = cf_snapshot.summary_text() + "\n"

        lines = []
        for i, item in enumerate(items[:20], 1):
            sectors = ", ".join(item.affected_sectors) if item.affected_sectors else "N/A"
            stocks = ", ".join(item.affected_stocks) if item.affected_stocks else "N/A"
            sentiment = item.sentiment or "未知"
            lines.append(
                f"{i}. [{sentiment}] {item.title}\n"
                f"   板块: {sectors} | 个股: {stocks} | {item.reasoning or ''}"
            )

        analysis_summary = "\n".join(lines)
        prompt = SUMMARIZE_PROMPT.format(
            capital_flow_summary=cf_summary,
            analysis_summary=analysis_summary,
        )

        try:
            return self._llm.chat(
                system_prompt="你是一位A股市场分析师。请用中文回复，不要使用emoji。",
                user_prompt=prompt,
                max_tokens=2048,
            )
        except Exception as e:
            logger.error("Summary generation failed: %s", e)
            return None

    # ── Full pipeline ──

    def run(self, summarize: bool = True) -> Dict[str, Any]:
        """Run the full A-share news ingestion pipeline."""
        logger.info("=== A-share news ingestion pipeline ===")

        # Phase 1
        raw = self.scrape_news()
        cf = self.fetch_capital_flow()

        # Phase 2
        deduped = self.dedup(raw)
        logger.info("Dedup: %d → %d items", len(raw), len(deduped))

        # Phase 3
        stored = self.store(deduped, cf)

        # Phase 4
        analyzed = self.analyze(deduped, cf)

        result = {
            "scraped_count": len(raw),
            "deduped_count": len(deduped),
            "stored_count": stored,
            "analyzed_count": len([i for i in analyzed if i.sentiment]),
            "has_capital_flow": cf.has_data if cf else False,
            "domain": "astock",
        }

        if summarize:
            result["summary"] = self.summarize(analyzed, cf)

        logger.info("=== Pipeline complete ===")
        return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_astock_items(items: List[NewsItem]) -> str:
    """Format A-share news items for the prompt."""
    lines = []
    for item in items:
        source_val = item.source.value if hasattr(item.source, 'value') else str(item.source)
        lines.append(
            f"[新闻ID: {item.id}]\n"
            f"来源: {source_val}\n"
            f"标题: {item.title}\n"
            f"内容: {item.content[:500]}\n"
        )
    return "\n".join(lines)


def _parse_json_response(text: str) -> List[Dict[str, Any]]:
    """Extract and parse JSON from LLM response."""
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        text = match.group()

    data = json.loads(text)
    return data.get("analysis", [])
