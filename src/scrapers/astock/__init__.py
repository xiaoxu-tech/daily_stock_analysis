# -*- coding: utf-8 -*-
"""A-share news scrapers package.

Contains 6 Chinese financial news scrapers:
    - WallStreetCNScraper  (API-based, 华尔街见闻)
    - EastMoneyScraper     (HTML-based, 东方财富)
    - STCNScraper          (HTML-based, 证券时报)
    - YicaiScraper         (HTML-based, 第一财经)
    - JiemianScraper       (HTML-based, 界面新闻)
    - YahooChinaScraper    (RSS-based,  Yahoo Finance China)
"""

from .wallstreetcn import WallStreetCNScraper
from .eastmoney_news import EastMoneyScraper
from .stcn import STCNScraper
from .yicai import YicaiScraper
from .jiemian import JiemianScraper
from .yahoo_rss import YahooChinaScraper

__all__ = [
    "WallStreetCNScraper",
    "EastMoneyScraper",
    "STCNScraper",
    "YicaiScraper",
    "JiemianScraper",
    "YahooChinaScraper",
]
