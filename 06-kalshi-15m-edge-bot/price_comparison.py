"""
Price Source Comparison: CF Benchmarks REST vs CEX WebSocket mid-prices

Runs both sources in parallel for a configurable duration and shows:
- CF Benchmarks REST (median of Coinbase/Binance/Kraken) — what the bot currently uses
- CEX WebSocket mid-price ((best_bid + best_ask) / 2) from each exchange
- Spread between REST and WS mid
- Statistics at the end

Usage:
    python price_comparison.py [duration_seconds] [symbol]
    python price_comparison.py 120 BTC
    python price_comparison.py 60 ETH

Kalshi settles using CF Benchmarks RTI, so we're checking whether our REST-polled
median already matches the WS mid-price closely enough, or whether switching to WS
would meaningfully change the price we see.
"""

import asyncio
import json
import logging
import sys
import time
from collections import defaultdict
from statistics import mean, stdev
from typing import Dict, List, Optional

import aiohttp

try:
    import websockets
except ImportError:
    print("❌ Install websockets: pip install websockets")
    sys.exit(1)

logging.basicConfig(
    level=logging.WARNING,  # suppress noisy WS logs
    format='%(asctime)s %(name)s %(levelname)s %(message)s'
)
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
DURATION   = int(sys.argv[1]) if len(sys.argv) > 1 else 120
SYMBOL     = (sys.argv[2] if len(sys.argv) > 2 else 'BTC').upper()
INTERVAL   = 2.0   # seconds between samples

# ── Shared state ──────────────────────────────────────────────────────────────
ws_books: Dict[str, Dict] = {}   # exchange -> {bids, asks, ts}
samples: List[Dict] = []
stop_event = asyncio.Event()


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket feeds (mirrors order_book_feed.py, simplified)
# ─────────────────────────────────────────────────────────────────────────────

def _mid(bids, asks) -> Optional[float]:
    if bids and asks:
        return (float(bids[0][0]) + float(asks[0][0])) / 2
    return None


async def _feed_binance(symbol: str):
    ws_sym = f"{symbol}USDT".lower()
    url = f"wss://stream.binance.com:9443/ws/{ws_sym}@depth20@100ms"
    while not stop_event.is_set():
        try:
            async with websockets.connect(url) as ws:
                async for raw in ws:
                    if stop_event.is_set():
                        return
                    data = json.loads(raw)
                    bids = [[float(p), float(q)] for p, q in data.get('bids', [])]
                    asks = [[float(p), float(q)] for p, q in data.get('asks', [])]
                    ws_books['binance'] = {'bids': bids, 'asks': asks, 'ts': time.time()}
        except Exception:
            if not stop_event.is_set():
                await asyncio.sleep(2)


async def _feed_kraken(symbol: str):
    kraken_map = {'BTC': 'XBT/USD', 'ETH': 'ETH/USD', 'SOL': 'SOL/USD', 'XRP': 'XRP/USD'}
    ws_sym = kraken_map.get(symbol, f"{symbol}/USD")
    url = "wss://ws.kraken.com/"
    sub = {"event": "subscribe", "pair": [ws_sym], "subscription": {"name": "book", "depth": 10}}
    while not stop_event.is_set():
        try:
            async with websockets.connect(url) as ws:
                await ws.send(json.dumps(sub))
                async for raw in ws:
                    if stop_event.is_set():
                        return
                    data = json.loads(raw)
                    if isinstance(data, list) and len(data) >= 2 and isinstance(data[1], dict):
                        book = data[1]
                        bids = [[float(p), float(q)] for p, q, _ in book.get('bs', book.get('b', []))]
                        asks = [[float(p), float(q)] for p, q, _ in book.get('as', book.get('a', []))]
                        if bids or asks:
                            ws_books['kraken'] = {'bids': bids, 'asks': asks, 'ts': time.time()}
        except Exception:
            if not stop_event.is_set():
                await asyncio.sleep(2)


