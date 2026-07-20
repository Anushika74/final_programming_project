"""Linux hardware monitor.

Reads sensors using a layered strategy, preferring psutil and falling back to
sysfs. Every access is defensive: a missing or unreadable sensor yields ``None``
rather than an exception.

Sources (in priority order):
  1. psutil.sensors_temperatures / sensors_fans / sensors_battery
  2. /sys/class/power_supply  (battery health, temperature, status)
  3. /sys/class/thermal       (thermal zones fallback)
  4. /sys/class/hwmon         (generic hwmon fallback)
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import psutil

from app.hardware.base import HardwareMonitor, HardwareReading

logger = logging.getLogger(__name__)

# Sensor-chip name hints used to classify psutil temperature groups.
_CPU_CHIPS = ("coretemp", "k10temp", "zenpower", "cpu_thermal", "k8temp")
_GPU_CHIPS = ("amdgpu", "nouveau", "radeon", "gpu")
_SSD_CHIPS = ("nvme", "drivetemp")
_BOARD_CHIPS = ("acpitz", "pch", "mb", "motherboard")


def _read_sysfs(path: str) -> str | None:
    """Read a sysfs file, returning stripped text or None on any error."""
    try:
        return Path(path).read_text().strip()
    except (OSError, PermissionError, ValueError):
        return None


def _read_int(path: str) -> int | None:
    raw = _read_sysfs(path)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


class LinuxHardwareMonitor(HardwareMonitor):
    """Hardware monitor for Linux hosts."""

    platform = "linux"

    def is_supported(self) -> bool:
        return os.name == "posix" and os.path.isdir("/sys")

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def read(self) -> HardwareReading:
        reading = HardwareReading(source="psutil+sysfs")
        self._read_temperatures(reading)
        self._read_fans(reading)
        self._read_cpu(reading)
        self._read_battery(reading)

        # Fallbacks if psutil exposed nothing useful for CPU temperature.
        if reading.cpu_package_temp is None:
            reading.cpu_package_temp = self._thermal_zone_cpu_temp()

        reading.available_sensors = self._collect_available(reading)
        return reading

    def detect_sensors(self) -> list[str]:
        return self._collect_available(self.read())

    # ------------------------------------------------------------------ #
    # Temperature sensors
    # ------------------------------------------------------------------ #
    def _read_temperatures(self, reading: HardwareReading) -> None:
        try:
            temps = psutil.sensors_temperatures()
        except (AttributeError, OSError):  # not available on this platform
            temps = {}

        for chip, entries in temps.items():
            chip_lower = chip.lower()
            if any(h in chip_lower for h in _CPU_CHIPS):
                self._classify_cpu(entries, reading)
            elif any(h in chip_lower for h in _GPU_CHIPS):
                reading.gpu_temp = self._first_current(entries, reading.gpu_temp)
            elif any(h in chip_lower for h in _SSD_CHIPS):
                reading.ssd_temp = self._first_current(entries, reading.ssd_temp)
            elif any(h in chip_lower for h in _BOARD_CHIPS):
                reading.motherboard_temp = self._first_current(entries, reading.motherboard_temp)

    @staticmethod
    def _classify_cpu(entries, reading: HardwareReading) -> None:
        cores: list[float] = []
        for entry in entries:
            label = (entry.label or "").lower()
            current = entry.current
            if current is None:
                continue
            if "package" in label or "tdie" in label or "tctl" in label:
                reading.cpu_package_temp = round(float(current), 1)
            elif label.startswith("core") or "core" in label:
                cores.append(round(float(current), 1))
        if cores:
            reading.cpu_core_temps = cores
            if reading.cpu_package_temp is None:
                # Approximate package temp as the hottest core.
                reading.cpu_package_temp = max(cores)
        elif reading.cpu_package_temp is None and entries:
            reading.cpu_package_temp = round(float(entries[0].current), 1)

    @staticmethod
    def _first_current(entries, existing: float | None) -> float | None:
        for entry in entries:
            if entry.current is not None:
                return round(float(entry.current), 1)
        return existing

    @staticmethod
    def _thermal_zone_cpu_temp() -> float | None:
        """Fallback: read /sys/class/thermal/thermal_zone*/temp (millidegrees)."""
        base = Path("/sys/class/thermal")
        if not base.is_dir():
            return None
        best: float | None = None
        try:
            for zone in base.glob("thermal_zone*"):
                zone_type = _read_sysfs(str(zone / "type")) or ""
                millideg = _read_int(str(zone / "temp"))
                if millideg is None:
                    continue
                celsius = millideg / 1000.0
                # Prefer x86_pkg_temp / cpu zones, else keep the max.
                if "x86_pkg" in zone_type or "cpu" in zone_type.lower():
                    return round(celsius, 1)
                best = celsius if best is None else max(best, celsius)
        except OSError:
            return best
        return round(best, 1) if best is not None else None

    # ------------------------------------------------------------------ #
    # Fans
    # ------------------------------------------------------------------ #
    def _read_fans(self, reading: HardwareReading) -> None:
        try:
            fans = psutil.sensors_fans()
        except (AttributeError, OSError):
            fans = {}
        speeds: list[float] = []
        for entries in fans.values():
            for entry in entries:
                if entry.current:
                    speeds.append(float(entry.current))
        if speeds:
            reading.fan_speed_rpm = round(max(speeds), 0)

    # ------------------------------------------------------------------ #
    # CPU frequency & utilization
    # ------------------------------------------------------------------ #
    def _read_cpu(self, reading: HardwareReading) -> None:
        try:
            freq = psutil.cpu_freq()
            if freq is not None:
                reading.cpu_frequency_mhz = round(freq.current, 1) if freq.current else None
                reading.cpu_frequency_max_mhz = round(freq.max, 1) if freq.max else None
        except (AttributeError, OSError):
            pass
        try:
            reading.cpu_utilization = round(psutil.cpu_percent(interval=None), 1)
        except OSError:
            pass

    # ------------------------------------------------------------------ #
    # Battery
    # ------------------------------------------------------------------ #
    def _read_battery(self, reading: HardwareReading) -> None:
        try:
            batt = psutil.sensors_battery()
        except (AttributeError, OSError):
            batt = None
        if batt is not None:
            reading.battery_percent = round(float(batt.percent), 1)
            reading.battery_status = "charging" if batt.power_plugged else "discharging"

        # sysfs gives richer info: health, temperature, precise status.
        base = Path("/sys/class/power_supply")
        if not base.is_dir():
            return
        try:
            batteries = [p for p in base.iterdir() if p.name.upper().startswith("BAT")]
        except OSError:
            batteries = []
        for bat in batteries:
            # Health = current full capacity / design capacity.
            full = _read_int(str(bat / "charge_full")) or _read_int(str(bat / "energy_full"))
            design = _read_int(str(bat / "charge_full_design")) or _read_int(
                str(bat / "energy_full_design")
            )
            if full and design:
                reading.battery_health = round(min(100.0, full / design * 100.0), 1)

            # Battery temperature is reported in tenths of a degree Celsius.
            temp_deci = _read_int(str(bat / "temp"))
            if temp_deci is not None:
                reading.battery_temp = round(temp_deci / 10.0, 1)

            status = _read_sysfs(str(bat / "status"))
            if status:
                reading.battery_status = status.lower()
            break  # first battery is sufficient for laptops

    # ------------------------------------------------------------------ #
    # Availability summary
    # ------------------------------------------------------------------ #
    @staticmethod
    def _collect_available(reading: HardwareReading) -> list[str]:
        available: list[str] = []
        mapping = {
            "cpu_package_temp": reading.cpu_package_temp,
            "cpu_core_temps": reading.cpu_core_temps or None,
            "cpu_frequency": reading.cpu_frequency_mhz,
            "gpu_temp": reading.gpu_temp,
            "ssd_temp": reading.ssd_temp,
            "hdd_temp": reading.hdd_temp,
            "motherboard_temp": reading.motherboard_temp,
            "fan_speed": reading.fan_speed_rpm,
            "battery_temp": reading.battery_temp,
            "battery_health": reading.battery_health,
            "battery_status": reading.battery_status,
        }
        for name, value in mapping.items():
            if value is not None:
                available.append(name)
        return available
