# check_setup.py
import yaml
from edge_detector import EdgeDetector

def test():
    try:
        with open("config_15m.yaml", 'r') as f:
            config = yaml.safe_load(f)
        
        # Initialize EdgeDetector to see if it crashes
        detector = EdgeDetector(None, None, config)
        
        print("✅ EdgeDetector initialized with Safety Tiers:")
        print(f"   - Min Price: ${detector.min_entry_price}")
        print(f"   - Slippage Buffer: {detector.slippage_buffer}")
        print(f"   - Max Spread: ${detector.max_spread}")
        
        if hasattr(detector, 'traded_tickers'):
            print("✅ Ticker Lock (State Management) is PRESENT.")
            
    except Exception as e:
        print(f"❌ Setup Error: {e}")

if __name__ == "__main__":
    test()
