# -*- coding: utf-8 -*-
"""Capital flow signal: converts A-share capital flow data into trading signals.

Uses northbound net inflow trend, sector rotation heat, and dragon-tiger
activity to generate a composite sentiment signal (-1 to +1).
"""

from __future__ import annotations

import json
import logging
from typing import Optional, Dict, Any, List

import numpy as np

from src.signals.base import BaseSignal, SignalResult

logger = logging.getLogger(__name__)


class CapitalFlowSignal(BaseSignal):
    """Capital flow → sentiment signal for A-share market regime analysis.

    Fetches recent capital flow snapshots from DB and computes:
    - Northbound trend (weight 40%): short-term vs medium-term net inflow
    - Sector flow breadth (weight 35%): ratio of sectors with positive main inflow
    - Dragon-tiger activity (weight 25%): net buying ratio
    """

    def __init__(
        self,
        db_manager=None,
        lookback_days: int = 5,
        weights: Optional[Dict[str, float]] = None,
    ):
        self._db = db_manager
        self._lookback_days = lookback_days
        self.weights = weights or {
            "northbound": 0.40,
            "sector_breadth": 0.35,
            "dragon_tiger": 0.25,
        }

    @property
    def name(self) -> str:
        return "capital_flow"

    def compute(self, asset_code: str = "A_SHARE", **kwargs) -> SignalResult:
        """Compute capital flow signal.

        Args:
            asset_code: Ignored (capital flow is market-wide, not per-stock).

        Returns:
            SignalResult with composite score and component breakdowns.
        """
        components: Dict[str, Any] = {}
        total_score = 0.0

        # Fetch recent snapshots
        snapshots = self._fetch_recent_snapshots()
        if not snapshots:
            return SignalResult(
                asset_code=asset_code or "A_SHARE",
                asset_type="stock",
                composite_score=0.0,
                signal_label="neutral",
                components={"northbound": {"score": 0.0, "signal": "no_data"}},
                weights=self.weights,
            )

        # 1. Northbound trend (40%)
        nb_score, nb_detail = self._compute_northbound_signal(snapshots)
        if nb_detail.get("signal") != "no_data":
            total_score += self.weights["northbound"] * nb_score
        components["northbound"] = {"score": round(nb_score, 3), **nb_detail}

        # 2. Sector flow breadth (35%)
        sf_score, sf_detail = self._compute_sector_breadth(snapshots)
        if sf_detail.get("signal") != "no_data":
            total_score += self.weights["sector_breadth"] * sf_score
        components["sector_breadth"] = {"score": round(sf_score, 3), **sf_detail}

        # 3. Dragon-tiger activity (25%)
        dt_score, dt_detail = self._compute_dragon_tiger_activity(snapshots)
        if dt_detail.get("signal") != "no_data":
            total_score += self.weights["dragon_tiger"] * dt_score
        components["dragon_tiger"] = {"score": round(dt_score, 3), **dt_detail}

        # Classify
        composite = round(total_score, 3)
        if composite >= 0.3:
            label = "bullish"
        elif composite <= -0.3:
            label = "bearish"
        else:
            label = "neutral"

        return SignalResult(
            asset_code="A_SHARE",
            asset_type="stock",
            composite_score=composite,
            signal_label=label,
            components=components,
            weights=self.weights,
        )

    # ------------------------------------------------------------------
    # Internal computation methods
    # ------------------------------------------------------------------

    def _fetch_recent_snapshots(self) -> List[Dict[str, Any]]:
        """Fetch recent capital flow snapshots from DB."""
        if not self._db:
            return []

        try:
            rows = self._db.get_capital_flow_snapshots(days=self._lookback_days)
            result = []
            for row in rows:
                try:
                    payload = json.loads(row.get("payload_json", "{}"))
                    payload["_date"] = str(row.get("snapshot_date", ""))
                    result.append(payload)
                except (json.JSONDecodeError, TypeError):
                    continue
            return result
        except Exception as e:
            logger.warning("Failed to fetch capital flow snapshots: %s", e)
            return []

    def _compute_northbound_signal(self, snapshots: List[dict]) -> tuple:
        """Northbound net inflow trend analysis."""
        all_flows = []
        for snap in snapshots:
            for nb in snap.get("northbound", []):
                try:
                    all_flows.append(float(nb.get("net_inflow_cny", 0)))
                except (ValueError, TypeError):
                    continue

        if not all_flows:
            return 0.0, {"signal": "no_data", "total_inflow": 0.0, "days": 0}

        total = sum(all_flows)
        avg_daily = total / len(all_flows)
        recent = all_flows[:max(2, len(all_flows) // 2)]  # more recent half
        avg_recent = sum(recent) / len(recent) if recent else 0

        # Trend: compare recent vs overall
        trend = avg_recent - avg_daily

        score = np.tanh(total * 0.3 + trend * 2.0)

        if score >= 0.3:
            label = "北向持续流入"
        elif score <= -0.3:
            label = "北向持续流出"
        else:
            label = "北向震荡"

        return float(score), {
            "signal": label,
            "total_inflow": round(total, 2),
            "avg_daily": round(avg_daily, 2),
            "days": len(all_flows),
        }

    def _compute_sector_breadth(self, snapshots: List[dict]) -> tuple:
        """Ratio of sectors with positive main net inflow (breadth indicator)."""
        all_flows = []
        for snap in snapshots:
            for sf in snap.get("sector_flows", []):
                try:
                    all_flows.append(float(sf.get("main_net_inflow", 0)))
                except (ValueError, TypeError):
                    continue

        if not all_flows:
            return 0.0, {"signal": "no_data", "positive_ratio": 0.0, "sectors": 0}

        positive = sum(1 for f in all_flows if f > 0)
        ratio = positive / len(all_flows)

        # Map ratio to signal: >60% positive = bullish, <30% = bearish
        if ratio >= 0.6:
            signal, label = min(1.0, ratio * 1.5), "资金普入"
        elif ratio >= 0.4:
            signal, label = 0.0, "资金分化"
        elif ratio >= 0.2:
            signal, label = -0.3, "资金偏出"
        else:
            signal, label = max(-1.0, -ratio * 1.5), "资金流出"

        return round(signal, 3), {
            "signal": label,
            "positive_ratio": round(ratio, 3),
            "sectors": len(all_flows),
        }

    def _compute_dragon_tiger_activity(self, snapshots: List[dict]) -> tuple:
        """Dragon-tiger board: net buying vs selling ratio."""
        all_stocks = []
        for snap in snapshots:
            for dt in snap.get("dragon_tiger", []):
                try:
                    net = float(dt.get("net_amount_cny", 0))
                    buy = float(dt.get("buy_amount_cny", 0))
                    all_stocks.append({"net": net, "buy": buy})
                except (ValueError, TypeError):
                    continue

        if not all_stocks:
            return 0.0, {"signal": "no_data", "stocks": 0}

        total_net = sum(s["net"] for s in all_stocks)
        total_buy = sum(s["buy"] for s in all_stocks) or 1.0
        net_ratio = total_net / total_buy

        # Net buying ratio → signal
        if net_ratio >= 0.3:
            signal, label = 0.5, "游资活跃偏多"
        elif net_ratio >= 0.05:
            signal, label = 0.2, "游资中性偏多"
        elif net_ratio >= -0.05:
            signal, label = 0.0, "游资平衡"
        elif net_ratio >= -0.2:
            signal, label = -0.3, "游资偏空"
        else:
            signal, label = -0.6, "游资出货"

        return round(signal, 3), {
            "signal": label,
            "net_ratio": round(net_ratio, 3),
            "total_net_billion": round(total_net, 2),
            "stocks": len(all_stocks),
        }
