"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-01-01 00:00:00.000000

This baseline migration creates all SystemIQ tables. It mirrors the SQLAlchemy
models; you can regenerate subsequent migrations with
``alembic revision --autogenerate -m "<message>"``.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_user_role = sa.Enum("ADMIN", "USER", name="userrole")
_severity = sa.Enum("INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL", name="severity")
_metric_type = sa.Enum("CPU", "MEMORY", "DISK", "NETWORK", name="metrictype")
_alert_type = sa.Enum("CPU", "MEMORY", "DISK", "NETWORK", "SYSTEM", name="alerttype")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(64), nullable=False, unique=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", _user_role, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "system_metrics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cpu_usage", sa.Float(), nullable=False),
        sa.Column("memory_usage", sa.Float(), nullable=False),
        sa.Column("disk_usage", sa.Float(), nullable=False),
        sa.Column("network_sent", sa.Float(), nullable=False, server_default="0"),
        sa.Column("network_recv", sa.Float(), nullable=False, server_default="0"),
        sa.Column("load_avg_1m", sa.Float(), nullable=False, server_default="0"),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_system_metrics_timestamp", "system_metrics", ["timestamp"])

    op.create_table(
        "processes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("process_name", sa.String(255), nullable=False),
        sa.Column("pid", sa.Integer(), nullable=False),
        sa.Column("cpu_usage", sa.Float(), nullable=False, server_default="0"),
        sa.Column("memory_usage", sa.Float(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False, server_default="unknown"),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "predictions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("metric_type", _metric_type, nullable=False),
        sa.Column("predicted_value", sa.Float(), nullable=False),
        sa.Column("horizon_minutes", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("model_name", sa.String(64), nullable=False, server_default="unknown"),
        sa.Column("prediction_time", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "recommendations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=False),
        sa.Column("category", sa.String(64), nullable=False, server_default="general"),
        sa.Column("severity", _severity, nullable=False),
        sa.Column("suggested_action", sa.String(64), nullable=True),
        sa.Column("acknowledged", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("alert_type", _alert_type, nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("severity", _severity, nullable=False),
        sa.Column("value", sa.Float(), nullable=False, server_default="0"),
        sa.Column("threshold", sa.Float(), nullable=False, server_default="0"),
        sa.Column("resolved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(255), nullable=False, server_default="system"),
        sa.Column("raw_log", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("category", sa.String(64), nullable=False, server_default="info"),
        sa.Column("severity", _severity, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("logs")
    op.drop_table("alerts")
    op.drop_table("recommendations")
    op.drop_table("predictions")
    op.drop_table("processes")
    op.drop_index("ix_system_metrics_timestamp", table_name="system_metrics")
    op.drop_table("system_metrics")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
