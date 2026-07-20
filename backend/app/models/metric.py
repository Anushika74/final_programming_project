"""System metric snapshot ORM model (time-series)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SystemMetric(Base):
    __tablename__ = "system_metrics"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    cpu_usage: Mapped[float] = mapped_column(Float, nullable=False)
    memory_usage: Mapped[float] = mapped_column(Float, nullable=False)
    disk_usage: Mapped[float] = mapped_column(Float, nullable=False)
    # Network usage stored as bytes/sec sent + received aggregate.
    network_sent: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    network_recv: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    load_avg_1m: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        Index("ix_system_metrics_timestamp_desc", timestamp.desc()),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<SystemMetric cpu={self.cpu_usage} mem={self.memory_usage} "
            f"disk={self.disk_usage} at={self.timestamp}>"
        )
