# -*- coding: utf-8 -*-
"""Crypto derivatives data client.

Fetches open interest, funding rates, and liquidations from CoinGecko public API.
Free tier: 30 calls/min, no API key needed.
"""

import logging
from typing import Optional, List, Dict, Any

import httpx

logger = logging.getLogger(__name__)

COINGECKO_BASE = "https://api.coingecko.com/api/v3"

COINGECKO_IDS = {
    "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana",
    "XRP": "ripple", "DOGE": "dogecoin", "ADA": "cardano",
    "BNB": "binancecoin", "LINK": "chainlink", "AVAX": "avalanche-2",
    "DOT": "polkadot", "MATIC": "matic-network", "UNI": "uniswap",
    "ATOM": "cosmos", "LTC": "litecoin",
}


class DerivativesClient:
    """Fetch derivatives market data from CoinGecko public API."""

    def __init__(self, timeout: int = 15):
        self._session = httpx.Client(
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=timeout,
        )

    def close(self):
        self._session.close()

    def _get(self, path: str, params: dict = None) -> Optional[dict]:
        try:
            r = self._session.get(f"{COINGECKO_BASE}{path}", params=params or {})
            if r.status_code == 200:
                return r.json()
            elif r.status_code == 429:
                logger.warning("CoinGecko rate limited")
                return None
            else:
                logger.warning("CoinGecko API error: %s", r.status_code)
                return None
        except Exception as e:
            logger.error("CoinGecko request failed: %s", e)
            return None

    def get_derivatives_tickers(self) -> List[Dict[str, Any]]:
        data = self._get("/derivatives")
        if not data:
            return []
        return [
            {
                "symbol": d.get("symbol", ""),
                "exchange": d.get("market", ""),
                "open_interest_usd": d.get("open_interest_usd", 0),
                "volume_24h_usd": d.get("volume_24h", 0),
                "funding_rate": d.get("funding_rate"),
                "liquidation_volume": d.get("liquidation_volume", 0),
            }
            for d in data
        ]

    def get_global_stats(self) -> Dict[str, Any]:
        tickers = self.get_derivatives_tickers()
        if not tickers:
            return {}
        total_oi = sum(t.get("open_interest_usd", 0) or 0 for t in tickers)
        total_vol = sum(t.get("volume_24h_usd", 0) or 0 for t in tickers)
        funding_rates = [t.get("funding_rate") for t in tickers
                         if t.get("funding_rate") is not None]
        return {
            "total_open_interest_usd": total_oi,
            "total_volume_24h_usd": total_vol,
            "avg_funding_rate": (sum(funding_rates) / len(funding_rates)
                                 if funding_rates else 0),
            "funding_positive_count": sum(1 for f in funding_rates if f > 0),
            "funding_negative_count": sum(1 for f in funding_rates if f < 0),
            "ticker_count": len(tickers),
        }

    def get_coin_market_data(self, coin_symbol: str) -> Optional[Dict[str, Any]]:
        cg_id = COINGECKO_IDS.get(coin_symbol.upper())
        if not cg_id:
            return None
        data = self._get(
            f"/coins/{cg_id}",
            params={"localization": "false", "tickers": "false",
                    "community_data": "false", "developer_data": "false"},
        )
        if not data:
            return None
        market = data.get("market_data", {})
        return {
            "symbol": coin_symbol,
            "name": data.get("name", ""),
            "current_price_usd": market.get("current_price", {}).get("usd"),
            "market_cap_usd": market.get("market_cap", {}).get("usd"),
            "total_volume_usd": market.get("total_volume", {}).get("usd"),
            "price_change_24h_pct": market.get("price_change_percentage_24h"),
            "price_change_7d_pct": market.get("price_change_percentage_7d"),
            "price_change_30d_pct": market.get("price_change_percentage_30d"),
            "ath_usd": market.get("ath", {}).get("usd"),
            "ath_date": market.get("ath_date", {}).get("usd"),
            "ath_change_pct": market.get("ath_change_percentage", {}).get("usd"),
            "atl_usd": market.get("atl", {}).get("usd"),
            "high_24h_usd": market.get("high_24h", {}).get("usd"),
            "low_24h_usd": market.get("low_24h", {}).get("usd"),
        }

    def get_trending_coins(self) -> List[Dict[str, Any]]:
        data = self._get("/search/trending")
        if not data:
            return []
        coins = []
        for item in data.get("coins", [])[:15]:
            c = item.get("item", {})
            coins.append({
                "symbol": c.get("symbol", ""),
                "name": c.get("name", ""),
                "market_cap_rank": c.get("market_cap_rank"),
                "score_rank": c.get("score"),
            })
        return coins
