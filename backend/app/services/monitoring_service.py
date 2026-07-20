"""Real-time system monitoring using psutil.

Collects CPU, memory, disk, network, uptime and load-average metrics. Network
throughput is computed as a delta between successive samples so the values are
expressed in bytes/second rather than cumulative counters.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

import psutil

from app.schemas.metric import MetricSnapshot

logger = logging.getLogger(__name__)


class MonitoringService:
    """Collects point-in-time system metrics.

    A single shared instance is used so network deltas remain consistent across
    successive samples.
    """

    def __init__(self) -> None:
        self._last_net = psutil.net_io_counters()
        self._last_net_time = time.monotonic()
        # Prime psutil's per-call CPU percentage (first call returns 0.0).
        psutil.cpu_percent(interval=None)

    def _network_rates(self) -> tuple[float, float, float, float]:
        """Return (sent_bps, recv_bps, total_sent_mb, total_recv_mb)."""
        now = time.monotonic()
        counters = psutil.net_io_counters()
        elapsed = max(now - self._last_net_time, 1e-6)

        sent_bps = (counters.bytes_sent - self._last_net.bytes_sent) / elapsed
        recv_bps = (counters.bytes_recv - self._last_net.bytes_recv) / elapsed

        self._last_net = counters
        self._last_net_time = now

        return (
            max(sent_bps, 0.0),
            max(recv_bps, 0.0),
            counters.bytes_sent / (1024 * 1024),
            counters.bytes_recv / (1024 * 1024),
        )

    @staticmethod
    def _load_average() -> tuple[float, float, float]:
        """Return the 1/5/15-minute load averages (0,0,0 if unavailable)."""
        try:
            return psutil.getloadavg()  # Available on Linux/macOS.
        except (AttributeError, OSError):  # pragma: no cover - platform dependent
            return (0.0, 0.0, 0.0)

    def collect(self) -> MetricSnapshot:
        """Collect a full metric snapshot."""
        cpu_usage = psutil.cpu_percent(interval=None)
        cpu_count = psutil.cpu_count(logical=True) or 1

        vmem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        sent_bps, recv_bps, sent_total_mb, recv_total_mb = self._network_rates()
        load1, load5, load15 = self._load_average()

        boot_time = datetime.fromtimestamp(psutil.boot_time(), tz=timezone.utc)
        uptime_seconds = time.time() - psutil.boot_time()

        return MetricSnapshot(
            cpu_usage=round(cpu_usage, 2),
            memory_usage=round(vmem.percent, 2),
            memory_total_mb=round(vmem.total / (1024 * 1024), 2),
            memory_used_mb=round(vmem.used / (1024 * 1024), 2),
            disk_usage=round(disk.percent, 2),
            disk_total_gb=round(disk.total / (1024**3), 2),
            disk_used_gb=round(disk.used / (1024**3), 2),
            network_sent=round(sent_bps, 2),
            network_recv=round(recv_bps, 2),
            network_sent_total_mb=round(sent_total_mb, 2),
            network_recv_total_mb=round(recv_total_mb, 2),
            load_avg_1m=round(load1, 2),
            load_avg_5m=round(load5, 2),
            load_avg_15m=round(load15, 2),
            cpu_count=cpu_count,
            uptime_seconds=round(uptime_seconds, 0),
            boot_time=boot_time,
            timestamp=datetime.now(timezone.utc),
        )


# Shared singleton used by the broadcaster, REST routes and alert engine.
monitoring_service = MonitoringService()
