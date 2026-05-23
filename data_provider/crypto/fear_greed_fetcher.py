# -*- coding: utf-8 -*-
"""Fear & Greed Index client for crypto market sentiment.

Data source: alternative.me (free, no API key required).
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

import requests

logger = logging.getLogger(__name__)

FEAR_GREED_URL = "https://api.alternative.me/fng/"

CLASSIFICATION_COLORS = {
    "Extreme Fear": "#dc2626",
    "Fear": "#f97316",
    "Neutral": "#eab308",
    "Greed": "#22c55e",
    "Extreme Greed": "#16a34a",
}


class FearGreedClient:
    """Fetch Fear & Greed Index from alternative.me."""

    def __init__(self, timeout: int = 10):
        self._timeout = timeout

    def _fetch(self, limit: int = 1) -> List[Dict]:
        try:
            resp = requests.get(
                FEAR_GREED_URL,
                params={"limit": limit, "format": "json"},
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", [])
        except Exception as e:
            logger.error("Fear & Greed fetch failed: %s", e)
            return []

    def get_current(self) -> Optional[Dict[str, Any]]:
        data = self._fetch(limit=1)
        if data:
            return {
                "value": int(data[0].get("value", 50)),
                "classification": data[0].get("value_classification", "Neutral"),
                "timestamp": datetime.now().isoformat(),
            }
        return None

    def get_history(self, days: int = 30) -> List[Dict[str, Any]]:
        data = self._fetch(limit=days)
        result = []
        for d in data:
            try:
                ts = datetime.fromtimestamp(int(d.get("timestamp", 0)))
            except (ValueError, OSError):
                ts = datetime.now()
            result.append({
                "value": int(d.get("value", 50)),
                "classification": d.get("value_classification", "Neutral"),
                "timestamp": ts.isoformat(),
            })
        return result

    def get_signal(self) -> Dict[str, Any]:
        """Get F&G as a contrarian signal (-1 to +1).

        Extreme Fear → buy signal (contrarian)
        Extreme Greed → sell signal (contrarian)
        """
        current = self.get_current()
        if not current:
            return {"score": 0.0, "label": "no_data", "value": None}

        value = current["value"]
        # Map [0, 100] to [-1, +1] with inverse relationship (fear=buy)
        score = round((50 - value) / 50, 3)

        if value <= 25:
            label = f"极度恐惧 {value} (买入信号)"
        elif value <= 40:
            label = f"恐惧 {value} (偏买)"
        elif value <= 60:
            label = f"中性 {value}"
        elif value <= 75:
            label = f"贪婪 {value} (偏卖)"
        else:
            label = f"极度贪婪 {value} (卖出信号)"

        return {"score": score, "label": label, "value": value,
                "classification": current["classification"]}
