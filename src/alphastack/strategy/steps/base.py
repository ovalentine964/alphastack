"""Base class for every AlphaStack pipeline step."""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod

from alphastack.strategy.context import AlphaStackContext


class AlphaStackStep(ABC):
    """Abstract base for all 16 pipeline steps.

    Subclasses must implement :meth:`execute`.  The base class provides
    timing, logging, and uniform error handling around that call.
    """

    # Subclasses override these
    step_number: int = 0
    step_name: str = "unnamed"

    def __init__(self) -> None:
        self.logger = logging.getLogger(f"alphastack.step.{self.step_number:02d}_{self.step_name}")

    # ------------------------------------------------------------------
    # Public entry-point (wraps execute with logging / metrics)
    # ------------------------------------------------------------------

    async def run(self, context: AlphaStackContext) -> AlphaStackContext:
        """Run the step with instrumentation."""
        self.logger.info("▶ Step %02d [%s] starting", self.step_number, self.step_name)
        t0 = time.perf_counter()
        try:
            result = await self.execute(context)
            elapsed = (time.perf_counter() - t0) * 1000
            self.logger.info(
                "✓ Step %02d [%s] completed in %.1f ms",
                self.step_number,
                self.step_name,
                elapsed,
            )
            return result
        except Exception:
            self.logger.exception("✗ Step %02d [%s] FAILED", self.step_number, self.step_name)
            raise

    # ------------------------------------------------------------------
    # Subclass contract
    # ------------------------------------------------------------------

    @abstractmethod
    async def execute(self, context: AlphaStackContext) -> AlphaStackContext:
        """Execute the step logic and return a **new** immutable context."""
        ...
