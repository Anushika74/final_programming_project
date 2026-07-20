"""Historical metric persistence and analytics (trends, aggregation, retention)."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.metric import SystemMetric
from app.schemas.metric import MetricSnapshot, TrendPoint, TrendResponse

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Reads/writes time-series metrics and derives trends for charts."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ---- Persistence ----
    def persist_snapshot(self, snapshot: MetricSnapshot) -> SystemMetric:
        """Store a metric snapshot for historical analysis."""
        row = SystemMetric(
            cpu_usage=snapshot.cpu_usage,
            memory_usage=snapshot.memory_usage,
            disk_usage=snapshot.disk_usage,
            network_sent=snapshot.network_sent,
            network_recv=snapshot.network_recv,
            load_avg_1m=snapshot.load_avg_1m,
            timestamp=snapshot.timestamp,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def purge_old(self, retention_days: int) -> int:
        """Delete metrics older than `retention_days`. Returns rows removed."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        result = self.db.execute(
            delete(SystemMetric).where(SystemMetric.timestamp < cutoff)
        )
        self.db.commit()
        removed = result.rowcount or 0
        if removed:
            logger.info("Purged %d metric rows older than %d days", removed, retention_days)
        return removed

    # ---- Queries ----
    def get_history(self, minutes: int = 60, limit: int = 500) -> list[SystemMetric]:
        """Return raw stored metrics within the time window (newest first)."""
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        stmt = (
            select(SystemMetric)
            .where(SystemMetric.timestamp >= cutoff)
            .order_by(SystemMetric.timestamp.desc())
            .limit(limit)
        )
        rows = list(self.db.scalars(stmt))
        rows.reverse()  # chronological for charting
        return rows

    def get_recent_series(
        self, minutes: int, metric: str
    ) -> list[tuple[datetime, float]]:
        """Return (timestamp, value) tuples for a single metric column."""
        column = {
            "cpu": SystemMetric.cpu_usage,
            "memory": SystemMetric.memory_usage,
            "disk": SystemMetric.disk_usage,
            "network": SystemMetric.network_sent,
        }.get(metric, SystemMetric.cpu_usage)

        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        stmt = (
            select(SystemMetric.timestamp, column)
            .where(SystemMetric.timestamp >= cutoff)
            .order_by(SystemMetric.timestamp.asc())
        )
        return [(ts, float(val)) for ts, val in self.db.execute(stmt).all()]

    def get_trends(self, minutes: int = 60, buckets: int = 60) -> TrendResponse:
        """Down-sample stored metrics into evenly spaced time buckets.

        Implemented in Python (rather than DB-specific time_bucket SQL) so it
        works identically across SQLite, PostgreSQL and MySQL.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        stmt = (
            select(SystemMetric)
            .where(SystemMetric.timestamp >= cutoff)
            .order_by(SystemMetric.timestamp.asc())
        )
        rows = list(self.db.scalars(stmt))

        points: list[TrendPoint] = []
        if rows:
            window = timedelta(minutes=minutes) / buckets
            bucket_index: dict[int, list[SystemMetric]] = {}
            for row in rows:
                ts = _aware(row.timestamp)
                idx = int((ts - cutoff) / window)
                bucket_index.setdefault(idx, []).append(row)

            for idx in sorted(bucket_index):
                group = bucket_index[idx]
                bucket_time = cutoff + window * idx
                n = len(group)
                points.append(
                    TrendPoint(
                        bucket=bucket_time,
                        cpu_avg=round(sum(r.cpu_usage for r in group) / n, 2),
                        memory_avg=round(sum(r.memory_usage for r in group) / n, 2),
                        disk_avg=round(sum(r.disk_usage for r in group) / n, 2),
                        network_avg=round(
                            sum(r.network_sent + r.network_recv for r in group) / n, 2
                        ),
                    )
                )

        return TrendResponse(metric="all", range_minutes=minutes, points=points)

    def count(self) -> int:
        return int(self.db.scalar(select(func.count(SystemMetric.id))) or 0)

    def latest(self) -> SystemMetric | None:
        return self.db.scalar(
            select(SystemMetric).order_by(SystemMetric.timestamp.desc()).limit(1)
        )


def _aware(dt: datetime) -> datetime:
    """Ensure a datetime is timezone-aware (SQLite may return naive)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt
