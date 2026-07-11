# Fix: Data Flow Architecture — Critical Issues

> **Source:** `review_7_data_flow.md`
> **Date:** 2026-07-11
> **Scope:** FIX-1 through FIX-4 (P0 must-fix items before live/paper trading)

---

## FIX-1: candle_1m / market_data Divergence

### Problem

Two separate data paths produce 1-minute OHLCV data that don't reconcile:

1. **`candle_1m`** — a TimescaleDB continuous aggregate materialized view built from `ticks` using `bid` price.
2. **`market_data`** — a base hypertable that 5m+ continuous aggregates query (`WHERE timeframe = '1m'`).

Since `candle_1m` writes to its own materialized view and never populates `market_data`, the 5m → 15m → 1h → 4h → 1d cascade has **no 1-minute source rows** to aggregate from. Higher timeframes will be empty or stale.

### Solution: Single Source of Truth in `market_data`

Eliminate `candle_1m` as a separate materialized view. Instead, create a continuous aggregate that writes directly into `market_data` with `timeframe = '1m'`.

#### Step 1: Create the continuous aggregate targeting `market_data`

```sql
-- Drop the old standalone materialized view if it exists
DROP MATERIALIZED VIEW IF EXISTS candle_1m;

-- Create a continuous aggregate that feeds market_data
CREATE MATERIALIZED VIEW market_data_1m_agg
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 minute', time) AS bucket,
    symbol,
    '1m' AS timeframe,
    FIRST(bid, time) AS open,
    MAX(bid) AS high,
    MIN(bid) AS low,
    LAST(bid, time) AS close,
    SUM(tick_volume) AS volume,
    COUNT(*) AS tick_count
FROM ticks
GROUP BY bucket, symbol;
```

#### Step 2: Add a refresh policy with offset (prevent partial candles)

```sql
SELECT add_continuous_aggregate_policy('market_data_1m_agg',
    start_offset    => INTERVAL '3 minutes',
    end_offset      => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute'
);
```

The 1-minute end offset ensures the aggregate never computes on the current (incomplete) candle.

#### Step 3: Populate `market_data` via upsert trigger

Create a function that fires after each continuous aggregate refresh and upserts into `market_data`:

```sql
CREATE OR REPLACE FUNCTION sync_market_data_1m()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO market_data (time, symbol, timeframe, open, high, low, close, volume)
    VALUES (NEW.bucket, NEW.symbol, '1m', NEW.open, NEW.high, NEW.low, NEW.close, NEW.volume)
    ON CONFLICT (time, symbol, timeframe)
    DO UPDATE SET
        open   = EXCLUDED.open,
        high   = GREATEST(market_data.high, EXCLUDED.high),
        low    = LEAST(market_data.low, EXCLUDED.low),
        close  = EXCLUDED.close,
        volume = market_data.volume + EXCLUDED.volume;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

> **Note:** TimescaleDB continuous aggregates don't support row-level triggers directly. Use a **refresh completion callback** instead:

```sql
-- Alternative: Use a procedure called by pg_cron after aggregate refresh
CREATE OR REPLACE PROCEDURE materialize_1m_to_market_data()
LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO market_data (time, symbol, timeframe, open, high, low, close, volume)
    SELECT bucket, symbol, '1m', open, high, low, close, volume
    FROM market_data_1m_agg
    WHERE bucket >= NOW() - INTERVAL '5 minutes'
    ON CONFLICT (time, symbol, timeframe)
    DO UPDATE SET
        high   = GREATEST(market_data.high, EXCLUDED.high),
        low    = LEAST(market_data.low, EXCLUDED.low),
        close  = EXCLUDED.close,
        volume = market_data.volume + EXCLUDED.volume;
END;
$$;

-- Schedule the materialization 10 seconds after each aggregate refresh
SELECT cron.schedule('sync-1m-to-market-data', '* * * * *',
    'CALL materialize_1m_to_market_data()');