async def _feed_coinbase(symbol: str):
    if symbol == 'XRP':
        return  # no XRP on Coinbase Advanced Trade
    ws_sym = f"{symbol}-USD"
    url = "wss://advanced-trade-ws.coinbase.com"
    sub = {"type": "subscribe", "product_ids": [ws_sym], "channel": "level2"}

    # Maintain local OB for incremental updates
    bids_dict: Dict[float, float] = {}
    asks_dict: Dict[float, float] = {}

    while not stop_event.is_set():
        bids_dict.clear()
        asks_dict.clear()
        try:
            async with websockets.connect(url, max_size=10 * 1024 * 1024) as ws:
                await ws.send(json.dumps(sub))
                async for raw in ws:
                    if stop_event.is_set():
                        return
                    data = json.loads(raw)
                    if data.get('channel') != 'l2_data':
                        continue
                    for event in data.get('events', []):
                        etype = event.get('type')
                        if etype == 'snapshot':
                            bids_dict.clear(); asks_dict.clear()
                        for upd in event.get('updates', []):
                            side  = upd.get('side')
                            price = float(upd.get('price_level', 0))
                            qty   = float(upd.get('new_quantity', 0))
                            d = bids_dict if side == 'bid' else asks_dict
                            if qty == 0:
                                d.pop(price, None)
                            else:
                                d[price] = qty
                    bids = sorted([[p, q] for p, q in bids_dict.items()], key=lambda x: -x[0])[:5]
                    asks = sorted([[p, q] for p, q in asks_dict.items()], key=lambda x:  x[0])[:5]
                    if bids or asks:
                        ws_books['coinbase'] = {'bids': bids, 'asks': asks, 'ts': time.time()}
        except Exception:
            if not stop_event.is_set():
                await asyncio.sleep(2)


# ─────────────────────────────────────────────────────────────────────────────
# CF Benchmarks REST fetch (mirrors spot_price_feed.py)
# ─────────────────────────────────────────────────────────────────────────────

async def _fetch_rest_prices(symbol: str, session: aiohttp.ClientSession) -> Dict[str, Optional[float]]:
    """Fetch spot price from Coinbase, Binance, Kraken REST concurrently."""
    k_pair = {'BTC': 'XXBTZUSD', 'ETH': 'XETHZUSD', 'XRP': 'XXRPZUSD'}.get(symbol, f"{symbol}USD")
    urls = {
        'coinbase': f"https://api.coinbase.com/v2/prices/{symbol}-USD/spot",
        'binance':  f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}USDT",
        'kraken':   f"https://api.kraken.com/0/public/Ticker?pair={k_pair}",
    }

    async def _get(name, url):
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=3)) as r:
                if r.status != 200:
                    return name, None
                data = await r.json()
                if name == 'coinbase':
                    return name, float(data['data']['amount'])
                elif name == 'binance':
                    return name, float(data['price'])
                elif name == 'kraken':
                    res = data.get('result', {})
                    key = next(iter(res)) if res else None
                    return name, float(res[key]['c'][0]) if key else None
        except Exception:
            return name, None

    results = await asyncio.gather(*[_get(n, u) for n, u in urls.items()])
    return dict(results)


def _median(values: List[float]) -> Optional[float]:
    vals = sorted(v for v in values if v is not None)
    n = len(vals)
    if n == 0:
        return None
    return vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2


# ─────────────────────────────────────────────────────────────────────────────
# Sampling loop
# ─────────────────────────────────────────────────────────────────────────────

async def _sampler(symbol: str):
    """Every INTERVAL seconds, record REST prices and WS mid-prices."""
    print(f"\n{'─'*78}")
    print(f"  Price Comparison: {symbol}  |  CF Benchmarks REST  vs  CEX WebSocket mid")
    print(f"  Duration: {DURATION}s   Sample interval: {INTERVAL}s")
    print(f"{'─'*78}")
    hdr = (f"{'Time':8s}  {'REST_med':>10s}  "
           f"{'WS_BN':>10s}  {'WS_KK':>10s}  {'WS_CB':>10s}  "
           f"{'WS_avg':>10s}  {'Diff':>8s}  {'Diff%':>7s}")
    print(hdr)
    print('─' * 78)

    start = time.time()
    async with aiohttp.ClientSession() as session:
        while not stop_event.is_set():
            t0 = time.time()

            # REST fetch
            rest_px = await _fetch_rest_prices(symbol, session)
            rest_med = _median(list(rest_px.values()))

            # WS mid-prices (from already-streaming ws_books)
            ws_mids: Dict[str, Optional[float]] = {}
            for exch in ('binance', 'kraken', 'coinbase'):
                book = ws_books.get(exch)
                if book and (time.time() - book['ts']) < 5:
                    ws_mids[exch] = _mid(book['bids'], book['asks'])
                else:
                    ws_mids[exch] = None

            ws_values = [v for v in ws_mids.values() if v is not None]
            ws_avg = mean(ws_values) if ws_values else None

            elapsed = time.time() - start
            diff     = (ws_avg - rest_med) if (ws_avg and rest_med) else None
            diff_pct = (diff / rest_med * 100) if (diff is not None and rest_med) else None

            row = {
                'elapsed': elapsed,
                'rest_coinbase': rest_px.get('coinbase'),
                'rest_binance':  rest_px.get('binance'),
                'rest_kraken':   rest_px.get('kraken'),
                'rest_med':      rest_med,
                'ws_binance':    ws_mids.get('binance'),
                'ws_kraken':     ws_mids.get('kraken'),
                'ws_coinbase':   ws_mids.get('coinbase'),
                'ws_avg':        ws_avg,
                'diff':          diff,
                'diff_pct':      diff_pct,
            }
            samples.append(row)

            def fmt(v):
                return f"{v:>10,.2f}" if v is not None else f"{'N/A':>10s}"

            bn  = fmt(ws_mids.get('binance'))
            kk  = fmt(ws_mids.get('kraken'))
            cb  = fmt(ws_mids.get('coinbase'))
            wsa = fmt(ws_avg)
            rm  = fmt(rest_med)
            d   = f"{diff:>+8.2f}" if diff is not None else f"{'N/A':>8s}"
            dp  = f"{diff_pct:>+6.3f}%" if diff_pct is not None else f"{'N/A':>7s}"

            print(f"{elapsed:7.1f}s  {rm}  {bn}  {kk}  {cb}  {wsa}  {d}  {dp}")

            # Sleep for remainder of interval
            spent = time.time() - t0
            await asyncio.sleep(max(0, INTERVAL - spent))

    _print_stats(symbol)


