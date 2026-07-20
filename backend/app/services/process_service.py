"""Process monitoring service backed by psutil."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Literal, Optional

import psutil

from app.schemas.metric import ProcessDetail, ProcessInfo

logger = logging.getLogger(__name__)

SortKey = Literal["cpu", "memory", "name", "pid"]


class ProcessService:
    """Lists and inspects running processes."""

    # Attributes fetched in a single batch for efficiency.
    _ATTRS = ["pid", "name", "cpu_percent", "memory_percent", "memory_info", "status", "username"]

    def list_processes(
        self,
        search: Optional[str] = None,
        sort_by: SortKey = "cpu",
        descending: bool = True,
        limit: int = 100,
    ) -> list[ProcessInfo]:
        """Return running processes with optional search and sorting."""
        processes: list[ProcessInfo] = []
        for proc in psutil.process_iter(self._ATTRS):
            try:
                info = proc.info
                name = info.get("name") or ""
                if search and search.lower() not in name.lower():
                    continue
                mem_info = info.get("memory_info")
                mem_mb = (mem_info.rss / (1024 * 1024)) if mem_info else 0.0
                processes.append(
                    ProcessInfo(
                        pid=info["pid"],
                        name=name,
                        cpu_usage=round(info.get("cpu_percent") or 0.0, 2),
                        memory_usage=round(info.get("memory_percent") or 0.0, 2),
                        memory_mb=round(mem_mb, 2),
                        status=info.get("status") or "unknown",
                        username=info.get("username"),
                    )
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        key_map = {
            "cpu": lambda p: p.cpu_usage,
            "memory": lambda p: p.memory_usage,
            "name": lambda p: p.name.lower(),
            "pid": lambda p: p.pid,
        }
        sort_func = key_map.get(sort_by, key_map["cpu"])
        # For name we want ascending by default; numeric metrics descending.
        reverse = descending and sort_by not in {"name"}
        processes.sort(key=sort_func, reverse=reverse)
        return processes[:limit]

    def get_process(self, pid: int) -> Optional[ProcessDetail]:
        """Return detailed information for a single process."""
        try:
            proc = psutil.Process(pid)
            with proc.oneshot():
                mem_info = proc.memory_info()
                create_time = datetime.fromtimestamp(
                    proc.create_time(), tz=timezone.utc
                )
                return ProcessDetail(
                    pid=proc.pid,
                    name=proc.name(),
                    cpu_usage=round(proc.cpu_percent(interval=0.1), 2),
                    memory_usage=round(proc.memory_percent(), 2),
                    memory_mb=round(mem_info.rss / (1024 * 1024), 2),
                    status=proc.status(),
                    username=_safe(proc.username),
                    create_time=create_time,
                    cmdline=_safe(proc.cmdline, default=[]) or [],
                    num_threads=_safe(proc.num_threads, default=0) or 0,
                    nice=_safe(proc.nice),
                    exe=_safe(proc.exe),
                )
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return None

    def top_consumers(
        self, by: Literal["cpu", "memory"] = "memory", limit: int = 5
    ) -> list[ProcessInfo]:
        """Convenience helper returning the heaviest processes."""
        return self.list_processes(sort_by=by, descending=True, limit=limit)


def _safe(func, default=None):
    """Call a psutil accessor, swallowing permission errors."""
    try:
        return func()
    except (psutil.AccessDenied, psutil.NoSuchProcess, Exception):  # noqa: BLE001
        return default


process_service = ProcessService()
