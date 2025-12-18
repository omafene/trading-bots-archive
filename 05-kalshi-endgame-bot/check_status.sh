#!/bin/bash

echo "=============================="
echo "Kalshi Bot Status Check"
echo "Date: $(date)"
echo "=============================="

# Check if service is running
echo -e "\n[Service Status]"
systemctl is-active kalshi-bot

# Check recent positions
echo -e "\n[Recent Activity (last 10 lines)]"
tail -10 ~/kalshi_bot/logs/kalshi_bot.log

# Check disk space
echo -e "\n[Disk Space]"
df -h /

# Check memory
echo -e "\n[Memory Usage]"
free -h

echo -e "\n=============================="
