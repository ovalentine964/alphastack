#!/bin/bash
# AlphaStack Backend + Tunnel Monitor
# Keeps server and tunnel alive 24/7

LOG_DIR="/home/work/.openclaw/workspace/alphastack/logs"
mkdir -p "$LOG_DIR"

SERVER_PID=""
TUNNEL_PID=""
TUNNEL_URL=""

start_server() {
    cd /home/work/.openclaw/workspace/alphastack
    BINANCE_API_KEY="RMO3Gq…Wrth" \
    BINANCE_API_SECRET="f7Bkyk…sfUV" \
    python3 live_server.py >> "$LOG_DIR/server.log" 2>&1 &
    SERVER_PID=$!
    echo "[$(date)] Server started: PID $SERVER_PID"
}

start_tunnel() {
    ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=30 -o ServerAliveCountMax=3 \
        -R 80:localhost:8000 serveo.net > "$LOG_DIR/tunnel.log" 2>&1 &
    TUNNEL_PID=$!
    sleep 6
    TUNNEL_URL=$(grep -o 'https://[^[:space:]]*serveousercontent.com' "$LOG_DIR/tunnel.log" | head -1)
    echo "[$(date)] Tunnel started: PID $TUNNEL_PID → $TUNNEL_URL"
}

check_server() {
    if ! kill -0 "$SERVER_PID" 2>/dev/null; then
        echo "[$(date)] Server died! Restarting..."
        start_server
        sleep 3
        return 1
    fi
    if ! curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        echo "[$(date)] Server unhealthy! Restarting..."
        kill "$SERVER_PID" 2>/dev/null
        start_server
        sleep 3
        return 1
    fi
    return 0
}

check_tunnel() {
    if ! kill -0 "$TUNNEL_PID" 2>/dev/null; then
        echo "[$(date)] Tunnel died! Restarting..."
        start_tunnel
        return 1
    fi
    # Test if tunnel is actually reachable
    if [ -n "$TUNNEL_URL" ] && ! curl -sf "$TUNNEL_URL/health" > /dev/null 2>&1; then
        echo "[$(date)] Tunnel unreachable! Restarting..."
        kill "$TUNNEL_PID" 2>/dev/null
        start_tunnel
        return 1
    fi
    return 0
}

save_status() {
    local btc=$(curl -sf http://localhost:8000/health 2>/dev/null | python3 -c "import json,sys; print(f'\${json.load(sys.stdin).get(\"btc_price\",0):,.2f}')" 2>/dev/null || echo "N/A")
    cat > "$LOG_DIR/status.json" << EOF
{
    "server_pid": $SERVER_PID,
    "tunnel_pid": $TUNNEL_PID,
    "tunnel_url": "$TUNNEL_URL",
    "btc_price": "$btc",
    "last_check": "$(date -Iseconds)",
    "uptime_since": "$(date -Iseconds)"
}
EOF
}

echo "=== AlphaStack 24/7 Monitor Starting ==="
start_server
sleep 3
start_tunnel
save_status

echo "[$(date)] Monitor loop started. URL: $TUNNEL_URL"

while true; do
    sleep 60  # Check every 60 seconds
    
    if ! check_server; then
        sleep 3
        check_tunnel
        save_status
        continue
    fi
    
    check_tunnel
    save_status
done
