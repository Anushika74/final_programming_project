"""AI recommendation engine.

Generates human-readable, actionable recommendations by evaluating the current
metric snapshot and the heaviest processes against a set of heuristic rules.
The design is rule-based and explainable, which suits an operations context far
better than an opaque black box, while still being "AI" in the sense of
automated reasoning over system state.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import Severity
from app.models.recommendation import Recommendation
from app.schemas.metric import MetricSnapshot, ProcessInfo

logger = logging.getLogger(__name__)


@dataclass
class Insight:
    """A generated recommendation before persistence."""

    title: str
    recommendation: str
    category: str
    severity: Severity
    suggested_action: str | None = None


# Each rule receives the snapshot + top processes and returns an Insight or None.
Rule = Callable[[MetricSnapshot, list[ProcessInfo]], Insight | None]


def _rule_high_cpu(snap: MetricSnapshot, procs: list[ProcessInfo]) -> Insight | None:
    if snap.cpu_usage < 85:
        return None
    worst = procs[0].name if procs else "an application"
    sev = Severity.CRITICAL if snap.cpu_usage >= 95 else Severity.HIGH
    return Insight(
        title="High CPU usage detected",
        recommendation=(
            f"CPU usage is at {snap.cpu_usage:.0f}%. The top consumer appears to be "
            f"'{worst}'. Consider closing or throttling heavy applications, or "
            f"investigate runaway processes in the Process Explorer."
        ),
        category="cpu",
        severity=sev,
        suggested_action="analyze_startup",
    )


def _rule_high_memory(snap: MetricSnapshot, procs: list[ProcessInfo]) -> Insight | None:
    if snap.memory_usage < 85:
        return None
    worst = procs[0].name if procs else "an application"
    sev = Severity.CRITICAL if snap.memory_usage >= 95 else Severity.HIGH
    return Insight(
        title="High memory usage detected",
        recommendation=(
            f"Memory usage is at {snap.memory_usage:.0f}% "
            f"({snap.memory_used_mb:.0f} MB of {snap.memory_total_mb:.0f} MB). "
            f"'{worst}' is among the largest consumers. Close unused tabs/apps or "
            f"clear caches to free memory."
        ),
        category="memory",
        severity=sev,
        suggested_action="clear_memory_cache",
    )


def _rule_low_disk(snap: MetricSnapshot, _procs: list[ProcessInfo]) -> Insight | None:
    if snap.disk_usage < 85:
        return None
    free_gb = snap.disk_total_gb - snap.disk_used_gb
    sev = Severity.CRITICAL if snap.disk_usage >= 95 else Severity.HIGH
    return Insight(
        title="Low disk space",
        recommendation=(
            f"Disk usage is at {snap.disk_usage:.0f}% with only {free_gb:.1f} GB free. "
            f"Run the File Analyzer to find large/duplicate files and clear temporary "
            f"files to reclaim space."
        ),
        category="disk",
        severity=sev,
        suggested_action="clean_temp_files",
    )


def _rule_high_load(snap: MetricSnapshot, _procs: list[ProcessInfo]) -> Insight | None:
    if snap.cpu_count <= 0:
        return None
    ratio = snap.load_avg_1m / snap.cpu_count
    if ratio < 1.5:
        return None
    return Insight(
        title="System load is high",
        recommendation=(
            f"The 1-minute load average ({snap.load_avg_1m:.2f}) exceeds the number "
            f"of CPU cores ({snap.cpu_count}). The system is oversubscribed and may "
            f"feel sluggish. Reduce concurrent workloads."
        ),
        category="cpu",
        severity=Severity.MEDIUM,
    )


def _rule_heavy_process(snap: MetricSnapshot, procs: list[ProcessInfo]) -> Insight | None:
    for proc in procs:
        if proc.memory_usage >= 25 or proc.cpu_usage >= 50:
            return Insight(
                title="Resource-heavy application",
                recommendation=(
                    f"'{proc.name}' (PID {proc.pid}) is using "
                    f"{proc.cpu_usage:.0f}% CPU and {proc.memory_usage:.0f}% memory. "
                    f"If it is not essential right now, consider closing it."
                ),
                category="process",
                severity=Severity.LOW,
            )
    return None


RULES: list[Rule] = [
    _rule_high_cpu,
    _rule_high_memory,
    _rule_low_disk,
    _rule_high_load,
    _rule_heavy_process,
]


class RecommendationService:
    """Generates, persists and queries recommendations."""

    # Avoid spamming duplicate recommendations within this window.
    DEDUP_WINDOW = timedelta(minutes=10)

    def __init__(self, db: Session) -> None:
        self.db = db

    def evaluate(
        self, snapshot: MetricSnapshot, processes: list[ProcessInfo]
    ) -> list[Insight]:
        """Run all rules and return triggered insights."""
        insights: list[Insight] = []
        for rule in RULES:
            try:
                result = rule(snapshot, processes)
            except Exception as exc:  # noqa: BLE001 - one bad rule shouldn't kill all
                logger.warning("Recommendation rule %s failed: %s", rule.__name__, exc)
                result = None
            if result is not None:
                insights.append(result)
        return insights

    def generate_and_store(
        self, snapshot: MetricSnapshot, processes: list[ProcessInfo]
    ) -> list[Recommendation]:
        """Evaluate rules and persist new, non-duplicate recommendations."""
        insights = self.evaluate(snapshot, processes)
        stored: list[Recommendation] = []
        for insight in insights:
            if self._recently_seen(insight.title):
                continue
            rec = Recommendation(
                title=insight.title,
                recommendation=insight.recommendation,
                category=insight.category,
                severity=insight.severity,
                suggested_action=insight.suggested_action,
            )
            self.db.add(rec)
            stored.append(rec)
        if stored:
            self.db.commit()
            for rec in stored:
                self.db.refresh(rec)
            logger.info("Stored %d new recommendation(s)", len(stored))
        return stored

    def _recently_seen(self, title: str) -> bool:
        cutoff = datetime.now(timezone.utc) - self.DEDUP_WINDOW
        stmt = (
            select(Recommendation)
            .where(Recommendation.title == title)
            .where(Recommendation.created_at >= cutoff)
            .limit(1)
        )
        return self.db.scalar(stmt) is not None

    def list_recommendations(
        self, limit: int = 50, only_unacknowledged: bool = False
    ) -> list[Recommendation]:
        stmt = select(Recommendation).order_by(Recommendation.created_at.desc())
        if only_unacknowledged:
            stmt = stmt.where(Recommendation.acknowledged.is_(False))
        return list(self.db.scalars(stmt.limit(limit)))

    def acknowledge(self, rec_id: int) -> Recommendation | None:
        rec = self.db.get(Recommendation, rec_id)
        if rec is None:
            return None
        rec.acknowledged = True
        self.db.commit()
        self.db.refresh(rec)
        return rec
