"""Trading Engine — Continuous Loop for AlphaStack.

Implements the Loop Engineering pattern:
    Memory → Engine → Agents → Results → Memory → Repeat

Provides a background asyncio trading loop that reads from AGI memory,
runs the full multi-agent pipeline, executes trades, and writes results
back for continuous learning.
"""

from alphastack.engine.loop import TradingLoop, LoopConfig, LoopState

__all__ = ["TradingLoop", "LoopConfig", "LoopState"]
