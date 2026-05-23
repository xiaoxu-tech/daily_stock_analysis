# -*- coding: utf-8 -*-
"""Crypto signal package.

Contains:
- indicators: Technical indicators via `ta` library (RSI, MACD, BB, EMA, etc.)
- fusion: 6-factor weighted composite signal fusion engine
"""

from .indicators import TechnicalIndicators
from .fusion import SignalFusion, classify_signal, SIGNAL_CN

__all__ = [
    "TechnicalIndicators",
    "SignalFusion",
    "classify_signal",
    "SIGNAL_CN",
]
