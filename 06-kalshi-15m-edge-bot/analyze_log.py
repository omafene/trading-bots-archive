#!/usr/bin/env python3
"""
Analyze edge_bot.log for 2026-03-12 only.
Streams line by line to handle large file.
"""

import re
import sys
from collections import defaultdict
from datetime import datetime

LOG_FILE = "/root/kalshi_15m_bot/logs/edge_bot.log"
TARGET_DATE = "2026-03-12"

# ── Trade patterns ──────────────────────────────────────────────────────────
TRADE_PATTERNS = [
    re.compile(r'TRADE', re.IGNORECASE),
    re.compile(r'Order placed', re.IGNORECASE),
    re.compile(r'Placing order', re.IGNORECASE),
    re.compile(r'order placed', re.IGNORECASE),
    re.compile(r'✅.*[Oo]rder'),
    re.compile(r'🎯'),
    re.compile(r'\bBUY\b'),
    re.compile(r'\bSELL\b'),
    re.compile(r'submitted.*order', re.IGNORECASE),
    re.compile(r'order.*filled', re.IGNORECASE),
    re.compile(r'filled.*order', re.IGNORECASE),
    re.compile(r'IOC.*order', re.IGNORECASE),
    re.compile(r'limit.*order.*placed', re.IGNORECASE),
]

# ── Skip/filter patterns → category ─────────────────────────────────────────
SKIP_PATTERNS = [
    # Order matters: more specific first
    (re.compile(r'R.?squared|R²|r_squared', re.IGNORECASE),            "R² filter"),
    (re.compile(r'HTF.*div|div.*HTF|htf.*align|not.*aligned', re.IGNORECASE), "HTF divergence"),
    (re.compile(r'spread.*wide|wide.*spread|bid.ask.*spread|spread.*filter', re.IGNORECASE), "Spread too wide"),
    (re.compile(r'spread', re.IGNORECASE),                              "Spread too wide"),
    (re.compile(r'\bdepth\b.*insuffi|insuffi.*\bdepth\b|low.*depth|depth.*low|depth.*thin|thin.*depth', re.IGNORECASE), "Low depth"),
    (re.compile(r'\bdepth\b.*below|below.*\bdepth\b', re.IGNORECASE),  "Low depth"),
    (re.compile(r'\bdepth\b', re.IGNORECASE),                          "Low depth"),
    (re.compile(r'momentum.*low|low.*momentum|insufficient.*momentum', re.IGNORECASE), "Low momentum"),
    (re.compile(r'momentum.*filter|filter.*momentum', re.IGNORECASE),   "Low momentum"),
    (re.compile(r'no edge|insufficient edge|edge.*below|low edge', re.IGNORECASE), "Low/no edge"),
    (re.compile(r'below.*threshold|threshold.*not met', re.IGNORECASE), "Below threshold"),
    (re.compile(r'skip|skipping|skipped', re.IGNORECASE),               "Skipped (general)"),
    (re.compile(r'filter|filtered|filtering', re.IGNORECASE),           "Filtered (general)"),
    (re.compile(r'reject|rejected', re.IGNORECASE),                     "Rejected"),
    (re.compile(r'insufficient', re.IGNORECASE),                        "Insufficient (general)"),
    (re.compile(r'diverge|diverging|divergence', re.IGNORECASE),        "Divergence"),
]

# ── Ticker extractor ──────────────────────────────────────────────────────────
# Kalshi tickers look like: KXBTCD-26MAR1215-T72500, BTC-..., ETH-..., SOL-..., XRP-...
TICKER_RE = re.compile(r'\b((?:KX)?(?:BTC|ETH|SOL|XRP|NASDAQ|SPX|SP500)[A-Z0-9\-_]*)\b')
SYMBOL_RE = re.compile(r'\b(BTC|ETH|SOL|XRP|NASDAQ|SPX)\b', re.IGNORECASE)

# Timestamp prefix pattern
TS_RE = re.compile(r'^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})')

def extract_ticker(line):
    """Return the first ticker-like token from a line, or None."""
    m = TICKER_RE.search(line)
    return m.group(1) if m else None

def extract_symbol(ticker_or_line):
    """Return BTC/ETH/SOL/XRP/etc from a ticker or line."""
    if not ticker_or_line:
        return "UNKNOWN"
    m = SYMBOL_RE.search(ticker_or_line)
    return m.group(1).upper() if m else "UNKNOWN"

def categorize_skip(line):
    """Return skip category or None."""
    for pattern, category in SKIP_PATTERNS:
        if pattern.search(line):
            return category
    return None

def is_trade_line(line):
    for p in TRADE_PATTERNS:
        if p.search(line):
            return True
    return False

# ── Main ──────────────────────────────────────────────────────────────────────

trades = []  # list of dicts
# skip_data[category][ticker] = set of (date_minute) windows to deduplicate
skip_data = defaultdict(lambda: defaultdict(set))
skip_lines_sample = defaultdict(list)  # category → up to 3 sample lines

symbol_skip_count = defaultdict(lambda: defaultdict(set))  # symbol → category → tickers

total_lines = 0
today_lines = 0
in_today = False

print(f"Streaming {LOG_FILE} ...", flush=True)

