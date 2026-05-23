# -*- coding: utf-8 -*-
"""
===================================
新闻抓取层 - 包初始化
===================================

本包实现多源新闻抓取，支持：
1. 加密货币 RSS 抓取（9 个来源）
2. A 股新闻抓取（6 个来源）
3. 资金流向数据抓取（东方财富）

统一数据模型 + 模糊去重 + 工厂模式创建
"""

from .base import BaseScraper
from .models import (
    NewsItem,
    NewsSource,
    NewsItemCreate,
    extract_news_source_value,
)
from .dedup import deduplicate

__all__ = [
    'BaseScraper',
    'NewsItem',
    'NewsItemCreate',
    'NewsSource',
    'extract_news_source_value',
    'deduplicate',
]
