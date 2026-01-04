#!/usr/bin/env python3
"""
Test script for Order Book Feed
Verifies WebSocket connections and imbalance calculations
"""

import asyncio
import time
import logging
from order_book_feed import OrderBookFeed

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_order_book_feed():
    """Test Order Book Feed with live data"""

    # Mock config
    config = {
        'strategy': {
            'symbols': ['BTC', 'ETH', 'SOL', 'XRP']
        },
        'order_book': {
            'smoothing_samples': 3,
            'order_book_depth': 3
        }
    }

    feed = OrderBookFeed(config)

    # Start WebSocket task (non-blocking)
    logger.info("🔌 Starting Order Book WebSocket connections...")
    ws_task = asyncio.create_task(feed.start())

    # Wait for connections to establish
    await asyncio.sleep(3)

    # Test data retrieval
    logger.info("\n" + "="*60)
    logger.info("📊 ORDER BOOK FEED TEST RESULTS")
    logger.info("="*60)

    for symbol in config['strategy']['symbols']:
        logger.info(f"\n{symbol} Order Book:")
        logger.info("-" * 40)

        stats = feed.get_order_book_stats(symbol)

        if stats:
            logger.info(f"  Micro-Price:     ${stats['micro_price']:,.2f}")
            logger.info(f"  Mid-Price:       ${stats['mid_price']:,.2f}")
            logger.info(f"  Best Bid:        ${stats['best_bid']:,.2f}")
            logger.info(f"  Best Ask:        ${stats['best_ask']:,.2f}")
            logger.info(f"  Spread:          {stats['spread_pct']:.3f}%")
            logger.info(f"  Imbalance:       {stats['imbalance']:.2%} {'📈 Bullish' if stats['imbalance'] > 0.6 else '📉 Bearish' if stats['imbalance'] < 0.4 else '⚖️  Neutral'}")
            logger.info(f"  Data Age:        {stats['data_age_ms']:.0f}ms")

            # Interpretation
            if 0.4 < stats['imbalance'] < 0.6:
                logger.info(f"  ⚠️  VETO: Neutral order book (no directional edge)")
            elif stats['imbalance'] > 0.6:
                logger.info(f"  ✅ PASS: Strong bullish pressure detected")
            else:
                logger.info(f"  ✅ PASS: Strong bearish pressure detected")
        else:
            logger.info("  ❌ No data available")

    # Status check
    logger.info("\n" + "="*60)
    logger.info("🔌 CONNECTION STATUS")
    logger.info("="*60)

    status = feed.get_status()
    for symbol, info in status.items():
        status_emoji = "✅" if info['connected'] and info['data_fresh'] else "❌"
        logger.info(f"{status_emoji} {symbol}: {'Connected' if info['connected'] else 'Disconnected'} "
                   f"(age: {info['age_ms']:.0f}ms)")

    # Run for 10 seconds to show live updates
    logger.info("\n📊 Monitoring imbalance for 10 seconds...")
    for i in range(10):
        await asyncio.sleep(1)
        btc_imbalance = feed.get_imbalance('BTC')
        if btc_imbalance:
            trend = "📈" if btc_imbalance > 0.6 else "📉" if btc_imbalance < 0.4 else "⚖️ "
            logger.info(f"  [{i+1}/10] BTC Imbalance: {btc_imbalance:.2%} {trend}")

    # Stop feed
    logger.info("\n🛑 Stopping Order Book Feed...")
    await feed.stop()
    ws_task.cancel()

    logger.info("✅ Test complete!")


if __name__ == "__main__":
    try:
        asyncio.run(test_order_book_feed())
    except KeyboardInterrupt:
        logger.info("\n⚠️  Test interrupted by user")
    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