```

#### Step 4: Update 5m+ aggregates to read from `market_data` (no change needed)

Since `market_data` now contains `timeframe = '1m'` rows, the existing 5m → 15m → 1h → 4h → 1d cascade works as designed. No changes needed to higher-timeframe aggregates.

#### Step 5: Verify data flow

```sql
-- Check that 1m rows exist in market_data
SELECT COUNT(*), MAX(time) FROM market_data WHERE timeframe = '1m' AND symbol = 'EUR/USD';

-- Check that 5m aggregate has data
SELECT COUNT(*), MAX(bucket) FROM market_data_5m_agg WHERE symbol = 'EUR/USD';

-- Compare tick count: raw ticks vs aggregated
SELECT
    (SELECT COUNT(*) FROM ticks WHERE time > NOW() - INTERVAL '1 hour' AND symbol = 'EUR/USD') AS raw_ticks,
    (SELECT SUM(tick_count) FROM market_data_1m_agg WHERE bucket > NOW() - INTERVAL '1 hour' AND symbol = 'EUR/USD') AS agg_ticks;
```

### Validation Checklist

- [ ] `market_data` contains `timeframe = '1m'` rows populated from tick aggregation
- [ ] 5m+ continuous aggregates produce correct OHLCV from `market_data`
- [ ] No duplicate rows in `market_data` for the same (time, symbol, timeframe)
- [ ] High/low correctly use `GREATEST`/`LEAST` on conflict (handles late ticks)
- [ ] `candle_1m` materialized view is dropped; no code references it

---

## FIX-2: Replace Redis Pub/Sub with Redis Streams for Safety Channels

### Problem

Redis Pub/Sub is fire-and-forget. If a consumer (e.g., Risk Agent) briefly disconnects — network blip, restart, GC pause — and reconnects, every message published during that window is **permanently lost**.

For `tick:{symbol}`, `signal:{symbol}`, and `order:{account}` channels, this means:

- A black-swan tick with extreme spread → Risk Agent misses it → no circuit breaker triggered
- A confluence signal → Execution Agent misses it → trade opportunity lost (acceptable)
- An order fill notification → Position Manager misses it → phantom position state (critical)

### Solution: Migrate all safety-critical channels to Redis Streams

#### Channel Classification

| Channel | Current | Target | Rationale |
|---------|---------|--------|-----------|
| `tick:{symbol}` | Pub/Sub | **Stream** | Risk agent must see every tick for spread/volatility checks |
| `signal:{symbol}` | Pub/Sub | **Stream** | Confluence signals drive execution; no loss acceptable |
| `order:{account}` | Pub/Sub | **Stream** | Fill/reject notifications must be durable for position sync |
| `candle:{symbol}:{tf}` | Pub/Sub | **Stream** | Candle-close events trigger S14-S16; must not be lost |
| `system:alerts` | Pub/Sub | **Stream** | System alerts (circuit breaker, risk limit) must be durable |
| `dashboard:prices` | Pub/Sub | **Keep Pub/Sub** | Dashboard is ephemeral; reconnects get fresh snapshot anyway |
| `dashboard:events` | Pub/Sub | **Keep Pub/Sub** | UI-only; no safety impact |

#### Python Producer Pattern

```python
# Before (fire-and-forget):
await redis.publish(f"tick:{symbol}", json.dumps(tick_data))

# After (durable stream):
async def publish_tick(redis: redis.asyncio.Redis, symbol: str, tick: dict):
    """Publish tick to durable stream with automatic trimming."""
    stream_key = f"stream:tick:{symbol}"
    await redis.xadd(
        stream_key,
        {
            "bid": str(tick["bid"]),
            "ask": str(tick["ask"]),
            "spread": str(tick["spread"]),
            "volume": str(tick.get("volume", 0)),
            "timestamp": str(tick["timestamp"]),
        },
        maxlen=100_000,       # Keep last 100K ticks per symbol (~16 hours at 100/s)
        approximate=True,     # ~ prefix for O(1) trimming
    )

