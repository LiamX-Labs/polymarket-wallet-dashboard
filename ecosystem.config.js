module.exports = {
  apps: [
    {
      name: 'polymarket-tracker',
      script: './run-tracker.sh',
      cwd: '/home/william/polymarket-wallet-dashboard',
      interpreter: '/bin/bash',
      autorestart: true,
      watch: false,
      max_memory_restart: '500M',
      env: {
        NODE_ENV: 'production',
      },
      error_file: './logs/tracker-error.log',
      out_file: './logs/tracker-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
    },
    {
      name: 'polymarket-dashboard-server',
      script: 'npm',
      args: 'run dev',
      cwd: '/home/william/polymarket-wallet-dashboard/server',
      autorestart: true,
      watch: false,
      max_memory_restart: '300M',
      env: {
        NODE_ENV: 'production',
      },
      error_file: './logs/server-error.log',
      out_file: './logs/server-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
    },
    {
      name: 'polymarket-dashboard-client',
      script: 'npm',
      args: 'run dev',
      cwd: '/home/william/polymarket-wallet-dashboard/client',
      autorestart: true,
      watch: false,
      env: {
        NODE_ENV: 'development',
      },
      error_file: './logs/client-error.log',
      out_file: './logs/client-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
    },
  ],
};
