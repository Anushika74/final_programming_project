"""Hardware monitoring abstraction layer.

Exposes a platform-agnostic `HardwareMonitor` interface plus a `get_hardware_monitor`
factory. The business layer (services, API, ML) depends only on the interface and
the normalized `HardwareReading`, never on OS-specific details.
"""
from app.hardware.base import HardwareMonitor, HardwareReading
from app.hardware.factory import get_hardware_monitor

__all__ = ["HardwareMonitor", "HardwareReading", "get_hardware_monitor"]
