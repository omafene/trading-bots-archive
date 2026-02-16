#!/bin/bash
# Quick start script for Kalshi Hybrid Bot

cd "$(dirname "$0")"

echo "🚀 Starting Kalshi Hybrid Bot..."
echo ""

# Check dependencies
if ! python3 -c "import yaml, numpy, requests" 2>/dev/null; then
    echo "⚠️  Installing dependencies..."
    pip3 install -q -r requirements.txt
    echo "✅ Dependencies installed"
    echo ""
fi

# Check config
if [ ! -f ".env" ]; then
    echo "⚠️  No .env file found"
    echo "   Copy .env.example to .env and configure your API keys"
    exit 1
fi

# Run bot
python3 src/hybrid_bot.py
