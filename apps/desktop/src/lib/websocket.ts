import type { WSMessage, Position, Signal, Trade, Portfolio } from "./types";

type Listener = (msg: WSMessage) => void;

export type ConnectionStatus = "connected" | "disconnected" | "reconnecting";

type StatusListener = (status: ConnectionStatus) => void;

/**
 * WebSocket client for real-time trading data.
 * Handles reconnection with exponential backoff, heartbeat, and channel subscriptions.
 */
class WebSocketClient {
  private ws: WebSocket | null = null;
  private listeners: Set<Listener> = new Set();
  private statusListeners: Set<StatusListener> = new Set();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 20;
  private subscribedChannels: string[] = [];
  private _status: ConnectionStatus = "disconnected";
  private _url = "ws://localhost:8000/ws";

  get status(): ConnectionStatus {
    return this._status;
  }

  setUrl(url: string): void {
    this._url = url;
  }

  connect(token?: string): void {
    if (this.ws?.readyState === WebSocket.OPEN) return;

    const url = token ? `${this._url}?token=${token}` : this._url;

    try {
      this.ws = new WebSocket(url);
    } catch {
      this.scheduleReconnect();
      return;
    }

    this.ws.onopen = () => {
      console.log("[WS] connected");
      this.reconnectAttempts = 0;
      this.setStatus("connected");
      this.startHeartbeat();

      // Re-subscribe to channels after reconnect
      if (this.subscribedChannels.length > 0) {
        this.send({
          type: "subscribe",
          channels: this.subscribedChannels,
        });
      }
    };

    this.ws.onmessage = (event) => {
      try {
        const msg: WSMessage = JSON.parse(event.data);
        // Ignore pong responses
        if (msg.type === "pong") return;
        this.listeners.forEach((fn) => fn(msg));
      } catch {
        // ignore malformed messages
      }
    };

    this.ws.onclose = () => {
      console.log("[WS] disconnected");
      this.stopHeartbeat();
      this.setStatus("disconnected");
      this.scheduleReconnect();
    };

    this.ws.onerror = () => {
      this.ws?.close();
    };
  }

  private setStatus(status: ConnectionStatus): void {
    this._status = status;
    this.statusListeners.forEach((fn) => fn(status));
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.heartbeatTimer = setInterval(() => {
      this.send({ type: "ping" });
    }, 30_000);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) return;
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.warn("[WS] max reconnect attempts reached");
      return;
    }

    this.setStatus("reconnecting");
    const delay = Math.min(2000 * Math.pow(2, this.reconnectAttempts), 60_000);
    // Add jitter ±25%
    const jitter = delay * (0.75 + Math.random() * 0.5);
    this.reconnectAttempts++;

    console.log(
      `[WS] reconnecting in ${Math.round(jitter / 1000)}s (attempt ${this.reconnectAttempts})`
    );

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, jitter);
  }

  subscribe(fn: Listener): () => void {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  onStatusChange(fn: StatusListener): () => void {
    this.statusListeners.add(fn);
    return () => this.statusListeners.delete(fn);
  }

  subscribeChannels(channels: string[]): void {
    this.subscribedChannels = channels;
    this.send({ type: "subscribe", channels });
  }

  send(data: unknown): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }

  disconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.stopHeartbeat();
    this.maxReconnectAttempts = 0; // prevent auto-reconnect
    this.ws?.close();
    this.ws = null;
    this.setStatus("disconnected");
  }
}

export const wsClient = new WebSocketClient();
