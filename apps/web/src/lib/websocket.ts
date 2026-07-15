/**
 * WebSocket client for AlphaStack real-time data.
 *
 * Server protocol:
 *   Client → Server: {"type": "subscribe", "channels": ["prices", "trades", "signals"]}
 *                    {"type": "unsubscribe", "channels": ["prices"]}
 *                    {"type": "ping"}
 *   Server → Client: {"channel": "prices", "data": {...}, "ts": ...}   (broadcast)
 *                    {"type": "subscribed", "channels": [...]}         (control)
 *                    {"type": "pong", "ts": ...}                       (heartbeat)
 */

export type WSMessage = {
  /** Normalised message type — either a control type or channel name */
  type: string;
  data: unknown;
  ts?: number;
};

type Listener = (msg: WSMessage) => void;

const MAX_RECONNECT_ATTEMPTS = 10;
const BASE_RECONNECT_DELAY = 2000; // 2s, exponential backoff

class WSClient {
  private ws: WebSocket | null = null;
  private listeners: Set<Listener> = new Set();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectAttempts = 0;
  private url: string;
  private _subscribedChannels: Set<string> = new Set();

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

  connect() {
    if (this.ws?.readyState === WebSocket.OPEN) return;

    this.ws = new WebSocket(this.url);

    this.ws.onopen = () => {
      console.log("[WS] connected");
      this.reconnectAttempts = 0;
      if (this.reconnectTimer) {
        clearTimeout(this.reconnectTimer);
        this.reconnectTimer = null;
      }
      // Re-subscribe to channels after reconnect
      if (this._subscribedChannels.size > 0) {
        this.send({
          type: "subscribe",
          channels: Array.from(this._subscribedChannels),
        });
      }
    };

    this.ws.onmessage = (event) => {
      try {
        const raw = JSON.parse(event.data);
        // Normalise server message format:
        //   broadcast: {channel, data, ts}
        //   control:   {type, ...}
        const msg: WSMessage =
          raw.channel && raw.data
            ? { type: raw.channel, data: raw.data, ts: raw.ts }
            : { type: raw.type ?? "unknown", data: raw.data ?? {}, ts: raw.ts };
        this.listeners.forEach((fn) => fn(msg));
      } catch {
        // ignore malformed messages
      }
    };

    this.ws.onclose = () => {
      console.log("[WS] disconnected");
      this.scheduleReconnect();
    };

    this.ws.onerror = () => {
      this.ws?.close();
    };
  }

  private scheduleReconnect() {
    if (this.reconnectTimer) return;
    if (this.reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      console.warn("[WS] max reconnect attempts reached");
      return;
    }
    const delay = BASE_RECONNECT_DELAY * Math.pow(2, this.reconnectAttempts);
    this.reconnectAttempts++;
    console.log(`[WS] reconnecting in ${delay / 1000}s (attempt ${this.reconnectAttempts})…`);
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, delay);
  }

  /** Subscribe to server channels. */
  subscribeChannels(channels: string[]) {
    channels.forEach((c) => this._subscribedChannels.add(c));
    this.send({ type: "subscribe", channels });
  }

  /** Unsubscribe from server channels. */
  unsubscribeChannels(channels: string[]) {
    channels.forEach((c) => this._subscribedChannels.delete(c));
    this.send({ type: "unsubscribe", channels });
  }

  /** Register a message listener. Returns unsubscribe function. */
  subscribe(fn: Listener): () => void {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
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
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.reconnectAttempts = MAX_RECONNECT_ATTEMPTS; // prevent reconnect
    this._subscribedChannels.clear();
    this.ws?.close();
    this.ws = null;
  }
}

export const wsClient = new WSClient();
