#!/usr/bin/env python3
"""
Analyze edge_bot.log for 2026-03-12 only.
Reads only today's lines (passed via stdin or start line offset).
"""

import re
import sys
from collections import defaultdict

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
    re.compile(r'Executing.*trade', re.IGNORECASE),
    re.compile(r'Entered.*position', re.IGNORECASE),
    re.compile(r'position.*opened', re.IGNORECASE),
]

# ── Skip/filter patterns → category ─────────────────────────────────────────
SKIP_PATTERNS = [
    (re.compile(r'R.?squared|R²|r_squared', re.IGNORECASE),              "R² filter"),
    (re.compile(r'HTF.*div|div.*HTF|not.*htf.*align|htf.*not.*align|htf.*misalign|counter.*htf|against.*htf', re.IGNORECASE), "HTF divergence"),
    (re.compile(r'spread.*wide|wide.*spread|bid.ask.*spread|spread.*filter|spread.*exceeds|spread.*too', re.IGNORECASE), "Spread too wide"),
    (re.compile(r'spread', re.IGNORECASE),                                "Spread too wide"),
    (re.compile(r'depth.*insuffi|insuffi.*depth|low.*depth|depth.*low|depth.*thin|thin.*depth|depth.*below|below.*depth|depth.*\d+.*<|<.*depth', re.IGNORECASE), "Low depth"),
    (re.compile(r'depth', re.IGNORECASE),                                 "Low depth"),
    (re.compile(r'momentum.*low|low.*momentum|insufficient.*momentum|momentum.*insufficient|weak.*momentum', re.IGNORECASE), "Low momentum"),
    (re.compile(r'momentum.*filter|filter.*momentum|momentum.*skip|skip.*momentum|momentum.*fail', re.IGNORECASE), "Low momentum"),
    (re.compile(r'momentum', re.IGNORECASE),                              "Low momentum"),
    (re.compile(r'no edge|no_edge|insufficient.*edge|edge.*insufficient|edge.*below|below.*edge|low.*edge|edge.*too.*low', re.IGNORECASE), "Low/no edge"),
    (re.compile(r'below.*threshold|threshold.*not.*met|threshold.*below', re.IGNORECASE), "Below threshold"),
    (re.compile(r'skip|skipping|skipped', re.IGNORECASE),                 "Skipped (general)"),
    (re.compile(r'filter|filtered|filtering', re.IGNORECASE),             "Filtered (general)"),
    (re.compile(r'reject|rejected|rejecting', re.IGNORECASE),             "Rejected"),
    (re.compile(r'insufficient', re.IGNORECASE),                          "Insufficient (general)"),
    (re.compile(r'diverge|diverging|divergence', re.IGNORECASE),          "Divergence"),
]

# ── Ticker extractor ──────────────────────────────────────────────────────────
TICKER_RE = re.compile(r'\b((?:KX)?(?:BTC|ETH|SOL|XRP|NASDAQ|SPX|SP500)[A-Z0-9\-_]*)\b')
SYMBOL_RE = re.compile(r'\b(BTC|ETH|SOL|XRP|NASDAQ|SPX)\b', re.IGNORECASE)
TS_RE     = re.compile(r'^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})')

def extract_ticker(line):
    m = TICKER_RE.search(line)
    return m.group(1) if m else None

def extract_symbol(text):
    if not text:
        return "UNKNOWN"
    m = SYMBOL_RE.search(text)
    return m.group(1).upper() if m else "UNKNOWN"

def categorize_skip(line):
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
trades = []
skip_data   = defaultdict(lambda: defaultdict(set))   # category → ticker → {window_keys}
skip_sample = defaultdict(list)
symbol_skip = defaultdict(lambda: defaultdict(set))   # symbol → category → {tickers}

total_lines = 0

