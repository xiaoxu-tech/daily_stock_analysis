# -*- coding: utf-8 -*-
"""LLM prompt templates package.

Contains structured prompts for:
- crypto_news_prompt: Batch news analysis, event analysis, market summary, coin deep-dive
- astock_news_prompt: A-share news analysis, market summary (Chinese)
"""

from .crypto_news_prompt import (
    ANALYSIS_PROMPT as CRYPTO_ANALYSIS_PROMPT,
    EVENT_ANALYSIS_PROMPT,
    SUMMARIZE_PROMPT as CRYPTO_SUMMARIZE_PROMPT,
    COIN_ANALYSIS_PROMPT,
)
from .astock_news_prompt import (
    ANALYSIS_PROMPT as ASTOCK_ANALYSIS_PROMPT,
    SUMMARIZE_PROMPT as ASTOCK_SUMMARIZE_PROMPT,
)

__all__ = [
    "CRYPTO_ANALYSIS_PROMPT",
    "EVENT_ANALYSIS_PROMPT",
    "CRYPTO_SUMMARIZE_PROMPT",
    "COIN_ANALYSIS_PROMPT",
    "ASTOCK_ANALYSIS_PROMPT",
    "ASTOCK_SUMMARIZE_PROMPT",
]
