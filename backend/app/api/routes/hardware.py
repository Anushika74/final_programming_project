"""REST routes for Module 13 — Hardware Health & Thermal Intelligence."""
from __future__ import annotations

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models.alert import Alert
from app.models.enums import AlertType
from app.schemas.hardware import (
    HardwareAlertItem,
    HardwareHistory,
    HardwareMetricRead,
    HardwareOverview,
    HardwarePrediction,
    HardwareSnapshot,
    HealthScore,
    ThermalRecommendation,
    ThrottlingStatus,
)
from app.services.hardware_service import HardwareHealthService
from app.services.thermal_prediction import FORECASTABLE, ThermalPredictionService

router = APIRouter(prefix="/hardware", tags=["hardware"])


@router.get("/current", response_model=HardwareSnapshot)
def current_hardware(_: CurrentUser) -> HardwareSnapshot:
    """Live snapshot of all available hardware sensors."""
    return HardwareHealthService().get_snapshot()


@router.get("/history", response_model=HardwareHistory)
def hardware_history(
    _: CurrentUser,
    db: DbSession,
    minutes: int = Query(60, ge=1, le=60 * 24 * 30),
    limit: int = Query(500, ge=1, le=5000),
) -> HardwareHistory:
    """Historical hardware readings for charts/timelines."""
    rows = HardwareHealthService(db).get_history(minutes=minutes, limit=limit)
    return HardwareHistory(
        points=[HardwareMetricRead.model_validate(r) for r in rows],
        count=len(rows),
    )


@router.get("/health-score", response_model=HealthScore)
def health_score(_: CurrentUser) -> HealthScore:
    """Overall hardware health score with per-component breakdown."""
    service = HardwareHealthService()
    return service.compute_health_score(service.get_snapshot())


@router.get("/throttling", response_model=ThrottlingStatus)
def throttling_status(_: CurrentUser) -> ThrottlingStatus:
    """Detect whether the CPU is currently thermally throttling."""
    service = HardwareHealthService()
    return service.detect_throttling(service.get_snapshot())


@router.get("/predictions", response_model=HardwarePrediction)
def hardware_predictions(
    _: CurrentUser,
    db: DbSession,
    sensor: str = Query("cpu_package_temp", description=f"one of {sorted(FORECASTABLE)}"),
    horizon_minutes: int = Query(10, ge=5, le=120),
) -> HardwarePrediction:
    """ML temperature forecast for a sensor with overload-risk labelling."""
    return ThermalPredictionService(db).forecast(
        sensor=sensor, horizon_minutes=horizon_minutes
    )


@router.get("/recommendations", response_model=list[ThermalRecommendation])
def hardware_recommendations(_: CurrentUser, db: DbSession) -> list[ThermalRecommendation]:
    """Contextual, sensor-specific cooling/health recommendations."""
    service = HardwareHealthService(db)
    return service.generate_recommendations(service.get_snapshot())


@router.get("/alerts", response_model=list[HardwareAlertItem])
def hardware_alerts(
    _: CurrentUser,
    db: DbSession,
    limit: int = Query(50, ge=1, le=200),
    only_unresolved: bool = False,
) -> list[HardwareAlertItem]:
    """Thermal alerts (stored in the shared alert table, tagged [thermal:...])."""
    stmt = (
        select(Alert)
        .where(Alert.alert_type == AlertType.SYSTEM)
        .where(Alert.message.like("[thermal:%"))
        .order_by(Alert.created_at.desc())
    )
    if only_unresolved:
        stmt = stmt.where(Alert.resolved.is_(False))
    rows = list(db.scalars(stmt.limit(limit)))
    return [
        HardwareAlertItem(
            id=a.id,
            alert_type=a.alert_type.value,
            message=a.message,
            severity=a.severity.value,
            value=a.value,
            threshold=a.threshold,
            resolved=a.resolved,
            created_at=a.created_at,
        )
        for a in rows
    ]


@router.get("/overview", response_model=HardwareOverview)
def hardware_overview(_: CurrentUser, db: DbSession) -> HardwareOverview:
    """Consolidated payload for the Hardware Health dashboard landing view."""
    service = HardwareHealthService(db)
    snapshot = service.get_snapshot()
    return HardwareOverview(
        snapshot=snapshot,
        health=service.compute_health_score(snapshot),
        explanations=service.generate_explanations(snapshot),
        recommendations=service.generate_recommendations(snapshot),
        throttling=service.detect_throttling(snapshot),
    )
