"""System log utilities and reporting."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import List

from .logging_config import get_logger
from .logging_config import APP_DIR, get_logger
from .monitor import SystemMonitor

log_logger = get_logger("Logs")

LOG_FILES = [
    Path("/var/log/syslog"),
    Path("/var/log/messages"),
    Path("/var/log/dmesg"),
    APP_DIR / "system_optimizer.log",
]

REPORTS_DIR = Path.home() / ".system_optimizer" / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def read_logs(limit: int = 1000) -> List[str]:
    entries: List[str] = []
    for log_file in LOG_FILES:
        if not log_file.exists():
            continue
        try:
            lines = log_file.read_text().splitlines()
        except PermissionError as exc:
            log_logger.error("Permission denied reading %s: %s", log_file, exc)
            entries.append(f"Permission denied reading {log_file}: {exc}")
            continue
        entries.extend(lines[-limit:])
    if not entries:
        entries.append("No log entries available. Try generating a report or waiting for new events.")
    log_logger.info("Loaded %d log entries", len(entries))
    return entries


def clear_logs() -> bool:
    success = True
    for log_file in LOG_FILES:
        if not log_file.exists():
            continue
        try:
            log_file.write_text("")
            log_logger.info("Cleared log file %s", log_file)
        except PermissionError as exc:
            log_logger.error("Failed to clear %s: %s", log_file, exc)
            success = False
    return success


def export_logs(destination: Path) -> Path | None:
    try:
        destination.write_text("\n".join(read_logs()))
        log_logger.info("Exported logs to %s", destination)
        return destination
    except PermissionError as exc:
        log_logger.error("Failed to export logs: %s", exc)
