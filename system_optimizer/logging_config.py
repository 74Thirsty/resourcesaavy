"""Logging configuration for the System Optimizer application."""

from __future__ import annotations

import logging
from typing import Optional

LOG_FORMAT = "{timestamp} - {log_level} - {component} - {message}"


class ComponentLogger(logging.LoggerAdapter):
    """Logger adapter that injects the component name into the log record."""

    def __init__(self, logger: logging.Logger, component: str) -> None:
        super().__init__(logger, {"component": component})

    def process(self, msg: str, kwargs: dict) -> tuple[str, dict]:
        extra = kwargs.setdefault("extra", {})
        extra.setdefault("component", self.extra["component"])
        return msg, kwargs


def configure_logging(level: int = logging.INFO) -> None:
    """Configure application-wide logging with the mandated format."""

    class ComponentFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            timestamp = self.formatTime(record, self.datefmt)
            message = record.getMessage()
            component = getattr(record, "component", record.name)
            return LOG_FORMAT.format(
                timestamp=timestamp,
                log_level=record.levelname,
                component=component,
                message=message,
            )

    handler = logging.StreamHandler()
    handler.setFormatter(ComponentFormatter())

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clear default handlers to avoid duplicate logs when running multiple times.
    if root_logger.handlers:
        root_logger.handlers.clear()

    root_logger.addHandler(handler)


def get_logger(component: str, level: Optional[int] = None) -> ComponentLogger:
    """Return a component-specific logger adapter."""

    logger = logging.getLogger(component)
    if level is not None:
        logger.setLevel(level)
    return ComponentLogger(logger, component)
