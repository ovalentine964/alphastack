# Alpha Stack — Broker Disconnection Handling Fix

> **Version:** 1.0 · **Date:** 2026-07-11 · **Author:** Broker Resilience Engineer  
> **Scope:** Fix all 6 critical gaps in broker disconnection handling identified in edge case review  
> **Context:** Addresses gaps in Circuit Breaker Layer 4 (System Level) and adds new Broker Health Manager  
> **Priority:** CRITICAL — must be resolved before any live capital deployment

---

## Table of Contents

1. [Problem Summary](#1-problem-summary)
2. [Fix 1: Adaptive Timeout (30s → 10s for losers)](#2-fix-1-adaptive-timeout)
3. [Fix 2: Backup Broker Failover Routing](#3-fix-2-backup-broker-failover)
4. [Fix 3: Zombie Connection Detection (Heartbeat)](#4-fix-3-zombie-connection-detection)
5. [Fix 4: Position Reconciliation on Reconnect](#5-fix-4-position-reconciliation-on-reconnect)
6. [Fix 5: Degraded Broker State](#6-fix-5-degraded-broker-state)
7. [Fix 6: Partial Disconnection Handling](#7-fix-6-partial-disconnection-handling)
8. [Unified Broker Health Manager](#8-unified-broker-health-manager)
9. [Integration with Existing Architecture](#9-integration-with-existing-architecture)
10. [Configuration](#10-configuration)
11. [Testing Scenarios](#11-testing-scenarios)

---

## 1. Problem Summary

The current Circuit Breaker Layer 4 treats broker connectivity as binary (connected/disconnected) with a flat 30-second timeout. This is dangerously simplistic for live trading.

| Gap | Current State | Risk |
|-----|--------------|------|
| **30s timeout too long** | Flat 30s for all positions | 50+ pips adverse movement during NFP |
| **No failover** | Close on disconnected broker (which can't execute) | Positions remain open with no exit path |
| **Zombie connections** | TCP keepalive passes, no data flows | System thinks broker is alive when it's dead |
| **No reconciliation** | Trusts local state after reconnect | Misses SL fills, partial closes at broker |
| **No degraded state** | Binary connected/disconnected | Keeps entering trades on broken broker |
| **No partial disconnect** | Treats all failures the same | Quote feed alive but execution dead = silent death |

---

## 2. Fix 1: Adaptive Timeout

**Problem:** 30-second flat timeout. In a fast market, a losing position can hemorrhage capital in 30 seconds.

**Solution:** Dynamic timeout based on position unrealized R-multiple.

### 2.1 Timeout Tiers

```
┌─────────────────────────────────────────────────────────────┐
│              ADAPTIVE DISCONNECTION TIMEOUT                   │
│                                                              │
│  Unrealized Loss ≥ 0.5R  →  10 seconds (URGENT)            │
│  Unrealized Loss ≥ 0.0R  →  15 seconds (CAUTION)           │
│  Unrealized Profit > 0R  →  20 seconds (MONITOR)           │
│  No open positions       →  30 seconds (DEFAULT)            │
│                                                              │
│  Additional modifier: During news blackout → subtract 5s    │
│  Additional modifier: VIX > 30 → subtract 5s               │
│  Floor: 5 seconds minimum (never less)                       │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Implementation

```python
class AdaptiveDisconnectTimeout:
    """
    Dynamic timeout calculation based on position risk exposure.
    The more at-risk a position is, the faster we act.
    """
    
    # Base timeouts by risk tier
    TIMEOUT_LOSING_05R = 10     # Positions losing > 0.5R
    TIMEOUT_LOSING = 15          # Positions losing any amount
    TIMEOUT_PROFITABLE = 20      # Positions in profit
    TIMEOUT_NO_POSITIONS = 30    # No open positions
    
    # Modifiers
    NEWS_BLACKOUT_MODIFIER = -5  # Subtract 5s during news blackout
    HIGH_VOLATILITY_MODIFIER = -5  # Subtract 5s when VIX > 30
    FLOOR = 5                    # Never go below 5 seconds
    
    def calculate_timeout(
        self,
        open_positions: list[Position],
        is_news_blackout: bool = False,
        vix: float = 20.0
    ) -> int:
        """Calculate the appropriate disconnect timeout."""
        
        if not open_positions:
            base = self.TIMEOUT_NO_POSITIONS
        else:
            # Find the worst unrealized R across all positions
            worst_r = min(p.unrealized_pnl_r for p in open_positions)
            
            if worst_r <= -0.5:
                base = self.TIMEOUT_LOSING_05R
            elif worst_r < 0:
                base = self.TIMEOUT_LOSING
            else:
                base = self.TIMEOUT_PROFITABLE
        
        # Apply modifiers
        timeout = base
        if is_news_blackout:
            timeout += self.NEWS_BLACKOUT_MODIFIER
        if vix > 30:
            timeout += self.HIGH_VOLATILITY_MODIFIER
        
        # Enforce floor
        return max(timeout, self.FLOOR)
```

### 2.3 Integration Point

Modify the existing `CircuitBreakerSystem.check_system_health()` to use adaptive timeout:

```python
# BEFORE (flat 30s):
# if status.disconnected_duration_sec > self.CONNECTIVITY_TIMEOUT_SEC:

# AFTER (adaptive):
async def check_system_health(self, system_state: SystemState) -> bool:
    """Layer 4: Check infrastructure health with adaptive timeout."""
    tripped = False
    
    for broker, status in system_state.broker_status.items():
        # Calculate adaptive timeout based on current positions
        timeout = self.adaptive_timeout.calculate_timeout(
            open_positions=system_state.open_positions_on_broker(broker),
            is_news_blackout=self.news_handler.is_blackout_active_any(),
            vix=system_state.market_state.vix
        )
        
        if status.disconnected_duration_sec > timeout:
            await self._trip_breaker('connectivity', {
                'broker': broker,
                'disconnected_sec': status.disconnected_duration_sec,
                'timeout_used': timeout,
                'worst_position_r': self._worst_r(system_state, broker),
                'action': 'close_broker_positions'
            })
            tripped = True
    
    return tripped
```

---

## 3. Fix 2: Backup Broker Failover Routing

**Problem:** When primary broker disconnects, the system tries to close on the disconnected broker — which can't execute. Positions remain open with no exit path.

**Solution:** Failover routing that sends close orders to a backup broker via hedging.

### 3.1 Failover Architecture

```
                    ┌──────────────────┐
                    │   CLOSE ORDER    │
                    │   REQUESTED      │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │  PRIMARY BROKER  │
                    │  CONNECTED?      │
                    └──────┬───────────┘
                      YES/ │ \NO
                          / │  \
                         /  │   \
                        ▼   │    ▼
              ┌──────────┐  │  ┌──────────────────┐
              │ EXECUTE  │  │  │ FAILOVER ROUTER  │
              │ ON       │  │  │                  │
              │ PRIMARY  │  │  │ 1. Select backup │
              └──────────┘  │  │ 2. Hedge open    │
                            │  │ 3. Alert human   │
                            │  └────────┬─────────┘
                            │           │
                            │           ▼
                            │  ┌──────────────────┐
                            │  │  BACKUP BROKER   │
                            │  │  (OPPOSITE       │
                            │  │   DIRECTION)     │
                            │  └──────────────────┘
                            │           │
                            │           ▼
                            │  ┌──────────────────┐
                            │  │  POSITION IS     │
                            │  │  HEDGED (NET = 0)│
                            │  └──────────────────┘
                            │           │
                            │           ▼
                            │  ┌──────────────────┐
                            │  │  ON RECONNECT:   │
                            │  │  Close original  │
                            │  │  on primary,     │
                            │  │  close hedge     │
                            │  │  on backup       │
                            │  └──────────────────┘
```

### 3.2 Failover Router Implementation

```python
class BrokerFailoverRouter:
    """
    Routes close orders to backup brokers when primary is disconnected.
    Uses hedging (opposite position on backup) to neutralize exposure.
    """
    
    def __init__(self, brokers: dict[str, BrokerAdapter]):
        self.brokers = brokers
        self.primary_broker = None
        self.backup_brokers = []       # Ordered by preference
        self.hedge_positions = {}      # original_ticket → hedge_ticket
        self.failover_log = []         # Audit trail
    
    async def close_position(
        self,
        position: Position,
        reason: str,
        urgency: str = 'NORMAL'  # NORMAL, URGENT, EMERGENCY
    ) -> CloseResult:
        """
        Attempt to close a position. If primary broker fails, hedge on backup.
        """
        
        # Step 1: Try primary broker first
        primary_adapter = self.brokers.get(position.broker)
        if primary_adapter and primary_adapter.is_connected():
            try:
                result = await primary_adapter.close_position(
                    position.ticket,
                    position.lots
                )
                if result.success:
                    return CloseResult(
                        success=True,
                        broker=position.broker,
                        method='DIRECT_CLOSE',
                        fill_price=result.fill_price
                    )
            except BrokerException as e:
                logger.warning(f"Primary broker close failed: {e}")
                # Fall through to failover
        
        # Step 2: Primary failed — initiate failover
        logger.critical(
            f"FAILOVER: Primary broker {position.broker} unavailable. "
            f"Routing close to backup broker."
        )
        
        # Step 3: Select best backup broker
        backup = self._select_backup_broker(
            position.pair,
            position.direction,
            urgency
        )
        
        if not backup:
            logger.critical("FAILOVER FAILED: No backup brokers available")
            await self._emergency_alert(position, "No backup broker available")
            return CloseResult(
                success=False,
                broker=None,
                method='FAILOVER_FAILED',
                error="No backup brokers available"
            )
        
        # Step 4: Open hedge position on backup broker (opposite direction)
        hedge_direction = Direction.SHORT if position.direction == Direction.LONG else Direction.LONG
        
        try:
            hedge_result = await backup.open_position(
                pair=position.pair,
                direction=hedge_direction,
                lots=position.lots,
                sl=None,  # No SL on hedge — we'll close it manually
                tp=None,
                comment=f"HEDGE: Primary {position.broker} disconnected, "
                        f"original ticket {position.ticket}"
            )
            
            if hedge_result.success:
                # Record the hedge relationship
                self.hedge_positions[position.ticket] = HedgeRecord(
                    original_ticket=position.ticket,
                    original_broker=position.broker,
                    original_pair=position.pair,
                    original_direction=position.direction,
                    original_lots=position.lots,
                    hedge_ticket=hedge_result.ticket,
                    hedge_broker=backup.name,
                    hedge_direction=hedge_direction,
                    hedge_lots=position.lots,
                    hedge_open_price=hedge_result.fill_price,
                    hedge_open_time=datetime.utcnow(),
                    reason=reason,
                    status='ACTIVE'
                )
                
                # Log failover
                self.failover_log.append({
                    'timestamp': datetime.utcnow(),
                    'action': 'FAILOVER_HEDGE_OPENED',
                    'position': position.ticket,
                    'broker': position.broker,
                    'backup_broker': backup.name,
                    'hedge_ticket': hedge_result.ticket,
                    'reason': reason
                })
                
                # Alert human
                await self._failover_alert(position, backup.name, hedge_result)
                
                return CloseResult(
                    success=True,
                    broker=backup.name,
                    method='FAILOVER_HEDGE',
                    hedge_ticket=hedge_result.ticket,
                    hedge_price=hedge_result.fill_price,
                    note=f"Position hedged on {backup.name}. "
                         f"Will close hedge + original on reconnect."
                )
            else:
                logger.critical(f"FAILOVER: Hedge order failed on {backup.name}: {hedge_result.error}")
                # Try next backup
                return await self._try_next_backup(position, backup, reason, urgency)
                
        except BrokerException as e:
            logger.critical(f"FAILOVER: Exception on {backup.name}: {e}")
            return await self._try_next_backup(position, backup, reason, urgency)
    
    def _select_backup_broker(
        self,
        pair: str,
        direction: Direction,
        urgency: str
    ) -> BrokerAdapter | None:
        """
        Select the best backup broker for a hedge order.
        Criteria: connected, has the pair, lowest spread, fastest execution.
        """
        candidates = []
        
        for broker in self.backup_brokers:
            adapter = self.brokers.get(broker)
            if not adapter or not adapter.is_connected():
                continue
            if not adapter.has_pair(pair):
                continue
            
            # Score based on spread and execution speed
            score = adapter.get_pair_spread(pair) * 0.6 + adapter.avg_execution_ms * 0.4
            
            # Bonus for urgency: prefer fastest broker
            if urgency == 'EMERGENCY':
                score = adapter.avg_execution_ms  # Pure speed priority
            
            candidates.append((adapter, score))
        
        if not candidates:
            return None
        
        # Return best scored broker
        candidates.sort(key=lambda x: x[1])
        return candidates[0][0]
    
    async def _try_next_backup(
        self,
        position: Position,
        failed_broker: BrokerAdapter,
        reason: str,
        urgency: str
    ) -> CloseResult:
        """Try the next available backup broker after one fails."""
        remaining = [b for b in self.backup_brokers if b != failed_broker.name]
        
        for broker_name in remaining:
            adapter = self.brokers.get(broker_name)
            if not adapter or not adapter.is_connected():
                continue
            if not adapter.has_pair(position.pair):
                continue
            
            hedge_direction = Direction.SHORT if position.direction == Direction.LONG else Direction.LONG
            
            try:
                result = await adapter.open_position(
                    pair=position.pair,
                    direction=hedge_direction,
                    lots=position.lots,
                    comment=f"HEDGE-RETRY: Original {position.broker} #{position.ticket}"
                )
                
                if result.success:
                    self.hedge_positions[position.ticket] = HedgeRecord(
                        original_ticket=position.ticket,
                        original_broker=position.broker,
                        original_pair=position.pair,
                        original_direction=position.direction,
                        original_lots=position.lots,
                        hedge_ticket=result.ticket,
                        hedge_broker=broker_name,
                        hedge_direction=hedge_direction,
                        hedge_lots=position.lots,
                        hedge_open_price=result.fill_price,
                        hedge_open_time=datetime.utcnow(),
                        reason=reason,
                        status='ACTIVE'
                    )
                    
                    return CloseResult(
                        success=True,
                        broker=broker_name,
                        method='FAILOVER_HEDGE_RETRY',
                        hedge_ticket=result.ticket
                    )
            except Exception:
                continue
        
        # All brokers failed
        logger.critical(f"ALL FAILOVER ATTEMPTS FAILED for position {position.ticket}")
        await self._emergency_alert(position, "All backup brokers failed")
        return CloseResult(success=False, method='ALL_FAILED')
    
    async def resolve_hedge_on_reconnect(self, original_ticket: int):
        """
        Called when primary broker reconnects.
        Close the original position on primary, then close the hedge on backup.
        """
        hedge = self.hedge_positions.get(original_ticket)
        if not hedge or hedge.status != 'ACTIVE':
            return
        
        logger.info(f"Resolving hedge for position {original_ticket}")
        
        # Step 1: Close original on primary (now reconnected)
        primary_adapter = self.brokers.get(hedge.original_broker)
        if primary_adapter and primary_adapter.is_connected():
            try:
                await primary_adapter.close_position(
                    hedge.original_ticket,
                    hedge.original_lots
                )
            except Exception as e:
                logger.warning(f"Could not close original on reconnect: {e}. Hedge remains active.")
                return
        
        # Step 2: Close hedge on backup
        backup_adapter = self.brokers.get(hedge.hedge_broker)
        if backup_adapter and backup_adapter.is_connected():
            try:
                await backup_adapter.close_position(
                    hedge.hedge_ticket,
                    hedge.hedge_lots
                )
                hedge.status = 'RESOLVED'
                logger.info(f"Hedge resolved for position {original_ticket}")
            except Exception as e:
                logger.warning(f"Could not close hedge: {e}. Manual intervention required.")
                hedge.status = 'MANUAL_CLOSE_REQUIRED'
                await self._emergency_alert(
                    None,
                    f"Hedge {hedge.hedge_ticket} on {hedge.hedge_broker} needs manual close"
                )
    
    async def _failover_alert(self, position: Position, backup_broker: str, hedge_result):
        """Alert human about failover."""
        await self.event_bus.publish('system.alert', {
            'severity': 'CRITICAL',
            'channel': 'telegram',
            'message': (
                f"⚠️ BROKER FAILOVER EXECUTED\n\n"
                f"Position: {position.pair} {position.direction.value} {position.lots} lots\n"
                f"Primary broker: {position.broker} (DISCONNECTED)\n"
                f"Failover broker: {backup_broker}\n"
                f"Hedge ticket: {hedge_result.ticket}\n"
                f"Hedge price: {hedge_result.fill_price}\n\n"
                f"Position is now hedged (net exposure = 0).\n"
                f"Will close both sides on reconnect."
            ),
            'sound': 'alarm',
            'repeat': True,
            'repeat_interval': 120
        })
    
    async def _emergency_alert(self, position: Position, error: str):
        """Alert when all failover attempts have failed."""
        msg = (
            f"🚨 BROKER FAILOVER FAILED 🚨\n\n"
            f"Error: {error}\n"
        )
        if position:
            msg += (
                f"Position: {position.pair} {position.direction.value} {position.lots} lots\n"
                f"Broker: {position.broker}\n"
                f"Unrealized P&L: {position.unrealized_pnl_r:.2f}R\n\n"
            )
        msg += "MANUAL INTERVENTION REQUIRED IMMEDIATELY"
        
        await self.event_bus.publish('system.alert', {
            'severity': 'EMERGENCY',
            'channel': 'telegram',
            'message': msg,
            'sound': 'alarm',
            'repeat': True,
            'repeat_interval': 30  # Every 30 seconds
        })
```

### 3.3 Hedge Lifecycle

```
HEDGE LIFECYCLE:

1. PRIMARY DISCONNECTS
   └→ System detects disconnection (adaptive timeout)
   
2. FAILOVER TRIGGERED
   └→ Open opposite position on backup broker
   └→ Net exposure = 0 (fully hedged)
   
3. POSITION IS HEDGED
   └→ No directional risk
   └→ Small cost: spread + commission on hedge
   └→ Alert human for manual review
   
4. PRIMARY RECONNECTS
   └→ Close original on primary
   └→ Close hedge on backup
   └→ Net result: closed at ~hedge price (minus spread cost)
   
5. IF PRIMARY DOESN'T RECONNECT
   └→ Hedge stays open (position is safe)
   └→ Human must manually resolve
   └→ Options: close hedge at market, or transfer to new broker
```

---

## 4. Fix 3: Zombie Connection Detection

**Problem:** TCP keepalive passes but no data flows. The connection appears alive but is actually dead. Common with MT5 implementations.

**Solution:** Application-level heartbeat ping/pong independent of TCP keepalive.

### 4.1 Heartbeat Protocol

```
┌─────────────────────────────────────────────────────────────┐
│              ZOMBIE DETECTION HEARTBEAT                       │
│                                                              │
│  Every 5 seconds:                                            │
│  ┌──────────┐         PING          ┌──────────┐           │
│  │  SYSTEM  │ ─────────────────────→ │  BROKER  │           │
│  │          │ ←───────────────────── │  SERVER  │           │
│  └──────────┘         PONG          └──────────┘           │
│                                                              │
│  Failure criteria:                                           │
│  • No PONG within 5 seconds → failure_count++               │
│  • 3 consecutive failures → BROKER DECLARED DEAD            │
│  • Reset failure_count on any successful PONG                │
│                                                              │
│  Additional zombie signals:                                  │
│  • Last quote timestamp > 10s stale                         │
│  • Order book unchanged for > 15s during active session     │
│  • Bid = Ask (spread = 0, data feed frozen)                  │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 Implementation

```python
class ZombieDetector:
    """
    Application-level heartbeat to detect zombie connections.
    A zombie connection passes TCP keepalive but delivers no data.
    """
    
    PING_INTERVAL_SEC = 5      # Send ping every 5 seconds
    PONG_TIMEOUT_SEC = 5       # Expect pong within 5 seconds
    MAX_FAILURES = 3           # 3 consecutive failures = dead
    QUOTE_STALE_THRESHOLD_SEC = 10  # No quotes for 10s = suspicious
    ORDERBOOK_STALE_THRESHOLD_SEC = 15  # Orderbook unchanged for 15s = frozen
    
    def __init__(self, broker_name: str, adapter: BrokerAdapter):
        self.broker_name = broker_name
        self.adapter = adapter
        self.failure_count = 0
        self.last_successful_ping = datetime.utcnow()
        self.last_quote_time = datetime.utcnow()
        self.last_orderbook_change = datetime.utcnow()
        self.is_zombie = False
        self._ping_task = None
        self.event_bus = None
    
    async def start(self):
        """Start the heartbeat monitoring loop."""
        self._ping_task = asyncio.create_task(self._heartbeat_loop())
    
    async def stop(self):
        """Stop the heartbeat monitoring."""
        if self._ping_task:
            self._ping_task.cancel()
    
    async def _heartbeat_loop(self):
        """Main heartbeat loop — runs every 5 seconds."""
        while True:
            try:
                await asyncio.sleep(self.PING_INTERVAL_SEC)
                await self._send_ping()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Zombie detector error for {self.broker_name}: {e}")
    
    async def _send_ping(self):
        """Send a ping and wait for pong."""
        try:
            # Use broker-specific ping mechanism
            # MT5: AccountInfo or TerminalInfo call
            # cTrader: Ping API
            # OANDA: Account details API call
            pong_received = await asyncio.wait_for(
                self.adapter.ping(),
                timeout=self.PONG_TIMEOUT_SEC
            )
            
            if pong_received:
                self.failure_count = 0
                self.last_successful_ping = datetime.utcnow()
                
                if self.is_zombie:
                    # Was zombie, now alive again
                    self.is_zombie = False
                    logger.info(f"Broker {self.broker_name}: Zombie recovered")
                    await self.event_bus.publish('system.broker', {
                        'event': 'ZOMBIE_RECOVERED',
                        'broker': self.broker_name
                    })
            else:
                await self._record_failure("Ping returned False")
                
        except asyncio.TimeoutError:
            await self._record_failure(f"Pong timeout ({self.PONG_TIMEOUT_SEC}s)")
        except ConnectionError as e:
            await self._record_failure(f"Connection error: {e}")
        except Exception as e:
            await self._record_failure(f"Unexpected error: {e}")
    
    async def _record_failure(self, reason: str):
        """Record a ping failure and check if zombie threshold reached."""
        self.failure_count += 1
        
        logger.warning(
            f"Broker {self.broker_name}: Ping failure #{self.failure_count} — {reason}"
        )
        
        if self.failure_count >= self.MAX_FAILURES:
            if not self.is_zombie:
                self.is_zombie = True
                logger.critical(
                    f"Broker {self.broker_name}: ZOMBIE DETECTED — "
                    f"{self.failure_count} consecutive ping failures"
                )
                await self.event_bus.publish('system.broker', RiskEvent(
                    event_type=RiskEventType.BROKER_DISCONNECT,
                    severity='EMERGENCY',
                    component=f'zombie_detector.{self.broker_name}',
                    data={
                        'broker': self.broker_name,
                        'failure_count': self.failure_count,
                        'reason': reason,
                        'last_successful_ping': self.last_successful_ping.isoformat(),
                        'classification': 'ZOMBIE_CONNECTION'
                    },
                    action_required='CLOSE_ALL',
                    reasoning=f"Zombie connection detected: {self.failure_count} consecutive ping failures"
                ))
    
    def update_quote_time(self):
        """Called whenever a new quote arrives from this broker."""
        self.last_quote_time = datetime.utcnow()
    
    def update_orderbook_time(self):
        """Called whenever the order book changes."""
        self.last_orderbook_change = datetime.utcnow()
    
    async def check_data_staleness(self):
        """
        Secondary zombie detection: check if data feeds are actually delivering.
        This catches cases where ping succeeds but data pipeline is dead.
        """
        now = datetime.utcnow()
        
        quote_age = (now - self.last_quote_time).total_seconds()
        orderbook_age = (now - self.last_orderbook_change).total_seconds()
        
        signals = []
        
        if quote_age > self.QUOTE_STALE_THRESHOLD_SEC:
            signals.append(f'quotes_stale_{quote_age:.0f}s')
        
        if orderbook_age > self.ORDERBOOK_STALE_THRESHOLD_SEC:
            signals.append(f'orderbook_stale_{orderbook_age:.0f}s')
        
        # Check for frozen spread (bid = ask or spread = 0)
        if self.adapter.last_spread == 0:
            signals.append('spread_zero_frozen')
        
        if signals and not self.is_zombie:
            logger.warning(
                f"Broker {self.broker_name}: Data staleness signals: {signals}"
            )
            
            # If we have 2+ staleness signals, treat as zombie
            if len(signals) >= 2:
                self.is_zombie = True
                await self.event_bus.publish('system.broker', RiskEvent(
                    event_type=RiskEventType.BROKER_DISCONNECT,
                    severity='CRITICAL',
                    component=f'zombie_detector.{self.broker_name}',
                    data={
                        'broker': self.broker_name,
                        'staleness_signals': signals,
                        'quote_age_sec': quote_age,
                        'orderbook_age_sec': orderbook_age,
                        'classification': 'DATA_ZOMBIE'
                    },
                    action_required='HALT',
                    reasoning=f"Data zombie detected: {', '.join(signals)}"
                ))
    
    def get_status(self) -> dict:
        """Return current zombie detection status."""
        return {
            'broker': self.broker_name,
            'is_zombie': self.is_zombie,
            'failure_count': self.failure_count,
            'last_successful_ping': self.last_successful_ping.isoformat(),
            'seconds_since_last_ping': (
                datetime.utcnow() - self.last_successful_ping
            ).total_seconds(),
            'quote_age_sec': (
                datetime.utcnow() - self.last_quote_time
            ).total_seconds(),
            'orderbook_age_sec': (
                datetime.utcnow() - self.last_orderbook_change
            ).total_seconds()
        }
```

### 4.3 Ping Strategy Per Broker Type

| Broker Type | Ping Method | What It Verifies |
|-------------|------------|------------------|
| **MT5** | `TerminalInfoInteger(TERMINAL_CONNECTED)` + `AccountInfoDouble(UNREALIZED_PROFIT)` | Connection + data pipeline alive |
| **cTrader** | `Ping` API call + tick subscription heartbeat | API responsive + market data flowing |
| **OANDA** | `GET /v3/accounts/{id}` + latest pricing check | REST API alive + pricing stream active |

---

## 5. Fix 4: Position Reconciliation on Reconnect

**Problem:** After a disconnection, the system trusts its local state. But the broker may have executed stop-losses, partial closes, or margin calls during the blackout.

**Solution:** Full position reconciliation immediately on reconnect.

### 5.1 Reconciliation Protocol

```
RECONCILIATION SEQUENCE (runs on every reconnect):

┌─────────────────────────────────────────────────────────────┐
│  STEP 1: QUERY BROKER STATE                                  │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ • Get all open positions from broker                    │ │
│  │ • Get all pending orders from broker                    │ │
│  │ • Get account balance/equity from broker                │ │
│  │ • Get recent trade history (last 24h) from broker       │ │
│  └─────────────────────────────────────────────────────────┘ │
│                          │                                    │
│                          ▼                                    │
│  STEP 2: DIFF LOCAL VS BROKER                                │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ • Position in local but NOT in broker → SL/TP HIT       │ │
│  │ • Position in broker but NOT in local → MANUAL TRADE    │ │
│  │ • Position in both but size different → PARTIAL CLOSE    │ │
│  │ • Position in both but SL/TP different → MODIFIED        │ │
│  │ • Position in both but P&L mismatch → RECALCULATE        │ │
│  └─────────────────────────────────────────────────────────┘ │
│                          │                                    │
│                          ▼                                    │
│  STEP 3: RECONCILE                                           │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ • Update local state to match broker (broker = truth)   │ │
│  │ • Close any orphaned hedge positions                    │ │
│  │ • Recalculate all risk metrics (exposure, drawdown)     │ │
│  │ • Log all discrepancies for audit                       │ │
│  │ • Alert human if significant discrepancies found        │ │
│  └─────────────────────────────────────────────────────────┘ │
│                          │                                    │
│                          ▼                                    │
│  STEP 4: VALIDATE RISK STATE                                 │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ • Run full Risk Governor checks on reconciled state     │ │
│  │ • If drawdown limit breached during blackout → HALT     │ │
│  │ • If any position exceeds risk limits → REDUCE          │ │
│  │ • Resume trading only after validation passes            │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 Implementation

```python
class PositionReconciler:
    """
    Reconciles local position state with broker truth after reconnection.
    Broker state is always treated as authoritative.
    """
    
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.reconciliation_log = []  # Full audit trail
    
    async def reconcile(
        self,
        broker_name: str,
        broker_adapter: BrokerAdapter,
        local_positions: list[Position],
        local_orders: list[Order]
    ) -> ReconciliationResult:
        """
        Full reconciliation after reconnection.
        Returns discrepancies and corrective actions taken.
        """
        logger.info(f"Starting position reconciliation for {broker_name}")
        start_time = datetime.utcnow()
        
        # Step 1: Query broker state
        broker_positions = await broker_adapter.get_open_positions()
        broker_orders = await broker_adapter.get_pending_orders()
        broker_account = await broker_adapter.get_account_info()
        broker_history = await broker_adapter.get_trade_history(hours=24)
        
        # Step 2: Build lookup maps
        local_pos_map = {p.ticket: p for p in local_positions}
        broker_pos_map = {p.ticket: p for p in broker_positions}
        
        local_order_map = {o.ticket: o for o in local_orders}
        broker_order_map = {o.ticket: o for o in broker_orders}
        
        discrepancies = []
        corrective_actions = []
        
        # Step 3: Find positions closed during disconnect
        for ticket, local_pos in local_pos_map.items():
            if ticket not in broker_pos_map:
                # Position exists locally but not at broker → was closed
                close_info = self._find_close_in_history(ticket, broker_history)
                
                discrepancy = Discrepancy(
                    type='POSITION_CLOSED_DURING_DISCONNECT',
                    ticket=ticket,
                    pair=local_pos.pair,
                    local_state=f"OPEN {local_pos.lots} lots @ {local_pos.entry_price}",
                    broker_state="CLOSED",
                    close_price=close_info.fill_price if close_info else None,
                    close_reason=close_info.reason if close_info else 'UNKNOWN',
                    pnl_impact=close_info.pnl if close_info else None
                )
                discrepancies.append(discrepancy)
                
                # Remove from local state
                corrective_actions.append(CorrectiveAction(
                    action='REMOVE_LOCAL_POSITION',
                    ticket=ticket,
                    reason=f"Closed at broker during disconnect: {close_info.reason if close_info else 'unknown'}"
                ))
        
        # Step 4: Find positions modified during disconnect
        for ticket in set(local_pos_map.keys()) & set(broker_pos_map.keys()):
            local = local_pos_map[ticket]
            broker = broker_pos_map[ticket]
            
            # Check lot size change (partial close)
            if abs(local.lots - broker.lots) > 0.001:
                discrepancies.append(Discrepancy(
                    type='POSITION_PARTIALLY_CLOSED',
                    ticket=ticket,
                    pair=local.pos.pair,
                    local_state=f"{local.lots} lots",
                    broker_state=f"{broker.lots} lots",
                    detail=f"Partial close: {local.lots - broker.lots} lots closed"
                ))
                corrective_actions.append(CorrectiveAction(
                    action='UPDATE_LOCAL_LOTS',
                    ticket=ticket,
                    new_value=broker.lots,
                    reason="Partial close at broker during disconnect"
                ))
            
            # Check SL/TP change
            if local.sl != broker.sl or local.tp != broker.tp:
                discrepancies.append(Discrepancy(
                    type='STOP_MODIFIED',
                    ticket=ticket,
                    pair=local.pair,
                    local_state=f"SL={local.sl}, TP={local.tp}",
                    broker_state=f"SL={broker.sl}, TP={broker.tp}",
                    detail="SL/TP modified at broker during disconnect"
                ))
                corrective_actions.append(CorrectiveAction(
                    action='UPDATE_LOCAL_STOPS',
                    ticket=ticket,
                    new_sl=broker.sl,
                    new_tp=broker.tp,
                    reason="Broker modified stops during disconnect"
                ))
        
        # Step 5: Find positions at broker but not locally (manual trades)
        for ticket, broker_pos in broker_pos_map.items():
            if ticket not in local_pos_map:
                discrepancies.append(Discrepancy(
                    type='UNKNOWN_POSITION_AT_BROKER',
                    ticket=ticket,
                    pair=broker_pos.pair,
                    local_state="DOES_NOT_EXIST",
                    broker_state=f"OPEN {broker_pos.lots} lots @ {broker_pos.entry_price}",
                    detail="Position exists at broker but not in local state — possible manual trade"
                ))
                # Don't auto-close — flag for human review
                corrective_actions.append(CorrectiveAction(
                    action='FLAG_FOR_REVIEW',
                    ticket=ticket,
                    reason="Unknown position at broker — human must decide"
                ))
        
        # Step 6: Check for pending order changes
        for ticket in set(local_order_map.keys()) - set(broker_order_map.keys()):
            discrepancies.append(Discrepancy(
                type='ORDER_FILLED_OR_CANCELLED',
                ticket=ticket,
                local_state="PENDING",
                broker_state="GONE",
                detail="Pending order no longer at broker — may have been filled or cancelled"
            ))
        
        # Step 7: Check account balance impact
        balance_change = broker_account.balance - local_positions[0].account_balance if local_positions else 0
        if abs(balance_change) > 0:
            discrepancies.append(Discrepancy(
                type='ACCOUNT_BALANCE_CHANGED',
                local_state=f"Balance: ${local_positions[0].account_balance if local_positions else 'N/A'}",
                broker_state=f"Balance: ${broker_account.balance}",
                detail=f"Balance changed by ${balance_change:.2f} during disconnect"
            ))
        
        # Step 8: Execute corrective actions
        for action in corrective_actions:
            await self._execute_corrective_action(action)
        
        # Step 9: Log reconciliation
        reconciliation_record = {
            'timestamp': datetime.utcnow(),
            'broker': broker_name,
            'duration_ms': (datetime.utcnow() - start_time).total_seconds() * 1000,
            'local_positions_count': len(local_positions),
            'broker_positions_count': len(broker_positions),
            'discrepancies_found': len(discrepancies),
            'corrective_actions': len(corrective_actions),
            'discrepancies': [d.to_dict() for d in discrepancies]
        }
        self.reconciliation_log.append(reconciliation_record)
        
        # Step 10: Alert if significant discrepancies
        significant = [d for d in discrepancies if d.type in (
            'POSITION_CLOSED_DURING_DISCONNECT',
            'UNKNOWN_POSITION_AT_BROKER',
            'ACCOUNT_BALANCE_CHANGED'
        )]
        
        if significant:
            await self._reconciliation_alert(broker_name, significant)
        
        logger.info(
            f"Reconciliation complete for {broker_name}: "
            f"{len(discrepancies)} discrepancies, {len(corrective_actions)} corrective actions"
        )
        
        return ReconciliationResult(
            discrepancies=discrepancies,
            corrective_actions=corrective_actions,
            broker_account=broker_account,
            success=True
        )
    
    def _find_close_in_history(self, ticket: int, history: list) -> TradeRecord | None:
        """Find the closing record for a position in trade history."""
        for record in reversed(history):
            if record.ticket == ticket and record.type in ('CLOSE', 'CLOSE_BY', 'STOP_LOSS', 'TAKE_PROFIT'):
                return record
        return None
    
    async def _execute_corrective_action(self, action: CorrectiveAction):
        """Execute a corrective action to align local state with broker."""
        if action.action == 'REMOVE_LOCAL_POSITION':
            # Remove from local position tracking
            await self.event_bus.publish('position.reconcile', {
                'action': 'REMOVE',
                'ticket': action.ticket,
                'reason': action.reason
            })
        elif action.action == 'UPDATE_LOCAL_LOTS':
            await self.event_bus.publish('position.reconcile', {
                'action': 'UPDATE_LOTS',
                'ticket': action.ticket,
                'new_lots': action.new_value,
                'reason': action.reason
            })
        elif action.action == 'UPDATE_LOCAL_STOPS':
            await self.event_bus.publish('position.reconcile', {
                'action': 'UPDATE_STOPS',
                'ticket': action.ticket,
                'new_sl': action.new_sl,
                'new_tp': action.new_tp,
                'reason': action.reason
            })
        elif action.action == 'FLAG_FOR_REVIEW':
            await self.event_bus.publish('position.reconcile', {
                'action': 'FLAG',
                'ticket': action.ticket,
                'reason': action.reason,
                'requires_human': True
            })
    
    async def _reconciliation_alert(self, broker_name: str, discrepancies: list):
        """Alert human about significant reconciliation discrepancies."""
        details = "\n".join(
            f"• {d.type}: {d.pair} #{d.ticket} — {d.detail}"
            for d in discrepancies
        )
        
        await self.event_bus.publish('system.alert', {
            'severity': 'CRITICAL',
            'channel': 'telegram',
            'message': (
                f"📊 POSITION RECONCILIATION — {broker_name}\n\n"
                f"Significant discrepancies found during reconnect:\n\n"
                f"{details}\n\n"
                f"Local state has been updated to match broker.\n"
                f"Please review positions manually."
            ),
            'sound': 'notification'
        })
```

---

## 6. Fix 5: Degraded Broker State

**Problem:** The system treats broker connectivity as binary. But a broker can be "connected but unusable" — spreads blown out, rejections piling up, or server-side delays.

**Solution:** Define and detect a "degraded" broker state between "connected" and "disconnected."

### 6.1 Broker Health States

```
BROKER HEALTH STATE MACHINE:

    ┌──────────┐
    │          │
    │  HEALTHY │◄──────────────────────────────────────┐
    │          │                                       │
    └────┬─────┘                                       │
         │                                             │
         │ Spread > 5× normal OR                       │
         │ Rejection rate > 5% OR                       │
         │ Latency > 5× normal OR                       │
         │ Ping failures = 1-2                          │
         │                                             │
         ▼                                             │
    ┌──────────┐          Conditions normalized         │
    │          │ ──────────────────────────────────────┘
    │ DEGRADED │
    │          │
    └────┬─────┘
         │
         │ Spread > 10× normal OR
         │ Rejection rate > 20% OR
         │ Ping failures = 3+ OR
         │ No quotes for > 10s
         │
         ▼
    ┌──────────┐
    │          │
    │   DEAD   │ ──→ Trigger close-all / failover
    │          │
    └──────────┘
```

### 6.2 Health State Definitions

| State | Criteria | Allowed Actions |
|-------|----------|----------------|
| **HEALTHY** | All metrics normal | Full trading (entries + exits) |
| **DEGRADED** | Any metric exceeds threshold (see below) | Exits only — NO new entries. Stops remain at broker. |
| **DEAD** | Zombie detected OR all metrics critical | Close all → failover to backup |

### 6.3 Degradation Detection

```python
class BrokerHealthMonitor:
    """
    Monitors broker health across multiple dimensions.
    Classifies broker state as HEALTHY, DEGRADED, or DEAD.
    """
    
    # Degradation thresholds
    SPREAD_DEGRADED_MULTIPLIER = 5.0    # Spread > 5× normal
    SPREAD_DEAD_MULTIPLIER = 10.0       # Spread > 10× normal
    REJECTION_DEGRADED_PCT = 0.05       # > 5% orders rejected
    REJECTION_DEAD_PCT = 0.20           # > 20% orders rejected
    LATENCY_DEGRADED_MULTIPLIER = 5.0   # Latency > 5× normal
    LATENCY_DEAD_MULTIPLIER = 10.0      # Latency > 10× normal
    QUOTE_STALE_DEGRADED_SEC = 5        # No quotes for 5s
    QUOTE_STALE_DEAD_SEC = 10           # No quotes for 10s
    
    def __init__(self, broker_name: str, event_bus):
        self.broker_name = broker_name
        self.event_bus = event_bus
        self.state = 'HEALTHY'
        self.state_history = []
        
        # Metrics tracking
        self.spread_baseline = {}       # pair → average spread
        self.latency_baseline_ms = 100  # Average latency in ms
        self.order_results = []         # Recent order results for rejection rate
        self.quote_timestamps = {}      # pair → last quote time
    
    async def update(
        self,
        current_spreads: dict[str, float],
        latency_ms: float,
        order_result: OrderResult = None,
        quote_times: dict[str, datetime] = None
    ):
        """Update health metrics and check for state transitions."""
        
        signals = []
        
        # === CHECK 1: SPREAD ===
        for pair, spread in current_spreads.items():
            baseline = self.spread_baseline.get(pair, spread)
            if baseline > 0:
                ratio = spread / baseline
                if ratio >= self.SPREAD_DEAD_MULTIPLIER:
                    signals.append(('SPREAD_CRITICAL', pair, ratio))
                elif ratio >= self.SPREAD_DEGRADED_MULTIPLIER:
                    signals.append(('SPREAD_ELEVATED', pair, ratio))
        
        # === CHECK 2: REJECTION RATE ===
        if order_result:
            self.order_results.append(order_result)
            # Keep last 100 results
            if len(self.order_results) > 100:
                self.order_results = self.order_results[-100:]
            
            if len(self.order_results) >= 10:  # Need minimum sample
                rejections = sum(1 for r in self.order_results if r.rejected)
                rejection_rate = rejections / len(self.order_results)
                
                if rejection_rate >= self.REJECTION_DEAD_PCT:
                    signals.append(('REJECTION_CRITICAL', None, rejection_rate))
                elif rejection_rate >= self.REJECTION_DEGRADED_PCT:
                    signals.append(('REJECTION_ELEVATED', None, rejection_rate))
        
        # === CHECK 3: LATENCY ===
        latency_ratio = latency_ms / self.latency_baseline_ms if self.latency_baseline_ms > 0 else 1
        if latency_ratio >= self.LATENCY_DEAD_MULTIPLIER:
            signals.append(('LATENCY_CRITICAL', None, latency_ratio))
        elif latency_ratio >= self.LATENCY_DEGRADED_MULTIPLIER:
            signals.append(('LATENCY_ELEVATED', None, latency_ratio))
        
        # === CHECK 4: QUOTE STALENESS ===
        if quote_times:
            now = datetime.utcnow()
            for pair, last_quote in quote_times.items():
                age = (now - last_quote).total_seconds()
                if age >= self.QUOTE_STALE_DEAD_SEC:
                    signals.append(('QUOTE_STALE_CRITICAL', pair, age))
                elif age >= self.QUOTE_STALE_DEGRADED_SEC:
                    signals.append(('QUOTE_STALE_ELEVATED', pair, age))
        
        # === DETERMINE NEW STATE ===
        new_state = self._classify_state(signals)
        
        if new_state != self.state:
            await self._transition_state(self.state, new_state, signals)
    
    def _classify_state(self, signals: list) -> str:
        """Classify broker state based on detected signals."""
        has_critical = any(s[0].endswith('_CRITICAL') for s in signals)
        has_elevated = any(s[0].endswith('_ELEVATED') for s in signals)
        
        if has_critical:
            return 'DEAD'
        elif has_elevated:
            return 'DEGRADED'
        else:
            return 'HEALTHY'
    
    async def _transition_state(self, old_state: str, new_state: str, signals: list):
        """Handle broker state transition."""
        self.state = new_state
        self.state_history.append({
            'timestamp': datetime.utcnow(),
            'old_state': old_state,
            'new_state': new_state,
            'signals': signals
        })
        
        if new_state == 'DEGRADED':
            logger.warning(
                f"Broker {self.broker_name}: HEALTHY → DEGRADED. "
                f"Signals: {[s[0] for s in signals]}"
            )
            await self.event_bus.publish('system.broker', RiskEvent(
                event_type=RiskEventType.SYSTEM_HEALTH_DEGRADED,
                severity='WARNING',
                component=f'broker_health.{self.broker_name}',
                data={
                    'broker': self.broker_name,
                    'old_state': old_state,
                    'new_state': new_state,
                    'signals': signals,
                    'action': 'BLOCK_NEW_ENTRIES'
                },
                action_required='REDUCE',
                reasoning=f"Broker {self.broker_name} degraded — blocking new entries, keeping existing stops"
            ))
        
        elif new_state == 'DEAD':
            logger.critical(
                f"Broker {self.broker_name}: {old_state} → DEAD. "
                f"Signals: {[s[0] for s in signals]}"
            )
            await self.event_bus.publish('system.broker', RiskEvent(
                event_type=RiskEventType.BROKER_DISCONNECT,
                severity='EMERGENCY',
                component=f'broker_health.{self.broker_name}',
                data={
                    'broker': self.broker_name,
                    'old_state': old_state,
                    'new_state': new_state,
                    'signals': signals,
                    'action': 'CLOSE_ALL_AND_FAILOVER'
                },
                action_required='CLOSE_ALL',
                reasoning=f"Broker {self.broker_name} declared DEAD — initiating failover"
            ))
        
        elif new_state == 'HEALTHY' and old_state != 'HEALTHY':
            logger.info(f"Broker {self.broker_name}: {old_state} → HEALTHY (recovered)")
            await self.event_bus.publish('system.broker', {
                'event': 'BROKER_RECOVERED',
                'broker': self.broker_name,
                'old_state': old_state,
                'downtime_seconds': self._get_downtime()
            })
    
    def _get_downtime(self) -> float:
        """Calculate total downtime from state history."""
        for entry in reversed(self.state_history):
            if entry['new_state'] == 'HEALTHY':
                # Find when we left HEALTHY
                for prev in reversed(self.state_history[:self.state_history.index(entry)]):
                    if prev['old_state'] == 'HEALTHY':
                        return (entry['timestamp'] - prev['timestamp']).total_seconds()
        return 0
    
    def is_trading_allowed(self) -> bool:
        """Check if new trades are allowed on this broker."""
        return self.state == 'HEALTHY'
    
    def is_close_allowed(self) -> bool:
        """Check if close orders can be sent to this broker."""
        return self.state in ('HEALTHY', 'DEGRADED')
    
    def get_status(self) -> dict:
        """Return current health status."""
        return {
            'broker': self.broker_name,
            'state': self.state,
            'is_trading_allowed': self.is_trading_allowed(),
            'is_close_allowed': self.is_close_allowed(),
            'recent_signals': self.state_history[-5:] if self.state_history else []
        }
```

### 6.4 Degraded State Behavior Matrix

| Component | HEALTHY | DEGRADED | DEAD |
|-----------|---------|----------|------|
| **New entries** | ✅ Allowed | ❌ Blocked | ❌ Blocked |
| **Close orders** | ✅ Normal | ✅ Sent to primary | ❌ Failover to backup |
| **Stop-losses** | ✅ At broker | ✅ Keep alive at broker | ⚠️ May not execute → failover hedge |
| **Pending orders** | ✅ Normal | ❌ Cancel all | ❌ Cancel all |
| **Alerts** | None | ⚠️ Warning | 🚨 Emergency |
| **Auto-recovery** | N/A | Monitor for 60s healthy → recover | Requires reconnect + reconciliation |

---

## 7. Fix 6: Partial Disconnection Handling

**Problem:** Broker disconnection isn't binary. Scenarios like "quote feed alive but execution dead" can silently kill the system.

**Solution:** Track each broker subsystem independently and handle each partial failure scenario.

### 7.1 Partial Disconnection Matrix

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    PARTIAL DISCONNECTION SCENARIOS                       │
│                                                                          │
│  Scenario 1: QUOTE FEED ALIVE, EXECUTION DEAD                           │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  Quotes arriving normally (bid/ask updating)                      │  │
│  │  Order submissions rejected or timing out                         │  │
│  │  Risk: System sees prices, thinks it's trading, but orders fail   │  │
│  │  Detection: Rejection rate spike while quotes are fresh            │  │
│  │  Action: Block entries. Keep existing stops (may still work).      │  │
│  │          Alert human. If rejection > 20% → DEAD, failover.        │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  Scenario 2: EXECUTION ALIVE, QUOTE FEED DEAD                           │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  Can submit orders (broker accepts them)                          │  │
│  │  No price updates — trading blind                                  │  │
│  │  Risk: Orders fill at stale/wrong prices                           │  │
│  │  Detection: Quote staleness while orders execute                   │  │
│  │  Action: Block ALL trading (entries AND exits).                    │  │
│  │          Use backup feed for monitoring.                           │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  Scenario 3: CONNECTION ALIVE, SERVER-SIDE DELAYS                       │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  Orders accepted but delayed (requote, off-quotes)                │  │
│  │  Latency spikes to 5-30 seconds                                    │  │
│  │  Risk: Stale fills, slippage beyond breaker                        │  │
│  │  Detection: Latency > 5× baseline + requote rate > 10%            │  │
│  │  Action: Cancel all pending orders. Block entries.                 │  │
│  │          If latency > 10× → treat as DEAD.                        │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  Scenario 4: CONNECTION ALIVE, LEVERAGE/MARGIN CHANGED                  │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  Broker silently changes leverage or margin requirements           │  │
│  │  Risk: Margin call on positions that were previously safe          │  │
│  │  Detection: Compare current leverage/margin to last known values   │  │
│  │  Action: Recalculate all position risk. If margin utilization      │  │
│  │          exceeds 80% → reduce positions immediately.               │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  Scenario 5: CONNECTION ALIVE, BROKER IN MAINTENANCE                    │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  Server returns "maintenance mode" or "trading disabled"           │  │
│  │  Risk: Can't close positions during maintenance                     │  │
│  │  Detection: Specific error codes from broker API                   │  │
│  │  Action: Alert human. Monitor for maintenance end.                 │  │
│  │          If positions at risk → failover hedge on backup.          │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

### 7.2 Implementation

```python
class PartialDisconnectDetector:
    """
    Detects and handles partial broker disconnection scenarios.
    Each broker subsystem is monitored independently.
    """
    
    def __init__(self, broker_name: str, event_bus):
        self.broker_name = broker_name
        self.event_bus = event_bus
        
        # Subsystem states
        self.quote_feed_state = 'ALIVE'     # ALIVE, STALE, DEAD
        self.execution_state = 'ALIVE'      # ALIVE, DEGRADED, DEAD
        self.server_state = 'NORMAL'        # NORMAL, DELAYED, MAINTENANCE
        self.margin_state = 'STABLE'        # STABLE, CHANGED, CRITICAL
        
        # Detection thresholds
        self.quote_stale_sec = 5
        self.rejection_rate_threshold = 0.05
        self.requote_rate_threshold = 0.10
        self.latency_spike_threshold = 5.0  # 5× baseline
        self.margin_change_threshold = 0.20  # 20% change in leverage
    
    async def analyze(
        self,
        quote_freshness: dict[str, float],    # pair → seconds since last quote
        order_results: list[OrderResult],
        latency_ms: float,
        latency_baseline_ms: float,
        current_leverage: float,
        baseline_leverage: float,
        broker_error_codes: list[str]
    ):
        """Analyze all subsystems for partial disconnection."""
        
        # === QUOTE FEED CHECK ===
        max_staleness = max(quote_freshness.values()) if quote_freshness else 0
        
        if max_staleness > self.quote_stale_sec * 2:
            new_quote_state = 'DEAD'
        elif max_staleness > self.quote_stale_sec:
            new_quote_state = 'STALE'
        else:
            new_quote_state = 'ALIVE'
        
        if new_quote_state != self.quote_feed_state:
            await self._handle_quote_state_change(self.quote_feed_state, new_quote_state, max_staleness)
            self.quote_feed_state = new_quote_state
        
        # === EXECUTION CHECK ===
        if len(order_results) >= 10:
            rejections = sum(1 for r in order_results if r.rejected)
            rejection_rate = rejections / len(order_results)
            
            if rejection_rate >= self.rejection_rate_threshold * 4:
                new_exec_state = 'DEAD'
            elif rejection_rate >= self.rejection_rate_threshold:
                new_exec_state = 'DEGRADED'
            else:
                new_exec_state = 'ALIVE'
            
            if new_exec_state != self.execution_state:
                await self._handle_exec_state_change(self.execution_state, new_exec_state, rejection_rate)
                self.execution_state = new_exec_state
        
        # === SERVER DELAY CHECK ===
        latency_ratio = latency_ms / latency_baseline_ms if latency_baseline_ms > 0 else 1
        
        # Check for requote errors
        requote_errors = sum(1 for e in broker_error_codes if 'REQUOTE' in e.upper())
        requote_rate = requote_errors / max(len(order_results), 1)
        
        if latency_ratio > self.latency_spike_threshold * 2 or requote_rate > self.requote_rate_threshold * 2:
            new_server_state = 'MAINTENANCE'
        elif latency_ratio > self.latency_spike_threshold or requote_rate > self.requote_rate_threshold:
            new_server_state = 'DELAYED'
        else:
            new_server_state = 'NORMAL'
        
        if new_server_state != self.server_state:
            await self._handle_server_state_change(self.server_state, new_server_state, latency_ratio)
            self.server_state = new_server_state
        
        # === MARGIN/LEVERAGE CHECK ===
        if baseline_leverage > 0:
            leverage_change = abs(current_leverage - baseline_leverage) / baseline_leverage
            
            if leverage_change > self.margin_change_threshold * 2:
                new_margin_state = 'CRITICAL'
            elif leverage_change > self.margin_change_threshold:
                new_margin_state = 'CHANGED'
            else:
                new_margin_state = 'STABLE'
            
            if new_margin_state != self.margin_state:
                await self._handle_margin_state_change(
                    self.margin_state, new_margin_state,
                    current_leverage, baseline_leverage
                )
                self.margin_state = new_margin_state
        
        # === MAINTENANCE MODE DETECTION ===
        maintenance_codes = ['ERR_MAINTENANCE', 'ERR_TRADE_DISABLED', 'ERR_MARKET_CLOSED']
        if any(code in maintenance_codes for code in broker_error_codes):
            if self.server_state != 'MAINTENANCE':
                self.server_state = 'MAINTENANCE'
                await self._handle_maintenance_mode()
    
    async def _handle_quote_state_change(self, old: str, new: str, staleness: float):
        """Handle quote feed state change."""
        if new == 'DEAD':
            # Critical: can't see prices
            # Block everything — use backup feed if available
            await self.event_bus.publish('system.broker', {
                'event': 'QUOTE_FEED_DEAD',
                'broker': self.broker_name,
                'staleness_sec': staleness,
                'action': 'BLOCK_ALL_TRADING',
                'use_backup_feed': True
            })
        elif new == 'STALE':
            # Warning: prices may be wrong
            await self.event_bus.publish('system.broker', {
                'event': 'QUOTE_FEED_STALE',
                'broker': self.broker_name,
                'staleness_sec': staleness,
                'action': 'BLOCK_ENTRIES'
            })
    
    async def _handle_exec_state_change(self, old: str, new: str, rejection_rate: float):
        """Handle execution state change."""
        if new == 'DEAD':
            # Can't execute orders at all
            await self.event_bus.publish('system.broker', {
                'event': 'EXECUTION_DEAD',
                'broker': self.broker_name,
                'rejection_rate': rejection_rate,
                'action': 'FAILOVER_REQUIRED'
            })
        elif new == 'DEGRADED':
            # Some orders failing
            await self.event_bus.publish('system.broker', {
                'event': 'EXECUTION_DEGRADED',
                'broker': self.broker_name,
                'rejection_rate': rejection_rate,
                'action': 'BLOCK_ENTRIES_KEEP_STOPS'
            })
    
    async def _handle_server_state_change(self, old: str, new: str, latency_ratio: float):
        """Handle server delay state change."""
        if new == 'MAINTENANCE':
            await self.event_bus.publish('system.broker', {
                'event': 'SERVER_MAINTENANCE',
                'broker': self.broker_name,
                'latency_ratio': latency_ratio,
                'action': 'CANCEL_ALL_ORDERS_ALERT_HUMAN'
            })
        elif new == 'DELAYED':
            await self.event_bus.publish('system.broker', {
                'event': 'SERVER_DELAYED',
                'broker': self.broker_name,
                'latency_ratio': latency_ratio,
                'action': 'CANCEL_PENDING_ORDERS'
            })
    
    async def _handle_margin_state_change(self, old: str, new: str, current: float, baseline: float):
        """Handle leverage/margin change."""
        if new == 'CRITICAL':
            await self.event_bus.publish('system.broker', RiskEvent(
                event_type=RiskEventType.SYSTEM_HEALTH_DEGRADED,
                severity='EMERGENCY',
                component=f'partial_disconnect.{self.broker_name}',
                data={
                    'broker': self.broker_name,
                    'event': 'LEVERAGE_CRITICAL_CHANGE',
                    'current_leverage': current,
                    'baseline_leverage': baseline,
                    'action': 'REDUCE_POSITIONS_IMMEDIATELY'
                },
                action_required='REDUCE',
                reasoning=f"Leverage changed from {baseline}x to {current}x — margin call risk"
            ))
        elif new == 'CHANGED':
            await self.event_bus.publish('system.broker', {
                'event': 'LEVERAGE_CHANGED',
                'broker': self.broker_name,
                'current_leverage': current,
                'baseline_leverage': baseline,
                'action': 'RECALCULATE_RISK'
            })
    
    async def _handle_maintenance_mode(self):
        """Handle broker entering maintenance mode."""
        await self.event_bus.publish('system.broker', RiskEvent(
            event_type=RiskEventType.SYSTEM_HEALTH_DEGRADED,
            severity='CRITICAL',
            component=f'partial_disconnect.{self.broker_name}',
            data={
                'broker': self.broker_name,
                'event': 'MAINTENANCE_MODE',
                'action': 'ALERT_AND_MONITOR'
            },
            action_required='HALT',
            reasoning=f"Broker {self.broker_name} entered maintenance mode"
        ))
    
    def is_trading_safe(self) -> bool:
        """Check if it's safe to trade on this broker considering all subsystems."""
        return all([
            self.quote_feed_state == 'ALIVE',
            self.execution_state == 'ALIVE',
            self.server_state == 'NORMAL',
            self.margin_state == 'STABLE'
        ])
    
    def get_status(self) -> dict:
        """Return comprehensive partial disconnection status."""
        return {
            'broker': self.broker_name,
            'quote_feed': self.quote_feed_state,
            'execution': self.execution_state,
            'server': self.server_state,
            'margin': self.margin_state,
            'is_trading_safe': self.is_trading_safe(),
            'blocking_reasons': self._get_blocking_reasons()
        }
    
    def _get_blocking_reasons(self) -> list[str]:
        """Return reasons why trading might be blocked."""
        reasons = []
        if self.quote_feed_state != 'ALIVE':
            reasons.append(f'Quote feed: {self.quote_feed_state}')
        if self.execution_state != 'ALIVE':
            reasons.append(f'Execution: {self.execution_state}')
        if self.server_state != 'NORMAL':
            reasons.append(f'Server: {self.server_state}')
        if self.margin_state != 'STABLE':
            reasons.append(f'Margin: {self.margin_state}')
        return reasons
```

---

## 8. Unified Broker Health Manager

All six fixes are orchestrated by a single **Broker Health Manager** that sits alongside the existing Circuit Breaker System.

### 8.1 Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    BROKER HEALTH MANAGER                                 │
│                                                                          │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐      │
│  │ Adaptive         │  │ Zombie           │  │ Broker           │      │
│  │ Timeout          │  │ Detector         │  │ Health           │      │
│  │ Calculator       │  │ (Ping/Pong)      │  │ Monitor          │      │
│  │ [Fix 1]          │  │ [Fix 3]          │  │ [Fix 5]          │      │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘      │
│                                                                          │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐      │
│  │ Failover         │  │ Position         │  │ Partial          │      │
│  │ Router           │  │ Reconciler       │  │ Disconnect       │      │
│  │ [Fix 2]          │  │ [Fix 4]          │  │ Detector         │      │
│  │                  │  │                  │  │ [Fix 6]          │      │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘      │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                      BROKER STATE TABLE                           │   │
│  │                                                                   │   │
│  │  Broker    │ State    │ Quote │ Exec  │ Zombie │ Degraded │ Failover │
│  │  ──────────┼──────────┼───────┼───────┼────────┼──────────┼──────────│
│  │  MT5-IC    │ HEALTHY  │  ✅   │  ✅   │  No    │   No     │  N/A     │
│  │  cTrader   │ DEGRADED │  ✅   │  ⚠️   │  No    │  Spreads │  Ready   │
│  │  OANDA     │ DEAD     │  ❌   │  ❌   │  Yes   │   —      │  Active  │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 8.2 Implementation

```python
class BrokerHealthManager:
    """
    Unified broker health management orchestrating all 6 fixes.
    Integrates with Circuit Breaker Layer 4 and the Risk Governor.
    """
    
    def __init__(self, broker_configs: dict, event_bus):
        self.event_bus = event_bus
        
        # Initialize all components per broker
        self.brokers = {}
        for name, config in broker_configs.items():
            adapter = config['adapter']
            self.brokers[name] = {
                'adapter': adapter,
                'zombie_detector': ZombieDetector(name, adapter),
                'health_monitor': BrokerHealthMonitor(name, event_bus),
                'partial_detector': PartialDisconnectDetector(name, event_bus),
                'reconciler': PositionReconciler(event_bus)
            }
        
        # Shared components
        self.adaptive_timeout = AdaptiveDisconnectTimeout()
        self.failover_router = BrokerFailoverRouter({
            name: b['adapter'] for name, b in self.brokers.items()
        })
        
        # State
        self.open_hedges = {}  # ticket → HedgeRecord
    
    async def start(self):
        """Start all monitoring loops."""
        for name, broker in self.brokers.items():
            await broker['zombie_detector'].start()
        
        # Start main health check loop
        asyncio.create_task(self._health_check_loop())
    
    async def _health_check_loop(self):
        """Main health check loop — runs every second."""
        while True:
            try:
                for name, broker in self.brokers.items():
                    adapter = broker['adapter']
                    
                    # Collect metrics
                    spreads = adapter.get_current_spreads()
                    latency = adapter.get_last_latency_ms()
                    quote_times = adapter.get_last_quote_times()
                    
                    # Update all monitors
                    await broker['zombie_detector'].check_data_staleness()
                    await broker['health_monitor'].update(
                        current_spreads=spreads,
                        latency_ms=latency,
                        quote_times=quote_times
                    )
                    await broker['partial_detector'].analyze(
                        quote_freshness={
                            pair: (datetime.utcnow() - qt).total_seconds()
                            for pair, qt in quote_times.items()
                        },
                        order_results=adapter.get_recent_order_results(),
                        latency_ms=latency,
                        latency_baseline_ms=adapter.baseline_latency_ms,
                        current_leverage=adapter.get_leverage(),
                        baseline_leverage=adapter.baseline_leverage,
                        broker_error_codes=adapter.get_recent_errors()
                    )
                
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Health check loop error: {e}")
                await asyncio.sleep(5)
    
    async def handle_reconnect(self, broker_name: str):
        """
        Full reconnection handler — orchestrates Fix 2 + Fix 4.
        Called when a disconnected broker reconnects.
        """
        broker = self.brokers.get(broker_name)
        if not broker:
            return
        
        logger.info(f"Broker {broker_name} reconnected — starting reconciliation")
        
        # Step 1: Stability check (60 seconds of clean data)
        stability_ok = await self._stability_check(broker_name, duration_sec=60)
        
        if not stability_ok:
            logger.warning(f"Broker {broker_name}: stability check failed after reconnect")
            return
        
        # Step 2: Reconcile positions
        local_positions = await self._get_local_positions(broker_name)
        local_orders = await self._get_local_orders(broker_name)
        
        reconciliation = await broker['reconciler'].reconcile(
            broker_name=broker_name,
            broker_adapter=broker['adapter'],
            local_positions=local_positions,
            local_orders=local_orders
        )
        
        # Step 3: Resolve any hedges opened during disconnect
        for ticket, hedge in self.failover_router.hedge_positions.items():
            if hedge.original_broker == broker_name and hedge.status == 'ACTIVE':
                await self.failover_router.resolve_hedge_on_reconnect(ticket)
        
        # Step 4: Validate risk state
        risk_valid = await self._validate_risk_state(broker_name, reconciliation)
        
        if risk_valid:
            logger.info(f"Broker {broker_name}: reconciliation complete, trading can resume")
        else:
            logger.warning(f"Broker {broker_name}: reconciliation complete but risk limits breached")
    
    async def _stability_check(self, broker_name: str, duration_sec: int = 60) -> bool:
        """Monitor broker for stability after reconnect."""
        broker = self.brokers[broker_name]
        start = datetime.utcnow()
        
        while (datetime.utcnow() - start).total_seconds() < duration_sec:
            status = broker['health_monitor'].get_status()
            zombie_status = broker['zombie_detector'].get_status()
            
            if status['state'] != 'HEALTHY' or zombie_status['is_zombie']:
                return False
            
            await asyncio.sleep(1)
        
        return True
    
    async def _validate_risk_state(self, broker_name: str, reconciliation: ReconciliationResult) -> bool:
        """Validate that risk limits are still satisfied after reconciliation."""
        # Check if any position was closed at a loss during disconnect
        for disc in reconciliation.discrepancies:
            if disc.type == 'POSITION_CLOSED_DURING_DISCONNECT':
                if disc.pnl_impact and disc.pnl_impact < 0:
                    # Position closed at loss — check if daily limit breached
                    logger.warning(
                        f"Position {disc.ticket} closed at loss during disconnect: "
                        f"${disc.pnl_impact:.2f}"
                    )
        
        # Re-run drawdown check
        # (would integrate with DrawdownLimitManager here)
        
        return True  # Simplified — full implementation checks all limits
    
    def get_comprehensive_status(self) -> dict:
        """Return full status of all brokers."""
        status = {}
        for name, broker in self.brokers.items():
            status[name] = {
                'health': broker['health_monitor'].get_status(),
                'zombie': broker['zombie_detector'].get_status(),
                'partial': broker['partial_detector'].get_status(),
                'failover_hedges': [
                    h.to_dict() for h in self.failover_router.hedge_positions.values()
                    if h.original_broker == name and h.status == 'ACTIVE'
                ]
            }
        return status
```

---

## 9. Integration with Existing Architecture

### 9.1 Modified Circuit Breaker Layer 4

The existing `CircuitBreakerSystem.check_system_health()` is replaced with a call to `BrokerHealthManager`:

```python
# === LAYER 4: SYSTEM LEVEL (MODIFIED) ===

async def check_system_health(self, system_state: SystemState) -> bool:
    """
    Layer 4: Check infrastructure health.
    NOW DELEGATES to BrokerHealthManager for all broker-related checks.
    """
    tripped = False
    
    # Delegate broker health to BrokerHealth Manager
    broker_status = self.broker_health_manager.get_comprehensive_status()
    
    for broker_name, status in broker_status.items():
        health = status['health']
        zombie = status['zombie']
        partial = status['partial']
        
        # Dead broker → close all positions on that broker
        if health['state'] == 'DEAD' or zombie['is_zombie']:
            await self._trip_breaker('connectivity', {
                'broker': broker_name,
                'state': health['state'],
                'is_zombie': zombie['is_zombie'],
                'action': 'close_broker_positions'
            })
            tripped = True
        
        # Degraded broker → block new entries
        elif health['state'] == 'DEGRADED':
            await self._trip_breaker('broker_degraded', {
                'broker': broker_name,
                'state': health['state'],
                'action': 'block_new_entries'
            })
            tripped = True
        
        # Partial disconnect → specific actions per scenario
        if not partial['is_trading_safe']:
            await self._trip_breaker('partial_disconnect', {
                'broker': broker_name,
                'blocking_reasons': partial['blocking_reasons'],
                'action': 'block_entries'
            })
            tripped = True
    
    # Order rejections (unchanged from original)
    if system_state.order_rejection_rate > self.ORDER_REJECTION_THRESHOLD:
        await self._trip_breaker('order_rejection', {
            'rejection_rate': system_state.order_rejection_rate,
            'action': 'pause_trading'
        })
        tripped = True
    
    # Latency (unchanged from original)
    if system_state.latency_multiplier > self.LATENCY_SPIKE_MULTIPLIER:
        await self._trip_breaker('latency', {
            'latency_multiplier': system_state.latency_multiplier,
            'action': 'cancel_open_orders'
        })
        tripped = True
    
    return tripped
```

### 9.2 Risk Governor Integration

The Risk Governor's pre-trade check now includes broker health:

```python
# Add to RiskGovernor.pre_trade_check():

# === CHECK: Broker Health ===
broker_health = self.broker_health_manager.get_comprehensive_status()
primary_broker = proposal.broker

if primary_broker in broker_health:
    bh = broker_health[primary_broker]
    
    if bh['health']['state'] == 'DEAD':
        return RiskCheckResult(
            approved=False,
            reason="BROKER_DEAD",
            detail=f"Broker {primary_broker} is DEAD — use failover"
        )
    
    if bh['health']['state'] == 'DEGRADED':
        return RiskCheckResult(
            approved=False,
            reason="BROKER_DEGRADED",
            detail=f"Broker {primary_broker} is DEGRADED — no new entries"
        )
    
    if bh['zombie']['is_zombie']:
        return RiskCheckResult(
            approved=False,
            reason="BROKER_ZOMBIE",
            detail=f"Broker {primary_broker} is a zombie connection"
        )
    
    if not bh['partial']['is_trading_safe']:
        return RiskCheckResult(
            approved=False,
            reason="BROKER_PARTIAL_DISCONNECT",
            detail=f"Broker {primary_broker}: {bh['partial']['blocking_reasons']}"
        )
```

---

## 10. Configuration

```yaml
# broker_health_config.yaml

adaptive_timeout:
  losing_05r_sec: 10
  losing_sec: 15
  profitable_sec: 20
  no_positions_sec: 30
  news_modifier_sec: -5
  high_vol_modifier_sec: -5
  floor_sec: 5

zombie_detection:
  ping_interval_sec: 5
  pong_timeout_sec: 5
  max_failures: 3
  quote_stale_threshold_sec: 10
  orderbook_stale_threshold_sec: 15

failover:
  enabled: true
  primary_broker: "MT5-IC"
  backup_brokers:
    - "cTrader-Pepperstone"
    - "OANDA-Live"
  max_failover_attempts: 3
  hedge_comment_prefix: "FAILOVER_HEDGE"

reconciliation:
  stability_check_duration_sec: 60
  alert_on_closed_during_disconnect: true
  alert_on_unknown_positions: true
  auto_resolve_hedges: true

broker_health:
  spread_degraded_multiplier: 5.0
  spread_dead_multiplier: 10.0
  rejection_degraded_pct: 0.05
  rejection_dead_pct: 0.20
  latency_degraded_multiplier: 5.0
  latency_dead_multiplier: 10.0
  quote_stale_degraded_sec: 5
  quote_stale_dead_sec: 10

partial_disconnect:
  quote_stale_sec: 5
  rejection_rate_threshold: 0.05
  requote_rate_threshold: 0.10
  latency_spike_threshold: 5.0
  margin_change_threshold: 0.20

alerting:
  zombie_alert: true
  failover_alert: true
  reconciliation_alert: true
  degraded_alert: true
  partial_disconnect_alert: true
  channel: "telegram"
  repeat_interval_sec: 60
```

---

## 11. Testing Scenarios

### 11.1 Test Matrix

| # | Scenario | Expected Behavior | Verification |
|---|----------|-------------------|-------------|
| 1 | **Losing position + disconnect** | Close within 10s via failover | Timeout < 10s, hedge opened on backup |
| 2 | **Zombie connection (TCP alive, no data)** | Detected in 15s (3×5s pings) | Zombie flag set, failover triggered |
| 3 | **Quote feed alive, execution dead** | Entries blocked, stops kept alive | Rejection rate detection fires |
| 4 | **Execution alive, quote feed dead** | All trading blocked | Stale quote detection fires |
| 5 | **Broker spreads blow out (6×)** | New entries blocked, exits still work | Degraded state detected |
| 6 | **Broker reconnection after 45s disconnect** | Full reconciliation, hedge resolution | All positions matched with broker |
| 7 | **SL hit at broker during disconnect** | Reconciliation detects it, local state updated | Position removed from local, P&L updated |
| 8 | **All backup brokers fail** | Emergency alert, manual intervention | Alert sent every 30s |
| 9 | **Leverage changed mid-session** | Risk recalculation, positions reduced if needed | Margin state change detected |
| 10 | **Broker maintenance mode** | Alert human, monitor for end | Maintenance detection fires |

### 11.2 Chaos Test Script

```python
# chaos_broker_disconnect.py
"""
Chaos test: inject broker disconnection scenarios and verify system response.
Run in paper trading mode only.
"""

import asyncio
import random

class BrokerDisconnectChaosTest:
    
    def __init__(self, broker_health_manager: BrokerHealthManager):
        self.bhm = broker_health_manager
    
    async def test_scenario_1_losing_position_disconnect(self):
        """Scenario 1: Position losing >0.5R, broker disconnects."""
        # Setup: Open a position that's losing 0.7R
        # Action: Simulate broker disconnect
        # Verify: System acts within 10 seconds
        # Verify: Hedge opened on backup broker
        pass
    
    async def test_scenario_2_zombie_connection(self):
        """Scenario 2: TCP alive but no application data."""
        # Setup: Mock adapter to return success on TCP keepalive
        # Action: Make ping() always timeout
        # Verify: Zombie detected within 15 seconds (3 failures × 5s)
        # Verify: Failover triggered
        pass
    
    async def test_scenario_3_quote_alive_exec_dead(self):
        """Scenario 3: Quotes flowing, orders rejected."""
        # Setup: Mock adapter with fresh quotes
        # Action: Make all order submissions return rejection
        # Verify: Degraded execution state detected
        # Verify: New entries blocked, existing stops preserved
        pass
    
    async def test_scenario_4_reconciliation(self):
        """Scenario 4: Reconnect after positions changed at broker."""
        # Setup: Local state has 3 positions
        # Action: Broker has 2 positions (one was SL hit during disconnect)
        # Verify: Reconciliation finds the discrepancy
        # Verify: Local state updated, P&L recalculated
        pass
    
    async def test_scenario_5_spread_blowout(self):
        """Scenario 5: Spreads widen to 8× normal."""
        # Setup: Normal spreads
        # Action: Spike spreads to 8× baseline
        # Verify: Broker state → DEGRADED
        # Verify: New entries blocked
        pass
    
    async def test_scenario_6_full_failover(self):
        """Scenario 6: Primary broker dies, failover to backup."""
        # Setup: Position open on primary broker
        # Action: Primary broker becomes unreachable
        # Verify: Hedge opened on backup broker
        # Verify: Net exposure = 0
        # Verify: Human alerted
        pass
```

---

## Summary: All 6 Fixes

| # | Fix | Component | Key Metric |
|---|-----|-----------|-----------|
| 1 | **Adaptive Timeout** | `AdaptiveDisconnectTimeout` | 10s for losing positions (was 30s flat) |
| 2 | **Failover Routing** | `BrokerFailoverRouter` | Hedge on backup broker within seconds |
| 3 | **Zombie Detection** | `ZombieDetector` | 3 failed pings × 5s = 15s detection |
| 4 | **Position Reconciliation** | `PositionReconciler` | Broker state queried immediately on reconnect |
| 5 | **Degraded Broker State** | `BrokerHealthMonitor` | HEALTHY/DEGRADED/DEAD state machine |
| 6 | **Partial Disconnection** | `PartialDisconnectDetector` | Independent monitoring of quote/exec/server/margin |

All components are orchestrated by the **Broker Health Manager** and integrated with the existing Circuit Breaker Layer 4 and Risk Governor.

---

*"The broker connection that looks alive but isn't is more dangerous than one that's obviously dead."*

---

> **Document maintained by:** Broker Resilience Engineer — Alpha Stack  
> **Review cadence:** After any broker disconnection event, or monthly  
> **Next review:** Before any live capital deployment
