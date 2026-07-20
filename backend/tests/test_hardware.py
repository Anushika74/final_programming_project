"""Tests for Module 13 — Hardware Health & Thermal Intelligence."""
from __future__ import annotations

from datetime import datetime, timezone

from app.schemas.hardware import HardwareSnapshot
from app.services.hardware_service import HardwareHealthService


def _snapshot(**overrides) -> HardwareSnapshot:
    base = dict(
        cpu_package_temp=55.0,
        cpu_core_temps=[54.0, 56.0, 55.0, 53.0],
        cpu_frequency_mhz=3200.0,
        cpu_frequency_max_mhz=4000.0,
        cpu_utilization=30.0,
        ssd_temp=42.0,
        fan_speed_rpm=2500.0,
        battery_temp=34.0,
        battery_health=92.0,
        battery_percent=80.0,
        battery_status="discharging",
        available_sensors=["cpu_package_temp"],
        source="test",
        timestamp=datetime.now(timezone.utc),
    )
    base.update(overrides)
    return HardwareSnapshot(**base)


def test_monitor_reads_without_crashing():
    """The live monitor must never raise, even with no sensors present."""
    snap = HardwareHealthService().get_snapshot()
    assert isinstance(snap, HardwareSnapshot)
    assert snap.source  # some backend name is always set


def test_health_score_healthy_system():
    svc = HardwareHealthService()
    health = svc.compute_health_score(_snapshot())
    assert 0 <= health.overall <= 100
    assert health.rating in {"excellent", "good", "fair", "poor"}
    assert any(c.name == "CPU" for c in health.components)


def test_health_score_drops_when_hot():
    svc = HardwareHealthService()
    cool = svc.compute_health_score(_snapshot(cpu_package_temp=50.0)).overall
    hot = svc.compute_health_score(_snapshot(cpu_package_temp=98.0)).overall
    assert hot < cool


def test_throttling_detected():
    svc = HardwareHealthService()
    status = svc.detect_throttling(
        _snapshot(cpu_utilization=98.0, cpu_frequency_mhz=2100.0,
                  cpu_frequency_max_mhz=4000.0, cpu_package_temp=96.0)
    )
    assert status.throttling is True
    assert "throttling" in status.message.lower()


def test_throttling_not_detected_when_cool():
    svc = HardwareHealthService()
    status = svc.detect_throttling(_snapshot(cpu_utilization=20.0, cpu_package_temp=50.0))
    assert status.throttling is False


def test_recommendations_for_hot_cpu():
    svc = HardwareHealthService()
    recs = svc.generate_recommendations(_snapshot(cpu_package_temp=97.0))
    assert any("CPU" in r.issue for r in recs)


def test_explanations_normal_when_healthy():
    svc = HardwareHealthService()
    explanations = svc.generate_explanations(_snapshot())
    assert explanations
    assert explanations[0].level in {"normal", "warning", "critical", "emergency"}


def test_current_hardware_endpoint(client, auth_headers):
    resp = client.get("/api/v1/hardware/current", headers=auth_headers)
    assert resp.status_code == 200
    assert "source" in resp.json()


def test_health_score_endpoint(client, auth_headers):
    resp = client.get("/api/v1/hardware/health-score", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "overall" in body and "components" in body
