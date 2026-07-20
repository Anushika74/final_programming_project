"""The consolidated System Context object.

`SystemContext` is the single, normalized snapshot of *everything* the AI
Assistant needs: live software metrics, hardware sensors, health score, history,
top processes, predictions, recommendations, alerts and recent logs. The
SystemContextService builds it; the assistant reasons over it. It is also
JSON-serializable, so it can be handed straight to an LLM prompt builder later.
"""
from __future__ import annotations

from datetime import datetime
from typing import List

from pydantic import BaseModel


class TopProcess(BaseModel):
    pid: int
    name: str
    cpu_usage: float
    memory_usage: float
    memory_mb: float


class PredictionBrief(BaseModel):
    metric: str
    current: float | None = None
    predicted_peak: float | None = None
    risk: str = "low"
    message: str = ""


class RecommendationBrief(BaseModel):
    issue: str
    severity: str
    detail: str = ""


class AlertBrief(BaseModel):
    type: str
    message: str
    severity: str


class LogBrief(BaseModel):
    severity: str
    category: str
    explanation: str


class ComponentHealthBrief(BaseModel):
    name: str
    score: float
    status: str
    detail: str


class SystemContext(BaseModel):
    """One object describing the whole system state for the assistant."""

    timestamp: datetime

    # --- Software metrics ---
    cpu_usage: float | None = None
    memory_usage: float | None = None
    disk_usage: float | None = None
    network_recv_kbps: float | None = None
    network_sent_kbps: float | None = None
    load_avg_1m: float | None = None
    cpu_count: int | None = None
    cpu_frequency_mhz: float | None = None
    uptime_hours: float | None = None

    # --- Hardware sensors ---
    cpu_temp: float | None = None
    cpu_core_temps: List[float] = []
    gpu_temp: float | None = None
    ssd_temp: float | None = None
    hdd_temp: float | None = None
    motherboard_temp: float | None = None
    fan_speed_rpm: float | None = None
    battery_temp: float | None = None
    battery_health: float | None = None
    battery_percent: float | None = None
    battery_status: str | None = None
    sensor_source: str | None = None
    available_sensors: List[str] = []

    # --- Health & thermal intelligence ---
    health_overall: float | None = None
    health_rating: str | None = None
    health_components: List[ComponentHealthBrief] = []
    throttling: bool = False
    throttling_message: str = ""

    # --- Short-term history (last hour) ---
    cpu_avg_1h: float | None = None
    memory_avg_1h: float | None = None
    cpu_temp_avg_1h: float | None = None
    sustained_high_cpu_temp: bool = False

    # --- Derived collections ---
    top_cpu: List[TopProcess] = []
    top_memory: List[TopProcess] = []
    predictions: List[PredictionBrief] = []
    recommendations: List[RecommendationBrief] = []
    alerts: List[AlertBrief] = []
    recent_logs: List[LogBrief] = []

    # Which modules actually contributed (for transparency in the UI).
    sources: List[str] = []
