"""
Kalshi Trading Bot Performance Analysis
Analyzes completed trades and provides optimization insights
"""

import json
import pandas as pd
from datetime import datetime
from collections import defaultdict

def load_trades():
    """Load trade data from JSON"""
    try:
        with open('analysis/trades.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("❌ No trades.json found. Run data collection first.")
        return []

def analyze_trades(trades):
    """Comprehensive trade analysis"""
    
    if not trades:
        print("No trades to analyze")
        return
    
    print("=" * 80)
    print("KALSHI BOT PERFORMANCE ANALYSIS")
    print("=" * 80)
    
    # Convert to DataFrame for easier analysis
    df = pd.DataFrame(trades)
    
    # Basic Stats
    total_trades = len(df)
    print(f"\n📊 OVERALL STATISTICS")
    print(f"{'─' * 80}")
    print(f"Total Trades: {total_trades}")
    
    # Side breakdown
    if 'side' in df.columns:
        side_counts = df['side'].value_counts()
        print(f"\nTrades by Side:")
        for side, count in side_counts.items():
            pct = count / total_trades * 100
            print(f"  {side.upper()}: {count} ({pct:.1f}%)")
    
    # Action breakdown (buy vs sell)
    if 'action' in df.columns:
        action_counts = df['action'].value_counts()
        print(f"\nTrades by Action:")
        for action, count in action_counts.items():
            print(f"  {action.capitalize()}: {count}")
    
    # Price analysis
    print(f"\n💰 PRICE ANALYSIS")
    print(f"{'─' * 80}")
    
    # Extract prices based on side
    prices = []
    for _, trade in df.iterrows():
        side = trade.get('side', 'yes')
        if side == 'yes':
            price = trade.get('yes_price', 0) / 100
        else:
            price = trade.get('no_price', 0) / 100
        prices.append(price)
    
    if prices:
        df['price'] = prices
        print(f"Average Entry Price: ${pd.Series(prices).mean():.2f}")
        print(f"Median Entry Price: ${pd.Series(prices).median():.2f}")
        print(f"Min Entry Price: ${pd.Series(prices).min():.2f}")
        print(f"Max Entry Price: ${pd.Series(prices).max():.2f}")
        
        # Probability distribution
        print(f"\nProbability Distribution:")
        prob_bins = [0, 0.75, 0.80, 0.85, 0.90, 0.95, 1.01]
        prob_labels = ['<75%', '75-80%', '80-85%', '85-90%', '90-95%', '95-100%']
        df['prob_bucket'] = pd.cut(df['price'], bins=prob_bins, labels=prob_labels)
        bucket_counts = df['prob_bucket'].value_counts().sort_index()
        for bucket, count in bucket_counts.items():
            pct = count / total_trades * 100
            print(f"  {bucket}: {count} trades ({pct:.1f}%)")
    
    # Category analysis
    if 'ticker' in df.columns:
        print(f"\n📂 CATEGORY ANALYSIS")
        print(f"{'─' * 80}")
        
        # Extract category from ticker (first part before hyphen)
        df['category'] = df['ticker'].str.split('-').str[0]
        category_counts = df['category'].value_counts().head(10)
        
        print(f"Top 10 Categories:")
        for cat, count in category_counts.items():
            pct = count / total_trades * 100
            print(f"  {cat}: {count} trades ({pct:.1f}%)")
    
    # Time analysis
    if 'created_time' in df.columns:
        print(f"\n⏰ TIME ANALYSIS")
        print(f"{'─' * 80}")
        
        df['timestamp'] = pd.to_datetime(df['created_time'])
        df['date'] = df['timestamp'].dt.date
        df['hour'] = df['timestamp'].dt.hour
        
        print(f"Trading Period: {df['date'].min()} to {df['date'].max()}")
        print(f"Days Active: {df['date'].nunique()}")
        print(f"Average Trades per Day: {total_trades / df['date'].nunique():.1f}")
        
        # Hourly distribution
        hourly = df['hour'].value_counts().sort_index()
        print(f"\nMost Active Hours (EST):")
        for hour, count in hourly.head(5).items():
            print(f"  {hour:02d}:00 - {count} trades")
    
    # Cost analysis
    print(f"\n💸 COST ANALYSIS")
    print(f"{'─' * 80}")
    
    df['cost'] = df['count'] * df['price']
    print(f"Total Capital Deployed: ${df['cost'].sum():,.2f}")
    print(f"Average Position Size: ${df['cost'].mean():.2f}")
    print(f"Largest Position: ${df['cost'].max():.2f}")
    print(f"Smallest Position: ${df['cost'].min():.2f}")
    
    return df

def generate_recommendations(df):
    """Generate optimization recommendations based on analysis"""
    
    print(f"\n💡 OPTIMIZATION RECOMMENDATIONS")
    print(f"{'=' * 80}")
    
    recommendations = []
    
    # Probability analysis
    if 'price' in df.columns:
        avg_price = df['price'].mean()
        
        if avg_price < 0.80:
            recommendations.append({
                'area': 'Probability Threshold',
                'finding': f'Average entry at {avg_price:.0%} - trading lower probability markets',
                'recommendation': 'Consider raising min_probability to 0.85+ for higher win rate',
                'config': 'strategy.min_probability: 0.85'
            })
        elif avg_price > 0.93:
            recommendations.append({
                'area': 'Probability Threshold',
                'finding': f'Average entry at {avg_price:.0%} - very high probability only',
                'recommendation': 'You could lower to 0.85-0.90 for more opportunities',
                'config': 'strategy.min_probability: 0.85'
            })
    
    # Side analysis
    if 'side' in df.columns:
        yes_pct = (df['side'] == 'yes').sum() / len(df) * 100
        no_pct = (df['side'] == 'no').sum() / len(df) * 100
        
        if yes_pct > 90:
            recommendations.append({
                'area': 'Side Distribution',
                'finding': f'{yes_pct:.0f}% YES trades - heavily skewed',
                'recommendation': 'Verify NO side trading is working properly',
                'config': 'Check position_manager.py no_price handling'
            })
        elif no_pct > 70:
            recommendations.append({
                'area': 'Side Distribution',
                'finding': f'{no_pct:.0f}% NO trades - heavily skewed',
                'recommendation': 'Consider YES-only if NO side has lower win rate',
                'config': 'filters.require_yes_side: true'
            })
    
    # Position sizing
    if 'cost' in df.columns:
        avg_size = df['cost'].mean()
        
        if avg_size < 20:
            recommendations.append({
                'area': 'Position Sizing',
                'finding': f'Average position ${avg_size:.2f} - very small',
                'recommendation': 'Increase position_size_pct or lower min_position_size',
                'config': 'capital.position_size_pct: 0.10 (from current value)'
            })
        elif avg_size > 50:
            recommendations.append({
                'area': 'Position Sizing',
                'finding': f'Average position ${avg_size:.2f} - quite large',
                'recommendation': 'Consider smaller sizes for better diversification',
                'config': 'capital.max_position_size: 40'
            })
    
    # Category concentration
    if 'category' in df.columns:
        top_cat_pct = df['category'].value_counts().iloc[0] / len(df) * 100
        top_cat = df['category'].value_counts().index[0]
        
        if top_cat_pct > 50:
            recommendations.append({
                'area': 'Diversification',
                'finding': f'{top_cat_pct:.0f}% of trades in {top_cat} category',
                'recommendation': 'Add category limits for better diversification',
                'config': 'risk.max_per_category: 0.30'
            })
    
    # Print recommendations
    for i, rec in enumerate(recommendations, 1):
        print(f"\n{i}. {rec['area'].upper()}")
        print(f"   Finding: {rec['finding']}")
        print(f"   💡 Recommendation: {rec['recommendation']}")
        print(f"   Config: {rec['config']}")
    
    if not recommendations:
        print("\n✅ No major issues found - strategy looks balanced!")
    
    return recommendations

def main():
    """Main analysis function"""
    trades = load_trades()
    
    if trades:
        df = analyze_trades(trades)
        if df is not None:
            recommendations = generate_recommendations(df)
            
            # Save analysis
            with open('analysis/recommendations.txt', 'w') as f:
                f.write("OPTIMIZATION RECOMMENDATIONS\n")
                f.write("=" * 80 + "\n\n")
                for i, rec in enumerate(recommendations, 1):
                    f.write(f"{i}. {rec['area']}\n")
                    f.write(f"   {rec['finding']}\n")
                    f.write(f"   Recommendation: {rec['recommendation']}\n")
                    f.write(f"   Config: {rec['config']}\n\n")
            
            print(f"\n✅ Analysis saved to analysis/recommendations.txt")

if __name__ == "__main__":
    main()
