"""Dashboard summary route aggregating key system state in one call."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.api.websocket import manager
from app.services.alert_service import AlertService
from app.services.analytics_service import AnalyticsService
from app.services.monitoring_service import monitoring_service
from app.services.process_service import process_service
from app.services.recommendation_service import RecommendationService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def dashboard_summary(_: CurrentUser, db: DbSession) -> dict[str, Any]:
    """Return a consolidated snapshot for the dashboard landing page."""
    snapshot = monitoring_service.collect()
    top_cpu = process_service.top_consumers(by="cpu", limit=5)
    top_mem = process_service.top_consumers(by="memory", limit=5)

    alerts = AlertService(db).list_alerts(limit=5, only_unresolved=True)
    recs = RecommendationService(db).list_recommendations(limit=5, only_unacknowledged=True)
    metric_count = AnalyticsService(db).count()

    return {
        "metrics": snapshot.model_dump(mode="json"),
        "top_cpu": [p.model_dump(mode="json") for p in top_cpu],
        "top_memory": [p.model_dump(mode="json") for p in top_mem],
        "active_alerts": [
            {
                "id": a.id,
                "type": a.alert_type.value,
                "message": a.message,
                "severity": a.severity.value,
            }
            for a in alerts
        ],
        "recommendations": [
            {
                "id": r.id,
                "title": r.title,
                "severity": r.severity.value,
                "recommendation": r.recommendation,
            }
            for r in recs
        ],
        "stats": {
            "stored_metric_points": metric_count,
            "websocket_clients": manager.active_count,
        },
    }
