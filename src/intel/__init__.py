# -*- coding: utf-8 -*-
"""Intelligence ingestion orchestrators.

Each ingestor wraps the full pipeline for a specific data domain:
    scrape → dedup → store → analyze → summarize
"""

from .crypto_ingestor import CryptoIngestor
from .astock_ingestor import AstockIngestor
from .capital_flow_ingestor import CapitalFlowIngestor

__all__ = [
    "CryptoIngestor",
    "AstockIngestor",
    "CapitalFlowIngestor",
]
