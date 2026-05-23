# -*- coding: utf-8 -*-
"""EastMoney capital flow data fetcher.

Fetches 3 types of A-share capital flow data:
1. Northbound (沪深港通) daily net inflow
2. Sector flow (行业/概念板块) ranked by main net inflow
3. Dragon-tiger board (龙虎榜) daily top stocks

All data comes from EastMoney public APIs (no auth required).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import logging
from typing import Optional, List, Dict, Any

import httpx

logger = logging.getLogger(__name__)

# EastMoney public API tokens (fixed, not secrets)
UT_DELAY = "bd1d9ddb04089700cf9c27f6f7426281"
UT_HISTORY = "7eea3edcaed734bea9c9cba30746e32d"

_YUAN_TO_YI = 100_000_000  # 元 → 亿元


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class NorthboundFlow:
    """Single-day northbound capital flow (沪深港通)."""
    date: str                 # "2026-05-21"
    net_inflow_cny: float     # total net inflow (亿 CNY)
    sh_inflow_cny: float      # Shanghai Connect (亿 CNY)
    sz_inflow_cny: float      # Shenzhen Connect (亿 CNY)


@dataclass
class SectorFlow:
    """Sector-level capital flow (industry or concept)."""
    sector_name: str
    sector_code: str
    main_net_inflow: float     # 主力净流入 (亿)
    super_large_inflow: float  # 超大单 (亿)
    large_inflow: float        # 大单 (亿)
    medium_inflow: float       # 中单 (亿)
    small_inflow: float        # 小单 (亿)
    main_ratio_pct: float      # 主力净流入占比 (%)
    change_pct: float          # 涨跌幅 (%)
    lead_stock: str            # 领涨股


@dataclass
class DragonTigerStock:
    """Dragon-tiger board individual stock (龙虎榜)."""
    stock_code: str
    stock_name: str
    change_pct: float           # 涨跌幅 (%)
    net_amount_cny: float       # 净买入 (亿)
    buy_amount_cny: float       # 买入额 (亿)
    sell_amount_cny: float      # 卖出额 (亿)
    turnover_rate: float        # 换手率 (%)
    reason: str                 # 上榜原因


@dataclass
class CapitalFlowSnapshot:
    """Aggregate capital flow snapshot for a single fetch session."""
    fetched_at: str = field(default_factory=lambda: datetime.now().isoformat())
    northbound_history: List[NorthboundFlow] = field(default_factory=list)
    sector_flows: List[SectorFlow] = field(default_factory=list)       # industry
    concept_flows: List[SectorFlow] = field(default_factory=list)      # concept
    dragon_tiger: List[DragonTigerStock] = field(default_factory=list)

    @property
    def has_data(self) -> bool:
        return bool(self.northbound_history or self.sector_flows
                    or self.concept_flows or self.dragon_tiger)

    def summary_text(self, nb_top: int = 5, sector_top: int = 10,
                     dragon_top: int = 10) -> str:
        """Generate a Markdown context string for AI prompt injection."""
        lines = ["## 今日资金流向数据（辅助分析上下文）\n"]

        if self.northbound_history:
            lines.append("### 北向资金（近{}日）\n".format(min(nb_top, len(self.northbound_history))))
            lines.append("| 日期 | 净流入(亿) | 沪股通(亿) | 深股通(亿) |")
            lines.append("|------|-----------|-----------|-----------|")
            for nb in self.northbound_history[:nb_top]:
                lines.append(f"| {nb.date} | {nb.net_inflow_cny:+.2f} | "
                            f"{nb.sh_inflow_cny:+.2f} | {nb.sz_inflow_cny:+.2f} |")
            lines.append("")

        if self.sector_flows:
            lines.append("### 行业板块资金流向（Top {}）\n".format(min(sector_top, len(self.sector_flows))))
            lines.append("| 板块 | 主力净流入(亿) | 涨跌幅 | 领涨股 |")
            lines.append("|------|-------------|--------|--------|")
            for sf in self.sector_flows[:sector_top]:
                lines.append(f"| {sf.sector_name} | {sf.main_net_inflow:+.2f} | "
                            f"{sf.change_pct:+.2f}% | {sf.lead_stock} |")
            lines.append("")

        if self.dragon_tiger:
            lines.append("### 龙虎榜（Top {}）\n".format(min(dragon_top, len(self.dragon_tiger))))
            lines.append("| 股票 | 涨跌幅 | 净买入(亿) | 上榜原因 |")
            lines.append("|------|--------|----------|----------|")
            for dt in self.dragon_tiger[:dragon_top]:
                reason_short = dt.reason[:30] + "..." if len(dt.reason) > 30 else dt.reason
                lines.append(f"| {dt.stock_name}({dt.stock_code}) | "
                            f"{dt.change_pct:+.2f}% | {dt.net_amount_cny:+.2f} | {reason_short} |")
            lines.append("")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Fetcher
# ---------------------------------------------------------------------------

class EastMoneyCapitalFlowFetcher:
    """东方财富资金流向数据获取器."""

    def __init__(
        self,
        client: Optional[httpx.Client] = None,
        timeout: int = 15,
        northbound_days: int = 5,
        sector_top_n: int = 20,
        dragon_top_n: int = 20,
    ):
        self._client = client or httpx.Client(
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Referer": "https://data.eastmoney.com/",
            },
            timeout=httpx.Timeout(timeout),
        )
        self._northbound_days = northbound_days
        self._sector_top_n = sector_top_n
        self._dragon_top_n = dragon_top_n

    def close(self):
        self._client.close()

    # ── Northbound ──

    def fetch_northbound(self, days: int = 5) -> List[NorthboundFlow]:
        url = "https://push2his.eastmoney.com/api/qt/kamt.kline/get"
        params = {
            "fields1": "f1,f2,f3,f4",
            "fields2": "f51,f52,f53,f54,f55,f56",
            "klt": "1",
            "lmt": str(days + 3),
            "ut": UT_HISTORY,
        }
        resp = self._client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

        sh_lines = self._parse_kline(data, "hk2sh")
        sz_lines = self._parse_kline(data, "hk2sz")

        flows: List[NorthboundFlow] = []
        all_dates = sorted(set(sh_lines.keys()) | set(sz_lines.keys()), reverse=True)
        for date in all_dates[:days]:
            sh = sh_lines.get(date, 0.0)
            sz = sz_lines.get(date, 0.0)
            flows.append(NorthboundFlow(
                date=date,
                net_inflow_cny=round(sh + sz, 4),
                sh_inflow_cny=round(sh, 4),
                sz_inflow_cny=round(sz, 4),
            ))
        return flows

    @staticmethod
    def _parse_kline(resp_data: dict, key: str) -> Dict[str, float]:
        result: Dict[str, float] = {}
        lines = (resp_data.get("data") or {}).get(key) or []
        if not lines or not isinstance(lines, list):
            return result
        for line in lines:
            parts = str(line).split(",")
            if len(parts) < 2:
                continue
            date = parts[0]
            try:
                net = float(parts[1]) / _YUAN_TO_YI
            except (ValueError, IndexError):
                net = 0.0
            result[date] = net
        return result

    # ── Sector Flow ──

    def fetch_sector_flow(self, top_n: int = 20,
                          sector_type: str = "industry") -> List[SectorFlow]:
        fs_code = "m:90+t:3" if sector_type == "industry" else "m:90+t:2"

        url = "https://push2delay.eastmoney.com/api/qt/clist/get"
        params = {
            "pn": "1", "pz": str(min(top_n, 50)),
            "po": "0", "np": "1", "ut": UT_DELAY,
            "fltt": "2", "invt": "2", "fid": "f62", "fs": fs_code,
            "fields": "f2,f3,f4,f12,f14,f62,f184,f66,f69,f72,f75,f78,f81,f84,f87",
        }
        resp = self._client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

        flows: List[SectorFlow] = []
        diff_list = (data.get("data") or {}).get("diff") or []
        for item in diff_list:
            flows.append(SectorFlow(
                sector_name=str(item.get("f14", "")),
                sector_code=str(item.get("f12", "")),
                main_net_inflow=round(_to_yi(item.get("f62")), 4),
                super_large_inflow=round(_to_yi(item.get("f66")), 4),
                large_inflow=round(_to_yi(item.get("f72")), 4),
                medium_inflow=round(_to_yi(item.get("f78")), 4),
                small_inflow=round(_to_yi(item.get("f84")), 4),
                main_ratio_pct=_to_float(item.get("f184")),
                change_pct=_to_float(item.get("f3")),
                lead_stock=str(item.get("f128", "") or ""),
            ))
        return flows[:top_n]

    # ── Dragon Tiger ──

    def fetch_dragon_tiger(self, top_n: int = 20) -> List[DragonTigerStock]:
        url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
        params = {
            "reportName": "RPT_DAILYBILLBOARD_DETAILSNEW",
            "columns": "ALL",
            "sortColumns": "TRADE_DATE",
            "sortTypes": "-1",
            "pageSize": str(top_n),
            "pageNumber": "1",
            "source": "WEB",
            "client": "WEB",
        }
        resp = self._client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

        if not data.get("success"):
            logger.warning("[龙虎榜] API returned failure: %s", data.get("message", ""))
            return []

        stocks: List[DragonTigerStock] = []
        rows = (data.get("result") or {}).get("data") or []
        for item in rows:
            stocks.append(DragonTigerStock(
                stock_code=str(item.get("SECURITY_CODE", "")),
                stock_name=str(item.get("SECURITY_NAME_ABBR", "")),
                change_pct=_to_float(item.get("CHANGE_RATE")),
                net_amount_cny=round(_to_yi(item.get("BILLBOARD_NET_AMT")), 4),
                buy_amount_cny=round(_to_yi(item.get("BILLBOARD_BUY_AMT")), 4),
                sell_amount_cny=round(_to_yi(item.get("BILLBOARD_SELL_AMT")), 4),
                turnover_rate=_to_float(item.get("TURNOVERRATE")),
                reason=str(item.get("EXPLANATION", "")),
            ))
        return stocks

    # ── Aggregate ──

    def fetch_all(self) -> CapitalFlowSnapshot:
        """Fetch all capital flow data in one call, with independent error handling."""
        snapshot = CapitalFlowSnapshot()

        try:
            snapshot.northbound_history = self.fetch_northbound(self._northbound_days)
        except Exception as e:
            logger.error("北向资金获取失败: %s", e)

        try:
            snapshot.sector_flows = self.fetch_sector_flow(self._sector_top_n, "industry")
        except Exception as e:
            logger.error("行业板块资金获取失败: %s", e)

        try:
            snapshot.concept_flows = self.fetch_sector_flow(self._sector_top_n, "concept")
        except Exception as e:
            logger.error("概念板块资金获取失败: %s", e)

        try:
            snapshot.dragon_tiger = self.fetch_dragon_tiger(self._dragon_top_n)
        except Exception as e:
            logger.error("龙虎榜获取失败: %s", e)

        return snapshot


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_yi(val) -> float:
    """Convert raw yuan to 亿 CNY."""
    if val is None:
        return 0.0
    try:
        return float(val) / _YUAN_TO_YI
    except (ValueError, TypeError):
        return 0.0


def _to_float(val) -> float:
    if val is None:
        return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0
