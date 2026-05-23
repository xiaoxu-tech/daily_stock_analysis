# -*- coding: utf-8 -*-
r"""Standalone crypto analysis entry point.

Usage:
    python run_crypto.py
    python run_crypto.py --mode signals-only --coins BTC,ETH

Bypasses the heavy data_provider import chain in main.py.
"""

import argparse
import logging
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("crypto-run")

parser = argparse.ArgumentParser(description="DSA Crypto Analysis Pipeline")
parser.add_argument("--mode", default="full", choices=["full", "news-only", "signals-only"])
parser.add_argument("--coins", default="BTC,ETH,SOL", help="Comma-separated coin symbols")
args = parser.parse_args()

coins = [c.strip().upper() for c in args.coins.split(",") if c.strip()]
logger.info("Mode: %s | Coins: %s", args.mode, coins)

try:
    from src.intel.crypto_notifier import run_crypto_pipeline

    result = run_crypto_pipeline(mode=args.mode, coins=coins)

    # Print summary
    signals = result.get("signals", {})
    news = result.get("news", {})
    notification = result.get("notification", {})

    if signals:
        print()
        print("=== SIGNALS ===")
        for coin, s in signals.items():
            if isinstance(s, dict) and "error" not in s:
                print(f"  {coin}: {s.get('signal_cn', s.get('signal'))}  ({s.get('composite', 0):+.2f})")

    if news:
        print()
        print("=== NEWS ===")
        print(f"  scraped={news.get('scraped_count', 0)}, deduped={news.get('deduped_count', 0)}, stored={news.get('stored_count', 0)}")

    if notification:
        print()
        print("=== NOTIFICATION ===")
        for ch in notification.get("channels", []):
            print(f"  {ch.get('channel')}: {'SENT' if ch.get('sent') else 'FAILED'}")

    print()
    print("Done.")

except Exception as e:
    logger.error("Crypto pipeline failed: %s", e, exc_info=True)
    sys.exit(1)
