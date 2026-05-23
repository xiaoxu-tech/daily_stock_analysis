# -*- coding: utf-8 -*-
"""Capital flow API schemas — northbound, sector flow, dragon-tiger."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Northbound (北向资金)
# ---------------------------------------------------------------------------

class NorthboundFlow(BaseModel):
    """Single northbound flow record."""
    date: str = Field(..., description="日期")
    net_inflow_cny: float = Field(0.0, description="净流入(亿元)")
    balance: Optional[float] = Field(None, description="额度余额")
    quota: Optional[float] = Field(None, description="额度上限")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "date": "2025-01-15",
            "net_inflow_cny": 35.62,
            "balance": 520.0,
            "quota": 520.0,
        }
    })


class NorthboundResponse(BaseModel):
    """Northbound flow summary."""
    items: List[NorthboundFlow] = Field(default_factory=list)
    total_inflow: float = Field(0.0, description="期间累计净流入")
    avg_daily: float = Field(0.0, description="日均净流入")
    trend: Optional[str] = Field(None, description="趋势: 持续流入/流出/震荡")
    days: int = 0


# ---------------------------------------------------------------------------
# Sector Flow (板块资金)
# ---------------------------------------------------------------------------

class SectorFlow(BaseModel):
    """Single sector capital flow record."""
    sector_name: Optional[str] = Field(None, description="板块名称")
    sector_code: Optional[str] = Field(None, description="板块代码")
    main_net_inflow: float = Field(0.0, description="主力净流入(亿元)")
    super_large_net: Optional[float] = Field(None, description="超大单净流入")
    large_net: Optional[float] = Field(None, description="大单净流入")
    medium_net: Optional[float] = Field(None, description="中单净流入")
    small_net: Optional[float] = Field(None, description="小单净流入")
    price_change_pct: Optional[float] = Field(None, description="板块涨跌幅(%)")


class SectorFlowResponse(BaseModel):
    """Sector capital flow summary."""
    items: List[SectorFlow] = Field(default_factory=list)
    positive_sectors: int = Field(0, description="主力净流入板块数")
    total_sectors: int = 0
    positive_ratio: float = Field(0.0, description="净流入板块占比")
    top_inflow: List[SectorFlow] = Field(default_factory=list, description="流入前5")
    top_outflow: List[SectorFlow] = Field(default_factory=list, description="流出前5")


# ---------------------------------------------------------------------------
# Dragon-Tiger (龙虎榜)
# ---------------------------------------------------------------------------

class DragonTigerStock(BaseModel):
    """Single dragon-tiger board stock."""
    stock_code: str = Field(..., description="股票代码")
    stock_name: Optional[str] = Field(None, description="股票名称")
    buy_amount_cny: Optional[float] = Field(None, description="买入金额(亿元)")
    sell_amount_cny: Optional[float] = Field(None, description="卖出金额(亿元)")
    net_amount_cny: Optional[float] = Field(None, description="净额(亿元)")
    reason: Optional[str] = Field(None, description="上榜原因")
    change_pct: Optional[float] = Field(None, description="涨跌幅(%)")
    turnover_rate: Optional[float] = Field(None, description="换手率(%)")
    date: Optional[str] = Field(None, description="日期")


class DragonTigerResponse(BaseModel):
    """Dragon-tiger board summary."""
    items: List[DragonTigerStock] = Field(default_factory=list)
    total_net: float = Field(0.0, description="龙虎榜总净额(亿元)")
    net_ratio: float = Field(0.0, description="净买入比")
    signal: Optional[str] = Field(None, description="信号: 游资活跃偏多/偏空/平衡")
    stocks_count: int = 0


# ---------------------------------------------------------------------------
# Capital Flow Snapshot (完整快照)
# ---------------------------------------------------------------------------

class CapitalFlowSnapshot(BaseModel):
    """Complete capital flow snapshot for a single day."""
    date: str = Field(..., description="快照日期")
    northbound: List[NorthboundFlow] = Field(default_factory=list)
    sector_flows: List[SectorFlow] = Field(default_factory=list)
    dragon_tiger: List[DragonTigerStock] = Field(default_factory=list)
    signal: Optional[Dict[str, Any]] = Field(None, description="合成信号")


class CapitalFlowHistoryResponse(BaseModel):
    """Paginated capital flow snapshots."""
    items: List[CapitalFlowSnapshot] = Field(default_factory=list)
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Capital Flow Signal
# ---------------------------------------------------------------------------

class CapitalFlowSignalComponent(BaseModel):
    """Single component score."""
    score: float
    signal: Optional[str] = None
    detail: Optional[Dict[str, Any]] = None


class CapitalFlowSignalResponse(BaseModel):
    """Computed capital flow sentiment signal."""
    asset_code: str = "A_SHARE"
    composite_score: float = Field(..., description="综合分数 [-1,+1]")
    signal_label: str = Field(..., description="bullish/neutral/bearish")
    components: Dict[str, CapitalFlowSignalComponent] = Field(default_factory=dict)
    weights: Dict[str, float] = Field(default_factory=dict)

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "asset_code": "A_SHARE",
            "composite_score": 0.35,
            "signal_label": "bullish",
            "components": {
                "northbound": {"score": 0.45, "signal": "北向持续流入"},
                "sector_breadth": {"score": 0.30, "signal": "资金分化"},
                "dragon_tiger": {"score": 0.20, "signal": "游资中性偏多"},
            },
            "weights": {"northbound": 0.40, "sector_breadth": 0.35, "dragon_tiger": 0.25},
        }
    })