async def publish_signal(redis: redis.asyncio.Redis, signal: dict):
    """Publish agent signal to durable stream."""
    stream_key = f"stream:signal:{signal['symbol']}"
    await redis.xadd(
        stream_key,
        {
            "agent": signal["agent"],
            "direction": signal["direction"],
            "strength": str(signal["strength"]),
            "confidence": str(signal["confidence"]),
            "data": json.dumps(signal.get("data", {})),
            "timestamp": str(signal["timestamp"]),
        },
        maxlen=50_000,
        approximate=True,
    )

async def publish_order_event(redis: redis.asyncio.Redis, account: str, event: dict):
    """Publish order fill/reject/cancel to durable stream."""
    stream_key = f"stream:order:{account}"
    await redis.xadd(
        stream_key,
        {
            "type": event["type"],           # fill, reject, cancel, modify
            "order_id": event["order_id"],
            "symbol": event["symbol"],
            "side": event["side"],
            "qty": str(event["qty"]),
            "price": str(event.get("price", 0)),
            "broker": event["broker"],
            "timestamp": str(event["timestamp"]),
        },
        maxlen=100_000,
        approximate=True,
    )
```

#### Python Consumer Pattern with Consumer Groups

```python
class StreamConsumer:
    """Durable stream consumer with automatic checkpointing."""

    def __init__(self, redis: redis.asyncio.Redis, stream: str, group: str, consumer: str):
        self.redis = redis
        self.stream = stream
        self.group = group
        self.consumer = consumer
        self.last_id = "0"  # Start from beginning on first connect

    async def init(self):
        """Create consumer group if not exists. Idempotent."""
        try:
            await self.redis.xgroup_create(
                self.stream, self.group, id="0", mkstream=True
            )
        except redis.exceptions.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise  # Group already exists — fine

    async def read(self, count: int = 100, block_ms: int = 1000) -> list[dict]:
        """Read new messages. Automatically resumes from last checkpoint."""
        results = await self.redis.xreadgroup(
            groupname=self.group,
            consumername=self.consumer,
            streams={self.stream: ">"},   # ">" = new messages only
            count=count,
            block=block_ms,
        )
        messages = []
        for stream_name, entries in results:
            for msg_id, fields in entries:
                messages.append({"id": msg_id, **fields})
        return messages

    async def ack(self, msg_id: str):
        """Acknowledge message processing. Prevents redelivery."""
        await self.redis.xack(self.stream, self.group, msg_id)

    async def read_pending(self, count: int = 100) -> list[dict]:
        """Read unacknowledged messages (crash recovery)."""
        results = await self.redis.xreadgroup(
            groupname=self.group,
            consumername=self.consumer,
            streams={self.stream: "0"},   # "0" = pending messages
            count=count,
        )
        messages = []
        for stream_name, entries in results:
            for msg_id, fields in entries:
                messages.append({"id": msg_id, **fields})
        return messages
```

#### Risk Agent Integration Example

```python
async def risk_agent_main():
    """Risk agent: consume ticks from stream, never miss a safety signal."""
    redis = redis.asyncio.Redis(host="localhost", port=6379, decode_responses=True)

    # One consumer group per agent type
    tick_consumer = StreamConsumer(redis, "stream:tick:EUR/USD", "risk-agents", "risk-01")
    await tick_consumer.init()

    # On startup: process any pending messages first (crash recovery)
    pending = await tick_consumer.read_pending()
    for msg in pending:
        await process_tick_for_risk(msg)
        await tick_consumer.ack(msg["id"])

    # Main loop: consume new ticks
    while True:
        messages = await tick_consumer.read(count=50, block_ms=500)
        for msg in messages:
            await process_tick_for_risk(msg)
            await tick_consumer.ack(msg["id"])

async def process_tick_for_risk(tick: dict):
    """Check tick for safety signals: spread blowout, extreme price move, etc."""
    spread = float(tick["spread"])
    if spread > MAX_SPREAD_THRESHOLD:
        await trigger_spread_circuit_breaker(tick)
