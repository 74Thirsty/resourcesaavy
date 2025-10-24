"""System log utilities and reporting."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import List

from .logging_config import get_logger
from .monitor import SystemMonitor

log_logger = get_logger("Logs")

LOG_FILES = [
    Path("/var/log/syslog"),
    Path("/var/log/messages"),
    Path("/var/log/dmesg"),
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
            continue
        entries.extend(lines[-limit:])
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
        return None


def generate_performance_report(monitor: SystemMonitor, hours: int = 24) -> Path:
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORTS_DIR / f"performance_report_{timestamp}.txt"

    cpu = monitor.cpu_metrics()
    mem = monitor.memory_metrics()
    disk = monitor.disk_metrics()
    net = monitor.network_metrics()

    report_lines = [
        f"Performance Report generated at {dt.datetime.now().isoformat()}",
        "",
        "CPU Metrics:",
        f"  Total Usage: {cpu.total:.2f}%",
        f"  Per Core: {', '.join(f'{core:.2f}%' for core in cpu.per_core)}",
        f"  Temperature: {cpu.temperature or 'N/A'}",
        "",
        "Memory Metrics:",
        f"  Total: {mem.total / (1024 ** 3):.2f} GB",
        f"  Used: {mem.used / (1024 ** 3):.2f} GB",
        f"  Free: {mem.free / (1024 ** 3):.2f} GB",
        f"  Percent: {mem.percent:.2f}%",
        "",
        "Disk Metrics:",
    ]

    for mount, metrics in disk.items():
        report_lines.extend(
            [
                f"  Mount: {mount}",
                f"    Used: {metrics.used / (1024 ** 3):.2f} GB",
                f"    Free: {metrics.free / (1024 ** 3):.2f} GB",
                f"    Percent: {metrics.percent:.2f}%",
                f"    Read Bytes: {metrics.read_bytes}",
                f"    Write Bytes: {metrics.write_bytes}",
            ]
        )

    report_lines.extend(
        [
            "",
            "Network Metrics:",
            f"  Bytes Sent: {net.bytes_sent}",
            f"  Bytes Received: {net.bytes_recv}",
            f"  Active Connections: {len(net.connections)}",
        ]
    )

    report_path.write_text("\n".join(report_lines))
    log_logger.info("Generated performance report %s", report_path)
    return report_path
