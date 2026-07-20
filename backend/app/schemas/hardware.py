"""Pydantic schemas for the Hardware Health & Thermal Intelligence module."""
from __future__ import annotations

from datetime import datetime
from typing import List

from pydantic import BaseModel, ConfigDict


class HardwareSnapshot(BaseModel):
    """Live hardware reading pushed over WebSocket / returned by REST."""

    cpu_package_temp: float | None = None
    cpu_core_temps: List[float] = []
    cpu_frequency_mhz: float | None = None
    cpu_frequency_max_mhz: float | None = None
    cpu_utilization: float | None = None
    gpu_temp: float | None = None
    motherboard_temp: float | None = None
    ssd_temp: float | None = None
    hdd_temp: float | None = None
    fan_speed_rpm: float | None = None
    battery_temp: float | None = None
    battery_health: float | None = None
    battery_percent: float | None = None
    battery_status: str | None = None
    available_sensors: List[str] = []
    source: str = "unknown"
    timestamp: datetime


class HardwareMetricRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cpu_package_temp: float | None
    cpu_frequency: float | None
    cpu_utilization: float | None
    gpu_temp: float | None
    ssd_temp: float | None
    battery_temp: float | None
    fan_speed: float | None
    timestamp: datetime


class HardwareHistory(BaseModel):
    points: List[HardwareMetricRead]
    count: int


class ComponentHealth(BaseModel):
    name: str
    score: float
    status: str          # excellent | good | fair | poor
    detail: str


class HealthScore(BaseModel):
    overall: float
    rating: str
    components: List[ComponentHealth]


class ThermalExplanation(BaseModel):
    """An AI-generated, human-readable explanation of a thermal condition."""

    title: str
    level: str           # normal | warning | critical | emergency
    metric: str
    value: float | None
    explanation: str


class ThermalRecommendation(BaseModel):
    issue: str
    severity: str
    actions: List[str]


class ThrottlingStatus(BaseModel):
    throttling: bool
    message: str
    cpu_utilization: float | None = None
    cpu_frequency: float | None = None
    cpu_frequency_max: float | None = None
    cpu_temp: float | None = None


class HardwareForecastPoint(BaseModel):
    minutes_ahead: int
    value: float


class HardwarePrediction(BaseModel):
    sensor: str          # e.g. cpu_package_temp, ssd_temp, battery_temp
    model_name: str
    confidence: float
    current_value: float | None
    points: List[HardwareForecastPoint]
    risk: str
    message: str


class HardwareAlertItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    alert_type: str
    message: str
    severity: str
    value: float
    threshold: float
    resolved: bool
    created_at: datetime


class HardwareOverview(BaseModel):
    """Everything the Hardware Health dashboard needs in one call."""

    snapshot: HardwareSnapshot
    health: HealthScore
    explanations: List[ThermalExplanation]
    recommendations: List[ThermalRecommendation]
    throttling: ThrottlingStatus
