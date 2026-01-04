#!/usr/bin/env python3
"""
Analyze skip/filter lines from today's edge_bot.log (passed via stdin).
"""
import re, sys
from collections import defaultdict

TARGET_DATE = "2026-03-12"

# ── Patterns: (compiled_regex, category, priority) ────────────────────────────
# Higher priority = more specific; first match wins
SKIP_PATTERNS = [
    (re.compile(r'R.?squared|R²|r_squared|r2_filter', re.IGNORECASE),                    "R² filter"),
    (re.compile(r'HTF.*diverg|diverg.*HTF|htf.*not.*align|not.*htf.*align|htf.*misalign|counter.*htf|against.*htf|htf.*oppos|oppos.*htf', re.IGNORECASE), "HTF divergence"),
    (re.compile(r'htf.*align|align.*htf', re.IGNORECASE),                                "HTF (other)"),
    (re.compile(r'spread.*wide|wide.*spread|spread.*too|spread.*exceed|spread.*filter|spread.*above|spread.*high', re.IGNORECASE), "Spread too wide"),
    (re.compile(r'\bspread\b', re.IGNORECASE),                                           "Spread (other)"),
    (re.compile(r'depth.*insuffi|insuffi.*depth|depth.*too.*low|depth.*below|below.*depth|depth.*<|insufficient.*depth|depth.*thin|no.*depth|depth.*zero', re.IGNORECASE), "Low depth"),
    (re.compile(r'\bdepth\b', re.IGNORECASE),                                            "Low depth"),
    (re.compile(r'momentum.*low|low.*momentum|insuffi.*momentum|momentum.*insuffi|momentum.*fail|momentum.*weak|weak.*momentum|momentum.*below|below.*momentum', re.IGNORECASE), "Low momentum"),
    (re.compile(r'\bmomentum\b', re.IGNORECASE),                                         "Low momentum"),
    (re.compile(r'no edge|no_edge|insuffi.*edge|edge.*insuffi|edge.*below|below.*edge|low.*edge|edge.*too.*low|edge.*<', re.IGNORECASE), "Low/no edge"),
    (re.compile(r'below.*threshold|threshold.*not.*met|threshold.*below|below.*min', re.IGNORECASE), "Below threshold"),
    (re.compile(r'drawdown.*breaker|breaker.*drawdown|circuit.*breaker|max.*drawdown.*hit', re.IGNORECASE), "Drawdown breaker"),
    (re.compile(r'position.*limit|max.*position|already.*position|position.*open', re.IGNORECASE), "Position limit"),
    (re.compile(r'skip|skipping|skipped', re.IGNORECASE),                                "Skipped (general)"),
    (re.compile(r'filter|filtered|filtering', re.IGNORECASE),                            "Filtered (general)"),
    (re.compile(r'reject|rejected|rejecting', re.IGNORECASE),                            "Rejected"),
    (re.compile(r'insufficient', re.IGNORECASE),                                         "Insufficient (general)"),
    (re.compile(r'diverge|diverging|divergence', re.IGNORECASE),                         "Divergence"),
]

TICKER_RE = re.compile(r'\b((?:KX)?(?:BTC|ETH|SOL|XRP|NASDAQ|SPX|SP500)[A-Z0-9\-]*)\b')
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

def categorize(line):
    for pattern, cat in SKIP_PATTERNS:
        if pattern.search(line):
            return cat
    return None

# category → ticker → set of minute-window keys (for dedup)
skip_data   = defaultdict(lambda: defaultdict(set))
skip_sample = defaultdict(list)    # up to 5 samples per category
symbol_skip = defaultdict(lambda: defaultdict(set))  # symbol → cat → tickers

total = 0
for raw in sys.stdin:
    total += 1
    if total % 1_000_000 == 0:
        print(f"  ... {total:,} lines", file=sys.stderr, flush=True)

    line = raw.rstrip('\n')
    ts_m = TS_RE.match(line)
    if ts_m and ts_m.group(1) != TARGET_DATE:
        continue

    ts     = ts_m.group(0) if ts_m else ""
    minute = ts[:16] if ts else ""

    cat = categorize(line)
    if not cat:
        continue

    ticker = extract_ticker(line) or "NO_TICKER"
    symbol = extract_symbol(ticker if ticker != "NO_TICKER" else line)
    wkey   = f"{ticker}|{minute}"

    skip_data[cat][ticker].add(wkey)
    symbol_skip[symbol][cat].add(ticker)
    if len(skip_sample[cat]) < 5 and ticker != "NO_TICKER":
        # Only store if not already have this ticker
        already = any(ticker in s for s in skip_sample[cat])
        if not already:
            skip_sample[cat].append(f"  [{ts}] {line[50:200]}")

print(f"Lines processed: {total:,}\n", file=sys.stderr)

SEP = "=" * 72
sep = "─" * 72

print(SEP)
print(f"  SKIP / FILTER ANALYSIS — {TARGET_DATE}")
print(SEP)

# Build sorted list
summary = []
for cat, tdict in skip_data.items():
    real = {t for t in tdict if t != "NO_TICKER"}
    windows = sum(len(v) for v in tdict.values())
    summary.append((cat, real, windows))
summary.sort(key=lambda x: x[2], reverse=True)
grand = sum(x[2] for x in summary)

for cat, real_tickers, windows in summary:
    by_sym = defaultdict(list)
    for tk in sorted(real_tickers):
        by_sym[extract_symbol(tk)].append(tk)
    print(f"\n  [{cat}]  unique_tickers={len(real_tickers)}  skip_windows={windows}")
    for sym in sorted(by_sym):
        tks  = by_sym[sym]
        shown = tks[:12]
        more  = f"  (+{len(tks)-12} more)" if len(tks) > 12 else ""
        print(f"    {sym:8s}: {', '.join(shown)}{more}")
    if skip_sample[cat]:
        print(f"    Sample log lines:")
        for s in skip_sample[cat]:
            print(f"      →{s[:175]}")

# Per-symbol table
print(f"\n{sep}")
print("  SYMBOL FILTER TABLE (unique tickers per symbol per category)")
print(sep)

all_syms = sorted(s for s in symbol_skip if s != "UNKNOWN")
# use the order from summary (most frequent first)
all_cats = [c for c, _, _ in summary]

abbrev = {
    "R² filter":           "R²",
    "HTF divergence":      "HTF-div",
    "HTF (other)":         "HTF-other",
    "Spread too wide":     "Spread",
    "Spread (other)":      "Spread-oth",
    "Low depth":           "Depth",
    "Low momentum":        "Momentum",
    "Low/no edge":         "No-edge",
    "Below threshold":     "BelowThresh",
    "Drawdown breaker":    "DD-break",
    "Position limit":      "Pos-limit",
    "Skipped (general)":   "Skip-gen",
    "Filtered (general)":  "Filter-gen",
    "Rejected":            "Rejected",
    "Insufficient (general)": "Insuffi",
    "Divergence":          "Diverge",
}

# Print header
cols = [(c, abbrev.get(c, c[:12])) for c in all_cats]
print("  " + f"{'Symbol':<10}" + "".join(f"{ab:>12}" for _, ab in cols))
print("  " + "─"*(10 + 12*len(cols)))
for sym in all_syms:
    row = f"  {sym:<10}"
    for cat, _ in cols:
        n = len(symbol_skip[sym].get(cat, set()))
        row += f"{n:>12}"
    print(row)

print(f"\n  Grand total skip-windows: {grand:,}")
print(f"\n{SEP}\n")