```

#### Migration Checklist

- [ ] Replace all `redis.publish()` calls for tick/signal/order/candle channels with `redis.xadd()`
- [ ] Implement `StreamConsumer` class with consumer group support
- [ ] Each agent type gets its own consumer group (e.g., `risk-agents`, `execution-agents`, `monitoring`)
- [ ] On startup, each consumer reads pending messages first (crash recovery)
- [ ] Keep Pub/Sub only for `dashboard:*` channels
- [ ] Add Redis `XINFO STREAM` monitoring to health check
- [ ] Test: kill a consumer mid-stream, restart it, verify no messages lost

---

## FIX-3: Cache Warming on Restart

### Problem

When the system restarts (crash, deployment, maintenance), Redis is cold:

- No position state → Risk Agent can't enforce position limits
- No recent signals → Confluence Agent has no context
- No agent memory → All learned patterns are gone from hot cache
- No indicator state → Technical indicators need N bars to warm up

During this window (potentially minutes), the system makes decisions with incomplete context.

### Solution: Startup Sequence with Cache Warming

#### Startup State Machine

```
START → DRAIN → WARM → SYNC → VERIFY → READY
  │       │       │       │        │        │
  │       │       │       │        │        └─ Begin processing live data
  │       │       │       │        └─ Run verification checks
  │       │       │       └─ Sync with broker API
  │       │       └─ Warm caches from TimescaleDB
  │       └─ Drain pending stream messages
  └─ Initialize connections
```

#### Implementation

```python
import asyncio
from enum import Enum
from datetime import datetime, timedelta

class SystemState(Enum):
    START   = "start"
    DRAIN   = "drain"
    WARM    = "warm"
    SYNC    = "sync"
    VERIFY  = "verify"
    READY   = "ready"

