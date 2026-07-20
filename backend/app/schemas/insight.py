"""Schemas for recommendations, predictions, alerts, logs, files & NL assistant."""
from __future__ import annotations

from datetime import datetime
from typing import Any, List

from pydantic import BaseModel, ConfigDict

from app.models.enums import AlertType, MetricType, Severity


# ---- Recommendations ----
class RecommendationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    recommendation: str
    category: str
    severity: Severity
    suggested_action: str | None
    acknowledged: bool
    created_at: datetime


# ---- Predictions ----
class PredictionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    metric_type: MetricType
    predicted_value: float
    horizon_minutes: int
    confidence: float
    model_name: str
    prediction_time: datetime


class ForecastPoint(BaseModel):
    minutes_ahead: int
    value: float


class ForecastResponse(BaseModel):
    metric_type: MetricType
    model_name: str
    confidence: float
    current_value: float
    points: List[ForecastPoint]
    risk: str
    message: str


# ---- Alerts ----
class AlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    alert_type: AlertType
    message: str
    severity: Severity
    value: float
    threshold: float
    resolved: bool
    created_at: datetime


# ---- Logs ----
class LogAnalyzeRequest(BaseModel):
    source: str = "manual"
    content: str


class LogEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # id and created_at are only populated for persisted (notable) entries.
    # INFO-level lines are analyzed and returned but not saved, so these stay None.
    id: int | None = None
    source: str
    raw_log: str
    explanation: str
    category: str
    severity: Severity
    created_at: datetime | None = None


class LogAnalysisSummary(BaseModel):
    total: int
    by_severity: dict[str, int]
    entries: List[LogEntryRead]


# ---- File analyzer ----
class FileScanRequest(BaseModel):
    path: str
    min_large_file_mb: float = 100.0
    find_duplicates: bool = True
    max_depth: int | None = None


class FileInfo(BaseModel):
    path: str
    size_bytes: int
    size_human: str


class DuplicateGroup(BaseModel):
    hash: str
    size_bytes: int
    files: List[str]
    wasted_bytes: int


class FileScanResult(BaseModel):
    root: str
    scanned_files: int
    total_size_bytes: int
    large_files: List[FileInfo]
    temp_files: List[FileInfo]
    empty_folders: List[str]
    duplicate_groups: List[DuplicateGroup]
    reclaimable_bytes: int
    recommendations: List[str]


# ---- Optimization ----
class OptimizationAction(BaseModel):
    key: str
    title: str
    description: str
    risk: str
    requires_confirmation: bool = True
    estimated_impact: str | None = None


class OptimizationRequest(BaseModel):
    action_key: str
    confirm: bool = False
    dry_run: bool = True


class OptimizationResult(BaseModel):
    action_key: str
    executed: bool
    dry_run: bool
    message: str
    details: dict[str, Any] = {}


# ---- NL assistant ----
class AssistantQuery(BaseModel):
    query: str


class AssistantResponse(BaseModel):
    query: str
    intent: str
    answer: str
    data: dict[str, Any] = {}
    suggested_actions: List[OptimizationAction] = []
    # Which subsystems the assistant consulted to build the answer.
    sources: List[str] = []
