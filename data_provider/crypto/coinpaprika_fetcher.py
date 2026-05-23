# -*- coding: utf-8 -*-
"""CoinPaprika crypto price data fetcher.

Implements BaseFetcher for OHLCV data and provides additional ticker/global
market methods for crypto-specific use cases.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

import pandas as pd
from coinpaprika import client as CoinpaprikaClient

from data_provider.base import BaseFetcher

logger = logging.getLogger(__name__)


class CoinpaprikaFetcher(BaseFetcher):
    """Crypto OHLCV data fetcher via CoinPaprika API (free tier)."""

    name = "CoinPaprika"
    priority = 1

    def __init__(self):
        self._client = CoinpaprikaClient.Client()

    def _fetch_raw_data(self, stock_code: str, start_date: str,
                        end_date: str) -> pd.DataFrame:
        paprika_id = stock_code  # In crypto context, stock_code IS paprika_id
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            days = max(1, (end_dt - start_dt).days + 1)
            interval = "1h" if days <= 7 else "1d"
            limit = 24 * days if days <= 7 else days

            data = self._client.historical(
                coin_id=paprika_id, interval=interval, limit=limit,
            )
            if not data:
                return pd.DataFrame()

            rows = []
            for h in data:
                ts = h.get("timestamp")
                if ts:
                    dt = pd.to_datetime(ts)
                else:
                    continue
                rows.append({
                    "date": dt,
                    "open": h.get("open", 0) or h.get("price", 0),
                    "high": h.get("high", 0) or h.get("price", 0),
                    "low": h.get("low", 0) or h.get("price", 0),
                    "close": h.get("close", 0) or h.get("price", 0),
                    "volume": h.get("volume_24h", 0) or 0,
                    "amount": (h.get("price", 0) or 0) * (h.get("volume_24h", 0) or 0),
                    "pct_chg": 0.0,
                })
            return pd.DataFrame(rows)
        except Exception as e:
            logger.error("CoinPaprika historical failed for %s: %s", paprika_id, e)
            raise

    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        df = df.copy()
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
        for col in ["open", "high", "low", "close", "volume", "amount"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna(subset=["close"])
        df["pct_chg"] = df["close"].pct_change() * 100
        df = df.sort_values("date", ascending=True).reset_index(drop=True)
        return df

    # ── Crypto-specific public methods ──

    def get_ticker(self, paprika_id: str) -> Optional[Dict[str, Any]]:
        try:
            data = self._client.ticker(coin_id=paprika_id)
            quotes = data.get("quotes", {}).get("USD", {})
            return {
                "coin_id": paprika_id,
                "symbol": data.get("symbol", ""),
                "name": data.get("name", ""),
                "timestamp": datetime.now(timezone.utc),
                "price_usd": quotes.get("price", 0.0),
                "volume_24h_usd": quotes.get("volume_24h"),
                "market_cap_usd": quotes.get("market_cap"),
                "percent_change_1h": quotes.get("percent_change_1h"),
                "percent_change_24h": quotes.get("percent_change_24h"),
                "percent_change_7d": quotes.get("percent_change_7d"),
                "open_24h": quotes.get("open_24h"),
                "high_24h": quotes.get("high_24h"),
                "low_24h": quotes.get("low_24h"),
            }
        except Exception as e:
            logger.error("CoinPaprika ticker failed for %s: %s", paprika_id, e)
            return None

    def get_top_coins(self, limit: int = 50) -> List[Dict[str, Any]]:
        try:
            data = self._client.top_coins(limit=limit)
            return [
                {
                    "id": c.get("id", ""),
                    "name": c.get("name", ""),
                    "symbol": c.get("symbol", ""),
                    "rank": c.get("rank", 0),
                    "price_usd": c.get("quotes", {}).get("USD", {}).get("price", 0),
                    "market_cap_usd": c.get("quotes", {}).get("USD", {}).get("market_cap", 0),
                    "volume_24h_usd": c.get("quotes", {}).get("USD", {}).get("volume_24h", 0),
                    "percent_change_24h": c.get("quotes", {}).get("USD", {}).get("percent_change_24h", 0),
                    "percent_change_7d": c.get("quotes", {}).get("USD", {}).get("percent_change_7d", 0),
                }
                for c in data
            ]
        except Exception as e:
            logger.error("CoinPaprika top coins failed: %s", e)
            return []

    def get_global_market(self) -> Dict[str, Any]:
        try:
            data = self._client.global_market()
            return {
                "market_cap_usd": data.get("market_cap_usd", 0),
                "volume_24h_usd": data.get("volume_24h_usd", 0),
                "btc_dominance": data.get("bitcoin_dominance", 0),
                "active_cryptocurrencies": data.get("active_cryptocurrencies", 0),
                "total_market_cap_yesterday": data.get("total_market_cap_yesterday", 0),
            }
        except Exception as e:
            logger.error("CoinPaprika global market failed: %s", e)
            return {}

    def get_historical(self, paprika_id: str, days: int = 7) -> List[Dict]:
        try:
            interval = "1h" if days <= 7 else "1d"
            limit = 24 * days if days <= 7 else days
            data = self._client.historical(
                coin_id=paprika_id, interval=interval, limit=limit,
            )
            return [
                {
                    "timestamp": h.get("timestamp"),
                    "open": h.get("open"),
                    "high": h.get("high"),
                    "low": h.get("low"),
                    "close": h.get("close"),
                    "volume_24h": h.get("volume_24h", 0),
                }
                for h in data
            ]
        except Exception as e:
            logger.error("CoinPaprika historical failed for %s: %s", paprika_id, e)
            return []
