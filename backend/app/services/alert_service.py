"""Alert service: threshold evaluation, persistence and notification dispatch."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.alert import Alert
from app.models.enums import AlertType, Severity
from app.schemas.metric import MetricSnapshot
from app.services import notifications

logger = logging.getLogger(__name__)


class AlertService:
    """Detects threshold breaches and raises (de-duplicated) alerts."""

    # Don't re-raise the same alert type within this window.
    DEDUP_WINDOW = timedelta(minutes=5)

    def __init__(self, db: Session) -> None:
        self.db = db

    def check_snapshot(
        self, snapshot: MetricSnapshot, notify: bool = True
    ) -> list[Alert]:
        """Evaluate a snapshot against configured thresholds and raise alerts."""
        raised: list[Alert] = []

        checks = [
            (AlertType.CPU, snapshot.cpu_usage, settings.ALERT_CPU_THRESHOLD, "CPU"),
            (AlertType.MEMORY, snapshot.memory_usage, settings.ALERT_MEMORY_THRESHOLD, "Memory"),
            (AlertType.DISK, snapshot.disk_usage, settings.ALERT_DISK_THRESHOLD, "Disk"),
        ]

        for alert_type, value, threshold, label in checks:
            if value < threshold:
                continue
            if self._recently_raised(alert_type):
                continue
            severity = Severity.CRITICAL if value >= threshold + 5 else Severity.HIGH
            message = (
                f"{label} usage is {value:.0f}%, exceeding the {threshold:.0f}% "
                f"threshold."
            )
            alert = Alert(
                alert_type=alert_type,
                message=message,
                severity=severity,
                value=value,
                threshold=threshold,
            )
            self.db.add(alert)
            self.db.commit()
            self.db.refresh(alert)
            raised.append(alert)

            if notify:
                results = notifications.dispatch(f"{settings.APP_NAME} alert", message)
                alert.notified = any(results.values())
                self.db.commit()

        if raised:
            logger.info("Raised %d alert(s)", len(raised))
        return raised

    def _recently_raised(self, alert_type: AlertType) -> bool:
        cutoff = datetime.now(timezone.utc) - self.DEDUP_WINDOW
        stmt = (
            select(Alert)
            .where(Alert.alert_type == alert_type)
            .where(Alert.created_at >= cutoff)
            .where(Alert.resolved.is_(False))
            .limit(1)
        )
        return self.db.scalar(stmt) is not None

    def list_alerts(self, limit: int = 50, only_unresolved: bool = False) -> list[Alert]:
        stmt = select(Alert).order_by(Alert.created_at.desc())
        if only_unresolved:
            stmt = stmt.where(Alert.resolved.is_(False))
        return list(self.db.scalars(stmt.limit(limit)))

    def resolve(self, alert_id: int) -> Alert | None:
        alert = self.db.get(Alert, alert_id)
        if alert is None:
            return None
        alert.resolved = True
        self.db.commit()
        self.db.refresh(alert)
        return alert
