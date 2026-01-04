import re
import pandas as pd
from datetime import datetime, timedelta

def analyze_logs(log_file):
    trades = []
    # Pattern to catch the "EDGE DETECTED" blocks we built
    pattern = re.compile(r"💎 EDGE: ([\d.]+)%.*?Expected: ([\d.]+)% \| Market: ([\d.]+)%.*?💰 (YES|NO) @ (\d+)%", re.DOTALL)
    
    with open(log_file, 'r') as f:
        content = f.read()
        matches = pattern.findall(content)
        
        for match in matches:
            edge, expected, market_price, side, entry = match
            trades.append({
                "edge": float(edge),
                "side": side,
                "entry_price": int(entry) / 100,
                "status": "Potential Trade Found"
            })
    
    df = pd.DataFrame(trades)
    print("📊 LOG AUDIT SUMMARY")
    print(f"Total Signals Found: {len(df)}")
    if not df.empty:
        print(f"Avg Edge per Trade: {df['edge'].mean():.2f}%")
        print(f"Bias Check: {df['side'].value_counts(normalize=True).to_dict()}")
    return df

# Run it
if __name__ == "__main__":
    analyze_logs("/root/.pm2/logs/kalshi-bot-15m-out.log")
