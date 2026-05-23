# -*- coding: utf-8 -*-
"""Crypto coin-to-sector mapping loader.

Loads coin metadata (name, primary sector, sub-sectors, CoinPaprika ID)
from a YAML mapping file. Follows the same pattern as stock_index_loader.py.
"""

import logging
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

_sector_map: Optional[dict] = None


def _default_path() -> str:
    return str(Path(__file__).parent / "sectors" / "crypto_sector_map.yaml")


def load_sector_map(path: Optional[str] = None) -> dict:
    global _sector_map
    if _sector_map is not None:
        return _sector_map

    if path is None:
        path = _default_path()

    try:
        with open(path, encoding="utf-8") as f:
            _sector_map = yaml.safe_load(f) or {}
        logger.info("Loaded %d coin sector mappings", len(_sector_map))
    except FileNotFoundError:
        logger.warning("Crypto sector map not found: %s", path)
        _sector_map = {}
    except Exception as e:
        logger.error("Failed to load crypto sector map: %s", e)
        _sector_map = {}

    return _sector_map


def get_coin_info(symbol: str) -> Optional[dict]:
    sm = load_sector_map()
    return sm.get(symbol.upper())


def get_sector_coins(sector: str) -> list[dict]:
    sm = load_sector_map()
    result = []
    for symbol, info in sm.items():
        if info.get("primary_sector") == sector or sector in info.get("sub_sectors", []):
            result.append({"symbol": symbol, **info})
    return result


def get_all_sectors() -> list[str]:
    sm = load_sector_map()
    sectors: set[str] = set()
    for info in sm.values():
        if ps := info.get("primary_sector"):
            sectors.add(ps)
        sectors.update(info.get("sub_sectors", []))
    return sorted(sectors)


def get_paprika_id(symbol: str) -> Optional[str]:
    info = get_coin_info(symbol)
    return info.get("paprika_id") if info else None


def get_coin_name(symbol: str) -> Optional[str]:
    info = get_coin_info(symbol)
    return info.get("name") if info else None


def get_all_coins() -> list[str]:
    sm = load_sector_map()
    return sorted(sm.keys())


def is_known_crypto(symbol: str) -> bool:
    return symbol.upper() in load_sector_map()
