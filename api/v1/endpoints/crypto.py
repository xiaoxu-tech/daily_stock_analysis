# -*- coding: utf-8 -*-
"""Crypto API endpoints — coins, signals, fear & greed, sectors, macro, patterns."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from api.v1.schemas.common import ErrorResponse
from api.v1.schemas.crypto import (
    AnalyzeCoinRequest,
    AnalyzeCoinResponse,
    CoinListResponse,
    CoinPrice,
    CompositeSignalResponse,
    FearGreedHistoryResponse,
    FearGreedItem,
    MacroSummaryResponse,
    OHLCVItem,
    OHLCVResponse,
    PatternResponse,
    SectorListResponse,
    SignalHistoryItem,
    SignalHistoryResponse,
)
from src.data.crypto_sector_loader import load_sector_map
from src.signals.crypto.fusion import SignalFusion, classify_signal, SIGNAL_CN
from src.signals.crypto.enhanced_indicators import compute_enhanced_indicators
from src.storage import DatabaseManager

logger = logging.getLogger(__name__)

router = APIRouter()

# Default tracked coins (top 20 by market cap)
DEFAULT_COINS = [
    "BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "AVAX", "DOT", "MATIC",
    "LTC", "UNI", "LINK", "ATOM", "ETC", "XLM", "FIL", "TRX", "SHIB", "NEAR",
]


# -- helpers ---------------------------------------------------------------

def _bad_request(exc: Exception, *, error: str = "validation_error") -> HTTPException:
    return HTTPException(status_code=400, detail={"error": error, "message": str(exc)})


def _not_found(exc: Exception) -> HTTPException:
    return HTTPException(status_code=404, detail={"error": "not_found", "message": str(exc)})


def _internal_error(message: str, exc: Exception) -> HTTPException:
    logger.error("%s: %s", message, exc, exc_info=True)
    return HTTPException(status_code=500, detail={"error": "internal_error", "message": f"{message}: {str(exc)}"})


# -- Coin listing / details ------------------------------------------------

@router.get(
    "/coins",
    response_model=CoinListResponse,
    responses={500: {"model": ErrorResponse}},
    summary="获取跟踪的加密货币列表",
    description="返回所有跟踪币种的最新价格、24h/7d涨跌幅、市值排名及所属板块。支持分页。",
)
def list_coins(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    sector: Optional[str] = Query(None, description="按板块筛选"),
    sort_by: Optional[str] = Query("rank", description="排序字段: rank / change_24h / market_cap"),
):
    try:
        sector_map = load_sector_map()
        from data_provider.crypto.coinpaprika_fetcher import CoinpaprikaFetcher

        fetcher = CoinpaprikaFetcher()
        coins = []

        symbols = DEFAULT_COINS
        if sector:
            symbols = sector_map.get(sector, {}).get("coins", [])

        for sym in symbols:
            try:
                paprika_id = sector_map.get(sym, {}).get("paprika_id") if isinstance(sector_map.get(sym), dict) else None
                if not paprika_id:
                    from src.data.crypto_sector_loader import get_paprika_id
                    paprika_id = get_paprika_id(sym)
                if not paprika_id:
                    continue

                ticker = fetcher.get_ticker(paprika_id)
                if ticker:
                    sector_name = None
                    for sec_key, sec_data in sector_map.items():
                        if isinstance(sec_data, dict) and sym.upper() in [c.upper() for c in sec_data.get("coins", [])]:
                            sector_name = sec_key
                            break

                    coins.append(CoinPrice(
                        symbol=sym.upper(),
                        name=ticker.get("name") or sym,
                        price_usd=ticker.get("price_usd"),
                        change_24h=ticker.get("percent_change_24h"),
                        change_7d=ticker.get("percent_change_7d"),
                        market_cap_usd=ticker.get("market_cap_usd"),
                        volume_24h_usd=ticker.get("volume_24h"),
                        rank=ticker.get("rank"),
                        sector=sector_name,
                        updated_at=ticker.get("last_updated"),
                    ))
            except Exception as e:
                logger.debug("Failed to fetch %s: %s", sym, e)
                continue

        # Sort
        if sort_by == "change_24h":
            coins.sort(key=lambda c: c.change_24h or 0, reverse=True)
        elif sort_by == "market_cap":
            coins.sort(key=lambda c: c.market_cap_usd or 0, reverse=True)
        else:
            coins.sort(key=lambda c: c.rank or 999)

        total = len(coins)
        start = (page - 1) * page_size
        page_items = coins[start:start + page_size]

        return CoinListResponse(items=page_items, total=total, page=page, page_size=page_size)

    except Exception as exc:
        raise _internal_error("Failed to list coins", exc)


@router.get(
    "/coins/{symbol}",
    response_model=CoinPrice,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="获取单个币种详情",
    description="返回指定币种的最新价格、涨跌幅、市值等数据。",
)
def get_coin(symbol: str):
    try:
        from data_provider.crypto.coinpaprika_fetcher import CoinpaprikaFetcher
        from src.data.crypto_sector_loader import get_paprika_id

        paprika_id = get_paprika_id(symbol.upper())
        if not paprika_id:
            raise _not_found(ValueError(f"Unknown coin: {symbol}"))

        fetcher = CoinpaprikaFetcher()
        ticker = fetcher.get_ticker(paprika_id)
        if not ticker:
            raise _not_found(ValueError(f"No data for {symbol}"))

        sector_map = load_sector_map()
        sector_name = None
        for sec_key, sec_data in sector_map.items():
            if isinstance(sec_data, dict) and symbol.upper() in [c.upper() for c in sec_data.get("coins", [])]:
                sector_name = sec_key
                break

        return CoinPrice(
            symbol=symbol.upper(),
            name=ticker.get("name") or symbol,
            price_usd=ticker.get("price_usd"),
            change_24h=ticker.get("percent_change_24h"),
            change_7d=ticker.get("percent_change_7d"),
            market_cap_usd=ticker.get("market_cap_usd"),
            volume_24h_usd=ticker.get("volume_24h"),
            rank=ticker.get("rank"),
            sector=sector_name,
            updated_at=ticker.get("last_updated"),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise _internal_error(f"Failed to get coin {symbol}", exc)


# -- Signal ----------------------------------------------------------------

@router.get(
    "/coins/{symbol}/signals",
    response_model=CompositeSignalResponse,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="获取币种综合信号",
    description="返回6因子加权综合交易信号，包含AI情绪、技术分析、恐惧贪婪、动量、宏观、链上数据。",
)
def get_coin_signals(symbol: str):
    try:
        db = DatabaseManager()
        sf = SignalFusion(db_manager=db)
        result = sf.get_composite_signal(symbol.upper())

        if result.get("signal") == "no_data":
            raise _not_found(ValueError(f"No signal data for {symbol}"))

        return CompositeSignalResponse(**result)
    except HTTPException:
        raise
    except Exception as exc:
        raise _internal_error(f"Failed to get signals for {symbol}", exc)


@router.get(
    "/coins/{symbol}/signals/history",
    response_model=SignalHistoryResponse,
    responses={500: {"model": ErrorResponse}},
    summary="获取历史信号记录",
    description="返回指定币种的历史综合信号分数和标签。",
)
def get_signal_history(
    symbol: str,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    days: int = Query(30, ge=1, le=365, description="回溯天数"),
):
    try:
        db = DatabaseManager()
        rows = db.get_composite_signal_history(asset_code=symbol.upper(), days=days)
        items = [
            SignalHistoryItem(
                id=row.get("id", 0),
                asset_code=row.get("asset_code", symbol),
                composite_score=row.get("composite_score", 0.0),
                signal_label=row.get("signal_label", ""),
                created_at=str(row.get("created_at", "")),
            )
            for row in (rows or [])
        ]
        total = len(items)
        start = (page - 1) * page_size
        page_items = items[start:start + page_size]
        return SignalHistoryResponse(items=page_items, total=total, page=page, page_size=page_size)
    except Exception as exc:
        raise _internal_error(f"Failed to get signal history for {symbol}", exc)


# -- Fear & Greed ----------------------------------------------------------

@router.get(
    "/fear-greed",
    response_model=FearGreedItem,
    responses={500: {"model": ErrorResponse}},
    summary="获取当前恐惧贪婪指数",
    description="返回 alternative.me 加密货币恐惧贪婪指数（0-100），含信号解读。",
)
def get_fear_greed():
    try:
        from data_provider.crypto.fear_greed_fetcher import FearGreedClient
        client = FearGreedClient()
        fng = client.get_signal()
        client.close()

        if not fng or fng.get("label") == "no_data":
            raise _not_found(ValueError("Fear & Greed data unavailable"))

        return FearGreedItem(
            value=fng.get("latest_value", 0),
            label=fng.get("label", "neutral"),
            signal=fng.get("signal", "neutral"),
            score=fng.get("score", 0.0),
            timestamp=fng.get("timestamp"),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise _internal_error("Failed to get Fear & Greed index", exc)


@router.get(
    "/fear-greed/history",
    response_model=FearGreedHistoryResponse,
    responses={500: {"model": ErrorResponse}},
    summary="获取恐惧贪婪历史数据",
    description="返回恐惧贪婪指数历史数据（默认30天）。",
)
def get_fear_greed_history(
    days: int = Query(30, ge=1, le=365, description="回溯天数"),
):
    try:
        from data_provider.crypto.fear_greed_fetcher import FearGreedClient
        client = FearGreedClient()
        history = client.get_history(days=days)
        client.close()

        if not history:
            return FearGreedHistoryResponse(items=[], latest=None, total=0, days=days)

        items = [
            FearGreedHistoryItem(
                timestamp=h.get("timestamp", ""),
                value=h.get("value", 0),
                label=h.get("label", "neutral"),
            )
            for h in history
        ]

        latest = items[0] if items else None
        latest_reading = None
        if latest:
            fng = client.get_signal()
            if fng:
                latest_reading = FearGreedItem(
                    value=latest.value,
                    label=latest.label,
                    signal=fng.get("signal", "neutral"),
                    score=fng.get("score", 0.0),
                    timestamp=latest.timestamp,
                )

        return FearGreedHistoryResponse(
            items=items, latest=latest_reading, total=len(items), days=days,
        )
    except Exception as exc:
        raise _internal_error("Failed to get Fear & Greed history", exc)


# -- Sectors ---------------------------------------------------------------

@router.get(
    "/sectors",
    response_model=SectorListResponse,
    responses={500: {"model": ErrorResponse}},
    summary="获取加密货币板块列表",
    description="返回所有板块及其包含的币种。",
)
def list_sectors():
    try:
        sector_map = load_sector_map()
        sectors = []
        total_coins = 0

        for key, data in sector_map.items():
            if not isinstance(data, dict):
                continue
            coins = data.get("coins", [])
            sectors.append({
                "key": key,
                "name": data.get("name", key),
                "coins": coins,
                "coin_count": len(coins),
            })
            total_coins += len(coins)

        return SectorListResponse(
            sectors=sectors,
            total_sectors=len(sectors),
            total_coins=total_coins,
        )
    except Exception as exc:
        raise _internal_error("Failed to list sectors", exc)


# -- Macro -----------------------------------------------------------------

@router.get(
    "/macro",
    response_model=MacroSummaryResponse,
    responses={500: {"model": ErrorResponse}},
    summary="获取宏观指标摘要",
    description="返回 DXY、VIX、利率、通胀等宏观指标及其对加密货币的信号解读。",
)
def get_macro():
    try:
        from data_provider.crypto.macro_fetcher import MacroClient
        client = MacroClient()
        signals = client.get_all_signals()
        client.close()

        from api.v1.schemas.crypto import MacroSignal
        indicators = {
            key: MacroSignal(
                name=key,
                latest_value=val.get("latest_value") if isinstance(val, dict) else None,
                score=val.get("score") if isinstance(val, dict) else None,
                signal=val.get("signal") if isinstance(val, dict) else None,
            )
            for key, val in signals.items()
            if key not in ("composite_score", "composite_label", "summary")
            and isinstance(val, dict)
        }

        return MacroSummaryResponse(
            composite_score=signals.get("composite_score", 0.0),
            composite_label=signals.get("composite_label", "no_data"),
            indicators=indicators,
            summary=signals.get("summary"),
        )
    except Exception as exc:
        raise _internal_error("Failed to get macro signals", exc)


# -- OHLCV -----------------------------------------------------------------

@router.get(
    "/coins/{symbol}/ohlcv",
    response_model=OHLCVResponse,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="获取币种K线数据",
    description="返回指定币种的 OHLCV 历史数据。支持 1h/4h/1d 周期。",
)
def get_coin_ohlcv(
    symbol: str,
    interval: str = Query("1d", description="K线周期: 1h / 4h / 1d"),
    days: int = Query(30, ge=1, le=365, description="回溯天数"),
):
    try:
        import httpx
        import pandas as pd
        from datetime import datetime, timedelta, timezone
        from src.data.crypto_sector_loader import get_paprika_id

        paprika_id = get_paprika_id(symbol.upper())
        if not paprika_id:
            raise _not_found(ValueError(f"Unknown coin: {symbol}"))

        now = datetime.now(timezone.utc)
        if interval == "1h":
            start = (now - timedelta(hours=min(days * 24, 720))).strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            start = (now - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")

        r = httpx.get(
            f"https://api.coinpaprika.com/v1/tickers/{paprika_id}/historical",
            params={"start": start, "interval": interval},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=20,
        )
        if r.status_code != 200:
            raise _not_found(ValueError(f"Price data unavailable for {symbol}"))

        records = r.json()
        items = [
            OHLCVItem(
                timestamp=rec.get("timestamp", ""),
                open=rec.get("price"),
                high=rec.get("price"),
                low=rec.get("price"),
                close=float(rec.get("price", 0)),
                volume=rec.get("volume_24h"),
            )
            for rec in records
        ]

        return OHLCVResponse(coin=symbol.upper(), interval=interval, items=items, count=len(items))
    except HTTPException:
        raise
    except Exception as exc:
        raise _internal_error(f"Failed to get OHLCV for {symbol}", exc)


# -- Patterns --------------------------------------------------------------

@router.get(
    "/coins/{symbol}/patterns",
    response_model=PatternResponse,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="检测币种K线形态",
    description="识别最近K线的9种形态：十字星、锤子线、吞没、早晨之星、双底等。",
)
def get_coin_patterns(
    symbol: str,
    days: int = Query(60, ge=10, le=365, description="回溯天数"),
):
    try:
        import httpx
        import pandas as pd
        from datetime import datetime, timedelta, timezone
        from src.data.crypto_sector_loader import get_paprika_id

        paprika_id = get_paprika_id(symbol.upper())
        if not paprika_id:
            raise _not_found(ValueError(f"Unknown coin: {symbol}"))

        now = datetime.now(timezone.utc)
        start = (now - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")

        r = httpx.get(
            f"https://api.coinpaprika.com/v1/tickers/{paprika_id}/historical",
            params={"start": start, "interval": "1d"},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=20,
        )
        if r.status_code != 200:
            raise _not_found(ValueError(f"Not enough data for pattern detection on {symbol}"))

        records = r.json()
        if len(records) < 10:
            raise _not_found(ValueError(f"Need at least 10 candles, got {len(records)}"))

        df = pd.DataFrame(records)
        df["close"] = pd.to_numeric(df["price"], errors="coerce")
        df["open"] = df["close"]
        df["high"] = df["close"]
        df["low"] = df["close"]
        df = df.dropna(subset=["close"])

        enhanced = compute_enhanced_indicators(df)
        pat = enhanced.get("patterns", {})

        from api.v1.schemas.crypto import DetectedPattern
        patterns = [
            DetectedPattern(
                pattern=p.get("pattern", ""),
                type=p.get("type", ""),
                strength=p.get("strength"),
                desc=p.get("desc"),
                candle_offset=p.get("candle_offset"),
            )
            for p in pat.get("patterns", [])
        ]

        return PatternResponse(
            coin=symbol.upper(),
            patterns_count=pat.get("patterns_count", 0),
            pattern_signal=pat.get("pattern_signal"),
            pattern_score=pat.get("pattern_score"),
            summary=pat.get("summary"),
            current_price=pat.get("current_price"),
            patterns=patterns,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise _internal_error(f"Failed to detect patterns for {symbol}", exc)


# -- Analyze ---------------------------------------------------------------

@router.post(
    "/analyze",
    response_model=AnalyzeCoinResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="按需分析币种",
    description="触发对指定币种的即时分析（信号+形态，可选新闻）。",
)
def analyze_coin(request: AnalyzeCoinRequest):
    try:
        result = AnalyzeCoinResponse(coin=request.symbol.upper())
        from datetime import datetime, timezone

        if request.include_signals:
            try:
                sf = SignalFusion()
                sig = sf.get_composite_signal(request.symbol.upper())
                if sig and sig.get("composite") is not None:
                    result.signal = CompositeSignalResponse(**sig)
            except Exception as e:
                logger.warning("Signal computation failed for %s: %s", request.symbol, e)

        result.analysis_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        result.status = "ok"
        return result
    except Exception as exc:
        raise _internal_error(f"Failed to analyze {request.symbol}", exc)
