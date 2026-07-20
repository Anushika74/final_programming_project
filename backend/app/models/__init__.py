"""ORM models package.

Importing this package registers every model on the shared metadata, which is
required before `Base.metadata.create_all()` or Alembic autogeneration.
"""
from app.models.alert import Alert
from app.models.enums import AlertType, MetricType, Severity, UserRole
from app.models.hardware import HardwareMetric
from app.models.log import LogEntry
from app.models.metric import SystemMetric
from app.models.prediction import Prediction
from app.models.process import ProcessSnapshot
from app.models.recommendation import Recommendation
from app.models.user import User

__all__ = [
    "Alert",
    "AlertType",
    "HardwareMetric",
    "LogEntry",
    "MetricType",
    "Prediction",
    "ProcessSnapshot",
    "Recommendation",
    "Severity",
    "SystemMetric",
    "User",
    "UserRole",
]
