"""Platform-agnostic hardware monitoring interface and normalized reading.

`HardwareReading` is the single normalized data structure every monitor must
produce. Any sensor that is unavailable on the host is represented as ``None``
so downstream code (storage, charts, ML) can treat it uniformly and store NULL.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class HardwareReading:
    """A single, normalized snapshot of hardware sensors.

    Every temperature is expressed in degrees Celsius, frequency in MHz, and fan
    speed in RPM. Unavailable sensors are ``None``.
    """

    # CPU
    cpu_package_temp: float | None = None
    cpu_core_temps: list[float] = field(default_factory=list)
    cpu_frequency_mhz: float | None = None
    cpu_frequency_max_mhz: float | None = None
    cpu_utilization: float | None = None

    # Other components
    gpu_temp: float | None = None
    motherboard_temp: float | None = None
    ssd_temp: float | None = None
    hdd_temp: float | None = None

    # Cooling
    fan_speed_rpm: float | None = None

    # Battery
    battery_temp: float | None = None
    battery_health: float | None = None      # percent (full / design capacity)
    battery_percent: float | None = None
    battery_status: str | None = None        # charging | discharging | full | unknown

    # Meta
    available_sensors: list[str] = field(default_factory=list)
    source: str = "unknown"                  # which backend produced the reading
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def core_temp(self, index: int) -> float | None:
        """Return the temperature of CPU core `index` (0-based) or None."""
        if 0 <= index < len(self.cpu_core_temps):
            return self.cpu_core_temps[index]
        return None


class HardwareMonitor(ABC):
    """Abstract hardware monitor. One concrete implementation per platform."""

    #: Human-readable platform name, e.g. "linux".
    platform: str = "abstract"

    @abstractmethod
    def read(self) -> HardwareReading:
        """Collect a single normalized hardware reading.

        Implementations MUST NOT raise on missing sensors; they should return
        ``None`` for anything unavailable.
        """
        raise NotImplementedError

    @abstractmethod
    def detect_sensors(self) -> list[str]:
        """Return the list of sensor names available on this host."""
        raise NotImplementedError

    def is_supported(self) -> bool:
        """Whether this monitor can run on the current host."""
        return True
