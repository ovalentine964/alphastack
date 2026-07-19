"""PaperTrader — shadow-mode execution engine.

Runs the full AlphaStack pipeline (news → strategy → debate → risk → execution)
with virtual money.  Simulates order fills at market prices, tracks virtual
positions and PnL, and logs every trade decision with full reasoning.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from alphastack.paper.metrics import PerformanceMetrics, TradeRecord
from alphastack.utils.logger import get_logger, get_trade_logger

log = get_logger(__name__)
trade_log = get_trade_logger()


# ---------------------------------------------------------------------------
# Virtual position
# ---------------------------------------------------------------------------

class VirtualPosition(BaseModel):
    """A paper-traded position."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    symbol: str
    side: Literal["long", "short"]
    entry_price: float
    quantity: float
    stop_loss: float | None = None
    take_profit: float | None = None
    opened_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    strategy: str = ""
    reasoning: str = ""

    # Live tracking
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    max_favorable: float = 0.0  # max unrealized profit (for trailing)
    max_adverse: float = 0.0  # max unrealized loss (for risk monitoring)

    def update_price(self, price: float) -> None:
        """Update current price and recalculate unrealized P&L."""
        self.current_price = price
        if self.side == "long":
            self.unrealized_pnl = (price - self.entry_price) * self.quantity
        else:
            self.unrealized_pnl = (self.entry_price - price) * self.quantity

        if self.unrealized_pnl > self.max_favorable:
            self.max_favorable = self.unrealized_pnl
        if self.unrealized_pnl < -abs(self.max_adverse):
            self.max_adverse = abs(self.unrealized_pnl)

    @property
    def pnl_pct(self) -> float:
        if self.entry_price == 0:
            return 0.0
        if self.side == "long":
            return (self.current_price - self.entry_price) / self.entry_price
        return (self.entry_price - self.current_price) / self.entry_price

    @property
    def notional_value(self) -> float:
        return abs(self.quantity * self.entry_price)


# ---------------------------------------------------------------------------
# Trade journal entry
# ---------------------------------------------------------------------------

class TradeJournalEntry(BaseModel):
    """Full record of a trade decision for audit and analysis."""

    trade_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    symbol: str
    action: Literal["open", "close", "modify", "skip"]
    side: Literal["long", "short", "flat"] = "flat"
    quantity: float = 0.0
    price: float = 0.0
    stop_loss: float | None = None
    take_profit: float | None = None
    reasoning: str = ""
    strategy: str = ""

    # Pipeline context
    news_alerts: list[dict[str, Any]] = Field(default_factory=list)
    risk_status: dict[str, Any] = Field(default_factory=dict)
    debate_result: dict[str, Any] = Field(default_factory=dict)
    signal: dict[str, Any] = Field(default_factory=dict)

    # Outcome (filled after close)
    pnl: float = 0.0
    pnl_pct: float = 0.0
    exit_price: float = 0.0
    duration_minutes: float = 0.0
    commission: float = 0.0

    # Paper trading metadata
    simulated_slippage_bps: float = 0.0
    fill_latency_ms: float = 0.0


# ---------------------------------------------------------------------------
# Paper trading configuration
# ---------------------------------------------------------------------------

@dataclass
class PaperConfig:
    """Configuration for the paper trader."""

    # Account
    initial_balance: float = 10_000.0
    currency: str = "USDT"

    # Execution simulation
    slippage_bps: float = 5.0  # basis points
    commission_pct: float = 0.001  # 0.1% taker fee
    fill_latency_ms: float = 50.0  # simulated latency
    min_order_size: float = 0.0001  # minimum BTC
    max_order_size: float = 10.0  # maximum BTC

    # Symbols
    symbols: list[str] = field(default_factory=lambda: ["BTC/USDT"])
    default_timeframe: str = "1h"

    # Risk overrides (in addition to RiskGovernor)
    max_positions: int = 5
    max_position_pct: float = 0.20  # 20% of balance per position
    max_total_exposure_pct: float = 0.80  # 80% max total exposure

    # Persistence
    journal_path: str = "data/paper_journal.jsonl"
    equity_snapshot_interval: int = 60  # seconds between equity snapshots

    # Orchestrator settings
    human_in_the_loop: bool = False  # no HITL in paper mode
    hitl_threshold: float = 0.8


