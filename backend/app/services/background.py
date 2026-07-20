"""Background task orchestration.

Runs asynchronous loops that:
  * collect metrics and broadcast them to WebSocket clients (fast cadence),
  * persist metric snapshots to the database (slow cadence),
  * evaluate alert thresholds and generate recommendations (slow cadence),
  * purge old metrics once per day.

Each loop is resilient: an exception in one iteration is logged and the loop
continues. All tasks are cancelled cleanly on shutdown.
"""
from __future__ import annotations

import asyncio
import logging
import time

from app.api.websocket import manager
from app.core.config import settings
from app.core.database import SessionLocal
from app.services.alert_service import AlertService
from app.services.analytics_service import AnalyticsService
from app.services.hardware_service import HardwareHealthService
from app.services.monitoring_service import monitoring_service
from app.services.process_service import process_service
from app.services.recommendation_service import RecommendationService

logger = logging.getLogger(__name__)


class BackgroundManager:
    """Owns and lifecycle-manages the background asyncio tasks."""

    def __init__(self) -> None:
        self._tasks: list[asyncio.Task] = []
        self._running = False
        self._last_persist = 0.0
        self._last_purge = 0.0
        # Stateless monitor (no DB) used purely for live snapshots.
        self._hardware = HardwareHealthService()

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._tasks = [
            asyncio.create_task(self._broadcast_loop(), name="metrics-broadcast"),
            asyncio.create_task(self._persist_loop(), name="metrics-persist"),
        ]
        if settings.AUTO_RETRAIN_ENABLED:
            self._tasks.append(
                asyncio.create_task(self._retrain_loop(), name="ml-retrain")
            )
        logger.info("Background tasks started")

    async def stop(self) -> None:
        self._running = False
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks.clear()
        logger.info("Background tasks stopped")

    async def _broadcast_loop(self) -> None:
        """Collect + broadcast software metrics and hardware sensors to clients."""
        while self._running:
            try:
                if manager.active_count > 0:
                    snapshot = monitoring_service.collect()
                    await manager.broadcast(
                        {"type": "metrics", "payload": snapshot.model_dump(mode="json")}
                    )
                    # Hardware/thermal stream (event: hardware.temperature.updated).
                    try:
                        hw = self._hardware.get_snapshot()
                        await manager.broadcast(
                            {"type": "hardware", "payload": hw.model_dump(mode="json")}
                        )
                    except Exception as exc:  # noqa: BLE001 - sensors are best-effort
                        logger.debug("Hardware broadcast skipped: %s", exc)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Broadcast loop error: %s", exc)
            await asyncio.sleep(settings.METRICS_BROADCAST_INTERVAL)

    async def _persist_loop(self) -> None:
        """Persist snapshots, evaluate alerts + recommendations, purge old data."""
        while self._running:
            try:
                await asyncio.to_thread(self._persist_once)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Persist loop error: %s", exc)
            await asyncio.sleep(settings.METRICS_PERSIST_INTERVAL)

    def _persist_once(self) -> None:
        """Synchronous DB work executed in a worker thread."""
        snapshot = monitoring_service.collect()
        top = process_service.top_consumers(by="memory", limit=10)

        with SessionLocal() as db:
            AnalyticsService(db).persist_snapshot(snapshot)
            AlertService(db).check_snapshot(snapshot, notify=True)
            RecommendationService(db).generate_and_store(snapshot, top)

            # Hardware/thermal: persist a reading and raise thermal alerts.
            try:
                hw_service = HardwareHealthService(db)
                hw_snapshot = hw_service.get_snapshot()
                hw_service.persist_snapshot(hw_snapshot)
                hw_service.check_thermal_alerts(hw_snapshot)
            except Exception as exc:  # noqa: BLE001 - hardware is best-effort
                logger.debug("Hardware persist skipped: %s", exc)

            # Daily retention purge.
            now = time.monotonic()
            if now - self._last_purge > 24 * 60 * 60:
                AnalyticsService(db).purge_old(settings.METRICS_RETENTION_DAYS)
                try:
                    HardwareHealthService(db).purge_old(settings.METRICS_RETENTION_DAYS)
                except Exception:  # noqa: BLE001
                    pass
                self._last_purge = now

    # ------------------------------------------------------------------ #
    # Automatic ML retraining
    # ------------------------------------------------------------------ #
    async def _retrain_loop(self) -> None:
        """Periodically retrain & persist ML models from the collected data."""
        interval = max(300.0, settings.AUTO_RETRAIN_INTERVAL_HOURS * 3600.0)
        # Wait a bit after boot so some data has accumulated before the first run.
        await asyncio.sleep(min(interval, 600.0))
        while self._running:
            try:
                await asyncio.to_thread(self._retrain_once)
            except Exception as exc:  # noqa: BLE001 - training must never crash the app
                logger.warning("Auto-retrain error: %s", exc)
            await asyncio.sleep(interval)

    @staticmethod
    def _retrain_once() -> None:
        """Train and persist resource + thermal models (runs in a worker thread)."""
        # Imported lazily so app startup doesn't depend on the ML stack.
        from app.ml import train_resources, train_thermal

        logger.info("Auto-retraining ML models from collected data…")
        train_resources.train_all(report_dir=None)
        train_thermal.train_all(report_dir=None)
        logger.info("Auto-retraining complete.")


background_manager = BackgroundManager()