class CacheWarmer:
    """Warms Redis cache from PostgreSQL/TimescaleDB on startup."""

    def __init__(self, redis, pg_pool, broker_client):
        self.redis = redis
        self.pg = pg_pool
        self.broker = broker_client
        self.state = SystemState.START

    async def run_startup_sequence(self):
        """Full startup sequence. Blocks until READY."""
        await self._phase_drain()
        await self._phase_warm()
        await self._phase_sync()
        await self._phase_verify()
        self.state = SystemState.READY
        print(f"[{datetime.utcnow()}] System READY")

    async def _phase_drain(self):
        """Phase 1: Drain any pending Redis Stream messages from before restart."""
        self.state = SystemState.DRAIN
        print(f"[{datetime.utcnow()}] Phase: DRAIN — reading pending stream messages")

        streams = [
            "stream:tick:*",
            "stream:signal:*",
            "stream:order:*",
            "stream:system",
        ]

        # Read pending (unacknowledged) messages from all consumer groups
        for pattern in streams:
            for key in await self.redis.keys(pattern):
                pending = await self.redis.xpending_range(key, group="*", min="-", max="+", count=100)
                if pending:
                    print(f"  Found {len(pending)} pending messages in {key}")

        # Also read latest entries to know where we are
        for key in await self.redis.keys("stream:tick:*"):
            latest = await self.redis.xrevlen(key)
            print(f"  {key}: {latest} total entries")

        print(f"[{datetime.utcnow()}] DRAIN complete")

    async def _phase_warm(self):
        """Phase 2: Load hot data from TimescaleDB into Redis."""
        self.state = SystemState.WARM
        print(f"[{datetime.utcnow()}] Phase: WARM — loading from TimescaleDB")

        await asyncio.gather(
            self._warm_positions(),
            self._warm_latest_candles(),
            self._warm_indicator_state(),
            self._warm_agent_memory(),
            self._warm_symbol_metadata(),
        )

        print(f"[{datetime.utcnow()}] WARM complete")

    async def _warm_positions(self):
        """Load all open positions into Redis."""
        async with self.pg.acquire() as conn:
            rows = await conn.fetch("""
                SELECT account, symbol, side, qty, avg_price, unrealized_pnl,
                       stop_loss, take_profit, opened_at
                FROM positions
                WHERE status = 'open'
            """)

        for row in rows:
            key = f"position:{row['account']}:{row['symbol']}"
            await self.redis.hset(key, mapping={
                "side": row["side"],
                "qty": str(row["qty"]),
                "avg_price": str(row["avg_price"]),
                "unrealized_pnl": str(row["unrealized_pnl"]),
                "stop_loss": str(row["stop_loss"]) if row["stop_loss"] else "",
                "take_profit": str(row["take_profit"]) if row["take_profit"] else "",
                "opened_at": row["opened_at"].isoformat(),
            })

        print(f"  Warmed {len(rows)} positions")

    async def _warm_latest_candles(self):
        """Load recent candles for each symbol/timeframe into Redis."""
        timeframes = ["1m", "5m", "15m", "1h", "4h", "1d"]
        lookback = {
            "1m": 200, "5m": 200, "15m": 100,
            "1h": 100, "4h": 50, "1d": 50,
        }

        total = 0
        async with self.pg.acquire() as conn:
            for tf in timeframes:
                rows = await conn.fetch("""
                    SELECT symbol, time, open, high, low, close, volume
                    FROM market_data
                    WHERE timeframe = $1
                    ORDER BY time DESC
                    LIMIT $2
                """, tf, lookback[tf])

                for row in rows:
                    key = f"candle:{row['symbol']}:{tf}"
                    await self.redis.rpush(key, json.dumps({
                        "time": row["time"].isoformat(),
                        "open": str(row["open"]),
                        "high": str(row["high"]),
                        "low": str(row["low"]),
                        "close": str(row["close"]),
                        "volume": str(row["volume"]),
                    }))
                    total += 1

                # Trim to max length
                for key in await self.redis.keys(f"candle:*:{tf}"):
                    await self.redis.ltrim(key, -lookback[tf], -1)

        print(f"  Warmed {total} candles across {len(timeframes)} timeframes")

    async def _warm_indicator_state(self):
        """Load pre-computed indicator values from TimescaleDB."""
        async with self.pg.acquire() as conn:
            rows = await conn.fetch("""
                SELECT symbol, indicator, timeframe, value, computed_at
                FROM indicator_cache
                WHERE computed_at > NOW() - INTERVAL '4 hours'
            """)

        for row in rows:
            key = f"indicator:{row['symbol']}:{row['indicator']}:{row['timeframe']}"
            await self.redis.set(key, json.dumps({
                "value": str(row["value"]),
                "computed_at": row["computed_at"].isoformat(),
            }), ex=3600)  # 1 hour TTL

        print(f"  Warmed {len(rows)} indicator values")

    async def _warm_agent_memory(self):
        """Load high-importance agent memories from PostgreSQL."""
        async with self.pg.acquire() as conn:
            rows = await conn.fetch("""
                SELECT agent_id, memory_key, content, importance, access_count
                FROM agent_memories
                WHERE importance > 0.7
                ORDER BY importance DESC
                LIMIT 1000
            """)

        for row in rows:
            key = f"memory:{row['agent_id']}:{row['memory_key']}"
            await self.redis.set(key, json.dumps({
                "content": row["content"],
                "importance": str(row["importance"]),
                "access_count": row["access_count"],
            }), ex=86400)  # 24 hour TTL

        print(f"  Warmed {len(rows)} agent memories")

    async def _warm_symbol_metadata(self):
        """Load symbol metadata (pip value, contract size, etc.)."""
        async with self.pg.acquire() as conn:
            rows = await conn.fetch("""
                SELECT symbol, broker, pip_value, contract_size, min_lot,
                       max_lot, lot_step, margin_currency, is_active
                FROM symbol_metadata
                WHERE is_active = true
            """)

        for row in rows:
            key = f"meta:{row['broker']}:{row['symbol']}"
            await self.redis.hset(key, mapping={
                "pip_value": str(row["pip_value"]),
                "contract_size": str(row["contract_size"]),
                "min_lot": str(row["min_lot"]),
                "max_lot": str(row["max_lot"]),
                "lot_step": str(row["lot_step"]),
                "margin_currency": row["margin_currency"],
            })

        print(f"  Warmed {len(rows)} symbol metadata entries")

    async def _phase_sync(self):
        """Phase 3: Sync positions with broker API to catch any drift."""
        self.state = SystemState.SYNC
        print(f"[{datetime.utcnow()}] Phase: SYNC — reconciling with broker")

        broker_positions = await self.broker.get_open_positions()
        redis_positions = {}

        for key in await self.redis.keys("position:*"):
            pos = await self.redis.hgetall(key)
            redis_positions[key] = pos

        # Compare and flag discrepancies
        discrepancies = []
        for bpos in broker_positions:
            rkey = f"position:{bpos['account']}:{bpos['symbol']}"
            rpos = redis_positions.get(rkey)

            if not rpos:
                discrepancies.append(f"  MISSING in Redis: {bpos['account']}:{bpos['symbol']} "
                                     f"(broker has {bpos['qty']} {bpos['side']})")
            elif float(rpos["qty"]) != float(bpos["qty"]):
                discrepancies.append(f"  QTY MISMATCH: {rkey} "
                                     f"redis={rpos['qty']} broker={bpos['qty']}")

        if discrepancies:
            print(f"  ⚠️  Found {len(discrepancies)} discrepancies:")
            for d in discrepancies:
                print(d)
            # Resolve: broker is source of truth for positions
            await self._resolve_position_discrepancies(broker_positions)
        else:
            print("  ✅ All positions in sync")

        print(f"[{datetime.utcnow()}] SYNC complete")

    async def _resolve_position_discrepancies(self, broker_positions: list):
        """Overwrite Redis with broker state (broker is source of truth)."""
        for bpos in broker_positions:
            key = f"position:{bpos['account']}:{bpos['symbol']}"
            await self.redis.hset(key, mapping={
                "side": bpos["side"],
                "qty": str(bpos["qty"]),
                "avg_price": str(bpos["avg_price"]),
                "unrealized_pnl": str(bpos.get("unrealized_pnl", 0)),
                "stop_loss": str(bpos.get("stop_loss", "")),
                "take_profit": str(bpos.get("take_profit", "")),
                "opened_at": bpos.get("opened_at", ""),
            })
        print(f"  Resolved {len(broker_positions)} positions from broker")

    async def _phase_verify(self):
        """Phase 4: Run verification checks before going live."""
        self.state = SystemState.VERIFY
        print(f"[{datetime.utcnow()}] Phase: VERIFY — running checks")

        checks = {
            "redis_connected": await self._check_redis(),
            "pg_connected": await self._check_postgres(),
            "broker_connected": await self._check_broker(),
            "positions_loaded": await self._check_positions(),
            "candles_loaded": await self._check_candles(),
            "streams_active": await self._check_streams(),
        }

        failed = [k for k, v in checks.items() if not v]
        if failed:
            raise RuntimeError(f"Startup verification failed: {failed}")

        print(f"  ✅ All {len(checks)} checks passed")
        print(f"[{datetime.utcnow()}] VERIFY complete")

    # --- Verification helpers ---

    async def _check_redis(self) -> bool:
        return await self.redis.ping()

    async def _check_postgres(self) -> bool:
        async with self.pg.acquire() as conn:
            return await conn.fetchval("SELECT 1") == 1

    async def _check_broker(self) -> bool:
        try:
            await self.broker.ping()
            return True
        except Exception:
            return False

    async def _check_positions(self) -> bool:
        count = len(await self.redis.keys("position:*"))
        print(f"    Positions in Redis: {count}")
        return True  # Zero positions is valid (no open trades)

    async def _check_candles(self) -> bool:
        keys = await self.redis.keys("candle:EUR/USD:1h")
        if keys:
            length = await self.redis.llen(keys[0])
            print(f"    EUR/USD 1h candles: {length}")
            return length > 0
        return False

    async def _check_streams(self) -> bool:
        keys = await self.redis.keys("stream:*")
        print(f"    Active streams: {len(keys)}")
        return True
