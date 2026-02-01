from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .logging_config import get_logger

optimizer_logger = get_logger("Optimizer")

CPU_GOVERNOR_PATH = Path("/sys/devices/system/cpu")
SWAPPINESS_PATH = Path("/proc/sys/vm/swappiness")
DROP_CACHES_PATH = Path("/proc/sys/vm/drop_caches")
SYSTEMD_PATH = Path("/usr/bin/systemctl")


class ServiceManager:
    """Handle systemd service management."""

    def list_services(self) -> List[Dict[str, str]]:
        try:
            output = subprocess.run(
                ["systemctl", "list-units", "--type=service", "--all", "--output=json"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            services = json.loads(output)
            return [
                {
                    "name": svc.get("unit", "").replace(".service", ""),
                    "active": svc.get("active", "unknown"),
                    "sub": svc.get("sub", "unknown"),
                    "load": svc.get("load", "unknown"),
                }
                for svc in services
            ]
        except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
            optimizer_logger.error("Failed to list services: %s", exc)
            return []

    def _run_action(self, service: str, action: str) -> bool:
        try:
            subprocess.run([SYSTEMD_PATH, action, service], check=True, capture_output=True)
            optimizer_logger.info("%s service %s", action.capitalize(), service)
            return True
        except subprocess.CalledProcessError as exc:
            optimizer_logger.error("Failed to %s %s: %s", action, service, exc)
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
