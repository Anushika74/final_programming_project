"""Seed the system_metrics table with realistic synthetic data.

Lets the Analytics trends and the resource ML forecasts populate immediately for
demos/vivas, instead of waiting for real readings to accumulate.

Usage (from the backend directory, venv active):
    python -m scripts.seed_metrics                 # 6 hours, 1-min cadence
    python -m scripts.seed_metrics --hours 48
"""
from __future__ import annotations

import argparse
import math
import random
from datetime import datetime, timedelta, timezone

from app.core.database import SessionLocal, init_db
from app.models.metric import SystemMetric


def generate(hours: int, interval_seconds: int) -> list[SystemMetric]:
    now = datetime.now(timezone.utc)
    total = int(hours * 3600 / interval_seconds)
    start = now - timedelta(seconds=total * interval_seconds)

    rows: list[SystemMetric] = []
    cpu = 25.0
    mem = 45.0
    disk = 55.0  # slowly creeping upward to make disk-growth forecasts meaningful

    for i in range(total):
        ts = start + timedelta(seconds=i * interval_seconds)

        # CPU: daily-ish sine wave + random bursts + inertia.
        phase = math.sin(i / total * math.pi * 8)
        burst = 40.0 if random.random() < 0.06 else 0.0
        target_cpu = max(3.0, min(100.0, 28.0 + phase * 22.0 + burst + random.gauss(0, 5)))
        cpu += (target_cpu - cpu) * 0.4
        cpu = max(1.0, min(100.0, cpu))

        # Memory drifts slowly with small steps.
        mem += random.gauss(0, 0.6) + (0.3 if random.random() < 0.1 else 0)
        mem = max(20.0, min(95.0, mem))

        # Disk creeps up very slowly (good for the 7-day disk forecast).
        disk += 0.0008 + random.gauss(0, 0.02)
        disk = max(10.0, min(99.0, disk))

        load = round(cpu / 100.0 * 4.0 + random.gauss(0, 0.2), 2)
        net_sent = max(0.0, random.gauss(50_000, 30_000) * (cpu / 50.0))
        net_recv = max(0.0, random.gauss(120_000, 60_000) * (cpu / 50.0))

        rows.append(
            SystemMetric(
                cpu_usage=round(cpu, 1),
                memory_usage=round(mem, 1),
                disk_usage=round(disk, 1),
                network_sent=round(net_sent, 1),
                network_recv=round(net_recv, 1),
                load_avg_1m=max(0.0, load),
                timestamp=ts,
            )
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed synthetic system metrics")
    parser.add_argument("--hours", type=int, default=6, help="hours of data to generate")
    parser.add_argument("--interval-seconds", type=int, default=60, help="sample cadence")
    args = parser.parse_args()

    init_db()
    rows = generate(args.hours, args.interval_seconds)
    with SessionLocal() as db:
        db.add_all(rows)
        db.commit()
    print(f"Seeded {len(rows)} system_metrics rows "
          f"({args.hours}h @ {args.interval_seconds}s).")


if __name__ == "__main__":
    main()
