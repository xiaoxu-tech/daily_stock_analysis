# -*- coding: utf-8 -*-
"""News API endpoints — unified feed for crypto + A-share news."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from api.v1.schemas.common import ErrorResponse
from api.v1.schemas.news import (
    NewsDetailResponse,
    NewsItem,
    NewsListResponse,
    NewsSource,
    NewsSourceListResponse,
    NewsStats,
    ScrapeRequest,
    ScrapeResponse,
)
from src.storage import DatabaseManager

logger = logging.getLogger(__name__)

router = APIRouter()

# All known scrapers
KNOWN_SOURCES = {
    "crypto": [
        {"source": "CoinDesk", "description": "Global crypto news leader"},
        {"source": "CoinTelegraph", "description": "Crypto news & analysis"},
        {"source": "TheBlock", "description": "Institutional crypto research news"},
        {"source": "Decrypt", "description": "Crypto & Web3 news"},
        {"source": "CryptoSlate", "description": "Crypto news aggregator"},
        {"source": "NewsBTC", "description": "Bitcoin & crypto news"},
        {"source": "BeInCrypto", "description": "Crypto market news"},
        {"source": "CryptoBriefing", "description": "Crypto analysis & news"},
        {"source": "U_Today", "description": "Crypto & blockchain news"},
    ],
    "astock": [
        {"source": "华尔街见闻", "description": "WallStreetCN — 快讯与深度"},
        {"source": "东方财富", "description": "EastMoney — A股要闻"},
        {"source": "证券时报", "description": "STCN — 证券时报网"},
        {"source": "第一财经", "description": "Yicai — 财经新闻"},
        {"source": "界面新闻", "description": "Jiemian — 财经频道"},
        {"source": "Yahoo中国", "description": "Yahoo Finance CN RSS"},
    ],
}


def _bad_request(exc: Exception, *, error: str = "validation_error") -> HTTPException:
    return HTTPException(status_code=400, detail={"error": error, "message": str(exc)})


def _not_found(exc: Exception) -> HTTPException:
    return HTTPException(status_code=404, detail={"error": "not_found", "message": str(exc)})


def _internal_error(message: str, exc: Exception) -> HTTPException:
    logger.error("%s: %s", message, exc, exc_info=True)
    return HTTPException(status_code=500, detail={"error": "internal_error", "message": f"{message}: {str(exc)}"})


def _row_to_news_item(row) -> NewsItem:
    """Convert a DB row dict to a NewsItem schema."""
    import json

    mentioned_coins = None
    mc_raw = row.get("mentioned_coins")
    if mc_raw:
        try:
            mentioned_coins = json.loads(mc_raw) if isinstance(mc_raw, str) else mc_raw
        except (json.JSONDecodeError, TypeError):
            pass

    affected_stocks = None
    as_raw = row.get("affected_stocks")
    if as_raw:
        try:
            affected_stocks = json.loads(as_raw) if isinstance(as_raw, str) else as_raw
        except (json.JSONDecodeError, TypeError):
            pass

    return NewsItem(
        id=row.get("id"),
        news_id=row.get("news_id", ""),
        source=row.get("source", ""),
        source_type=row.get("source_type", ""),
        title=row.get("title", ""),
        url=row.get("url"),
        summary=row.get("summary"),
        content=row.get("content"),
        published_at=str(row.get("published_at") or ""),
        scraped_at=str(row.get("scraped_at") or ""),
        mentioned_coins=mentioned_coins,
        sentiment_score=row.get("sentiment_score"),
        sentiment_label=row.get("sentiment_label"),
        event_type=row.get("event_type"),
        ai_analysis=row.get("ai_analysis"),
        affected_stocks=affected_stocks,
        a_sentiment=row.get("a_sentiment"),
    )


# -- Feed ------------------------------------------------------------------

@router.get(
    "/feed",
    response_model=NewsListResponse,
    responses={500: {"model": ErrorResponse}},
    summary="获取统一新闻流",
    description="返回加密货币和A股新闻的统一列表，支持按来源、类型、币种、日期筛选。",
)
def get_news_feed(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    source_type: Optional[str] = Query(None, description="crypto / astock"),
    source: Optional[str] = Query(None, description="按来源筛选"),
    coin: Optional[str] = Query(None, description="按提及币种筛选"),
    hours: int = Query(168, ge=1, le=720, description="最近N小时"),
):
    try:
        db = DatabaseManager()
        if source_type == "crypto":
            rows = db.get_crypto_news(hours=hours, limit=500)
        elif source_type == "astock":
            rows = db.get_astock_news(hours=hours, limit=500)
        else:
            crypto_rows = db.get_crypto_news(hours=hours, limit=500) or []
            astock_rows = db.get_astock_news(hours=hours, limit=500) or []
            rows = (crypto_rows or []) + (astock_rows or [])

        items = [_row_to_news_item(r) for r in (rows or [])]

        # Filter by source
        if source:
            items = [it for it in items if it.source == source]

        # Filter by coin
        if coin:
            items = [it for it in items if it.mentioned_coins and coin.upper() in [c.upper() for c in it.mentioned_coins]]

        # Sort by published_at descending
        items.sort(key=lambda x: x.published_at or "", reverse=True)

        total = len(items)
        start = (page - 1) * page_size
        page_items = items[start:start + page_size]

        return NewsListResponse(items=page_items, total=total, page=page, page_size=page_size)

    except Exception as exc:
        raise _internal_error("Failed to get news feed", exc)


@router.get(
    "/feed/{news_id}",
    response_model=NewsDetailResponse,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="获取新闻详情",
    description="返回单条新闻的完整内容及AI分析。",
)
def get_news_detail(news_id: str):
    try:
        db = DatabaseManager()
        rows = db.get_crypto_news(hours=720, limit=1000) or []
        rows += db.get_astock_news(hours=720, limit=1000) or []

        matched = None
        for r in rows:
            if r.get("news_id") == news_id:
                matched = r
                break

        if not matched:
            raise _not_found(ValueError(f"News not found: {news_id}"))

        item = _row_to_news_item(matched)
        return NewsDetailResponse(item=item, related_news=[])

    except HTTPException:
        raise
    except Exception as exc:
        raise _internal_error(f"Failed to get news detail for {news_id}", exc)


# -- Sources ---------------------------------------------------------------

@router.get(
    "/sources",
    response_model=NewsSourceListResponse,
    responses={500: {"model": ErrorResponse}},
    summary="获取新闻来源列表",
    description="返回所有可用的新闻来源及其描述。",
)
def list_sources():
    try:
        db = DatabaseManager()
        sources = []
        for st, src_list in KNOWN_SOURCES.items():
            for src in src_list:
                count = 0
                try:
                    if st == "crypto":
                        news_rows = db.get_crypto_news(hours=168, limit=1000) or []
                    else:
                        news_rows = db.get_astock_news(hours=168, limit=1000) or []
                    count = sum(1 for r in news_rows if r.get("source") == src["source"])
                except Exception:
                    pass

                sources.append(NewsSource(
                    source=src["source"],
                    source_type=st,
                    description=src["description"],
                    article_count=count,
                ))

        return NewsSourceListResponse(sources=sources, total_sources=len(sources))

    except Exception as exc:
        raise _internal_error("Failed to list sources", exc)


# -- Stats -----------------------------------------------------------------

@router.get(
    "/stats",
    response_model=NewsStats,
    responses={500: {"model": ErrorResponse}},
    summary="获取新闻统计",
    description="返回新闻数据的聚合统计：总量、24h/7d数量、来源分布、情绪分布、热门币种/股票。",
)
def get_news_stats():
    try:
        db = DatabaseManager()
        crypto_7d = db.get_crypto_news(hours=168, limit=10000) or []
        astock_7d = db.get_astock_news(hours=168, limit=10000) or []
        all_7d = list(crypto_7d) + list(astock_7d)

        now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)

        by_source: dict = {}
        by_sentiment: dict = {}
        top_coins: dict = {}
        top_stocks: dict = {}
        count_24h = 0

        import json
        for r in all_7d:
            src = r.get("source", "unknown")
            by_source[src] = by_source.get(src, 0) + 1

            sent = r.get("sentiment_label") or r.get("a_sentiment") or "unknown"
            by_sentiment[sent] = by_sentiment.get(sent, 0) + 1

            mc = r.get("mentioned_coins")
            if mc:
                try:
                    coins = json.loads(mc) if isinstance(mc, str) else mc
                    for c in coins:
                        top_coins[c] = top_coins.get(c, 0) + 1
                except (json.JSONDecodeError, TypeError):
                    pass

            ast = r.get("affected_stocks")
            if ast:
                try:
                    stocks = json.loads(ast) if isinstance(ast, str) else ast
                    for s in stocks:
                        top_stocks[s] = top_stocks.get(s, 0) + 1
                except (json.JSONDecodeError, TypeError):
                    pass

            pub = r.get("published_at")
            if pub:
                try:
                    pub_dt = __import__("datetime").datetime.fromisoformat(str(pub).replace("Z", "+00:00"))
                    if (now - pub_dt).total_seconds() < 86400:
                        count_24h += 1
                except Exception:
                    pass

        return NewsStats(
            total_articles=len(all_7d),
            articles_24h=count_24h,
            articles_7d=len(all_7d),
            by_source=dict(sorted(by_source.items(), key=lambda x: x[1], reverse=True)),
            by_sentiment=by_sentiment,
            top_coins=dict(sorted(top_coins.items(), key=lambda x: x[1], reverse=True)[:10]),
            top_stocks=dict(sorted(top_stocks.items(), key=lambda x: x[1], reverse=True)[:10]),
        )
    except Exception as exc:
        raise _internal_error("Failed to get news stats", exc)


# -- Scrape trigger --------------------------------------------------------

@router.post(
    "/scrape",
    response_model=ScrapeResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="触发新闻抓取",
    description="手动触发加密货币或A股新闻的抓取和分析。",
)
def trigger_scrape(request: ScrapeRequest):
    import time
    start_time = time.time()
    errors: list = []
    total_fetched = 0
    new_articles = 0
    duplicates = 0
    sources_scraped = 0

    try:
        if request.source_type in ("crypto", "both"):
            try:
                from src.intel.crypto_ingestor import CryptoIngestor
                ingestor = CryptoIngestor(max_articles=request.max_articles)
                result = ingestor.run()
                total_fetched += result.get("total_fetched", 0)
                new_articles += result.get("new_articles", 0)
                duplicates += result.get("duplicates", 0)
                sources_scraped += result.get("sources", 0)
            except Exception as e:
                errors.append(f"crypto scraper: {e}")

        if request.source_type in ("astock", "both"):
            try:
                from src.intel.astock_ingestor import AstockIngestor
                ingestor = AstockIngestor(max_articles=request.max_articles)
                result = ingestor.run()
                total_fetched += result.get("total_fetched", 0)
                new_articles += result.get("new_articles", 0)
                duplicates += result.get("duplicates", 0)
                sources_scraped += result.get("sources", 0)
            except Exception as e:
                errors.append(f"astock scraper: {e}")

        elapsed = round(time.time() - start_time, 2)

        return ScrapeResponse(
            status="ok" if not errors else "partial",
            source_type=request.source_type,
            sources_scraped=sources_scraped,
            total_fetched=total_fetched,
            new_articles=new_articles,
            duplicates_skipped=duplicates,
            errors=errors,
            elapsed_seconds=elapsed,
        )
    except Exception as exc:
        raise _internal_error("Failed to trigger scrape", exc)
