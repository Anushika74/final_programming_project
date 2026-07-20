"""hardware metrics table (Module 13)

Revision ID: 0002_hardware
Revises: 0001_initial
Create Date: 2026-02-01 00:00:00.000000

Adds the hardware_metrics time-series table for the Hardware Health & Thermal
Intelligence module. All sensor columns are nullable so hosts that lack a
particular sensor simply store NULL.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_hardware"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hardware_metrics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cpu_package_temp", sa.Float(), nullable=True),
        sa.Column("cpu_core_1_temp", sa.Float(), nullable=True),
        sa.Column("cpu_core_2_temp", sa.Float(), nullable=True),
        sa.Column("cpu_core_3_temp", sa.Float(), nullable=True),
        sa.Column("cpu_core_4_temp", sa.Float(), nullable=True),
        sa.Column("cpu_frequency", sa.Float(), nullable=True),
        sa.Column("cpu_utilization", sa.Float(), nullable=True),
        sa.Column("gpu_temp", sa.Float(), nullable=True),
        sa.Column("motherboard_temp", sa.Float(), nullable=True),
        sa.Column("ssd_temp", sa.Float(), nullable=True),
        sa.Column("hdd_temp", sa.Float(), nullable=True),
        sa.Column("fan_speed", sa.Float(), nullable=True),
        sa.Column("battery_temp", sa.Float(), nullable=True),
        sa.Column("battery_health", sa.Float(), nullable=True),
        sa.Column("battery_percent", sa.Float(), nullable=True),
        sa.Column("battery_status", sa.String(32), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_hardware_metrics_timestamp", "hardware_metrics", ["timestamp"])


def downgrade() -> None:
    op.drop_index("ix_hardware_metrics_timestamp", table_name="hardware_metrics")
    op.drop_table("hardware_metrics")