# ---------------------------------------------------------------------------
# PaperTrader
# ---------------------------------------------------------------------------

class PaperTrader:
    """Shadow-mode trading engine.

    Runs the full AlphaStack pipeline with simulated execution.
    Tracks virtual positions, computes real-time performance metrics,
    and logs every trade decision with full reasoning for later analysis.
    """

    def __init__(
        self,
        config: PaperConfig | None = None,
        orchestrator: Any | None = None,
        data_pipeline: Any | None = None,
    ) -> None:
        self.config = config or PaperConfig()
        self._orchestrator = orchestrator
        self._data_pipeline = data_pipeline

        # State
        self._balance: float = self.config.initial_balance
        self._positions: dict[str, VirtualPosition] = {}  # symbol → position
        self._closed_positions: list[VirtualPosition] = []
        self._journal: list[TradeJournalEntry] = []
        self._running: bool = False
        self._cycle_count: int = 0

        # Metrics
        self.metrics = PerformanceMetrics(
            initial_balance=self.config.initial_balance,
        )

        # Journal persistence
        self._journal_path = Path(self.config.journal_path)
        self._journal_path.parent.mkdir(parents=True, exist_ok=True)

        log.info(
            "paper_trader_initialized",
            balance=self._balance,
            symbols=self.config.symbols,
            slippage_bps=self.config.slippage_bps,
        )

    # -- Lifecycle ----------------------------------------------------------

    async def start(self, cycles: int | None = None) -> None:
        """Start the paper trading loop.

        Parameters
        ----------
        cycles : int | None
            Run for exactly N cycles then stop.  None = run forever.
        """
        self._running = True
        log.info("paper_trader_started", cycles=cycles)

        try:
            while self._running:
                self._cycle_count += 1
                if cycles and self._cycle_count > cycles:
                    break

                for symbol in self.config.symbols:
                    try:
                        await self._run_cycle(symbol)
                    except Exception as exc:
                        log.error(
                            "cycle_failed",
                            cycle=self._cycle_count,
                            symbol=symbol,
                            error=str(exc),
                            exc_info=True,
                        )

                # Snapshot equity
                equity = self._compute_equity()
                self.metrics.snapshot_equity(
                    equity=equity,
                    balance=self._balance,
                    unrealized_pnl=self._total_unrealized_pnl(),
                )

                # Wait between cycles (adaptive: faster if positions open)
                if self._positions:
                    await asyncio.sleep(10)
                else:
                    await asyncio.sleep(30)

        except asyncio.CancelledError:
            log.info("paper_trader_cancelled")
        finally:
            self._running = False
            log.info("paper_trader_stopped", cycles_completed=self._cycle_count)

    def stop(self) -> None:
        """Gracefully stop the paper trader."""
        self._running = False

    # -- Core cycle ---------------------------------------------------------

    async def _run_cycle(self, symbol: str) -> None:
        """Execute one full pipeline cycle for a symbol."""
        log.info("cycle_start", cycle=self._cycle_count, symbol=symbol)

        # 1. Fetch market data
        market_data = await self._fetch_market_data(symbol)
        if not market_data:
            log.warning("no_market_data", symbol=symbol)
            return

        # Update position prices
        self._update_position_prices(symbol, market_data)

        # Check stop-loss / take-profit before running pipeline
        await self._check_exits(symbol, market_data)

        # 2. Run full pipeline through orchestrator
        if self._orchestrator is None:
            log.warning("no_orchestrator_configured")
            return

        try:
            state = await self._orchestrator.run(
                market_data=market_data,
                symbol=symbol,
                timeframe=self.config.default_timeframe,
                thread_id=f"paper-{symbol}",
            )
        except Exception as exc:
            log.error("orchestrator_failed", symbol=symbol, error=str(exc))
            return

        # 3. Process approved trade decisions
        await self._process_decisions(state, market_data)

        log.info(
            "cycle_complete",
            cycle=self._cycle_count,
            symbol=symbol,
            positions=len(self._positions),
            balance=round(self._balance, 2),
        )

    # -- Market data --------------------------------------------------------

    async def _fetch_market_data(self, symbol: str) -> dict[str, Any] | None:
        """Fetch latest market data for the symbol."""
        if self._data_pipeline is not None:
            try:
                return self._data_pipeline.get_market_snapshot(symbol)
            except Exception as exc:
                log.warning("data_fetch_failed", symbol=symbol, error=str(exc))

        # Fallback: try to get from orchestrator's broker
        if self._orchestrator and hasattr(self._orchestrator, "broker_registry"):
            registry = self._orchestrator.broker_registry
            if registry:
                try:
                    connector = registry.get_default()
                    tick = await connector.get_tick(symbol)
                    bars = await connector.get_bars(symbol, self.config.default_timeframe, 100)
                    return {
                        symbol: {
                            "tick": tick.model_dump() if hasattr(tick, "model_dump") else tick,
                            "bars": [b.model_dump() if hasattr(b, "model_dump") else b for b in bars],
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                    }
                except Exception as exc:
                    log.warning("broker_data_failed", symbol=symbol, error=str(exc))

        return None

    # -- Position management ------------------------------------------------

    def _update_position_prices(self, symbol: str, market_data: dict[str, Any]) -> None:
        """Update current prices for all positions of a symbol."""
        price = self._extract_price(symbol, market_data)
        if price is None:
            return

        pos = self._positions.get(symbol)
        if pos:
            pos.update_price(price)

    def _extract_price(self, symbol: str, market_data: dict[str, Any]) -> float | None:
        """Extract the current market price from market data."""
        data = market_data.get(symbol, market_data)
        if isinstance(data, dict):
            # Try tick data
            tick = data.get("tick", {})
            if isinstance(tick, dict):
                for key in ("last", "mid", "close"):
                    if tick.get(key):
                        return float(tick[key])
                if tick.get("bid") and tick.get("ask"):
                    return (float(tick["bid"]) + float(tick["ask"])) / 2.0

            # Try bars (last close)
            bars = data.get("bars", [])
            if bars and isinstance(bars, list):
                last_bar = bars[-1]
                if isinstance(last_bar, dict) and last_bar.get("close"):
                    return float(last_bar["close"])

            # Try direct close/price
            for key in ("close", "price", "last"):
                if data.get(key):
                    return float(data[key])

        return None

    async def _check_exits(self, symbol: str, market_data: dict[str, Any]) -> None:
        """Check stop-loss and take-profit for open positions."""
        pos = self._positions.get(symbol)
        if not pos:
            return

        price = self._extract_price(symbol, market_data)
        if price is None:
            return

        # Stop-loss check
        if pos.stop_loss is not None:
            if pos.side == "long" and price <= pos.stop_loss:
                await self._close_position(symbol, price, "stop_loss", f"Stop-loss triggered at {pos.stop_loss}")
                return
            elif pos.side == "short" and price >= pos.stop_loss:
                await self._close_position(symbol, price, "stop_loss", f"Stop-loss triggered at {pos.stop_loss}")
                return

        # Take-profit check
        if pos.take_profit is not None:
            if pos.side == "long" and price >= pos.take_profit:
                await self._close_position(symbol, price, "take_profit", f"Take-profit triggered at {pos.take_profit}")
                return
            elif pos.side == "short" and price <= pos.take_profit:
                await self._close_position(symbol, price, "take_profit", f"Take-profit triggered at {pos.take_profit}")
                return

    # -- Decision processing ------------------------------------------------

    async def _process_decisions(self, state: Any, market_data: dict[str, Any]) -> None:
        """Process approved trade decisions from the pipeline."""
        decisions = state.trade_decisions if hasattr(state, "trade_decisions") else []
        for decision in decisions:
            d = decision if isinstance(decision, dict) else decision.model_dump()
            status = d.get("status", "pending")

            if status != "approved":
                # Journal the rejection
                self._journal_decision(d, action="skip", reasoning=d.get("rejection_reason", "Not approved"))
                continue

            symbol = d.get("symbol", "")
            action = d.get("action", "hold")
            quantity = d.get("quantity", 0)
            price = d.get("price", 0)
            order_type = d.get("order_type", "market")

            # Get signal reasoning
            signal = d.get("signal", {}) or {}
            reasoning = signal.get("reasoning", "")
            strategy = signal.get("strategy", "alphastack")
            stop_loss = signal.get("stop_loss")
            take_profit = signal.get("take_profit")

            # Get current price for market orders
            if order_type == "market" or price == 0:
                price = self._extract_price(symbol, market_data)
                if price is None:
                    log.warning("no_price_for_execution", symbol=symbol)
                    continue

            # Simulate execution
            if action in ("buy", "sell"):
                side = "long" if action == "buy" else "short"
                await self._open_position(
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                    price=price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    strategy=strategy,
                    reasoning=reasoning,
                    signal=signal,
                    risk_status=state.risk_status.model_dump() if hasattr(state.risk_status, "model_dump") else {},
                    news_alerts=[a.model_dump() if hasattr(a, "model_dump") else a for a in state.news_alerts],
                )
            elif action == "close":
                await self._close_position(symbol, price, "signal_close", reasoning)

    # -- Open / Close -------------------------------------------------------

    async def _open_position(
        self,
        symbol: str,
        side: Literal["long", "short"],
        quantity: float,
        price: float,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        strategy: str = "",
        reasoning: str = "",
        signal: dict[str, Any] | None = None,
        risk_status: dict[str, Any] | None = None,
        news_alerts: list[dict[str, Any]] | None = None,
    ) -> VirtualPosition | None:
        """Open a new paper position with simulated execution."""
        # Check if already have a position
        existing = self._positions.get(symbol)
        if existing:
            if existing.side == side:
                log.info("position_already_open", symbol=symbol, side=side)
                return None
            # Close opposite position first
            await self._close_position(price, symbol, "reversal", f"Reversing to {side}")

        # Apply slippage
        slippage = price * (self.config.slippage_bps / 10_000)
        if side == "long":
            fill_price = price + slippage
        else:
            fill_price = price - slippage

        # Compute commission
        notional = quantity * fill_price
        commission = notional * self.config.commission_pct

        # Check balance
        if notional + commission > self._balance:
            # Adjust quantity to fit balance
            max_notional = self._balance / (1 + self.config.commission_pct)
            quantity = max_notional / fill_price
            if quantity < self.config.min_order_size:
                log.warning("insufficient_balance", symbol=symbol, balance=self._balance)
                return None
            notional = quantity * fill_price
            commission = notional * self.config.commission_pct

        # Deduct from balance
        self._balance -= (notional + commission)

        # Create position
        pos = VirtualPosition(
            symbol=symbol,
            side=side,
            entry_price=fill_price,
            quantity=quantity,
            stop_loss=stop_loss,
            take_profit=take_profit,
            strategy=strategy,
            reasoning=reasoning,
            current_price=fill_price,
        )
        self._positions[symbol] = pos

        # Journal
        entry = TradeJournalEntry(
            trade_id=pos.id,
            symbol=symbol,
            action="open",
            side=side,
            quantity=quantity,
            price=fill_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            reasoning=reasoning,
            strategy=strategy,
            news_alerts=news_alerts or [],
            risk_status=risk_status or {},
            signal=signal or {},
            simulated_slippage_bps=self.config.slippage_bps,
            fill_latency_ms=self.config.fill_latency_ms,
            commission=commission,
        )
        self._write_journal(entry)

        trade_log.info(
            "paper_order_opened",
            trade_id=pos.id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=fill_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            commission=commission,
            reasoning=reasoning[:200],
        )

        log.info(
            "position_opened",
            trade_id=pos.id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=fill_price,
        )

        return pos

    async def _close_position(
        self,
        price: float,
        symbol: str,
        exit_reason: str = "manual",
        reasoning: str = "",
    ) -> TradeRecord | None:
        """Close an existing paper position."""
        pos = self._positions.pop(symbol, None)
        if not pos:
            log.warning("no_position_to_close", symbol=symbol)
            return None

        # Apply slippage
        slippage = price * (self.config.slippage_bps / 10_000)
        if pos.side == "long":
            fill_price = price - slippage  # sell lower
        else:
            fill_price = price + slippage  # buy higher

        # Compute P&L
        if pos.side == "long":
            pnl = (fill_price - pos.entry_price) * pos.quantity
        else:
            pnl = (pos.entry_price - fill_price) * pos.quantity

        # Commission
        notional = pos.quantity * fill_price
        commission = notional * self.config.commission_pct
        net_pnl = pnl - commission - pos.commission  # include open commission

        # Return capital + P&L
        self._balance += (pos.quantity * pos.entry_price) + net_pnl

        # P&L percentage
        pnl_pct = net_pnl / (pos.quantity * pos.entry_price) if pos.entry_price > 0 else 0.0

        # Create trade record for metrics
        now = datetime.now(timezone.utc)
        record = TradeRecord(
            id=pos.id,
            symbol=symbol,
            side=pos.side,
            entry_price=pos.entry_price,
            exit_price=fill_price,
            quantity=pos.quantity,
            pnl=net_pnl,
            pnl_pct=pnl_pct,
            entry_time=pos.opened_at,
            exit_time=now,
            commission=commission + pos.commission,
            slippage_bps=self.config.slippage_bps,
            reasoning=reasoning,
            strategy=pos.strategy,
            tags=[exit_reason],
        )
        self.metrics.record_trade(record)

        # Journal
        entry = TradeJournalEntry(
            trade_id=pos.id,
            symbol=symbol,
            action="close",
            side=pos.side,
            quantity=pos.quantity,
            price=fill_price,
            exit_reason=exit_reason,
            reasoning=reasoning,
            strategy=pos.strategy,
            pnl=net_pnl,
            pnl_pct=pnl_pct,
            exit_price=fill_price,
            duration_minutes=record.duration_minutes,
            commission=commission,
            simulated_slippage_bps=self.config.slippage_bps,
        )
        self._write_journal(entry)

        trade_log.info(
            "paper_position_closed",
            trade_id=pos.id,
            symbol=symbol,
            side=pos.side,
            entry_price=pos.entry_price,
            exit_price=fill_price,
            quantity=pos.quantity,
            pnl=round(net_pnl, 2),
            pnl_pct=round(pnl_pct, 4),
            exit_reason=exit_reason,
            duration_minutes=round(record.duration_minutes, 1),
            reasoning=reasoning[:200],
        )

        log.info(
            "position_closed",
            trade_id=pos.id,
            symbol=symbol,
            pnl=round(net_pnl, 2),
            exit_reason=exit_reason,
        )

        return record

    # -- Journaling ---------------------------------------------------------

    def _journal_decision(
        self,
        decision: dict[str, Any],
        action: str = "skip",
        reasoning: str = "",
    ) -> None:
        """Journal a trade decision (open, close, or skip)."""
        entry = TradeJournalEntry(
            trade_id=uuid.uuid4().hex[:12],
            symbol=decision.get("symbol", ""),
            action=action,  # type: ignore[arg-type]
            side=decision.get("action", "hold"),
            quantity=decision.get("quantity", 0),
            price=decision.get("price", 0),
            reasoning=reasoning,
        )
        self._write_journal(entry)

    def _write_journal(self, entry: TradeJournalEntry) -> None:
        """Append a journal entry to the JSONL file."""
        self._journal.append(entry)
        try:
            with open(self._journal_path, "a") as f:
                f.write(entry.model_dump_json() + "\n")
        except Exception as exc:
            log.warning("journal_write_failed", error=str(exc))

    # -- Account helpers ----------------------------------------------------

    def _compute_equity(self) -> float:
        """Total equity = balance + unrealized P&L."""
        return self._balance + self._total_unrealized_pnl()

    def _total_unrealized_pnl(self) -> float:
        return sum(p.unrealized_pnl for p in self._positions.values())

    @property
    def balance(self) -> float:
        return self._balance

    @property
    def equity(self) -> float:
        return self._compute_equity()

    @property
    def positions(self) -> dict[str, VirtualPosition]:
        return dict(self._positions)

    @property
    def is_running(self) -> bool:
        return self._running

    # -- Status -------------------------------------------------------------

    def status(self) -> dict[str, Any]:
        """Full paper trader status."""
        return {
            "running": self._running,
            "cycle_count": self._cycle_count,
            "balance": round(self._balance, 2),
            "equity": round(self._compute_equity(), 2),
            "unrealized_pnl": round(self._total_unrealized_pnl(), 2),
            "open_positions": len(self._positions),
            "positions": {
                sym: {
                    "side": p.side,
                    "entry_price": p.entry_price,
                    "current_price": p.current_price,
                    "quantity": p.quantity,
                    "unrealized_pnl": round(p.unrealized_pnl, 2),
                    "pnl_pct": round(p.pnl_pct * 100, 2),
                }
                for sym, p in self._positions.items()
            },
            "metrics": self.metrics.summary(),
        }
