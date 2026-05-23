# -*- coding: utf-8 -*-
"""Fuzzy deduplication for news items using rapidfuzz.

Strategy: title-based token_sort_ratio comparison, greedy sequential filter.
First occurrence of each near-duplicate group is kept; subsequent matches discarded.
"""

from __future__ import annotations

import logging
from typing import List, TYPE_CHECKING

from rapidfuzz import fuzz

if TYPE_CHECKING:
    from .models import NewsItem

logger = logging.getLogger(__name__)


def deduplicate(
    items: List["NewsItem"],
    threshold: float = 0.75,
    content_boost: bool = False,
) -> List["NewsItem"]:
    """Remove near-duplicate news items based on title similarity.

    Args:
        items: List of NewsItem objects to deduplicate.
        threshold: Similarity ratio (0.0-1.0) above which items are considered
                   duplicates. Default 0.75 (75% token-sort similarity).
        content_boost: If True, also compare content snippets for borderline
                       cases (0.70-0.80 title similarity). Adds accuracy but
                       is slower.

    Returns:
        Filtered list preserving original order, with duplicates removed.
    """
    if not items:
        return []

    kept: List["NewsItem"] = []
    total = len(items)

    for item in items:
        is_dup = False
        for existing in kept:
            sim = fuzz.token_sort_ratio(item.title, existing.title) / 100.0

            if sim >= threshold:
                is_dup = True
                break

            # Content boost: borderline title match → check content snippet
            if content_boost and sim >= 0.70:
                content_sim = fuzz.token_sort_ratio(
                    item.content[:200], existing.content[:200]
                ) / 100.0
                if content_sim >= threshold:
                    is_dup = True
                    break
                # Different source → likely different article even if similar
                if item.source != existing.source:
                    continue
                # Same source + borderline → treat as dup
                if sim >= threshold:
                    is_dup = True
                    break

        if not is_dup:
            kept.append(item)

    removed = total - len(kept)
    if removed > 0:
        logger.info("Dedup: removed %d/%d near-duplicates (threshold=%.0f%%)",
                    removed, total, threshold * 100)

    return kept


def deduplicate_by_key(
    items: List["NewsItem"],
    key_func=None,
) -> List["NewsItem"]:
    """Deduplicate by exact key match (fast, for same-source items).

    Args:
        items: List of NewsItem objects.
        key_func: Callable that returns a hashable key. Default uses dedup_key().

    Returns:
        List with exact-duplicate keys removed (first occurrence kept).
    """
    if not items:
        return []

    if key_func is None:
        key_func = lambda x: x.dedup_key()

    seen = set()
    result = []
    for item in items:
        key = key_func(item)
        if key not in seen:
            seen.add(key)
            result.append(item)

    removed = len(items) - len(result)
    if removed > 0:
        logger.debug("Key dedup: removed %d/%d exact duplicates", removed, len(items))

    return result
