# -*- coding: utf-8 -*-
"""Capital flow API endpoints — northbound, sector flow, dragon-tiger, signal."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from api.v1.schemas.capital_flow import (
    CapitalFlowHistoryResponse,
    CapitalFlowSignalResponse,
    CapitalFlowSnapshot,
    DragonTigerResponse,
    DragonTigerStock,
    NorthboundFlow,
    NorthboundResponse,
    SectorFlow,
    SectorFlowResponse,
)
from api.v1.schemas.common import ErrorResponse
from src.storage import DatabaseManager

logger = logging.getLogger(__name__)

router = APIRouter()


def _bad_request(exc: Exception, *, error: str = "validation_error") -> HTTPException:
    return HTTPException(status_code=400, detail={"error": error, "message": str(exc)})


def _not_found(exc: Exception) -> HTTPException:
    return HTTPException(status_code=404, detail={"error": "not_found", "message": str(exc)})


def _internal_error(message: str, exc: Exception) -> HTTPException:
    logger.error("%s: %s", message, exc, exc_info=True)
    return HTTPException(status_code=500, detail={"error": "internal_error", "message": f"{message}: {str(exc)}"})


# -- Northbound ------------------------------------------------------------

@router.get(
    "/northbound",
    response_model=NorthboundResponse,
    responses={500: {"model": ErrorResponse}},
    summary="获取北向资金流向",
    description="返回近期北向资金（沪/深股通）每日净流入数据，含趋势分析。",
)
def get_northbound(
    days: int = Query(5, ge=1, le=30, description="回溯天数"),
):
    try:
        db = DatabaseManager()
        snapshots = db.get_capital_flow_snapshots(days=days)

        items = []
        total_inflow = 0.0

        for snap in (snapshots or []):
            import json
            try:
                payload = json.loads(snap.get("payload_json", "{}"))
            except (json.JSONDecodeError, TypeError):
                continue

            for nb in payload.get("northbound", []):
                try:
                    net = float(nb.get("net_inflow_cny", 0))
                    items.append(NorthboundFlow(
                        date=str(snap.get("snapshot_date", "")),
                        net_inflow_cny=net,
                        balance=nb.get("balance"),
                        quota=nb.get("quota"),
                    ))
                    total_inflow += net
                except (ValueError, TypeError):
                    continue

        items.sort(key=lambda x: x.date, reverse=True)
        avg_daily = total_inflow / len(items) if items else 0.0

        # Trend detection
        if total_inflow > 10:
            trend = "北向持续流入"
        elif total_inflow < -10:
            trend = "北向持续流出"
        else:
            trend = "北向震荡"

        return NorthboundResponse(
            items=items,
            total_inflow=round(total_inflow, 2),
            avg_daily=round(avg_daily, 2),
            trend=trend,
            days=len(items),
        )
    except Exception as exc:
        raise _internal_error("Failed to get northbound flow", exc)


# -- Sector Flow -----------------------------------------------------------

@router.get(
    "/sectors",
    response_model=SectorFlowResponse,
    responses={500: {"model": ErrorResponse}},
    summary="获取板块资金流向",
    description="返回近期各板块主力资金净流入数据，含流入流出排行。",
)
def get_sector_flows(
    days: int = Query(3, ge=1, le=14, description="回溯天数"),
):
    try:
        db = DatabaseManager()
        snapshots = db.get_capital_flow_snapshots(days=days)

        all_flows = []
        for snap in (snapshots or []):
            import json
            try:
                payload = json.loads(snap.get("payload_json", "{}"))
            except (json.JSONDecodeError, TypeError):
                continue

            for sf in payload.get("sector_flows", []):
                try:
                    main_net = float(sf.get("main_net_inflow", 0))
                    all_flows.append(SectorFlow(
                        sector_name=sf.get("sector_name"),
                        sector_code=sf.get("sector_code"),
                        main_net_inflow=main_net,
                        super_large_net=sf.get("super_large_net"),
                        large_net=sf.get("large_net"),
                        medium_net=sf.get("medium_net"),
                        small_net=sf.get("small_net"),
                        price_change_pct=sf.get("price_change_pct"),
                    ))
                except (ValueError, TypeError):
                    continue

        positive = sum(1 for f in all_flows if f.main_net_inflow > 0)
        ratio = positive / len(all_flows) if all_flows else 0.0

        # Top inflow / outflow (by main_net_inflow)
        sorted_by_inflow = sorted(all_flows, key=lambda x: x.main_net_inflow, reverse=True)
        top_inflow = sorted_by_inflow[:5]
        top_outflow = sorted_by_inflow[-5:] if len(sorted_by_inflow) >= 5 else []
        top_outflow = sorted(top_outflow, key=lambda x: x.main_net_inflow)

        return SectorFlowResponse(
            items=sorted_by_inflow,
            positive_sectors=positive,
            total_sectors=len(all_flows),
            positive_ratio=round(ratio, 3),
            top_inflow=top_inflow,
            top_outflow=top_outflow,
        )
    except Exception as exc:
        raise _internal_error("Failed to get sector flows", exc)


# -- Dragon-Tiger ----------------------------------------------------------

@router.get(
    "/dragon-tiger",
    response_model=DragonTigerResponse,
    responses={500: {"model": ErrorResponse}},
    summary="获取龙虎榜数据",
    description="返回近期龙虎榜股票数据，含游资活跃度信号。",
)
def get_dragon_tiger(
    days: int = Query(5, ge=1, le=14, description="回溯天数"),
):
    try:
        db = DatabaseManager()
        snapshots = db.get_capital_flow_snapshots(days=days)

        all_stocks = []
        for snap in (snapshots or []):
            import json
            try:
                payload = json.loads(snap.get("payload_json", "{}"))
            except (json.JSONDecodeError, TypeError):
                continue

            for dt in payload.get("dragon_tiger", []):
                try:
                    net = float(dt.get("net_amount_cny", 0))
                    buy = float(dt.get("buy_amount_cny", 0))
                    all_stocks.append(DragonTigerStock(
                        stock_code=dt.get("stock_code", ""),
                        stock_name=dt.get("stock_name"),
                        buy_amount_cny=buy,
                        sell_amount_cny=dt.get("sell_amount_cny"),
                        net_amount_cny=net,
                        reason=dt.get("reason"),
                        change_pct=dt.get("change_pct"),
                        turnover_rate=dt.get("turnover_rate"),
                        date=str(snap.get("snapshot_date", "")),
                    ))
                except (ValueError, TypeError):
                    continue

        total_net = sum(s.net_amount_cny or 0 for s in all_stocks)
        total_buy = sum(s.buy_amount_cny or 0 for s in all_stocks) or 1.0
        net_ratio = total_net / total_buy

        if net_ratio >= 0.3:
            signal = "游资活跃偏多"
        elif net_ratio >= 0.05:
            signal = "游资中性偏多"
        elif net_ratio >= -0.05:
            signal = "游资平衡"
        elif net_ratio >= -0.2:
            signal = "游资偏空"
        else:
            signal = "游资出货"

        return DragonTigerResponse(
            items=all_stocks,
            total_net=round(total_net, 2),
            net_ratio=round(net_ratio, 3),
            signal=signal,
            stocks_count=len(all_stocks),
        )
    except Exception as exc:
        raise _internal_error("Failed to get dragon-tiger data", exc)


# -- Snapshots -------------------------------------------------------------

@router.get(
    "/snapshot",
    response_model=CapitalFlowSnapshot,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="获取最新资金流向快照",
    description="返回最新一天的资金流向完整快照（北向+板块+龙虎榜）。",
)
def get_latest_snapshot():
    try:
        db = DatabaseManager()
        snapshots = db.get_capital_flow_snapshots(days=1)

        if not snapshots:
            raise _not_found(ValueError("No capital flow snapshot available"))

        import json
        snap = snapshots[0]
        try:
            payload = json.loads(snap.get("payload_json", "{}"))
        except (json.JSONDecodeError, TypeError):
            raise _not_found(ValueError("Invalid snapshot data"))

        nb_items = [
            NorthboundFlow(
                date=str(snap.get("snapshot_date", "")),
                net_inflow_cny=float(n.get("net_inflow_cny", 0)),
                balance=n.get("balance"),
                quota=n.get("quota"),
            )
            for n in payload.get("northbound", [])
        ]

        sf_items = [
            SectorFlow(
                sector_name=s.get("sector_name"),
                sector_code=s.get("sector_code"),
                main_net_inflow=float(s.get("main_net_inflow", 0)),
                price_change_pct=s.get("price_change_pct"),
            )
            for s in payload.get("sector_flows", [])
        ]

        dt_items = [
            DragonTigerStock(
                stock_code=d.get("stock_code", ""),
                stock_name=d.get("stock_name"),
                net_amount_cny=float(d.get("net_amount_cny", 0)),
            )
            for d in payload.get("dragon_tiger", [])
        ]

        return CapitalFlowSnapshot(
            date=str(snap.get("snapshot_date", "")),
            northbound=nb_items,
            sector_flows=sf_items,
            dragon_tiger=dt_items,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise _internal_error("Failed to get capital flow snapshot", exc)


@router.get(
    "/snapshots/history",
    response_model=CapitalFlowHistoryResponse,
    responses={500: {"model": ErrorResponse}},
    summary="获取历史资金流向快照",
    description="返回历史资金流向快照分页列表。",
)
def get_snapshot_history(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=50, description="每页数量"),
    days: int = Query(30, ge=1, le=365, description="回溯天数"),
):
    try:
        db = DatabaseManager()
        snapshots = db.get_capital_flow_snapshots(days=days)
        import json

        items = []
        for snap in (snapshots or []):
            try:
                payload = json.loads(snap.get("payload_json", "{}"))
            except (json.JSONDecodeError, TypeError):
                continue

            items.append(CapitalFlowSnapshot(
                date=str(snap.get("snapshot_date", "")),
                northbound=[
                    NorthboundFlow(
                        date=str(snap.get("snapshot_date", "")),
                        net_inflow_cny=float(n.get("net_inflow_cny", 0)),
                    )
                    for n in payload.get("northbound", [])
                ],
                sector_flows=[
                    SectorFlow(
                        sector_name=s.get("sector_name"),
                        main_net_inflow=float(s.get("main_net_inflow", 0)),
                    )
                    for s in payload.get("sector_flows", [])
                ],
                dragon_tiger=[
                    DragonTigerStock(
                        stock_code=d.get("stock_code", ""),
                        stock_name=d.get("stock_name"),
                        net_amount_cny=float(d.get("net_amount_cny", 0)),
                    )
                    for d in payload.get("dragon_tiger", [])
                ],
            ))

        total = len(items)
        start = (page - 1) * page_size
        page_items = items[start:start + page_size]

        return CapitalFlowHistoryResponse(
            items=page_items, total=total, page=page, page_size=page_size,
        )
    except Exception as exc:
        raise _internal_error("Failed to get snapshot history", exc)


# -- Signal ----------------------------------------------------------------

@router.get(
    "/signal",
    response_model=CapitalFlowSignalResponse,
    responses={500: {"model": ErrorResponse}},
    summary="获取资金流向综合信号",
    description="返回基于北向资金+板块资金+龙虎榜的综合市场情绪信号。",
)
def get_capital_flow_signal():
    try:
        from src.signals.capital_flow_signal import CapitalFlowSignal
        db = DatabaseManager()
        signal = CapitalFlowSignal(db_manager=db)
        result = signal.compute()

        from api.v1.schemas.capital_flow import CapitalFlowSignalComponent
        components = {
            key: CapitalFlowSignalComponent(
                score=val.get("score", 0.0),
                signal=val.get("signal"),
                detail={k: v for k, v in val.items() if k != "score"},
            )
            for key, val in result.components.items()
        }

        return CapitalFlowSignalResponse(
            asset_code=result.asset_code,
            composite_score=result.composite_score,
            signal_label=result.signal_label,
            components=components,
            weights=result.weights,
        )
    except Exception as exc:
        raise _internal_error("Failed to compute capital flow signal", exc)
