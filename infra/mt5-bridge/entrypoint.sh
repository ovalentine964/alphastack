#!/bin/bash
set -e

export WINEPREFIX="${WINEPREFIX:-/config/.wine}"
export MT5_PORT="${MT5_PORT:-8001}"
export API_PORT="${API_PORT:-8000}"
export VNC_PORT="${VNC_PORT:-3000}"
export VNC_PASSWORD="${VNC_PASSWORD:-changeme}"

echo "=== MT5 Docker API + AlphaStack Bridge Starting ==="

mkdir -p "${WINEPREFIX}" /var/log/supervisor

cat > /etc/supervisor/conf.d/supervisord.conf << 'EOF'
[supervisord]
nodaemon=true
user=root

[program:xvfb]
command=/usr/bin/Xvfb :1 -screen 0 1024x768x16
autorestart=true
stdout_logfile=/var/log/supervisor/xvfb.log
stderr_logfile=/var/log/supervisor/xvfb.err

[program:x11vnc]
command=/usr/bin/x11vnc -display :1 -forever -shared -passwd %(ENV_VNC_PASSWORD)s
autorestart=true
startretries=10
stdout_logfile=/var/log/supervisor/x11vnc.log
stderr_logfile=/var/log/supervisor/x11vnc.err

[program:novnc]
command=/usr/bin/websockify --web=/usr/share/novnc/ %(ENV_VNC_PORT)s localhost:5900
autorestart=true
stdout_logfile=/var/log/supervisor/novnc.log
stderr_logfile=/var/log/supervisor/novnc.err

[program:mt5]
command=python3 /app/Metatrader/start.py
autorestart=true
environment=DISPLAY=":1",PYTHONUNBUFFERED="1"
stdout_logfile=/var/log/supervisor/mt5.log
stderr_logfile=/var/log/supervisor/mt5.err

[program:api]
command=python3 -m uvicorn src.api.main:app --host 0.0.0.0 --port %(ENV_API_PORT)s
directory=/app
autorestart=true
environment=PYTHONUNBUFFERED="1"
stdout_logfile=/var/log/supervisor/api.log
stderr_logfile=/var/log/supervisor/api.err

[program:bridge]
command=python3 /app/bridge_api.py
directory=/app
autorestart=true
environment=DISPLAY=":1",PYTHONUNBUFFERED="1",WINEPREFIX="/config/.wine"
stdout_logfile=/var/log/supervisor/bridge.log
stderr_logfile=/var/log/supervisor/bridge.err
EOF

echo "Starting supervisor..."
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
