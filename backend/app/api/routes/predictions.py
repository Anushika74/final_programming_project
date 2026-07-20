"""REST routes for ML predictions / forecasting."""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.models.enums import MetricType
from app.schemas.insight import ForecastResponse, PredictionRead
from app.services.prediction_service import PredictionService

router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.get("/forecast", response_model=ForecastResponse)
def forecast(
    _: CurrentUser,
    db: DbSession,
    metric: MetricType = MetricType.CPU,
    horizon_minutes: int = Query(10, ge=1, le=120),
) -> ForecastResponse:
    """Forecast a metric. CPU/memory/network use the short-horizon model;
    disk uses a multi-day linear trend (horizon interpreted as days)."""
    service = PredictionService(db)
    if metric == MetricType.DISK:
        return service.forecast_disk(horizon_days=max(1, horizon_minutes))
    return service.forecast_short(metric_type=metric, horizon_minutes=horizon_minutes)


@router.get("/disk", response_model=ForecastResponse)
def forecast_disk(
    _: CurrentUser,
    db: DbSession,
    horizon_days: int = Query(7, ge=1, le=90),
) -> ForecastResponse:
    """Forecast disk growth over the coming days."""
    return PredictionService(db).forecast_disk(horizon_days=horizon_days)


@router.get("/history", response_model=list[PredictionRead])
def prediction_history(
    _: CurrentUser,
    db: DbSession,
    limit: int = Query(50, ge=1, le=200),
) -> list[PredictionRead]:
    preds = PredictionService(db).recent_predictions(limit=limit)
    return [PredictionRead.model_validate(p) for p in preds]
