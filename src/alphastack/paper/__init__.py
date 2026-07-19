"""Paper trading module — shadow mode for AlphaStack.

Runs the full pipeline (news → strategy → risk → execution) with virtual
money.  Every trade decision is logged with reasoning, and real-time
performance metrics are computed continuously.

This is the bridge between code and real money.
"""

from alphastack.paper.metrics import PerformanceMetrics
from alphastack.paper.trader import PaperTrader

__all__ = ["PaperTrader", "PerformanceMetrics"]
