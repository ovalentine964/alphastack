import type { WSMessage, WSPriceUpdate, PipelineSignal, Trade } from "./types";

type Listener = (msg: WSMessage) => void;
type PriceListener = (update: WSPriceUpdate) => void;
type SignalListener = (signal: PipelineSignal) => void;
type TradeListener = (trade: Trade) => void;

export type ConnectionStatus = "connected" | "disconnected" | "reconnecting";
type StatusListener = (status: ConnectionStatus) => void;

/**
 * WebSocket client for real-time AlphaStack data.
 *
 * Protocol (from live_server.py /ws endpoint):
 *   → Client sends: { type: "subscribe", channels: [...] }
 *   ← Server sends: { type: "connected", data: { message } }
 *   ← Server sends: { type: "price_update", data: WSPriceUpdate }
 *   ← Server sends: { type: "signal_new", data: PipelineSignal }
 *   ← Server sends: { type: "trade_executed", data: Trade }
 *   ← Server sends: { type: "portfolio_update", data: {...} }
 *
 * The server requires a JWT token passed as ?token= query param.
 */
class WebSocketClient {
  private ws: WebSocket | null = null;
  private listeners: Set<Listener> = new Set();
  private priceListeners: Set<PriceListener> = new Set();
  private signalListeners: Set<SignalListener> = new Set();
  private tradeListeners: Set<TradeListener> = new Set();
  private statusListeners: Set<StatusListener> = new Set();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 20;
  private _status: ConnectionStatus = "disconnected";
  private _url = "ws://localhost:8000/ws";
  private _token: string | null = null;
  private _subscribedChannels: string[] = [];

  get status(): ConnectionStatus {
    return this._status;
  }

  setUrl(url: string): void {
    this._url = url;
  }

  setToken(token: string | null): void {
    this._token = token;
  }

  connect(token?: string): void {
    if (this.ws?.readyState === WebSocket.OPEN) return;

    const authToken = token || this._token;
    if (!authToken) {
      console.warn("[WS] no auth token — skipping connect");
      return;
    }

    const url = `${this._url}?token=${encodeURIComponent(authToken)}`;

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
      if (this._subscribedChannels.length > 0) {
        this.send({
          type: "subscribe",
          channels: this._subscribedChannels,
        });
      }
    };

    this.ws.onmessage = (event) => {
      try {
        const msg: WSMessage = JSON.parse(event.data);
        if (msg.type === "pong") return;

        // Dispatch to typed listeners
        this.dispatchTyped(msg);

        // Dispatch to generic listeners
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

  private dispatchTyped(msg: WSMessage): void {
    if (!msg.data) return;

    switch (msg.type) {
      case "price_update":
        this.priceListeners.forEach((fn) => fn(msg.data as WSPriceUpdate));
        break;
      case "signal_new":
      case "signal_update":
        this.signalListeners.forEach((fn) => fn(msg.data as PipelineSignal));
        break;
      case "trade_executed":
      case "trade_updated":
        this.tradeListeners.forEach((fn) => fn(msg.data as Trade));
        break;
    }
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

  // ── Generic listener ─────────────────────────────────────

  subscribe(fn: Listener): () => void {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  // ── Typed listeners ──────────────────────────────────────

  onPriceUpdate(fn: PriceListener): () => void {
    this.priceListeners.add(fn);
    return () => this.priceListeners.delete(fn);
  }

  onSignal(fn: SignalListener): () => void {
    this.signalListeners.add(fn);
    return () => this.signalListeners.delete(fn);
  }

  onTrade(fn: TradeListener): () => void {
    this.tradeListeners.add(fn);
    return () => this.tradeListeners.delete(fn);
  }

  onStatusChange(fn: StatusListener): () => void {
    this.statusListeners.add(fn);
    return () => this.statusListeners.delete(fn);
  }

  // ── Channel subscriptions ────────────────────────────────

  subscribeChannels(channels: string[]): void {
    this._subscribedChannels = channels;
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
    this.maxReconnectAttempts = 0;
    this.ws?.close();
    this.ws = null;
    this.setStatus("disconnected");
  }
}

export const wsClient = new WebSocketClient();