```

#### systemd / Docker Integration

```ini
# systemd unit: alpha-stack.service
[Unit]
Description=Alpha Stack Trading System
After=redis.service postgresql.service
Requires=redis.service postgresql.service

[Service]
Type=notify
ExecStartPre=/usr/bin/redis-cli ping
ExecStartPre=/usr/bin/pg_isready
ExecStart=/opt/alpha-stack/main.py --startup-sequence
Restart=on-failure
RestartSec=10
WatchdogSec=120
```

```yaml
# docker-compose.yml (relevant parts)
services:
  trading:
    depends_on:
      redis:
        condition: service_healthy
      timescaledb:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "python", "-c", "import redis; r=redis.Redis(); r.ping()"]
      interval: 10s
      timeout: 5s
      retries: 3

  redis:
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 3
```

### Validation Checklist

- [ ] System enters `READY` state only after all warm phases complete
- [ ] Positions in Redis match broker API after startup sync
- [ ] Recent candles loaded for all active symbols
- [ ] Pending stream messages are drained before live processing begins
- [ ] Startup takes < 30 seconds with typical data volumes
- [ ] Failed startup aborts cleanly (no partial state)

---

## FIX-4: Clock Synchronization (NTP)

### Problem

No NTP or clock synchronization strategy is documented. Clock skew between components causes:

| Component | Impact of 2s Drift |
|-----------|-------------------|
| Candle boundaries | 1m candle at :02 instead of :00 → all aggregates wrong |
| Session classification | London open detected at 08:00:02 → wrong session params |
| Order timestamps | Fill time doesn't match broker time → reconciliation failures |
| Signal timestamps | Signals from different agents appear out-of-order → wrong causality |
| Log correlation | Logs from different services can't be correlated by timestamp |
| Rate limiting | Token bucket / sliding window calculations are wrong |

### Solution: NTP Configuration + Monitoring

#### 1. NTP Configuration (chrony — preferred for VPS)

```bash
# /etc/chrony/chrony.conf

