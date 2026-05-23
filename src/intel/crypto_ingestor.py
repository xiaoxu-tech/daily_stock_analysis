# -*- coding: utf-8 -*-
"""Crypto news ingestion pipeline orchestrator.

Wraps the full crypto news pipeline:
    1. Scrape 9 RSS feeds
    2. Fuzzy deduplicate
    3. Store raw items to DB
    4. Batch analyze via LLM (sentiment, sectors, coins)
    5. Update DB with analysis results
    6. Generate market summary (optional)
"""

from __future__ import annotations

import json
import logging
import re
from typing import Optional, List, Dict, Any

from src.scrapers.models import NewsItem, NewsSource
from src.scrapers.crypto_rss import create_crypto_scrapers, SOURCE_LABELS
from src.scrapers.dedup import deduplicate
from src.analyzer_prompts.crypto_news_prompt import (
    ANALYSIS_PROMPT,
    SUMMARIZE_PROMPT,
)

logger = logging.getLogger(__name__)

BATCH_SIZE = 15  # items per LLM call


class CryptoIngestor:
    """Orchestrate crypto news scraping → dedup → store → analyze → summarize."""

    def __init__(
        self,
        db_manager=None,
        llm_provider=None,
        enabled_sources: Optional[List[NewsSource]] = None,
        max_per_source: int = 20,
        dedup_threshold: float = 0.75,
        request_delay: float = 0.5,
    ):
        """Initialize the crypto news ingestor.

        Args:
            db_manager: DSA's DatabaseManager singleton for crypto_news + coin_prices tables.
            llm_provider: Any callable with a chat(system, prompt, max_tokens) → str method.
            enabled_sources: Which RSS sources to scrape. None = all 9.
            max_per_source: Max items per RSS feed.
            dedup_threshold: rapidfuzz similarity threshold.
            request_delay: Seconds between HTTP requests.
        """
        self._db = db_manager
        self._llm = llm_provider
        self._enabled_sources = enabled_sources
        self._max_per_source = max_per_source
        self._dedup_threshold = dedup_threshold
        self._request_delay = request_delay

    # ── Pipeline phases ──

    def scrape(self) -> List[NewsItem]:
        """Phase 1: Scrape all enabled RSS sources."""
        scrapers = create_crypto_scrapers(
            enabled_sources=self._enabled_sources,
            max_per_source=self._max_per_source,
            request_delay=self._request_delay,
        )
        all_items: List[NewsItem] = []
        for scraper in scrapers:
            try:
                items = scraper.scrape()
                all_items.extend(items)
                logger.info("Scraped %d items from %s", len(items), scraper.source().value)
            except Exception as e:
                logger.error("Scraper %s failed: %s", scraper.source().value, e)
            finally:
                scraper.close()
        return all_items

    def dedup(self, items: List[NewsItem]) -> List[NewsItem]:
        """Phase 2: Remove near-duplicates by title similarity."""
        return deduplicate(items, threshold=self._dedup_threshold)

    def store(self, items: List[NewsItem]) -> int:
        """Phase 3: Store raw news items to DB (crypto_news table)."""
        if not self._db:
            logger.warning("No DB manager configured; skipping store")
            return 0

        stored = 0
        for item in items:
            try:
                self._db.save_crypto_news([item.to_dict()])
                stored += 1
            except Exception as e:
                logger.debug("Failed to store item %s: %s", item.id, e)
        logger.info("Stored %d/%d items to DB", stored, len(items))
        return stored

    def analyze(self, items: List[NewsItem]) -> List[NewsItem]:
        """Phase 4: Batch LLM analysis (sentiment, sectors, coins)."""
        if not self._llm:
            logger.warning("No LLM provider configured; skipping analysis")
            return items
        if not items:
            return items

        all_results: Dict[str, Dict[str, Any]] = {}
        total = len(items)

        for batch_start in range(0, total, BATCH_SIZE):
            batch = items[batch_start:batch_start + BATCH_SIZE]
            batch_end = min(batch_start + len(batch), total)
            logger.info("LLM batch %d-%d / %d", batch_start + 1, batch_end, total)

            news_text = _format_items_for_prompt(batch)
            prompt = ANALYSIS_PROMPT.format(news_items=news_text)

            try:
                response = self._llm.chat(
                    system_prompt="You are a cryptocurrency market analyst. Always respond in JSON format as instructed. No extra text.",
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

        # Apply results back to items
        for item in items:
            result = all_results.get(item.id)
            if result:
                item.mentioned_coins = result.get("mentioned_coins", [])
                item.affected_sectors = result.get("affected_sectors", [])
                item.sentiment = result.get("sentiment")
                item.sentiment_score = result.get("sentiment_score")
                item.event_type = result.get("event_type")
                item.relevance_score = result.get("relevance_score")
                item.reasoning = result.get("reasoning")
                item.concept_coins = result.get("concept_coins", [])

            # Update DB with analysis results
            if self._db and result:
                try:
                    self._db.save_crypto_news([item.to_dict()])
                except Exception as e:
                    logger.debug("Failed to update analysis for %s: %s", item.id, e)

        analyzed = len(all_results)
        logger.info("AI analysis complete: %d/%d items analyzed", analyzed, total)
        return items

    def summarize(self, items: List[NewsItem]) -> Optional[str]:
        """Phase 5: Generate market summary from analyzed items."""
        if not self._llm or not items:
            return None

        lines = []
        for i, item in enumerate(items[:20], 1):
            coins = ", ".join(item.mentioned_coins) if item.mentioned_coins else "N/A"
            sectors = ", ".join(item.affected_sectors) if item.affected_sectors else "N/A"
            sentiment_label = item.sentiment or "unknown"
            score = f"({item.sentiment_score:.2f})" if item.sentiment_score is not None else ""
            source_label = SOURCE_LABELS.get(item.source, item.source.value if hasattr(item.source, 'value') else str(item.source))
            lines.append(
                f"{i}. [{sentiment_label}{score}] [{source_label}] {item.title}\n"
                f"   Coins: {coins} | Sectors: {sectors} | {item.reasoning or ''}"
            )

        summary_text = "\n".join(lines)
        prompt = SUMMARIZE_PROMPT.format(analysis_summary=summary_text)

        try:
            return self._llm.chat(
                system_prompt="You are a crypto market analyst. Write in clear English. No emoji.",
                user_prompt=prompt,
                max_tokens=2048,
            )
        except Exception as e:
            logger.error("Summary generation failed: %s", e)
            return None

    # ── Full pipeline ──

    def run(self, summarize: bool = True) -> Dict[str, Any]:
        """Run the full crypto news ingestion pipeline.

        Returns:
            Dict with keys: scraped_count, deduped_count, stored_count,
            analyzed_count, summary (optional).
        """
        logger.info("=== Crypto news ingestion pipeline ===")

        # Phase 1-2: Scrape + dedup
        raw = self.scrape()
        deduped = self.dedup(raw)
        logger.info("Dedup: %d → %d items", len(raw), len(deduped))

        # Phase 3: Store
        stored = self.store(deduped)

        # Phase 4: Analyze
        analyzed = self.analyze(deduped)

        result = {
            "scraped_count": len(raw),
            "deduped_count": len(deduped),
            "stored_count": stored,
            "analyzed_count": len([i for i in analyzed if i.sentiment]),
            "domain": "crypto",
        }

        # Phase 5: Summarize
        if summarize:
            result["summary"] = self.summarize(analyzed)

        logger.info("=== Pipeline complete: %s ===", {k: v for k, v in result.items() if k != "summary"})
        return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _format_items_for_prompt(items: List[NewsItem]) -> str:
    """Serialize a batch of NewsItems into prompt text format."""
    lines = []
    for item in items:
        source_val = item.source.value if hasattr(item.source, 'value') else str(item.source)
        lines.append(
            f"[ID: {item.id}]\n"
            f"Source: {source_val}\n"
            f"Title: {item.title}\n"
            f"Content: {item.content[:500]}\n"
        )
    return "\n".join(lines)


def _parse_json_response(text: str) -> List[Dict[str, Any]]:
    """Extract and parse JSON from LLM response (handles code fences)."""
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        text = match.group()

    data = json.loads(text)
    return data.get("analysis", [])
