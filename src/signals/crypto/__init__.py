# -*- coding: utf-8 -*-
"""Crypto signal package.

Contains:
- indicators: Technical indicators via `ta` library (RSI, MACD, BB, EMA, etc.)
- enhanced_indicators: DSA-derived patterns, volume analysis, multi-RSI, BIAS, trend
- fusion: 6-factor weighted composite signal fusion engine
"""

from .indicators import TechnicalIndicators
from .enhanced_indicators import (
    CandlestickPatterns,
    VolumeAnalyzer,
    MultiPeriodRSI,
    BIASAnalyzer,
    TrendClassifier,
    compute_enhanced_indicators,
)
from .fusion import SignalFusion, classify_signal, SIGNAL_CN

__all__ = [
    "TechnicalIndicators",
    "CandlestickPatterns",
    "VolumeAnalyzer",
    "MultiPeriodRSI",
    "BIASAnalyzer",
    "TrendClassifier",
    "compute_enhanced_indicators",
    "SignalFusion",
    "classify_signal",
    "SIGNAL_CN",
]
