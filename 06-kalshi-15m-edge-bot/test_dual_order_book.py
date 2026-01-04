#!/usr/bin/env python3
"""
Test script for Dual-Source Order Book Feed
Tests Binance + Coinbase connections and cross-validation
"""

import asyncio
import logging
from order_book_feed_dual import DualSourceOrderBookFeed

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_dual_feed():
    """Test dual-source order book feed"""

    # Mock config
    config = {
        'strategy': {
            'symbols': ['BTC', 'ETH', 'SOL']  # Test 3 symbols
        },
        'order_book': {
            'smoothing_samples': 3,
            'order_book_depth': 3
        }
    }

    feed = DualSourceOrderBookFeed(config)

    logger.info("🔌 Starting Dual-Source Order Book Feed...")
    ws_task = asyncio.create_task(feed.start())

    # Wait for connections
    await asyncio.sleep(5)

    # Test data retrieval
    logger.info("\n" + "="*70)
    logger.info("📊 DUAL-SOURCE ORDER BOOK TEST RESULTS")
    logger.info("="*70)

    for symbol in config['strategy']['symbols']:
        logger.info(f"\n{symbol} Order Book (Dual-Source):")
        logger.info("-" * 70)

        stats = feed.get_order_book_stats(symbol)

        if stats:
            logger.info(f"  Sources Available: {', '.join(stats['sources_available'])}")

            # Per-exchange imbalances
            if stats['imbalance_binance'] is not None:
                trend = "📈" if stats['imbalance_binance'] > 0.6 else "📉" if stats['imbalance_binance'] < 0.4 else "⚖️"
                logger.info(f"  Binance Imbalance:  {stats['imbalance_binance']:.2%} {trend} "
                           f"(age: {stats['data_age_ms'].get('binance', 0):.0f}ms)")

            if stats['imbalance_coinbase'] is not None:
                trend = "📈" if stats['imbalance_coinbase'] > 0.6 else "📉" if stats['imbalance_coinbase'] < 0.4 else "⚖️"
                logger.info(f"  Coinbase Imbalance: {stats['imbalance_coinbase']:.2%} {trend} "
                           f"(age: {stats['data_age_ms'].get('coinbase', 0):.0f}ms)")

            # Aggregated imbalance
            if stats['imbalance_aggregated'] is not None:
                trend = "📈" if stats['imbalance_aggregated'] > 0.6 else "📉" if stats['imbalance_aggregated'] < 0.4 else "⚖️"
                logger.info(f"  AGGREGATED:         {stats['imbalance_aggregated']:.2%} {trend}")

            # Divergence check
            if stats['divergence'] is not None:
                if stats['divergence'] > 0.20:
                    logger.info(f"  ⚠️  DIVERGENCE:      {stats['divergence']:.2%} (HIGH - exchanges disagree!)")
                else:
                    logger.info(f"  ✅ Divergence:       {stats['divergence']:.2%} (Low - exchanges agree)")

            # Trading decision
            logger.info("")
            if stats['divergence'] and stats['divergence'] > 0.20:
                logger.info(f"  🚫 VETO: High divergence - market uncertainty")
            elif 0.4 < stats['imbalance_aggregated'] < 0.6:
                logger.info(f"  🚫 VETO: Neutral imbalance - no clear direction")
            elif stats['imbalance_aggregated'] > 0.6:
                logger.info(f"  ✅ PASS: Strong bullish pressure detected")
            elif stats['imbalance_aggregated'] < 0.4:
                logger.info(f"  ✅ PASS: Strong bearish pressure detected")
        else:
            logger.info("  ❌ No data available")

    # Connection status
    logger.info("\n" + "="*70)
    logger.info("🔌 CONNECTION STATUS")
    logger.info("="*70)

    status = feed.get_status()
    for symbol, exchanges in status.items():
        logger.info(f"\n{symbol}:")
        for exchange, info in exchanges.items():
            emoji = "✅" if info['connected'] and info['data_fresh'] else "❌"
            logger.info(f"  {emoji} {exchange.capitalize()}: "
                       f"{'Connected' if info['connected'] else 'Disconnected'} "
                       f"(age: {info['age_ms']:.0f}ms)")

    # Monitor for 15 seconds
    logger.info("\n📊 Live monitoring for 15 seconds...")
    for i in range(15):
        await asyncio.sleep(1)

        btc_stats = feed.get_order_book_stats('BTC')
        if btc_stats and btc_stats['imbalance_aggregated']:
            imb = btc_stats['imbalance_aggregated']
            div = btc_stats['divergence'] or 0
            trend = "📈" if imb > 0.6 else "📉" if imb < 0.4 else "⚖️"

            logger.info(f"  [{i+1}/15] BTC: {imb:.2%} {trend} | "
                       f"Divergence: {div:.2%} | "
                       f"Sources: {len(btc_stats['sources_available'])}")

    # Stop feed
    logger.info("\n🛑 Stopping Order Book Feed...")
    await feed.stop()
    ws_task.cancel()

    logger.info("✅ Test complete!")


if __name__ == "__main__":
    try:
        asyncio.run(test_dual_feed())
    except KeyboardInterrupt:
        logger.info("\n⚠️  Test interrupted by user")
    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
