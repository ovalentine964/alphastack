"""Structured logging for AlphaStack."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import structlog


def setup_logging(
    level: str = "INFO",
    json_output: bool = True,
    log_dir: str | Path = "logs",
) -> None:
    """Configure structured logging with structlog.

    Args:
        level: Root log level.
        json_output: If True, emit JSON lines; otherwise, use console colours.
        log_dir: Directory for trade log files.
    """
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # Shared processors
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if json_output:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level.upper())
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)

    # Trade-specific file handler (always JSON)
    trade_handler = logging.FileHandler(log_path / "trades.jsonl")
    trade_formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
        foreign_pre_chain=shared_processors,
    )
    trade_handler.setFormatter(trade_formatter)
    trade_logger = logging.getLogger("alphastack.trades")
    trade_logger.addHandler(trade_handler)
    trade_logger.setLevel("DEBUG")
    trade_logger.propagate = True

    # Suppress noisy libraries
    for noisy in ("httpx", "httpcore", "asyncio", "uvicorn.access"):
        logging.getLogger(noisy).setLevel("WARNING")


def get_logger(name: str, **initial_context: Any) -> structlog.stdlib.BoundLogger:
    """Get a bound structlog logger.

    Args:
        name: Logger name (typically ``__name__``).
        **initial_context: Pre-bound key/value pairs.

    Returns:
        A configured ``BoundLogger``.
    """
    return structlog.get_logger(name).bind(**initial_context)  # type: ignore[return-value]


def get_trade_logger(**initial_context: Any) -> structlog.stdlib.BoundLogger:
    """Get a logger specifically for trade events (writes to trades.jsonl)."""
    return get_logger("alphastack.trades", **initial_context)
