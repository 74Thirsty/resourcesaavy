from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Dict, List, Optional

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
            lines = log_file.read_text(errors="ignore").splitlines()
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


def export_logs(destination: Path) -> Optional[Path]:
    try:
        destination.write_text("\n".join(read_logs()))
        log_logger.info("Exported logs to %s", destination)
        return destination
    except PermissionError as exc:
        log_logger.error("Failed to export logs: %s", exc)
        return None


def generate_performance_report(monitor: SystemMonitor) -> Path:
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = REPORTS_DIR / f"performance_report_{timestamp}.json"

    try:
        cpu = monitor.cpu_metrics()
        mem = monitor.memory_metrics()
        disk = monitor.disk_metrics()
        net = monitor.network_metrics()
        procs = monitor.running_processes(50)

        report: Dict[str, object] = {
            "generated_at": dt.datetime.now().isoformat(),
            "cpu": {"total": cpu.total, "per_core": cpu.per_core, "temperature": cpu.temperature},
            "memory": {
                "total": mem.total,
                "used": mem.used,
                "free": mem.free,
                "percent": mem.percent,
                "swap": {"total": mem.swap_total, "used": mem.swap_used, "free": mem.swap_free, "percent": mem.swap_percent},
            },
            "disk": {k: v.__dict__ for k, v in disk.items()},
            "network": {"bytes_sent": net.bytes_sent, "bytes_recv": net.bytes_recv, "connections": net.connections},
            "top_processes": [{"pid": p[0], "name": p[1], "cpu_percent": p[2]} for p in procs],
            "logs_sample": read_logs(200),
        }

        filename.write_text(json.dumps(report, indent=2))
        log_logger.info("Generated performance report %s", filename)
        return filename
    except Exception as exc:
        log_logger.error("Failed to generate performance report: %s", exc)
        fallback = REPORTS_DIR / f"performance_report_error_{timestamp}.txt"
        fallback.write_text(f"Failed to generate report: {exc}\n")
        return fallback