def _print_stats(symbol: str):
    valid = [s for s in samples if s['diff'] is not None]
    if not valid:
        print("\n❌ No valid paired samples collected.")
        return

    diffs     = [s['diff']     for s in valid]
    diff_pcts = [s['diff_pct'] for s in valid]
    rest_meds = [s['rest_med'] for s in valid if s['rest_med']]
    ws_avgs   = [s['ws_avg']   for s in valid if s['ws_avg']]

    print(f"\n{'═'*78}")
    print(f"  STATISTICS  ({len(valid)} paired samples over {DURATION}s)")
    print(f"{'═'*78}")
    print(f"  REST median  — avg: ${mean(rest_meds):,.2f}")
    print(f"  WS avg mid   — avg: ${mean(ws_avgs):,.2f}")
    print()
    print(f"  WS_avg − REST_med (absolute $):")
    print(f"    mean   : {mean(diffs):>+.4f}")
    print(f"    std    : {stdev(diffs):.4f}" if len(diffs) > 1 else "    std    : N/A")
    print(f"    min    : {min(diffs):>+.4f}")
    print(f"    max    : {max(diffs):>+.4f}")
    print()
    print(f"  WS_avg − REST_med (percent of REST):")
    print(f"    mean   : {mean(diff_pcts):>+.5f}%")
    print(f"    std    : {stdev(diff_pcts):.5f}%" if len(diff_pcts) > 1 else "    std    : N/A")
    print(f"    max|Δ| : {max(abs(d) for d in diff_pcts):.5f}%")
    print()
    # Latency note
    print(f"  Latency note:")
    print(f"    REST — one HTTP round-trip per exchange (~50-200ms) + 2s cache window")
    print(f"    WS   — streaming, data age at sample time typically <100ms")
    print()
    print(f"  Interpretation:")
    pct_abs = mean(abs(d) for d in diff_pcts)
    if pct_abs < 0.01:
        verdict = "✅ Prices are essentially identical (<0.01% avg diff). REST is fine."
    elif pct_abs < 0.05:
        verdict = "✅ Very small avg diff (<0.05%). Both sources equally valid."
    else:
        verdict = "⚠️  Noticeable avg diff (>0.05%). WS may be marginally fresher."
    print(f"    {verdict}")
    print(f"    Kalshi settles on CF Benchmarks — REST median is closer to their")
    print(f"    calculation methodology. WS mid-price is slightly faster but uses")
    print(f"    a single-exchange mid vs. multi-exchange median.")
    print(f"{'═'*78}\n")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

async def main():
    print(f"\n🔌 Starting WebSocket feeds for {SYMBOL}...")
    print(f"   (Waiting 5s for WS connections to establish before sampling)")

    tasks = [
        asyncio.create_task(_feed_binance(SYMBOL)),
        asyncio.create_task(_feed_kraken(SYMBOL)),
        asyncio.create_task(_feed_coinbase(SYMBOL)),
    ]

    # Give WS feeds 5 seconds to connect and receive first data
    await asyncio.sleep(5)

    # Run sampler for DURATION seconds
    sampler = asyncio.create_task(_sampler(SYMBOL))
    await asyncio.sleep(DURATION)
    stop_event.set()
    await sampler

    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == '__main__':
    asyncio.run(main())
