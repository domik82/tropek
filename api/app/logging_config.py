"""Structured logging configuration using structlog."""

from __future__ import annotations

import structlog


def configure_logging(*, json_output: bool = False) -> None:
    """Configure structlog processors and output format.

    Args:
        json_output: If True, render logs as JSON; otherwise use console renderer.
    """
    processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]
    if json_output:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
