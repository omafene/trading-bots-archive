import os

# CONFIGURATION
MIN_EDGE = 15.0
PRICE_FLOOR = 0.10
SLIPPAGE_PENALTY = 2.0 

def calibrate_direct():
    target_file = 'my_results.txt'
    if not os.path.exists(target_file):
        print(f"❌ File not found: {target_file}. Please create it and paste your results.")
        return

    stats = {
        'raw_lines': 0,
        'filtered_trades': 0,
        'wins': 0,
        'losses': 0,
        'skipped_lock': 0,
        'skipped_price': 0,
        'skipped_edge': 0
    }
    ticker_lock = set()

    with open(target_file, 'r') as f:
        for line in f:
            if 'KX' not in line or '@' not in line:
                continue
                
            stats['raw_lines'] += 1
            try:
                # Extract Ticker
                ticker = line.split(':')[0].strip().split()[-1]
                
                # Extract Side
                side = 'YES' if 'YES' in line.upper() else 'NO'
                
                # Extract Price
                price_str = line.split('@')[1].split('%')[0].strip()
                price_val = int(price_str) / 100.0
                
                # Extract Edge
                edge_val = 0.0
                if 'Edge:' in line:
                    edge_val = float(line.split('Edge:')[1].split('%')[0].strip())
                
                # Extract Result
                won = '✅' in line or 'WIN' in line.upper()

                # --- FILTERS ---
                if ticker in ticker_lock:
                    stats['skipped_lock'] += 1
                    continue
                
                if price_val < PRICE_FLOOR:
                    stats['skipped_price'] += 1
                    continue

                calibrated_edge = edge_val - SLIPPAGE_PENALTY
                if calibrated_edge < MIN_EDGE:
                    stats['skipped_edge'] += 1
                    continue

                # SUCCESS
                ticker_lock.add(ticker)
                stats['filtered_trades'] += 1
                if won: stats['wins'] += 1
                else: stats['losses'] += 1
                
                print(f"✅ PASSED: {ticker} | {side} @ {price_str}% | Win: {won}")

            except:
                continue

    # Final Report
    wr = (stats['wins'] / stats['filtered_trades'] * 100) if stats['filtered_trades'] > 0 else 0
    print("\n" + "="*60)
    print("CALIBRATION REPORT (v3.1 Filters)")
    print("="*60)
    print(f"Total Tickers Found: {stats['raw_lines']}")
    print(f"Unique Trades Executed: {stats['filtered_trades']}")
    print(f"Calibrated Win Rate: {wr:.1f}%")
    print("-" * 30)
    print(f"🚫 Blocked Lock (Spam):  {stats['skipped_lock']}")
    print(f"🚫 Blocked Floor (Dust): {stats['skipped_price']}")
    print(f"🚫 Blocked Edge (Low):   {stats['skipped_edge']}")
    print("="*60)

if __name__ == "__main__":
    calibrate_direct()
