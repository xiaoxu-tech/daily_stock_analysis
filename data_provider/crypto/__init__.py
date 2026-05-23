# -*- coding: utf-8 -*-
"""Crypto data providers.

- CoinpaprikaFetcher: OHLCV + ticker data from CoinPaprika (implements BaseFetcher)
- FearGreedClient: Fear & Greed Index from alternative.me
- DerivativesClient: Open interest, funding rates, liquidations from CoinGecko
- MacroClient: Macro indicators (DXY, VIX, Fed funds, CPI, etc.)
- OnchainClient: Blockchain metrics (hashrate, exchange flows, TVL, etc.)
"""

from .coinpaprika_fetcher import CoinpaprikaFetcher
from .fear_greed_fetcher import FearGreedClient
from .derivatives_fetcher import DerivativesClient
from .onchain_fetcher import OnchainClient
from .macro_fetcher import MacroClient

__all__ = [
    "CoinpaprikaFetcher",
    "FearGreedClient",
    "DerivativesClient",
    "OnchainClient",
    "MacroClient",
]
