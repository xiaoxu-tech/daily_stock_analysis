# -*- coding: utf-8 -*-
"""Technical indicators for crypto price data.

Uses the `ta` library (pure Python technical analysis) to compute:
RSI, Stochastic, MACD, EMA, Bollinger Bands, ATR, VWAP.
"""

from __future__ import annotations

import logging
from typing import Optional, Dict, Any

import pandas as pd
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import MACD, EMAIndicator, ADXIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from ta.volume import VolumeWeightedAveragePrice

logger = logging.getLogger(__name__)


class TechnicalIndicators:
    """Calculate common technical indicators from OHLCV price data.

    Usage:
        ti = TechnicalIndicators(df)
        ti.compute_all()
        signals = ti.get_latest_signals()
    """

    def __init__(self, df: pd.DataFrame):
        """Initialize with OHLCV DataFrame.

        Args:
            df: DataFrame with columns: timestamp, close
                Optional: open, high, low, volume
        """
        self.df = df.copy()
        self.df["close"] = pd.to_numeric(self.df["close"], errors="coerce")
        if "high" in self.df.columns:
            self.df["high"] = pd.to_numeric(self.df["high"], errors="coerce")
        if "low" in self.df.columns:
            self.df["low"] = pd.to_numeric(self.df["low"], errors="coerce")
        if "volume" in self.df.columns:
            self.df["volume"] = pd.to_numeric(self.df["volume"], errors="coerce")

    def compute_all(self) -> pd.DataFrame:
        """Compute all indicators and add them as columns to the DataFrame."""
        close = self.df["close"].dropna()
        if len(close) < 14:
            logger.debug("Not enough data for indicators (need >=14, got %d)", len(close))
            return self.df

        try:
            # -- Momentum --
            rsi = RSIIndicator(close=close, window=14)
            self.df["rsi"] = rsi.rsi()

            stoch = StochasticOscillator(
                high=self.df["high"] if "high" in self.df else close,
                low=self.df["low"] if "low" in self.df else close,
                close=close, window=14, smooth_window=3,
            )
            self.df["stoch_k"] = stoch.stoch()
            self.df["stoch_d"] = stoch.stoch_signal()

            # -- Trend --
            macd = MACD(close=close, window_slow=26, window_fast=12, window_sign=9)
            self.df["macd"] = macd.macd()
            self.df["macd_signal_line"] = macd.macd_signal()
            self.df["macd_diff"] = macd.macd_diff()

            ema12 = EMAIndicator(close=close, window=12)
            ema26 = EMAIndicator(close=close, window=26)
            self.df["ema_12"] = ema12.ema_indicator()
            self.df["ema_26"] = ema26.ema_indicator()

            # -- Volatility --
            bb = BollingerBands(close=close, window=20, window_dev=2)
            self.df["bb_upper"] = bb.bollinger_hband()
            self.df["bb_middle"] = bb.bollinger_mavg()
            self.df["bb_lower"] = bb.bollinger_lband()
            self.df["bb_width"] = (
                (self.df["bb_upper"] - self.df["bb_lower"]) / self.df["bb_middle"]
            )

            if "high" in self.df and "low" in self.df:
                atr = AverageTrueRange(
                    high=self.df["high"], low=self.df["low"], close=close, window=14,
                )
                self.df["atr"] = atr.average_true_range()

            # -- Volume --
            if "high" in self.df and "low" in self.df and "volume" in self.df:
                vwap = VolumeWeightedAveragePrice(
                    high=self.df["high"], low=self.df["low"], close=close,
                    volume=self.df["volume"], window=14,
                )
                self.df["vwap"] = vwap.volume_weighted_average_price()

        except Exception as e:
            logger.warning("Indicator calculation failed: %s", e)

        return self.df

    def get_latest_signals(self) -> Dict[str, Any]:
        """Extract the latest indicator values as a dict for signal fusion."""
        if self.df.empty:
            return {}

        latest = self.df.iloc[-1]
        signals: Dict[str, Any] = {}

        # RSI
        rsi_val = latest.get("rsi")
        if rsi_val is not None and not pd.isna(rsi_val):
            signals["rsi"] = float(rsi_val)
            if rsi_val > 70:
                signals["rsi_signal"] = "overbought"
            elif rsi_val < 30:
                signals["rsi_signal"] = "oversold"
            else:
                signals["rsi_signal"] = "neutral"

        # MACD
        macd_val = latest.get("macd")
        macd_sig = latest.get("macd_signal_line")
        macd_diff = latest.get("macd_diff")
        if all(v is not None and not pd.isna(v) for v in [macd_val, macd_sig, macd_diff]):
            signals["macd"] = float(macd_val)
            signals["macd_signal_line"] = float(macd_sig)
            signals["macd_histogram"] = float(macd_diff)

            prev_diff = None
            if len(self.df) > 1:
                prev = self.df.iloc[-2].get("macd_diff")
                if prev is not None and not pd.isna(prev):
                    prev_diff = prev

            if prev_diff is not None:
                if macd_diff > 0 and prev_diff <= 0:
                    signals["macd_signal"] = "bullish_cross"
                elif macd_diff < 0 and prev_diff >= 0:
                    signals["macd_signal"] = "bearish_cross"
                elif macd_diff > 0:
                    signals["macd_signal"] = "bullish"
                else:
                    signals["macd_signal"] = "bearish"
            else:
                signals["macd_signal"] = "bullish" if macd_diff > 0 else "bearish"

        # Bollinger Bands
        bb_upper = latest.get("bb_upper")
        bb_lower = latest.get("bb_lower")
        close_val = latest.get("close")
        if all(v is not None and not pd.isna(v) for v in [bb_upper, bb_lower, close_val]):
            signals["bb_position"] = float(
                (close_val - bb_lower) / (bb_upper - bb_lower)
                if (bb_upper - bb_lower) != 0 else 0.5
            )
            if close_val > bb_upper:
                signals["bb_signal"] = "above_band"
            elif close_val < bb_lower:
                signals["bb_signal"] = "below_band"
            else:
                signals["bb_signal"] = "inside"

        # EMA trend
        ema12 = latest.get("ema_12")
        ema26 = latest.get("ema_26")
        if all(v is not None and not pd.isna(v) for v in [ema12, ema26]):
            signals["ema_trend"] = "bullish" if ema12 > ema26 else "bearish"

        return signals
