"""Tests for monitoring, processes and the metric snapshot shape."""
from __future__ import annotations

from app.services.monitoring_service import MonitoringService


def test_collect_snapshot_fields():
    snap = MonitoringService().collect()
    assert 0 <= snap.cpu_usage <= 100
    assert 0 <= snap.memory_usage <= 100
    assert 0 <= snap.disk_usage <= 100
    assert snap.cpu_count >= 1
    assert snap.memory_total_mb > 0


def test_current_metrics_endpoint(client, auth_headers):
    resp = client.get("/api/v1/metrics/current", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "cpu_usage" in body and "memory_usage" in body


def test_process_list_endpoint(client, auth_headers):
    resp = client.get("/api/v1/processes?limit=5", headers=auth_headers)
    assert resp.status_code == 200
    rows = resp.json()
    assert isinstance(rows, list)
    if rows:
        assert {"pid", "name", "cpu_usage", "memory_usage"}.issubset(rows[0].keys())


def test_dashboard_summary(client, auth_headers):
    resp = client.get("/api/v1/dashboard/summary", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "metrics" in body and "stats" in body
