"""Continuous Trading Loop — Loop Engineering Pattern for AlphaStack.

Implements: Memory → Engine → Agents → Results → Memory → Repeat

Each cycle:
    1. READ MEMORY   — load recent trades, patterns, corrections
    2. ANALYZE MARKET — fetch live data from Binance
    3. RUN PIPELINE   — execute 16-step strategy pipeline
    4. DEBATE         — bull vs bear debate on signal
    5. REFLECT        — pre-trade reflection check
    6. EXECUTE        — place trade if all checks pass
    7. LOG            — store result in memory
    8. LEARN          — update weights based on outcome
    9. WAIT           — sleep until next cycle
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Coroutine, Optional

from alphastack.agi.memory import EpisodicMemory, TradeEpisode
from alphastack.agents.debate.debate_engine import DebateEngine
from alphastack.agents.debate.risk_arbiter import DebateVerdict
from alphastack.agents.reflection.post_trade import (
    CorrectionEngine,
    PostTradeReflection,
    SkillCreator,
)
from alphastack.utils.logger import get_logger

logger = get_logger("alphastack.engine")


# ═══════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════


class Interval(str, Enum):
    """Supported loop intervals."""
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"


_INTERVAL_SECONDS: dict[Interval, int] = {
    Interval.H1: 3600,
    Interval.H4: 14400,
    Interval.D1: 86400,
}


@dataclass
class LoopConfig:
    """Configuration for the trading loop.

    Attributes
    ----------
    interval : Interval
        How often to run a cycle.
    symbols : list[str]
        Trading pairs to monitor.
    max_concurrent_trades : int
        Maximum open positions allowed.
    cooldown_after_loss : int
        Skip N cycles after a losing trade.
    evolution_enabled : bool
        Whether to auto-adjust weights from outcomes.
    """

    interval: Interval = Interval.H4
    symbols: list[str] = field(default_factory=lambda: [
        "BTC/USDT", "ETH/USDT", "SOL/USDT",
    ])
    max_concurrent_trades: int = 3
    cooldown_after_loss: int = 1
    evolution_enabled: bool = True

    @property
    def interval_seconds(self) -> int:
        return _INTERVAL_SECONDS[self.interval]

    def to_dict(self) -> dict[str, Any]:
        return {
            "interval": self.interval.value,
            "symbols": self.symbols,
            "max_concurrent_trades": self.max_concurrent_trades,
            "cooldown_after_loss": self.cooldown_after_loss,
            "evolution_enabled": self.evolution_enabled,
            "interval_seconds": self.interval_seconds,
        }


# ═══════════════════════════════════════════════════════════
# State
# ═══════════════════════════════════════════════════════════


@dataclass
class LoopState:
    """Mutable state tracked across loop cycles.

    Attributes
    ----------
    cycle_count : int
        How many cycles have completed.
    last_trade_time : float
        Unix timestamp of the last trade placed.
    current_drawdown : float
        Running drawdown from peak equity.
    win_streak : int
        Current streak (positive = wins, negative = losses).
    cooldown_remaining : int
        Cycles left to wait after a loss.
    running : bool
        Whether the loop is active.
    stopping : bool
        Graceful shutdown requested.
    last_cycle_at : float
        When the last cycle started.
    total_pnl : float
        Cumulative P&L across all cycles.
    trades_placed : int
        Total trades placed by the loop.
    """

    cycle_count: int = 0
    last_trade_time: float = 0.0
    current_drawdown: float = 0.0
    peak_pnl: float = 0.0  # Track peak P&L for drawdown calculation
    win_streak: int = 0
    cooldown_remaining: int = 0
    running: bool = False
    stopping: bool = False
    last_cycle_at: float = 0.0
    total_pnl: float = 0.0
    trades_placed: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_count": self.cycle_count,
            "last_trade_time": self.last_trade_time,
            "current_drawdown": round(self.current_drawdown, 4),
            "peak_pnl": round(self.peak_pnl, 4),
            "win_streak": self.win_streak,
            "cooldown_remaining": self.cooldown_remaining,
            "running": self.running,
            "stopping": self.stopping,
            "last_cycle_at": self.last_cycle_at,
            "total_pnl": round(self.total_pnl, 4),
            "trades_placed": self.trades_placed,
        }


# ═══════════════════════════════════════════════════════════
# Trading Loop
# ═══════════════════════════════════════════════════════════


class TradingLoop:
    """Background continuous trading loop.

    Parameters
    ----------
    config : LoopConfig
        Loop configuration.
    build_market_data : Callable[[str], Coroutine]
        Async function that fetches market data for a symbol.
    run_pipeline : Callable[[str], Coroutine]
        Async function that runs the 16-step pipeline and returns a signal dict.
    run_orchestrator : Callable[[str], Coroutine]
        Async function that runs the full multi-agent orchestrator.
    trade_store : Any
        TradeStore instance for placing/closing trades.
    episodic_memory : EpisodicMemory
        AGI episodic memory for storing/retrieving trade episodes.
    event_bus : Any | None
        Optional event bus for publishing loop events.
    """

    def __init__(
        self,
        config: LoopConfig,
        build_market_data: Callable[[str], Coroutine[Any, Any, dict[str, Any]]],
        run_pipeline: Callable[[str], Coroutine[Any, Any, dict[str, Any]]],
        run_orchestrator: Callable[[str], Coroutine[Any, Any, dict[str, Any]]],
        trade_store: Any,
        episodic_memory: EpisodicMemory,
        event_bus: Any | None = None,
    ) -> None:
        self.config = config
        self.state = LoopState()
        self._build_market_data = build_market_data
        self._run_pipeline = run_pipeline
        self._run_orchestrator = run_orchestrator
        self._trade_store = trade_store
        self._memory = episodic_memory
        self._event_bus = event_bus

        # Post-trade learning components
        self._post_reflection = PostTradeReflection()
        self._correction_engine = CorrectionEngine()
        self._skill_creator = SkillCreator()
        self._debate_engine = DebateEngine()

        self._task: asyncio.Task | None = None

    # ── Lifecycle ────────────────────────────────────────────

    async def start(self) -> dict[str, Any]:
        """Start the background loop. Returns immediately."""
        if self.state.running:
            return {"status": "already_running", "state": self.state.to_dict()}

        self.state.running = True
        self.state.stopping = False
        self._task = asyncio.create_task(self._run_forever())
        logger.info("loop.started", interval=self.config.interval.value,
                     symbols=self.config.symbols)
        return {"status": "started", "config": self.config.to_dict()}

    async def stop(self) -> dict[str, Any]:
        """Request graceful shutdown. Current cycle finishes first."""
        if not self.state.running:
            return {"status": "not_running"}

        self.state.stopping = True
        logger.info("loop.stopping", cycle=self.state.cycle_count)
        # Wait for the task to finish its current cycle
        if self._task and not self._task.done():
            try:
                await asyncio.wait_for(self._task, timeout=300)
            except asyncio.TimeoutError:
                self._task.cancel()
        self.state.running = False
        self.state.stopping = False
        logger.info("loop.stopped", cycles=self.state.cycle_count)
        return {"status": "stopped", "state": self.state.to_dict()}

    def status(self) -> dict[str, Any]:
        """Return current loop status."""
        return {
            "running": self.state.running,
            "stopping": self.state.stopping,
            "config": self.config.to_dict(),
            "state": self.state.to_dict(),
            "memory_stats": self._memory.stats(),
        }

    async def update_config(self, **kwargs: Any) -> dict[str, Any]:
        """Hot-update config. Takes effect next cycle."""
        for key, value in kwargs.items():
            if key == "interval" and isinstance(value, str):
                self.config.interval = Interval(value)
            elif hasattr(self.config, key):
                setattr(self.config, key, value)
        logger.info("loop.config_updated", config=self.config.to_dict())
        return {"status": "updated", "config": self.config.to_dict()}

    # ── Main Loop ────────────────────────────────────────────

    async def _run_forever(self) -> None:
        """Background loop that runs until stopped."""
        while self.state.running and not self.state.stopping:
            try:
                await self._run_cycle()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.warning("loop.cycle_error", exc_info=True)

            # Wait for next cycle
            if self.state.running and not self.state.stopping:
                await asyncio.sleep(self.config.interval_seconds)

        self.state.running = False

    async def _run_cycle(self) -> None:
        """Execute one full loop cycle.

        Steps: Memory → Market → Pipeline → Debate → Reflect →
               Execute → Log → Learn → Wait
        """
        cycle_id = uuid.uuid4().hex[:8]
        self.state.cycle_count += 1
        self.state.last_cycle_at = time.time()
        cycle_start = time.time()

        logger.info("loop.cycle_start", cycle=self.state.cycle_count,
                     cycle_id=cycle_id)

        # ── Cooldown check ───────────────────────────────────
        if self.state.cooldown_remaining > 0:
            self.state.cooldown_remaining -= 1
            logger.info("loop.cooldown", remaining=self.state.cooldown_remaining)
            return

        # ── 1. READ MEMORY ───────────────────────────────────
        memory_context = self._read_memory()

        # ── 2–6. Per-symbol: Analyze → Pipeline → Debate → Reflect → Execute ──
        signals = []
        for symbol in self.config.symbols:
            try:
                # 2. ANALYZE MARKET
                market_data = await self._build_market_data(symbol)

                # 3. RUN PIPELINE
                signal = await self._run_pipeline(symbol)
                if not signal:
                    continue

                # 4. DEBATE
                debate_ok = self._debate_signal(signal, market_data, memory_context)
                if not debate_ok:
                    continue

                # 5. REFLECT (pre-trade check)
                reflect_ok = self._pre_trade_reflect(signal, memory_context)
                if not reflect_ok:
                    continue

                signals.append(signal)
            except Exception:
                logger.warning("loop.symbol_error", symbol=symbol, exc_info=True)

        # ── 6. EXECUTE ───────────────────────────────────────
        trades = []
        open_count = len(self._trade_store.list_trades(status_filter="open"))
        for signal in signals:
            if open_count >= self.config.max_concurrent_trades:
                break
            trade = self._execute_trade(signal)
            if trade:
                trades.append(trade)
                open_count += 1

        # ── 7. LOG to memory ─────────────────────────────────
        for trade in trades:
            self._log_to_memory(trade, cycle_id)

        # ── 8. LEARN ─────────────────────────────────────────
        if self.config.evolution_enabled:
            self._learn_from_outcomes(trades, cycle_id)

        elapsed = round(time.time() - cycle_start, 2)
        logger.info("loop.cycle_complete", cycle=self.state.cycle_count,
                     signals=len(signals), trades=len(trades), elapsed_s=elapsed)

    # ── Step implementations ─────────────────────────────────

    def _read_memory(self) -> dict[str, Any]:
        """Load recent episodes, lessons, and patterns from memory."""
        stats = self._memory.stats()
        lessons = self._memory.get_lessons()
        all_eps = list(self._memory._short_term.values()) + list(self._memory._long_term.values())
        recent = sorted(all_eps, key=lambda e: e.entry_time, reverse=True)[:10]

        recent_trades = []
        for ep in recent:
            recent_trades.append({
                "symbol": ep.symbol, "direction": ep.direction,
                "pnl": ep.pnl, "outcome": ep.outcome,
                "impact_score": ep.impact_score,
            })

        return {
            "stats": stats,
            "lessons": lessons[-20:],
            "recent_trades": recent_trades,
            "current_drawdown": self.state.current_drawdown,
            "win_streak": self.state.win_streak,
        }

    def _debate_signal(
        self,
        signal: dict[str, Any],
        market_data: dict[str, Any],
        memory_context: dict[str, Any],
    ) -> bool:
        """Run bull vs bear debate. Returns True if signal survives."""
        try:
            result = self._debate_engine.debate(
                signal=signal,
                market_data=market_data,
                indicators={},
                news_sentiment=0.0,
                risk_context={
                    "drawdown_pct": self.state.current_drawdown,
                    "daily_loss_pct": 0.0,
                    "open_positions": len(
                        self._trade_store.list_trades(status_filter="open")
                    ),
                    "max_positions": self.config.max_concurrent_trades,
                },
            )
            if result.verdict == DebateVerdict.REJECT:
                logger.info("loop.debate_rejected", symbol=signal.get("symbol"),
                            reason=result.reasoning)
                return False
            return True
        except Exception:
            logger.warning("loop.debate_error", exc_info=True)
            return False  # Fail-closed: reject signal on debate failure

    def _pre_trade_reflect(
        self,
        signal: dict[str, Any],
        memory_context: dict[str, Any],
    ) -> bool:
        """Pre-trade reflection check against memory patterns."""
        # Check if similar trades recently lost
        recent_losses = [
            t for t in memory_context.get("recent_trades", [])
            if t["outcome"] == "loss"
            and t["symbol"] == signal.get("symbol")
        ]
        if len(recent_losses) >= 2:
            logger.info("loop.reflect_blocked", symbol=signal.get("symbol"),
                        reason="consecutive_recent_losses")
            return False

        # Check drawdown limit
        if self.state.current_drawdown > 15.0:
            logger.info("loop.reflect_blocked", reason="max_drawdown",
                        drawdown=self.state.current_drawdown)
            return False

        return True

    def _execute_trade(self, signal: dict[str, Any]) -> dict[str, Any] | None:
        """Place a trade via the trade store."""
        # Circuit breaker: halt trading if drawdown exceeds threshold
        if self.state.current_drawdown > 20.0:
            logger.info("loop.circuit_breaker", drawdown=self.state.current_drawdown)
            return None

        try:
            # Safe take_profit access
            tp = signal.get("take_profit")
            if isinstance(tp, (list, tuple)) and tp:
                take_profit = tp[0]
            elif isinstance(tp, (int, float)):
                take_profit = tp
            else:
                take_profit = None

            trade = self._trade_store.create_trade({
                "symbol": signal["symbol"],
                "side": "buy" if signal.get("direction") == "long" else "sell",
                "quantity": 0.001,  # Minimal size for safety
                "price": signal.get("entry_price"),
                "stop_loss": signal.get("stop_loss"),
                "take_profit": take_profit,
                "strategy_id": signal.get("strategy_id", "loop_engine"),
                "notes": f"loop_cycle={self.state.cycle_count}",
            })
            self.state.last_trade_time = time.time()
            self.state.trades_placed += 1
            logger.info("loop.trade_executed", trade_id=trade.get("id"),
                        symbol=signal["symbol"])
            return trade
        except Exception:
            logger.warning("loop.execute_error", exc_info=True)
            return None

    def _log_to_memory(
        self,
        trade: dict[str, Any],
        cycle_id: str,
    ) -> None:
        """Store trade result in episodic memory."""
        episode = TradeEpisode(
            symbol=trade.get("symbol", ""),
            direction="long" if trade.get("side") == "buy" else "short",
            entry_price=trade.get("entry_price") or 0.0,
            exit_price=trade.get("exit_price") or 0.0,
            pnl=trade.get("pnl") or 0.0,
            market_context={"cycle_id": cycle_id, "engine": "loop"},
        )
        episode.finalize()
        episode.lessons.append(f"loop_cycle={cycle_id}")
        self._memory.store(episode)

    def _learn_from_outcomes(
        self,
        trades: list[dict[str, Any]],
        cycle_id: str,
    ) -> None:
        """Update state and weights based on recently closed trade outcomes.

        Instead of learning from just-placed trades (which have pnl=0),
        query the trade store for recently closed trades and learn from those.
        """
        closed = self._trade_store.list_trades(status_filter="closed")[-10:]
        for trade in closed:
            pnl = trade.get("pnl") or 0.0
            self.state.total_pnl += pnl

            if pnl > 0:
                if self.state.win_streak > 0:
                    self.state.win_streak += 1
                else:
                    self.state.win_streak = 1
            elif pnl == 0:
                self.state.win_streak = 0
            elif pnl < 0:
                if self.state.win_streak < 0:
                    self.state.win_streak -= 1
                else:
                    self.state.win_streak = -1
                self.state.cooldown_remaining = self.config.cooldown_after_loss

            # Update drawdown (peak-to-trough)
            self.state.peak_pnl = max(self.state.peak_pnl, self.state.total_pnl)
            if self.state.peak_pnl > 0:
                self.state.current_drawdown = (
                    (self.state.peak_pnl - self.state.total_pnl) / self.state.peak_pnl * 100
                )
            else:
                self.state.current_drawdown = abs(self.state.total_pnl)
            self.state.current_drawdown = max(0.0, self.state.current_drawdown)

        # Run post-trade reflection on closed trades
        try:
            for trade in closed:
                trade_data = {
                    **trade,
                    "direction": "long" if trade.get("side") == "buy" else "short",
                    "indicators": {},
                    "market_context": {"cycle_id": cycle_id},
                }
                chain = self._post_reflection.reflect(trade_data)
                correction = self._correction_engine.generate(
                    chain, trade_data, current_params={},
                )
                if correction:
                    logger.info("loop.correction_generated",
                                cycle_id=cycle_id, trade_id=trade.get("id"))
        except Exception:
            logger.warning("loop.learn_error", exc_info=True)
