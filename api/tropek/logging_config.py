"""Structured logging configuration using structlog.

Routes structlog through Python's stdlib logging so that all output
(structlog + stdlib) goes to the same handlers: stderr + rotating file.
"""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

import structlog

_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
_BACKUP_COUNT = 100


def configure_logging(
    *,
    json_output: bool = False,
    service_name: str = 'api',
) -> None:
    """Configure structlog to route through stdlib logging with rotating file output.

    Args:
        json_output: If True, render logs as JSON; otherwise use console renderer.
        service_name: Name used for the log file (e.g. 'api', 'worker').
    """
    # --- stdlib logging setup (handlers) ---
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # Avoid duplicate handlers on repeated calls (e.g. worker startup)
    if root.handlers:
        return

    # Stderr handler — uses structlog's formatter for pretty console output
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.INFO)

    console_renderer = (
        structlog.processors.JSONRenderer() if json_output else structlog.dev.ConsoleRenderer()
    )

    stderr_handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processor=console_renderer,
            foreign_pre_chain=[
                structlog.stdlib.add_log_level,
                structlog.processors.TimeStamper(fmt='iso'),
            ],
        )
    )
    root.addHandler(stderr_handler)

    # File handler via LOG_DIR env var — rotating 10 MB x 100 files
    log_dir = os.environ.get('LOG_DIR')
    if log_dir:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_path / f'{service_name}.log',
            maxBytes=_MAX_BYTES,
            backupCount=_BACKUP_COUNT,
        )
        file_handler.setLevel(logging.DEBUG)
        file_renderer = (
            structlog.processors.JSONRenderer()
            if json_output
            else structlog.dev.ConsoleRenderer(colors=False)
        )
        file_handler.setFormatter(
            structlog.stdlib.ProcessorFormatter(
                processor=file_renderer,
                foreign_pre_chain=[
                    structlog.stdlib.add_log_level,
                    structlog.processors.TimeStamper(fmt='iso'),
                ],
            )
        )
        root.addHandler(file_handler)

    # --- structlog setup (route through stdlib) ---
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt='iso'),
            structlog.processors.StackInfoRenderer(),
            # Hand off to stdlib logging — ProcessorFormatter does final rendering
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
