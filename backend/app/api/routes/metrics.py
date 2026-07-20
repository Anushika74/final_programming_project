"""REST routes for current metrics and historical analytics."""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.schemas.metric import (
    MetricHistory,
    MetricRead,
    MetricSnapshot,
    TrendResponse,
)
from app.services.analytics_service import AnalyticsService
from app.services.monitoring_service import monitoring_service

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/current", response_model=MetricSnapshot)
def current_metrics(_: CurrentUser) -> MetricSnapshot:
    """Return a live snapshot of system metrics."""
    return monitoring_service.collect()


@router.get("/history", response_model=MetricHistory)
def metric_history(
    _: CurrentUser,
    db: DbSession,
    minutes: int = Query(60, ge=1, le=60 * 24 * 30),
    limit: int = Query(500, ge=1, le=5000),
) -> MetricHistory:
    """Return raw stored metric points within the last `minutes`."""
    points = AnalyticsService(db).get_history(minutes=minutes, limit=limit)
    return MetricHistory(
        points=[MetricRead.model_validate(p) for p in points],
        count=len(points),
    )


@router.get("/trends", response_model=TrendResponse)
def metric_trends(
    _: CurrentUser,
    db: DbSession,
    minutes: int = Query(60, ge=5, le=60 * 24 * 30),
    buckets: int = Query(60, ge=5, le=500),
) -> TrendResponse:
    """Return down-sampled, time-bucketed averages suitable for charts."""
    return AnalyticsService(db).get_trends(minutes=minutes, buckets=buckets)
