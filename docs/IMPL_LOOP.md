# IMPL_LOOP — Continuous Trading Loop Engine

## Summary

Implemented the **Loop Engineering pattern** for AlphaStack: a background asyncio trading loop that continuously cycles through memory, market analysis, pipeline execution, debate, reflection, trade execution, logging, and learning.

## Files Created

### `src/alphastack/engine/__init__.py`
Package init that exports `TradingLoop`, `LoopConfig`, `LoopState`.

### `src/alphastack/engine/loop.py` (~300 lines)
Core loop implementation with three classes:

#### `LoopConfig`
| Field | Type | Default | Description |
|---|---|---|---|
| `interval` | `Interval` | `4h` | Cycle frequency: `1h`, `4h`, `1d` |
| `symbols` | `list[str]` | BTC, ETH, SOL | Pairs to monitor |
| `max_concurrent_trades` | `int` | 3 | Max open positions |
| `cooldown_after_loss` | `int` | 1 | Skip N cycles after loss |
| `evolution_enabled` | `bool` | True | Auto-adjust weights |

#### `LoopState`
Tracks per-session mutable state:
- `cycle_count`, `last_trade_time`, `current_drawdown`, `win_streak`
- `cooldown_remaining`, `running`, `stopping`
- `total_pnl`, `trades_placed`

#### `TradingLoop`
Main loop class with lifecycle methods:
- `start()` — spawn background asyncio task
- `stop()` — graceful shutdown (finishes current cycle)
- `status()` — return config + state + memory stats
- `update_config()` — hot-update config (takes effect next cycle)

## Cycle Flow

Each cycle executes these steps in order:

```
1. READ MEMORY     → Load recent trades, lessons, patterns from EpisodicMemory
2. ANALYZE MARKET  → Fetch live Binance data per symbol
3. RUN PIPELINE    → Execute 16-step strategy pipeline → produce signal
4. DEBATE          → Bull vs Bear debate via DebateEngine; reject/modify/approve
5. REFLECT         → Pre-trade check: recent loss history, drawdown limits
6. EXECUTE         → Place trade via TradeStore if all checks pass
7. LOG             → Store TradeEpisode in EpisodicMemory
8. LEARN           → Update win_streak, drawdown, cooldown; run PostTradeReflection
9. WAIT            → Sleep until next cycle
```

## API Endpoints (added to `live_server.py`)

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/loop/start` | Start the background loop |
| `POST` | `/api/v1/loop/stop` | Graceful stop (finishes current cycle) |
| `GET` | `/api/v1/loop/status` | Current status, config, state, memory stats |
| `PATCH` | `/api/v1/loop/config` | Hot-update config (interval, symbols, etc.) |

## Integration

- **Singleton**: `trading_loop` created during `lifespan()` startup
- **Graceful shutdown**: Loop stopped before event bus closes on app shutdown
- **Non-blocking**: Runs as `asyncio.create_task` — doesn't block API
- **Wired to existing singletons**: Uses same `trade_store`, `episodic_memory`, `event_bus`, `_build_market_data`, `_run_pipeline_signal`

## Safety Features

- **Cooldown after loss**: Configurable delay between cycles after a losing trade
- **Drawdown guard**: Blocks trades if drawdown > 15%
- **Recent loss check**: Blocks if 2+ recent losses on same symbol
- **Max concurrent positions**: Respects `max_concurrent_trades` limit
- **Minimal position size**: Uses 0.001 quantity for safety
- **Graceful shutdown**: Current cycle completes before stopping

## Key Design Decisions

1. **Background asyncio task** — no threads, no processes, pure async
2. **Hot-config updates** — PATCH endpoint changes take effect next cycle, no restart needed
3. **Memory-driven** — reads lessons/patterns before each cycle, writes episodes after
4. **Debate integration** — every signal passes through bull/bear debate before execution
5. **Reflection integration** — pre-trade reflection blocks risky trades; post-trade reflection generates corrections
6. **Simple** — ~280 lines of loop code, no over-engineering
