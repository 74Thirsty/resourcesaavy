from __future__ import annotations

import datetime as dt
import json
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Iterable, List, Optional

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
    """Create a simple performance report from the provided `SystemMonitor`.

    The report is a JSON file placed in `REPORTS_DIR` and the function returns
    the `Path` to the generated file.
    """
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
            "cpu": {
                "total": cpu.total,
                "per_core": cpu.per_core,
                "temperature": cpu.temperature,
            },
            "memory": {
                "total": mem.total,
                "used": mem.used,
                "free": mem.free,
                "percent": mem.percent,
                "swap": {
                    "total": mem.swap_total,
                    "used": mem.swap_used,
                    "free": mem.swap_free,
                    "percent": mem.swap_percent,
                },
            },
            "disk": {k: v.__dict__ for k, v in disk.items()},
            "network": {
                "bytes_sent": net.bytes_sent,
                "bytes_recv": net.bytes_recv,
                "connections": net.connections,
            },
            "top_processes": [
                {"pid": p[0], "name": p[1], "cpu_percent": p[2]} for p in procs
            ],
            "logs_sample": read_logs(200),
        }

        filename.write_text(json.dumps(report, indent=2))
        log_logger.info("Generated performance report %s", filename)
        return filename
    except Exception as exc:
        log_logger.error("Failed to generate performance report: %s", exc)
        # ensure we still return a path even on failure if possible
        fallback = REPORTS_DIR / f"performance_report_error_{timestamp}.txt"
        fallback.write_text(f"Failed to generate report: {exc}\n")
        return fallback
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
        try:
            subprocess.run([SYSTEMD_PATH, action, service], check=True, capture_output=True)
            service_logger.info("%s service %s", action.capitalize(), service)
            return True
        except subprocess.CalledProcessError as exc:
            service_logger.error("Failed to %s %s: %s", action, service, exc)
            return False

    def start_service(self, service: str) -> bool:
        return self._run_action(service, "start")

    def stop_service(self, service: str) -> bool:
        return self._run_action(service, "stop")

    def enable_service(self, service: str) -> bool:
        return self._run_action(service, "enable")

    def disable_service(self, service: str) -> bool:
        return self._run_action(service, "disable")


class CpuTuner:
    """Handle CPU governor adjustments."""

    def available_governors(self) -> List[str]:
        governors: List[str] = []
        for cpu_path in CPU_GOVERNOR_PATH.glob("cpu[0-9]*/cpufreq/scaling_available_governors"):
            try:
                content = cpu_path.read_text().strip()
            except FileNotFoundError:
                continue
            governors.extend(content.split())
        return sorted(set(governors))

    def current_governor(self) -> Optional[str]:
        for cpu_path in CPU_GOVERNOR_PATH.glob("cpu[0-9]*/cpufreq/scaling_governor"):
            try:
                return cpu_path.read_text().strip()
            except FileNotFoundError:
                continue
        return None

    def set_governor(self, governor: str) -> bool:
        success = True
        for cpu_path in CPU_GOVERNOR_PATH.glob("cpu[0-9]*/cpufreq/scaling_governor"):
            try:
                cpu_path.write_text(governor)
                optimizer_logger.info("CPU governor set to %s for %s", governor, cpu_path.parent.name)
            except (FileNotFoundError, PermissionError) as exc:
                optimizer_logger.error("Failed to set governor for %s: %s", cpu_path.parent.name, exc)
                success = False
        return success


class MemoryTuner:
    """Adjust memory-related settings."""

    def swappiness(self) -> Optional[int]:
        try:
            return int(SWAPPINESS_PATH.read_text().strip())
        except (FileNotFoundError, ValueError):
            optimizer_logger.error("Unable to read swappiness value")
            return None

    def set_swappiness(self, value: int) -> bool:
        try:
            SWAPPINESS_PATH.write_text(str(value))
            optimizer_logger.info("Swappiness set to %d", value)
            return True
        except (FileNotFoundError, PermissionError) as exc:
            optimizer_logger.error("Failed to set swappiness: %s", exc)
            return False

    def clear_cache(self) -> bool:
        try:
            DROP_CACHES_PATH.write_text("3\n")
            optimizer_logger.info("Cleared page cache, dentries, and inodes")
            return True
        except (FileNotFoundError, PermissionError) as exc:
            optimizer_logger.error("Failed to clear caches: %s", exc)
            return False


class DiskCleaner:
    """Clean disk by removing unused files and invoking system package managers."""

    TEMP_DIRS = [Path("/tmp"), Path.home() / ".cache"]

    def clean_temp_files(self) -> List[Path]:
        removed: List[Path] = []
        for temp_dir in self.TEMP_DIRS:
            if not temp_dir.exists():
                continue
            for item in temp_dir.iterdir():
                try:
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
                    removed.append(item)
                    optimizer_logger.info("Removed temporary file %s", item)
                except (PermissionError, OSError) as exc:
                    optimizer_logger.error("Failed to remove %s: %s", item, exc)
        return removed

    def clean_package_cache(self) -> bool:
        commands = [
            ["apt", "clean"],
            ["apt", "autoremove", "-y"],
            ["journalctl", "--vacuum-time=7d"],
        ]
        success = True
        for command in commands:
            try:
                subprocess.run(command, check=True, capture_output=True)
                optimizer_logger.info("Executed %s", " ".join(command))
            except (FileNotFoundError, subprocess.CalledProcessError) as exc:
                optimizer_logger.error("Failed to execute %s: %s", command[0], exc)
                success = False
        return success


class SystemTuner:
    """Provide simple recommendations based on current system state."""

    def recommendations(self, services: Iterable[Dict[str, str]]) -> List[str]:
        recs: List[str] = []
        inactive = [svc for svc in services if svc.get("active") == "inactive"]
        if inactive:
            recs.append(f"Disable {len(inactive)} inactive services to free resources")
        if shutil.disk_usage("/").free < 5 * 1024 ** 3:
            recs.append("Low disk space detected on root partition")
        if not recs:
            recs.append("System is running optimally")
        optimizer_logger.info("Generated %d recommendations", len(recs))
        return recs

    def apply_recommendations(self, services: Iterable[Dict[str, str]]) -> List[str]:
        applied: List[str] = []
        service_manager = ServiceManager()
        for svc in services:
            if svc.get("active") == "inactive":
                if service_manager.disable_service(svc["name"]):
                    message = f"Disabled service {svc['name']}"
                    applied.append(message)
                    optimizer_logger.info(message)
        return applied


def save_schedule_config(config: Dict[str, object], path: Path) -> None:
    path.write_text(json.dumps(config, indent=2))
    optimizer_logger.info("Saved schedule configuration to %s", path)


def load_schedule_config(path: Path) -> Dict[str, object]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        optimizer_logger.error("Invalid schedule configuration in %s", path)
        return {}
