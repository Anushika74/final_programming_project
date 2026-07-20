"""Prediction service: trains forecasters on stored metrics and produces
forecasts plus overload-risk indicators.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.ml.forecaster import ShortHorizonForecaster, TrendForecaster
from app.models.enums import MetricType
from app.models.prediction import Prediction
from app.schemas.insight import ForecastPoint, ForecastResponse
from app.services.analytics_service import AnalyticsService

logger = logging.getLogger(__name__)

# Risk thresholds applied to forecast peaks (percentage metrics).
_RISK_HIGH = 90.0
_RISK_MEDIUM = 75.0


def _resource_model_path(metric: str) -> Path:
    """Path to a persisted resource model (see app/ml/train_resources.py)."""
    return Path(settings.ML_MODEL_DIR) / f"resource_{metric}.joblib"


class PredictionService:
    """Generates ML forecasts for CPU, memory and disk usage."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.analytics = AnalyticsService(db)

    def _risk_for(self, peak: float) -> str:
        if peak >= _RISK_HIGH:
            return "high"
        if peak >= _RISK_MEDIUM:
            return "medium"
        return "low"

    def forecast_short(
        self,
        metric_type: MetricType,
        history_minutes: int = 180,
        horizon_minutes: int = 10,
        step_minutes: int = 1,
        model_name: str = "random_forest",
    ) -> ForecastResponse:
        """Forecast CPU or memory for the next `horizon_minutes`."""
        series = self.analytics.get_recent_series(history_minutes, metric_type.value)
        values = [v for _, v in series]

        forecaster = ShortHorizonForecaster(lags=5, model_name=model_name)
        # Prefer a pre-trained, persisted model; otherwise train on the fly.
        loaded = forecaster.load(_resource_model_path(metric_type.value))
        if loaded:
            trained = True
        elif len(values) >= settings.ML_MIN_TRAINING_SAMPLES:
            trained = forecaster.fit(values)
        else:
            trained = False
        steps = max(1, horizon_minutes // step_minutes)
        result = forecaster.forecast(values, steps=steps)

        points = [
            ForecastPoint(minutes_ahead=(i + 1) * step_minutes, value=val)
            for i, val in enumerate(result.horizon_values)
        ]
        peak = max(result.horizon_values) if result.horizon_values else result.current_value
        risk = self._risk_for(peak)
        message = self._build_message(metric_type, peak, horizon_minutes, risk, trained)

        # Persist the headline prediction (the horizon peak).
        self._store_prediction(metric_type, peak, horizon_minutes, result.confidence, result.model_name)

        return ForecastResponse(
            metric_type=metric_type,
            model_name=result.model_name,
            confidence=result.confidence,
            current_value=round(result.current_value, 2),
            points=points,
            risk=risk,
            message=message,
        )

    def forecast_disk(
        self, history_minutes: int = 60 * 24 * 7, horizon_days: int = 7
    ) -> ForecastResponse:
        """Forecast disk usage `horizon_days` ahead via linear trend."""
        series = self.analytics.get_recent_series(history_minutes, "disk")
        timestamps = [ts for ts, _ in series]
        values = [v for _, v in series]

        forecaster = TrendForecaster()
        horizon_minutes = horizon_days * 24 * 60
        result = forecaster.fit_predict(timestamps, values, horizon_minutes)

        predicted = result.horizon_values[0] if result.horizon_values else result.current_value
        risk = self._risk_for(predicted)

        if predicted >= 95:
            message = (
                f"Disk space may become critically low within {horizon_days} days "
                f"(projected {predicted:.0f}% usage)."
            )
        elif predicted >= 85:
            message = (
                f"Disk usage is trending upward and may reach {predicted:.0f}% "
                f"within {horizon_days} days. Plan a cleanup."
            )
        else:
            message = (
                f"Disk usage is projected at {predicted:.0f}% in {horizon_days} days "
                f"— no immediate concern."
            )

        self._store_prediction(
            MetricType.DISK, predicted, horizon_minutes, result.confidence, result.model_name
        )

        return ForecastResponse(
            metric_type=MetricType.DISK,
            model_name=result.model_name,
            confidence=result.confidence,
            current_value=round(result.current_value, 2),
            points=[ForecastPoint(minutes_ahead=horizon_minutes, value=predicted)],
            risk=risk,
            message=message,
        )

    def _build_message(
        self,
        metric_type: MetricType,
        peak: float,
        horizon_minutes: int,
        risk: str,
        trained: bool,
    ) -> str:
        label = metric_type.value.upper()
        if not trained:
            return (
                f"Not enough history yet to train a reliable {label} model "
                f"(need ~{settings.ML_MIN_TRAINING_SAMPLES} samples). Showing a naive "
                f"estimate; collect more data for accurate forecasts."
            )
        if risk == "high":
            return (
                f"{label} usage is likely to exceed {peak:.0f}% within "
                f"{horizon_minutes} minutes. Consider acting now."
            )
        if risk == "medium":
            return (
                f"{label} usage may rise to around {peak:.0f}% within "
                f"{horizon_minutes} minutes."
            )
        return (
            f"{label} usage is expected to stay around {peak:.0f}% over the next "
            f"{horizon_minutes} minutes."
        )

    def _store_prediction(
        self,
        metric_type: MetricType,
        value: float,
        horizon_minutes: int,
        confidence: float,
        model_name: str,
    ) -> None:
        record = Prediction(
            metric_type=metric_type,
            predicted_value=round(value, 2),
            horizon_minutes=horizon_minutes,
            confidence=confidence,
            model_name=model_name,
            prediction_time=datetime.now(timezone.utc),
        )
        self.db.add(record)
        self.db.commit()

    def recent_predictions(self, limit: int = 50) -> list[Prediction]:
        stmt = select(Prediction).order_by(Prediction.prediction_time.desc()).limit(limit)
        return list(self.db.scalars(stmt))