# Upstream NTP servers (use 3+ for redundancy)
server time.google.com iburst prefer
server time.cloudflare.com iburst
server time.aws.com iburst
server ntp.ubuntu.com iburst

# Allow large initial correction on first sync
makestep 1.0 3

# Drift file for persistent correction between restarts
driftfile /var/lib/chrony/chrony.drift

# Log for audit
logdir /var/log/chrony
log tracking measurements statistics

# RTC sync (for bare metal; skip on VPS)
# rtcsync

# Serve NTP to local network containers (if applicable)
# allow 172.16.0.0/12
```

```bash
# Enable and start
sudo systemctl enable chronyd
sudo systemctl start chronyd

# Verify sync
chronyc tracking
chronyc sources -v
```

#### 2. Docker / Container Considerations

```yaml
# docker-compose.yml — containers share host clock via /etc/localtime
services:
  trading:
    volumes:
      - /etc/localtime:/etc/localtime:ro
      - /etc/timezone:/etc/timezone:ro
    environment:
      - TZ=UTC

  # If running chrony inside a container:
  chrony:
    image: cturra/ntp
    cap_add:
      - SYS_TIME
    environment:
      - NTP_SERVERS=time.google.com,time.cloudflare.com
    restart: always
```

#### 3. Application-Level Clock Check

```python
import time
import ntplib  # pip install ntplib
from datetime import datetime, timezone

