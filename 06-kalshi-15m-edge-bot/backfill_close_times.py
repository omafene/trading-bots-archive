#!/usr/bin/env python3
"""
Backfill close_time for existing skipped trades by parsing ticker
"""

import csv
import re
from datetime import datetime, timezone
from pathlib import Path

def parse_close_time_from_ticker(ticker: str):
    """
    Parse close time from ticker format: KXBTC15M-26FEB061030-00
    Format: KXSYMBOL15M-YYMMMDDHHMMM-NN
    Example: KXBTC15M-26FEB061030-00 = 2026-Feb-06 10:30
    Returns ISO format string or None
    """
    try:
        # Pattern: KXSYMBOL15M-YYMMMDDMM-NN
        # Extract: YY (year), MMM (month), DD (day), HHMM (time)
        match = re.search(r'(\d{2})([A-Z]{3})(\d{2})(\d{4})', ticker)
        if not match:
            return None

        year, month_str, day, time_str = match.groups()

        # Map month abbreviation to number
        months = {
            'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
            'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
        }

        month = months.get(month_str.upper())
        if not month:
            return None

        # Parse time (HHMM)
        hour = int(time_str[:2])
        minute = int(time_str[2:])

        # Construct datetime (assume 20XX year)
        full_year = 2000 + int(year)
        dt = datetime(full_year, month, int(day), hour, minute, tzinfo=timezone.utc)

        return dt.isoformat()
    except Exception as e:
        print(f"Error parsing ticker {ticker}: {e}")
        return None


def backfill_csv(csv_path):
    """Backfill close_time column for all rows"""
    csv_path = Path(csv_path)

    if not csv_path.exists():
        print(f"❌ CSV not found: {csv_path}")
        return

    # Read all rows
    rows = []
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames

        for row in reader:
            # Always parse close_time from ticker (overwrite wrong values)
            close_time = parse_close_time_from_ticker(row['ticker'])
            if close_time:
                row['close_time'] = close_time
                # Recalculate minutes_to_close (will be negative for past markets)
                try:
                    close_dt = datetime.fromisoformat(close_time)
                    now = datetime.now(timezone.utc)
                    minutes = (close_dt - now).total_seconds() / 60
                    row['minutes_to_close'] = str(round(minutes, 1))
                except:
                    pass

            rows.append(row)

    # Write back
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Count fixed
    fixed = sum(1 for r in rows if r['close_time'])
    print(f"✅ Backfilled {fixed}/{len(rows)} rows with close_time")


if __name__ == '__main__':
    csv_path = 'data/negative_edges/skipped_trades.csv'
    print(f"Backfilling close_time from tickers...")
    backfill_csv(csv_path)
    print("Done! Now run: python3 analyze_calibration.py --check-outcomes")
