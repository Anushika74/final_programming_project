"""Offline trainer for thermal forecasting models.

Implements the recommended end-to-end ML pipeline:
  1. Read collected hardware metrics from the database.
  2. (Optionally) export them to CSV for inspection / reproducibility.
  3. Train a scikit-learn model per forecastable sensor.
  4. Persist each model to ML_MODEL_DIR with joblib.

The FastAPI backend (ThermalPredictionService) then loads these saved models
to serve live predictions.

Usage (from the backend directory, venv active):
    python -m app.ml.train_thermal              # train + save models
    python -m app.ml.train_thermal --csv data   # also export CSV to ./data
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
from pathlib import Path

from app.core.config import settings
from app.core.database import SessionLocal
from app.ml.forecaster import ShortHorizonForecaster
from app.services.thermal_prediction import FORECASTABLE
from app.services.hardware_service import HardwareHealthService

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger("train_thermal")


def export_csv(out_dir: str) -> None:
    """Export the full hardware_metrics table to CSV."""
    from app.models.hardware import HardwareMetric
    from sqlalchemy import select

    Path(out_dir).mkdir(parents=True, exist_ok=True)
    out_path = Path(out_dir) / "hardware_metrics.csv"
    with SessionLocal() as db:
        rows = list(db.scalars(select(HardwareMetric).order_by(HardwareMetric.timestamp)))
    if not rows:
        logger.warning("No hardware_metrics rows to export.")
        return
    columns = [c.name for c in HardwareMetric.__table__.columns]
    with open(out_path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(columns)
        for row in rows:
            writer.writerow([getattr(row, c) for c in columns])
    logger.info("Exported %d rows to %s", len(rows), out_path)


def _write_report(metrics: list[dict], report_dir: str) -> None:
    """Write the evaluation metrics to JSON and CSV for the project report."""
    if not metrics:
        return
    Path(report_dir).mkdir(parents=True, exist_ok=True)
    json_path = Path(report_dir) / "thermal_model_metrics.json"
    csv_path = Path(report_dir) / "thermal_model_metrics.csv"

    json_path.write_text(json.dumps(metrics, indent=2))

    columns = ["sensor", "model", "n_train", "n_test", "mae", "rmse", "r2", "mape_pct"]
    with open(csv_path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        for row in metrics:
            writer.writerow({c: row.get(c) for c in columns})
    logger.info("Wrote evaluation report to %s and %s", json_path, csv_path)


def _print_table(metrics: list[dict]) -> None:
    """Pretty-print the metrics table to the console."""
    if not metrics:
        logger.warning("No models were evaluated (insufficient data).")
        return
    header = f"{'sensor':<20}{'model':<15}{'MAE':>8}{'RMSE':>8}{'R2':>7}{'MAPE%':>8}"
    print("\n" + header)
    print("-" * len(header))
    for m in metrics:
        print(
            f"{m['sensor']:<20}{m['model']:<15}{m['mae']:>8.2f}{m['rmse']:>8.2f}"
            f"{m['r2']:>7.2f}{m['mape_pct']:>8.2f}"
        )
    print()


def train_all(history_minutes: int = 60 * 24 * 30, report_dir: str | None = None) -> None:
    """Evaluate, then train and persist a model for each forecastable sensor."""
    model_dir = Path(settings.ML_MODEL_DIR)
    model_dir.mkdir(parents=True, exist_ok=True)
    metrics: list[dict] = []

    with SessionLocal() as db:
        service = HardwareHealthService(db)
        for sensor, column in FORECASTABLE.items():
            series = service.get_series(history_minutes, column)
            values = [v for _, v in series]
            if len(values) < settings.ML_MIN_TRAINING_SAMPLES:
                logger.warning(
                    "Skipping %s: only %d samples (need >= %d).",
                    sensor, len(values), settings.ML_MIN_TRAINING_SAMPLES,
                )
                continue

            forecaster = ShortHorizonForecaster(lags=5, model_name="random_forest")

            # 1. Evaluate on a chronological hold-out split (honest accuracy).
            evaluation = forecaster.evaluate(values, test_fraction=0.2)
            if evaluation is not None:
                row = {"sensor": sensor, **evaluation.as_dict()}
                metrics.append(row)
                logger.info(
                    "%s evaluation -> MAE=%.2f RMSE=%.2f R2=%.2f MAPE=%.2f%% "
                    "(train=%d, test=%d)",
                    sensor, evaluation.mae, evaluation.rmse, evaluation.r2,
                    evaluation.mape, evaluation.n_train, evaluation.n_test,
                )

            # 2. Re-train on ALL data and persist the production model.
            if forecaster.fit(values):
                path = model_dir / f"thermal_{sensor}.joblib"
                forecaster.save(path)
                logger.info("Trained %s on %d samples -> %s", sensor, len(values), path)
            else:
                logger.warning("Training failed for %s", sensor)

    _print_table(metrics)
    if report_dir:
        _write_report(metrics, report_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description="Train & evaluate SystemIQ thermal models")
    parser.add_argument("--csv", metavar="DIR", help="export raw metrics to CSV in DIR")
    parser.add_argument(
        "--report", metavar="DIR", default="data",
        help="write evaluation metrics (JSON+CSV) to DIR (default: ./data)",
    )
    parser.add_argument(
        "--history-minutes", type=int, default=60 * 24 * 30,
        help="how much history to train on (default: 30 days)",
    )
    args = parser.parse_args()

    if args.csv:
        export_csv(args.csv)
    train_all(history_minutes=args.history_minutes, report_dir=args.report)
    logger.info("Done.")


if __name__ == "__main__":
    main()
