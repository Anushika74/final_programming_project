"""Generic psutil-based monitor used on platforms without a dedicated monitor.

Provides whatever psutil can expose (CPU frequency/utilization, battery, and
temperatures/fans if the OS supports them) so SystemIQ runs everywhere, just
with fewer sensors. A dedicated Windows/Mac monitor can replace this later.
"""
from __future__ import annotations

import psutil

from app.hardware.base import HardwareMonitor, HardwareReading


class FallbackHardwareMonitor(HardwareMonitor):
    platform = "generic"

    def read(self) -> HardwareReading:
        reading = HardwareReading(source="psutil-fallback")
        try:
            temps = psutil.sensors_temperatures()
            for entries in temps.values():
                for entry in entries:
                    if entry.current is not None:
                        reading.cpu_package_temp = round(float(entry.current), 1)
                        break
                if reading.cpu_package_temp is not None:
                    break
        except (AttributeError, OSError):
            pass

        try:
            freq = psutil.cpu_freq()
            if freq:
                reading.cpu_frequency_mhz = round(freq.current, 1) if freq.current else None
                reading.cpu_frequency_max_mhz = round(freq.max, 1) if freq.max else None
        except (AttributeError, OSError):
            pass

        try:
            reading.cpu_utilization = round(psutil.cpu_percent(interval=None), 1)
        except OSError:
            pass

        try:
            batt = psutil.sensors_battery()
            if batt is not None:
                reading.battery_percent = round(float(batt.percent), 1)
                reading.battery_status = "charging" if batt.power_plugged else "discharging"
        except (AttributeError, OSError):
            pass

        reading.available_sensors = [
            name
            for name, value in {
                "cpu_package_temp": reading.cpu_package_temp,
                "cpu_frequency": reading.cpu_frequency_mhz,
                "battery_status": reading.battery_status,
            }.items()
            if value is not None
        ]
        return reading

    def detect_sensors(self) -> list[str]:
        return self.read().available_sensors
