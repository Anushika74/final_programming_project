"""Thermal predictive analytics.

Forecasts future sensor temperatures using the shared scikit-learn
`ShortHorizonForecaster`. If a pre-trained model has been saved to disk
(see app/ml/train_thermal.py) it is loaded and used; otherwise a model is
trained on the fly from recent history. This mirrors a real ML pipeline:
collect data -> train offline -> persist with joblib -> serve predictions.
"""
from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.ml.forecaster import ShortHorizonForecaster
from app.schemas.hardware import HardwareForecastPoint, HardwarePrediction
from app.services.hardware_service import (
    CPU_CRITICAL,
    CPU_WARNING,
    HardwareHealthService,
)

logger = logging.getLogger(__name__)

# Sensors that can be forecast, mapped to their DB column.
FORECASTABLE = {
    "cpu_package_temp": "cpu_package_temp",
    "ssd_temp": "ssd_temp",
    "battery_temp": "battery_temp",
    "gpu_temp": "gpu_temp",
}

# Per-sensor warning/critical bands for risk labelling.
_RISK_BANDS = {
    "cpu_package_temp": (CPU_WARNING, CPU_CRITICAL),
    "gpu_temp": (85.0, 95.0),
    "ssd_temp": (70.0, 80.0),
    "battery_temp": (45.0, 55.0),
}


def _model_path(sensor: str) -> Path:
    return Path(settings.ML_MODEL_DIR) / f"thermal_{sensor}.joblib"


def _risk_for(sensor: str, peak: float) -> str:
    warn, crit = _RISK_BANDS.get(sensor, (85.0, 95.0))
    if peak >= crit:
        return "high"
    if peak >= warn:
        return "medium"
    return "low"


class ThermalPredictionService:
    """Generates temperature forecasts for hardware sensors."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.hardware = HardwareHealthService(db)

    def forecast(
        self,
        sensor: str = "cpu_package_temp",
        history_minutes: int = 180,
        horizon_minutes: int = 10,
        step_minutes: int = 5,
    ) -> HardwarePrediction:
        if sensor not in FORECASTABLE:
            sensor = "cpu_package_temp"
        column = FORECASTABLE[sensor]

        series = self.hardware.get_series(history_minutes, column)
        values = [v for _, v in series]
        current = values[-1] if values else None

        forecaster = ShortHorizonForecaster(lags=5, model_name="random_forest")
        loaded = forecaster.load(_model_path(sensor))
        trained = loaded
        if not loaded and len(values) >= settings.ML_MIN_TRAINING_SAMPLES:
            trained = forecaster.fit(values)

        steps = max(1, horizon_minutes // step_minutes)
        result = forecaster.forecast(values, steps=steps)

        points = [
            HardwareForecastPoint(minutes_ahead=(i + 1) * step_minutes, value=val)
            for i, val in enumerate(result.horizon_values)
        ]
        peak = max(result.horizon_values) if result.horizon_values else (current or 0.0)
        risk = _risk_for(sensor, peak)
        message = self._message(sensor, peak, horizon_minutes, risk, trained, current)

        return HardwarePrediction(
            sensor=sensor,
            model_name=result.model_name if trained else "persistence",
            confidence=result.confidence,
            current_value=round(current, 1) if current is not None else None,
            points=points,
            risk=risk,
            message=message,
        )

    @staticmethod
    def _message(
        sensor: str,
        peak: float,
        horizon_minutes: int,
        risk: str,
        trained: bool,
        current: float | None,
    ) -> str:
        label = sensor.replace("_", " ").replace("temp", "temperature").upper()
        if current is None:
            return f"No data yet for {label}. Let the monitor run to collect readings."
        if not trained:
            return (
                f"Not enough history to train a reliable model for {label} yet "
                f"(need ~{settings.ML_MIN_TRAINING_SAMPLES} readings). Showing a naive "
                "estimate; collect more data for accurate forecasts."
            )
        if risk == "high":
            return (
                f"{label} is predicted to reach about {peak:.0f}°C within "
                f"{horizon_minutes} minutes — a high overheating risk. Take action now."
            )
        if risk == "medium":
            return (
                f"{label} may rise to around {peak:.0f}°C within {horizon_minutes} "
                "minutes. Monitor closely."
            )
        return (
            f"{label} is expected to stay around {peak:.0f}°C over the next "
            f"{horizon_minutes} minutes — no overheating risk."
        )
