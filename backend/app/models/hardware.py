"""Hardware metric snapshot ORM model (time-series, nullable sensors)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class HardwareMetric(Base):
    """A stored hardware/thermal reading. Unavailable sensors are NULL."""

    __tablename__ = "hardware_metrics"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # CPU thermal & frequency
    cpu_package_temp: Mapped[float | None] = mapped_column(Float, nullable=True)
    cpu_core_1_temp: Mapped[float | None] = mapped_column(Float, nullable=True)
    cpu_core_2_temp: Mapped[float | None] = mapped_column(Float, nullable=True)
    cpu_core_3_temp: Mapped[float | None] = mapped_column(Float, nullable=True)
    cpu_core_4_temp: Mapped[float | None] = mapped_column(Float, nullable=True)
    cpu_frequency: Mapped[float | None] = mapped_column(Float, nullable=True)
    cpu_utilization: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Other components
    gpu_temp: Mapped[float | None] = mapped_column(Float, nullable=True)
    motherboard_temp: Mapped[float | None] = mapped_column(Float, nullable=True)
    ssd_temp: Mapped[float | None] = mapped_column(Float, nullable=True)
    hdd_temp: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Cooling
    fan_speed: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Battery
    battery_temp: Mapped[float | None] = mapped_column(Float, nullable=True)
    battery_health: Mapped[float | None] = mapped_column(Float, nullable=True)
    battery_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    battery_status: Mapped[str | None] = mapped_column(String(32), nullable=True)

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<HardwareMetric cpu={self.cpu_package_temp}C at={self.timestamp}>"
