"""System metric & process Pydantic schemas."""
from __future__ import annotations

from datetime import datetime
from typing import List

from pydantic import BaseModel, ConfigDict


class MetricSnapshot(BaseModel):
    """Live metric payload pushed over the WebSocket / returned by REST."""

    cpu_usage: float
    memory_usage: float
    memory_total_mb: float
    memory_used_mb: float
    disk_usage: float
    disk_total_gb: float
    disk_used_gb: float
    network_sent: float
    network_recv: float
    network_sent_total_mb: float
    network_recv_total_mb: float
    load_avg_1m: float
    load_avg_5m: float
    load_avg_15m: float
    cpu_count: int
    uptime_seconds: float
    boot_time: datetime
    timestamp: datetime


class MetricRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    network_sent: float
    network_recv: float
    load_avg_1m: float
    timestamp: datetime


class MetricHistory(BaseModel):
    points: List[MetricRead]
    count: int


class TrendPoint(BaseModel):
    bucket: datetime
    cpu_avg: float
    memory_avg: float
    disk_avg: float
    network_avg: float


class TrendResponse(BaseModel):
    metric: str
    range_minutes: int
    points: List[TrendPoint]


class ProcessInfo(BaseModel):
    pid: int
    name: str
    cpu_usage: float
    memory_usage: float
    memory_mb: float
    status: str
    username: str | None = None
    create_time: datetime | None = None


class ProcessDetail(ProcessInfo):
    cmdline: List[str] = []
    num_threads: int = 0
    nice: int | None = None
    exe: str | None = None
