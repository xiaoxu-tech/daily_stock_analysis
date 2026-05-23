# -*- coding: utf-8 -*-
"""Crypto API schemas — coins, signals, fear & greed, sectors, macro."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Coin / Price
# ---------------------------------------------------------------------------

class CoinPrice(BaseModel):
    """Coin latest price from CoinPaprika."""
    symbol: str = Field(..., description="币种代码，如 BTC")
    name: Optional[str] = Field(None, description="币种名称")
    price_usd: Optional[float] = Field(None, description="USD 价格")
    change_24h: Optional[float] = Field(None, description="24h 涨跌幅 (%)")
    change_7d: Optional[float] = Field(None, description="7d 涨跌幅 (%))")
    market_cap_usd: Optional[float] = Field(None, description="市值 (USD)")
    volume_24h_usd: Optional[float] = Field(None, description="24h 成交量 (USD)")
    rank: Optional[int] = Field(None, description="市值排名")
    sector: Optional[str] = Field(None, description="所属板块")
    updated_at: Optional[str] = Field(None, description="数据更新时间")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "symbol": "BTC",
            "name": "Bitcoin",
            "price_usd": 67890.50,
            "change_24h": 2.35,
            "change_7d": -1.20,
            "market_cap_usd": 1332000000000,
            "volume_24h_usd": 28400000000,
            "rank": 1,
            "sector": "Layer1",
            "updated_at": "2025-01-15T10:30:00Z",
        }
    })


class CoinListResponse(BaseModel):
    """Paginated list of tracked coins."""
    items: List[CoinPrice] = Field(default_factory=list)
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Signal
# ---------------------------------------------------------------------------

class SignalComponent(BaseModel):
    """Single component of the composite signal."""
    score: float = Field(..., description="该组件分数 [-1, +1]")
    signal: Optional[str] = Field(None, description="信号标签")
    detail: Optional[Dict[str, Any]] = Field(None, description="组件详情")


class EnhancedTechnicalDetail(BaseModel):
    """DSA-derived enhanced indicator breakdown."""
    signal: Optional[str] = Field(None, description="增强信号标签")
    score: Optional[float] = Field(None, description="增强综合分数 [-1, +1]")
    patterns: Optional[str] = Field(None, description="检测到的K线形态")
    patterns_count: Optional[int] = Field(None, description="形态数量")
    volume_status: Optional[str] = Field(None, description="量能状态")
    rsi_signal: Optional[str] = Field(None, description="多周期RSI信号")
    bias_signal: Optional[str] = Field(None, description="乖离率信号")
    trend_state: Optional[str] = Field(None, description="趋势状态")
    sub_scores: Optional[Dict[str, Optional[float]]] = Field(
        None, description="子项分数: patterns/volume/rsi/bias/trend"
    )


class TimeframeDetail(BaseModel):
    """Single-timeframe technical indicator snapshot."""
    score: float
    rsi: Optional[float] = None
    macd_signal: Optional[str] = None
    bb_signal: Optional[str] = None
    ema_trend: Optional[str] = None


class TechnicalDetail(BaseModel):
    """Full multi-timeframe technical signal breakdown."""
    signal: Optional[str] = Field(None, description="技术信号标签")
    rsi: Optional[float] = None
    macd: Optional[str] = None
    bb: Optional[str] = None
    ema: Optional[str] = None
    score: float = Field(..., description="技术综合分数 [-1, +1]")
    ta_score: Optional[float] = Field(None, description="ta库指标分数")
    enhanced_score: Optional[float] = Field(None, description="增强指标分数")
    alignment: Optional[str] = Field(None, description="多时间框架一致方向")
    enhanced: Optional[EnhancedTechnicalDetail] = None
    timeframes: Optional[Dict[str, TimeframeDetail]] = None


class CompositeSignalResponse(BaseModel):
    """Full 6-factor composite signal for a single coin."""
    coin: str = Field(..., description="币种代码")
    composite: float = Field(..., description="综合分数 [-1, +1]")
    signal: str = Field(..., description="综合信号 (strong_buy/buy/neutral/sell/strong_sell)")
    signal_cn: str = Field(..., description="综合信号（中文）")
    components: Dict[str, SignalComponent] = Field(
        default_factory=dict, description="各因子详情"
    )
    weights: Dict[str, float] = Field(default_factory=dict, description="各因子权重")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "coin": "BTC",
            "composite": 0.42,
            "signal": "buy",
            "signal_cn": "🟢 买入",
            "components": {
                "sentiment": {"score": 0.35, "signal": "slightly_bullish"},
                "technical": {"score": 0.28, "signal": "multi_tf"},
                "fear_greed": {"score": -0.15, "signal": "fear"},
                "momentum": {"score": 0.50, "signal": "positive"},
                "macro": {"score": 0.20, "signal": "neutral"},
                "onchain": {"score": 0.10, "signal": "neutral"},
            },
            "weights": {
                "sentiment": 0.28, "technical": 0.22, "fear_greed": 0.10,
                "momentum": 0.14, "macro": 0.18, "onchain": 0.08,
            },
        }
    })


class SignalHistoryItem(BaseModel):
    """Historical composite signal record."""
    id: int
    asset_code: str
    composite_score: float
    signal_label: str
    created_at: Optional[str] = None


class SignalHistoryResponse(BaseModel):
    """Paginated signal history."""
    items: List[SignalHistoryItem] = Field(default_factory=list)
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Fear & Greed
# ---------------------------------------------------------------------------

class FearGreedItem(BaseModel):
    """Single Fear & Greed reading."""
    value: int = Field(..., description="恐惧贪婪指数 (0-100)")
    label: str = Field(..., description="分类标签")
    signal: str = Field(..., description="信号方向")
    score: float = Field(..., description="信号分数 [-1, +1]")
    timestamp: Optional[str] = Field(None, description="数据时间")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "value": 72,
            "label": "greed",
            "signal": "neutral",
            "score": -0.15,
            "timestamp": "2025-01-15T10:00:00Z",
        }
    })


class FearGreedHistoryItem(BaseModel):
    """Historical Fear & Greed data point."""
    timestamp: str
    value: int
    label: str


class FearGreedHistoryResponse(BaseModel):
    """Historical Fear & Greed data."""
    items: List[FearGreedHistoryItem] = Field(default_factory=list)
    latest: Optional[FearGreedItem] = None
    total: int
    days: int


# ---------------------------------------------------------------------------
# Sector
# ---------------------------------------------------------------------------

class CryptoSector(BaseModel):
    """Crypto sector grouping."""
    key: str = Field(..., description="板块标识")
    name: str = Field(..., description="板块中文名")
    coins: List[str] = Field(default_factory=list, description="包含币种")
    coin_count: int = Field(0, description="币种数")


class SectorListResponse(BaseModel):
    """List of crypto sectors."""
    sectors: List[CryptoSector] = Field(default_factory=list)
    total_sectors: int
    total_coins: int


# ---------------------------------------------------------------------------
# Macro
# ---------------------------------------------------------------------------

class MacroSignal(BaseModel):
    """Macro indicator with signal interpretation."""
    name: str
    latest_value: Optional[float] = None
    score: Optional[float] = Field(None, description="[-1, +1] 方向")
    signal: Optional[str] = Field(None, description="bullish/neutral/bearish")


class MacroSummaryResponse(BaseModel):
    """Composite macro regime summary."""
    composite_score: float = Field(..., description="宏观综合分数 [-1,+1]")
    composite_label: str = Field(..., description="宏观综合标签")
    indicators: Dict[str, MacroSignal] = Field(default_factory=dict)
    summary: Optional[str] = Field(None, description="一句话宏观概述")


# ---------------------------------------------------------------------------
# OHLCV
# ---------------------------------------------------------------------------

class OHLCVItem(BaseModel):
    """Single OHLCV candle."""
    timestamp: str
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: float
    volume: Optional[float] = None


class OHLCVResponse(BaseModel):
    """OHLCV price history."""
    coin: str
    interval: str = Field("1d", description="K线周期")
    items: List[OHLCVItem] = Field(default_factory=list)
    count: int


# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

class DetectedPattern(BaseModel):
    """A detected candlestick or chart pattern."""
    pattern: str
    type: str
    strength: Optional[str] = None
    desc: Optional[str] = None
    candle_offset: Optional[int] = None


class PatternResponse(BaseModel):
    """Pattern detection result."""
    coin: str
    patterns_count: int
    pattern_signal: Optional[str] = None
    pattern_score: Optional[float] = None
    summary: Optional[str] = None
    current_price: Optional[float] = None
    patterns: List[DetectedPattern] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# On-demand analysis
# ---------------------------------------------------------------------------

class AnalyzeCoinRequest(BaseModel):
    """Request to run on-demand analysis for a coin."""
    symbol: str = Field(..., min_length=1, max_length=10, description="币种代码")
    include_news: bool = Field(True, description="是否包含 AI 新闻分析")
    include_signals: bool = Field(True, description="是否包含信号计算")


class AnalyzeCoinResponse(BaseModel):
    """Result of on-demand coin analysis."""
    coin: str
    signal: Optional[CompositeSignalResponse] = None
    news_count: Optional[int] = None
    patterns: Optional[PatternResponse] = None
    analysis_time: Optional[str] = None
    status: str = Field("ok", description="ok / partial / error")