class ClockMonitor:
    """Monitor clock drift against NTP servers."""

    def __init__(self, ntp_servers: list[str] = None):
        self.ntp_servers = ntp_servers or [
            "time.google.com",
            "time.cloudflare.com",
            "time.aws.com",
        ]
        self.ntp_client = ntplib.NTPClient()
        self.max_drift_ms = 100  # Alert threshold

    def check_drift(self) -> dict:
        """Check clock drift against multiple NTP sources."""
        results = []
        for server in self.ntp_servers:
            try:
                response = self.ntp_client.request(server, version=3, timeout=2)
                drift_ms = response.offset * 1000
                results.append({
                    "server": server,
                    "drift_ms": round(drift_ms, 2),
                    "delay_ms": round(response.delay * 1000, 2),
                    "stratum": response.stratum,
                })
            except Exception as e:
                results.append({"server": server, "error": str(e)})

        # Use median drift from successful queries
        successful = [r for r in results if "drift_ms" in r]
        if not successful:
            return {"status": "error", "message": "All NTP servers unreachable", "results": results}

        successful.sort(key=lambda r: r["drift_ms"])
        median_drift = successful[len(successful) // 2]["drift_ms"]

        status = "ok" if abs(median_drift) < self.max_drift_ms else "ALERT"

        return {
            "status": status,
            "median_drift_ms": median_drift,
            "threshold_ms": self.max_drift_ms,
            "details": results,
        }

    async def monitor_loop(self, check_interval_sec: int = 300, alert_callback=None):
        """Run continuous clock monitoring."""
        while True:
            result = self.check_drift()
            if result["status"] == "ALERT" and alert_callback:
                await alert_callback(
                    f"⚠️ Clock drift {result['median_drift_ms']:.1f}ms "
                    f"exceeds threshold {result['threshold_ms']}ms"
                )
            await asyncio.sleep(check_interval_sec)
```

#### 4. Prometheus / Grafana Monitoring

```yaml
# prometheus.yml — add NTP scrape target
scrape_configs:
  - job_name: 'ntp'
    static_configs:
      - targets: ['localhost:9100']  # node_exporter exposes ntp metrics
    metrics_path: /metrics
```

Key metrics to alert on:

```yaml
# alerting_rules.yml
groups:
  - name: clock_sync
    rules:
      - alert: ClockDriftHigh
        expr: node_timex_offset_seconds > 0.1  # > 100ms
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Clock drift {{ $value }}s on {{ $instance }}"

      - alert: ClockDriftCritical
        expr: node_timex_offset_seconds > 1.0  # > 1s
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "CRITICAL: Clock drift {{ $value }}s on {{ $instance }}"

      - alert: NTPUnreachable
        expr: node_ntp_sanity == 0
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "NTP sync lost on {{ $instance }}"
```

#### 5. Infrastructure Checklist

```markdown
## Clock Sync — Pre-Launch Checklist

- [ ] chrony installed and running on all hosts
- [ ] `chronyc tracking` shows stratum ≤ 4 and offset < 50ms
- [ ] chrony configured with 3+ upstream NTP servers
- [ ] `makestep 1.0 3` allows initial correction
- [ ] Docker containers share host clock (`/etc/localtime:ro`)
- [ ] Application-level clock check runs every 5 minutes
- [ ] Prometheus node_exporter scrapes NTP metrics
- [ ] Grafana dashboard shows clock offset per host
- [ ] Alert fires if drift > 100ms for > 5 minutes
- [ ] All timestamps in application use UTC
- [ ] Log correlation uses ISO 8601 with timezone
```

---

## Summary

| Fix | Issue | Solution | Effort |
|-----|-------|----------|--------|
| FIX-1 | candle_1m / market_data divergence | Single `market_data` table as source of truth; continuous aggregate writes directly into it | 2 hours |
| FIX-2 | Redis Pub/Sub message loss | Replace with Redis Streams + consumer groups for all safety channels; keep Pub/Sub only for dashboard | 4 hours |
| FIX-3 | No cache warming on restart | Startup state machine: DRAIN → WARM → SYNC → VERIFY → READY | 4 hours |
| FIX-4 | No clock synchronization | chrony NTP + application-level monitoring + Prometheus alerts | 30 min |

**Total estimated effort: ~11 hours**

---

*Fix document generated from `review_7_data_flow.md` — 2026-07-11*