with open(LOG_FILE, 'r', errors='replace') as f:
    for raw_line in f:
        total_lines += 1
        if total_lines % 5_000_000 == 0:
            print(f"  ... {total_lines:,} lines processed, today_lines={today_lines:,}", flush=True)

        line = raw_line.rstrip('\n')

        # ── Date filter ────────────────────────────────────────────────────
        m = TS_RE.match(line)
        if m:
            line_date = m.group(1)
            if line_date == TARGET_DATE:
                in_today = True
            elif line_date > TARGET_DATE:
                # Log is chronological; once we pass today we can stop
                break
            else:
                in_today = False
        # Lines without a timestamp: inherit current in_today state
        if not in_today:
            continue

        today_lines += 1

        # Extract timestamp for context
        ts_match = TS_RE.match(line)
        ts = ts_match.group(0) if ts_match else ""
        minute = ts[:16] if ts else ""  # "2026-03-12 HH:MM"

        # ── Trade detection ────────────────────────────────────────────────
        if is_trade_line(line):
            ticker = extract_ticker(line)
            symbol = extract_symbol(ticker or line)
            # Try to parse side/size/price
            side_m = re.search(r'\b(YES|NO)\b', line)
            size_m = re.search(r'(?:size|qty|quantity|contracts?)[=:\s]+(\d+)', line, re.IGNORECASE)
            price_m = re.search(r'(?:price|@)[=:\s]+\$?([\d.]+)', line, re.IGNORECASE)
            trades.append({
                'time': ts,
                'ticker': ticker or '?',
                'symbol': symbol,
                'side': side_m.group(1) if side_m else '?',
                'size': size_m.group(1) if size_m else '?',
                'price': price_m.group(1) if price_m else '?',
                'line': line[:200],
            })

        # ── Skip/filter detection ──────────────────────────────────────────
        category = categorize_skip(line)
        if category:
            ticker = extract_ticker(line)
            if not ticker:
                ticker = "NO_TICKER"
            symbol = extract_symbol(ticker or line)
            # Deduplicate by (ticker, minute) per category
            window_key = f"{ticker}|{minute}"
            skip_data[category][ticker].add(window_key)
            symbol_skip_count[symbol][category].add(ticker)
            if len(skip_lines_sample[category]) < 3:
                skip_lines_sample[category].append(line[:200])

print(f"\nDone. Total lines read: {total_lines:,} | Today's lines: {today_lines:,}\n")

# ── Report ─────────────────────────────────────────────────────────────────────

print("=" * 70)
print(f"  KALSHI EDGE BOT LOG ANALYSIS — {TARGET_DATE}")
print("=" * 70)

# 1. Trades
print(f"\n{'─'*70}")
print(f"  ACTUAL TRADES EXECUTED  ({len(trades)} matching lines)")
print(f"{'─'*70}")

if trades:
    for t in trades:
        print(f"  [{t['time']}] {t['symbol']:6s} | ticker={t['ticker']} | side={t['side']} | size={t['size']} | price={t['price']}")
        print(f"           └─ {t['line'][:150]}")
else:
    print("  (no trade lines found)")

# 2. Skipped markets
print(f"\n{'─'*70}")
print(f"  SKIPPED / FILTERED MARKETS")
print(f"{'─'*70}")

total_unique_skip_events = 0
category_summary = []
for category, ticker_dict in sorted(skip_data.items()):
    unique_tickers = set(ticker_dict.keys())
    unique_tickers.discard("NO_TICKER")
    total_windows = sum(len(v) for v in ticker_dict.values())
    total_unique_skip_events += total_windows
    category_summary.append((category, unique_tickers, total_windows))

# Sort by total windows descending
category_summary.sort(key=lambda x: x[2], reverse=True)

for category, unique_tickers, total_windows in category_summary:
    print(f"\n  [{category}]  unique tickers={len(unique_tickers)}  total skip-windows={total_windows}")
    # Show tickers grouped by symbol
    by_symbol = defaultdict(list)
    for tk in sorted(unique_tickers):
        sym = extract_symbol(tk)
        by_symbol[sym].append(tk)
    for sym, tks in sorted(by_symbol.items()):
        print(f"    {sym}: {', '.join(tks[:10])}{'...' if len(tks)>10 else ''}")
    # Sample log lines
    if skip_lines_sample[category]:
        print(f"    Sample lines:")
        for s in skip_lines_sample[category]:
            print(f"      → {s[:160]}")

# 3. Symbol summary
print(f"\n{'─'*70}")
print(f"  SYMBOL FILTER SUMMARY (unique tickers filtered per symbol per category)")
print(f"{'─'*70}")

all_symbols = sorted(symbol_skip_count.keys())
all_categories = sorted(set(cat for cats in symbol_skip_count.values() for cat in cats))

# Header
header = f"  {'Symbol':<10}"
for cat in all_categories:
    short = cat[:18]
    header += f"  {short:<18}"
print(header)
print("  " + "─" * (10 + 20 * len(all_categories)))
for sym in all_symbols:
    row = f"  {sym:<10}"
    for cat in all_categories:
        count = len(symbol_skip_count[sym].get(cat, set()))
        row += f"  {count:<18}"
    print(row)

print(f"\n  Total unique skip windows today: {total_unique_skip_events:,}")
print(f"\n{'='*70}\n")
