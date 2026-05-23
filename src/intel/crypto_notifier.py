# -*- coding: utf-8 -*-
"""Crypto notification orchestrator.

Wires the crypto news ingestion + signal engine pipelines into DSA's
existing notification infrastructure (FeishuSender, etc.).

Usage:
  from src.intel.crypto_notifier import CryptoNotifier
  notifier = CryptoNotifier()
  notifier.run(coins=['BTC', 'ETH', 'SOL'])
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

from src.config import get_config, Config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Report formatting helpers
# ---------------------------------------------------------------------------

SIGNAL_EMOJI: Dict[str, str] = {
    "strong_buy": "🟢",
    "buy": "🟢",
    "neutral": "🟡",
    "sell": "🔴",
    "strong_sell": "🔴",
}


def _format_signal_summary(signals: Dict[str, Dict[str, Any]]) -> str:
    """Format crypto signal results into a Feishu-friendly message block."""
    if not signals or signals.get("error"):
        return ""

    lines = ["📊 **综合信号**"]
    for coin, sig in signals.items():
        if isinstance(sig, dict) and "error" not in sig:
            emoji = SIGNAL_EMOJI.get(sig.get("signal", ""), "⚪")
            composite = sig.get("composite", 0)
            signal_cn = sig.get("signal_cn", sig.get("signal", "N/A"))
            lines.append(f"  {emoji} {coin}: {signal_cn}  ({composite:+.2f})")

            # Component breakdown if available
            components = sig.get("components", {})
            if components:
                comp_parts = []
                for name, comp in components.items():
                    if isinstance(comp, dict):
                        score = comp.get("score", 0)
                        comp_parts.append(f"{name}:{score:+.2f}")
                if comp_parts:
                    lines.append(f"      {' | '.join(comp_parts)}")

    return "\n".join(lines)


def _format_news_summary(news_result: Dict[str, Any]) -> str:
    """Format news pipeline results."""
    if not news_result or news_result.get("error"):
        return ""

    lines = ["📰 **新闻抓取**"]
    lines.append(
        f"  原始: {news_result.get('scraped_count', 0)} 条 → "
        f"去重: {news_result.get('deduped_count', 0)} 条 → "
        f"入库: {news_result.get('stored_count', 0)} 条"
    )
    return "\n".join(lines)


def _format_market_summary(summary: Optional[str]) -> str:
    """Wrap LLM-generated market summary."""
    if not summary:
        return ""
    return f"📝 **市场摘要**\n{summary}"


def build_crypto_report(
    signals: Optional[Dict[str, Dict[str, Any]]] = None,
    news: Optional[Dict[str, Any]] = None,
    summary: Optional[str] = None,
    footer: str = "⚡ 由 DSA Crypto Pipeline 自动生成",
) -> str:
    """Build a complete crypto analysis report for notification.

    Args:
        signals: Dict of coin→signal_result from SignalFusion.
        news: Pipeline result dict from CryptoIngestor.run().
        summary: Optional LLM-generated market summary text.
        footer: Footer text.

    Returns:
        Formatted markdown string ready for Feishu/Telegram/etc.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    blocks = [f"**【加密货币分析报告】**", f"时间: {now}", ""]

    if signals:
        blocks.append(_format_signal_summary(signals))
        blocks.append("")

    if news:
        blocks.append(_format_news_summary(news))
        blocks.append("")

    if summary:
        blocks.append(_format_market_summary(summary))
        blocks.append("")

    blocks.append(footer)
    return "\n".join(blocks)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class CryptoNotifier:
    """Run crypto analysis pipelines and send results via configured channels."""

    def __init__(self, config: Optional[Config] = None):
        self._config = config or get_config()

    # ── Public API ──

    def run(
        self,
        coins: Optional[List[str]] = None,
        *,
        scrape_news: bool = True,
        compute_signals: bool = True,
        send_notification: bool = True,
    ) -> Dict[str, Any]:
        """Run the full crypto analysis → notification pipeline.

        Args:
            coins: List of coin symbols (e.g., ['BTC', 'ETH']).
                   Defaults to config.crypto_coins or ['BTC', 'ETH', 'SOL'].
            scrape_news: Whether to run the news scraping pipeline.
            compute_signals: Whether to compute composite signals.
            send_notification: Whether to send results to notification channels.

        Returns:
            Dict with keys: signals, news, summary, notification.
        """
        coins = coins or self._resolve_coins()
        results: Dict[str, Any] = {}

        if compute_signals:
            results["signals"] = self._run_signals(coins)

        if scrape_news:
            results["news"] = self._run_news_pipeline()

        if send_notification:
            results["notification"] = self._send_report(results)

        return results

    def run_signals_only(self, coins: Optional[List[str]] = None) -> Dict[str, Any]:
        """Compute signals only, return results without sending notifications."""
        return self.run(coins=coins, scrape_news=False, send_notification=False)

    def run_news_only(self) -> Dict[str, Any]:
        """Scrape news only, return results without sending notifications."""
        return self.run(scrape_news=True, compute_signals=False, send_notification=False)

    # ── Internal ──

    def _resolve_coins(self) -> List[str]:
        configured = getattr(self._config, 'crypto_coins', None)
        if configured:
            if isinstance(configured, str):
                return [c.strip().upper() for c in configured.split(",") if c.strip()]
            return list(configured)
        return ["BTC", "ETH", "SOL"]

    def _run_signals(self, coins: List[str]) -> Dict[str, Dict[str, Any]]:
        """Run signal fusion for each coin."""
        logger.info("Computing crypto signals for: %s", coins)
        signal_results: Dict[str, Dict[str, Any]] = {}
        try:
            from src.signals.crypto.fusion import SignalFusion

            sf = SignalFusion()
            for coin in coins:
                try:
                    sig = sf.get_composite_signal(coin)
                    signal_results[coin] = {
                        "signal": sig.get("signal"),
                        "signal_cn": sig.get("signalCn"),
                        "composite": sig.get("composite", 0),
                        "components": sig.get("components", {}),
                    }
                    logger.info(
                        "%s: signal=%s composite=%.2f",
                        coin,
                        sig.get("signal"),
                        sig.get("composite", 0),
                    )
                except Exception as e:
                    logger.error("Signal failed for %s: %s", coin, e)
                    signal_results[coin] = {"error": str(e)}
        except Exception as e:
            logger.error("Signal engine init failed: %s", e, exc_info=True)
            signal_results["error"] = str(e)
        return signal_results

    def _run_news_pipeline(self) -> Dict[str, Any]:
        """Run the crypto news ingestion pipeline."""
        logger.info("Running crypto news pipeline")
        try:
            from src.intel.crypto_ingestor import CryptoIngestor
            from src.storage import get_db

            db = get_db()
            ingestor = CryptoIngestor(
                db_manager=db,
                max_per_source=10,
                dedup_threshold=0.75,
            )
            result = ingestor.run(summarize=True)
            logger.info(
                "News pipeline: scraped=%d deduped=%d stored=%d",
                result.get("scraped_count", 0),
                result.get("deduped_count", 0),
                result.get("stored_count", 0),
            )
            return result
        except Exception as e:
            logger.error("News pipeline failed: %s", e, exc_info=True)
            return {"error": str(e)}

    def _send_report(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Send analysis report through configured notification channels."""
        notification_result: Dict[str, Any] = {"channels": []}

        signals = results.get("signals", {})
        news = results.get("news", {})
        summary = news.get("summary") if isinstance(news, dict) else None

        report = build_crypto_report(
            signals=signals,
            news=news,
            summary=summary,
        )

        # ── Feishu ──
        feishu_url = getattr(self._config, "feishu_webhook_url", None)
        if feishu_url:
            try:
                from src.notification_sender.feishu_sender import FeishuSender

                sender = FeishuSender(self._config)
                sent = sender.send_to_feishu(report)
                notification_result["channels"].append({"channel": "feishu", "sent": sent})
                logger.info("Feishu notification: %s", "sent" if sent else "failed")
            except Exception as e:
                logger.error("Feishu notification failed: %s", e, exc_info=True)
                notification_result["channels"].append({"channel": "feishu", "error": str(e)})

        return notification_result


# ---------------------------------------------------------------------------
# CLI entry point (used by main.py --crypto)
# ---------------------------------------------------------------------------

def run_crypto_pipeline(
    mode: str = "full",
    coins: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """CLI-friendly wrapper around CryptoNotifier.

    Args:
        mode: 'full', 'news-only', or 'signals-only'.
        coins: Coin symbols.

    Returns:
        Pipeline results dict.
    """
    cfg = get_config()
    notifier = CryptoNotifier(cfg)

    if mode == "news-only":
        return notifier.run_news_only()
    elif mode == "signals-only":
        return notifier.run_signals_only(coins=coins)
    else:
        return notifier.run(coins=coins)
