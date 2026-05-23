# -*- coding: utf-8 -*-
"""Abstract base classes for signal computation.

Defines the interface that all signal generators must implement.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class SignalResult:
    """Unified signal output from any signal generator.

    Attributes:
        asset_code: Stock or crypto code (e.g., 'BTC', '600519')
        asset_type: 'crypto', 'stock', or 'index'
        composite_score: Final score from -1.0 (strong sell) to +1.0 (strong buy)
        signal_label: Human-readable label (strong_buy/buy/neutral/sell/strong_sell)
        components: Dict of sub-signal scores (e.g. {'sentiment': 0.5, 'technical': -0.2})
        weights: Dict of weights applied to each component
        metadata: Arbitrary extra info (timestamps, source data, etc.)
    """
    asset_code: str
    asset_type: str = "crypto"
    composite_score: float = 0.0
    signal_label: str = "neutral"
    components: Dict[str, Any] = field(default_factory=dict)
    weights: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_code": self.asset_code,
            "asset_type": self.asset_type,
            "composite_score": self.composite_score,
            "signal_label": self.signal_label,
            "components": self.components,
            "weights": self.weights,
            "metadata": self.metadata,
        }


class BaseSignal(ABC):
    """Abstract signal generator.

    Subclasses implement `compute()` which returns a SignalResult.
    """

    @abstractmethod
    def compute(self, asset_code: str, **kwargs) -> SignalResult:
        """Compute the signal for a given asset."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of this signal generator."""
        ...
