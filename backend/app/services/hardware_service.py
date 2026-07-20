"""Hardware Health & Thermal Intelligence service.

Responsibilities (Clean Architecture — this is the business layer):
  * read normalized sensor data via the platform-agnostic HardwareMonitor,
  * persist readings (time-series),
  * compute an overall hardware health score from component sub-scores,
  * detect thermal throttling and sustained-overheat anomalies,
  * generate human-readable AI explanations (rule-based, LLM-swappable),
  * generate contextual recommendations,
  * raise de-duplicated thermal alerts (reusing the shared Alert table).

The explanation engine is intentionally rule-based and explainable; the
`explain_*` methods are isolated so an LLM can later enhance/replace them
without touching detection or scoring logic.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.hardware import HardwareReading, get_hardware_monitor
from app.models.alert import Alert
from app.models.enums import AlertType, Severity
from app.models.hardware import HardwareMetric
from app.schemas.hardware import (
    ComponentHealth,
    HardwareSnapshot,
    HealthScore,
    ThermalExplanation,
    ThermalRecommendation,
    ThrottlingStatus,
)

logger = logging.getLogger(__name__)

# ---- Thermal thresholds (degrees Celsius) ----
CPU_WARNING = 85.0
CPU_CRITICAL = 95.0
CPU_EMERGENCY = 100.0
GPU_WARNING = 85.0
SSD_WARNING = 70.0
BATTERY_WARNING = 45.0
BATTERY_CRITICAL = 55.0

# Sustained-overheat detection window.
SUSTAINED_MINUTES = 5
SUSTAINED_CPU_TEMP = 90.0

# Throttling heuristic.
THROTTLE_UTIL = 80.0          # CPU busy
THROTTLE_FREQ_RATIO = 0.75    # running below 75% of max frequency
THROTTLE_TEMP = CPU_WARNING


class HardwareHealthService:
    """Encapsulates all hardware-health business logic."""

    def __init__(self, db: Session | None = None) -> None:
        self.db = db
        self.monitor = get_hardware_monitor()

    # ------------------------------------------------------------------ #
    # Reading & persistence
    # ------------------------------------------------------------------ #
    def get_snapshot(self) -> HardwareSnapshot:
        """Collect a live, normalized hardware snapshot."""
        reading = self.monitor.read()
        return self._to_snapshot(reading)

    @staticmethod
    def _to_snapshot(reading: HardwareReading) -> HardwareSnapshot:
        return HardwareSnapshot(
            cpu_package_temp=reading.cpu_package_temp,
            cpu_core_temps=reading.cpu_core_temps,
            cpu_frequency_mhz=reading.cpu_frequency_mhz,
            cpu_frequency_max_mhz=reading.cpu_frequency_max_mhz,
            cpu_utilization=reading.cpu_utilization,
            gpu_temp=reading.gpu_temp,
            motherboard_temp=reading.motherboard_temp,
            ssd_temp=reading.ssd_temp,
            hdd_temp=reading.hdd_temp,
            fan_speed_rpm=reading.fan_speed_rpm,
            battery_temp=reading.battery_temp,
            battery_health=reading.battery_health,
            battery_percent=reading.battery_percent,
            battery_status=reading.battery_status,
            available_sensors=reading.available_sensors,
            source=reading.source,
            timestamp=reading.timestamp,
        )

    def persist_snapshot(self, snapshot: HardwareSnapshot) -> HardwareMetric:
        """Store a hardware snapshot for trend analysis and ML training."""
        if self.db is None:
            raise RuntimeError("persist_snapshot requires a database session")
        cores = snapshot.cpu_core_temps
        row = HardwareMetric(
            cpu_package_temp=snapshot.cpu_package_temp,
            cpu_core_1_temp=cores[0] if len(cores) > 0 else None,
            cpu_core_2_temp=cores[1] if len(cores) > 1 else None,
            cpu_core_3_temp=cores[2] if len(cores) > 2 else None,
            cpu_core_4_temp=cores[3] if len(cores) > 3 else None,
            cpu_frequency=snapshot.cpu_frequency_mhz,
            cpu_utilization=snapshot.cpu_utilization,
            gpu_temp=snapshot.gpu_temp,
            motherboard_temp=snapshot.motherboard_temp,
            ssd_temp=snapshot.ssd_temp,
            hdd_temp=snapshot.hdd_temp,
            fan_speed=snapshot.fan_speed_rpm,
            battery_temp=snapshot.battery_temp,
            battery_health=snapshot.battery_health,
            battery_percent=snapshot.battery_percent,
            battery_status=snapshot.battery_status,
            timestamp=snapshot.timestamp,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_history(self, minutes: int = 60, limit: int = 500) -> list[HardwareMetric]:
        if self.db is None:
            return []
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        stmt = (
            select(HardwareMetric)
            .where(HardwareMetric.timestamp >= cutoff)
            .order_by(HardwareMetric.timestamp.desc())
            .limit(limit)
        )
        rows = list(self.db.scalars(stmt))
        rows.reverse()
        return rows

    def get_series(self, minutes: int, column: str) -> list[tuple[datetime, float]]:
        """Return (timestamp, value) pairs for a single non-null sensor column."""
        if self.db is None:
            return []
        col = getattr(HardwareMetric, column, HardwareMetric.cpu_package_temp)
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        stmt = (
            select(HardwareMetric.timestamp, col)
            .where(HardwareMetric.timestamp >= cutoff)
            .where(col.is_not(None))
            .order_by(HardwareMetric.timestamp.asc())
        )
        return [(ts, float(v)) for ts, v in self.db.execute(stmt).all() if v is not None]

    def purge_old(self, retention_days: int) -> int:
        if self.db is None:
            return 0
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        result = self.db.execute(
            delete(HardwareMetric).where(HardwareMetric.timestamp < cutoff)
        )
        self.db.commit()
        return result.rowcount or 0

    # ------------------------------------------------------------------ #
    # Health scoring
    # ------------------------------------------------------------------ #
    @staticmethod
    def _temp_score(temp: float | None, good: float, warn: float, crit: float) -> float | None:
        """Map a temperature to a 0-100 score (cooler = higher)."""
        if temp is None:
            return None
        if temp <= good:
            return 100.0
        if temp >= crit:
            return max(0.0, 30.0 - (temp - crit))
        # Linear interpolation between good (100) and crit (30).
        span = crit - good
        return round(100.0 - (temp - good) / span * 70.0, 1)

    @staticmethod
    def _rating(score: float) -> str:
        if score >= 90:
            return "excellent"
        if score >= 75:
            return "good"
        if score >= 60:
            return "fair"
        return "poor"

    def compute_health_score(self, snapshot: HardwareSnapshot) -> HealthScore:
        components: list[ComponentHealth] = []

        # CPU health from package temperature.
        cpu_score = self._temp_score(snapshot.cpu_package_temp, 60, CPU_WARNING, CPU_CRITICAL)
        if cpu_score is not None:
            components.append(
                ComponentHealth(
                    name="CPU",
                    score=cpu_score,
                    status=self._rating(cpu_score),
                    detail=f"Package temperature {snapshot.cpu_package_temp:.0f}°C",
                )
            )

        # Cooling efficiency: high temp with low/absent fan response is bad.
        cooling = self._cooling_score(snapshot)
        if cooling is not None:
            components.append(
                ComponentHealth(
                    name="Cooling",
                    score=cooling,
                    status=self._rating(cooling),
                    detail=(
                        f"Fan {snapshot.fan_speed_rpm:.0f} RPM"
                        if snapshot.fan_speed_rpm
                        else "Fan sensor unavailable"
                    ),
                )
            )

        # Storage health from SSD/HDD temperature.
        storage_temp = snapshot.ssd_temp if snapshot.ssd_temp is not None else snapshot.hdd_temp
        storage_score = self._temp_score(storage_temp, 45, SSD_WARNING, 80)
        if storage_score is not None:
            components.append(
                ComponentHealth(
                    name="Storage",
                    score=storage_score,
                    status=self._rating(storage_score),
                    detail=f"Drive temperature {storage_temp:.0f}°C",
                )
            )

        # Battery health (reported directly by the OS).
        if snapshot.battery_health is not None:
            components.append(
                ComponentHealth(
                    name="Battery",
                    score=round(snapshot.battery_health, 1),
                    status=self._rating(snapshot.battery_health),
                    detail=f"{snapshot.battery_health:.0f}% of design capacity",
                )
            )

        if components:
            overall = round(sum(c.score for c in components) / len(components), 1)
        else:
            overall = 0.0
        return HealthScore(overall=overall, rating=self._rating(overall), components=components)

    def _cooling_score(self, snapshot: HardwareSnapshot) -> float | None:
        temp = snapshot.cpu_package_temp
        if temp is None:
            return None
        fan = snapshot.fan_speed_rpm
        if temp <= 65:
            return 100.0
        if temp >= CPU_CRITICAL:
            # Hot CPU; if the fan isn't spinning hard, cooling is failing.
            if fan is not None and fan < 1500:
                return 25.0
            return 45.0
        base = self._temp_score(temp, 65, CPU_WARNING, CPU_CRITICAL) or 60.0
        if fan is not None and fan >= 3000:
            base = min(100.0, base + 10.0)  # fan is actively responding
        return round(base, 1)

    # ------------------------------------------------------------------ #
    # Throttling detection
    # ------------------------------------------------------------------ #
    def detect_throttling(self, snapshot: HardwareSnapshot) -> ThrottlingStatus:
        util = snapshot.cpu_utilization
        freq = snapshot.cpu_frequency_mhz
        freq_max = snapshot.cpu_frequency_max_mhz
        temp = snapshot.cpu_package_temp

        throttling = False
        if (
            util is not None
            and freq is not None
            and freq_max
            and temp is not None
            and util >= THROTTLE_UTIL
            and freq <= freq_max * THROTTLE_FREQ_RATIO
            and temp >= THROTTLE_TEMP
        ):
            throttling = True

        if throttling:
            message = (
                "Thermal throttling detected. The processor has automatically reduced "
                f"its clock frequency (now {freq:.0f} MHz of {freq_max:.0f} MHz max) "
                f"to prevent hardware damage while running at {util:.0f}% load and "
                f"{temp:.0f}°C."
            )
        else:
            message = "No thermal throttling detected; the CPU is running at expected clocks."

        return ThrottlingStatus(
            throttling=throttling,
            message=message,
            cpu_utilization=util,
            cpu_frequency=freq,
            cpu_frequency_max=freq_max,
            cpu_temp=temp,
        )

    # ------------------------------------------------------------------ #
    # AI explanations (rule-based; LLM-swappable)
    # ------------------------------------------------------------------ #
    def generate_explanations(self, snapshot: HardwareSnapshot) -> list[ThermalExplanation]:
        explanations: list[ThermalExplanation] = []

        cpu = snapshot.cpu_package_temp
        if cpu is not None:
            sustained = self._sustained_high_cpu()
            if cpu >= CPU_EMERGENCY:
                explanations.append(ThermalExplanation(
                    title="CPU temperature is dangerously high",
                    level="emergency", metric="cpu_package_temp", value=cpu,
                    explanation=(
                        f"The processor is at {cpu:.0f}°C, at or above its emergency limit. "
                        "Save your work and reduce load immediately — sustained operation "
                        "here risks hardware damage and forced shutdown."),
                ))
            elif cpu >= CPU_CRITICAL:
                explanations.append(ThermalExplanation(
                    title="CPU temperature critical",
                    level="critical", metric="cpu_package_temp", value=cpu,
                    explanation=(
                        f"The processor has reached {cpu:.0f}°C. The CPU will likely begin "
                        "thermal throttling, reducing performance. Close heavy applications "
                        "and check that cooling vents are not blocked."),
                ))
            elif cpu >= CPU_WARNING or sustained:
                note = (
                    " It has stayed above 90°C for over five minutes, "
                    "indicating a sustained heavy workload or insufficient cooling."
                    if sustained else ""
                )
                explanations.append(ThermalExplanation(
                    title="CPU running warm",
                    level="warning", metric="cpu_package_temp", value=cpu,
                    explanation=(
                        f"The processor is at {cpu:.0f}°C.{note} If this trend continues the "
                        "CPU may reduce its clock speed (thermal throttling), leading to "
                        "lower performance."),
                ))

        if snapshot.ssd_temp is not None and snapshot.ssd_temp >= SSD_WARNING:
            explanations.append(ThermalExplanation(
                title="Storage overheating",
                level="warning", metric="ssd_temp", value=snapshot.ssd_temp,
                explanation=(
                    f"The SSD/NVMe drive is at {snapshot.ssd_temp:.0f}°C. Sustained "
                    "high temperatures can trigger drive throttling and shorten its "
                    "lifespan. Reduce sustained disk-intensive operations."),
            ))

        if snapshot.battery_temp is not None and snapshot.battery_temp >= BATTERY_WARNING:
            level = "critical" if snapshot.battery_temp >= BATTERY_CRITICAL else "warning"
            explanations.append(ThermalExplanation(
                title="Battery temperature high",
                level=level, metric="battery_temp", value=snapshot.battery_temp,
                explanation=(
                    f"The battery is at {snapshot.battery_temp:.0f}°C, above its safe range. "
                    "Heat accelerates battery wear. Reduce system load and, if charging, "
                    "consider unplugging until it cools."),
            ))

        throttle = self.detect_throttling(snapshot)
        if throttle.throttling:
            explanations.append(ThermalExplanation(
                title="Thermal throttling active",
                level="critical", metric="cpu_frequency", value=snapshot.cpu_frequency_mhz,
                explanation=throttle.message,
            ))

        if not explanations:
            explanations.append(ThermalExplanation(
                title="Hardware thermals are healthy",
                level="normal", metric="cpu_package_temp", value=cpu,
                explanation=(
                    "All monitored sensors are within safe ranges. No thermal action "
                    "is needed right now."),
            ))
        return explanations

    def _sustained_high_cpu(self) -> bool:
        """True if CPU package temp stayed above SUSTAINED_CPU_TEMP for the window."""
        series = self.get_series(SUSTAINED_MINUTES, "cpu_package_temp")
        if len(series) < 3:
            return False
        return all(v >= SUSTAINED_CPU_TEMP for _, v in series)

    # ------------------------------------------------------------------ #
    # Recommendations
    # ------------------------------------------------------------------ #
    def generate_recommendations(self, snapshot: HardwareSnapshot) -> list[ThermalRecommendation]:
        recs: list[ThermalRecommendation] = []
        cpu = snapshot.cpu_package_temp
        if cpu is not None and cpu >= CPU_WARNING:
            recs.append(ThermalRecommendation(
                issue="High CPU temperature",
                severity="high" if cpu >= CPU_CRITICAL else "medium",
                actions=[
                    "Close CPU-intensive applications.",
                    "Reduce the number of open browser tabs.",
                    "Switch to Power Saver / balanced power mode.",
                    "Ensure cooling vents are unobstructed.",
                ],
            ))
        if snapshot.ssd_temp is not None and snapshot.ssd_temp >= SSD_WARNING:
            recs.append(ThermalRecommendation(
                issue="High SSD temperature",
                severity="medium",
                actions=[
                    "Pause large file transfers or backups.",
                    "Reduce sustained disk-intensive operations.",
                    "Improve case airflow around the drive.",
                ],
            ))
        if snapshot.battery_temp is not None and snapshot.battery_temp >= BATTERY_WARNING:
            recs.append(ThermalRecommendation(
                issue="High battery temperature",
                severity="high" if snapshot.battery_temp >= BATTERY_CRITICAL else "medium",
                actions=[
                    "Disconnect the charger if it is not needed.",
                    "Reduce system load until the battery cools.",
                    "Avoid using the laptop on soft surfaces that block vents.",
                ],
            ))
        if (
            snapshot.fan_speed_rpm is not None
            and snapshot.fan_speed_rpm < 1200
            and cpu is not None
            and cpu >= CPU_WARNING
        ):
            recs.append(ThermalRecommendation(
                issue="Low fan speed with high CPU temperature (possible cooling failure)",
                severity="high",
                actions=[
                    "Clean dust from the cooling vents and fan.",
                    "Inspect the cooling fan for failure.",
                    "Consider re-applying thermal paste if the laptop is old.",
                ],
            ))
        if not recs:
            recs.append(ThermalRecommendation(
                issue="No thermal issues detected",
                severity="info",
                actions=["No action needed. Keep vents clear for continued healthy operation."],
            ))
        return recs

    # ------------------------------------------------------------------ #
    # Thermal alerts (reuse shared Alert table)
    # ------------------------------------------------------------------ #
    DEDUP_WINDOW = timedelta(minutes=5)

    def check_thermal_alerts(self, snapshot: HardwareSnapshot) -> list[Alert]:
        if self.db is None:
            return []
        raised: list[Alert] = []
        checks = [
            ("CPU", snapshot.cpu_package_temp, CPU_CRITICAL, CPU_EMERGENCY),
            ("GPU", snapshot.gpu_temp, GPU_WARNING, GPU_WARNING + 10),
            ("SSD", snapshot.ssd_temp, SSD_WARNING, SSD_WARNING + 10),
            ("Battery", snapshot.battery_temp, BATTERY_WARNING, BATTERY_CRITICAL),
        ]
        for label, value, warn, crit in checks:
            if value is None or value < warn:
                continue
            key = f"[thermal:{label}]"
            if self._recently_raised(key):
                continue
            severity = Severity.CRITICAL if value >= crit else Severity.HIGH
            alert = Alert(
                alert_type=AlertType.SYSTEM,
                message=f"{key} {label} temperature {value:.0f}°C exceeds the {warn:.0f}°C threshold.",
                severity=severity,
                value=float(value),
                threshold=float(warn),
            )
            self.db.add(alert)
            self.db.commit()
            self.db.refresh(alert)
            raised.append(alert)
        return raised

    def _recently_raised(self, key: str) -> bool:
        cutoff = datetime.now(timezone.utc) - self.DEDUP_WINDOW
        stmt = (
            select(Alert)
            .where(Alert.alert_type == AlertType.SYSTEM)
            .where(Alert.message.like(f"{key}%"))
            .where(Alert.created_at >= cutoff)
            .where(Alert.resolved.is_(False))
            .limit(1)
        )
        return self.db.scalar(stmt) is not None
