#!/bin/bash
# Kalshi Hybrid Bot - PM2 Control Script

BOT_NAME="kalshi-hybrid-bot"
BOT_DIR="/root/kalshi_hybrid_bot"

cd "$BOT_DIR" || exit 1

case "$1" in
    start)
        echo "🚀 Starting Kalshi Hybrid Bot..."
        pm2 start ecosystem.config.js
        echo ""
        echo "✅ Bot started!"
        echo ""
        echo "Useful commands:"
        echo "  ./bot-control.sh status    - Check bot status"
        echo "  ./bot-control.sh logs      - View live logs"
        echo "  ./bot-control.sh stop      - Stop the bot"
        ;;

    stop)
        echo "🛑 Stopping Kalshi Hybrid Bot..."
        pm2 stop $BOT_NAME
        echo "✅ Bot stopped"
        ;;

    restart)
        echo "🔄 Restarting Kalshi Hybrid Bot..."
        pm2 restart $BOT_NAME
        echo "✅ Bot restarted"
        ;;

    status)
        echo "📊 Bot Status:"
        echo ""
        pm2 status $BOT_NAME
        ;;

    logs)
        echo "📜 Live Logs (Ctrl+C to exit):"
        echo ""
        pm2 logs $BOT_NAME --lines 50
        ;;

    errors)
        echo "❌ Error Logs:"
        echo ""
        tail -100 logs/pm2-error.log
        ;;

    info)
        echo "ℹ️  Bot Information:"
        echo ""
        pm2 info $BOT_NAME
        ;;

    monitor)
        echo "📈 Opening PM2 Monitor..."
        pm2 monit
        ;;

    delete)
        echo "🗑️  Deleting bot from PM2..."
        pm2 delete $BOT_NAME
        echo "✅ Bot deleted from PM2"
        ;;

    save)
        echo "💾 Saving PM2 process list..."
        pm2 save
        echo "✅ PM2 configuration saved"
        echo ""
        echo "To auto-start on reboot:"
        echo "  pm2 startup"
        echo "  (follow the instructions)"
        ;;

    *)
        echo "Kalshi Hybrid Bot - Control Script"
        echo ""
        echo "Usage: ./bot-control.sh [command]"
        echo ""
        echo "Commands:"
        echo "  start      - Start the bot"
        echo "  stop       - Stop the bot"
        echo "  restart    - Restart the bot"
        echo "  status     - Show bot status"
        echo "  logs       - View live logs"
        echo "  errors     - View error logs"
        echo "  info       - Show detailed info"
        echo "  monitor    - Open PM2 monitor"
        echo "  delete     - Remove from PM2"
        echo "  save       - Save PM2 config"
        echo ""
        echo "Quick Start:"
        echo "  1. ./bot-control.sh start"
        echo "  2. ./bot-control.sh logs"
        echo ""
        ;;
esac
