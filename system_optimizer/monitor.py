"""System monitoring utilities."""

from __future__ import annotations

import os
import psutil
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, Iterable, List, Tuple

from .logging_config import get_logger

logger = get_logger("CPU")


@dataclass
class CpuMetrics:
    total: float
    per_core: List[float]
    temperature: float | None


@dataclass
class MemoryMetrics:
    total: int
    used: int
    free: int
    percent: float
    swap_total: int
    swap_used: int
    swap_free: int
    swap_percent: float


@dataclass
class DiskMetrics:
    total: int
    used: int
    free: int
    percent: float
    read_bytes: int
    write_bytes: int


@dataclass
class NetworkMetrics:
    bytes_sent: int
    bytes_recv: int
    connections: List[Tuple[str, str, str]]


@dataclass
class HistoricalSeries:
    """Maintain a fixed length history of metrics for charting."""

    maxlen: int
    values: Deque[float] = field(init=False)

    def __post_init__(self) -> None:
        self.values = deque(maxlen=self.maxlen)

    def append(self, value: float) -> None:
        self.values.append(value)

    def __iter__(self) -> Iterable[float]:
        return iter(self.values)


class SystemMonitor:
    """Collect system metrics using psutil."""

    def __init__(self, history_size: int = 60) -> None:
        self.cpu_history = HistoricalSeries(history_size)
        self.memory_history = HistoricalSeries(history_size)
        self.network_history = HistoricalSeries(history_size)
        self._prev_disk_io = psutil.disk_io_counters()
        self._prev_net_io = psutil.net_io_counters()

    def cpu_metrics(self) -> CpuMetrics:
        total = psutil.cpu_percent(interval=None)
        per_core = psutil.cpu_percent(interval=None, percpu=True)
        temperature = self._read_cpu_temperature()
        self.cpu_history.append(total)
        logger.info("Updated CPU usage to %.2f%%", total)
        return CpuMetrics(total=total, per_core=per_core, temperature=temperature)

    def _read_cpu_temperature(self) -> float | None:
        try:
            temps = psutil.sensors_temperatures()
        except (AttributeError, NotImplementedError):
            logger.warning("CPU temperature reading not supported on this platform")
            return None
        if not temps:
            return None
        for entries in temps.values():
            for entry in entries:
                if entry.current is not None:
                    return float(entry.current)
        return None

    def memory_metrics(self) -> MemoryMetrics:
        vm = psutil.virtual_memory()
        sm = psutil.swap_memory()
        self.memory_history.append(vm.percent)
        return MemoryMetrics(
            total=vm.total,
            used=vm.used,
            free=vm.available,
            percent=vm.percent,
            swap_total=sm.total,
            swap_used=sm.used,
            swap_free=sm.free,
            swap_percent=sm.percent,
        )

    def disk_metrics(self) -> Dict[str, DiskMetrics]:
        metrics: Dict[str, DiskMetrics] = {}
        for part in psutil.disk_partitions():
            if os.name == "nt":
                if "cdrom" in part.opts or part.fstype == "":
                    continue
            try:
                usage = psutil.disk_usage(part.mountpoint)
            except PermissionError:
                continue
        
            current_io = psutil.disk_io_counters()
            read_bytes = current_io.read_bytes - self._prev_disk_io.read_bytes
            write_bytes = current_io.write_bytes - self._prev_disk_io.write_bytes
            metrics[part.mountpoint] = DiskMetrics(
                total=usage.total,
                used=usage.used,
                free=usage.free,
                percent=usage.percent,
                read_bytes=read_bytes,
                write_bytes=write_bytes,
            )
        self._prev_disk_io = psutil.disk_io_counters()
        return metrics

    def network_metrics(self) -> NetworkMetrics:
        current_io = psutil.net_io_counters()
        sent = current_io.bytes_sent - self._prev_net_io.bytes_sent
        recv = current_io.bytes_recv - self._prev_net_io.bytes_recv
        self._prev_net_io = current_io
        self.network_history.append(max(sent, recv))

        connections: List[Tuple[str, str, str]] = []
        for conn in psutil.net_connections():
            laddr = f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else ""
            raddr = f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else ""
            status = conn.status
            connections.append((conn.type.name if hasattr(conn.type, "name") else str(conn.type), laddr, raddr or status))
        return NetworkMetrics(bytes_sent=sent, bytes_recv=recv, connections=connections)

    def running_processes(self, limit: int = 50) -> List[Tuple[int, str, float]]:
        processes: List[Tuple[int, str, float]] = []
        for proc in psutil.process_iter(["pid", "name", "cpu_percent"]):
            try:
                processes.append((proc.info["pid"], proc.info["name"], proc.info["cpu_percent"]))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        processes.sort(key=lambda item: item[2], reverse=True)
        return processes[:limit]

