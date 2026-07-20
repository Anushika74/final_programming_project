"""Unit tests for the analytical/AI services that don't need the HTTP layer."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.ml.forecaster import ShortHorizonForecaster, TrendForecaster
from app.schemas.insight import FileScanRequest
from app.schemas.metric import MetricSnapshot, ProcessInfo
from app.services.file_analyzer_service import FileAnalyzerService, human_size
from app.services.log_analyzer_service import LogAnalyzerService
from app.services.optimization_service import OptimizationService
from app.services.recommendation_service import RecommendationService


def _snapshot(cpu=50.0, mem=50.0, disk=50.0) -> MetricSnapshot:
    now = datetime.now(timezone.utc)
    return MetricSnapshot(
        cpu_usage=cpu, memory_usage=mem, memory_total_mb=16000, memory_used_mb=mem * 160,
        disk_usage=disk, disk_total_gb=500, disk_used_gb=disk * 5,
        network_sent=0, network_recv=0, network_sent_total_mb=0, network_recv_total_mb=0,
        load_avg_1m=1.0, load_avg_5m=1.0, load_avg_15m=1.0, cpu_count=4,
        uptime_seconds=3600, boot_time=now, timestamp=now,
    )


def test_recommendation_rules_fire_on_high_usage(db_session):
    svc = RecommendationService(db_session)
    procs = [ProcessInfo(pid=1, name="chrome", cpu_usage=95, memory_usage=30, memory_mb=900, status="running")]
    insights = svc.evaluate(_snapshot(cpu=96, mem=96, disk=96), procs)
    titles = {i.title for i in insights}
    assert "High CPU usage detected" in titles
    assert "High memory usage detected" in titles
    assert "Low disk space" in titles


def test_recommendation_quiet_when_healthy(db_session):
    svc = RecommendationService(db_session)
    insights = svc.evaluate(_snapshot(cpu=10, mem=10, disk=10), [])
    assert insights == []


def test_log_analyzer_classifies_severities():
    svc = LogAnalyzerService()
    summary = svc.analyze(
        "kernel: Out of memory: Killed process\nsshd: Failed password for root\nsystemd: Started service",
        persist=False,
    )
    assert summary.total == 3
    assert summary.by_severity["critical"] >= 1


def test_short_horizon_forecaster_trains_and_predicts():
    series = [float(x % 100) for x in range(60)]
    f = ShortHorizonForecaster(lags=5, model_name="linear")
    assert f.fit(series) is True
    result = f.forecast(series, steps=5)
    assert len(result.horizon_values) == 5
    assert all(0 <= v <= 100 for v in result.horizon_values)


def test_forecaster_evaluate_returns_metrics():
    # A smooth, learnable wave so the model should score reasonably.
    series = [50.0 + 10.0 * ((i % 20) / 20.0) for i in range(120)]
    f = ShortHorizonForecaster(lags=5, model_name="random_forest")
    ev = f.evaluate(series, test_fraction=0.2)
    assert ev is not None
    assert ev.n_train > 0 and ev.n_test > 0
    assert ev.mae >= 0.0
    # RMSE is always >= MAE for the same errors.
    assert ev.rmse + 1e-6 >= ev.mae
    assert ev.mape >= 0.0


def test_forecaster_evaluate_insufficient_data_returns_none():
    f = ShortHorizonForecaster(lags=5)
    assert f.evaluate([1.0, 2.0, 3.0]) is None


def test_trend_forecaster_extrapolates_growth():
    base = datetime.now(timezone.utc)
    ts = [base + timedelta(minutes=i) for i in range(20)]
    values = [50 + i * 0.5 for i in range(20)]  # steadily increasing
    result = TrendForecaster().fit_predict(ts, values, horizon_minutes=60)
    assert result.horizon_values[0] >= values[-1]


def test_file_analyzer_scans_tmp(tmp_path):
    (tmp_path / "a.txt").write_text("hello world")
    (tmp_path / "b.txt").write_text("hello world")  # duplicate content
    (tmp_path / "junk.tmp").write_text("temp")
    (tmp_path / "empty").mkdir()

    result = FileAnalyzerService().scan(
        FileScanRequest(path=str(tmp_path), min_large_file_mb=0.0, find_duplicates=True)
    )
    assert result.scanned_files >= 3
    assert any(g.files for g in result.duplicate_groups)
    assert any("junk.tmp" in f.path for f in result.temp_files)


def test_human_size():
    assert human_size(0) == "0.0 B"
    assert human_size(1024).endswith("KB")


def test_optimization_dry_run_does_not_execute():
    res = OptimizationService().execute("clean_temp_files", confirm=False, dry_run=True)
    assert res.executed is False
    assert res.dry_run is True


def test_optimization_requires_confirmation():
    res = OptimizationService().execute("clean_temp_files", confirm=False, dry_run=False)
    assert res.executed is False
    assert "confirm" in res.message.lower()


def test_unknown_optimization_action():
    res = OptimizationService().execute("nope", confirm=True, dry_run=False)
    assert res.executed is False
