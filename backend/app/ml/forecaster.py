"""Time-series forecasting for system metrics using scikit-learn.

Two complementary strategies are provided:

1. **Short-horizon forecasting** (CPU / memory, next N minutes):
   A supervised lag-feature model. We build a sliding window of the last `k`
   observations to predict the next value, then forecast iteratively. A
   ``RandomForestRegressor`` is used by default (captures non-linear behaviour);
   it degrades gracefully to a simple persistence model when data is scarce.

2. **Long-horizon trend forecasting** (disk growth, days ahead):
   A ``LinearRegression`` fit on elapsed-time -> usage, extrapolated forward.
   Suitable for slow, near-monotonic growth such as disk consumption.

Models can be persisted to / loaded from disk via joblib.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Sequence

import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

logger = logging.getLogger(__name__)


@dataclass
class ForecastResult:
    """Output of a forecasting run."""

    model_name: str
    confidence: float
    current_value: float
    horizon_values: list[float] = field(default_factory=list)


@dataclass
class EvaluationResult:
    """Hold-out accuracy metrics from a chronological train/test split."""

    model_name: str
    n_train: int
    n_test: int
    mae: float          # mean absolute error (same units as the metric)
    rmse: float         # root mean squared error
    r2: float           # coefficient of determination (1.0 = perfect)
    mape: float         # mean absolute percentage error (%)

    def as_dict(self) -> dict[str, float | int | str]:
        return {
            "model": self.model_name,
            "n_train": self.n_train,
            "n_test": self.n_test,
            "mae": round(self.mae, 3),
            "rmse": round(self.rmse, 3),
            "r2": round(self.r2, 3),
            "mape_pct": round(self.mape, 2),
        }


class ShortHorizonForecaster:
    """Lag-feature supervised forecaster for short-term metric prediction."""

    def __init__(self, lags: int = 5, model_name: str = "random_forest") -> None:
        self.lags = lags
        self.model_name = model_name
        self.model: RandomForestRegressor | LinearRegression | None = None
        self._confidence = 0.0

    def _make_model(self) -> RandomForestRegressor | LinearRegression:
        """Instantiate a fresh estimator according to `model_name`."""
        if self.model_name == "linear":
            return LinearRegression()
        return RandomForestRegressor(
            n_estimators=120, max_depth=8, random_state=42, n_jobs=-1
        )

    def _build_supervised(self, values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Create (X, y) lag matrices from a 1-D series."""
        x_rows, y_rows = [], []
        for i in range(self.lags, len(values)):
            x_rows.append(values[i - self.lags : i])
            y_rows.append(values[i])
        return np.asarray(x_rows), np.asarray(y_rows)

    def fit(self, values: Sequence[float]) -> bool:
        """Train the model. Returns False if there is insufficient data."""
        arr = np.asarray(values, dtype=float)
        if len(arr) < self.lags + 5:
            self.model = None
            return False

        x, y = self._build_supervised(arr)
        model = self._make_model()
        model.fit(x, y)

        # In-sample R^2 as a rough confidence proxy (clamped to [0, 1]).
        preds = model.predict(x)
        self._confidence = float(max(0.0, min(1.0, r2_score(y, preds))))
        self.model = model
        return True

    def evaluate(
        self, values: Sequence[float], test_fraction: float = 0.2
    ) -> EvaluationResult | None:
        """Evaluate accuracy with a **chronological** hold-out split.

        Time-series data must not be shuffled, so we train on the earliest
        ``(1 - test_fraction)`` of the windows and test on the most recent
        ``test_fraction``. Each test prediction uses the *actual* preceding
        observations as features (one-step-ahead evaluation), which is the
        standard, honest way to score a short-horizon forecaster.

        Returns None if there is not enough data to form a meaningful split.
        """
        arr = np.asarray(values, dtype=float)
        if len(arr) < self.lags + 10:
            return None

        x, y = self._build_supervised(arr)
        n = len(x)
        split = int(n * (1.0 - test_fraction))
        if split < 1 or split >= n:
            return None

        x_train, y_train = x[:split], y[:split]
        x_test, y_test = x[split:], y[split:]

        model = self._make_model()
        model.fit(x_train, y_train)
        preds = model.predict(x_test)

        mae = float(mean_absolute_error(y_test, preds))
        rmse = float(np.sqrt(mean_squared_error(y_test, preds)))
        r2 = float(r2_score(y_test, preds)) if len(np.unique(y_test)) > 1 else 0.0

        # MAPE, guarding against division by zero.
        nonzero = np.abs(y_test) > 1e-6
        if nonzero.any():
            mape = float(
                np.mean(np.abs((y_test[nonzero] - preds[nonzero]) / y_test[nonzero])) * 100.0
            )
        else:
            mape = 0.0

        return EvaluationResult(
            model_name=self.model_name,
            n_train=len(x_train),
            n_test=len(x_test),
            mae=mae,
            rmse=rmse,
            r2=r2,
            mape=mape,
        )

    def forecast(self, values: Sequence[float], steps: int) -> ForecastResult:
        """Forecast `steps` future values, iteratively feeding predictions back."""
        arr = np.asarray(values, dtype=float)
        current = float(arr[-1]) if len(arr) else 0.0

        if self.model is None or len(arr) < self.lags:
            # Persistence fallback: assume the last value holds.
            return ForecastResult(
                model_name="persistence",
                confidence=0.2,
                current_value=current,
                horizon_values=[current] * steps,
            )

        window = list(arr[-self.lags :])
        forecasts: list[float] = []
        for _ in range(steps):
            x = np.asarray(window[-self.lags :]).reshape(1, -1)
            pred = float(self.model.predict(x)[0])
            pred = max(0.0, min(100.0, pred))  # clamp percentage metrics
            forecasts.append(round(pred, 2))
            window.append(pred)

        return ForecastResult(
            model_name=self.model_name,
            confidence=round(self._confidence, 3),
            current_value=current,
            horizon_values=forecasts,
        )

    # ---- Persistence ----
    def save(self, path: str | Path) -> None:
        import joblib

        if self.model is not None:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            joblib.dump(
                {"model": self.model, "lags": self.lags, "name": self.model_name,
                 "confidence": self._confidence},
                path,
            )

    def load(self, path: str | Path) -> bool:
        import joblib

        p = Path(path)
        if not p.exists():
            return False
        payload = joblib.load(p)
        self.model = payload["model"]
        self.lags = payload["lags"]
        self.model_name = payload["name"]
        self._confidence = payload.get("confidence", 0.0)
        return True


