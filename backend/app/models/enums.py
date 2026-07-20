"""Shared enumerations used across models and schemas."""
from __future__ import annotations

import enum


class UserRole(str, enum.Enum):
    """Role-based access control roles."""

    ADMIN = "admin"
    USER = "user"


class Severity(str, enum.Enum):
    """Severity levels for recommendations and alerts."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MetricType(str, enum.Enum):
    """Metric types used by predictions and analytics."""

    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"


class AlertType(str, enum.Enum):
    """Categories of alerts."""

    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"
    SYSTEM = "system"
