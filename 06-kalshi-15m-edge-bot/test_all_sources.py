#!/usr/bin/env python3
"""
Test all 3 sources individually to see what's working
"""
import asyncio
import logging
from order_book_feed import OrderBookFeed

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

async def test():
    config = {
        'strategy': {'symbols': ['BTC']},
        'order_book': {'smoothing_samples': 1}
    }

    feed = OrderBookFeed(config)
    asyncio.create_task(feed.start())
    
    logger.info("Waiting 8 seconds for all sources to connect and send data...")
    await asyncio.sleep(8)
    
    logger.info("\n" + "="*60)
    logger.info("CHECKING DATA RECEIVED FROM EACH EXCHANGE")
    logger.info("="*60)
    
    if 'BTC' in feed.order_books:
        for exchange in ['binance', 'kraken', 'coinbase']:
            if exchange in feed.order_books['BTC']:
                ob = feed.order_books['BTC'][exchange]
                age = (asyncio.get_event_loop().time() - ob['timestamp']) * 1000
                bids_count = len(ob['bids'])
                asks_count = len(ob['asks'])
                
                logger.info(f"\n{exchange.upper()}:")
                logger.info(f"  ✅ Data received!")
                logger.info(f"  Bids: {bids_count}, Asks: {asks_count}")
                logger.info(f"  Age: {age:.0f}ms")
                if bids_count > 0 and asks_count > 0:
                    logger.info(f"  Best Bid: ${ob['bids'][0][0]:,.2f}")
                    logger.info(f"  Best Ask: ${ob['asks'][0][0]:,.2f}")
            else:
                logger.info(f"\n{exchange.upper()}:")
                logger.info(f"  ❌ No data received (connection issue or parsing problem)")
    else:
        logger.info("❌ No BTC data at all!")
    
    await feed.stop()

asyncio.run(test())
