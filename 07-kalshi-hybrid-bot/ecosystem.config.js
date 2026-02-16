module.exports = {
  apps: [{
    name: 'kalshi-hybrid-bot',
    script: 'src/hybrid_bot.py',
    interpreter: 'python3',
    cwd: '/root/kalshi_hybrid_bot',

    // Environment
    env: {
      PYTHONUNBUFFERED: '1',
      PYTHONPATH: '/root/kalshi_hybrid_bot/src'
    },

    // Logging
    output: './logs/pm2-out.log',
    error: './logs/pm2-error.log',
    log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
    combine_logs: true,

    // Process management
    instances: 1,
    autorestart: true,
    watch: false,
    max_memory_restart: '500M',

    // Restart settings
    min_uptime: '10s',
    max_restarts: 10,
    restart_delay: 5000,

    // Advanced
    kill_timeout: 5000,
    listen_timeout: 3000,

    // Cron restart (optional - restart daily at 3 AM)
    // cron_restart: '0 3 * * *',
  }]
};