for raw_line in sys.stdin:
    total_lines += 1
    if total_lines % 1_000_000 == 0:
        print(f"  ... {total_lines:,} lines processed", file=sys.stderr, flush=True)

    line = raw_line.rstrip('\n')

    # Only process target date lines
    m = TS_RE.match(line)
    if m and m.group(1) != TARGET_DATE:
        continue

    ts_match = TS_RE.match(line)
    ts     = ts_match.group(0) if ts_match else ""
    minute = ts[:16] if ts else ""

    # ── Trade detection ────────────────────────────────────────────────
    if is_trade_line(line):
        ticker = extract_ticker(line)
        symbol = extract_symbol(ticker or line)
        side_m  = re.search(r'\b(YES|NO)\b', line)
        size_m  = re.search(r'(?:size|qty|quantity|contracts?)[=:\s]+(\d+)', line, re.IGNORECASE)
        price_m = re.search(r'(?:price|@)[=:\s]+\$?([\d.]+)', line, re.IGNORECASE)
        trades.append({
            'time':   ts,
            'ticker': ticker or '?',
            'symbol': symbol,
            'side':   side_m.group(1)  if side_m  else '?',
            'size':   size_m.group(1)  if size_m  else '?',
            'price':  price_m.group(1) if price_m else '?',
            'line':   line[:220],
        })

    # ── Skip/filter detection ──────────────────────────────────────────
    category = categorize_skip(line)
    if category:
        ticker = extract_ticker(line) or "NO_TICKER"
        symbol = extract_symbol(ticker or line)
        window_key = f"{ticker}|{minute}"
        skip_data[category][ticker].add(window_key)
        symbol_skip[symbol][category].add(ticker)
        if len(skip_sample[category]) < 4:
            skip_sample[category].append(line[:200])

print(f"\nLines processed: {total_lines:,}", file=sys.stderr)

# ── Report ─────────────────────────────────────────────────────────────────────
SEP = "=" * 72
sep = "─" * 72

print(SEP)
print(f"  KALSHI EDGE BOT LOG ANALYSIS — {TARGET_DATE}")
print(SEP)

# 1. Trades
print(f"\n{sep}")
print(f"  ACTUAL TRADES EXECUTED  ({len(trades)} candidate lines)")
print(sep)
if trades:
    for t in trades:
        print(f"  [{t['time']}] {t['symbol']:6s} | {t['ticker']} | side={t['side']} | size={t['size']} | @{t['price']}")
        print(f"    {t['line'][:160]}")
else:
    print("  (no trade lines matched)")

# 2. Skipped markets
print(f"\n{sep}")
print(f"  SKIPPED / FILTERED MARKETS — by category")
print(sep)

category_summary = []
for category, td in skip_data.items():
    real_tickers = {t for t in td if t != "NO_TICKER"}
    total_windows = sum(len(v) for v in td.values())
    category_summary.append((category, real_tickers, total_windows))
category_summary.sort(key=lambda x: x[2], reverse=True)

grand_total = sum(x[2] for x in category_summary)

for category, real_tickers, total_windows in category_summary:
    print(f"\n  [{category}]")
    print(f"    Unique tickers : {len(real_tickers)}")
    print(f"    Skip windows   : {total_windows}")
    by_sym = defaultdict(list)
    for tk in sorted(real_tickers):
        by_sym[extract_symbol(tk)].append(tk)
    for sym, tks in sorted(by_sym.items()):
        shown = tks[:8]
        more  = f"  (+{len(tks)-8} more)" if len(tks) > 8 else ""
        print(f"    {sym:8s}: {', '.join(shown)}{more}")
    print(f"    Samples:")
    for s in skip_sample[category]:
        print(f"      → {s[:165]}")

# 3. Symbol summary table
print(f"\n{sep}")
print(f"  SYMBOL FILTER SUMMARY (unique tickers filtered, per symbol per reason)")
print(sep)

all_syms  = sorted(symbol_skip.keys())
all_cats  = [c for c, _, _ in category_summary]  # already sorted by freq

# Abbreviate category names for table
abbrev = {
    "R² filter":            "R²",
    "HTF divergence":       "HTF-div",
    "Spread too wide":      "Spread",
    "Low depth":            "Depth",
    "Low momentum":         "Momentum",
    "Low/no edge":          "No-edge",
    "Below threshold":      "BelowThresh",
    "Skipped (general)":    "Skip-gen",
    "Filtered (general)":   "Filter-gen",
    "Rejected":             "Rejected",
    "Insufficient (general)": "Insuffi",
    "Divergence":           "Diverge",
}

cols = [(c, abbrev.get(c, c[:12])) for c in all_cats]
hdr = f"  {'Symbol':<10}" + "".join(f"{ab:>12}" for _, ab in cols)
print(hdr)
print("  " + "─" * (10 + 12 * len(cols)))
for sym in all_syms:
    row = f"  {sym:<10}"
    for cat, _ in cols:
        n = len(symbol_skip[sym].get(cat, set()))
        row += f"{n:>12}"
    print(row)

print(f"\n  Grand total skip-windows today: {grand_total:,}")
print(f"\n{SEP}\n")
