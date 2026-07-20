"""Offline trainer + evaluator for software-resource forecasting models.

Mirrors app/ml/train_thermal.py but for the `system_metrics` series (CPU,
memory, disk, network). It:
  1. reads collected metrics from the database,
  2. optionally exports them to CSV,
  3. evaluates each model on a chronological train/test split (MAE/RMSE/R²/MAPE),
  4. re-trains on all data and persists each model with joblib.

The FastAPI backend (PredictionService) loads these saved models for live
forecasts, falling back to on-the-fly training when no model is present.

Usage (from the backend directory, venv active):
    python -m app.ml.train_resources                  # train + evaluate + save
    python -m app.ml.train_resources --csv data --report data
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
from app.services.analytics_service import AnalyticsService

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger("train_resources")

# Resource metrics that can be forecast (name -> series key understood by
# AnalyticsService.get_recent_series).
RESOURCE_METRICS = ["cpu", "memory", "disk", "network"]


def export_csv(out_dir: str) -> None:
    """Export the full system_metrics table to CSV."""
    from sqlalchemy import select

    from app.models.metric import SystemMetric

    Path(out_dir).mkdir(parents=True, exist_ok=True)
    out_path = Path(out_dir) / "system_metrics.csv"
    with SessionLocal() as db:
        rows = list(db.scalars(select(SystemMetric).order_by(SystemMetric.timestamp)))
    if not rows:
        logger.warning("No system_metrics rows to export.")
        return
    columns = [c.name for c in SystemMetric.__table__.columns]
    with open(out_path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(columns)
        for row in rows:
            writer.writerow([getattr(row, c) for c in columns])
    logger.info("Exported %d rows to %s", len(rows), out_path)


def _write_report(metrics: list[dict], report_dir: str) -> None:
    if not metrics:
        return
    Path(report_dir).mkdir(parents=True, exist_ok=True)
    json_path = Path(report_dir) / "resource_model_metrics.json"
    csv_path = Path(report_dir) / "resource_model_metrics.csv"
    json_path.write_text(json.dumps(metrics, indent=2))
    columns = ["metric", "model", "n_train", "n_test", "mae", "rmse", "r2", "mape_pct"]
    with open(csv_path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        for row in metrics:
            writer.writerow({c: row.get(c) for c in columns})
    logger.info("Wrote evaluation report to %s and %s", json_path, csv_path)


def _print_table(metrics: list[dict]) -> None:
    if not metrics:
        logger.warning("No models were evaluated (insufficient data).")
        return
    header = f"{'metric':<12}{'model':<15}{'MAE':>8}{'RMSE':>8}{'R2':>7}{'MAPE%':>8}"
    print("\n" + header)
    print("-" * len(header))
    for m in metrics:
        print(
            f"{m['metric']:<12}{m['model']:<15}{m['mae']:>8.2f}{m['rmse']:>8.2f}"
            f"{m['r2']:>7.2f}{m['mape_pct']:>8.2f}"
        )
    print()


def train_all(history_minutes: int = 60 * 24 * 30, report_dir: str | None = None) -> None:
    """Evaluate, then train and persist a model for each resource metric."""
    model_dir = Path(settings.ML_MODEL_DIR)
    model_dir.mkdir(parents=True, exist_ok=True)
    metrics: list[dict] = []

    with SessionLocal() as db:
        analytics = AnalyticsService(db)
        for metric in RESOURCE_METRICS:
            series = analytics.get_recent_series(history_minutes, metric)
            values = [v for _, v in series]
            if len(values) < settings.ML_MIN_TRAINING_SAMPLES:
                logger.warning(
                    "Skipping %s: only %d samples (need >= %d).",
                    metric, len(values), settings.ML_MIN_TRAINING_SAMPLES,
                )
                continue

            forecaster = ShortHorizonForecaster(lags=5, model_name="random_forest")

            evaluation = forecaster.evaluate(values, test_fraction=0.2)
            if evaluation is not None:
                metrics.append({"metric": metric, **evaluation.as_dict()})
                logger.info(
                    "%s evaluation -> MAE=%.2f RMSE=%.2f R2=%.2f MAPE=%.2f%% "
                    "(train=%d, test=%d)",
                    metric, evaluation.mae, evaluation.rmse, evaluation.r2,
                    evaluation.mape, evaluation.n_train, evaluation.n_test,
                )

            if forecaster.fit(values):
                path = model_dir / f"resource_{metric}.joblib"
                forecaster.save(path)
                logger.info("Trained %s on %d samples -> %s", metric, len(values), path)
            else:
                logger.warning("Training failed for %s", metric)

    _print_table(metrics)
    if report_dir:
        _write_report(metrics, report_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description="Train & evaluate SystemIQ resource models")
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
