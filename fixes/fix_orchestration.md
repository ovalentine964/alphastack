# Agent Orchestration — Top 5 Fix Design

> **Version:** 1.0 · **Date:** 2026-07-11 · **Author:** Orchestration Fix Agent
> **Source:** `review_agent_orchestration.md` (H-6, H-3, H-1, H-5, H-2)
> **Status:** Implementation-Ready Design Specifications

---

## Table of Contents

1. [Fix #1: Unify Confluence Scoring vs Consensus Formula (H-6)](#fix-1-unify-confluence-scoring-vs-consensus-formula-h-6)
2. [Fix #2: Redis HA + Persistent Position State Backup (H-3)](#fix-2-redis-ha--persistent-position-state-backup-h-3)
3. [Fix #3: Orchestrator Redundancy — Hot-Standby with Leader Election (H-1)](#fix-3-orchestrator-redundancy--hot-standby-with-leader-election-h-1)
4. [Fix #4: Cascade Failure Detection Triggers (H-5)](#fix-4-cascade-failure-detection-triggers-h-5)
5. [Fix #5: Parallel Instrument Pipelines (H-2)](#fix-5-parallel-instrument-pipelines-h-2)
6. [Implementation Order & Dependencies](#implementation-order--dependencies)

---

## Fix #1: Unify Confluence Scoring vs Consensus Formula (H-6)

### Problem

Two disconnected scoring systems exist:

| System | Range | Purpose | Used By |
|--------|-------|---------|---------|
| **Confluence Matrix** | 0–100+ | Signal quality score (presence + bonuses) | Pipeline flow diagram (≥40 threshold) |
| **Consensus Formula** | 0–1 | Weighted directional agreement | Consensus section |

An implementer cannot know which is authoritative. The confluence score says "this setup scores 65" while the consensus formula says "directional agreement is 0.87" — these are unrelated numbers measuring different things.

### Solution: Two-Stage Gate Architecture

**Stage 1 — Confluence Score (Signal Quality Gate):**
Measures *how many independent signals align*. This is a prerequisite filter — a trade needs sufficient signal coverage before direction even matters.

**Stage 2 — Weighted Consensus (Directional Agreement Gate):**
Measures *how strongly the aligned signals agree on direction*. This is the directional confirmation — signals must not just exist but agree.

A trade requires **both** gates to pass. This eliminates ambiguity: confluence answers "is there enough evidence?" and consensus answers "does the evidence agree?"

### Implementation

#### Stage 1: Confluence Score (Authoritative Gate: ≥40 to proceed)

```python
# confluence_engine.py

class ConfluenceEngine:
    """
    Computes signal quality score from the 7 specialist agents.
    Score range: 0–100+
    
    This is the FIRST gate. If confluence < 40, the pipeline stops.
    Direction doesn't matter if there isn't enough evidence.
    """
    
    # Base weights per signal type (sum to 100 for a perfect setup)
    SIGNAL_WEIGHTS = {
        'fundamental':  15,   # S1: Macro/event analysis
        'bias':         10,   # S2: Multi-timeframe directional bias
        'session':      10,   # S3: Session/volatility context
        'structure':    20,   # S4: Market structure (BOS/CHoCH)
        'sr_levels':    15,   # S5: Support/resistance zones
        'liquidity':    10,   # S6: Liquidity pool mapping
        'smc':          20,   # S7: Smart money concepts (FVG, OB, IFVG)
    }
    
    # Bonus/penalty modifiers
    BONUS_RULES = {
        'htf_alignment':     +10,  # H4 + H1 + M15 all agree
        'session_overlap':   +5,   # London-NY overlap active
        'news_proximity':    -15,  # High-impact event within 30min
        'conflict_penalty':  -20,  # Fundamental vs technical disagree >0.7
        'regime_alignment':  +5,   # Signal matches current regime
    }
    
    MINIMUM_VOTERS = 4  # At least 4 of 7 agents must provide signals
    
    def compute(self, agent_signals: dict) -> dict:
        """
        Args:
            agent_signals: {
                'fundamental': {'active': True, 'vote': 0.8, 'confidence': 0.9},
                'bias': {'active': True, 'vote': 0.6, 'confidence': 0.7},
                ...
            }
        
        Returns:
            {
                'confluence_score': int,       # 0–100+
                'signals_active': int,          # count of active signals
                'gate_passed': bool,            # score >= 40
                'rejection_reason': str|None,   # why gate failed
                'breakdown': dict,              # per-signal contribution
                'bonuses_applied': list,        # which bonuses/penalties
            }
        """
        active_signals = {
            k: v for k, v in agent_signals.items()
            if v.get('active', False)
        }
        
        # Gate: minimum voters
        if len(active_signals) < self.MINIMUM_VOTERS:
            return {
                'confluence_score': 0,
                'signals_active': len(active_signals),
                'gate_passed': False,
                'rejection_reason': f'Insufficient voters: {len(active_signals)}/{self.MINIMUM_VOTERS} required',
                'breakdown': {},
                'bonuses_applied': [],
            }
        
        # Compute base score
        score = 0
        breakdown = {}
        for signal_type, weight in self.SIGNAL_WEIGHTS.items():
            if signal_type in active_signals:
                sig = active_signals[signal_type]
                # Signal contributes proportional to its confidence
                contribution = weight * min(sig.get('confidence', 0.5), 1.0)
                score += contribution
                breakdown[signal_type] = round(contribution, 1)
            else:
                breakdown[signal_type] = 0
        
        # Apply bonuses/penalties
        bonuses_applied = []
        for rule, modifier in self.BONUS_RULES.items():
            if self._check_bonus_rule(rule, agent_signals, active_signals):
                score += modifier
                bonuses_applied.append({'rule': rule, 'modifier': modifier})
        
        score = max(0, round(score))  # Floor at 0
        
        return {
            'confluence_score': score,
            'signals_active': len(active_signals),
            'gate_passed': score >= 40,
            'rejection_reason': None if score >= 40 else f'Confluence {score} < 40 minimum',
            'breakdown': breakdown,
            'bonuses_applied': bonuses_applied,
        }
    
    def _check_bonus_rule(self, rule, all_signals, active_signals):
        """Evaluate bonus/penalty conditions. Implementation depends on signal data."""
        # HTF alignment: H4, H1, M15 all same direction
        if rule == 'htf_alignment':
            htf = [s for k, s in active_signals.items() 
                   if k in ('bias', 'structure', 'smc')]
            return len(htf) >= 3 and all(
                s.get('vote', 0) > 0.5 for s in htf
            ) or all(s.get('vote', 0) < 0.5 for s in htf)
        
        # Conflict: fundamental and technical disagree strongly
        if rule == 'conflict_penalty':
            fund = active_signals.get('fundamental', {})
            tech = active_signals.get('smc', {})
            if fund and tech:
                return abs(fund.get('vote', 0.5) - tech.get('vote', 0.5)) > 0.7
            return False
        
        # News proximity: checked against calendar:today in Redis
        if rule == 'news_proximity':
            # Implementation: check Redis calendar:today for events within 30min
            return False  # Placeholder
        
        return False
```

#### Stage 2: Weighted Consensus (Directional Agreement Gate: ≥0.65 to trade)

```python
# consensus_engine.py

class ConsensusEngine:
    """
    Computes weighted directional agreement from agent votes.
    Score range: 0.0–1.0
    
    This is the SECOND gate. Only evaluated if confluence gate passed.
    Answers: "Do the active signals agree on DIRECTION?"
    """
    
    # Adaptive weights (updated weekly by Reflection Agent)
    # These start equal and adjust based on historical accuracy
    DEFAULT_WEIGHTS = {
        'fundamental':  0.10,
        'bias':         0.10,
        'session':      0.10,
        'structure':    0.20,
        'sr_levels':    0.15,
        'liquidity':    0.10,
        'smc':          0.25,
    }
    
    # Adaptive weight bounds
    MIN_WEIGHT = 0.05
    MAX_WEIGHT = 0.35
    MAX_WEIGHT_CHANGE_PER_WEEK = 0.03  # Prevent over-correction (M-9 fix)
    
    # Minimum agreement threshold
    CONSENSUS_THRESHOLD = 0.65
    
    def compute(self, agent_signals: dict, weights: dict = None) -> dict:
        """
        Args:
            agent_signals: Same format as ConfluenceEngine
            weights: Optional override weights (from adaptive system)
        
        Returns:
            {
                'consensus_score': float,      # 0.0–1.0
                'direction': str,               # 'long' | 'short' | 'neutral'
                'directional_strength': float,  # How far from 0.5
                'gate_passed': bool,            # score >= 0.65
                'rejection_reason': str|None,
                'vote_breakdown': dict,
            }
        """
        if weights is None:
            weights = self.DEFAULT_WEIGHTS
        
        active_signals = {
            k: v for k, v in agent_signals.items()
            if v.get('active', False) and k in weights
        }
        
        if not active_signals:
            return {
                'consensus_score': 0,
                'direction': 'neutral',
                'directional_strength': 0,
                'gate_passed': False,
                'rejection_reason': 'No active signals for consensus',
                'vote_breakdown': {},
            }
        
        # Normalize weights to sum to 1.0 for active signals only
        active_weight_sum = sum(weights[k] for k in active_signals)
        normalized_weights = {
            k: weights[k] / active_weight_sum for k in active_signals
        }
        
        # Weighted consensus formula:
        # Σ(weight × vote × confidence) / Σ(weight × confidence)
        numerator = 0
        denominator = 0
        vote_breakdown = {}
        
        for sig_type, sig_data in active_signals.items():
            w = normalized_weights[sig_type]
            vote = sig_data.get('vote', 0.5)      # 0=full short, 0.5=neutral, 1=full long
            conf = sig_data.get('confidence', 0.5)  # 0–1
            
            contribution = w * vote * conf
            weight_conf = w * conf
            
            numerator += contribution
            denominator += weight_conf
            
            vote_breakdown[sig_type] = {
                'weight': round(w, 3),
                'vote': vote,
                'confidence': conf,
                'contribution': round(contribution, 4),
            }
        
        if denominator == 0:
            consensus = 0.5
        else:
            consensus = numerator / denominator
        
        # Determine direction
        if consensus > 0.55:
            direction = 'long'
        elif consensus < 0.45:
            direction = 'short'
        else:
            direction = 'neutral'
        
        directional_strength = abs(consensus - 0.5) * 2  # 0–1 scale
        
        return {
            'consensus_score': round(consensus, 4),
            'direction': direction,
            'directional_strength': round(directional_strength, 4),
            'gate_passed': directional_strength >= (self.CONSENSUS_THRESHOLD - 0.5) * 2,
            'rejection_reason': None if directional_strength >= 0.3 else 'Insufficient directional agreement',
            'vote_breakdown': vote_breakdown,
        }
```

#### Unified Pipeline Integration

```python
# pipeline_decision.py

class TradeDecisionPipeline:
    """
    Two-stage gate: Confluence → Consensus → Trade
    
    Flow:
    1. Compute confluence score (signal quality)
    2. If confluence >= 40: compute consensus (directional agreement)
    3. If consensus >= 0.65 strength: proceed to position sizing
    4. Risk Gate has final veto (infrastructure-level, code-only)
    """
    
    def __init__(self):
        self.confluence = ConfluenceEngine()
        self.consensus = ConsensusEngine()
    
    def evaluate(self, agent_signals: dict) -> dict:
        # Stage 1: Confluence
        confluence_result = self.confluence.compute(agent_signals)
        
        if not confluence_result['gate_passed']:
            return {
                'decision': 'NO_TRADE',
                'stage_failed': 'confluence',
                'confluence': confluence_result,
                'consensus': None,
                'reason': confluence_result['rejection_reason'],
            }
        
        # Stage 2: Consensus
        consensus_result = self.consensus.compute(agent_signals)
        
        if not consensus_result['gate_passed']:
            return {
                'decision': 'NO_TRADE',
                'stage_failed': 'consensus',
                'confluence': confluence_result,
                'consensus': consensus_result,
                'reason': consensus_result['rejection_reason'],
            }
        
        # Both gates passed
        return {
            'decision': 'TRADE_CANDIDATE',
            'stage_failed': None,
            'confluence': confluence_result,
            'consensus': consensus_result,
            'direction': consensus_result['direction'],
            'confluence_score': confluence_result['confluence_score'],
            'consensus_strength': consensus_result['directional_strength'],
            'reason': f"Confluence {confluence_result['confluence_score']}, "
                      f"consensus {consensus_result['consensus_score']} "
                      f"({consensus_result['direction']})",
        }
```

#### Adaptive Weight Update Rules (M-9 Fix Integrated)

```python
# weight_adjuster.py

class AdaptiveWeightAdjuster:
    """
    Weekly weight adjustment based on agent accuracy.
    
    Anti-manipulation rules (from M-9 review finding):
    - Minimum 100 trades lookback (not 50)
    - Statistical significance required (p < 0.05)
    - Max ±0.03 change per week
    - 50/50 blend for first 200 trades (not 70/30)
    """
    
    MIN_LOOKBACK_TRADES = 100
    MAX_CHANGE_PER_WEEK = 0.03
    SIGNIFICANCE_THRESHOLD = 0.05  # p-value
    EARLY_TRADE_THRESHOLD = 200    # Use 50/50 blend before this
    
    def adjust_weights(self, agent_accuracies: dict, total_trades: int,
                       current_weights: dict) -> dict:
        blend_ratio = 0.7 if total_trades > self.EARLY_TRADE_THRESHOLD else 0.5
        
        new_weights = {}
        for agent, accuracy_data in agent_accuracies.items():
            recent_acc = accuracy_data['recent_accuracy']   # Last N trades
            historical_acc = accuracy_data['all_time_accuracy']
            n_recent = accuracy_data['recent_count']
            
            # Skip if insufficient data
            if n_recent < self.MIN_LOOKBACK_TRADES:
                new_weights[agent] = current_weights.get(agent, 0.1)
                continue
            
            # Statistical significance check
            p_value = accuracy_data.get('p_value', 1.0)
            if p_value > self.SIGNIFICANCE_THRESHOLD:
                # Difference not significant — keep current weight
                new_weights[agent] = current_weights.get(agent, 0.1)
                continue
            
            # Compute target weight
            blended = (blend_ratio * recent_acc + (1 - blend_ratio) * historical_acc)
            target = 0.05 + (blended * 0.30)  # Map accuracy to 0.05–0.35 range
            
            # Clamp change magnitude
            current = current_weights.get(agent, 0.1)
            delta = target - current
            delta = max(-self.MAX_CHANGE_PER_WEEK, min(self.MAX_CHANGE_PER_WEEK, delta))
            
            new_weights[agent] = round(
                max(ConfluenceEngine.MIN_WEIGHT, 
                    min(ConfluenceEngine.MAX_WEIGHT, current + delta)),
                3
            )
        
        return new_weights
```

### Data Flow Diagram

```
                    ┌─────────────────────┐
                    │   Agent Signals      │
                    │  (7 specialist       │
                    │   agents vote)       │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │   STAGE 1:           │
                    │   CONFLUENCE SCORE   │
                    │   (0–100 scale)      │
                    │                      │
                    │   ≥40 → PASS         │
                    │   <40 → NO_TRADE     │
                    └──────────┬──────────┘
                               │ PASS
                    ┌──────────▼──────────┐
                    │   STAGE 2:           │
                    │   WEIGHTED CONSENSUS │
                    │   (0.0–1.0 scale)    │
                    │                      │
                    │   strength ≥0.3 →    │
                    │     PASS             │
                    │   strength <0.3 →    │
                    │     NO_TRADE         │
                    └──────────┬──────────┘
                               │ PASS
                    ┌──────────▼──────────┐
                    │   RISK GATE          │
                    │   (Code-only,        │
                    │    infrastructure)    │
                    │                      │
                    │   Veto or Approve    │
                    └──────────┬──────────┘
                               │ APPROVE
                    ┌──────────▼──────────┐
                    │   TRADE EXECUTION    │
                    └─────────────────────┘
```

---

## Fix #2: Redis HA + Persistent Position State Backup (H-3)

### Problem

Single Redis node with volatile position data:

- Redis crash = total system failure (all state, messages, positions lost)
- `state:positions` in memory = position data loss risk during outage
- No failover = positions unprotected during Redis downtime
- Kill switch uses fire-and-forget Pub/Sub — missed by disconnected agents

### Solution: Three-Layer Resilience Architecture

```
Layer 1: Redis Sentinel (automatic failover)
Layer 2: PostgreSQL persistent backup (position state survives total Redis loss)
Layer 3: Broker API reconciliation (ground truth from broker itself)
```

### Implementation

#### Layer 1: Redis Sentinel Deployment

```yaml
# docker-compose.redis-ha.yml

version: '3.8'

services:
  redis-primary:
    image: redis:7-alpine
    container_name: alpha-redis-primary
    command: >
      redis-server
      --port 6379
      --requirepass ${REDIS_PASSWORD}
      --maxmemory 512mb
      --maxmemory-policy allkeys-lru
      --appendonly yes
      --appendfsync everysec
      --save 900 1
      --save 300 10
      --save 60 10000
      --min-replicas-to-write 1
      --min-replicas-max-lag 10
    ports:
      - "6379:6379"
    volumes:
      - redis-primary-data:/data
    networks:
      - alpha-net
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3

  redis-replica-1:
    image: redis:7-alpine
    container_name: alpha-redis-replica-1
    command: >
      redis-server
      --port 6380
      --replicaof redis-primary 6379
      --masterauth ${REDIS_PASSWORD}
      --requirepass ${REDIS_PASSWORD}
      --appendonly yes
    ports:
      - "6380:6380"
    depends_on:
      - redis-primary
    networks:
      - alpha-net

  redis-replica-2:
    image: redis:7-alpine
    container_name: alpha-redis-replica-2
    command: >
      redis-server
      --port 6381
      --replicaof redis-primary 6379
      --masterauth ${REDIS_PASSWORD}
      --requirepass ${REDIS_PASSWORD}
      --appendonly yes
    ports:
      - "6381:6381"
    depends_on:
      - redis-primary
    networks:
      - alpha-net

  sentinel-1:
    image: redis:7-alpine
    container_name: alpha-sentinel-1
    command: >
      redis-sentinel /etc/redis/sentinel.conf
    volumes:
      - ./sentinel-1.conf:/etc/redis/sentinel.conf
    ports:
      - "26379:26379"
    depends_on:
      - redis-primary
      - redis-replica-1
      - redis-replica-2
    networks:
      - alpha-net

  sentinel-2:
    image: redis:7-alpine
    container_name: alpha-sentinel-2
    command: >
      redis-sentinel /etc/redis/sentinel.conf
    volumes:
      - ./sentinel-2.conf:/etc/redis/sentinel.conf
    ports:
      - "26380:26379"
    depends_on:
      - redis-primary
      - redis-replica-1
      - redis-replica-2
    networks:
      - alpha-net

  sentinel-3:
    image: redis:7-alpine
    container_name: alpha-sentinel-3
    command: >
      redis-sentinel /etc/redis/sentinel.conf
    volumes:
      - ./sentinel-3.conf:/etc/redis/sentinel.conf
    ports:
      - "26381:26379"
    depends_on:
      - redis-primary
      - redis-replica-1
      - redis-replica-2
    networks:
      - alpha-net

volumes:
  redis-primary-data:

networks:
  alpha-net:
    driver: bridge
```

```conf
# sentinel.conf (identical for all 3 sentinels, different port bindings)

port 26379
sentinel monitor alpha-master redis-primary 6379 2
sentinel auth-pass alpha-master ${REDIS_PASSWORD}
sentinel down-after-milliseconds alpha-master 5000
sentinel failover-timeout alpha-master 10000
sentinel parallel-syncs alpha-master 1
```

**Failover behavior:**
- Sentinel detects primary down after 5 seconds
- Quorum (2 of 3 sentinels) must agree
- Replica promoted to primary within 10 seconds
- Total failover time: **~10–15 seconds**
- Clients reconnect to new primary via Sentinel discovery

#### Layer 2: PostgreSQL Position State Backup

```sql
-- Position state backup table (TimescaleDB hypertable)
CREATE TABLE position_state (
    time            TIMESTAMPTZ     NOT NULL,
    account_id      TEXT            NOT NULL,
    symbol          TEXT            NOT NULL,
    side            TEXT            NOT NULL,   -- 'long' | 'short'
    volume          DOUBLE PRECISION NOT NULL,
    entry_price     DOUBLE PRECISION NOT NULL,
    current_price   DOUBLE PRECISION,
    stop_loss       DOUBLE PRECISION,
    take_profit_1   DOUBLE PRECISION,
    take_profit_2   DOUBLE PRECISION,
    take_profit_3   DOUBLE PRECISION,
    pnl_unrealized  DOUBLE PRECISION,
    status          TEXT            NOT NULL,   -- 'open' | 'partial' | 'closed'
    agent_id        TEXT,                       -- Which agent opened it
    strategy_id     TEXT,                       -- Which strategy
    open_time       TIMESTAMPTZ     NOT NULL,
    last_update     TIMESTAMPTZ     NOT NULL,
    redis_version   BIGINT,                     -- Redis HINCRBY version for conflict detection
    PRIMARY KEY (time, account_id, symbol)
);

SELECT create_hypertable('position_state', 'time',
    chunk_time_interval => INTERVAL '1 day');

-- Latest position state view (for reconciliation)
CREATE MATERIALIZED VIEW position_latest AS
SELECT DISTINCT ON (account_id, symbol)
    account_id, symbol, side, volume, entry_price,
    stop_loss, take_profit_1, take_profit_2, take_profit_3,
    status, open_time, last_update, redis_version
FROM position_state
ORDER BY account_id, symbol, time DESC;
```

```python
# position_state_manager.py

import redis
import json
import time
import psycopg2
from datetime import datetime, timezone

class PositionStateManager:
    """
    Manages position state across Redis (hot) and PostgreSQL (persistent).
    
    Write path: Redis first → async PostgreSQL backup
    Read path: Redis first → fallback to PostgreSQL → fallback to broker API
    Reconciliation: Every 60 seconds, compare all three sources
    """
    
    REDIS_KEY_PREFIX = "position:"
    PG_TABLE = "position_state"
    BACKUP_INTERVAL_SEC = 5  # Async PG backup every 5 seconds
    RECONCILE_INTERVAL_SEC = 60
    
    def __init__(self, redis_client: redis.Redis, pg_conn, broker_client):
        self.redis = redis_client
        self.pg = pg_conn
        self.broker = broker_client
        self._last_backup = 0
        self._last_reconcile = 0
    
    # ── Write Path ──────────────────────────────────────────────
    
    def update_position(self, account_id: str, symbol: str, 
                        position_data: dict) -> bool:
        """
        Update position in Redis + queue PostgreSQL backup.
        Uses Redis HSET with version tracking for conflict detection.
        """
        key = f"{self.REDIS_KEY_PREFIX}{account_id}:{symbol}"
        
        # Increment version for conflict detection
        version = self.redis.hincrby(key, "redis_version", 1)
        position_data['redis_version'] = version
        position_data['last_update'] = datetime.now(timezone.utc).isoformat()
        
        # Atomic Redis update
        pipe = self.redis.pipeline()
        pipe.hset(key, mapping={k: str(v) for k, v in position_data.items()})
        pipe.expire(key, 86400)  # 24h TTL as safety net
        pipe.execute()
        
        # Async PostgreSQL backup (non-blocking)
        self._queue_pg_backup(account_id, symbol, position_data)
        
        return True
    
    def close_position(self, account_id: str, symbol: str) -> bool:
        """Mark position as closed in Redis + backup to PostgreSQL."""
        key = f"{self.REDIS_KEY_PREFIX}{account_id}:{symbol}"
        
        pipe = self.redis.pipeline()
        pipe.hset(key, "status", "closed")
        pipe.hset(key, "last_update", datetime.now(timezone.utc).isoformat())
        pipe.hincrby(key, "redis_version", 1)
        pipe.expire(key, 300)  # Keep for 5 min after close for dedup
        pipe.execute()
        
        # Immediate PG backup for closed positions
        self._backup_to_pg(account_id, symbol, {"status": "closed"})
        
        return True
    
    # ── Read Path (Three-Level Fallback) ────────────────────────
    
    def get_position(self, account_id: str, symbol: str) -> dict | None:
        """
        Read position with three-level fallback:
        1. Redis (hot, fastest)
        2. PostgreSQL (persistent, survives Redis loss)
        3. Broker API (ground truth)
        """
        # Level 1: Redis
        key = f"{self.REDIS_KEY_PREFIX}{account_id}:{symbol}"
        redis_data = self.redis.hgetall(key)
        
        if redis_data:
            return {k.decode(): v.decode() for k, v in redis_data.items()}
        
        # Level 2: PostgreSQL
        pg_data = self._read_from_pg(account_id, symbol)
        if pg_data and pg_data.get('status') == 'open':
            # Restore to Redis (cache warming)
            self.redis.hset(key, mapping={k: str(v) for k, v in pg_data.items()})
            self.redis.expire(key, 86400)
            return pg_data
        
        # Level 3: Broker API (ground truth)
        broker_data = self.broker.get_position(account_id, symbol)
        if broker_data:
            # Restore to both Redis and PostgreSQL
            self.update_position(account_id, symbol, broker_data)
            return broker_data
        
        return None
    
    def get_all_positions(self, account_id: str) -> list:
        """Get all open positions for an account."""
        pattern = f"{self.REDIS_KEY_PREFIX}{account_id}:*"
        keys = self.redis.keys(pattern)
        
        positions = []
        for key in keys:
            data = self.redis.hgetall(key)
            if data:
                decoded = {k.decode(): v.decode() for k, v in data.items()}
                if decoded.get('status') == 'open':
                    positions.append(decoded)
        
        return positions
    
    # ── PostgreSQL Backup ───────────────────────────────────────
    
    def _queue_pg_backup(self, account_id, symbol, data):
        """Queue async PostgreSQL backup (batched for performance)."""
        now = time.time()
        if now - self._last_backup < self.BACKUP_INTERVAL_SEC:
            return  # Will be picked up in next batch
        
        self._backup_to_pg(account_id, symbol, data)
        self._last_backup = now
    
    def _backup_to_pg(self, account_id, symbol, data):
        """Write position state to PostgreSQL."""
        with self.pg.cursor() as cur:
            cur.execute(f"""
                INSERT INTO {self.PG_TABLE} 
                (time, account_id, symbol, side, volume, entry_price,
                 stop_loss, take_profit_1, take_profit_2, take_profit_3,
                 status, last_update, redis_version)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                datetime.now(timezone.utc),
                account_id, symbol,
                data.get('side'), data.get('volume'), data.get('entry_price'),
                data.get('stop_loss'), data.get('take_profit_1'),
                data.get('take_profit_2'), data.get('take_profit_3'),
                data.get('status', 'open'),
                data.get('last_update'),
                data.get('redis_version'),
            ))
        self.pg.commit()
    
    def _read_from_pg(self, account_id, symbol) -> dict | None:
        """Read latest position from PostgreSQL."""
        with self.pg.cursor() as cur:
            cur.execute("""
                SELECT side, volume, entry_price, stop_loss,
                       take_profit_1, take_profit_2, take_profit_3,
                       status, last_update, redis_version
                FROM position_state
                WHERE account_id = %s AND symbol = %s
                ORDER BY time DESC LIMIT 1
            """, (account_id, symbol))
            row = cur.fetchone()
            
            if row:
                return {
                    'side': row[0], 'volume': row[1], 'entry_price': row[2],
                    'stop_loss': row[3], 'take_profit_1': row[4],
                    'take_profit_2': row[5], 'take_profit_3': row[6],
                    'status': row[7], 'last_update': str(row[8]),
                    'redis_version': row[9],
                }
        return None
    
    # ── Reconciliation ──────────────────────────────────────────
    
    def reconcile(self) -> dict:
        """
        Three-way reconciliation: Redis vs PostgreSQL vs Broker.
        Runs every 60 seconds. Alerts on discrepancies.
        
        Returns:
            {
                'redis_positions': int,
                'pg_positions': int,
                'broker_positions': int,
                'discrepancies': list,
                'actions_taken': list,
            }
        """
        now = time.time()
        if now - self._last_reconcile < self.RECONCILE_INTERVAL_SEC:
            return {'skipped': True, 'reason': 'Too soon'}
        
        self._last_reconcile = now
        
        # Get positions from all three sources
        redis_positions = {
            p['symbol']: p for p in self.get_all_positions('main')
        }
        broker_positions = {
            p['symbol']: p for p in self.broker.get_all_positions()
        }
        
        discrepancies = []
        actions = []
        
        all_symbols = set(redis_positions.keys()) | set(broker_positions.keys())
        
        for symbol in all_symbols:
            redis_pos = redis_positions.get(symbol)
            broker_pos = broker_positions.get(symbol)
            
            # Case 1: Position in Redis but not at broker (ghost position)
            if redis_pos and not broker_pos:
                discrepancies.append({
                    'symbol': symbol,
                    'type': 'ghost_position',
                    'detail': 'Position in Redis but not at broker',
                    'severity': 'CRITICAL',
                })
                # Auto-fix: close the ghost position in Redis
                self.close_position('main', symbol)
                actions.append(f"Closed ghost position: {symbol}")
            
            # Case 2: Position at broker but not in Redis (orphan position)
            elif broker_pos and not redis_pos:
                discrepancies.append({
                    'symbol': symbol,
                    'type': 'orphan_position',
                    'detail': 'Position at broker but not in Redis',
                    'severity': 'CRITICAL',
                })
                # Auto-fix: restore position to Redis + PG
                self.update_position('main', symbol, broker_pos)
                actions.append(f"Restored orphan position: {symbol}")
            
            # Case 3: Size mismatch
            elif redis_pos and broker_pos:
                redis_vol = float(redis_pos.get('volume', 0))
                broker_vol = float(broker_pos.get('volume', 0))
                if abs(redis_vol - broker_vol) > 0.001:
                    discrepancies.append({
                        'symbol': symbol,
                        'type': 'size_mismatch',
                        'detail': f"Redis={redis_vol}, Broker={broker_vol}",
                        'severity': 'HIGH',
                    })
                    # Auto-fix: trust broker (ground truth)
                    self.update_position('main', symbol, broker_pos)
                    actions.append(f"Reconciled size for {symbol}: broker={broker_vol}")
        
        return {
            'redis_positions': len(redis_positions),
            'broker_positions': len(broker_positions),
            'discrepancies': discrepancies,
            'actions_taken': actions,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }
    
    # ── State Recovery on Startup ───────────────────────────────
    
    def recover_state(self) -> dict:
        """
        Called on system startup. Restores state from best available source.
        
        Priority: Broker API (ground truth) > PostgreSQL > Redis
        Redis may have stale data if it crashed and recovered from RDB/AOF.
        """
        broker_positions = self.broker.get_all_positions()
        
        recovered = 0
        for pos in broker_positions:
            key = f"{self.REDIS_KEY_PREFIX}main:{pos['symbol']}"
            self.redis.hset(key, mapping={k: str(v) for k, v in pos.items()})
            self.redis.expire(key, 86400)
            self._backup_to_pg('main', pos['symbol'], pos)
            recovered += 1
        
        return {
            'positions_recovered': recovered,
            'source': 'broker_api',
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }
```

#### Layer 3: Enhanced Kill Switch (Persistent + Pub/Sub)

```python
# kill_switch.py

class KillSwitchManager:
    """
    Kill switch uses BOTH Pub/Sub (immediate) AND persistent flag (survives disconnect).
    
    Review M-2 finding: Pub/Sub is fire-and-forget. Agents that miss the message
    continue trading during a drawdown crisis.
    
    Solution: Dual-channel delivery + periodic re-publish + startup check.
    """
    
    KILL_SWITCH_KEY = "system:kill_switch"
    KILL_SWITCH_STREAM = "stream:kill_switch"
    REPUBLISH_INTERVAL_SEC = 10  # Re-publish every 10 seconds while active
    
    def activate(self, reason: str, activated_by: str = "orchestrator"):
        """Activate kill switch. Stops all trading immediately."""
        timestamp = datetime.now(timezone.utc).isoformat()
        
        state = {
            'active': 'true',
            'reason': reason,
            'activated_by': activated_by,
            'activated_at': timestamp,
        }
        
        pipe = self.redis.pipeline()
        
        # Persistent flag (survives agent restarts)
        pipe.hset(self.KILL_SWITCH_KEY, mapping=state)
        
        # Stream entry (durable, ordered)
        pipe.xadd(self.KILL_SWITCH_STREAM, {
            'event': 'kill_switch_activated',
            'reason': reason,
            'activated_by': activated_by,
            'timestamp': timestamp,
        })
        
        # Pub/Sub (immediate delivery to connected agents)
        pipe.publish('kill_switch', json.dumps(state))
        
        pipe.execute()
        
        # Start re-publish loop (ensures newly-connected agents get the signal)
        self._start_republish_loop()
    
    def deactivate(self, deactivated_by: str = "orchestrator"):
        """Deactivate kill switch. Resume trading."""
        state = {
            'active': 'false',
            'deactivated_by': deactivated_by,
            'deactivated_at': datetime.now(timezone.utc).isoformat(),
        }
        
        pipe = self.redis.pipeline()
        pipe.hset(self.KILL_SWITCH_KEY, mapping=state)
        pipe.xadd(self.KILL_SWITCH_STREAM, {
            'event': 'kill_switch_deactivated',
            'deactivated_by': deactivated_by,
        })
        pipe.publish('kill_switch', json.dumps(state))
        pipe.execute()
        
        self._stop_republish_loop()
    
    def is_active(self) -> bool:
        """Check kill switch state. Agents call this on EVERY pipeline start."""
        state = self.redis.hgetall(self.KILL_SWITCH_KEY)
        if not state:
            return False
        return state.get(b'active', b'false') == b'true'
    
    def check_or_halt(self, agent_id: str):
        """
        Called at the start of every pipeline. If kill switch is active,
        raise KillSwitchActive exception to halt the pipeline.
        """
        if self.is_active():
            state = self.redis.hgetall(self.KILL_SWITCH_KEY)
            raise KillSwitchActive(
                f"Kill switch active: {state.get(b'reason', b'unknown').decode()} "
                f"(activated {state.get(b'activated_at', b'unknown').decode()})"
            )
    
    def _start_republish_loop(self):
        """Background task: re-publish kill switch state periodically."""
        # Implementation: asyncio task or thread that publishes every 10s
        pass
    
    def _stop_republish_loop(self):
        """Stop the re-publish loop."""
        pass
```

#### Client Connection Factory (Sentinel-Aware)

```python
# redis_factory.py

from redis.sentinel import Sentinel

class RedisFactory:
    """
    Creates Redis clients that are Sentinel-aware.
    Automatic failover: if primary goes down, client reconnects to new primary.
    """
    
    def __init__(self, sentinel_hosts: list, password: str, service_name: str = "alpha-master"):
        """
        Args:
            sentinel_hosts: [('host1', 26379), ('host2', 26380), ('host3', 26381)]
            password: Redis AUTH password
            service_name: Sentinel master name
        """
        self.sentinel = Sentinel(
            sentinel_hosts,
            socket_timeout=0.5,
            socket_connect_timeout=0.5,
            password=password,
        )
        self.service_name = service_name
        self._password = password
    
    def get_master(self) -> redis.Redis:
        """Get connection to current primary (writable)."""
        return self.sentinel.master_for(
            self.service_name,
            socket_timeout=2,
            socket_connect_timeout=2,
            password=self._password,
            decode_responses=True,
        )
    
    def get_replica(self) -> redis.Redis:
        """Get connection to a read replica (read-only)."""
        return self.sentinel.slave_for(
            self.service_name,
            socket_timeout=2,
            socket_connect_timeout=2,
            password=self._password,
            decode_responses=True,
        )
    
    def get_master_for_pipeline(self):
        """Get master connection optimized for pipeline operations."""
        master = self.get_master()
        master.config_set('client-output-buffer-limit', 
                          'normal 0 0 0 replica 268435456 67108864 60 pubsub 33554432 8388608 60')
        return master
```

### Redis Client Usage in Agents

```python
# Every agent uses this pattern:

class BaseAgent:
    def __init__(self):
        self.redis_factory = RedisFactory(
            sentinel_hosts=[
                ('sentinel-1', 26379),
                ('sentinel-2', 26380),
                ('sentinel-3', 26381),
            ],
            password=os.environ['REDIS_PASSWORD'],
        )
        self.redis = self.redis_factory.get_master()
        self.redis_ro = self.redis_factory.get_replica()  # For reads
        
        self.kill_switch = KillSwitchManager(self.redis)
        self.position_mgr = PositionStateManager(
            self.redis, pg_conn, broker_client
        )
    
    async def run_pipeline(self, symbol: str):
        # Check kill switch FIRST (every pipeline start)
        self.kill_switch.check_halt(self.agent_id)
        
        # Read-heavy operations use replica
        signals = self.redis_ro.hgetall(f"signal:{symbol}")
        
        # Writes go to master (auto-failover via Sentinel)
        self.redis.hset(f"signal:{self.agent_id}:{symbol}", mapping=result)
```

---

## Fix #3: Orchestrator Redundancy — Hot-Standby with Leader Election (H-1)

### Problem

The Orchestrator Agent (Depth 0) is a single point of failure:

- No pipeline routing if it crashes
- No HITL checkpoints enforced
- No agent health monitoring
- All instruments go offline simultaneously
- Pipeline state is in-process memory — lost on crash

### Solution: Hot-Standby with Redis-Based Leader Election

```
┌──────────────────────────────────────────────────────────────┐
│                  ORCHESTRATOR REDUNDANCY                       │
│                                                               │
│  ┌─────────────┐         ┌─────────────┐                    │
│  │  Primary     │ ◄─────► │  Standby     │                    │
│  │  Orchestrator│ heartbeat│  Orchestrator│                    │
│  │  (ACTIVE)    │         │  (HOT-STANDBY)│                   │
│  └──────┬──────┘         └──────┬──────┘                    │
│         │                       │                             │
│         └───────────┬───────────┘                             │
│                     │                                         │
│            ┌────────▼────────┐                                │
│            │  Redis Sentinel  │                                │
│            │  (Leader Lock)   │                                │
│            │  TTL: 5 seconds  │                                │
│            └─────────────────┘                                │
│                                                               │
│  All pipeline state in Redis (not in-process memory)          │
│  Failover time: < 5 seconds                                   │
└──────────────────────────────────────────────────────────────┘
```

### Implementation

```python
# orchestrator_leader.py

import redis
import time
import json
import threading
from datetime import datetime, timezone
from enum import Enum

class OrchestratorRole(Enum):
    ACTIVE = "active"
    STANDBY = "standby"
    UNKNOWN = "unknown"


class LeaderElection:
    """
    Redis-based leader election for Orchestrator redundancy.
    
    Mechanism:
    - Both instances try to acquire a Redis lock (SET NX with TTL)
    - The lock holder is the ACTIVE orchestrator
    - The non-holder is the STANDBY
    - Standby monitors the lock; if it expires, standby takes over
    
    Failover time: lock TTL (5 seconds) + detection latency (~1 second) = ~6 seconds
    """
    
    LEADER_LOCK_KEY = "orchestrator:leader_lock"
    LEADER_HEARTBEAT_KEY = "orchestrator:leader_heartbeat"
    LEADER_STATE_KEY = "orchestrator:state"
    LOCK_TTL_SEC = 5
    HEARTBEAT_INTERVAL_SEC = 2  # Must be < LOCK_TTL_SEC
    FAILOVER_CHECK_INTERVAL_SEC = 1
    
    def __init__(self, redis_client: redis.Redis, instance_id: str):
        self.redis = redis_client
        self.instance_id = instance_id
        self.role = OrchestratorRole.UNKNOWN
        self._running = False
        self._heartbeat_thread = None
        self._monitor_thread = None
        self._on_become_active = None  # Callback
        self._on_become_standby = None  # Callback
    
    def start(self, on_become_active=None, on_become_standby=None):
        """
        Start the leader election process.
        Call callbacks when role changes.
        """
        self._on_become_active = on_become_active
        self._on_become_standby = on_become_standby
        self._running = True
        
        # Try to acquire leadership immediately
        self._try_acquire()
        
        # Start background threads
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop, daemon=True
        )
        self._heartbeat_thread.start()
        
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, daemon=True
        )
        self._monitor_thread.start()
    
    def stop(self):
        """Graceful shutdown — release leadership if held."""
        self._running = False
        
        if self.role == OrchestratorRole.ACTIVE:
            # Release the lock so standby can take over immediately
            self.redis.delete(self.LEADER_LOCK_KEY)
            self.redis.delete(self.LEADER_HEARTBEAT_KEY)
            self._publish_role_change("standby_shutdown")
        
        self.role = OrchestratorRole.UNKNOWN
    
    def _try_acquire(self) -> bool:
        """Attempt to acquire the leader lock."""
        acquired = self.redis.set(
            self.LEADER_LOCK_KEY,
            self.instance_id,
            nx=True,  # Only if not exists
            ex=self.LOCK_TTL_SEC,
        )
        
        if acquired:
            self._set_role(OrchestratorRole.ACTIVE)
            self._publish_role_change("acquired")
            return True
        
        # Check who holds the lock
        holder = self.redis.get(self.LEADER_LOCK_KEY)
        if holder and holder.decode() == self.instance_id:
            # We already hold it (re-acquire after restart)
            self.redis.expire(self.LEADER_LOCK_KEY, self.LOCK_TTL_SEC)
            self._set_role(OrchestratorRole.ACTIVE)
            return True
        
        self._set_role(OrchestratorRole.STANDBY)
        return False
    
    def _heartbeat_loop(self):
        """
        ACTIVE: Extend lock TTL + publish heartbeat every 2 seconds.
        This prevents the lock from expiring while the active instance is healthy.
        """
        while self._running:
            if self.role == OrchestratorRole.ACTIVE:
                try:
                    # Extend lock TTL
                    current_holder = self.redis.get(self.LEADER_LOCK_KEY)
                    if current_holder and current_holder.decode() == self.instance_id:
                        self.redis.expire(self.LEADER_LOCK_KEY, self.LOCK_TTL_SEC)
                        
                        # Publish heartbeat with state
                        heartbeat = {
                            'instance_id': self.instance_id,
                            'timestamp': datetime.now(timezone.utc).isoformat(),
                            'active_pipelines': self._get_active_pipeline_count(),
                            'healthy_agents': self._get_healthy_agent_count(),
                        }
                        self.redis.set(
                            self.LEADER_HEARTBEAT_KEY,
                            json.dumps(heartbeat),
                            ex=self.LOCK_TTL_SEC,
                        )
                    else:
                        # Lost the lock — become standby
                        self._set_role(OrchestratorRole.STANDBY)
                except redis.RedisError:
                    pass  # Transient error, keep trying
            
            time.sleep(self.HEARTBEAT_INTERVAL_SEC)
    
    def _monitor_loop(self):
        """
        STANDBY: Watch for lock expiration. Take over if active fails.
        """
        while self._running:
            if self.role == OrchestratorRole.STANDBY:
                try:
                    # Check if lock exists
                    holder = self.redis.get(self.LEADER_LOCK_KEY)
                    
                    if not holder:
                        # Lock expired — active instance failed
                        # Attempt to acquire
                        if self._try_acquire():
                            # We are now the active orchestrator
                            self._on_failover()
                    else:
                        # Lock exists — active is healthy
                        # Read heartbeat for monitoring
                        heartbeat = self.redis.get(self.LEADER_HEARTBEAT_KEY)
                        if heartbeat:
                            hb = json.loads(heartbeat)
                            # Log for monitoring
                            pass
                
                except redis.RedisError:
                    # Redis connection issue — try to acquire lock
                    # (if Redis is down, both instances will be in UNKNOWN state)
                    self._set_role(OrchestratorRole.UNKNOWN)
            
            time.sleep(self.FAILOVER_CHECK_INTERVAL_SEC)
    
    def _on_failover(self):
        """
        Called when standby takes over as active.
        Restores pipeline state from Redis (not in-process memory).
        """
        # Publish failover event
        self.redis.xadd("stream:system", {
            'event': 'orchestrator_failover',
            'new_leader': self.instance_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        })
        
        # Restore pipeline state from Redis
        self._restore_pipeline_state()
        
        # Notify agents of new orchestrator
        self.redis.publish('system:orchestrator', json.dumps({
            'event': 'new_leader',
            'instance_id': self.instance_id,
        }))
        
        # Invoke callback
        if self._on_become_active:
            self._on_become_active()
    
    def _restore_pipeline_state(self):
        """
        Restore all pipeline state from Redis.
        This is why pipeline state MUST be in Redis, not in-process memory.
        """
        # Read all active pipeline states
        pipeline_keys = self.redis.keys("pipeline:*:state")
        
        for key in pipeline_keys:
            state = self.redis.hgetall(key)
            if state:
                decoded = {k.decode(): v.decode() for k, v in state.items()}
                if decoded.get('status') == 'running':
                    # Resume pipeline from last checkpoint
                    self._resume_pipeline(decoded)
    
    def _resume_pipeline(self, pipeline_state: dict):
        """Resume a pipeline from its last Redis-persisted checkpoint."""
        pipeline_id = pipeline_state.get('pipeline_id')
        last_phase = pipeline_state.get('last_completed_phase', '0')
        symbol = pipeline_state.get('symbol')
        
        # Resume from the next phase
        next_phase = int(last_phase) + 1
        # ... resume logic ...
    
    def _set_role(self, new_role: OrchestratorRole):
        if self.role != new_role:
            old_role = self.role
            self.role = new_role
            
            # Publish role change
            self.redis.xadd("stream:system", {
                'event': 'orchestrator_role_change',
                'instance_id': self.instance_id,
                'old_role': old_role.value,
                'new_role': new_role.value,
            })
            
            # Invoke callbacks
            if new_role == OrchestratorRole.ACTIVE and self._on_become_active:
                self._on_become_active()
            elif new_role == OrchestratorRole.STANDBY and self._on_become_standby:
                self._on_become_standby()
    
    def _publish_role_change(self, reason: str):
        self.redis.xadd("stream:system", {
            'event': 'orchestrator_role_change',
            'instance_id': self.instance_id,
            'role': self.role.value,
            'reason': reason,
        })
    
    def _get_active_pipeline_count(self) -> int:
        keys = self.redis.keys("pipeline:*:state")
        count = 0
        for key in keys:
            state = self.redis.hget(key, "status")
            if state and state.decode() == "running":
                count += 1
        return count
    
    def _get_healthy_agent_count(self) -> int:
        keys = self.redis.keys("agent:*:heartbeat")
        count = 0
        now = time.time()
        for key in keys:
            ts = self.redis.get(key)
            if ts and (now - float(ts.decode())) < 30:
                count += 1
        return count


class OrchestratorInstance:
    """
    Complete orchestrator instance with leader election.
    Run two instances of this class for redundancy.
    """
    
    def __init__(self, instance_id: str, redis_factory: 'RedisFactory'):
        self.instance_id = instance_id
        self.redis_factory = redis_factory
        self.redis = redis_factory.get_master()
        
        self.leader = LeaderElection(self.redis, instance_id)
        self.pipeline_router = PipelineRouter(self.redis)  # Code-only, no LLM
        self.kill_switch = KillSwitchManager(self.redis)
    
    def start(self):
        """Start orchestrator with leader election."""
        self.leader.start(
            on_become_active=self._on_active,
            on_become_standby=self._on_standby,
        )
    
    def stop(self):
        """Graceful shutdown."""
        self.leader.stop()
    
    def _on_active(self):
        """Called when this instance becomes the active orchestrator."""
        # Start pipeline scheduling
        self.pipeline_router.start()
        # Start agent health monitoring
        self._start_health_monitor()
        # Start HITL checkpoint processing
        self._start_hitl_processor()
    
    def _on_standby(self):
        """Called when this instance becomes standby."""
        # Stop active processing (if any)
        self.pipeline_router.stop()
        # Keep monitoring (ready to take over)
```

### Pipeline State Persistence

```python
# pipeline_state.py

class PipelineState:
    """
    Pipeline state MUST be in Redis for failover to work.
    Not in-process memory.
    """
    
    STATE_KEY = "pipeline:{pipeline_id}:state"
    
    def __init__(self, redis_client, pipeline_id: str, symbol: str):
        self.redis = redis_client
        self.pipeline_id = pipeline_id
        self.key = self.STATE_KEY.format(pipeline_id=pipeline_id)
    
    def save_checkpoint(self, phase: int, phase_result: dict):
        """Save pipeline checkpoint to Redis after each phase completes."""
        pipe = self.redis.pipeline()
        pipe.hset(self.key, mapping={
            'pipeline_id': self.pipeline_id,
            'symbol': self.symbol,
            'last_completed_phase': str(phase),
            'status': 'running',
            'updated_at': datetime.now(timezone.utc).isoformat(),
            'phase_result': json.dumps(phase_result),
        })
        pipe.expire(self.key, 3600)  # 1h TTL
        pipe.execute()
    
    def mark_complete(self, result: dict):
        """Mark pipeline as complete."""
        self.redis.hset(self.key, mapping={
            'status': 'complete',
            'result': json.dumps(result),
            'completed_at': datetime.now(timezone.utc).isoformat(),
        })
    
    def mark_failed(self, error: str):
        """Mark pipeline as failed."""
        self.redis.hset(self.key, mapping={
            'status': 'failed',
            'error': error,
            'failed_at': datetime.now(timezone.utc).isoformat(),
        })
    
    def get_state(self) -> dict:
        """Get current pipeline state from Redis."""
        data = self.redis.hgetall(self.key)
        if not data:
            return None
        return {k.decode(): v.decode() for k, v in data.items()}
```

---

## Fix #4: Cascade Failure Detection Triggers (H-5)

### Problem

The architecture defines Level 4/5 circuit breakers but doesn't specify **how to detect a cascade failure**. Without explicit rules, the Monitor Agent cannot escalate in time.

### Solution: Explicit Cascade Detection Rules with Correlation Engine

```
┌──────────────────────────────────────────────────────────────────────┐
│                    CASCADE DETECTION SYSTEM                           │
│                                                                       │
│  Level 1: Single agent failure      → Auto-restart                    │
│  Level 2: Multiple agents in pipe   → Pipeline halt + alert           │
│  Level 3: Execution failure         → Position freeze                 │
│  Level 4: CASCADE DETECTION         → Emergency halt (defined below)  │
│  Level 5: SYSTEM-WIDE FAILURE       → Full shutdown (defined below)   │
│                                                                       │
│  ┌───────────────────────────────────────────────────────────────┐   │
│  │  Monitor Agent                                                │   │
│  │                                                               │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │   │
│  │  │ Agent Health │  │ Failure     │  │ Correlation         │  │   │
│  │  │ Tracker      │  │ Rate Calc   │  │ Engine              │  │   │
│  │  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │   │
│  │         └────────────────┼─────────────────────┘              │   │
│  │                          │                                     │   │
│  │                 ┌────────▼────────┐                            │   │
│  │                 │ Cascade         │                            │   │
│  │                 │ Decision Engine │                            │   │
│  │                 └────────┬────────┘                            │   │
│  │                          │                                     │   │
│  │            ┌─────────────┼─────────────┐                      │   │
│  │            │             │             │                      │   │
│  │     ┌──────▼──────┐ ┌───▼────┐ ┌──────▼──────┐              │   │
│  │     │ Level 4     │ │ Level  │ │ Level 5     │              │   │
│  │     │ Emergency   │ │ Alert  │ │ Full        │              │   │
│  │     │ Halt        │ │        │ │ Shutdown    │              │   │
│  │     └─────────────┘ └────────┘ └─────────────┘              │   │
│  └───────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
# cascade_detector.py

import time
import json
from collections import defaultdict, deque
from datetime import datetime, timezone
from enum import IntEnum

class CircuitBreakerLevel(IntEnum):
    NORMAL = 0
    LEVEL_1 = 1  # Single agent failure
    LEVEL_2 = 2  # Multiple agents in pipeline
    LEVEL_3 = 3  # Execution failure
    LEVEL_4 = 4  # Cascade failure (EMERGENCY HALT)
    LEVEL_5 = 5  # System-wide failure (FULL SHUTDOWN)


class CascadeDetector:
    """
    Detects cascade failures and triggers appropriate circuit breaker levels.
    
    Review H-5 finding: "The architecture defines Level 4/5 circuit breakers
    but doesn't specify how to detect a cascade failure."
    
    This class defines EXACT detection rules.
    """
    
    # ── Detection Windows ───────────────────────────────────────
    
    CASCADE_WINDOW_SEC = 60       # Rolling window for cascade detection
    SYSTEM_WINDOW_SEC = 300       # 5-minute window for system-wide detection
    
    # ── Level 4 Triggers (EMERGENCY HALT) ───────────────────────
    
    # Rule 4A: >50% of active agents report errors within 60 seconds
    L4_AGENT_ERROR_THRESHOLD = 0.50  # 50% of agents
    L4_WINDOW_SEC = 60
    
    # Rule 4B: Orchestrator itself fails (heartbeat lost)
    L4_ORCHESTRATOR_TIMEOUT_SEC = 10
    
    # Rule 4C: 3+ different agent types fail within 60 seconds
    L4_DIVERSE_FAILURE_COUNT = 3
    L4_DIVERSE_WINDOW_SEC = 60
    
    # Rule 4D: Redis connectivity lost for >10 seconds
    L4_REDIS_DOWN_SEC = 10
    
    # Rule 4E: Broker connectivity lost for >30 seconds
    L4_BROKER_DOWN_SEC = 30
    
    # ── Level 5 Triggers (FULL SHUTDOWN) ────────────────────────
    
    # Rule 5A: Level 4 conditions persist for >5 minutes
    L5_L4_PERSISTENCE_SEC = 300
    
    # Rule 5B: Redis connectivity lost for >30 seconds
    L5_REDIS_DOWN_SEC = 30
    
    # Rule 5C: Broker connectivity lost for >60 seconds
    L5_BROKER_DOWN_SEC = 60
    
    # Rule 5D: All agents of any single type are down
    L5_ALL_SAME_TYPE_DOWN = True
    
    # Rule 5E: 2+ independent infrastructure failures (Redis AND broker AND/or data source)
    L5_INFRA_FAILURE_COUNT = 2
    
    def __init__(self, redis_client, broker_client, kill_switch: 'KillSwitchManager'):
        self.redis = redis_client
        self.broker = broker_client
        self.kill_switch = kill_switch
        
        # Rolling failure tracking
        self.agent_failures = defaultdict(lambda: deque(maxlen=100))  # agent_id -> [(timestamp, error)]
        self.agent_heartbeats = {}  # agent_id -> last_heartbeat_timestamp
        self.infra_failures = deque(maxlen=50)  # [(timestamp, component, error)]
        
        # State tracking
        self.current_level = CircuitBreakerLevel.NORMAL
        self.level4_started_at = None
        self.last_check = time.time()
    
    def record_agent_failure(self, agent_id: str, agent_type: str, error: str):
        """Record an agent failure for cascade detection."""
        now = time.time()
        self.agent_failures[agent_id].append({
            'timestamp': now,
            'type': agent_type,
            'error': error,
        })
        
        # Store in Redis for cross-instance visibility
        self.redis.xadd("stream:agent_failures", {
            'agent_id': agent_id,
            'agent_type': agent_type,
            'error': error[:200],
            'timestamp': datetime.now(timezone.utc).isoformat(),
        })
        
        # Check cascade triggers immediately
        self._check_triggers()
    
    def record_agent_heartbeat(self, agent_id: str):
        """Record agent heartbeat."""
        self.agent_heartbeats[agent_id] = time.time()
        self.redis.set(f"agent:{agent_id}:heartbeat", str(time.time()), ex=30)
    
    def record_infra_failure(self, component: str, error: str):
        """Record an infrastructure failure (Redis, broker, data source)."""
        now = time.time()
        self.infra_failures.append({
            'timestamp': now,
            'component': component,
            'error': error,
        })
        
        self.redis.xadd("stream:infra_failures", {
            'component': component,
            'error': error[:200],
            'timestamp': datetime.now(timezone.utc).isoformat(),
        })
        
        self._check_triggers()
    
    def check_all(self) -> dict:
        """
        Full cascade detection check. Called periodically by Monitor Agent.
        Returns the current circuit breaker state and any actions taken.
        """
        self._check_triggers()
        
        return {
            'current_level': self.current_level.name,
            'level_value': self.current_level.value,
            'active_agents': self._count_active_agents(),
            'failed_agents': self._count_failed_agents(),
            'failure_rate': self._get_failure_rate(),
            'infra_status': self._get_infra_status(),
            'actions_taken': self._get_recent_actions(),
        }
    
    def _check_triggers(self):
        """Evaluate all cascade detection rules."""
        now = time.time()
        
        # ── Level 5 Checks (highest priority, checked first) ────
        
        # Rule 5B: Redis down >30 seconds
        if self._is_redis_down(L5_REDIS_DOWN_SEC):
            self._trigger_level5("Redis connectivity lost >30s")
            return
        
        # Rule 5C: Broker down >60 seconds
        if self._is_broker_down(L5_BROKER_DOWN_SEC):
            self._trigger_level5("Broker connectivity lost >60s")
            return
        
        # Rule 5A: Level 4 persisted >5 minutes
        if (self.current_level >= CircuitBreakerLevel.LEVEL_4 and
            self.level4_started_at and
            (now - self.level4_started_at) > self.L5_L4_PERSISTENCE_SEC):
            self._trigger_level5("Level 4 conditions persisted >5 minutes")
            return
        
        # Rule 5D: All agents of any type are down
        if self._is_all_same_type_down():
            self._trigger_level5("All agents of a type are down")
            return
        
        # Rule 5E: 2+ independent infra failures
        if self._count_recent_infra_failures(L4_WINDOW_SEC) >= L5_INFRA_FAILURE_COUNT:
            self._trigger_level5("Multiple independent infrastructure failures")
            return
        
        # ── Level 4 Checks ──────────────────────────────────────
        
        # Rule 4D: Redis down >10 seconds
        if self._is_redis_down(L4_REDIS_DOWN_SEC):
            self._trigger_level4("Redis connectivity lost >10s")
            return
        
        # Rule 4E: Broker down >30 seconds
        if self._is_broker_down(L4_BROKER_DOWN_SEC):
            self._trigger_level4("Broker connectivity lost >30s")
            return
        
        # Rule 4A: >50% of agents failing in 60-second window
        failure_rate = self._get_failure_rate(L4_WINDOW_SEC)
        if failure_rate > L4_AGENT_ERROR_THRESHOLD:
            self._trigger_level4(
                f"Agent failure rate {failure_rate:.0%} > {L4_AGENT_ERROR_THRESHOLD:.0%} "
                f"within {L4_WINDOW_SEC}s window"
            )
            return
        
        # Rule 4B: Orchestrator heartbeat lost
        if self._is_orchestrator_down():
            self._trigger_level4("Orchestrator heartbeat lost")
            return
        
        # Rule 4C: 3+ different agent types failing
        diverse_failures = self._count_diverse_failures(L4_DIVERSE_WINDOW_SEC)
        if diverse_failures >= L4_DIVERSE_FAILURE_COUNT:
            self._trigger_level4(
                f"{diverse_failures} different agent types failed within "
                f"{L4_DIVERSE_WINDOW_SEC}s"
            )
            return
        
        # ── If no triggers, degrade back to normal ──────────────
        if self.current_level >= CircuitBreakerLevel.LEVEL_4:
            # Only downgrade if conditions have cleared for >60 seconds
            if self._all_conditions_clear(duration=60):
                self._downgrade_level()
    
    # ── Trigger Actions ─────────────────────────────────────────
    
    def _trigger_level4(self, reason: str):
        """Level 4: Emergency halt — stop all trading immediately."""
        if self.current_level >= CircuitBreakerLevel.LEVEL_4:
            return  # Already at Level 4+
        
        self.current_level = CircuitBreakerLevel.LEVEL_4
        self.level4_started_at = time.time()
        
        # Activate kill switch
        self.kill_switch.activate(
            reason=f"LEVEL 4 CASCADE: {reason}",
            activated_by="cascade_detector",
        )
        
        # Alert
        self._send_alert(
            level="CRITICAL",
            title="LEVEL 4 CASCADE FAILURE DETECTED",
            message=f"Emergency halt triggered: {reason}",
            actions=["Kill switch activated", "All trading halted", "Manual review required"],
        )
        
        # Log
        self.redis.xadd("stream:system", {
            'event': 'circuit_breaker_level_4',
            'reason': reason,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        })
    
    def _trigger_level5(self, reason: str):
        """Level 5: Full shutdown — kill everything, protect capital."""
        if self.current_level >= CircuitBreakerLevel.LEVEL_5:
            return  # Already at Level 5
        
        self.current_level = CircuitBreakerLevel.LEVEL_5
        
        # Kill switch (should already be active from Level 4)
        self.kill_switch.activate(
            reason=f"LEVEL 5 SYSTEM FAILURE: {reason}",
            activated_by="cascade_detector",
        )
        
        # Close all positions at market (if broker is available)
        try:
            if not self._is_broker_down(5):
                self._close_all_positions()
        except Exception:
            pass  # If broker is down, rely on broker-side stops
        
        # Alert
        self._send_alert(
            level="EMERGENCY",
            title="LEVEL 5 SYSTEM-WIDE FAILURE",
            message=f"Full shutdown triggered: {reason}",
            actions=[
                "Kill switch activated",
                "All positions closed at market (if possible)",
                "All agents halted",
                "IMMEDIATE HUMAN INTERVENTION REQUIRED",
            ],
        )
        
        # Log
        self.redis.xadd("stream:system", {
            'event': 'circuit_breaker_level_5',
            'reason': reason,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        })
    
    # ── Detection Helpers ───────────────────────────────────────
    
    def _get_failure_rate(self, window_sec: int = CASCADE_WINDOW_SEC) -> float:
        """Calculate agent failure rate within the window."""
        now = time.time()
        cutoff = now - window_sec
        
        total_agents = self._count_active_agents()
        if total_agents == 0:
            return 0.0
        
        failed_agents = set()
        for agent_id, failures in self.agent_failures.items():
            for failure in failures:
                if failure['timestamp'] > cutoff:
                    failed_agents.add(agent_id)
                    break
        
        return len(failed_agents) / total_agents
    
    def _count_diverse_failures(self, window_sec: int) -> int:
        """Count distinct agent types that had failures in the window."""
        now = time.time()
        cutoff = now - window_sec
        
        types = set()
        for agent_id, failures in self.agent_failures.items():
            for failure in failures:
                if failure['timestamp'] > cutoff:
                    types.add(failure['type'])
                    break
        
        return len(types)
    
    def _is_redis_down(self, threshold_sec: float) -> bool:
        """Check if Redis has been unreachable for longer than threshold."""
        try:
            self.redis.ping()
            self.redis.set("_health_check", str(time.time()), ex=5)
            return False
        except redis.RedisError:
            # Check how long it's been down
            last_success = float(self.redis.get("_last_redis_success") or 0)
            return (time.time() - last_success) > threshold_sec
    
    def _is_broker_down(self, threshold_sec: float) -> bool:
        """Check if broker API has been unreachable for longer than threshold."""
        try:
            self.broker.ping()
            self.redis.set("_last_broker_success", str(time.time()), ex=60)
            return False
        except Exception:
            last_success = float(self.redis.get("_last_broker_success") or 0)
            return (time.time() - last_success) > threshold_sec
    
    def _is_orchestrator_down(self) -> bool:
        """Check if orchestrator heartbeat is stale."""
        heartbeat = self.redis.get("orchestrator:leader_heartbeat")
        if not heartbeat:
            return True
        
        try:
            hb = json.loads(heartbeat)
            ts = datetime.fromisoformat(hb['timestamp'])
            age = (datetime.now(timezone.utc) - ts).total_seconds()
            return age > L4_ORCHESTRATOR_TIMEOUT_SEC
        except (json.JSONDecodeError, KeyError):
            return True
    
    def _is_all_same_type_down(self) -> bool:
        """Check if all agents of any single type are down."""
        # Group agents by type
        agent_types = defaultdict(list)
        for agent_id in self._get_all_agent_ids():
            agent_type = self._get_agent_type(agent_id)
            agent_types[agent_type].append(agent_id)
        
        # Check if any type has all agents down
        for agent_type, agent_ids in agent_types.items():
            all_down = all(
                not self._is_agent_healthy(aid) for aid in agent_ids
            )
            if all_down and len(agent_ids) > 0:
                return True
        
        return False
    
    def _count_recent_infra_failures(self, window_sec: int) -> int:
        """Count distinct infrastructure components that failed in the window."""
        now = time.time()
        cutoff = now - window_sec
        components = set()
        for failure in self.infra_failures:
            if failure['timestamp'] > cutoff:
                components.add(failure['component'])
        return len(components)
    
    def _all_conditions_clear(self, duration: int = 60) -> bool:
        """Check if all Level 4+ conditions have been clear for `duration` seconds."""
        now = time.time()
        
        if self._get_failure_rate(duration) > 0.1:
            return False
        if self._is_redis_down(5):
            return False
        if self._is_broker_down(5):
            return False
        if self._is_orchestrator_down():
            return False
        
        return True
    
    def _downgrade_level(self):
        """Step down one level at a time."""
        if self.current_level > CircuitBreakerLevel.NORMAL:
            self.current_level = CircuitBreakerLevel(self.current_level - 1)
            if self.current_level < CircuitBreakerLevel.LEVEL_4:
                self.level4_started_at = None
            
            self.redis.xadd("stream:system", {
                'event': 'circuit_breaker_downgrade',
                'new_level': self.current_level.name,
                'timestamp': datetime.now(timezone.utc).isoformat(),
            })
    
    def _count_active_agents(self) -> int:
        now = time.time()
        return sum(
            1 for ts in self.agent_heartbeats.values()
            if (now - ts) < 30
        )
    
    def _count_failed_agents(self) -> int:
        now = time.time()
        return sum(
            1 for ts in self.agent_heartbeats.values()
            if (now - ts) >= 30
        )
    
    def _is_agent_healthy(self, agent_id: str) -> bool:
        ts = self.agent_heartbeats.get(agent_id, 0)
        return (time.time() - ts) < 30
    
    def _get_agent_type(self, agent_id: str) -> str:
        # Lookup from Redis agent registry
        agent_type = self.redis.hget(f"agent:{agent_id}:config", "type")
        return agent_type.decode() if agent_type else "unknown"
    
    def _get_all_agent_ids(self) -> list:
        keys = self.redis.keys("agent:*:config")
        return [k.decode().split(":")[1] for k in keys]
    
    def _get_infra_status(self) -> dict:
        return {
            'redis': 'up' if not self._is_redis_down(5) else 'down',
            'broker': 'up' if not self._is_broker_down(5) else 'down',
            'orchestrator': 'up' if not self._is_orchestrator_down() else 'down',
        }
    
    def _get_recent_actions(self) -> list:
        # Read from stream:system recent entries
        entries = self.redis.xrevrange("stream:system", count=10)
        return [
            {k.decode(): v.decode() for k, v in e[1].items()}
            for e in entries
            if any(kw in e[1].get(b'event', b'').decode()
                   for kw in ['circuit_breaker', 'kill_switch'])
        ]
    
    def _send_alert(self, level: str, title: str, message: str, actions: list):
        """Send alert to monitoring system + human notification."""
        alert = {
            'level': level,
            'title': title,
            'message': message,
            'actions': actions,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }
        self.redis.xadd("stream:alerts", alert)
        self.redis.publish("alert:critical", json.dumps(alert))
    
    def _close_all_positions(self):
        """Emergency: close all open positions at market."""
        positions = self.redis.keys("position:*:*")
        for key in positions:
            data = self.redis.hgetall(key)
            if data and data.get(b'status', b'') == b'open':
                symbol = key.decode().split(":")[-1]
                try:
                    self.broker.close_position_market(symbol)
                except Exception:
                    pass
```

### Cascade Detection Rule Summary Table

| Level | Rule ID | Trigger Condition | Action |
|-------|---------|-------------------|--------|
| **4** | 4A | >50% of active agents report errors within 60s | Emergency halt |
| **4** | 4B | Orchestrator heartbeat lost >10s | Emergency halt |
| **4** | 4C | 3+ different agent types fail within 60s | Emergency halt |
| **4** | 4D | Redis connectivity lost >10s | Emergency halt |
| **4** | 4E | Broker connectivity lost >30s | Emergency halt |
| **5** | 5A | Level 4 conditions persist >5 minutes | Full shutdown |
| **5** | 5B | Redis connectivity lost >30s | Full shutdown |
| **5** | 5C | Broker connectivity lost >60s | Full shutdown |
| **5** | 5D | All agents of any single type are down | Full shutdown |
| **5** | 5E | 2+ independent infra failures within 60s | Full shutdown |

---

## Fix #5: Parallel Instrument Pipelines (H-2)

### Problem

Sequential per-instrument processing creates a serialization bottleneck:

- 5 instruments × 5 seconds each = 25 seconds total
- Real-time trading requires <10 second end-to-end latency
- Adding instruments makes the system progressively slower

### Solution: Fan-Out Parallel Execution with Shared State

```
┌──────────────────────────────────────────────────────────────────┐
│              PARALLEL PIPELINE ARCHITECTURE                       │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Pipeline Scheduler (Code-only, no LLM)                   │   │
│  │  - Reads instrument list from config                      │   │
│  │  - Fans out to parallel pipeline executors                │   │
│  │  - Manages concurrency limits                             │   │
│  └────────────────────┬─────────────────────────────────────┘   │
│                       │ fan-out                                   │
│       ┌───────────────┼───────────────┐                          │
│       │               │               │                          │
│  ┌────▼────┐    ┌────▼────┐    ┌────▼────┐                     │
│  │ EUR/USD │    │ GBP/USD │    │ BTC/USD │    ... N instruments │
│  │ Pipeline│    │ Pipeline│    │ Pipeline│                      │
│  │ (async) │    │ (async) │    │ (async) │                      │
│  └────┬────┘    └────┬────┘    └────┬────┘                     │
│       │               │               │                          │
│       └───────────────┼───────────────┘                          │
│                       │ join                                      │
│  ┌────────────────────▼─────────────────────────────────────┐   │
│  │  Result Aggregator                                        │   │
│  │  - Collects all pipeline results                          │   │
│  │  - Feeds into Trade Decision (Stage 1 + Stage 2)         │   │
│  │  - Applies portfolio-level risk checks                    │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
# pipeline_scheduler.py

import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

class PipelinePhase(Enum):
    CONTEXT = 1        # Steps 1-4 (fundamental, bias, session, structure)
    SIGNALS = 2        # Steps 5-8 (S/R, liquidity, SMC, RSI)
    DECISION = 3       # Steps 9-10 (confluence + consensus)
    EXECUTION = 4      # Steps 11-12 (position sizing, SL/TP)
    MANAGEMENT = 5     # Steps 13-14 (trade management, trailing)
    LEARNING = 6       # Step 16 (reflection, weight update)


@dataclass
class PipelineConfig:
    """Configuration for a single instrument pipeline."""
    symbol: str
    phases_to_run: list  # Which phases to execute
    priority: int = 0     # Higher = runs first
    timeout_sec: float = 30.0
    max_agents: int = 7


@dataclass
class PipelineResult:
    """Result of a single instrument pipeline execution."""
    symbol: str
    success: bool
    phase_results: dict = field(default_factory=dict)
    confluence_score: Optional[float] = None
    consensus_score: Optional[float] = None
    direction: Optional[str] = None
    trade_candidate: bool = False
    error: Optional[str] = None
    duration_sec: float = 0.0


class PipelineScheduler:
    """
    Orchestrates parallel execution of instrument pipelines.
    
    Review H-2 finding: "With 5+ instruments, the Orchestrator becomes a
    serialization bottleneck. If each pipeline takes 5 seconds, analyzing
    5 instruments sequentially takes 25 seconds."
    
    Solution: Run all instrument pipelines concurrently using asyncio.
    Each pipeline is independent and doesn't share state with other pipelines.
    """
    
    def __init__(self, redis_factory, agent_pool, config: dict):
        self.redis_factory = redis_factory
        self.redis = redis_factory.get_master()
        self.agent_pool = agent_pool
        self.config = config
        
        # Concurrency controls
        self.max_concurrent_pipelines = config.get('max_concurrent_pipelines', 10)
        self.max_concurrent_agents = config.get('max_concurrent_agents', 20)
        
        # Semaphore for concurrency limiting
        self._pipeline_semaphore = asyncio.Semaphore(self.max_concurrent_pipelines)
        self._agent_semaphore = asyncio.Semaphore(self.max_concurrent_agents)
        
        # Shared phase cache (Phase 1-2 results valid until next H4 candle)
        self._phase_cache = {}
        self._cache_ttl = config.get('phase_cache_ttl_sec', 14400)  # 4 hours
    
    async def run_all(self, instruments: list[PipelineConfig]) -> list[PipelineResult]:
        """
        Run pipelines for all instruments in parallel.
        
        Args:
            instruments: List of PipelineConfig for each instrument
        
        Returns:
            List of PipelineResult, one per instrument
        """
        # Sort by priority (higher first)
        sorted_instruments = sorted(instruments, key=lambda x: x.priority, reverse=True)
        
        # Check kill switch before starting
        kill_switch = KillSwitchManager(self.redis)
        kill_switch.check_or_halt("pipeline_scheduler")
        
        # Fan out: create async tasks for all instruments
        tasks = [
            self._run_single_pipeline(config)
            for config in sorted_instruments
        ]
        
        # Execute all concurrently with semaphore limiting
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        pipeline_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                pipeline_results.append(PipelineResult(
                    symbol=sorted_instruments[i].symbol,
                    success=False,
                    error=str(result),
                ))
            else:
                pipeline_results.append(result)
        
        return pipeline_results
    
    async def _run_single_pipeline(self, config: PipelineConfig) -> PipelineResult:
        """
        Execute a single instrument pipeline.
        Uses semaphore to limit concurrent pipeline execution.
        """
        start_time = time.time()
        
        async with self._pipeline_semaphore:
            try:
                # Check kill switch
                kill_switch = KillSwitchManager(self.redis)
                kill_switch.check_or_halt(f"pipeline:{config.symbol}")
                
                result = PipelineResult(symbol=config.symbol, success=True)
                
                # Phase 1: Context (Steps 1-4)
                if PipelinePhase.CONTEXT in config.phases_to_run:
                    cached = self._get_cached_phase(config.symbol, PipelinePhase.CONTEXT)
                    if cached:
                        result.phase_results['context'] = cached
                    else:
                        context_result = await self._run_phase(
                            config.symbol, PipelinePhase.CONTEXT, config.timeout_sec
                        )
                        result.phase_results['context'] = context_result
                        self._cache_phase(config.symbol, PipelinePhase.CONTEXT, context_result)
                    
                    # Check for fundamental veto
                    if context_result.get('fundamental_veto'):
                        result.success = True
                        result.trade_candidate = False
                        result.error = "Fundamental veto"
                        result.duration_sec = time.time() - start_time
                        return result
                
                # Phase 2: Signals (Steps 5-8) — can run in parallel with Phase 1
                if PipelinePhase.SIGNALS in config.phases_to_run:
                    cached = self._get_cached_phase(config.symbol, PipelinePhase.SIGNALS)
                    if cached:
                        result.phase_results['signals'] = cached
                    else:
                        signals_result = await self._run_phase(
                            config.symbol, PipelinePhase.SIGNALS, config.timeout_sec
                        )
                        result.phase_results['signals'] = signals_result
                        self._cache_phase(config.symbol, PipelinePhase.SIGNALS, signals_result)
                
                # Phase 1+2 optimization: run in parallel
                if (PipelinePhase.CONTEXT in config.phases_to_run and 
                    PipelinePhase.SIGNALS in config.phases_to_run):
                    # Already handled above — signals run after context
                    # But if both are cached, this is instant
                    pass
                
                # Phase 3: Decision (Steps 9-10) — needs Phase 1+2 results
                if PipelinePhase.DECISION in config.phases_to_run:
                    decision_result = await self._run_phase(
                        config.symbol, PipelinePhase.DECISION, config.timeout_sec,
                        dependencies={
                            'context': result.phase_results.get('context'),
                            'signals': result.phase_results.get('signals'),
                        }
                    )
                    result.phase_results['decision'] = decision_result
                    result.confluence_score = decision_result.get('confluence_score')
                    result.consensus_score = decision_result.get('consensus_score')
                    result.direction = decision_result.get('direction')
                    result.trade_candidate = decision_result.get('trade_candidate', False)
                
                result.duration_sec = time.time() - start_time
                return result
                
            except KillSwitchActive:
                return PipelineResult(
                    symbol=config.symbol,
                    success=False,
                    error="Kill switch active",
                    duration_sec=time.time() - start_time,
                )
            except asyncio.TimeoutError:
                return PipelineResult(
                    symbol=config.symbol,
                    success=False,
                    error=f"Pipeline timeout ({config.timeout_sec}s)",
                    duration_sec=time.time() - start_time,
                )
            except Exception as e:
                return PipelineResult(
                    symbol=config.symbol,
                    success=False,
                    error=str(e),
                    duration_sec=time.time() - start_time,
                )
    
    async def _run_phase(self, symbol: str, phase: PipelinePhase, 
                         timeout: float, dependencies: dict = None) -> dict:
        """
        Run a single pipeline phase for an instrument.
        Uses agent semaphore to limit concurrent agent invocations.
        """
        async with self._agent_semaphore:
            # Create pipeline state checkpoint
            pipeline_id = f"{symbol}:{phase.name}:{int(time.time())}"
            state = PipelineState(self.redis, pipeline_id, symbol)
            
            try:
                # Run with timeout
                result = await asyncio.wait_for(
                    self._execute_phase(symbol, phase, dependencies),
                    timeout=timeout,
                )
                
                # Save checkpoint
                state.save_checkpoint(phase.value, result)
                
                return result
                
            except asyncio.TimeoutError:
                state.mark_failed(f"Phase {phase.name} timeout")
                raise
            except Exception as e:
                state.mark_failed(str(e))
                raise
    
    async def _execute_phase(self, symbol: str, phase: PipelinePhase,
                             dependencies: dict = None) -> dict:
        """
        Execute the actual phase logic.
        Dispatches to the appropriate agents.
        """
        if phase == PipelinePhase.CONTEXT:
            # Steps 1-4: Run in parallel
            tasks = [
                self.agent_pool.invoke('fundamental', symbol),
                self.agent_pool.invoke('bias', symbol),
                self.agent_pool.invoke('session', symbol),
                self.agent_pool.invoke('structure', symbol),
            ]
            results = await asyncio.gather(*tasks)
            return {
                'fundamental': results[0],
                'bias': results[1],
                'session': results[2],
                'structure': results[3],
                'fundamental_veto': results[0].get('veto', False),
            }
        
        elif phase == PipelinePhase.SIGNALS:
            # Steps 5-8: Run in parallel
            tasks = [
                self.agent_pool.invoke('sr_levels', symbol),
                self.agent_pool.invoke('liquidity', symbol),
                self.agent_pool.invoke('smc', symbol),
                self.agent_pool.invoke('rsi', symbol),
            ]
            results = await asyncio.gather(*tasks)
            return {
                'sr_levels': results[0],
                'liquidity': results[1],
                'smc': results[2],
                'rsi': results[3],
            }
        
        elif phase == PipelinePhase.DECISION:
            # Steps 9-10: Confluence + Consensus (unified — see Fix #1)
            context = dependencies.get('context', {})
            signals = dependencies.get('signals', {})
            
            # Merge all signals for the unified pipeline
            all_signals = {}
            all_signals.update(context)
            all_signals.update(signals)
            
            pipeline = TradeDecisionPipeline()
            decision = pipeline.evaluate(all_signals)
            
            return {
                'confluence_score': decision.get('confluence_score'),
                'consensus_score': decision.get('consensus_strength'),
                'direction': decision.get('direction'),
                'trade_candidate': decision.get('decision') == 'TRADE_CANDIDATE',
                'details': decision,
            }
        
        elif phase == PipelinePhase.EXECUTION:
            # Steps 11-12: Position sizing + SL/TP
            if not dependencies.get('decision', {}).get('trade_candidate'):
                return {'skipped': True, 'reason': 'Not a trade candidate'}
            
            tasks = [
                self.agent_pool.invoke('position_sizer', symbol, dependencies),
                self.agent_pool.invoke('sl_tp_calculator', symbol, dependencies),
            ]
            results = await asyncio.gather(*tasks)
            return {
                'position_size': results[0],
                'sl_tp': results[1],
            }
        
        elif phase == PipelinePhase.MANAGEMENT:
            # Steps 13-14: Trade management
            return await self.agent_pool.invoke('trade_manager', symbol, dependencies)
        
        elif phase == PipelinePhase.LEARNING:
            # Step 16: Reflection
            return await self.agent_pool.invoke('reflection', symbol, dependencies)
        
        return {}
    
    # ── Phase Caching (H4 candle validity) ──────────────────────
    
    def _get_cached_phase(self, symbol: str, phase: PipelinePhase) -> Optional[dict]:
        """Get cached phase result if still valid."""
        cache_key = f"{symbol}:{phase.name}"
        cached = self._phase_cache.get(cache_key)
        
        if cached and (time.time() - cached['timestamp']) < self._cache_ttl:
            return cached['result']
        
        # Also check Redis for cross-instance cache
        redis_cached = self.redis.get(f"cache:phase:{cache_key}")
        if redis_cached:
            import json
            data = json.loads(redis_cached)
            if (time.time() - data['timestamp']) < self._cache_ttl:
                return data['result']
        
        return None
    
    def _cache_phase(self, symbol: str, phase: PipelinePhase, result: dict):
        """Cache phase result in memory + Redis."""
        cache_key = f"{symbol}:{phase.name}"
        entry = {'result': result, 'timestamp': time.time()}
        
        # In-process cache
        self._phase_cache[cache_key] = entry
        
        # Redis cache (cross-instance)
        import json
        self.redis.setex(
            f"cache:phase:{cache_key}",
            self._cache_ttl,
            json.dumps(entry),
        )


class AgentPool:
    """
    Pool of agent workers for parallel execution.
    Manages agent lifecycle, health, and load balancing.
    """
    
    def __init__(self, redis_factory, config: dict):
        self.redis_factory = redis_factory
        self.redis = redis_factory.get_master()
        self.config = config
        
        # Agent worker pool
        self._workers: dict[str, asyncio.Queue] = {}  # agent_type -> queue
        self._health: dict[str, float] = {}  # agent_id -> last_healthy_at
    
    async def invoke(self, agent_type: str, symbol: str, 
                     context: dict = None) -> dict:
        """
        Invoke an agent of the given type for the given symbol.
        Uses connection pooling and load balancing.
        """
        # Get available worker for this agent type
        worker_id = await self._get_available_worker(agent_type)
        
        # Build invocation message
        message = {
            'agent_id': worker_id,
            'agent_type': agent_type,
            'symbol': symbol,
            'context': context or {},
            'timestamp': time.time(),
        }
        
        # Send via Redis Stream (durable)
        stream_key = f"stream:agent:{agent_type}"
        msg_id = self.redis.xadd(stream_key, {
            'payload': json.dumps(message),
            'symbol': symbol,
            'priority': 'normal',
        })
        
        # Wait for response (with timeout)
        response = await self._wait_for_response(worker_id, msg_id, timeout=30)
        
        return response
    
    async def _get_available_worker(self, agent_type: str) -> str:
        """Get an available worker for the given agent type."""
        # Check health of all workers of this type
        workers = self.redis.smembers(f"agents:{agent_type}:pool")
        
        healthy_workers = []
        for worker_id in workers:
            wid = worker_id.decode()
            last_healthy = self._health.get(wid, 0)
            if (time.time() - last_healthy) < 30:
                healthy_workers.append(wid)
        
        if not healthy_workers:
            # Spawn new worker
            healthy_workers = [await self._spawn_worker(agent_type)]
        
        # Simple round-robin (can be replaced with least-connections)
        return healthy_workers[0]
    
    async def _wait_for_response(self, worker_id: str, msg_id: str,
                                  timeout: float) -> dict:
        """Wait for agent response on the response stream."""
        response_stream = f"stream:response:{worker_id}"
        
        start = time.time()
        while (time.time() - start) < timeout:
            # Read from response stream
            entries = self.redis.xread(
                {response_stream: '$'},
                count=1,
                block=1000,  # Block for 1 second
            )
            
            if entries:
                for stream_name, messages in entries:
                    for msg_id, data in messages:
                        payload = json.loads(data.get(b'payload', b'{}'))
                        if payload.get('request_msg_id') == msg_id:
                            return payload
            
            # Check kill switch
            kill_switch = KillSwitchManager(self.redis)
            if kill_switch.is_active():
                raise KillSwitchActive("Kill switch active during agent wait")
        
        raise asyncio.TimeoutError(f"Agent {worker_id} response timeout")
    
    async def _spawn_worker(self, agent_type: str) -> str:
        """Spawn a new agent worker."""
        import uuid
        worker_id = f"{agent_type}:{uuid.uuid4().hex[:8]}"
        
        # Register in pool
        self.redis.sadd(f"agents:{agent_type}:pool", worker_id)
        
        # Set initial health
        self._health[worker_id] = time.time()
        
        return worker_id
```

### Orchestrator Integration

```python
# orchestrator_main.py (updated)

class Orchestrator:
    """
    Updated orchestrator with parallel pipeline scheduling.
    """
    
    def __init__(self, redis_factory, config):
        self.redis_factory = redis_factory
        self.redis = redis_factory.get_master()
        self.config = config
        
        self.leader = LeaderElection(self.redis, config['instance_id'])
        self.scheduler = PipelineScheduler(
            redis_factory, 
            AgentPool(redis_factory, config),
            config,
        )
        self.cascade_detector = CascadeDetector(
            self.redis, 
            broker_client=None,  # Injected
            kill_switch=KillSwitchManager(self.redis),
        )
    
    def start(self):
        self.leader.start(
            on_become_active=self._run_active,
            on_become_standby=self._run_standby,
        )
    
    async def _run_active(self):
        """Main loop when this instance is the active orchestrator."""
        instruments = self._load_instruments()
        
        while self.leader.role == OrchestratorRole.ACTIVE:
            # Check cascade detector
            status = self.cascade_detector.check_all()
            if status['level_value'] >= 4:
                # Level 4+ — emergency halt, don't run pipelines
                await asyncio.sleep(5)
                continue
            
            # Run all instrument pipelines in parallel
            results = await self.scheduler.run_all(instruments)
            
            # Process results (trade candidates go to execution)
            for result in results:
                if result.trade_candidate:
                    await self._submit_to_execution(result)
            
            # Wait for next trigger (candle close, timer, etc.)
            await self._wait_for_next_trigger()
    
    def _load_instruments(self) -> list:
        """Load instrument list from config."""
        symbols = self.config.get('instruments', ['EUR/USD', 'GBP/USD'])
        return [
            PipelineConfig(
                symbol=s,
                phases_to_run=list(PipelinePhase),
                priority=1,
                timeout_sec=30,
            )
            for s in symbols
        ]
```

### Performance Comparison

| Scenario | Sequential (Before) | Parallel (After) | Improvement |
|----------|--------------------|--------------------|-------------|
| 2 instruments | 10s | 5s | **2x faster** |
| 5 instruments | 25s | 5s | **5x faster** |
| 10 instruments | 50s | 7s* | **7x faster** |
| 20 instruments | 100s | 12s* | **8x faster** |

*With max_concurrent_pipelines=10 and phase caching active

### Phase Caching Benefit

For H4 timeframe analysis, Phase 1-2 results are valid until the next H4 candle close. With caching:

| Instrument | First Run | Subsequent Runs (same H4 candle) |
|------------|-----------|----------------------------------|
| EUR/USD | 5s (full) | <0.5s (cached) |
| GBP/USD | 5s (full) | <0.5s (cached) |
| All 5 | 5s (parallel) | <1s (all cached) |

---

## Implementation Order & Dependencies

```
┌─────────────────────────────────────────────────────────────────────┐
│                    IMPLEMENTATION SEQUENCE                            │
│                                                                      │
│  Week 1: Fix #1 (Scoring Unification)                                │
│  ┌─────────────────────────────────────────────┐                    │
│  │ 1. Implement ConfluenceEngine                │                    │
│  │ 2. Implement ConsensusEngine                 │                    │
│  │ 3. Implement TradeDecisionPipeline           │                    │
│  │ 4. Unit tests for both stages                │                    │
│  │ 5. Update pipeline flow to use unified gates │                    │
│  └─────────────────────────────────────────────┘                    │
│           │                                                          │
│           ▼                                                          │
│  Week 2: Fix #2 (Redis HA)                                           │
│  ┌─────────────────────────────────────────────┐                    │
│  │ 1. Deploy Redis Sentinel (3 sentinels)       │                    │
│  │ 2. Deploy Redis replica                      │                    │
│  │ 3. Implement RedisFactory (Sentinel-aware)   │                    │
│  │ 4. Implement PositionStateManager             │                    │
│  │ 5. Implement enhanced KillSwitchManager      │                    │
│  │ 6. PostgreSQL position backup table          │                    │
│  │ 7. Reconciliation process                    │                    │
│  │ 8. Failover testing                          │                    │
│  └─────────────────────────────────────────────┘                    │
│           │                                                          │
│           ▼                                                          │
│  Week 3: Fix #3 (Orchestrator Redundancy)                            │
│  ┌─────────────────────────────────────────────┐                    │
│  │ 1. Implement LeaderElection                  │                    │
│  │ 2. Implement PipelineState (Redis-backed)    │                    │
│  │ 3. Implement OrchestratorInstance             │                    │
│  │ 4. Run two instances + test failover         │                    │
│  │ 5. Verify state restoration on failover      │                    │
│  └─────────────────────────────────────────────┘                    │
│           │                                                          │
│           ▼                                                          │
│  Week 3-4: Fix #4 (Cascade Detection)                                │
│  ┌─────────────────────────────────────────────┐                    │
│  │ 1. Implement CascadeDetector                 │                    │
│  │ 2. Define all trigger rules (4A-4E, 5A-5E)   │                    │
│  │ 3. Integrate with Monitor Agent              │                    │
│  │ 4. Test with simulated failures              │                    │
│  │ 5. Validate kill switch integration          │                    │
│  └─────────────────────────────────────────────┘                    │
│           │                                                          │
│           ▼                                                          │
│  Week 4: Fix #5 (Parallel Pipelines)                                 │
│  ┌─────────────────────────────────────────────┐                    │
│  │ 1. Implement PipelineScheduler               │                    │
│  │ 2. Implement AgentPool                       │                    │
│  │ 3. Implement phase caching                   │                    │
│  │ 4. Update Orchestrator main loop             │                    │
│  │ 5. Load testing (5, 10, 20 instruments)      │                    │
│  │ 6. Validate latency targets                  │                    │
│  └─────────────────────────────────────────────┘                    │
│                                                                      │
│  Week 5: Integration Testing                                         │
│  ┌─────────────────────────────────────────────┐                    │
│  │ 1. End-to-end pipeline test (all 5 fixes)    │                    │
│  │ 2. Failure injection testing                 │                    │
│  │ 3. Performance benchmarking                  │                    │
│  │ 4. Documentation updates                     │                    │
│  └─────────────────────────────────────────────┘                    │
└─────────────────────────────────────────────────────────────────────┘
```

### Dependency Graph

```
Fix #1 (Scoring) ──────────────┐
                               │
Fix #2 (Redis HA) ─────────────┼──► Fix #3 (Orchestrator Redundancy)
                               │         │
                               │         ▼
                               ├──► Fix #4 (Cascade Detection)
                               │
                               └──► Fix #5 (Parallel Pipelines)
```

**Key dependencies:**
- Fix #3 depends on Fix #2 (leader election needs Redis HA)
- Fix #4 depends on Fix #2 (cascade detector needs Redis + position state)
- Fix #5 depends on Fix #1 (parallel pipelines use unified scoring)
- Fix #1 is independent — can be implemented first

---

## Appendix: Files to Create/Modify

| File | Action | Fix |
|------|--------|-----|
| `confluence_engine.py` | CREATE | #1 |
| `consensus_engine.py` | CREATE | #1 |
| `pipeline_decision.py` | CREATE | #1 |
| `weight_adjuster.py` | CREATE | #1 |
| `docker-compose.redis-ha.yml` | CREATE | #2 |
| `sentinel.conf` (×3) | CREATE | #2 |
| `redis_factory.py` | CREATE | #2 |
| `position_state_manager.py` | CREATE | #2 |
| `kill_switch.py` | MODIFY | #2 |
| `position_state.sql` | CREATE | #2 |
| `orchestrator_leader.py` | CREATE | #3 |
| `pipeline_state.py` | CREATE | #3 |
| `cascade_detector.py` | CREATE | #4 |
| `pipeline_scheduler.py` | CREATE | #5 |
| `agent_pool.py` | CREATE | #5 |
| `orchestrator_main.py` | MODIFY | #3, #5 |

---

*Document generated: 2026-07-11*
*Author: Orchestration Fix Agent*
*Source: review_agent_orchestration.md Top 5 Actions*
