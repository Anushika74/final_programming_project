"""Prediction ORM model produced by the ML service."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import MetricType


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    metric_type: Mapped[MetricType] = mapped_column(Enum(MetricType), nullable=False, index=True)
    predicted_value: Mapped[float] = mapped_column(Float, nullable=False)
    # horizon in minutes the prediction targets
    horizon_minutes: Mapped[int] = mapped_column(default=10, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    model_name: Mapped[str] = mapped_column(String(64), default="unknown", nullable=False)
    prediction_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Prediction {self.metric_type}={self.predicted_value} "
            f"+{self.horizon_minutes}m>"
        )
