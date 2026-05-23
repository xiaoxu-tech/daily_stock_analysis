# -*- coding: utf-8 -*-
"""Enhanced technical indicators for crypto — derived from DSA's stock analysis.

Unlike `indicators.py` (which uses the `ta` library), this module provides
domain-agnostic indicators originally built for A-share stocks but equally
applicable to cryptocurrency markets:

- CandlestickPatterns: 9 candlestick & chart patterns (Doji, Hammer, Engulfing, etc.)
- VolumeAnalyzer: 5-state volume classification (heavy/shrink × up/down)
- MultiPeriodRSI: RSI(6/12/24) with Wilder's EMA smoothing
- BIASAnalyzer: price deviation from moving averages
- TrendClassifier: MA5/MA10/MA20 7-state trend classification

All classes accept a pandas DataFrame (columns: open, high, low, close, volume)
and return plain dicts — no stock-specific types.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ======================================================================
# CandlestickPatterns — 9 pattern types extracted from DSA agent tools
# ======================================================================

class CandlestickPatterns:
    """Detect candlestick and chart patterns from OHLCV data.

    Patterns detected:
        Single-candle: Doji, Hammer/Hanging Man, Shooting Star/Inverted Hammer,
                       Big Bullish/Bearish candle
        Multi-candle:  Morning Star, Evening Star, Bullish/Bearish Engulfing
        Chart:         Double Bottom, Breakout (20d high), Box Oscillation
    """

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy().reset_index(drop=True)
        self._o: np.ndarray = self.df["open"].values
        self._h: np.ndarray = self.df["high"].values
        self._l: np.ndarray = self.df["low"].values
        self._c: np.ndarray = self.df["close"].values
        self._v: Optional[np.ndarray] = (
            self.df["volume"].values if "volume" in self.df.columns else None
        )
        self._n = len(self._c)

    # -- helpers -----------------------------------------------------------

    def _body(self, i: int) -> float:
        return abs(self._c[i] - self._o[i])

    def _upper_shadow(self, i: int) -> float:
        return self._h[i] - max(self._c[i], self._o[i])

    def _lower_shadow(self, i: int) -> float:
        return min(self._c[i], self._o[i]) - self._l[i]

    def _is_bullish(self, i: int) -> bool:
        return self._c[i] > self._o[i]

    def _is_bearish(self, i: int) -> bool:
        return self._c[i] < self._o[i]

    # -- main API ----------------------------------------------------------

    def detect_all(self) -> Dict[str, Any]:
        """Run all pattern detection and return a dict summary."""
        if self._n < 10:
            return {"error": "insufficient_data", "min_required": 10, "got": self._n}

        patterns: List[Dict[str, Any]] = []
        avg_body = float(sum(self._body(i) for i in range(self._n)) / self._n)

        # --- Single-candle patterns (scan last 5 candles) ---
        for i in range(max(0, self._n - 5), self._n):
            bd = self._body(i)
            us = self._upper_shadow(i)
            ls = self._lower_shadow(i)

            # Doji (十字星)
            if bd < avg_body * 0.1 and (us + ls) > bd * 3:
                patterns.append({
                    "pattern": "十字星 (Doji)", "type": "reversal_signal",
                    "candle_offset": -(self._n - 1 - i),
                    "strength": "弱", "desc": "多空平衡，可能变盘信号",
                })

            # Hammer / Hanging Man
            if ls > bd * 2 and us < bd * 0.5:
                label = (
                    "锤子线 (Hammer)" if i == 0 or self._c[i] >= self._c[i - 1]
                    else "上吊线 (Hanging Man)"
                )
                patterns.append({
                    "pattern": label, "type": "reversal_signal",
                    "candle_offset": -(self._n - 1 - i),
                    "strength": "中", "desc": "下影线长，潜在支撑/反转",
                })

            # Shooting Star / Inverted Hammer
            if us > bd * 2 and ls < bd * 0.5:
                label = "流星线 (Shooting Star)" if self._is_bearish(i) else "倒锤子"
                patterns.append({
                    "pattern": label, "type": "bearish_signal",
                    "candle_offset": -(self._n - 1 - i),
                    "strength": "中", "desc": "上影线长，潜在压力/反转",
                })

            # Big candle
            if bd > avg_body * 2.5:
                label = "大阳线" if self._is_bullish(i) else "大阴线"
                t = "bullish" if self._is_bullish(i) else "bearish"
                patterns.append({
                    "pattern": label, "type": t,
                    "candle_offset": -(self._n - 1 - i),
                    "strength": "强", "desc": "实体大，方向明确",
                })

        # --- Multi-candle patterns ---
        if self._n >= 3:
            i = self._n - 1
            # Morning Star (早晨之星) — bottom reversal
            if (self._is_bearish(i - 2) and self._body(i - 2) > avg_body * 1.5
                    and self._body(i - 1) < avg_body * 0.4
                    and self._is_bullish(i) and self._body(i) > avg_body * 1.5
                    and self._c[i] > (self._o[i - 2] + self._c[i - 2]) / 2):
                patterns.append({
                    "pattern": "早晨之星 (Morning Star)", "type": "bullish_reversal",
                    "candle_offset": -2, "strength": "强",
                    "desc": "三根K线底部反转形态",
                })

            # Evening Star (黄昏之星) — top reversal
            if (self._is_bullish(i - 2) and self._body(i - 2) > avg_body * 1.5
                    and self._body(i - 1) < avg_body * 0.4
                    and self._is_bearish(i) and self._body(i) > avg_body * 1.5
                    and self._c[i] < (self._o[i - 2] + self._c[i - 2]) / 2):
                patterns.append({
                    "pattern": "黄昏之星 (Evening Star)", "type": "bearish_reversal",
                    "candle_offset": -2, "strength": "强",
                    "desc": "三根K线顶部反转形态",
                })

            # Engulfing (吞没形态)
            if (self._is_bullish(i) and self._is_bearish(i - 1)
                    and self._o[i] < self._c[i - 1] and self._c[i] > self._o[i - 1]):
                patterns.append({
                    "pattern": "看涨吞没 (Bullish Engulfing)", "type": "bullish_reversal",
                    "candle_offset": -1, "strength": "强",
                    "desc": "阳线完全覆盖前一阴线",
                })
            elif (self._is_bearish(i) and self._is_bullish(i - 1)
                  and self._o[i] > self._c[i - 1] and self._c[i] < self._o[i - 1]):
                patterns.append({
                    "pattern": "看跌吞没 (Bearish Engulfing)", "type": "bearish_reversal",
                    "candle_offset": -1, "strength": "强",
                    "desc": "阴线完全覆盖前一阳线",
                })

        # --- Chart patterns ---
        # Double bottom: two nearby lows + mid high
        recent_lows_idx = sorted(range(self._n), key=lambda i: self._l[i])[:5]
        if len(recent_lows_idx) >= 2:
            lo1, lo2 = sorted(recent_lows_idx[:2])
            if (lo2 - lo1 >= 5
                    and abs(self._l[lo1] - self._l[lo2]) / max(self._l[lo1], self._l[lo2]) < 0.03):
                mid_high = max(self._h[lo1:lo2 + 1])
                if mid_high > self._l[lo1] * 1.03:
                    patterns.append({
                        "pattern": "双底 (Double Bottom)", "type": "bullish_reversal",
                        "candle_offset": -(self._n - 1 - lo2),
                        "strength": "强", "desc": "两个相近低点，W型底部形态",
                    })

        # Breakout: close above 20d high with volume
        if self._n >= 21:
            high_20d = float(max(self._h[self._n - 21:self._n - 1]))
            if (self._c[-1] > high_20d
                    and self._v is not None
                    and self._v[-1] > sum(self._v[self._n - 6:self._n - 1]) / 5 * 1.5):
                patterns.append({
                    "pattern": "放量突破20日高点", "type": "bullish_breakout",
                    "candle_offset": 0, "strength": "强",
                    "desc": "收盘突破近20日最高，量能配合",
                })

        # Box oscillation: tight range in last 10 candles
        if self._n >= 10:
            recent_high = float(max(self._h[self._n - 10:]))
            recent_low = float(min(self._l[self._n - 10:]))
            box_range_pct = (recent_high - recent_low) / recent_low * 100 if recent_low > 0 else 0
            if box_range_pct < 8:
                patterns.append({
                    "pattern": "箱体震荡", "type": "consolidation",
                    "candle_offset": 0, "strength": "中",
                    "desc": f"近10日波幅 {box_range_pct:.1f}%，价格在区间内震荡",
                })

        # Deduplicate by pattern name
        seen: set = set()
        unique: List[Dict[str, Any]] = []
        for p in reversed(patterns):
            if p["pattern"] not in seen:
                seen.add(p["pattern"])
                unique.append(p)
        unique = list(reversed(unique))

        # -- Composite pattern signal --
        bullish_count = sum(1 for p in unique if "bullish" in p.get("type", ""))
        bearish_count = sum(1 for p in unique if "bearish" in p.get("type", ""))
        total = len(unique) or 1

        pattern_score = (bullish_count - bearish_count) / total
        if pattern_score >= 0.4:
            pattern_signal = "bullish"
        elif pattern_score <= -0.4:
            pattern_signal = "bearish"
        else:
            pattern_signal = "mixed"

        return {
            "patterns_count": len(unique),
            "patterns": unique,
            "pattern_signal": pattern_signal,
            "pattern_score": round(pattern_score, 3),
            "summary": (
                "未发现明显形态" if not unique
                else "、".join(p["pattern"] for p in unique)
            ),
            "current_price": round(float(self._c[-1]), 4),
        }


# ======================================================================
# VolumeAnalyzer — 5-state volume classification
# ======================================================================

class VolumeAnalyzer:
    """Classify volume patterns: heavy/shrink × up/down.

    Uses 5-day average volume as baseline.
    """

    VOLUME_HEAVY = 1.5   # volume_ratio >= 1.5 → heavy
    VOLUME_SHRINK = 0.7  # volume_ratio <= 0.7 → shrink

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy().reset_index(drop=True)

    def analyze(self) -> Dict[str, Any]:
        """Classify current volume regime."""
        n = len(self.df)
        if n < 6:
            return {"volume_status": "insufficient_data", "volume_ratio": 1.0}

        if "volume" not in self.df.columns:
            return {"volume_status": "no_volume_data", "volume_ratio": 1.0}

        latest = self.df.iloc[-1]
        vol_now = float(latest["volume"]) if latest["volume"] and latest["volume"] > 0 else 0
        vol_5d_avg = float(self.df["volume"].iloc[-6:-1].mean()) if n >= 6 else vol_now

        if vol_5d_avg <= 0:
            return {"volume_status": "normal", "volume_ratio": 1.0}

        ratio = vol_now / vol_5d_avg

        # Price direction
        if "close" in self.df.columns:
            prev_close = float(self.df.iloc[-2]["close"]) if n >= 2 else float(self.df.iloc[-1]["close"])
            price_up = vol_now > 0 and float(latest["close"]) > prev_close
        else:
            price_up = True

        if ratio >= self.VOLUME_HEAVY:
            if price_up:
                status, desc = "heavy_volume_up", "放量上涨，多头力量强劲"
            else:
                status, desc = "heavy_volume_down", "放量下跌，注意风险"
        elif ratio <= self.VOLUME_SHRINK:
            if price_up:
                status, desc = "shrink_volume_up", "缩量上涨，上攻动能不足"
            else:
                status, desc = "shrink_volume_down", "缩量回调，洗盘特征明显"
        else:
            status, desc = "normal", "量能正常"

        # Score: positive for bullish volume patterns
        score_map = {
            "shrink_volume_down": 0.3,
            "heavy_volume_up": 0.2,
            "normal": 0.0,
            "shrink_volume_up": -0.1,
            "heavy_volume_down": -0.3,
        }

        return {
            "volume_status": status,
            "volume_desc": desc,
            "volume_ratio": round(ratio, 3),
            "volume_score": score_map.get(status, 0.0),
        }


# ======================================================================
# MultiPeriodRSI — RSI(6/12/24) using Wilder's EMA
# ======================================================================

class MultiPeriodRSI:
    """Compute RSI with Wilder's EMA (SMMA) — matches common charting platforms.

    Ported from StockTrendAnalyzer._calculate_rsi() / _analyze_rsi().
    """

    PERIODS = (6, 12, 24)
    OVERBOUGHT = 70
    OVERSOLD = 30

    def __init__(self, df: pd.DataFrame):
        """DataFrame must have a 'close' column."""
        self.df = df.copy().reset_index(drop=True)

    def compute(self) -> pd.DataFrame:
        """Add RSI_6, RSI_12, RSI_24 columns to the DataFrame."""
        df = self.df
        close = df["close"]

        for period in self.PERIODS:
            delta = close.diff()
            gain = delta.where(delta > 0, 0.0)
            loss = (-delta).where(delta < 0, 0.0)

            avg_gain = gain.ewm(alpha=1.0 / period, adjust=False).mean()
            avg_loss = loss.ewm(alpha=1.0 / period, adjust=False).mean()

            rs = avg_gain / avg_loss.replace(0, float("nan"))
            rsi = 100.0 - (100.0 / (1.0 + rs))
            rsi = rsi.fillna(50.0)

            df[f"RSI_{period}"] = rsi

        self.df = df
        return df

    def get_latest(self) -> Dict[str, Any]:
        """Return the latest RSI values with interpretation."""
        if self.df is None or len(self.df) < max(self.PERIODS):
            return {"rsi_signal": "insufficient_data"}

        rsi_names = [f"RSI_{p}" for p in self.PERIODS]
        for col in rsi_names:
            if col not in self.df.columns:
                self.compute()
                break

        latest = self.df.iloc[-1]
        result: Dict[str, Any] = {}
        for p in self.PERIODS:
            col = f"RSI_{p}"
            val = latest.get(col)
            if val is not None and not pd.isna(val):
                result[col.lower()] = round(float(val), 1)

        # Use RSI_12 as primary for signal
        rsi_mid = result.get("rsi_12", 50.0)

        if rsi_mid > self.OVERBOUGHT:
            signal = "overbought"
            score = -0.4
        elif rsi_mid > 60:
            signal = "strong"
            score = 0.15
        elif rsi_mid >= 40:
            signal = "neutral"
            score = 0.0
        elif rsi_mid >= self.OVERSOLD:
            signal = "weak"
            score = 0.1
        else:
            signal = "oversold"
            score = 0.4

        # Multi-period resonance
        vals = [result.get(f"rsi_{p}") for p in self.PERIODS]
        if all(v is not None for v in vals):
            result["rsi_resonance"] = (
                "all_overbought" if all(v > self.OVERBOUGHT for v in vals)
                else "all_oversold" if all(v < self.OVERSOLD for v in vals)
                else "mixed"
            )

        result["rsi_signal"] = signal
        result["rsi_score"] = score

        return result


# ======================================================================
# BIASAnalyzer — price deviation from moving averages
# ======================================================================

class BIASAnalyzer:
    """Compute price deviation (乖离率) from MA5 and MA20.

    High positive bias → over-extended (risk of pullback).
    High negative bias → oversold (potential bounce).
    """

    MA_SLOW = 20   # MA20
    MA_FAST = 5    # MA5

    def __init__(self, df: pd.DataFrame):
        """DataFrame must have a 'close' column."""
        self.df = df.copy().reset_index(drop=True)

    def compute(self) -> pd.DataFrame:
        """Add MA5, MA20, BIAS_MA5, BIAS_MA20 columns."""
        df = self.df
        df["MA5"] = df["close"].rolling(window=self.MA_FAST).mean()
        df["MA20"] = df["close"].rolling(window=self.MA_SLOW).mean()
        df["BIAS_MA5"] = (df["close"] - df["MA5"]) / df["MA5"] * 100.0
        df["BIAS_MA20"] = (df["close"] - df["MA20"]) / df["MA20"] * 100.0
        self.df = df
        return df

    def get_latest(self) -> Dict[str, Any]:
        """Return latest MA values and BIAS with interpretation."""
        cols_needed = ["MA5", "MA20", "BIAS_MA5", "BIAS_MA20"]
        for col in cols_needed:
            if col not in self.df.columns:
                self.compute()
                break

        latest = self.df.iloc[-1]
        bias_ma5 = float(latest.get("BIAS_MA5", 0) or 0)
        bias_ma20 = float(latest.get("BIAS_MA20", 0) or 0)
        ma5 = float(latest.get("MA5", 0) or 0)
        ma20 = float(latest.get("MA20", 0) or 0)
        close = float(latest.get("close", 0) or 0)

        # Score: prefer moderate bias (not too far from MA)
        # Positive extreme (>8%) → bearish (overbought), negative extreme (<-8%) → bullish (oversold)
        abs_bias = abs(bias_ma5)

        if abs_bias > 15:
            bias_score = -0.3  # extreme deviation, either direction
        elif abs_bias > 8:
            # If price way above MA → risk of pullback; way below → potential bounce
            bias_score = -0.3 if bias_ma5 > 0 else 0.3
        elif abs_bias > 4:
            bias_score = -0.1 if bias_ma5 > 0 else 0.15
        elif abs_bias > 1:
            bias_score = 0.1  # slight pullback, good entry
        else:
            bias_score = 0.2  # trading right at MA, neutral

        # Bias signal label
        if bias_ma5 > 8:
            bias_signal = "highly_extended"
        elif bias_ma5 > 4:
            bias_signal = "extended"
        elif bias_ma5 > 1:
            bias_signal = "slightly_extended"
        elif bias_ma5 > -1:
            bias_signal = "near_ma"
        elif bias_ma5 > -4:
            bias_signal = "slightly_depressed"
        elif bias_ma5 > -8:
            bias_signal = "depressed"
        else:
            bias_signal = "highly_depressed"

        return {
            "ma5": round(ma5, 4),
            "ma20": round(ma20, 4),
            "close": round(close, 4),
            "bias_ma5_pct": round(bias_ma5, 2),
            "bias_ma20_pct": round(bias_ma20, 2),
            "bias_signal": bias_signal,
            "bias_score": round(bias_score, 3),
        }


# ======================================================================
# TrendClassifier — MA5/MA10/MA20 7-state trend
# ======================================================================

class TrendClassifier:
    """Classify trend based on MA5/MA10/MA20 alignment.

    7 states (strongest → weakest):
        strong_bull → bull → weak_bull → consolidation →
        weak_bear → bear → strong_bear
    """

    def __init__(self, df: pd.DataFrame):
        """DataFrame must have a 'close' column."""
        self.df = df.copy().reset_index(drop=True)

    def compute(self) -> pd.DataFrame:
        """Add MA5, MA10, MA20 columns."""
        df = self.df
        df["MA5"] = df["close"].rolling(window=5).mean()
        df["MA10"] = df["close"].rolling(window=10).mean()
        df["MA20"] = df["close"].rolling(window=20).mean()
        self.df = df
        return df

    def classify(self) -> Dict[str, Any]:
        """Return trend classification based on latest MA alignment."""
        for col in ("MA5", "MA10", "MA20"):
            if col not in self.df.columns:
                self.compute()
                break

        n = len(self.df)
        if n < 22:  # need at least one valid MA20 + 1 prior for comparison
            return {"trend_state": "insufficient_data", "trend_score": 0.0}

        latest = self.df.iloc[-1]
        ma5 = float(latest["MA5"] or 0)
        ma10 = float(latest["MA10"] or 0)
        ma20 = float(latest["MA20"] or 0)

        if ma5 == 0 or ma10 == 0 or ma20 == 0:
            return {"trend_state": "insufficient_data", "trend_score": 0.0}

        # Determine alignment
        prev = self.df.iloc[-6]  # ~5 candles back for spread comparison

        if ma5 > ma10 > ma20:
            prev_spread = (float(prev["MA5"] or ma5) - float(prev["MA20"] or ma20)) / float(prev["MA20"] or 1) * 100
            curr_spread = (ma5 - ma20) / ma20 * 100
            if curr_spread > prev_spread and curr_spread > 5:
                state, score, desc = "strong_bull", 0.9, "强势多头，均线发散上行"
            else:
                state, score, desc = "bull", 0.6, "多头排列 MA5>MA10>MA20"

        elif ma5 > ma10 and ma10 <= ma20:
            state, score, desc = "weak_bull", 0.2, "弱势多头，MA5>MA10但MA10≤MA20"

        elif ma5 < ma10 < ma20:
            prev_spread = (float(prev["MA20"] or ma20) - float(prev["MA5"] or ma5)) / float(prev["MA5"] or 1) * 100
            curr_spread = (ma20 - ma5) / ma5 * 100
            if curr_spread > prev_spread and curr_spread > 5:
                state, score, desc = "strong_bear", -0.9, "强势空头，均线发散下行"
            else:
                state, score, desc = "bear", -0.6, "空头排列 MA5<MA10<MA20"

        elif ma5 < ma10 and ma10 >= ma20:
            state, score, desc = "weak_bear", -0.2, "弱势空头，MA5<MA10但MA10≥MA20"

        else:
            state, score, desc = "consolidation", 0.0, "均线缠绕，趋势不明"

        return {
            "trend_state": state,
            "trend_desc": desc,
            "trend_score": score,
            "ma5": round(ma5, 4),
            "ma10": round(ma10, 4),
            "ma20": round(ma20, 4),
            "close": round(float(latest["close"] or 0), 4),
        }


# ======================================================================
# Convenience: compute all enhanced indicators at once
# ======================================================================

def compute_enhanced_indicators(df: pd.DataFrame) -> Dict[str, Any]:
    """Run all enhanced indicators on a single OHLCV DataFrame.

    Returns a dict suitable for merging into the signal fusion pipeline.

    Args:
        df: DataFrame with columns open, high, low, close, volume (all optional
            except close; missing columns degrade gracefully).

    Returns:
        Dict with keys: patterns, volume, rsi, bias, trend — each a sub-dict.
    """
    result: Dict[str, Any] = {}

    # Ensure numeric types
    for col in ("open", "high", "low", "close"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "volume" in df.columns:
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
    df = df.dropna(subset=["close"])

    if len(df) < 10:
        return {"error": "insufficient_data", "min_rows": 10, "got": len(df)}

    # 1. Candlestick patterns (needs open, high, low, close)
    has_ohlc = all(c in df.columns for c in ("open", "high", "low"))
    if has_ohlc:
        try:
            patterns = CandlestickPatterns(df)
            result["patterns"] = patterns.detect_all()
        except Exception as e:
            logger.debug("Pattern detection failed: %s", e)
            result["patterns"] = {"error": str(e)}
    else:
        result["patterns"] = {"error": "missing OHLC columns for patterns"}

    # 2. Volume analysis
    if "volume" in df.columns:
        try:
            va = VolumeAnalyzer(df)
            result["volume"] = va.analyze()
        except Exception as e:
            logger.debug("Volume analysis failed: %s", e)
            result["volume"] = {"error": str(e)}
    else:
        result["volume"] = {"error": "missing volume column"}

    # 3. Multi-period RSI
    try:
        rsi = MultiPeriodRSI(df)
        result["rsi"] = rsi.get_latest()
    except Exception as e:
        logger.debug("Multi-RSI failed: %s", e)
        result["rsi"] = {"error": str(e)}

    # 4. BIAS
    try:
        bias = BIASAnalyzer(df)
        result["bias"] = bias.get_latest()
    except Exception as e:
        logger.debug("BIAS failed: %s", e)
        result["bias"] = {"error": str(e)}

    # 5. Trend classification
    try:
        trend = TrendClassifier(df)
        result["trend"] = trend.classify()
    except Exception as e:
        logger.debug("Trend classification failed: %s", e)
        result["trend"] = {"error": str(e)}

    # -- Compute a composite enhanced score --
    scores = []
    weights = []

    # Pattern score (weight: 20%)
    pat = result.get("patterns", {})
    if "pattern_score" in pat:
        scores.append(pat["pattern_score"])
        weights.append(0.20)

    # Volume score (weight: 15%)
    vol = result.get("volume", {})
    if "volume_score" in vol:
        scores.append(vol["volume_score"])
        weights.append(0.15)

    # RSI score (weight: 20%)
    rsi_data = result.get("rsi", {})
    if "rsi_score" in rsi_data:
        scores.append(rsi_data["rsi_score"])
        weights.append(0.20)

    # BIAS score (weight: 20%)
    bias_data = result.get("bias", {})
    if "bias_score" in bias_data:
        scores.append(bias_data["bias_score"])
        weights.append(0.20)

    # Trend score (weight: 25%)
    trend_data = result.get("trend", {})
    if "trend_score" in trend_data:
        scores.append(trend_data["trend_score"])
        weights.append(0.25)

    if scores and weights:
        total_w = sum(weights)
        composite = sum(s * w / total_w for s, w in zip(scores, weights)) if total_w > 0 else 0.0
        composite = max(-1.0, min(1.0, composite))

        if composite >= 0.4:
            label = "bullish"
        elif composite >= 0.15:
            label = "slightly_bullish"
        elif composite > -0.15:
            label = "neutral"
        elif composite > -0.4:
            label = "slightly_bearish"
        else:
            label = "bearish"

        result["composite"] = {
            "score": round(composite, 3),
            "signal": label,
            "weights_used": {
                k: round(v, 2) for k, v in zip(
                    ["patterns", "volume", "rsi", "bias", "trend"], weights
                )
            },
        }

    return result
