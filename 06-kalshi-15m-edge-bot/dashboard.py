"""
Performance Monitoring Dashboard
Web-based real-time monitoring interface
"""

from flask import Flask, render_template, jsonify
from flask_cors import CORS
import logging
import json
from pathlib import Path
from datetime import datetime, timezone
import threading

logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for API calls

# Global reference to bot instance
_bot_instance = None


def set_bot_instance(bot):
    """Set bot instance for dashboard to monitor"""
    global _bot_instance
    _bot_instance = bot
    logger.info("✅ Dashboard connected to bot instance")


def get_bot_metrics():
    """Get current bot metrics"""
    if not _bot_instance:
        return None

    try:
        bot = _bot_instance
        balance = bot.client.get_balance()
        positions = bot.position_manager.open_positions
        state_stats = bot.state_manager.get_stats()
        dd_status = bot.risk_manager.get_drawdown_status(balance)

        # Calculate today's P&L
        closed_today = bot.state_manager.get_closed_positions(limit=50)
        today_pnl = sum(p.get('pnl_pct', 0) for p in closed_today if p.get('closed_at', '').startswith(datetime.now().strftime('%Y-%m-%d')))

        # Calculate win rate
        wins = sum(1 for p in closed_today if p.get('pnl_pct', 0) > 0)
        total = len(closed_today)
        win_rate = (wins / total * 100) if total > 0 else 0

        return {
            'balance': balance,
            'peak_balance': dd_status['peak_balance'],
            'drawdown': dd_status['drawdown'] * 100,  # Convert to percentage
            'open_positions': len(positions),
            'positions': positions[:5],  # Latest 5
            'bot_status': 'PAUSED' if bot.paused else 'ACTIVE',
            'circuit_breaker': bot.risk_manager.circuit_breaker_enabled and dd_status['circuit_breaker_triggered'],
            'trades_today': state_stats['trades_today'],
            'trades_total': state_stats['trades_total'],
            'today_pnl': today_pnl,
            'win_rate': win_rate,
            'bot_uptime': state_stats['bot_uptime'],
            'closed_positions': closed_today[:10]  # Latest 10
        }
    except Exception as e:
        logger.error(f"Error getting bot metrics: {e}")
        return None


@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('dashboard.html')


@app.route('/api/metrics')
def api_metrics():
    """API endpoint for bot metrics"""
    metrics = get_bot_metrics()
    if metrics:
        return jsonify(metrics)
    else:
        return jsonify({'error': 'Bot not connected'}), 503


@app.route('/api/health')
def api_health():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'bot_connected': _bot_instance is not None
    })


def start_dashboard(bot, host='0.0.0.0', port=8080):
    """Start dashboard server in background thread"""
    set_bot_instance(bot)

    def run_server():
        logger.info(f"🌐 Dashboard starting on http://{host}:{port}")
        app.run(host=host, port=port, debug=False, use_reloader=False)

    dashboard_thread = threading.Thread(target=run_server, daemon=True)
    dashboard_thread.start()

    logger.info(f"✅ Dashboard available at http://localhost:{port}")


if __name__ == '__main__':
    # For standalone testing
    app.run(host='0.0.0.0', port=8080, debug=True)
