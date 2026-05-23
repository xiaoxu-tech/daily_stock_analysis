# -*- coding: utf-8 -*-
"""Crypto data providers.

- CoinpaprikaFetcher: OHLCV + ticker data from CoinPaprika (implements BaseFetcher)
- FearGreedClient: Fear & Greed Index from alternative.me
- DerivativesClient: Open interest, funding rates, liquidations from CoinGecko
- MacroClient: Macro indicators (DXY, VIX, Fed funds, CPI, etc.)
- OnchainClient: Blockchain metrics (hashrate, exchange flows, TVL, etc.)

Imports are lazy to avoid failing when optional crypto dependencies are missing.
"""

import logging

logger = logging.getLogger(__name__)


def _lazy_import(name: str, class_name: str):
    """Lazy import a single class from a submodule."""
    try:
        module = __import__(f"data_provider.crypto.{name}", fromlist=[class_name])
        return getattr(module, class_name)
    except ImportError as e:
        logger.debug("Crypto fetcher %s unavailable: %s", class_name, e)
        return None


def _get_fetcher(attr_name: str, module_name: str, class_name: str):
    """Lazy singleton for a crypto fetcher class."""
    cache = getattr(_get_fetcher, "_cache", None)
    if cache is None:
        cache = {}
        setattr(_get_fetcher, "_cache", cache)

    if attr_name not in cache:
        cls = _lazy_import(module_name, class_name)
        cache[attr_name] = cls

    return cache[attr_name]


# Public API — modules that import `from data_provider.crypto import X`
# get a class (or None if the dependency is missing).

def __getattr__(name: str):
    _map = {
        "CoinpaprikaFetcher": ("coinpaprika_fetcher", "CoinpaprikaFetcher"),
        "FearGreedClient": ("fear_greed_fetcher", "FearGreedClient"),
        "DerivativesClient": ("derivatives_fetcher", "DerivativesClient"),
        "OnchainClient": ("onchain_fetcher", "OnchainClient"),
        "MacroClient": ("macro_fetcher", "MacroClient"),
    }
    if name in _map:
        mod, cls = _map[name]
        return _get_fetcher(name, mod, cls)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "CoinpaprikaFetcher",
    "FearGreedClient",
    "DerivativesClient",
    "OnchainClient",
    "MacroClient",
]
