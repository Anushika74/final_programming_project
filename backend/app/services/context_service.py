"""System Context Service — the aggregation layer beneath the AI Assistant.

Gathers a complete, normalized `SystemContext` from every SystemIQ subsystem
(metrics, hardware, processes, predictions, recommendations, alerts, logs,
history) so the assistant can reason over one consolidated object instead of
calling each service itself.

Design notes:
  * The AI Assistant depends only on this service, never on sensors/DB directly
    (keeps the assistant a pure reasoning layer — SOLID/clean architecture).
  * Every section is wrapped defensively: if one subsystem fails or has no data,
    the rest of the context is still produced.
  * `sources` records which subsystems actually contributed, for UI transparency.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.enums import MetricType
from app.schemas.context import (
    AlertBrief,
    ComponentHealthBrief,
    LogBrief,
    PredictionBrief,
    RecommendationBrief,
    SystemContext,
    TopProcess,
)
from app.services.alert_service import AlertService
from app.services.analytics_service import AnalyticsService
from app.services.hardware_service import HardwareHealthService
from app.services.log_analyzer_service import LogAnalyzerService
from app.services.monitoring_service import monitoring_service
from app.services.prediction_service import PredictionService
from app.services.process_service import process_service
from app.services.recommendation_service import RecommendationService
from app.services.thermal_prediction import ThermalPredictionService

logger = logging.getLogger(__name__)


def _avg(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 1) if values else None


class SystemContextService:
    """Builds the consolidated SystemContext for the AI Assistant."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def build(self, include_predictions: bool = True) -> SystemContext:
        ctx = SystemContext(timestamp=datetime.now(timezone.utc))
        sources: list[str] = []

        self._add_metrics(ctx, sources)
        self._add_hardware(ctx, sources)
        self._add_processes(ctx, sources)
        self._add_history(ctx, sources)
        if include_predictions:
            self._add_predictions(ctx, sources)
        self._add_recommendations(ctx, sources)
        self._add_alerts(ctx, sources)
        self._add_logs(ctx, sources)

        ctx.sources = sources
        return ctx

    # ------------------------------------------------------------------ #
    def _add_metrics(self, ctx: SystemContext, sources: list[str]) -> None:
        try:
            m = monitoring_service.collect()
            ctx.cpu_usage = m.cpu_usage
            ctx.memory_usage = m.memory_usage
            ctx.disk_usage = m.disk_usage
            ctx.network_recv_kbps = round(m.network_recv / 1024, 1)
            ctx.network_sent_kbps = round(m.network_sent / 1024, 1)
            ctx.load_avg_1m = m.load_avg_1m
            ctx.cpu_count = m.cpu_count
            ctx.uptime_hours = round(m.uptime_seconds / 3600, 1)
            sources.append("metrics")
        except Exception as exc:  # noqa: BLE001
            logger.debug("context metrics failed: %s", exc)

    def _add_hardware(self, ctx: SystemContext, sources: list[str]) -> None:
        try:
            service = HardwareHealthService(self.db)
            snap = service.get_snapshot()
            ctx.cpu_temp = snap.cpu_package_temp
            ctx.cpu_core_temps = snap.cpu_core_temps
            ctx.gpu_temp = snap.gpu_temp
            ctx.ssd_temp = snap.ssd_temp
            ctx.hdd_temp = snap.hdd_temp
            ctx.motherboard_temp = snap.motherboard_temp
            ctx.fan_speed_rpm = snap.fan_speed_rpm
            ctx.battery_temp = snap.battery_temp
            ctx.battery_health = snap.battery_health
            ctx.battery_percent = snap.battery_percent
            ctx.battery_status = snap.battery_status
            ctx.sensor_source = snap.source
            ctx.available_sensors = snap.available_sensors
            ctx.cpu_frequency_mhz = snap.cpu_frequency_mhz

            health = service.compute_health_score(snap)
            ctx.health_overall = health.overall
            ctx.health_rating = health.rating
            ctx.health_components = [
                ComponentHealthBrief(name=c.name, score=c.score, status=c.status, detail=c.detail)
                for c in health.components
            ]
            throttle = service.detect_throttling(snap)
            ctx.throttling = throttle.throttling
            ctx.throttling_message = throttle.message
            ctx.sustained_high_cpu_temp = service._sustained_high_cpu()  # noqa: SLF001
            sources.append("hardware")
        except Exception as exc:  # noqa: BLE001
            logger.debug("context hardware failed: %s", exc)

    def _add_processes(self, ctx: SystemContext, sources: list[str]) -> None:
        try:
            ctx.top_cpu = [
                TopProcess(pid=p.pid, name=p.name, cpu_usage=p.cpu_usage,
                           memory_usage=p.memory_usage, memory_mb=p.memory_mb)
                for p in process_service.top_consumers(by="cpu", limit=5)
            ]
            ctx.top_memory = [
                TopProcess(pid=p.pid, name=p.name, cpu_usage=p.cpu_usage,
                           memory_usage=p.memory_usage, memory_mb=p.memory_mb)
                for p in process_service.top_consumers(by="memory", limit=5)
            ]
            sources.append("processes")
        except Exception as exc:  # noqa: BLE001
            logger.debug("context processes failed: %s", exc)

    def _add_history(self, ctx: SystemContext, sources: list[str]) -> None:
        try:
            analytics = AnalyticsService(self.db)
            ctx.cpu_avg_1h = _avg([v for _, v in analytics.get_recent_series(60, "cpu")])
            ctx.memory_avg_1h = _avg([v for _, v in analytics.get_recent_series(60, "memory")])
            hw = HardwareHealthService(self.db)
            ctx.cpu_temp_avg_1h = _avg([v for _, v in hw.get_series(60, "cpu_package_temp")])
            if ctx.cpu_avg_1h is not None or ctx.cpu_temp_avg_1h is not None:
                sources.append("history")
        except Exception as exc:  # noqa: BLE001
            logger.debug("context history failed: %s", exc)

    def _add_predictions(self, ctx: SystemContext, sources: list[str]) -> None:
        try:
            pred = PredictionService(self.db)
            for metric in (MetricType.CPU, MetricType.MEMORY):
                f = pred.forecast_short(metric_type=metric, horizon_minutes=10)
                peak = max((p.value for p in f.points), default=f.current_value)
                ctx.predictions.append(PredictionBrief(
                    metric=metric.value, current=f.current_value,
                    predicted_peak=round(peak, 1), risk=f.risk, message=f.message,
                ))
            thermal = ThermalPredictionService(self.db)
            tf = thermal.forecast(sensor="cpu_package_temp", horizon_minutes=10)
            peak = max((p.value for p in tf.points), default=tf.current_value)
            ctx.predictions.append(PredictionBrief(
                metric="cpu_temperature", current=tf.current_value,
                predicted_peak=round(peak, 1) if peak is not None else None,
                risk=tf.risk, message=tf.message,
            ))
            sources.append("predictions")
        except Exception as exc:  # noqa: BLE001
            logger.debug("context predictions failed: %s", exc)

    def _add_recommendations(self, ctx: SystemContext, sources: list[str]) -> None:
        try:
            for r in RecommendationService(self.db).list_recommendations(limit=5):
                ctx.recommendations.append(RecommendationBrief(
                    issue=r.title, severity=r.severity.value, detail=r.recommendation,
                ))
            # Hardware/thermal recommendations from the live snapshot.
            hw = HardwareHealthService(self.db)
            for tr in hw.generate_recommendations(hw.get_snapshot()):
                if tr.severity == "info":
                    continue
                ctx.recommendations.append(RecommendationBrief(
                    issue=tr.issue, severity=tr.severity, detail="; ".join(tr.actions),
                ))
            if ctx.recommendations:
                sources.append("recommendations")
        except Exception as exc:  # noqa: BLE001
            logger.debug("context recommendations failed: %s", exc)

    def _add_alerts(self, ctx: SystemContext, sources: list[str]) -> None:
        try:
            for a in AlertService(self.db).list_alerts(limit=8, only_unresolved=True):
                ctx.alerts.append(AlertBrief(
                    type=a.alert_type.value, message=a.message, severity=a.severity.value,
                ))
            if ctx.alerts:
                sources.append("alerts")
        except Exception as exc:  # noqa: BLE001
            logger.debug("context alerts failed: %s", exc)

    def _add_logs(self, ctx: SystemContext, sources: list[str]) -> None:
        try:
            for e in LogAnalyzerService(self.db).recent_entries(limit=5):
                ctx.recent_logs.append(LogBrief(
                    severity=e.severity.value, category=e.category, explanation=e.explanation,
                ))
            if ctx.recent_logs:
                sources.append("logs")
        except Exception as exc:  # noqa: BLE001
            logger.debug("context logs failed: %s", exc)
