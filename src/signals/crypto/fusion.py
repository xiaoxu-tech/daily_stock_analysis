# -*- coding: utf-8 -*-
"""Signal Fusion Engine: 6-factor weighted composite trading signals.

Combines:
    1. AI News Sentiment (28%) — from analyzed crypto news in DB
    2. Technical Analysis (22%) — multi-TF RSI/MACD/BB/EMA
    3. Fear & Greed (10%) — contrarian indicator
    4. Price Momentum (14%) — 24h + 7d percent changes
    5. Macro Regime (18%) — DXY, VIX, rates, inflation, etc.
    6. On-chain Data (8%) — exchange flows, TVL, hashrate, etc.

Output: composite score [-1.0, +1.0] → signal label
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, Tuple

import httpx
import numpy as np
import pandas as pd

from src.data.crypto_sector_loader import get_paprika_id
from .indicators import TechnicalIndicators

logger = logging.getLogger(__name__)

# Signal strength thresholds
STRONG_BUY = 0.6
BUY = 0.3
NEUTRAL_LOW = -0.3
SELL = -0.3
STRONG_SELL = -0.6


def classify_signal(score: float) -> str:
    """Convert a composite score [-1, +1] to a human-readable signal label."""
    if score >= STRONG_BUY:
        return "strong_buy"
    elif score >= BUY:
        return "buy"
    elif score >= NEUTRAL_LOW:
        return "neutral"
    elif score >= STRONG_SELL:
        return "sell"
    else:
        return "strong_sell"


SIGNAL_CN: Dict[str, str] = {
    "strong_buy": "🟢 强烈买入",
    "buy": "🟢 买入",
    "neutral": "🟡 中性",
    "sell": "🔴 卖出",
    "strong_sell": "🔴 强烈卖出",
}


class SignalFusion:
    """6-factor weighted composite signal generator for crypto assets.

    Usage:
        sf = SignalFusion(db_manager=db)
        result = sf.get_composite_signal("BTC")
        # result is a dict with composite score, signal label, components, weights.
    """

    def __init__(
        self,
        db_manager=None,
        enabled_signals: Optional[List[str]] = None,
        weights: Optional[Dict[str, float]] = None,
    ):
        """Initialize the signal fusion engine.

        Args:
            db_manager: DSA's DatabaseManager singleton for crypto_news queries.
            enabled_signals: Which signal components to include (None = all 6).
            weights: Custom weights dict. None uses defaults below.
        """
        self._db = db_manager

        # Default weights (sum to 1.0)
        self.weights = weights or {
            "sentiment": 0.28,
            "technical": 0.22,
            "fear_greed": 0.10,
            "momentum": 0.14,
            "macro": 0.18,
            "onchain": 0.08,
        }
        self._enabled = set(enabled_signals or self.weights.keys())

    # ------------------------------------------------------------------
    # 1. AI News Sentiment Signal
    # ------------------------------------------------------------------

    def _get_sentiment_signal(self, coin_symbol: str) -> Tuple[float, dict]:
        """Extract AI sentiment for a coin from recent analyzed news in DB."""
        if not self._db:
            return 0.0, {"signal": "no_data", "score": 0.0, "news_count": 0}

        try:
            # Use the DB crypto_news methods we added in Phase 1
            recent_data = self._db.get_crypto_news(hours=168, limit=200)  # 7 days
            if not recent_data:
                return 0.0, {"signal": "no_data", "score": 0.0, "news_count": 0}

            # Filter news that mention this coin (in mentioned_coins JSON)
            relevant = []
            for row in recent_data:
                try:
                    import json
                    coins = json.loads(row.get("mentioned_coins", "[]") or "[]")
                    if coin_symbol.upper() in [c.upper() for c in coins]:
                        score = row.get("sentiment_score")
                        if score is not None:
                            relevant.append(float(score))
                except Exception:
                    continue

            if not relevant:
                return 0.0, {"signal": "no_data", "score": 0.0, "news_count": 0}

            avg = float(np.mean(relevant))
            count = len(relevant)

            # Convert 0-1 sentiment score to -1 to +1 signal
            signal = (avg - 0.5) * 2.0

            if avg >= 0.65:
                label = "bullish"
            elif avg >= 0.55:
                label = "slightly_bullish"
            elif avg >= 0.45:
                label = "neutral"
            elif avg >= 0.35:
                label = "slightly_bearish"
            else:
                label = "bearish"

            return signal, {"signal": label, "score": avg, "news_count": count}

        except Exception as e:
            logger.warning("Sentiment signal failed for %s: %s", coin_symbol, e)
            return 0.0, {"signal": "error", "error": str(e)}

    # ------------------------------------------------------------------
    # 2. Multi-Timeframe Technical Signal
    # ------------------------------------------------------------------

    def _fetch_timeframe_data(self, coin_symbol: str) -> Dict[str, pd.DataFrame]:
        """Fetch OHLCV data for 1h/4h/1d timeframes from CoinPaprika."""
        paprika_id = get_paprika_id(coin_symbol)
        if not paprika_id:
            return {}

        now = datetime.now(timezone.utc)
        frames: Dict[str, pd.DataFrame] = {}

        try:
            # 1h data (free plan: ~24h lookback)
            start_1h = (now - timedelta(hours=23)).strftime("%Y-%m-%dT%H:%M:%SZ")
            r = httpx.get(
                f"https://api.coinpaprika.com/v1/tickers/{paprika_id}/historical",
                params={"start": start_1h, "interval": "1h"},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=20,
            )
            if r.status_code == 200:
                records = r.json()
                if len(records) >= 14:
                    df_1h = pd.DataFrame(records)
                    df_1h["close"] = pd.to_numeric(df_1h["price"], errors="coerce")
                    df_1h["high"] = df_1h["close"]
                    df_1h["low"] = df_1h["close"]
                    df_1h["open"] = df_1h["close"]
                    if "volume_24h" in df_1h.columns:
                        df_1h["volume"] = pd.to_numeric(df_1h["volume_24h"], errors="coerce")
                    df_1h["timestamp"] = pd.to_datetime(df_1h["timestamp"])
                    df_1h = df_1h.sort_values("timestamp").dropna(subset=["close"])
                    frames["1h"] = df_1h

                    # Resample 1h → 4h
                    if len(df_1h) >= 12:
                        df_1h_idx = df_1h.set_index("timestamp")
                        df_4h = df_1h_idx.resample("4h").agg({
                            "open": "first", "high": "max",
                            "low": "min", "close": "last", "volume": "sum",
                        }).dropna()
                        if len(df_4h) >= 3:
                            frames["4h"] = df_4h.reset_index()
        except Exception as e:
            logger.warning("1h/4h data fetch failed for %s: %s", coin_symbol, e)

        try:
            # 1d data (90 days)
            start_1d = (now - timedelta(days=90)).strftime("%Y-%m-%dT00:00:00Z")
            r = httpx.get(
                f"https://api.coinpaprika.com/v1/tickers/{paprika_id}/historical",
                params={"start": start_1d, "interval": "1d"},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=15,
            )
            if r.status_code == 200:
                records = r.json()
                if len(records) >= 14:
                    df_1d = pd.DataFrame(records)
                    df_1d["close"] = pd.to_numeric(df_1d["price"], errors="coerce")
                    if "volume_24h" in df_1d.columns:
                        df_1d["volume"] = pd.to_numeric(df_1d["volume_24h"], errors="coerce")
                    df_1d["timestamp"] = pd.to_datetime(df_1d["timestamp"])
                    df_1d = df_1d.sort_values("timestamp").dropna(subset=["close"])
                    frames["1d"] = df_1d
        except Exception as e:
            logger.warning("1d data fetch failed for %s: %s", coin_symbol, e)

        return frames

    @staticmethod
    def _compute_single_tf_score(df: pd.DataFrame) -> Tuple[float, dict]:
        """Compute RSI/MACD/BB/EMA score for a single timeframe."""
        try:
            ti = TechnicalIndicators(df)
            ti.compute_all()
            indicators = ti.get_latest_signals()

            rsi = indicators.get("rsi")
            macd_signal = indicators.get("macd_signal")
            bb_signal = indicators.get("bb_signal")
            ema_trend = indicators.get("ema_trend")

            score = 0.0
            details: Dict[str, Any] = {}

            # RSI
            if rsi is not None:
                details["rsi"] = round(rsi, 1)
                if rsi > 70:
                    score -= 0.4
                elif rsi > 60:
                    score -= 0.1
                elif rsi < 30:
                    score += 0.4
                elif rsi < 40:
                    score += 0.1

            # MACD
            if macd_signal:
                details["macd_signal"] = macd_signal
                if macd_signal == "bullish_cross":
                    score += 0.35
                elif macd_signal == "bullish":
                    score += 0.15
                elif macd_signal == "bearish_cross":
                    score -= 0.35
                elif macd_signal == "bearish":
                    score -= 0.15

            # Bollinger Bands
            if bb_signal:
                details["bb_signal"] = bb_signal
                if bb_signal == "below_band":
                    score += 0.2
                elif bb_signal == "above_band":
                    score -= 0.2

            # EMA trend
            if ema_trend:
                details["ema_trend"] = ema_trend
                score += 0.15 if ema_trend == "bullish" else -0.15

            score = max(-1.0, min(1.0, score))
            return score, details
        except Exception:
            return 0.0, {"rsi": None}

    def _get_technical_signal(self, coin_symbol: str) -> Tuple[float, dict]:
        """Multi-timeframe technical analysis with alignment bonus.

        Weights: 1h=35%, 4h=35%, 1d=30%
        Alignment: if all 3 TFs agree on direction → +20% boost.
        """
        frames = self._fetch_timeframe_data(coin_symbol)
        if not frames:
            return 0.0, {"signal": "no_data", "rsi": None}

        tf_scores: Dict[str, float] = {}
        tf_details: Dict[str, Any] = {}

        for tf_name in ("1h", "4h", "1d"):
            if tf_name in frames:
                score, detail = self._compute_single_tf_score(frames[tf_name])
                tf_scores[tf_name] = score
                tf_details[tf_name] = detail
            else:
                tf_scores[tf_name] = 0.0
                tf_details[tf_name] = {"rsi": None}

        weights = {"1h": 0.35, "4h": 0.35, "1d": 0.30}
        total_w = sum(weights[tf] for tf in tf_scores if tf in frames)
        if total_w == 0:
            return 0.0, {"signal": "no_data", "rsi": None}

        composite = sum(
            tf_scores[tf] * weights[tf] / total_w
            for tf in tf_scores if tf in frames
        )

        # Alignment bonus
        available_scores = [tf_scores[tf] for tf in tf_scores if tf in frames]
        if len(available_scores) >= 2:
            all_bullish = all(s > 0.05 for s in available_scores)
            all_bearish = all(s < -0.05 for s in available_scores)
            if all_bullish or all_bearish:
                composite *= 1.20
            alignment = "all_bullish" if all_bullish else ("all_bearish" if all_bearish else "mixed")
        else:
            alignment = "insufficient"

        composite = max(-1.0, min(1.0, composite))

        d1 = tf_details.get("1d", {})
        detail = {
            "signal": "multi_tf",
            "rsi": d1.get("rsi"),
            "macd": d1.get("macd_signal"),
            "bb": d1.get("bb_signal"),
            "ema": d1.get("ema_trend"),
            "score": round(composite, 3),
            "alignment": alignment,
            "timeframes": {
                tf: {
                    "score": round(tf_scores[tf], 3),
                    **{k: v for k, v in tf_details.get(tf, {}).items()},
                }
                for tf in ("1h", "4h", "1d") if tf in tf_details
            },
        }
        return composite, detail

    # ------------------------------------------------------------------
    # 3. Fear & Greed Signal
    # ------------------------------------------------------------------

    def _get_fng_signal(self) -> Tuple[float, dict]:
        """Fear & Greed Index → contrarian signal."""
        try:
            from data_provider.crypto.fear_greed_fetcher import FearGreedClient
            client = FearGreedClient()
            fng = client.get_signal()
            client.close()

            if not fng or fng.get("label") == "no_data":
                return 0.0, {"signal": "no_data"}

            score = fng.get("score", 0.0)
            value = fng.get("latest_value")
            label = fng.get("label", "no_data")
            return score, {"signal": label, "value": value}
        except Exception as e:
            logger.warning("F&G signal failed: %s", e)
            return 0.0, {"signal": "error", "error": str(e)}

    # ------------------------------------------------------------------
    # 4. Price Momentum Signal
    # ------------------------------------------------------------------

    def _get_momentum_signal(self, coin_symbol: str) -> Tuple[float, dict]:
        """Price momentum from CoinPaprika ticker (24h + 7d % change)."""
        paprika_id = get_paprika_id(coin_symbol)
        if not paprika_id:
            return 0.0, {"signal": "no_data"}

        try:
            from data_provider.crypto.coinpaprika_fetcher import CoinpaprikaFetcher
            fetcher = CoinpaprikaFetcher()
            ticker = fetcher.get_ticker(paprika_id)
            if not ticker:
                return 0.0, {"signal": "no_data"}

            change_24h = ticker.get("percent_change_24h") or 0
            change_7d = ticker.get("percent_change_7d") or 0

            momentum = change_24h * 0.6 + change_7d * 0.4

            # Map to -1..+1
            if momentum > 10:
                signal = 0.8
            elif momentum > 5:
                signal = 0.5
            elif momentum > 1:
                signal = 0.2
            elif momentum > -1:
                signal = 0.0
            elif momentum > -5:
                signal = -0.2
            elif momentum > -10:
                signal = -0.5
            else:
                signal = -0.8

            details = {
                "price": ticker.get("price_usd"),
                "change_24h": change_24h,
                "change_7d": change_7d,
                "momentum_pct": round(momentum, 2),
            }
            return signal, details
        except Exception as e:
            logger.warning("Momentum signal failed for %s: %s", coin_symbol, e)
            return 0.0, {"signal": "error", "error": str(e)}

    # ------------------------------------------------------------------
    # 5. Macro Regime Signal
    # ------------------------------------------------------------------

    def _get_macro_signal(self) -> Tuple[float, dict]:
        """Macro regime signal from DXY, rates, CPI, VIX, etc."""
        try:
            from data_provider.crypto.macro_fetcher import MacroClient
            client = MacroClient()
            signals = client.get_all_signals()
            client.close()

            score = signals.get("composite_score", 0.0)
            label = signals.get("composite_label", "no_data")
            return score, {
                "signal": label, "score": score,
                "dxy": signals.get("dxy", {}).get("latest_value"),
                "rate": signals.get("rate", {}).get("latest_value"),
                "inflation": signals.get("inflation", {}).get("latest_value"),
                "vix": signals.get("vix", {}).get("latest_value"),
                "spx": signals.get("spx", {}).get("latest_value"),
            }
        except Exception as e:
            logger.warning("Macro signal failed: %s", e)
            return 0.0, {"signal": "error", "error": str(e)}

    # ------------------------------------------------------------------
    # 6. On-chain Signal
    # ------------------------------------------------------------------

    def _get_onchain_signal(self, coin_symbol: str) -> Tuple[float, dict]:
        """On-chain composite signal (exchange flows, TVL, hashrate, etc.)."""
        try:
            asset_map = {"BTC": "btc", "ETH": "eth", "SOL": "sol", "LTC": "ltc"}
            asset = asset_map.get(coin_symbol.upper(), "btc")

            from data_provider.crypto.onchain_fetcher import OnchainClient
            client = OnchainClient()
            signals = client.get_all_signals(asset)
            client.close()

            score = signals.get("composite_score", 0.0)
            label = signals.get("composite_label", "no_data")
            return score, {
                "signal": label, "score": score,
                "exchange_flow": signals.get("exchange_flow", {}).get("score", 0.0),
                "active_addresses": signals.get("active_addresses", {}).get("score", 0.0),
                "tvl": signals.get("tvl", {}).get("score", 0.0),
                "stablecoins": signals.get("stablecoins", {}).get("score", 0.0),
                "hashrate": signals.get("hashrate", {}).get("score", 0.0),
            }
        except Exception as e:
            logger.warning("Onchain signal failed for %s: %s", coin_symbol, e)
            return 0.0, {"signal": "error", "error": str(e)}

    # ------------------------------------------------------------------
    # Composite
    # ------------------------------------------------------------------

    def get_composite_signal(self, coin_symbol: str) -> Dict[str, Any]:
        """Calculate the full 6-factor composite signal for a single coin.

        Returns:
            Dict with keys: coin, composite, signal, signal_cn, components, weights.
        """
        coin_symbol = coin_symbol.upper()

        # Collect all signals
        signals: Dict[str, Tuple[float, dict]] = {}

        if "sentiment" in self._enabled:
            signals["sentiment"] = self._get_sentiment_signal(coin_symbol)
        if "technical" in self._enabled:
            signals["technical"] = self._get_technical_signal(coin_symbol)
        if "fear_greed" in self._enabled:
            signals["fear_greed"] = self._get_fng_signal()
        if "momentum" in self._enabled:
            signals["momentum"] = self._get_momentum_signal(coin_symbol)
        if "macro" in self._enabled:
            signals["macro"] = self._get_macro_signal()
        if "onchain" in self._enabled:
            signals["onchain"] = self._get_onchain_signal(coin_symbol)

        # Weighted composite
        composite = 0.0
        total_weight = 0.0
        components: Dict[str, Any] = {}

        for name, (score, detail) in signals.items():
            w = self.weights.get(name, 0.0)
            composite += w * score
            total_weight += w
            components[name] = {"score": round(score, 3), **detail}

        if total_weight > 0:
            composite /= total_weight
        composite = round(composite, 3)

        signal_label = classify_signal(composite)

        result = {
            "coin": coin_symbol,
            "composite": composite,
            "signal": signal_label,
            "signal_cn": SIGNAL_CN.get(signal_label, signal_label),
            "components": components,
            "weights": {k: v for k, v in self.weights.items() if k in self._enabled},
        }

        # Persist to DB if available
        if self._db:
            try:
                import json
                self._db.save_composite_signal(
                    asset_code=coin_symbol,
                    asset_type="crypto",
                    composite_score=composite,
                    signal_label=signal_label,
                    components_json=json.dumps(components, ensure_ascii=False),
                    weights_json=json.dumps(result["weights"], ensure_ascii=False),
                )
            except Exception as e:
                logger.debug("Failed to persist composite signal: %s", e)

        return result

    def get_all_signals(self, coin_symbols: List[str]) -> List[Dict[str, Any]]:
        """Get composite signals for multiple coins, sorted by signal strength."""
        results = []
        for symbol in coin_symbols:
            try:
                signal = self.get_composite_signal(symbol)
                results.append(signal)
            except Exception as e:
                logger.error("Signal failed for %s: %s", symbol, e)

        results.sort(key=lambda x: x["composite"], reverse=True)
        return results
