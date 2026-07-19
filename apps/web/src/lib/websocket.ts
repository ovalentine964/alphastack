/**
 * WebSocket client for AlphaStack real-time data.
 *
 * Server protocol (requires auth):
 *   1. Connect
 *   2. Send: {"type": "auth", "token": "<jwt>"}
 *   3. Receive: {"type": "auth_ok", "user_id": "...", "email": "..."}
 *   4. Subscribe: {"type": "subscribe", "channels": ["prices", "trades", "signals"]}
 *   5. Receive broadcasts: {"channel": "prices", "data": {...}, "ts": ...}
 *
 * Heartbeat: server sends {"type": "heartbeat"} every 30s.
 *   Client should respond with {"type": "ping"}.
 */

import type { WSChannel, WSMessage, WSBroadcastMessage } from "@/types";

type Listener = (msg: WSMessage) => void;
type ConnectionState = "disconnected" | "connecting" | "authenticating" | "connected";

const MAX_RECONNECT_ATTEMPTS = 10;
const BASE_RECONNECT_DELAY = 2000;

class WSClient {
  private ws: WebSocket | null = null;
  private listeners: Set<Listener> = new Set();
  private stateListeners: Set<(state: ConnectionState) => void> = new Set();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectAttempts = 0;
  private url: string;
  private _subscribedChannels: Set<WSChannel> = new Set();
  private _state: ConnectionState = "disconnected";
  private _token: string | null = null;
  private _heartbeatTimer: ReturnType<typeof setInterval> | null = null;

  constructor() {
    const proto =
      typeof window !== "undefined" && window.location.protocol === "https:"
        ? "wss"
        : "ws";
    this.url =
      typeof window !== "undefined"
        ? `${proto}://${window.location.host}/ws`
        : "ws://localhost:8000/ws";
  }

  get connectionState(): ConnectionState {
    return this._state;
  }

  get isConnected(): boolean {
    return this._state === "connected";
  }

  /** Set the JWT token for authentication. Call before connect(). */
  setToken(token: string | null) {
    this._token = token;
  }

  connect() {
    if (this.ws?.readyState === WebSocket.OPEN) return;
    if (this._state === "connecting" || this._state === "authenticating") return;

    this._setState("connecting");

    try {
      this.ws = new WebSocket(this.url);
    } catch {
      this._setState("disconnected");
      this.scheduleReconnect();
      return;
    }

    this.ws.onopen = () => {
      console.log("[WS] connected, authenticating…");
      this._setState("authenticating");
      this.reconnectAttempts = 0;
      if (this.reconnectTimer) {
        clearTimeout(this.reconnectTimer);
        this.reconnectTimer = null;
      }

      // Send auth message immediately
      if (this._token) {
        this.send({ type: "auth", token: this._token });
      } else {
        console.warn("[WS] no token set, sending anonymous auth");
        this.send({ type: "auth", token: "" });
      }
    };

    this.ws.onmessage = (event) => {
      try {
        const raw = JSON.parse(event.data as string);

        // Handle auth response
        if (raw.type === "auth_ok") {
          console.log("[WS] authenticated as", raw.email || raw.user_id);
          this._setState("connected");
          // Re-subscribe to channels after reconnect
          if (this._subscribedChannels.size > 0) {
            this.send({
              type: "subscribe",
              channels: Array.from(this._subscribedChannels),
            });
          }
          this._startHeartbeat();
          return;
        }

        if (raw.type === "auth_error") {
          console.error("[WS] auth failed:", raw.detail);
          this.ws?.close();
          return;
        }

        // Handle heartbeat from server
        if (raw.type === "heartbeat") {
          this.send({ type: "ping" });
          return;
        }

        // Normalise broadcast vs control messages
        const msg: WSMessage =
          raw.channel && raw.data
            ? {
                type: raw.channel,
                data: raw.data,
                ts: raw.ts,
              } as WSBroadcastMessage
            : { type: raw.type ?? "unknown", data: raw.data ?? {}, ts: raw.ts };

        this.listeners.forEach((fn) => fn(msg));
      } catch {
        // ignore malformed messages
      }
    };

    this.ws.onclose = () => {
      console.log("[WS] disconnected");
      this._stopHeartbeat();
      this._setState("disconnected");
      this.scheduleReconnect();
    };

    this.ws.onerror = () => {
      this.ws?.close();
    };
  }

  private _setState(state: ConnectionState) {
    this._state = state;
    this.stateListeners.forEach((fn) => fn(state));
  }

  private _startHeartbeat() {
    this._stopHeartbeat();
    // Client-side keepalive ping every 25s (server pings at 30s)
    this._heartbeatTimer = setInterval(() => {
      this.ping();
    }, 25_000);
  }

  private _stopHeartbeat() {
    if (this._heartbeatTimer) {
      clearInterval(this._heartbeatTimer);
      this._heartbeatTimer = null;
    }
  }

  private scheduleReconnect() {
    if (this.reconnectTimer) return;
    if (this.reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      console.warn("[WS] max reconnect attempts reached");
      return;
    }
    const delay = BASE_RECONNECT_DELAY * Math.pow(2, this.reconnectAttempts);
    this.reconnectAttempts++;
    console.log(
      `[WS] reconnecting in ${delay / 1000}s (attempt ${this.reconnectAttempts})…`
    );
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, delay);
  }

  /** Subscribe to server channels. */
  subscribeChannels(channels: WSChannel[]) {
    channels.forEach((c) => this._subscribedChannels.add(c));
    if (this._state === "connected") {
      this.send({ type: "subscribe", channels });
    }
  }

  /** Unsubscribe from server channels. */
  unsubscribeChannels(channels: WSChannel[]) {
    channels.forEach((c) => this._subscribedChannels.delete(c));
    if (this._state === "connected") {
      this.send({ type: "unsubscribe", channels });
    }
  }

  /** Register a message listener. Returns unsubscribe function. */
  subscribe(fn: Listener): () => void {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  /** Register a connection state listener. Returns unsubscribe function. */
  onStateChange(fn: (state: ConnectionState) => void): () => void {
    this.stateListeners.add(fn);
    return () => this.stateListeners.delete(fn);
  }

  send(data: unknown) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }

  /** Send a ping to keep the connection alive. */
  ping() {
    this.send({ type: "ping" });
  }

  disconnect() {
    this._stopHeartbeat();
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.reconnectAttempts = MAX_RECONNECT_ATTEMPTS; // prevent reconnect
    this._subscribedChannels.clear();
    this._token = null;
    this.ws?.close();
    this.ws = null;
    this._setState("disconnected");
  }
}

export const wsClient = new WSClient();
