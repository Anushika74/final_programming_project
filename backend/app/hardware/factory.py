"""Factory that returns the appropriate HardwareMonitor for the current host.

The rest of the application depends on this factory rather than a concrete
monitor, so new platforms (Windows, macOS) can be supported by adding a class
and one branch here — no changes to services, API or ML code.
"""
from __future__ import annotations

import logging
import platform
from functools import lru_cache

from app.hardware.base import HardwareMonitor
from app.hardware.fallback import FallbackHardwareMonitor
from app.hardware.linux import LinuxHardwareMonitor

logger = logging.getLogger(__name__)


@lru_cache
def get_hardware_monitor() -> HardwareMonitor:
    """Return a cached HardwareMonitor suitable for this operating system."""
    system = platform.system().lower()

    if system == "linux":
        monitor = LinuxHardwareMonitor()
        if monitor.is_supported():
            logger.info("Using LinuxHardwareMonitor for hardware sensors")
            return monitor

    # Placeholder branches for future platform-specific monitors:
    # if system == "windows":
    #     return WindowsHardwareMonitor()
    # if system == "darwin":
    #     return MacHardwareMonitor()

    logger.warning(
        "No dedicated hardware monitor for '%s'; using psutil fallback", system
    )
    return FallbackHardwareMonitor()
