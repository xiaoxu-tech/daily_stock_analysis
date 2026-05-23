# -*- coding: utf-8 -*-
"""On-chain data client for crypto blockchain metrics.

Fetches network/blockchain metrics and converts to trading signals (-1 to +1).
Data sources (all FREE): Blockchain.com, CoinMetrics Community API, DeFiLlama.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import httpx
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

BLOCKCHAIN_STATS_URL = "https://api.blockchain.info/stats"
BLOCKCHAIN_CHARTS_URL = "https://api.blockchain.info/charts"
DEFILLAMA_TVL_URL = "https://api.llama.fi/v2/chains"
DEFILLAMA_STABLECOINS_URL = "https://stablecoins.llama.fi/stablecoins"
COINMETRICS_BASE = "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"


class OnchainClient:
    """Fetch on-chain metrics and generate composite on-chain regime signal."""

    def __init__(self, timeout: int = 30):
        self._session = httpx.Client(
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Accept": "application/json",
            },
            timeout=timeout,
        )

    def close(self):
        self._session.close()

    # ── Blockchain.com ──

    def _fetch_blockchain_chart(self, chart_name: str,
                                timespan: str = "6months") -> Optional[pd.Series]:
        try:
            url = f"{BLOCKCHAIN_CHARTS_URL}/{chart_name}"
            r = self._session.get(url, params={"timespan": timespan, "format": "json"})
            if r.status_code != 200:
                logger.warning("Blockchain chart %s returned %s", chart_name, r.status_code)
                return None
            data = r.json()
            values = data.get("values", [])
            if not values:
                return None
            dates, vals = [], []
            for point in values:
                try:
                    dates.append(pd.to_datetime(point["x"], unit="s"))
                    vals.append(float(point["y"]))
                except (KeyError, ValueError, TypeError):
                    continue
            if not dates:
                return None
            return pd.Series(vals, index=pd.DatetimeIndex(dates), name=chart_name).sort_index()
        except Exception as e:
            logger.error("Blockchain chart %s error: %s", chart_name, e)
            return None

    def get_hashrate_signal(self) -> dict:
        s = self._fetch_blockchain_chart("hash-rate", "6months")
        if s is None or len(s) < 7:
            return {"score": 0.0, "label": "no_data", "latest_value": None}
        latest = s.iloc[-1]
        sma30 = s.iloc[-30:].mean() if len(s) >= 30 else s.mean()
        trend_pct = (latest / sma30 - 1) * 100
        score = round(float(np.tanh(trend_pct * 0.5)), 3)
        latest_disp = latest / 1e6
        if trend_pct > 5:
            label = f"算力快速增长 {latest_disp:.0f}M (利好)"
        elif trend_pct > 1:
            label = f"算力温和增长 {latest_disp:.0f}M"
        elif trend_pct > -1:
            label = f"算力稳定 {latest_disp:.0f}M"
        elif trend_pct > -5:
            label = f"算力下降 {latest_disp:.0f}M (偏空)"
        else:
            label = f"算力显著下降 {latest_disp:.0f}M (利空)"
        return {"score": score, "label": label, "latest_value": round(latest_disp, 0)}

    def get_transaction_signal(self) -> dict:
        s = self._fetch_blockchain_chart("n-transactions", "6months")
        if s is None or len(s) < 7:
            return {"score": 0.0, "label": "no_data", "latest_value": None}
        latest = s.iloc[-1]
        sma30 = s.iloc[-30:].mean() if len(s) >= 30 else s.mean()
        trend_pct = (latest / sma30 - 1) * 100
        score = round(float(np.tanh(trend_pct * 0.3)), 3)
        latest_k = latest / 1000
        if trend_pct > 10:
            label = f"日交易笔数激增 {latest_k:.0f}k (利好)"
        elif trend_pct > 3:
            label = f"日交易笔数增长 {latest_k:.0f}k"
        elif trend_pct > -3:
            label = f"日交易笔数稳定 {latest_k:.0f}k"
        elif trend_pct > -10:
            label = f"日交易笔数下降 {latest_k:.0f}k (偏空)"
        else:
            label = f"日交易笔数锐减 {latest_k:.0f}k (利空)"
        return {"score": score, "label": label, "latest_value": round(latest_k, 0)}

    def get_fees_signal(self) -> dict:
        s = self._fetch_blockchain_chart("transaction-fees-usd", "3months")
        if s is None or len(s) < 7:
            return {"score": 0.0, "label": "no_data", "latest_value": None}
        latest = s.iloc[-1]
        sma30 = s.iloc[-30:].mean() if len(s) >= 30 else s.mean()
        ratio = latest / sma30 if sma30 > 0 else 1.0
        latest_k = latest / 1000
        if ratio < 0.5:
            score, label = -0.3, f"手续费极低 ${latest_k:.0f}k (低需求)"
        elif ratio < 0.8:
            score, label = 0.1, f"手续费偏低 ${latest_k:.0f}k"
        elif ratio < 1.5:
            score, label = 0.4, f"手续费适中 ${latest_k:.0f}k (活跃)"
        elif ratio < 3.0:
            score, label = 0.1, f"手续费偏高 ${latest_k:.0f}k (拥挤)"
        else:
            score, label = -0.4, f"手续费极高 ${latest_k:.0f}k (拥堵)"
        return {"score": score, "label": label, "latest_value": round(latest_k, 0)}

    # ── CoinMetrics ──

    def _fetch_coinmetrics(self, asset: str, metrics: list,
                           days: int = 90) -> Optional[pd.DataFrame]:
        try:
            end = datetime.utcnow()
            start = end - timedelta(days=days)
            params = {
                "assets": asset, "metrics": ",".join(metrics),
                "frequency": "1d",
                "start_time": start.strftime("%Y-%m-%dT00:00:00Z"),
                "end_time": end.strftime("%Y-%m-%dT23:59:59Z"),
                "page_size": days + 10, "api_key": "free",
            }
            r = self._session.get(COINMETRICS_BASE, params=params)
            if r.status_code != 200:
                logger.warning("CoinMetrics returned %s", r.status_code)
                return None
            rows = r.json().get("data", [])
            if not rows:
                return None
            records = []
            for row in rows:
                ts = row.get("time")
                if not ts:
                    continue
                entry = {"timestamp": pd.to_datetime(ts)}
                for k, v in row.items():
                    if k in ("time", "asset"):
                        continue
                    try:
                        entry[k] = float(v)
                    except (ValueError, TypeError):
                        entry[k] = np.nan
                records.append(entry)
            if not records:
                return None
            return pd.DataFrame(records).set_index("timestamp").sort_index()
        except Exception as e:
            logger.error("CoinMetrics error for %s: %s", asset, e)
            return None

    def get_exchange_flow_signal(self, asset: str = "btc") -> dict:
        df = self._fetch_coinmetrics(asset, ["FlowInExNtv", "FlowOutExNtv"])
        if df is None or len(df) < 7:
            return {"score": 0.0, "label": "no_data", "latest_value": None}
        if "FlowInExNtv" not in df.columns or "FlowOutExNtv" not in df.columns:
            return {"score": 0.0, "label": "no_data", "latest_value": None}
        df["net_flow"] = df["FlowOutExNtv"].fillna(0) - df["FlowInExNtv"].fillna(0)
        df["net_flow_7d"] = df["net_flow"].rolling(7, min_periods=3).sum()
        latest_net = df["net_flow_7d"].iloc[-1]
        if pd.isna(latest_net) or latest_net == 0:
            return {"score": 0.0, "label": "no_data", "latest_value": None}
        hist_std = df["net_flow_7d"].std()
        z_score = latest_net / hist_std if (pd.notna(hist_std) and hist_std != 0) else 0.0
        score = round(float(np.tanh(z_score * 0.5)), 3)
        if score >= 0.4:
            label = "大幅流出交易所 (囤积, 利好)"
        elif score >= 0.15:
            label = "小幅流出交易所 (偏多)"
        elif score >= -0.15:
            label = "交易所流量平衡"
        elif score >= -0.4:
            label = "小幅流入交易所 (偏空)"
        else:
            label = "大幅流入交易所 (派发, 利空)"
        return {"score": score, "label": label, "latest_value": round(latest_net, 0)}

    def get_active_addresses_signal(self, asset: str = "btc") -> dict:
        df = self._fetch_coinmetrics(asset, ["AdrActCnt"])
        if df is None or len(df) < 7:
            return {"score": 0.0, "label": "no_data", "latest_value": None}
        if "AdrActCnt" not in df.columns:
            return {"score": 0.0, "label": "no_data", "latest_value": None}
        series = df["AdrActCnt"].dropna()
        if len(series) < 7:
            return {"score": 0.0, "label": "no_data", "latest_value": None}
        latest = series.iloc[-1]
        sma30 = series.iloc[-30:].mean() if len(series) >= 30 else series.mean()
        trend_pct = (latest / sma30 - 1) * 100
        score = round(float(np.tanh(trend_pct * 0.3)), 3)
        latest_k = latest / 1000
        if trend_pct > 15:
            label = f"活跃地址激增 {latest_k:.0f}k (利好)"
        elif trend_pct > 5:
            label = f"活跃地址增长 {latest_k:.0f}k"
        elif trend_pct > -5:
            label = f"活跃地址稳定 {latest_k:.0f}k"
        elif trend_pct > -15:
            label = f"活跃地址下降 {latest_k:.0f}k (偏空)"
        else:
            label = f"活跃地址锐减 {latest_k:.0f}k (利空)"
        return {"score": score, "label": label, "latest_value": round(latest_k, 0)}

    # ── DeFiLlama ──

    def _fetch_defillama_historical(self) -> Optional[pd.Series]:
        try:
            r = self._session.get("https://api.llama.fi/charts")
            if r.status_code != 200:
                return None
            data = r.json()
            if not data or not isinstance(data, list):
                return None
            dates, values = [], []
            for point in data:
                try:
                    dates.append(pd.to_datetime(int(point["date"]), unit="s"))
                    values.append(float(point["totalLiquidityUSD"]))
                except (KeyError, ValueError, TypeError):
                    continue
            if not dates:
                return None
            return pd.Series(values, index=pd.DatetimeIndex(dates), name="tvl").sort_index()
        except Exception as e:
            logger.error("DeFiLlama historical TVL error: %s", e)
            return None

    def get_tvl_signal(self) -> dict:
        s = self._fetch_defillama_historical()
        if s is None or len(s) < 7:
            return {"score": 0.0, "label": "no_data", "latest_value": None}
        latest = s.iloc[-1]
        sma30 = s.iloc[-30:].mean() if len(s) >= 30 else s.mean()
        trend_pct = (latest / sma30 - 1) * 100
        score = round(float(np.tanh(trend_pct * 0.2)), 3)
        latest_b = latest / 1e9
        if trend_pct > 10:
            label = f"TVL 快速增长 ${latest_b:.1f}B (利好)"
        elif trend_pct > 3:
            label = f"TVL 温和增长 ${latest_b:.1f}B"
        elif trend_pct > -3:
            label = f"TVL 稳定 ${latest_b:.1f}B"
        elif trend_pct > -10:
            label = f"TVL 下降 ${latest_b:.1f}B (偏空)"
        else:
            label = f"TVL 大幅下降 ${latest_b:.1f}B (利空)"
        return {"score": score, "label": label, "latest_value": round(latest_b, 1)}

    def get_stablecoin_signal(self) -> dict:
        try:
            r = self._session.get(f"{DEFILLAMA_STABLECOINS_URL}?includePrices=false")
            if r.status_code != 200:
                return {"score": 0.0, "label": "no_data", "latest_value": None}
            data = r.json()
            pegged = data.get("peggedAssets", [])
            if not pegged:
                return {"score": 0.0, "label": "no_data", "latest_value": None}
            total = sum(
                a.get("circulating", {}).get("peggedUSD", 0) or 0
                for a in pegged
            )
            total_b = total / 1e9
            if total_b > 200:
                score, label = 0.7, f"稳定币充裕 ${total_b:.0f}B (利好)"
            elif total_b > 150:
                score, label = 0.4, f"稳定币充足 ${total_b:.0f}B"
            elif total_b > 100:
                score, label = 0.1, f"稳定币适中 ${total_b:.0f}B"
            elif total_b > 50:
                score, label = -0.2, f"稳定币偏低 ${total_b:.0f}B (偏空)"
            else:
                score, label = -0.5, f"稳定币不足 ${total_b:.0f}B (利空)"
            return {"score": score, "label": label, "latest_value": round(total_b, 0)}
        except Exception as e:
            logger.error("DeFiLlama stablecoins error: %s", e)
            return {"score": 0.0, "label": "no_data", "latest_value": None}

    # ── Composite ──

    def get_all_signals(self, asset: str = "btc") -> Dict[str, Any]:
        results: Dict[str, Any] = {}
        results["exchange_flow"] = self.get_exchange_flow_signal(asset)
        results["active_addresses"] = self.get_active_addresses_signal(asset)
        results["hashrate"] = self.get_hashrate_signal()
        results["transactions"] = self.get_transaction_signal()
        results["fees"] = self.get_fees_signal()
        results["tvl"] = self.get_tvl_signal()
        results["stablecoins"] = self.get_stablecoin_signal()

        weights = {
            "exchange_flow": 0.22, "active_addresses": 0.18,
            "hashrate": 0.15, "transactions": 0.12, "fees": 0.05,
            "tvl": 0.15, "stablecoins": 0.13,
        }

        total_w, composite = 0.0, 0.0
        for key, w in weights.items():
            if key in results and results[key].get("label") != "no_data":
                composite += results[key]["score"] * w
                total_w += w

        composite = round(composite / total_w, 3) if total_w > 0 else 0.0

        if composite >= 0.3:
            comp_label = "链上利好 (积累)"
        elif composite <= -0.3:
            comp_label = "链上利空 (派发)"
        else:
            comp_label = "链上中性"

        results["composite_score"] = composite
        results["composite_label"] = comp_label
        results["indicators"] = list(weights.keys())
        return results
