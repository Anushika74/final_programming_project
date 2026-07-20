"""Seed the hardware_metrics table with realistic synthetic data.

Useful for demos/vivas: it lets the Hardware Health timelines and the ML
thermal forecasts populate immediately instead of waiting hours for real
readings to accumulate.

The generated series is *plausible*, not random noise: CPU temperature follows
load with thermal inertia, the fan ramps up with temperature, frequency drops
during simulated throttling, and SSD/battery temperatures drift gently.

Usage (from the backend directory, venv active):
    python -m scripts.seed_hardware                 # 6 hours, 1-min cadence
    python -m scripts.seed_hardware --hours 48      # two days of data
"""
from __future__ import annotations

import argparse
import math
import random
from datetime import datetime, timedelta, timezone

from app.core.database import SessionLocal, init_db
from app.models.hardware import HardwareMetric


def generate(hours: int, interval_seconds: int) -> list[HardwareMetric]:
    now = datetime.now(timezone.utc)
    total = int(hours * 3600 / interval_seconds)
    start = now - timedelta(seconds=total * interval_seconds)

    rows: list[HardwareMetric] = []
    base_cpu = 48.0
    cpu_temp = base_cpu
    battery_temp = 34.0
    ssd_temp = 40.0
    freq_max = 4000.0

    for i in range(total):
        ts = start + timedelta(seconds=i * interval_seconds)

        # Simulated CPU load: daily-ish sine wave + random bursts.
        phase = math.sin(i / total * math.pi * 6)
        burst = 35.0 if random.random() < 0.05 else 0.0
        load = max(2.0, min(100.0, 30.0 + phase * 25.0 + burst + random.gauss(0, 6)))

        # CPU temperature trends toward a target set by load (thermal inertia).
        target = 45.0 + load * 0.5
        cpu_temp += (target - cpu_temp) * 0.3 + random.gauss(0, 1.0)
        cpu_temp = max(35.0, min(101.0, cpu_temp))

        # Fan ramps with temperature.
        fan = 1200 + max(0.0, cpu_temp - 50.0) * 70 + random.gauss(0, 60)
        fan = max(0.0, round(fan, 0))

        # Frequency: drops when hot (throttling) else near max under load.
        if cpu_temp >= 95:
            freq = freq_max * random.uniform(0.5, 0.65)
        else:
            freq = freq_max * (0.55 + load / 100.0 * 0.45) + random.gauss(0, 50)
        freq = round(max(800.0, min(freq_max, freq)), 0)

        # SSD and battery drift slowly with a little load coupling.
        ssd_temp += (40.0 + load * 0.15 - ssd_temp) * 0.2 + random.gauss(0, 0.5)
        battery_temp += (33.0 + load * 0.08 - battery_temp) * 0.1 + random.gauss(0, 0.3)

        # Per-core temps scatter around the package temperature.
        cores = [round(cpu_temp + random.gauss(0, 1.5), 1) for _ in range(4)]

        rows.append(
            HardwareMetric(
                cpu_package_temp=round(cpu_temp, 1),
                cpu_core_1_temp=cores[0],
                cpu_core_2_temp=cores[1],
                cpu_core_3_temp=cores[2],
                cpu_core_4_temp=cores[3],
                cpu_frequency=freq,
                cpu_utilization=round(load, 1),
                gpu_temp=round(cpu_temp - random.uniform(5, 12), 1),
                motherboard_temp=round(38 + load * 0.1 + random.gauss(0, 1), 1),
                ssd_temp=round(ssd_temp, 1),
                hdd_temp=None,
                fan_speed=fan,
                battery_temp=round(battery_temp, 1),
                battery_health=round(92.0 - i / total * 0.5, 1),  # slow degradation
                battery_percent=round(max(20.0, 100.0 - (i % 600) / 6.0), 1),
                battery_status="discharging",
                timestamp=ts,
            )
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed synthetic hardware metrics")
    parser.add_argument("--hours", type=int, default=6, help="hours of data to generate")
    parser.add_argument("--interval-seconds", type=int, default=60, help="sample cadence")
    args = parser.parse_args()

    init_db()  # ensure tables exist
    rows = generate(args.hours, args.interval_seconds)
    with SessionLocal() as db:
        db.add_all(rows)
        db.commit()
    print(f"Seeded {len(rows)} hardware_metrics rows "
          f"({args.hours}h @ {args.interval_seconds}s).")


if __name__ == "__main__":
    main()
