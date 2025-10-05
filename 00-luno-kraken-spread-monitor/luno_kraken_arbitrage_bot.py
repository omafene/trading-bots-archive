#!/usr/bin/env python3
# luno_kraken_arbitrage_bot.py
# Optimized arbitrage alert bot for Luno-Kraken non-NGN pairs

import ccxt
import time
import json
import requests
from datetime import datetime
import logging
from typing import Dict, List, Optional, Tuple

class LunoKrakenArbitrageBot:
    """
    Monitors price differences between Luno and Kraken exchanges.
    Sends Telegram alerts for profitable arbitrage opportunities.
    """
    
    def __init__(self, config_file='config.json'):
        # Load configuration
        with open(config_file) as f:
            self.config = json.load(f)
        
        # Initialize exchanges
        self.luno = ccxt.luno({
            'enableRateLimit': True,
            'rateLimit': 1000,  # 1 request per second max
        })
        
        self.kraken = ccxt.kraken({
            'enableRateLimit': True,
            'rateLimit': 600,   # Kraken allows faster requests
        })
        
        # Top liquid pairs that exist on both exchanges
        # Ordered by typical liquidity (highest first)
        self.pairs = [
            'BTC/USDT',   # Highest liquidity
            'ETH/USDT',   # Very high liquidity
            'SOL/USDT',   # High liquidity, major L1
            'ETH/BTC',    # Good liquidity, established pair
            'XRP/BTC',    # Medium liquidity
            'LTC/BTC',    # Medium liquidity
            'XRP/USDT',   # If available
            'LTC/USDT',   # If available
            'BCH/BTC',    # Lower liquidity
            'USDC/USDT',  # Stablecoin pair (if available)
            'BTC/USDC',   # Alternative stable pair
            'USDT/XRP',   # Reverse XRP
            'USDT/SOL',   # Reverse SOL
        ]
        
        # Accurate fee structures (as of 2024)
        self.fees = {
            'luno': {
                'maker': 0.001,   # 0.1% maker
                'taker': 0.001    # 0.1% taker (Luno has same fee)
            },
            'kraken': {
                'maker': 0.0016,  # 0.16% maker
                'taker': 0.0026   # 0.26% taker (0-50k USD volume tier)
            }
        }
        
        # Smart thresholds based on pair characteristics
        self.thresholds = {
            'stablecoin': {
                'min_spread': 0.005,      # 0.5% minimum
                'good_spread': 0.008,     # 0.8% is good
                'excellent_spread': 0.015  # 1.5% is excellent
            },
            'major_stable': {  # BTC/USDT, ETH/USDT
                'min_spread': 0.003,
                'good_spread': 0.008,
                'excellent_spread': 0.015
            },
            'major_crypto': {  # ETH/BTC
                'min_spread': 0.012,
                'good_spread': 0.018,
                'excellent_spread': 0.025
            },
            'alt_btc': {  # XRP/BTC, LTC/BTC
                'min_spread': 0.018,
                'good_spread': 0.025,
                'excellent_spread': 0.035
            },
            'volatile': {  # Others
                'min_spread': 0.025,
                'good_spread': 0.035,
                'excellent_spread': 0.050
            }
        }
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('luno_kraken_arbitrage.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Alert management
        self.recent_alerts = {}
        self.alert_cooldown = 300  # 5 minutes between same pair alerts
        
        # Statistics tracking
        self.stats = {
            'opportunities_found': 0,
            'alerts_sent': 0,
            'by_pair': {}
        }
    
    def categorize_pair(self, pair: str) -> str:
        """Categorize pair by volatility/risk level"""
        if pair in ['USDC/USDT', 'DAI/USDT']:
            return 'stablecoin'
        elif pair in ['BTC/USDT', 'ETH/USDT', 'BTC/USDC', 'ETH/USDC']:
            return 'major_stable'
        elif pair == 'ETH/BTC':
            return 'major_crypto'
        elif pair in ['XRP/BTC', 'LTC/BTC', 'XRP/USDT', 'LTC/USDT']:
            return 'alt_btc'
        else:
            return 'volatile'
    
    def get_thresholds(self, pair: str) -> Dict[str, float]:
        """Get appropriate thresholds for a pair"""
        category = self.categorize_pair(pair)
        return self.thresholds[category]
    
    def calculate_real_profit(self, spread: float, buy_exchange: str, 
                             sell_exchange: str, pair: str) -> float:
        """
        Calculate actual profit after all costs
        
        Args:
            spread: Gross spread percentage
            buy_exchange: Exchange to buy from
            sell_exchange: Exchange to sell on
            pair: Trading pair
        
        Returns:
            Net profit percentage after fees and estimated slippage
        """
        buy_fee = self.fees[buy_exchange]['taker']
        sell_fee = self.fees[sell_exchange]['taker']
        
        # Estimate slippage based on pair type
        category = self.categorize_pair(pair)
        if category == 'stablecoin':
            slippage = 0.0005  # 0.05% (very tight)
        elif category == 'major_stable':
            slippage = 0.001   # 0.1%
        elif category == 'major_crypto':
            slippage = 0.0015  # 0.15%
        else:
            slippage = 0.002   # 0.2% (wider for alts)
        
        net_profit = spread - buy_fee - sell_fee - slippage
        return net_profit
    
    def get_risk_label(self, pair: str) -> Tuple[str, str]:
        """Get emoji and text label for risk level"""
        category = self.categorize_pair(pair)
        
        risk_map = {
            'stablecoin': ('🟢', 'VERY LOW RISK'),
            'major_stable': ('🟢', 'LOW RISK'),
            'major_crypto': ('🟡', 'MEDIUM RISK'),
            'alt_btc': ('🟠', 'MODERATE RISK'),
            'volatile': ('🔴', 'HIGH RISK - EXECUTE FAST')
        }
        
        return risk_map.get(category, ('🔴', 'HIGH RISK'))
    
    def check_pair_availability(self) -> List[str]:
        """Verify which pairs are tradeable on both exchanges"""
        self.logger.info("Checking pair availability on both exchanges...")
        
        try:
            luno_markets = self.luno.load_markets()
            kraken_markets = self.kraken.load_markets()
            
            available_pairs = []
            
            for pair in self.pairs:
                luno_has = pair in luno_markets
                kraken_has = pair in kraken_markets
                
                if luno_has and kraken_has:
                    available_pairs.append(pair)
                    category = self.categorize_pair(pair)
                    thresholds = self.get_thresholds(pair)
                    self.logger.info(
                        f"✓ {pair} available | Category: {category} | "
                        f"Min spread: {thresholds['min_spread']*100:.1f}%"
                    )
                    
                    # Initialize stats
                    self.stats['by_pair'][pair] = {
                        'opportunities': 0,
                        'alerts': 0
                    }
                else:
                    if not luno_has:
                        self.logger.warning(f"✗ {pair} not on Luno")
                    if not kraken_has:
                        self.logger.warning(f"✗ {pair} not on Kraken")
            
            self.pairs = available_pairs
            return available_pairs
            
        except Exception as e:
            self.logger.error(f"Error checking markets: {e}")
            return self.pairs
    
    def should_alert(self, pair: str, direction: str, spread: float) -> bool:
        """Check if we should send alert (cooldown + threshold check)"""
        alert_key = f"{pair}_{direction}"
        current_time = time.time()
        
        # Check cooldown
        if alert_key in self.recent_alerts:
            time_since_last = current_time - self.recent_alerts[alert_key]
            if time_since_last < self.alert_cooldown:
                return False
        
        # Check if spread meets minimum threshold
        thresholds = self.get_thresholds(pair)
        if spread < thresholds['min_spread']:
            return False
        
        self.recent_alerts[alert_key] = current_time
        return True
    
    def send_telegram_alert(self, message: str, urgent: bool = False) -> None:
        """Send alert to Telegram"""
        if not self.config.get('telegram_enabled'):
            return
        
        try:
            token = self.config['telegram_bot_token']
            chat_id = self.config['telegram_chat_id']
            
            if urgent:
                message = "🚨 EXCELLENT OPPORTUNITY 🚨\n\n" + message
            
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            data = {
                'chat_id': chat_id,
                'text': message,
                'parse_mode': 'Markdown',
                'disable_web_page_preview': True
            }
            
            response = requests.post(url, data=data, timeout=10)
            if response.status_code == 200:
                self.stats['alerts_sent'] += 1
            else:
                self.logger.error(f"Telegram failed: {response.text}")
                
        except Exception as e:
            self.logger.error(f"Telegram error: {e}")
    
    def format_alert_message(self, opportunity: Dict) -> str:
        """Format opportunity into readable alert with risk assessment"""
        pair = opportunity['pair']
        emoji, risk_label = self.get_risk_label(pair)
        thresholds = self.get_thresholds(pair)
        
        # Determine quality rating
        if opportunity['real_profit'] >= thresholds['excellent_spread']:
            quality = "⭐️⭐️⭐️ EXCELLENT"
        elif opportunity['real_profit'] >= thresholds['good_spread']:
            quality = "⭐️⭐️ GOOD"
        else:
            quality = "⭐️ MARGINAL"
        
        message = f"""
{emoji} *{risk_label}*
{quality}

*Pair:* `{opportunity['pair']}`
*Direction:* {opportunity['buy_exchange']} → {opportunity['sell_exchange']}

*Prices:*
Buy @ {opportunity['buy_price']:.8f}
Sell @ {opportunity['sell_price']:.8f}

*Financials:*
Gross Spread: {opportunity['spread']*100:.2f}%
Net Profit: {opportunity['real_profit']*100:.2f}%
Est. profit on $1000: ${opportunity['profit_usd_1000']:.2f}

*Execution:* {opportunity['execution_advice']}
*Time:* {opportunity['timestamp']}
        """
        return message.strip()
    
    def get_execution_advice(self, pair: str, real_profit: float) -> str:
        """Get execution advice based on pair and profit"""
        category = self.categorize_pair(pair)
        thresholds = self.get_thresholds(pair)
        
        if category in ['stablecoin', 'major_stable']:
            return "Low urgency - stable assets"
        elif real_profit >= thresholds['excellent_spread']:
            return "Execute ASAP - excellent spread"
        elif category == 'volatile':
            return "URGENT - Price may move fast"
        else:
            return "Execute within 2 minutes"
    
    def monitor_spreads(self) -> None:
        """Main monitoring loop"""
        self.logger.info(f"Starting monitoring for {len(self.pairs)} pairs")
        self.logger.info(f"Pairs: {', '.join(self.pairs)}")
        
        # Send startup notification
        startup_msg = f"✅ *Luno-Kraken Arbitrage Bot Started*\n\nMonitoring {len(self.pairs)} pairs:\n"
        startup_msg += '\n'.join([f"• {pair}" for pair in self.pairs])
        self.send_telegram_alert(startup_msg)
        
        consecutive_errors = 0
        
        while True:
            try:
                for pair in self.pairs:
                    try:
                        # Fetch tickers from both exchanges
                        luno_ticker = self.luno.fetch_ticker(pair)
                        time.sleep(0.1)  # Small delay to avoid rate limits
                        kraken_ticker = self.kraken.fetch_ticker(pair)
                        
                        # Validate data
                        if not all([
                            luno_ticker.get('bid'), luno_ticker.get('ask'),
                            kraken_ticker.get('bid'), kraken_ticker.get('ask')
                        ]):
                            continue
                        
                        # Log current prices (debug level)
                        self.logger.debug(
                            f"{pair} | Luno: {luno_ticker['bid']:.8f}/{luno_ticker['ask']:.8f} | "
                            f"Kraken: {kraken_ticker['bid']:.8f}/{kraken_ticker['ask']:.8f}"
                        )
                        
                        # Check both arbitrage directions
                        
                        # Direction 1: Buy Luno → Sell Kraken
                        spread_luno_kraken = (
                            kraken_ticker['bid'] - luno_ticker['ask']
                        ) / luno_ticker['ask']
                        
                        real_profit_1 = self.calculate_real_profit(
                            spread_luno_kraken, 'luno', 'kraken', pair
                        )
                        
                        if self.should_alert(pair, 'luno_to_kraken', spread_luno_kraken):
                            self.stats['opportunities_found'] += 1
                            self.stats['by_pair'][pair]['opportunities'] += 1
                            
                            opportunity = {
                                'pair': pair,
                                'buy_exchange': 'Luno',
                                'sell_exchange': 'Kraken',
                                'buy_price': luno_ticker['ask'],
                                'sell_price': kraken_ticker['bid'],
                                'spread': spread_luno_kraken,
                                'real_profit': real_profit_1,
                                'profit_usd_1000': real_profit_1 * 1000,
                                'execution_advice': self.get_execution_advice(pair, real_profit_1),
                                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            }
                            
                            message = self.format_alert_message(opportunity)
                            self.logger.info(
                                f"OPPORTUNITY: {pair} | Buy Luno @ {luno_ticker['ask']:.8f}, "
                                f"Sell Kraken @ {kraken_ticker['bid']:.8f} | "
                                f"Net profit: {real_profit_1*100:.2f}%"
                            )
                            
                            thresholds = self.get_thresholds(pair)
                            urgent = real_profit_1 >= thresholds['excellent_spread']
                            self.send_telegram_alert(message, urgent)
                            self.stats['by_pair'][pair]['alerts'] += 1
                            
                            # Log to file
                            with open('opportunities.json', 'a') as f:
                                json.dump(opportunity, f)
                                f.write('\n')
                        
                        # Direction 2: Buy Kraken → Sell Luno
                        spread_kraken_luno = (
                            luno_ticker['bid'] - kraken_ticker['ask']
                        ) / kraken_ticker['ask']
                        
                        real_profit_2 = self.calculate_real_profit(
                            spread_kraken_luno, 'kraken', 'luno', pair
                        )
                        
                        if self.should_alert(pair, 'kraken_to_luno', spread_kraken_luno):
                            self.stats['opportunities_found'] += 1
                            self.stats['by_pair'][pair]['opportunities'] += 1
                            
                            opportunity = {
                                'pair': pair,
                                'buy_exchange': 'Kraken',
                                'sell_exchange': 'Luno',
                                'buy_price': kraken_ticker['ask'],
                                'sell_price': luno_ticker['bid'],
                                'spread': spread_kraken_luno,
                                'real_profit': real_profit_2,
                                'profit_usd_1000': real_profit_2 * 1000,
                                'execution_advice': self.get_execution_advice(pair, real_profit_2),
                                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            }
                            
                            message = self.format_alert_message(opportunity)
                            self.logger.info(
                                f"OPPORTUNITY: {pair} | Buy Kraken @ {kraken_ticker['ask']:.8f}, "
                                f"Sell Luno @ {luno_ticker['bid']:.8f} | "
                                f"Net profit: {real_profit_2*100:.2f}%"
                            )
                            
                            thresholds = self.get_thresholds(pair)
                            urgent = real_profit_2 >= thresholds['excellent_spread']
                            self.send_telegram_alert(message, urgent)
                            self.stats['by_pair'][pair]['alerts'] += 1
                            
                            with open('opportunities.json', 'a') as f:
                                json.dump(opportunity, f)
                                f.write('\n')
                        
                    except Exception as e:
                        self.logger.error(f"Error checking {pair}: {e}")
                        continue
                
                # Reset error counter on successful loop
                consecutive_errors = 0
                
                # Sleep between full cycles
                time.sleep(self.config.get('monitoring_interval_seconds', 30))
                
            except KeyboardInterrupt:
                self.logger.info("Bot stopped by user")
                break
            except Exception as e:
                consecutive_errors += 1
                self.logger.error(f"Main loop error: {e}")
                
                if consecutive_errors >= 5:
                    self.send_telegram_alert(
                        "⚠️ Bot experiencing repeated errors. Check logs."
                    )
                    consecutive_errors = 0
                
                time.sleep(60)
    
    def print_statistics(self) -> None:
        """Print bot statistics"""
        self.logger.info("=" * 50)
        self.logger.info("Bot Statistics:")
        self.logger.info(f"Total opportunities found: {self.stats['opportunities_found']}")
        self.logger.info(f"Total alerts sent: {self.stats['alerts_sent']}")
        self.logger.info("\nBy pair:")
        for pair, data in self.stats['by_pair'].items():
            self.logger.info(
                f"  {pair}: {data['opportunities']} opportunities, "
                f"{data['alerts']} alerts"
            )
        self.logger.info("=" * 50)
    
    def run(self) -> None:
        """Start the bot"""
        self.logger.info("=" * 50)
        self.logger.info("Luno-Kraken Arbitrage Alert Bot")
        self.logger.info("Optimized for non-NGN liquid pairs")
        self.logger.info("=" * 50)
        
        # Check available pairs
        available = self.check_pair_availability()
        
        if not available:
            self.logger.error("No valid pairs found. Exiting.")
            return
        
        self.logger.info(f"\nMonitoring {len(available)} pairs")
        
        # Start monitoring
        try:
            self.monitor_spreads()
        except KeyboardInterrupt:
            self.logger.info("\nShutting down gracefully...")
        finally:
            self.print_statistics()

if __name__ == "__main__":
    bot = LunoKrakenArbitrageBot()
    bot.run()
