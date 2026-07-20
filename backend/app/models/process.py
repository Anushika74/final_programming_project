"""Process snapshot ORM model."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ProcessSnapshot(Base):
    __tablename__ = "processes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    process_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    pid: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    cpu_usage: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    memory_usage: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="unknown", nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ProcessSnapshot pid={self.pid} name={self.process_name!r}>"
