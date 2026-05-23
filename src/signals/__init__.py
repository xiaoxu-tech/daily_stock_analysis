# -*- coding: utf-8 -*-
"""Signal computation layer.

Contains:
- base: Abstract signal classes and SignalResult
- crypto/: Technical indicators + 6-factor fusion engine
- capital_flow_signal: Capital flow → sentiment signal for A-shares
"""

from .base import BaseSignal, SignalResult
from .crypto import SignalFusion, TechnicalIndicators, classify_signal, SIGNAL_CN
from .capital_flow_signal import CapitalFlowSignal

__all__ = [
    "BaseSignal",
    "SignalResult",
    "SignalFusion",
    "TechnicalIndicators",
    "CapitalFlowSignal",
    "classify_signal",
    "SIGNAL_CN",
]