class TrendForecaster:
    """Linear extrapolation for slow-growing metrics (e.g. disk usage)."""

    def __init__(self) -> None:
        self.model = LinearRegression()
        self._fitted = False
        self._confidence = 0.0

    def fit_predict(
        self,
        timestamps: Sequence[datetime],
        values: Sequence[float],
        horizon_minutes: int,
    ) -> ForecastResult:
        """Fit usage vs elapsed-minutes and predict `horizon_minutes` ahead."""
        if len(values) < 5:
            current = float(values[-1]) if values else 0.0
            return ForecastResult(
                model_name="persistence",
                confidence=0.2,
                current_value=current,
                horizon_values=[current],
            )

        t0 = timestamps[0]
        x = np.asarray(
            [[(ts - t0).total_seconds() / 60.0] for ts in timestamps], dtype=float
        )
        y = np.asarray(values, dtype=float)
        self.model.fit(x, y)
        preds_in = self.model.predict(x)
        self._confidence = float(max(0.0, min(1.0, r2_score(y, preds_in))))
        self._fitted = True

        future_minute = x[-1][0] + horizon_minutes
        predicted = float(self.model.predict([[future_minute]])[0])
        predicted = max(0.0, min(100.0, predicted))

        return ForecastResult(
            model_name="linear_regression",
            confidence=round(self._confidence, 3),
            current_value=float(y[-1]),
            horizon_values=[round(predicted, 2)],
        )
