# -*- coding: utf-8 -*-
"""Capital flow data ingestion pipeline.

Fetches EastMoney capital flow data and stores it as a daily snapshot
for downstream AI context injection and historical analysis.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from typing import Optional, Dict, Any

from src.scrapers.capital_flow import EastMoneyCapitalFlowFetcher, CapitalFlowSnapshot

logger = logging.getLogger(__name__)


class CapitalFlowIngestor:
    """Fetch capital flow data and persist as a daily snapshot."""

    def __init__(
        self,
        db_manager=None,
        northbound_days: int = 5,
        sector_top_n: int = 20,
        dragon_top_n: int = 20,
        timeout: int = 15,
    ):
        self._db = db_manager
        self._northbound_days = northbound_days
        self._sector_top_n = sector_top_n
        self._dragon_top_n = dragon_top_n
        self._timeout = timeout

    def fetch(self) -> CapitalFlowSnapshot:
        """Fetch all capital flow data from EastMoney."""
        fetcher = EastMoneyCapitalFlowFetcher(
            northbound_days=self._northbound_days,
            sector_top_n=self._sector_top_n,
            dragon_top_n=self._dragon_top_n,
            timeout=self._timeout,
        )
        try:
            return fetcher.fetch_all()
        finally:
            fetcher.close()

    def store(self, snapshot: CapitalFlowSnapshot) -> bool:
        """Persist the snapshot to DB."""
        if not self._db or not snapshot.has_data:
            return False

        try:
            payload = json.dumps({
                "northbound": [
                    {
                        "date": nb.date,
                        "net_inflow_cny": nb.net_inflow_cny,
                        "sh_inflow_cny": nb.sh_inflow_cny,
                        "sz_inflow_cny": nb.sz_inflow_cny,
                    }
                    for nb in snapshot.northbound_history
                ],
                "sector_flows": [
                    {
                        "sector_name": sf.sector_name,
                        "sector_code": sf.sector_code,
                        "main_net_inflow": sf.main_net_inflow,
                        "main_ratio_pct": sf.main_ratio_pct,
                        "change_pct": sf.change_pct,
                        "lead_stock": sf.lead_stock,
                    }
                    for sf in snapshot.sector_flows
                ],
                "concept_flows": [
                    {
                        "sector_name": cf.sector_name,
                        "sector_code": cf.sector_code,
                        "main_net_inflow": cf.main_net_inflow,
                        "main_ratio_pct": cf.main_ratio_pct,
                        "change_pct": cf.change_pct,
                        "lead_stock": cf.lead_stock,
                    }
                    for cf in snapshot.concept_flows
                ],
                "dragon_tiger": [
                    {
                        "stock_code": dt.stock_code,
                        "stock_name": dt.stock_name,
                        "change_pct": dt.change_pct,
                        "net_amount_cny": dt.net_amount_cny,
                        "turnover_rate": dt.turnover_rate,
                        "reason": dt.reason,
                    }
                    for dt in snapshot.dragon_tiger
                ],
            }, ensure_ascii=False)

            self._db.save_capital_flow_snapshot(
                snapshot_date=date.today().isoformat(),
                payload_json=payload,
            )
            logger.info("Capital flow snapshot stored for %s", date.today().isoformat())
            return True
        except Exception as e:
            logger.error("Failed to store capital flow snapshot: %s", e)
            return False

    def run(self) -> Dict[str, Any]:
        """Run the full capital flow ingestion pipeline.

        Returns:
            Dict with fetch summary info.
        """
        logger.info("=== Capital flow ingestion ===")
        snapshot = self.fetch()
        stored = self.store(snapshot)

        return {
            "northbound_count": len(snapshot.northbound_history),
            "sector_count": len(snapshot.sector_flows),
            "concept_count": len(snapshot.concept_flows),
            "dragon_tiger_count": len(snapshot.dragon_tiger),
            "stored": stored,
            "domain": "capital_flow",
        }
