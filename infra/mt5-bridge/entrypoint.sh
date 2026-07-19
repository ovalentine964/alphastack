#!/bin/bash
# =============================================================================
# AlphaStack MT5 Bridge — Entrypoint
# =============================================================================
# Starts: Xvfb (virtual display) + x11vnc (VNC) + noVNC (web) + MT5 + Bridge
# =============================================================================
set -e

export WINEPREFIX="${WINEPREFIX:-/config/.wine}"
export MT5_PORT="${MT5_PORT:-8001}"
export API_PORT="${API_PORT:-8080}"
export VNC_PORT="${VNC_PORT:-3000}"
export VNC_PASSWORD="${VNC_PASSWORD:-changeme}"

echo "=== AlphaStack MT5 Bridge v1.1.0 ==="
echo "  API_PORT=${API_PORT}"
echo "  VNC_PORT=${VNC_PORT}"
echo "  WINEPREFIX=${WINEPREFIX}"

mkdir -p "${WINEPREFIX}" /var/log/supervisor

# Generate supervisor config
cat > /etc/supervisor/conf.d/supervisord.conf << SUPEREOF
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

[program:bridge]
command=python3 /app/bridge_api.py
directory=/app
autorestart=true
environment=DISPLAY=":1",PYTHONUNBUFFERED="1",WINEPREFIX="/config/.wine"
stdout_logfile=/var/log/supervisor/bridge.log
stderr_logfile=/var/log/supervisor/bridge.err
SUPEREOF

echo "Starting supervisord..."
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
