# -*- coding: utf-8 -*-
"""Macroeconomic data client for crypto regime analysis.

Fetches macro indicators and converts them to trading signals (-1 to +1).
Data sources (all FREE): Yahoo Finance v8, FRED public CSV, GPR Index.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any

import httpx
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

YAHOO_SYMBOLS = {
    "dxy": "DX-Y.NYB",
    "tnx": "^TNX",
    "vix": "^VIX",
    "spx": "^GSPC",
}

FRED_SERIES = {
    "fed_funds": "FEDFUNDS",
    "cpi": "CPIAUCSL",
    "unemployment": "UNRATE",
}

GPR_URL = "https://www.matteoiacoviello.com/gpr_files/data_gpr_export.xls"


class MacroClient:
    """Fetch macro indicators and generate composite macro regime signal."""

    def __init__(self, timeout: int = 20):
        self._session = httpx.Client(
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            timeout=timeout,
        )

    def close(self):
        self._session.close()

    # ── Data fetching ──

    def _fetch_yahoo(self, symbol: str, period: str = "6mo") -> Optional[pd.Series]:
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
            r = self._session.get(url, params={"range": period, "interval": "1d"})
            if r.status_code != 200:
                logger.warning("Yahoo %s returned %s", symbol, r.status_code)
                return None
            data = r.json()
            result = data.get("chart", {}).get("result", [])
            if not result:
                return None
            quotes = result[0]
            timestamps = quotes.get("timestamp", [])
            closes = quotes.get("indicators", {}).get("quote", [{}])[0].get("close", [])
            s = pd.Series(closes, index=pd.to_datetime(timestamps, unit="s"), name=symbol)
            return s.dropna()
        except Exception as e:
            logger.error("Yahoo fetch error for %s: %s", symbol, e)
            return None

    def _fetch_fred(self, series_id: str) -> Optional[pd.Series]:
        try:
            url = "https://fred.stlouisfed.org/graph/fredgraph.csv"
            r = self._session.get(url, params={"id": series_id, "cosd": "2015-01-01"})
            if r.status_code != 200:
                logger.warning("FRED %s returned %s", series_id, r.status_code)
                return None
            lines = r.text.strip().split("\n")
            data = []
            for line in lines[1:]:
                parts = line.split(",")
                if len(parts) == 2:
                    try:
                        data.append((pd.to_datetime(parts[0]), float(parts[1])))
                    except (ValueError, TypeError):
                        continue
            if not data:
                return None
            dates, vals = zip(*data)
            return pd.Series(vals, index=pd.DatetimeIndex(dates), name=series_id).sort_index()
        except Exception as e:
            logger.error("FRED fetch error for %s: %s", series_id, e)
            return None

    def _fetch_gpr(self) -> Optional[pd.Series]:
        try:
            r = self._session.get(GPR_URL)
            if r.status_code != 200:
                return None
            df = None
            for engine in ["openpyxl", "xlrd", None]:
                try:
                    df = pd.read_excel(pd.io.common.BytesIO(r.content), engine=engine)
                    break
                except Exception:
                    continue
            if df is None:
                return None
            if "Unnamed: 0" in df.columns:
                df = df.set_index("Unnamed: 0")
            gpr_row = None
            for idx in df.index:
                if isinstance(idx, str) and "all" in idx.lower():
                    gpr_row = df.loc[idx]
                    break
            if gpr_row is None:
                gpr_row = df.iloc[0]
            dates, values = [], []
            for col in df.columns:
                try:
                    if isinstance(col, str) and len(str(col)) >= 6:
                        dates.append(pd.to_datetime(str(col)))
                        values.append(float(gpr_row[col]))
                except (ValueError, TypeError):
                    continue
            if not dates:
                return None
            return pd.Series(values, index=pd.DatetimeIndex(dates), name="gpr").sort_index()
        except Exception as e:
            logger.error("GPR fetch error: %s", e)
            return None

    # ── Individual signal generators ──

    def get_dxy_signal(self) -> dict:
        s = self._fetch_yahoo(YAHOO_SYMBOLS["dxy"], "6mo")
        if s is None or len(s) < 10:
            return {"score": 0.0, "label": "no_data", "latest_value": None}
        latest = s.iloc[-1]
        sma = s.iloc[-60:].mean() if len(s) >= 60 else s.rolling(20).mean().iloc[-1]
        trend = (latest / sma - 1) * 100
        score = round(float(-np.tanh(trend * 0.5)), 3)
        if score >= 0.3:
            label = f"美元走弱 {latest:.1f} (利好)"
        elif score <= -0.3:
            label = f"美元走强 {latest:.1f} (利空)"
        else:
            label = f"美元震荡 {latest:.1f}"
        return {"score": score, "label": label, "latest_value": round(latest, 2)}

    def get_rate_signal(self) -> dict:
        s = self._fetch_fred(FRED_SERIES["fed_funds"])
        if s is None or len(s) < 3:
            return {"score": 0.0, "label": "no_data", "latest_value": None}
        latest = s.iloc[-1]
        three_mo_ago = s.iloc[-4] if len(s) >= 4 else s.iloc[0]
        change = latest - three_mo_ago
        score = round(float(-np.tanh(change * 2.0)), 3)
        if change < -0.01:
            label = f"降息 {abs(change):.2f}% (利好)"
        elif change > 0.01:
            label = f"加息 {change:.2f}% (利空)"
        else:
            level = "高位" if latest > 4 else ("中位" if latest > 2 else "低位")
            label = f"利率不变 {latest:.2f}% ({level})"
        return {"score": score, "label": label, "latest_value": round(latest, 2)}

    def get_inflation_signal(self) -> dict:
        s = self._fetch_fred(FRED_SERIES["cpi"])
        if s is None or len(s) < 12:
            return {"score": 0.0, "label": "no_data", "latest_value": None}
        latest = s.iloc[-1]
        year_ago = s.iloc[-13] if len(s) >= 13 else s.iloc[0]
        yoy = (latest / year_ago - 1) * 100
        if yoy < 2:
            score, label = 0.6, f"通胀放缓 {yoy:.1f}% (利好)"
        elif yoy < 3:
            score, label = 0.2, f"通胀温和 {yoy:.1f}%"
        elif yoy < 4:
            score, label = -0.3, f"通胀偏高 {yoy:.1f}% (偏空)"
        elif yoy < 6:
            score, label = -0.6, f"通胀高企 {yoy:.1f}% (利空)"
        else:
            score, label = -0.9, f"恶性通胀 {yoy:.1f}% (严重利空)"
        return {"score": score, "label": label, "latest_value": round(yoy, 1)}

    def get_employment_signal(self) -> dict:
        s = self._fetch_fred(FRED_SERIES["unemployment"])
        if s is None or len(s) < 3:
            return {"score": 0.0, "label": "no_data", "latest_value": None}
        latest = s.iloc[-1]
        three_mo_ago = s.iloc[-4] if len(s) >= 4 else s.iloc[0]
        trend = latest - three_mo_ago
        score = round(float(-np.tanh(trend * 3.0)), 3)
        level = "低位" if latest < 4 else ("中位" if latest < 6 else "高位")
        if trend > 0.2:
            label = f"失业率上升 {latest:.1f}% ({level}, 利空)"
        elif trend < -0.2:
            label = f"失业率下降 {latest:.1f}% ({level}, 利好)"
        else:
            label = f"失业率稳定 {latest:.1f}% ({level})"
        return {"score": score, "label": label, "latest_value": round(latest, 1)}

    def get_vix_signal(self) -> dict:
        s = self._fetch_yahoo(YAHOO_SYMBOLS["vix"], "3mo")
        if s is None or len(s) < 5:
            return {"score": 0.0, "label": "no_data", "latest_value": None}
        latest = s.iloc[-1]
        if latest < 15:
            score, label = 0.5, f"极低波动 {latest:.1f} (风险偏好)"
        elif latest < 20:
            score, label = 0.2, f"低波动 {latest:.1f}"
        elif latest < 25:
            score, label = -0.2, f"中等波动 {latest:.1f}"
        elif latest < 30:
            score, label = -0.5, f"高波动 {latest:.1f} (避险)"
        else:
            score, label = -0.8, f"恐慌 {latest:.1f} (严重避险)"
        return {"score": score, "label": label, "latest_value": round(latest, 1)}

    def get_spx_signal(self) -> dict:
        s = self._fetch_yahoo(YAHOO_SYMBOLS["spx"], "6mo")
        if s is None or len(s) < 10:
            return {"score": 0.0, "label": "no_data", "latest_value": None}
        latest = s.iloc[-1]
        sma = s.iloc[-60:].mean() if len(s) >= 60 else s.mean()
        trend = (latest / sma - 1) * 100
        score = round(float(np.tanh(trend * 0.4)), 3)
        if score >= 0.3:
            label = f"股市上涨 {latest:.0f} (利好)"
        elif score <= -0.3:
            label = f"股市下跌 {latest:.0f} (利空)"
        else:
            label = f"股市震荡 {latest:.0f}"
        return {"score": score, "label": label, "latest_value": round(latest, 0)}

    def get_yield_signal(self) -> dict:
        s = self._fetch_yahoo(YAHOO_SYMBOLS["tnx"], "6mo")
        if s is None or len(s) < 10:
            return {"score": 0.0, "label": "no_data", "latest_value": None}
        latest = s.iloc[-1]
        sma = s.iloc[-60:].mean() if len(s) >= 60 else s.mean()
        trend = latest - sma
        score = round(float(-np.tanh(trend * 1.5)), 3)
        if score >= 0.3:
            label = f"收益率下降 {latest:.2f}% (利好)"
        elif score <= -0.3:
            label = f"收益率上升 {latest:.2f}% (利空)"
        else:
            label = f"收益率稳定 {latest:.2f}%"
        return {"score": score, "label": label, "latest_value": round(latest, 2)}

    def get_gpr_signal(self) -> dict:
        s = self._fetch_gpr()
        if s is None or len(s) < 3:
            return {"score": 0.0, "label": "no_data", "latest_value": None}
        latest = s.iloc[-1]
        pctile = (s.iloc[-60:] < latest).mean() if len(s) >= 60 else (s < latest).mean()
        score = round(float((0.5 - pctile) * 2), 3)
        if latest > 150:
            label = f"严重地缘冲突 ({latest:.0f})"
        elif latest > 100:
            label = f"地缘紧张 ({latest:.0f})"
        elif latest > 70:
            label = f"地缘关注 ({latest:.0f})"
        else:
            label = f"地缘平稳 ({latest:.0f})"
        return {"score": score, "label": label, "latest_value": round(latest, 0)}

    # ── Composite ──

    def get_all_signals(self) -> Dict[str, Any]:
        results: Dict[str, Any] = {}
        results["dxy"] = self.get_dxy_signal()
        results["rate"] = self.get_rate_signal()
        results["inflation"] = self.get_inflation_signal()
        results["employment"] = self.get_employment_signal()
        results["vix"] = self.get_vix_signal()
        results["spx"] = self.get_spx_signal()
        results["yield_10y"] = self.get_yield_signal()
        results["gpr"] = self.get_gpr_signal()

        weights = {
            "dxy": 0.18, "rate": 0.20, "inflation": 0.15,
            "employment": 0.10, "vix": 0.12, "spx": 0.12,
            "yield_10y": 0.08, "gpr": 0.05,
        }

        total_w, composite = 0.0, 0.0
        for key, w in weights.items():
            if key in results and results[key]["score"] != 0.0:
                composite += results[key]["score"] * w
                total_w += w

        composite = round(composite / total_w, 3) if total_w > 0 else 0.0

        if composite >= 0.3:
            comp_label = "宏观利好"
        elif composite <= -0.3:
            comp_label = "宏观利空"
        else:
            comp_label = "宏观中性"

        results["composite_score"] = composite
        results["composite_label"] = comp_label
        results["indicators"] = list(weights.keys())
        return results
